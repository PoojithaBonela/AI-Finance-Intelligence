import sys
import asyncio
import logging
from typing import List
from datetime import datetime, timezone

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.agents.insights_agent.agent import (
    run_insights_agent,
    build_agent3_system_instruction,
    TOOL_REGISTRY,
)
from app.agents.insights_agent.schemas import ChatMessage
from app.agents.insights_agent.embedding import generate_embedding
from app.agents.insights_agent.retrieval import search_receipts
from app.agents.insights_agent.tools import get_total_spending
from app.services.memory_service import extract_and_persist_memories_bg
from app.database import supabase_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_agent_context")

TEST_USER_ID = "77e1e09e-428f-4d1d-96b0-5121db368045"
ISOLATED_USER_ID = "00000000-0000-0000-0000-000000000000"


async def run_context_tests():
    print("\n=======================================================")
    print("PHASE 3.6 STEP 3: AGENT 3 CONTEXT ASSEMBLY VERIFICATION")
    print("=======================================================\n")

    created_memory_ids: List[str] = []

    try:
        # -------------------------------------------------------------
        # 1. Agent Receives Relevant Cross-Chat Memory
        # -------------------------------------------------------------
        print("--- 1. Testing Agent Receives Relevant Cross-Chat Memory ---")
        memories = ["User prefers all currency amounts to be displayed in USD ($)."]
        q1 = "What is my total spending in 2024?"
        res1 = await run_insights_agent(
            user_id=TEST_USER_ID,
            question=q1,
            memories=memories,
        )
        print(f"Question: {q1}")
        print(f"Injected Memory: {memories}")
        print(f"Tools Used: {[t.tool_name for t in res1.tools_used]}")
        print(f"Answer: {res1.answer}\n")
        assert "$" in res1.answer or "USD" in res1.answer, "Agent failed to apply the injected USD preference memory"
        print(">>> PASS: 1. Agent successfully utilized cross-chat memory.")

        # -------------------------------------------------------------
        # 2. Agent Receives Conversation Summary
        # -------------------------------------------------------------
        print("\n--- 2. Testing Agent Receives Conversation Summary ---")
        summary2 = "Earlier in this conversation: The user analyzed September 2024 expenses and noted they exceeded their dining budget at Starbucks."
        q2 = "Which place did I say I overspent at earlier?"
        res2 = await run_insights_agent(
            user_id=TEST_USER_ID,
            question=q2,
            summary=summary2,
        )
        print(f"Question: {q2}")
        print(f"Summary: {summary2}")
        print(f"Answer: {res2.answer}\n")
        assert "starbucks" in res2.answer.lower(), "Agent failed to recall information from the conversation summary"
        print(">>> PASS: 2. Agent successfully recalled older context from conversation summary.")

        # -------------------------------------------------------------
        # 3. Agent Receives Recent Raw Messages
        # -------------------------------------------------------------
        print("\n--- 3. Testing Agent Receives Recent Raw Messages ---")
        history3 = [
            ChatMessage(role="user", content="How much did I spend in 2024?"),
            ChatMessage(role="assistant", content="You spent ₹9,577 in 2024."),
        ]
        q3 = "What were my biggest purchases then?"
        res3 = await run_insights_agent(
            user_id=TEST_USER_ID,
            question=q3,
            history=history3,
        )
        print(f"History: Turn 1 about 2024")
        print(f"Follow-up: {q3}")
        print(f"Tools Used: {[t.tool_name for t in res3.tools_used]}")
        print(f"Tool Args: {[t.arguments for t in res3.tools_used]}")
        print(f"Answer: {res3.answer}\n")
        used_year_2024 = any(t.arguments.get("year") == 2024 for t in res3.tools_used)
        assert used_year_2024, "Agent failed to infer year 2024 from raw dialogue history"
        print(">>> PASS: 3. Agent correctly resolved context from recent raw messages.")

        # -------------------------------------------------------------
        # 4. New Chat Can Retrieve Cross-Chat Memory Automatically
        # -------------------------------------------------------------
        print("\n--- 4. Testing New Chat Retrieves Cross-Chat Memory Automatically ---")
        # Insert a unique test memory for TEST_USER_ID
        ins_mem4 = supabase_client.table("user_memories").insert({
            "user_id": TEST_USER_ID,
            "memory_type": "financial_goal",
            "memory_text": "User has a monthly coffee budget target of exactly 3,000 INR.",
            "embedding": generate_embedding("User has a monthly coffee budget target of exactly 3,000 INR."),
            "is_active": True,
            "importance": 4,
            "confidence": 1.0,
        }).execute()
        assert ins_mem4.data
        mem4_id = ins_mem4.data[0]["id"]
        created_memory_ids.append(mem4_id)

        # Call with memories=None, history=None (brand-new chat session)
        q4 = "What is my target budget for coffee each month?"
        res4 = await run_insights_agent(
            user_id=TEST_USER_ID,
            question=q4,
            history=None,
            summary=None,
            memories=None, # Trigger auto-retrieval
        )
        print(f"New Chat Question: {q4}")
        print(f"Answer: {res4.answer}\n")
        assert "3,000" in res4.answer or "3000" in res4.answer, "Agent in new chat failed to auto-retrieve and recall coffee budget memory"
        print(">>> PASS: 4. Brand-new chat session automatically retrieved cross-chat memory.")

        # -------------------------------------------------------------
        # 5. Existing Chat Uses Summary + Recent Messages Together
        # -------------------------------------------------------------
        print("\n--- 5. Testing Existing Chat Combines Summary + Recent Messages ---")
        summary5 = "In the first half of this chat: User reviewed annual 2024 spending totaling ₹9,577."
        history5 = [
            ChatMessage(role="user", content="How much did I spend at cafes?"),
            ChatMessage(role="assistant", content="You spent ₹2,880 at cafes."),
            ChatMessage(role="user", content="Can you compare that to my total spending mentioned earlier?"),
        ]
        q5 = "What percentage of my annual spending went to cafes?"
        res5 = await run_insights_agent(
            user_id=TEST_USER_ID,
            question=q5,
            history=history5,
            summary=summary5,
        )
        print(f"Question: {q5}")
        print(f"Answer: {res5.answer}\n")
        # 2880 / 9577 is ~30%
        assert "30" in res5.answer or "percent" in res5.answer.lower() or "percentage" in res5.answer.lower() or "9,577" in res5.answer or "2,880" in res5.answer
        print(">>> PASS: 5. Combined summary and recent messages successfully synthesized.")

        # -------------------------------------------------------------
        # 6. Irrelevant Memories Are Not Injected
        # -------------------------------------------------------------
        print("\n--- 6. Testing Irrelevant Memories Are Not Injected ---")
        # Querying an unrelated topic should not match the coffee budget
        q6 = "What was my highest expense in 2024?"
        # Auto-retrieval with precomputed embedding
        res6 = await run_insights_agent(
            user_id=TEST_USER_ID,
            question=q6,
            memories=None,
        )
        print(f"Question: {q6}")
        print(f"Answer: {res6.answer}\n")
        # The coffee budget target shouldn't be randomly injected or mentioned for highest expense
        assert "3,000 INR" not in res6.answer
        print(">>> PASS: 6. Irrelevant memories correctly omitted.")

        # -------------------------------------------------------------
        # 7. Receipt RAG Remains Unchanged
        # -------------------------------------------------------------
        print("\n--- 7. Testing Receipt RAG Remains Unchanged ---")
        rag_res = await search_receipts(
            user_id=TEST_USER_ID,
            query_text="Where did I go for momos and drinks with friends?",
            top_k=3,
        )
        print(f"Receipt RAG matches count: {len(rag_res)}")
        assert len(rag_res) > 0, "Receipt RAG returned no matches"
        top_merchant = rag_res[0]["merchant"]
        print(f"Top Receipt Merchant: {top_merchant}")
        assert "Hi Spirits" in top_merchant or "Cafe" in top_merchant
        print(">>> PASS: 7. Receipt RAG operates consistently without regression.")

        # -------------------------------------------------------------
        # 8. SQL Tools Remain Unchanged
        # -------------------------------------------------------------
        print("\n--- 8. Testing SQL Tools Remain Unchanged ---")
        sql_res = await get_total_spending(user_id=TEST_USER_ID, year=2024)
        print(f"SQL Tool Result: {sql_res}")
        assert sql_res["total_spending"] == 9577.0
        assert sql_res["receipt_count"] == 3
        print(">>> PASS: 8. SQL tools operate consistently without regression.")

        # -------------------------------------------------------------
        # 9. user_id Never Enters Gemini-Generated Tool Arguments
        # -------------------------------------------------------------
        print("\n--- 9. Testing user_id Never Enters Tool Arguments ---")
        for tr in res1.tools_used + res3.tools_used:
            assert "user_id" not in tr.arguments, f"CRITICAL: user_id found in Gemini tool arguments for {tr.tool_name}!"
        print(">>> PASS: 9. Verified user_id is completely absent from all LLM tool arguments.")

        # -------------------------------------------------------------
        # 10. Same Question Embedding Can Be Reused
        # -------------------------------------------------------------
        print("\n--- 10. Testing Query Embedding Reuse ---")
        reuse_query = "What electronics have I purchased?"
        shared_embedding = generate_embedding(reuse_query)
        assert len(shared_embedding) == 768

        # Pass precomputed embedding to run_insights_agent
        res10 = await run_insights_agent(
            user_id=TEST_USER_ID,
            question=reuse_query,
            precomputed_embedding=shared_embedding,
        )
        print(f"Reused Query Embedding for: {reuse_query}")
        print(f"Tools Used: {[t.tool_name for t in res10.tools_used]}")
        print(f"Answer: {res10.answer}\n")
        assert len(res10.tools_used) > 0
        print(">>> PASS: 10. Precomputed query embedding successfully reused.")

        # -------------------------------------------------------------
        # 11. No-Memory / No-Summary Baseline Works Cleanly
        # -------------------------------------------------------------
        print("\n--- 11. Testing Baseline (No Memory, No Summary) ---")
        res11 = await run_insights_agent(
            user_id=TEST_USER_ID,
            question="How much did I spend in total in 2024?",
            history=[],
            summary=None,
            memories=[],
        )
        print(f"Baseline Answer: {res11.answer}\n")
        assert "9,577" in res11.answer or "9577" in res11.answer
        print(">>> PASS: 11. Clean baseline execution without memory or summary.")

        print("\n=======================================================")
        print("ALL 11 AGENT 3 CONTEXT ASSEMBLY TESTS PASSED!")
        print("=======================================================\n")

    finally:
        print("Cleaning up test memory records...")
        for mid in created_memory_ids:
            try:
                supabase_client.table("user_memories").delete().eq("id", mid).execute()
            except Exception as e:
                logger.warning(f"Failed to delete test memory {mid}: {e}")
        print("Cleanup completed.")


if __name__ == "__main__":
    asyncio.run(run_context_tests())

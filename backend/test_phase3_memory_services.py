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
from app.services.memory_service import (
    retrieve_user_memories,
    extract_memories_from_text,
    extract_and_persist_memories_bg,
)
from app.services.summary_service import update_conversation_summary_bg
from app.agents.insights_agent.embedding import generate_embedding
from app.database import supabase_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_memory_services")

TEST_USER_ID = "77e1e09e-428f-4d1d-96b0-5121db368045"
ISOLATED_USER_ID = "00000000-0000-0000-0000-000000000000"


async def run_memory_tests():
    print("\n=======================================================")
    print("PHASE 3.6 STEP 2: MEMORY & SUMMARY SERVICES VERIFICATION")
    print("=======================================================\n")

    created_memory_ids: List[str] = []
    created_conversation_ids: List[str] = []

    try:
        # -------------------------------------------------------------
        # 1. Relevant Memory Retrieval
        # -------------------------------------------------------------
        print("--- 1. Testing Relevant Memory Retrieval ---")
        pref_text = "User explicitly prefers viewing all personal finance reports in INR currency."
        emb1 = generate_embedding(pref_text)
        res_ins1 = supabase_client.table("user_memories").insert({
            "user_id": TEST_USER_ID,
            "memory_type": "preference",
            "memory_text": pref_text,
            "embedding": emb1,
            "is_active": True,
            "importance": 4,
            "confidence": 1.0,
        }).execute()
        assert res_ins1.data, "Failed to insert test memory"
        mem1_id = res_ins1.data[0]["id"]
        created_memory_ids.append(mem1_id)

        retrieved1 = await retrieve_user_memories(
            user_id=TEST_USER_ID,
            query_text="What currency should you use for my reports?",
            match_threshold=0.60
        )
        print(f"Retrieved memories count: {len(retrieved1)}")
        assert len(retrieved1) > 0, "Expected at least 1 memory retrieved"
        match_texts = [m["memory_text"] for m in retrieved1]
        assert any("INR currency" in t for t in match_texts), f"Expected INR memory in results: {match_texts}"
        print(f">>> PASS: 1. Relevant memory retrieved (similarity={retrieved1[0]['similarity']:.4f}).")

        # -------------------------------------------------------------
        # 2. User Isolation
        # -------------------------------------------------------------
        print("\n--- 2. Testing User Isolation ---")
        retrieved_iso = await retrieve_user_memories(
            user_id=ISOLATED_USER_ID,
            query_text="What currency should you use for my reports?",
            match_threshold=0.60
        )
        print(f"Isolated user retrieved count: {len(retrieved_iso)}")
        assert len(retrieved_iso) == 0, "Cross-user memory leak detected!"
        print(">>> PASS: 2. Cross-user isolation strictly enforced.")

        # -------------------------------------------------------------
        # 3. Empty Memory Result
        # -------------------------------------------------------------
        print("\n--- 3. Testing Empty Memory Result ---")
        empty_res = await retrieve_user_memories(
            user_id=TEST_USER_ID,
            query_text="How do quantum computers calculate prime factorizations in physics?",
            match_threshold=0.85
        )
        assert len(empty_res) == 0, f"Expected 0 results for unrelated query, got {len(empty_res)}"
        print(">>> PASS: 3. Unrelated queries return empty list cleanly.")

        # -------------------------------------------------------------
        # 4. Explicit Preference Extraction
        # -------------------------------------------------------------
        print("\n--- 4. Testing Explicit Preference Extraction ---")
        user_msg4 = "Please always display all of my spending totals and charts in USD."
        asst_msg4 = "Understood. I will display all your future spending totals and charts in USD."
        extracted4 = extract_memories_from_text(user_msg4, asst_msg4)
        print(f"Extracted memories: {extracted4}")
        assert len(extracted4) >= 1, "Failed to extract explicit user preference"
        cand4 = extracted4[0]
        assert cand4["memory_type"] == "preference"
        assert "usd" in cand4["memory_text"].lower()
        print(">>> PASS: 4. Explicit preference extracted with correct category.")

        # -------------------------------------------------------------
        # 5. Explicit Financial Goal Extraction
        # -------------------------------------------------------------
        print("\n--- 5. Testing Explicit Financial Goal Extraction ---")
        user_msg5 = "I am setting a strict monthly dining budget limit of 15000 INR starting this month."
        asst_msg5 = "I have noted your monthly dining budget of 15,000 INR."
        extracted5 = extract_memories_from_text(user_msg5, asst_msg5)
        print(f"Extracted goals: {extracted5}")
        assert len(extracted5) >= 1, "Failed to extract explicit financial goal"
        cand5 = extracted5[0]
        assert cand5["memory_type"] == "financial_goal"
        assert "15000" in cand5["memory_text"] or "15,000" in cand5["memory_text"]
        print(">>> PASS: 5. Explicit financial goal extracted accurately.")

        # -------------------------------------------------------------
        # 6. Transient Question Ignored
        # -------------------------------------------------------------
        print("\n--- 6. Testing Transient Question Ignored ---")
        user_msg6 = "How much did I spend on groceries yesterday?"
        asst_msg6 = "You spent ₹1,450 on groceries at PB Swalayan yesterday."
        extracted6 = extract_memories_from_text(user_msg6, asst_msg6)
        print(f"Extracted from transient query: {extracted6}")
        assert len(extracted6) == 0, f"Transient query should produce 0 memories, got {extracted6}"
        print(">>> PASS: 6. Transient question ignored without creating memories.")

        # -------------------------------------------------------------
        # 7. Unsupported Inference Ignored
        # -------------------------------------------------------------
        print("\n--- 7. Testing Unsupported Assistant Inference Ignored ---")
        user_msg7 = "Can you show me my receipt from Starbucks?"
        asst_msg7 = "Here is your Starbucks receipt for ₹420. Based on this, you clearly have a severe coffee addiction and visit cafes 5 times a week!"
        extracted7 = extract_memories_from_text(user_msg7, asst_msg7)
        print(f"Extracted from assistant inference: {extracted7}")
        assert len(extracted7) == 0, f"Assistant inference without user confirmation must produce 0 memories, got {extracted7}"
        print(">>> PASS: 7. Unsupported assistant inference ignored.")

        # -------------------------------------------------------------
        # 8. Memory Embedding Dimension = 768
        # -------------------------------------------------------------
        print("\n--- 8. Testing Memory Embedding Dimension = 768 ---")
        test_vector = generate_embedding("User is saving for a new laptop in December.")
        assert len(test_vector) == 768, f"Expected vector length 768, got {len(test_vector)}"
        print(">>> PASS: 8. Embedding dimension verified exactly 768.")

        # -------------------------------------------------------------
        # 9. Duplicate Memory Detection
        # -------------------------------------------------------------
        print("\n--- 9. Testing Duplicate Memory Detection ---")
        dup_text = "User prefers concise weekly spending summaries with bullet points."
        # First insertion
        res_dup1 = await extract_and_persist_memories_bg(
            user_id=TEST_USER_ID,
            conversation_id=None,
            user_message="I prefer concise weekly spending summaries with bullet points.",
            assistant_message="Understood."
        )
        assert len(res_dup1) > 0, "First memory extraction should succeed"
        dup_id1 = res_dup1[0]["id"]
        created_memory_ids.append(dup_id1)

        # Count active preference memories with this text
        before_count_res = supabase_client.table("user_memories").select("id").eq("user_id", TEST_USER_ID).eq("is_active", True).execute()
        before_count = len(before_count_res.data or [])

        # Second insertion of near-identical preference
        res_dup2 = await extract_and_persist_memories_bg(
            user_id=TEST_USER_ID,
            conversation_id=None,
            user_message="I prefer concise weekly spending summaries with bullet points.",
            assistant_message="Got it."
        )
        after_count_res = supabase_client.table("user_memories").select("id").eq("user_id", TEST_USER_ID).eq("is_active", True).execute()
        after_count = len(after_count_res.data or [])

        assert after_count == before_count, f"Duplicate memory created! before={before_count}, after={after_count}"
        print(f">>> PASS: 9. Duplicate memory detected; active count remained {after_count}.")

        # -------------------------------------------------------------
        # 10. Conflicting Memory Deactivation
        # -------------------------------------------------------------
        print("\n--- 10. Testing Conflicting Memory Deactivation ---")
        # Step A: Insert initial budget goal
        res_conflict_a = await extract_and_persist_memories_bg(
            user_id=TEST_USER_ID,
            conversation_id=None,
            user_message="My monthly coffee budget is set to ₹2,000 for this year.",
            assistant_message="Noted: ₹2,000 monthly coffee budget."
        )
        assert len(res_conflict_a) > 0
        old_goal_id = res_conflict_a[0]["id"]
        created_memory_ids.append(old_goal_id)

        # Step B: User updates the budget
        res_conflict_b = await extract_and_persist_memories_bg(
            user_id=TEST_USER_ID,
            conversation_id=None,
            user_message="I decided to change my monthly coffee budget, it is now ₹4,500.",
            assistant_message="Updated: your monthly coffee budget is now ₹4,500."
        )
        assert len(res_conflict_b) > 0
        new_goal_id = res_conflict_b[0]["id"]
        created_memory_ids.append(new_goal_id)

        # Verify old memory is deactivated
        old_mem_check = supabase_client.table("user_memories").select("id, is_active, memory_text").eq("id", old_goal_id).execute()
        assert old_mem_check.data and old_mem_check.data[0]["is_active"] is False, "Old conflicting memory was not deactivated!"

        # Verify new memory is active
        new_mem_check = supabase_client.table("user_memories").select("id, is_active, memory_text").eq("id", new_goal_id).execute()
        assert new_mem_check.data and new_mem_check.data[0]["is_active"] is True, "New updated memory is not active!"
        print(f">>> PASS: 10. Conflicting memory deactivated (old={old_goal_id} active=False, new={new_goal_id} active=True).")

        # -------------------------------------------------------------
        # 11. Conversation Summary Generation
        # -------------------------------------------------------------
        print("\n--- 11. Testing Conversation Summary Generation (> 10 messages) ---")
        # Create a conversation with 12 messages
        conv_res = supabase_client.table("conversations").insert({
            "user_id": TEST_USER_ID,
            "title": "[TEST_MEMORY] September Budget Discussion",
        }).execute()
        assert conv_res.data
        conv_id = conv_res.data[0]["id"]
        created_conversation_ids.append(conv_id)

        # Insert 12 messages sequentially
        dialogue = [
            ("user", "Can you review my total spending in September 2024?"),
            ("assistant", "In September 2024, you spent a total of ₹31,000 across 4 receipts."),
            ("user", "What was the largest expense in that month?"),
            ("assistant", "Your largest expense was ₹18,500 at Apple Store for AirPods Pro."),
            ("user", "Did I buy any books or study materials?"),
            ("assistant", "Yes, you purchased two programming textbooks on Amazon for ₹3,200."),
            ("user", "How much was left from my ₹35,000 monthly target?"),
            ("assistant", "You had ₹4,000 remaining from your ₹35,000 target budget."),
            ("user", "Can you check my dining out expenses as well?"),
            ("assistant", "You spent ₹5,400 on dining across 3 visits to cafes."),
            ("user", "I need to cut down dining expenses next month."),
            ("assistant", "Understood. Setting a lower dining target for October will keep your savings on track."),
        ]

        inserted_messages = []
        for role, text in dialogue:
            m_res = supabase_client.table("messages").insert({
                "conversation_id": conv_id,
                "role": role,
                "content": text,
            }).execute()
            inserted_messages.append(m_res.data[0])

        summary_result = await update_conversation_summary_bg(conv_id, TEST_USER_ID)
        print(f"Generated Summary:\n{summary_result}\n")
        assert summary_result, "Expected non-empty summary for conversation with 12 messages"
        print(">>> PASS: 11. Summary generated for conversation with > 10 messages.")

        # -------------------------------------------------------------
        # 12. Summary Preserves Older Context
        # -------------------------------------------------------------
        print("--- 12. Testing Summary Preserves Older Context ---")
        assert "31,000" in summary_result or "September" in summary_result or "AirPods" in summary_result or "Apple" in summary_result or "Amazon" in summary_result, (
            f"Summary failed to capture key financial facts from older messages: {summary_result}"
        )
        print(">>> PASS: 12. Summary successfully preserved key older financial context.")

        # -------------------------------------------------------------
        # 13. Latest 6 Messages Remain Outside Summary
        # -------------------------------------------------------------
        print("\n--- 13. Testing Latest 6 Messages Outside Summary ---")
        # In a 12-message conversation, messages[0:6] are summarized, messages[6:12] remain raw
        conv_check = supabase_client.table("conversations").select("summary, summarized_through_message_id").eq("id", conv_id).execute()
        summarized_marker = conv_check.data[0]["summarized_through_message_id"]
        # The 6th message is inserted_messages[5] (index 5)
        sixth_msg_id = inserted_messages[5]["id"]
        print(f"summarized_through_message_id: {summarized_marker}, sixth message id: {sixth_msg_id}")
        assert summarized_marker == sixth_msg_id, f"Expected summarized marker {sixth_msg_id}, got {summarized_marker}"
        print(">>> PASS: 13. Exactly the latest 6 messages remain outside the summary window.")

        # -------------------------------------------------------------
        # 14. summarized_through_message_id Advances Correctly
        # -------------------------------------------------------------
        print("\n--- 14. Testing summarized_through_message_id Advances ---")
        # Add 4 more messages (total = 16)
        more_dialogue = [
            ("user", "What was my grocery spending in September?"),
            ("assistant", "Your grocery spending was ₹3,900 at PB Swalayan."),
            ("user", "Okay, please make sure we budget ₹4,000 for groceries in October."),
            ("assistant", "Noted, budgeting ₹4,000 for October groceries."),
        ]
        for role, text in more_dialogue:
            m_res = supabase_client.table("messages").insert({
                "conversation_id": conv_id,
                "role": role,
                "content": text,
            }).execute()
            inserted_messages.append(m_res.data[0])

        # Run summary again: total messages = 16, eligible for summary = 16 - 6 = 10 (index 0..9)
        updated_summary2 = await update_conversation_summary_bg(conv_id, TEST_USER_ID)
        conv_check2 = supabase_client.table("conversations").select("summary, summarized_through_message_id").eq("id", conv_id).execute()
        new_marker = conv_check2.data[0]["summarized_through_message_id"]
        tenth_msg_id = inserted_messages[9]["id"]
        print(f"Advanced marker: {new_marker}, tenth message id: {tenth_msg_id}")
        assert new_marker == tenth_msg_id, f"Expected advanced marker {tenth_msg_id}, got {new_marker}"
        print(">>> PASS: 14. summarized_through_message_id advanced accurately.")

        # -------------------------------------------------------------
        # 15. Summary/Memory Failures Logged Without Crashing
        # -------------------------------------------------------------
        print("\n--- 15. Testing Failure Resilience Without Crashing ---")
        # Non-existent conversation
        fail_summary = await update_conversation_summary_bg("00000000-0000-0000-0000-000000000000", TEST_USER_ID)
        assert fail_summary is None, "Expected None for non-existent conversation"

        # Invalid user_id for memory extraction
        fail_mem = await extract_and_persist_memories_bg("", None, "test", "test")
        assert fail_mem == [], "Expected [] for invalid user_id"
        print(">>> PASS: 15. Graceful handling of invalid requests without crashing.")

        print("\n=======================================================")
        print("ALL 15 MEMORY & SUMMARY SERVICE TESTS PASSED!")
        print("=======================================================\n")

    finally:
        # Cleanup test data
        print("Cleaning up test records from database...")
        for mid in created_memory_ids:
            try:
                supabase_client.table("user_memories").delete().eq("id", mid).execute()
            except Exception as e:
                logger.warning(f"Failed to delete test memory {mid}: {e}")

        for cid in created_conversation_ids:
            try:
                supabase_client.table("conversations").delete().eq("id", cid).execute()
            except Exception as e:
                logger.warning(f"Failed to delete test conversation {cid}: {e}")
        print("Cleanup completed.")


if __name__ == "__main__":
    asyncio.run(run_memory_tests())

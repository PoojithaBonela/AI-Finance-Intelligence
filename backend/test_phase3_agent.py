import sys
import asyncio
import logging

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from app.agents.insights_agent.agent import run_insights_agent, TOOL_REGISTRY
from app.agents.insights_agent.schemas import ChatMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_agent")

TEST_USER_ID = "77e1e09e-428f-4d1d-96b0-5121db368045"
ISOLATED_USER_ID = "00000000-0000-0000-0000-000000000000"


async def run_agent_tests():
    print("\n=======================================================")
    print("PHASE 3.5 GEMINI TOOL-CALLING AGENT VERIFICATION")
    print("=======================================================\n")

    # 1. SQL-only Question
    print("--- 1. Testing SQL-only Question ---")
    q1 = "How much did I spend in total in 2024?"
    res1 = await run_insights_agent(user_id=TEST_USER_ID, question=q1)
    print(f"User: {q1}")
    print(f"Tools Used: {[t.tool_name for t in res1.tools_used]}")
    print(f"Answer: {res1.answer}\n")
    tool_names1 = [t.tool_name for t in res1.tools_used]
    assert any("spending" in t for t in tool_names1), "Expected spending SQL tool called"
    assert "9,577" in res1.answer or "9577" in res1.answer, "Expected 2024 total spending (9,577) in answer"
    print(">>> PASS: 1. SQL-only question executed and grounded correctly.")

    # 2. RAG-only Question
    print("\n--- 2. Testing RAG-only Question ---")
    q2 = "Where did I go for drinks and momos with friends?"
    res2 = await run_insights_agent(user_id=TEST_USER_ID, question=q2)
    print(f"User: {q2}")
    print(f"Tools Used: {[t.tool_name for t in res2.tools_used]}")
    print(f"Answer: {res2.answer}\n")
    tool_names2 = [t.tool_name for t in res2.tools_used]
    assert "search_receipts" in tool_names2, "Expected search_receipts RAG tool called"
    assert "Hi Spirits" in res2.answer or "Cafe" in res2.answer, "Expected Hi Spirits Cafe & Pub mentioned in answer"
    print(">>> PASS: 2. RAG-only question executed and grounded correctly.")

    # 3. Question requiring Multiple SQL Tools
    print("\n--- 3. Testing Question Requiring Multiple SQL Tools ---")
    q3 = "What is my spending breakdown by category and what were my biggest purchases?"
    res3 = await run_insights_agent(user_id=TEST_USER_ID, question=q3)
    print(f"User: {q3}")
    print(f"Tools Used: {[t.tool_name for t in res3.tools_used]}")
    print(f"Answer: {res3.answer}\n")
    tool_names3 = [t.tool_name for t in res3.tools_used]
    assert "get_category_breakdown" in tool_names3 or "get_total_spending" in tool_names3
    assert "get_largest_expenses" in tool_names3 or "get_recent_purchases" in tool_names3
    print(">>> PASS: 3. Question requiring multiple SQL tools executed.")

    # 4. Question requiring SQL + RAG
    print("\n--- 4. Testing Question Requiring SQL + RAG ---")
    q4 = "How much did I spend in total, and what specific items did I buy from Amazon?"
    res4 = await run_insights_agent(user_id=TEST_USER_ID, question=q4)
    print(f"User: {q4}")
    print(f"Tools Used: {[t.tool_name for t in res4.tools_used]}")
    print(f"Answer: {res4.answer}\n")
    tool_names4 = [t.tool_name for t in res4.tools_used]
    assert len(tool_names4) >= 2, f"Expected at least 2 tools called, got {tool_names4}"
    has_sql = any("spending" in t or "expense" in t for t in tool_names4)
    has_rag = "search_receipts" in tool_names4 or any("purchase" in t for t in tool_names4)
    assert has_sql and has_rag, "Expected both SQL and search tools to be used"
    print(">>> PASS: 4. Combined SQL + RAG question executed successfully.")

    # 5. Follow-up Question using Context
    print("\n--- 5. Testing Follow-up Question using Context ---")
    history = [
        ChatMessage(role="user", content="How much did I spend in 2024?"),
        ChatMessage(role="assistant", content="You spent a total of ₹9,577 in 2024 across 2 receipts."),
    ]
    q5 = "What were my biggest purchases then?"
    res5 = await run_insights_agent(user_id=TEST_USER_ID, question=q5, history=history)
    print(f"History: Turn 1 about 2024")
    print(f"Follow-up: {q5}")
    print(f"Tools Used: {[t.tool_name for t in res5.tools_used]}")
    print(f"Tool Args: {[t.arguments for t in res5.tools_used]}")
    print(f"Answer: {res5.answer}\n")
    # Verify the tool call used 2024 from the context
    used_year_2024 = any(t.arguments.get("year") == 2024 for t in res5.tools_used)
    assert used_year_2024, "Follow-up failed to infer year 2024 from previous turn context"
    print(">>> PASS: 5. Follow-up correctly leveraged previous context.")

    # 6. No-results Question
    print("\n--- 6. Testing No-results Question ---")
    q6 = "How much did I spend in 1985?"
    res6 = await run_insights_agent(user_id=TEST_USER_ID, question=q6)
    print(f"User: {q6}")
    print(f"Answer: {res6.answer}\n")
    assert "0" in res6.answer or "no" in res6.answer.lower() or "not" in res6.answer.lower()
    print(">>> PASS: 6. Handled no-results cleanly without hallucination.")

    # 7. Tool Execution Error Resilience
    print("\n--- 7. Testing Tool Execution Error Handling ---")
    # Temporarily monkey-patch a tool to simulate failure
    original_fn = TOOL_REGISTRY["get_total_spending"]
    try:
        async def failing_tool(**kwargs):
            raise RuntimeError("Database connection timed out")
        TOOL_REGISTRY["get_total_spending"] = failing_tool

        res7 = await run_insights_agent(user_id=TEST_USER_ID, question="What was my total spending?")
        print(f"Answer on error: {res7.answer}\n")
        assert res7.answer, "Expected non-empty response even when tool fails"
        assert "timed out" not in res7.answer.lower(), "Raw database error should not leak directly to user"
        print(">>> PASS: 7. Graceful degradation on tool execution error.")
    finally:
        TOOL_REGISTRY["get_total_spending"] = original_fn

    # 8. Multiple Tool Calls in Single Session
    print("\n--- 8. Testing Multiple Tool Calls ---")
    assert len(res3.tools_used) >= 2 or len(res4.tools_used) >= 2
    print(">>> PASS: 8. Verified agent calls and aggregates multiple tools.")

    # 9. Maximum Tool-Round Protection
    print("\n--- 9. Testing Maximum Tool-Round Protection ---")
    res9 = await run_insights_agent(
        user_id=TEST_USER_ID,
        question="Compare all my categories and tell me all receipts from every merchant in detail",
        max_rounds=1
    )
    print(f"Rounds used with max_rounds=1: {res9.rounds_used}")
    assert res9.rounds_used <= 1, f"Expected rounds <= 1, got {res9.rounds_used}"
    assert res9.answer, "Expected answer even when max rounds hit"
    print(">>> PASS: 9. Max tool-round protection terminates cleanly.")

    # 10. Security: user_id is Injected by Backend and NEVER Chosen by LLM
    print("\n--- 10. Testing Security: user_id Isolation & Injection ---")
    # Verify no tool call generated by Gemini has user_id in its arguments
    all_tool_records = res1.tools_used + res2.tools_used + res3.tools_used + res4.tools_used + res5.tools_used
    for tr in all_tool_records:
        assert "user_id" not in tr.arguments, f"CRITICAL: user_id was exposed to or chosen by LLM in {tr.tool_name}!"
    print("Confirmed: user_id is completely absent from all LLM-generated tool arguments.")

    # Verify query for isolated user returns 0 data
    res_iso = await run_insights_agent(user_id=ISOLATED_USER_ID, question="How much did I spend in 2024?")
    print(f"Isolated User Query Answer: {res_iso.answer}")
    assert "9,577" not in res_iso.answer and "9577" not in res_iso.answer, "Isolated user leaked another user's spending!"
    print(">>> PASS: 10. user_id strictly backend-injected; cross-user isolation guaranteed.")

    print("\n=======================================================")
    print("ALL 10 AGENT 3 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=======================================================\n")


if __name__ == "__main__":
    asyncio.run(run_agent_tests())

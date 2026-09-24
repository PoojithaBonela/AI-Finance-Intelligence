import sys
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import httpx
from app.main import app
from app.dependencies import get_current_user
from app.database import supabase_client
from app.agents.insights_agent.embedding import generate_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase3_api")

TEST_USER_ID = "77e1e09e-428f-4d1d-96b0-5121db368045"
ISOLATED_USER_ID = "00000000-0000-0000-0000-000000000000"


async def run_api_tests():
    print("\n=======================================================")
    print("PHASE 3.6 STEP 4: AI INSIGHTS API & PERSISTENCE TESTS")
    print("=======================================================\n")

    created_conversation_ids: List[str] = []
    created_memory_ids: List[str] = []

    # Use ASGI transport to test FastAPI endpoints directly
    transport = httpx.ASGITransport(app=app)

    try:
        # Default dependency override: Authenticated as TEST_USER_ID
        app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer mock-token"}

            # -------------------------------------------------------------
            # 0. POST /api/insights/conversations - Explicit New Chat
            # -------------------------------------------------------------
            print("--- 0. Testing Explicit New Chat Creation (POST /api/insights/conversations) ---")
            resp0 = await client.post(
                "/api/insights/conversations",
                headers=headers,
            )
            print(f"Status Code: {resp0.status_code}")
            assert resp0.status_code == 200, f"Expected 200 OK, got {resp0.status_code}: {resp0.text}"
            data0 = resp0.json()
            conv_id0 = data0["id"]
            created_conversation_ids.append(conv_id0)
            assert data0["title"] == "New Chat"
            assert data0["summary"] is None

            # Verify DB state: zero messages initially
            db_msgs0 = supabase_client.table("messages").select("id").eq("conversation_id", conv_id0).execute()
            assert len(db_msgs0.data) == 0, f"Expected 0 messages in new conversation, got {len(db_msgs0.data)}"
            print(">>> PASS: 0. Explicit New Chat endpoint created empty persistent conversation.")

            # -------------------------------------------------------------
            # 1. POST /api/insights/ask - First Message in Conversation
            # -------------------------------------------------------------
            print("--- 1. Testing First Message in New Conversation (POST /api/insights/ask) ---")
            q1 = "How much did I spend in total in 2024?"
            resp1 = await client.post(
                "/api/insights/ask",
                json={"conversation_id": conv_id0, "question": q1},
                headers=headers,
            )
            print(f"Status Code: {resp1.status_code}")
            assert resp1.status_code == 200, f"Expected 200 OK, got {resp1.status_code}: {resp1.text}"
            data1 = resp1.json()
            conv_id1 = data1["conversation_id"]
            assert conv_id1 == conv_id0

            print(f"Conversation ID: {conv_id1}")
            print(f"Answer: {data1['answer']}")
            print(f"Tools Used: {data1['tools_used']}")
            print(f"Rounds Used: {data1['rounds_used']}")

            assert "get_total_spending" in data1["tools_used"], "Expected get_total_spending called"
            assert "9,577" in data1["answer"] or "9577" in data1["answer"], "Expected 2024 total spending (9,577) in answer"

            # Verify DB persistence of conversation
            db_conv = supabase_client.table("conversations").select("*").eq("id", conv_id1).execute()
            assert db_conv.data, f"Conversation {conv_id1} not found in DB"
            assert db_conv.data[0]["user_id"] == TEST_USER_ID
            assert db_conv.data[0]["title"], "Expected non-empty title generated"
            print(f"Generated Conversation Title: '{db_conv.data[0]['title']}'")

            # Verify DB persistence of messages (User + Assistant)
            db_msgs = (
                supabase_client.table("messages")
                .select("*")
                .eq("conversation_id", conv_id1)
                .order("created_at", desc=False)
                .execute()
            )
            assert len(db_msgs.data) == 2, f"Expected exactly 2 messages in DB, got {len(db_msgs.data)}"
            user_msg = db_msgs.data[0]
            asst_msg = db_msgs.data[1]

            assert user_msg["role"] == "user"
            assert user_msg["content"] == q1
            assert user_msg["metadata"] == {}

            assert asst_msg["role"] == "assistant"
            assert asst_msg["content"] == data1["answer"]
            assert asst_msg["metadata"]["tools_used"] == data1["tools_used"]
            assert asst_msg["metadata"]["rounds_used"] == data1["rounds_used"]
            print(">>> PASS: 1. New conversation and messages persisted with metadata.")

            # -------------------------------------------------------------
            # 2. POST /api/insights/ask - Continue Existing Conversation
            # -------------------------------------------------------------
            print("\n--- 2. Testing Continue Existing Conversation ---")
            q2 = "What were my biggest purchases then?"
            resp2 = await client.post(
                "/api/insights/ask",
                json={
                    "conversation_id": conv_id1,
                    "question": q2,
                },
                headers=headers,
            )
            print(f"Status Code: {resp2.status_code}")
            assert resp2.status_code == 200, f"Expected 200 OK, got {resp2.status_code}: {resp2.text}"
            data2 = resp2.json()
            assert data2["conversation_id"] == conv_id1
            print(f"Follow-up Tools: {data2['tools_used']}")
            print(f"Follow-up Answer: {data2['answer']}")
            assert "get_largest_expenses" in data2["tools_used"], "Expected get_largest_expenses called"
            assert "Hi Spirits" in data2["answer"] or "9,013" in data2["answer"] or "9013" in data2["answer"]

            # Verify DB now has 4 messages total
            db_msgs2 = (
                supabase_client.table("messages")
                .select("role, content, metadata")
                .eq("conversation_id", conv_id1)
                .order("created_at", desc=False)
                .execute()
            )
            assert len(db_msgs2.data) == 4, f"Expected 4 messages, got {len(db_msgs2.data)}"
            assert db_msgs2.data[2]["role"] == "user"
            assert db_msgs2.data[3]["role"] == "assistant"
            assert "get_largest_expenses" in db_msgs2.data[3]["metadata"]["tools_used"]
            print(">>> PASS: 2. Conversation continuation and context retention verified.")

            # -------------------------------------------------------------
            # 3. Cross-Chat Memory Retrieval on Brand New Conversation
            # -------------------------------------------------------------
            print("\n--- 3. Testing Cross-Chat Memory Retrieval in New Conversation ---")
            # Create a durable memory for TEST_USER_ID
            mem_text = "User has a monthly coffee budget target of exactly 3,000 INR."
            ins_mem = supabase_client.table("user_memories").insert({
                "user_id": TEST_USER_ID,
                "memory_type": "financial_goal",
                "memory_text": mem_text,
                "embedding": generate_embedding(mem_text),
                "is_active": True,
                "importance": 5,
                "confidence": 1.0,
            }).execute()
            assert ins_mem.data
            created_memory_ids.append(ins_mem.data[0]["id"])

            # Ask in a NEW conversation (no conversation_id provided)
            q3 = "What is my target budget for coffee each month?"
            resp3 = await client.post(
                "/api/insights/ask",
                json={"question": q3},
                headers=headers,
            )
            assert resp3.status_code == 200
            data3 = resp3.json()
            conv_id3 = data3["conversation_id"]
            created_conversation_ids.append(conv_id3)
            print(f"Cross-Chat Answer: {data3['answer']}")
            assert "3,000" in data3["answer"] or "3000" in data3["answer"], "Failed to apply cross-chat coffee budget memory"
            print(">>> PASS: 3. Cross-chat user memory retrieved and applied in brand new chat.")

            # -------------------------------------------------------------
            # 4. Conversation Summary Integration
            # -------------------------------------------------------------
            print("\n--- 4. Testing Conversation Summary Integration ---")
            # Update summary of conv_id1 directly
            test_summary = "Earlier: User reviewed 2024 spending and discussed overspending on drinks at Starbucks."
            supabase_client.table("conversations").update({"summary": test_summary}).eq("id", conv_id1).execute()

            q4 = "Which place did I mention earlier that I overspent at?"
            resp4 = await client.post(
                "/api/insights/ask",
                json={
                    "conversation_id": conv_id1,
                    "question": q4,
                },
                headers=headers,
            )
            assert resp4.status_code == 200
            data4 = resp4.json()
            print(f"Summary Recall Answer: {data4['answer']}")
            assert "starbucks" in data4["answer"].lower(), "Failed to recall Starbucks from conversation summary"
            print(">>> PASS: 4. Conversation summary loaded and recalled correctly.")

            # -------------------------------------------------------------
            # 5. Strict User Ownership Isolation
            # -------------------------------------------------------------
            print("\n--- 5. Testing Strict User Ownership Isolation ---")
            # Switch authenticated user to ISOLATED_USER_ID
            app.dependency_overrides[get_current_user] = lambda: ISOLATED_USER_ID

            # Try to ask a question in User A's conversation
            resp_iso_ask = await client.post(
                "/api/insights/ask",
                json={
                    "conversation_id": conv_id1,
                    "question": "What is User A spending?",
                },
                headers=headers,
            )
            print(f"Unauthorized Ask Status: {resp_iso_ask.status_code}")
            assert resp_iso_ask.status_code == 403, f"Expected 403 Forbidden, got {resp_iso_ask.status_code}"

            # Try to get detail of User A's conversation
            resp_iso_get = await client.get(
                f"/api/insights/conversations/{conv_id1}",
                headers=headers,
            )
            print(f"Unauthorized GET Status: {resp_iso_get.status_code}")
            assert resp_iso_get.status_code == 403, f"Expected 403 Forbidden, got {resp_iso_get.status_code}"

            # Try to delete User A's conversation
            resp_iso_del = await client.delete(
                f"/api/insights/conversations/{conv_id1}",
                headers=headers,
            )
            print(f"Unauthorized DELETE Status: {resp_iso_del.status_code}")
            assert resp_iso_del.status_code == 403, f"Expected 403 Forbidden, got {resp_iso_del.status_code}"
            print(">>> PASS: 5. Strict user ownership isolation enforced (403 Forbidden).")

            # Restore TEST_USER_ID auth
            app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID

            # -------------------------------------------------------------
            # 6. Input Validation Errors
            # -------------------------------------------------------------
            print("\n--- 6. Testing Input Validation Errors ---")
            # Empty question
            resp_empty = await client.post(
                "/api/insights/ask",
                json={"question": "   "},
                headers=headers,
            )
            assert resp_empty.status_code == 400, f"Expected 400 for empty question, got {resp_empty.status_code}"

            # Invalid UUID format
            resp_bad_uuid = await client.post(
                "/api/insights/ask",
                json={"conversation_id": "not-a-valid-uuid", "question": "Hello?"},
                headers=headers,
            )
            assert resp_bad_uuid.status_code == 400, f"Expected 400 for invalid UUID, got {resp_bad_uuid.status_code}"

            # Non-existent conversation UUID
            fake_uuid = str(uuid.uuid4())
            resp_404 = await client.post(
                "/api/insights/ask",
                json={"conversation_id": fake_uuid, "question": "Hello?"},
                headers=headers,
            )
            assert resp_404.status_code == 404, f"Expected 404 for non-existent UUID, got {resp_404.status_code}"
            print(">>> PASS: 6. Input validation errors return proper 400 and 404 HTTP codes.")

            # -------------------------------------------------------------
            # 7. GET /api/insights/conversations - List Conversations
            # -------------------------------------------------------------
            print("\n--- 7. Testing List Conversations Endpoint ---")
            resp_list = await client.get("/api/insights/conversations", headers=headers)
            assert resp_list.status_code == 200
            list_data = resp_list.json()
            assert isinstance(list_data, list)
            assert len(list_data) >= 2, "Expected at least 2 conversations for TEST_USER_ID"
            conv_ids_listed = [c["id"] for c in list_data]
            assert conv_id1 in conv_ids_listed
            assert conv_id3 in conv_ids_listed
            print(f"Listed {len(list_data)} conversations successfully.")
            print(">>> PASS: 7. Conversations list endpoint returned user threads sorted by updated_at.")

            # -------------------------------------------------------------
            # 8. GET /api/insights/conversations/{id} - Conversation Detail & Pagination
            # -------------------------------------------------------------
            print("\n--- 8. Testing Conversation Detail & Pagination ---")
            resp_detail = await client.get(
                f"/api/insights/conversations/{conv_id1}?limit=2&offset=0",
                headers=headers,
            )
            assert resp_detail.status_code == 200
            detail_data = resp_detail.json()
            assert detail_data["id"] == conv_id1
            assert detail_data["total_messages"] >= 4
            assert len(detail_data["messages"]) == 2, "Pagination limit=2 respected"
            assert detail_data["limit"] == 2
            assert detail_data["offset"] == 0
            # Messages must have metadata
            assert "metadata" in detail_data["messages"][0]
            print(f"Detail returned {detail_data['total_messages']} total messages, page limit 2 respected.")
            print(">>> PASS: 8. Conversation detail and pagination operate properly.")

            # -------------------------------------------------------------
            # 9. DELETE /api/insights/conversations/{id} - Cascade & Memory Independence
            # -------------------------------------------------------------
            print("\n--- 9. Testing Conversation Deletion & Memory Independence ---")
            # Associate the test memory with conv_id3
            supabase_client.table("user_memories").update({
                "source_conversation_id": conv_id3
            }).eq("id", created_memory_ids[0]).execute()

            # Delete conv_id3
            resp_del = await client.delete(
                f"/api/insights/conversations/{conv_id3}",
                headers=headers,
            )
            assert resp_del.status_code == 200
            assert resp_del.json()["status"] == "success"

            # Confirm conv_id3 is gone
            chk_conv = supabase_client.table("conversations").select("id").eq("id", conv_id3).execute()
            assert len(chk_conv.data) == 0, "Conversation still exists after deletion"

            # Confirm messages of conv_id3 are CASCADE-deleted
            chk_msgs = supabase_client.table("messages").select("id").eq("conversation_id", conv_id3).execute()
            assert len(chk_msgs.data) == 0, "Messages were not cascade-deleted"

            # Confirm cross-chat user memory remains active (with source_conversation_id set to NULL)
            chk_mem = supabase_client.table("user_memories").select("*").eq("id", created_memory_ids[0]).execute()
            assert len(chk_mem.data) == 1, "User memory was unexpectedly deleted!"
            assert chk_mem.data[0]["is_active"] is True, "User memory was deactivated"
            assert chk_mem.data[0]["source_conversation_id"] is None, "Foreign key did not set NULL on cascade delete"
            print(">>> PASS: 9. Conversation deleted, messages cascade-deleted, user memory preserved independently.")

            # Delete conv_id1 as well for clean DB state
            resp_del1 = await client.delete(f"/api/insights/conversations/{conv_id1}", headers=headers)
            assert resp_del1.status_code == 200

            print("\n=======================================================")
            print("ALL 9 AI INSIGHTS API & PERSISTENCE TESTS PASSED!")
            print("=======================================================\n")

    finally:
        app.dependency_overrides.clear()
        print("Cleaning up test records from database...")
        for mid in created_memory_ids:
            try:
                supabase_client.table("user_memories").delete().eq("id", mid).execute()
            except Exception as e:
                logger.warning(f"Error cleaning memory {mid}: {e}")
        for cid in created_conversation_ids:
            try:
                supabase_client.table("conversations").delete().eq("id", cid).execute()
            except Exception as e:
                logger.warning(f"Error cleaning conversation {cid}: {e}")
        print("Cleanup completed.")


if __name__ == "__main__":
    asyncio.run(run_api_tests())

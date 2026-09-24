import asyncio
import logging
from app.agents.insights_agent.embedding import process_receipt_embedding_background
from app.agents.insights_agent.retrieval import search_receipts
from app.database import supabase_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_retrieval")

TEST_USER_ID = "77e1e09e-428f-4d1d-96b0-5121db368045"
PUB_RECEIPT_ID = "fd61473b-bd1d-44eb-9458-f0f3652c75a9"
AMAZON_RECEIPT_ID = "687d1981-e2d6-41e3-990d-5fadc7bc59ff"
SOFT_DELETED_RECEIPT_ID = "ccb3940e-8302-4493-91d8-e628f695f98c"

async def run_end_to_end_test():
    print("\n=======================================================")
    print("PHASE 3.3 END-TO-END RAG RETRIEVAL VERIFICATION")
    print("=======================================================\n")

    # 1. Verify existing real receipt in Supabase
    receipt_res = (
        supabase_client.table("receipts")
        .select("id, merchant_name, category, total_amount, currency, purchase_date, deleted_at")
        .eq("id", PUB_RECEIPT_ID)
        .eq("user_id", TEST_USER_ID)
        .execute()
    )
    assert receipt_res.data, f"Receipt {PUB_RECEIPT_ID} not found for test user {TEST_USER_ID}"
    receipt = receipt_res.data[0]
    print(f"[Step 1] Found real existing receipt: {receipt['merchant_name']} (Category: {receipt['category']}, Date: {receipt['purchase_date']})")

    # 2. Check / Populate embedding for this existing receipt using Phase 3.2 pipeline
    emb_res = (
        supabase_client.table("receipt_embeddings")
        .select("id, receipt_id, summary_text, embedding")
        .eq("receipt_id", PUB_RECEIPT_ID)
        .execute()
    )
    if not emb_res.data:
        print("[Step 2] Generating embedding for existing receipt via Phase 3.2 pipeline...")
        await process_receipt_embedding_background(PUB_RECEIPT_ID, TEST_USER_ID)
        emb_res = (
            supabase_client.table("receipt_embeddings")
            .select("id, receipt_id, summary_text, embedding")
            .eq("receipt_id", PUB_RECEIPT_ID)
            .execute()
        )

    assert emb_res.data, "Failed to find or generate embedding for test receipt"
    embedding_row = emb_res.data[0]
    print(f"[Step 2] Embedding exists in database. Embedding row ID: {embedding_row['id']}")
    print(f"[Step 2] Stored summary_text:\n{embedding_row['summary_text']}")

    # Also ensure the Amazon receipt has an embedding for comparison
    await process_receipt_embedding_background(AMAZON_RECEIPT_ID, TEST_USER_ID)

    # 3. Confirm 768 dimensions
    raw_emb = embedding_row["embedding"]
    if isinstance(raw_emb, str):
        vals = [float(x) for x in raw_emb.strip("[]").split(",") if x.strip()]
    else:
        vals = list(raw_emb)
    print(f"[Step 3] Stored embedding dimension: {len(vals)}")
    assert len(vals) == 768, f"Expected 768 dimensions, got {len(vals)}"

    # 4 & 5 & 6. Realistic semantic query & search_receipts invocation
    query = "Where did I go for drinks and food with friends?"
    print(f"\n[Step 4-6] Executing semantic search for query: '{query}'")
    results = await search_receipts(user_id=TEST_USER_ID, query_text=query, top_k=3)

    # 7. Verify relevant results returned
    print(f"[Step 7] Number of results returned: {len(results)}")
    assert len(results) > 0, "Expected at least 1 result returned"
    top_result = results[0]
    print(f"[Step 7] Top Match: {top_result['merchant']} (Score: {top_result['similarity_score']})")
    assert top_result["merchant"] == "Hi Spirits Cafe & Pub", f"Expected Hi Spirits Cafe & Pub as top match, got {top_result['merchant']}"

    # 8. Verify all required fields
    required_fields = [
        "receipt_id", "merchant", "category", "purchase_date",
        "total", "currency", "items", "summary_text", "similarity_score"
    ]
    for field in required_fields:
        assert field in top_result, f"Field '{field}' missing from top_result"
        print(f"  - {field}: {top_result[field] if field != 'items' else f'{len(top_result[field])} item(s)'}")

    # 9. Verify similarity_score is sensible
    score = top_result["similarity_score"]
    print(f"\n[Step 9] Verified similarity score: {score}")
    assert 0.0 <= score <= 1.0, f"Score out of range [0, 1]: {score}"
    assert score >= 0.5, f"Expected high similarity for relevant query, got {score}"

    # 10. Verify soft-deleted receipts are excluded
    print("\n[Step 10] Testing soft-delete exclusion...")
    # Check if soft-deleted receipt has an embedding (let's insert one temporarily into receipt_embeddings to test exclusion)
    supabase_client.table("receipt_embeddings").upsert({
        "receipt_id": SOFT_DELETED_RECEIPT_ID,
        "user_id": TEST_USER_ID,
        "summary_text": "Merchant: HARISHANKER VEG RESTO\nCategory: Other\nDate: 2025-04-19\nTotal: ₹1,864\nItems: Veg food",
        "embedding": vals,  # using the same vector so it would score high if not filtered
    }, on_conflict="receipt_id").execute()

    # Search specifically for vegetarian food
    soft_test_results = await search_receipts(user_id=TEST_USER_ID, query_text="HARISHANKER VEG RESTO vegetarian food", top_k=5)
    matched_ids = [r["receipt_id"] for r in soft_test_results]
    assert SOFT_DELETED_RECEIPT_ID not in matched_ids, f"Soft-deleted receipt {SOFT_DELETED_RECEIPT_ID} was returned!"
    print(f"[Step 10] PASS: Soft-deleted receipt ({SOFT_DELETED_RECEIPT_ID}) was strictly excluded by r.deleted_at IS NULL")

    # Clean up the test embedding row for the soft-deleted receipt
    supabase_client.table("receipt_embeddings").delete().eq("receipt_id", SOFT_DELETED_RECEIPT_ID).execute()

    # 11. Verify user isolation
    print("\n[Step 11] Testing user isolation...")
    isolated_user_id = "00000000-0000-0000-0000-000000000000"
    isolated_results = await search_receipts(user_id=isolated_user_id, query_text=query, top_k=5)
    print(f"[Step 11] Results for unauthorized/unrelated user: {len(isolated_results)}")
    assert len(isolated_results) == 0, f"User isolation breached! Found {len(isolated_results)} results for another user."
    print("[Step 11] PASS: Strict user isolation confirmed (0 results returned for different user)")

    print("\n=======================================================")
    print("ALL 11 VERIFICATION CHECKS PASSED SUCCESSFULLY")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(run_end_to_end_test())

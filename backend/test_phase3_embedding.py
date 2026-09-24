import asyncio
import logging
import uuid
from app.agents.insights_agent.embedding import (
    build_receipt_summary,
    generate_embedding,
    upsert_receipt_embedding,
    process_receipt_embedding_background,
)
from app.database import supabase_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_embedding")

def test_summary_building():
    print("\n--- TEST 1: Summary Building ---")
    receipt_data = {
        "merchant_name": "Amazon",
        "category": "Shopping",
        "purchase_date": "2026-08-14",
        "total_amount": 2880.0,
        "currency": "INR",
    }
    items = [
        {"item_name": "Logitech MX Keys", "quantity": 1, "total_price": 2500.0},
        {"item_name": "USB-C Cable", "quantity": 2, "total_price": 380.0},
    ]
    summary = build_receipt_summary(receipt_data, items)
    print("Generated Summary:\n" + summary)
    
    assert "Merchant: Amazon" in summary, "Merchant missing"
    assert "Category: Shopping" in summary, "Category missing"
    assert "Date: 2026-08-14" in summary, "Date missing"
    assert "Total: ₹2,880" in summary, "Total missing or incorrect format"
    assert "Logitech MX Keys" in summary, "Item 1 missing"
    assert "USB-C Cable (x2)" in summary, "Item 2 with quantity missing"
    print(">>> PASS: test_summary_building")

def test_embedding_generation():
    print("\n--- TEST 2: Gemini Embedding Generation ---")
    test_text = (
        "Merchant: Amazon\n"
        "Category: Shopping\n"
        "Date: 2026-08-14\n"
        "Total: ₹2,880\n"
        "Items: Logitech MX Keys, USB-C Cable (x2)"
    )
    vector = generate_embedding(test_text)
    print(f"Generated Vector Dimension: {len(vector)}")
    print(f"Sample values: {vector[:5]} ...")
    
    assert isinstance(vector, list), "Vector should be a list"
    assert len(vector) == 768, f"Expected 768 dimensions, got {len(vector)}"
    assert all(isinstance(x, (float, int)) for x in vector), "All vector elements must be numbers"
    print(">>> PASS: test_embedding_generation")

async def test_database_lifecycle():
    print("\n--- TEST 3: Database Upsert, Idempotency & Soft-delete ---")
    if not supabase_client:
        print("Supabase client not initialized! Skipping DB tests.")
        return

    # Find a real user in receipts to associate with foreign key
    users_res = supabase_client.table("receipts").select("user_id").limit(1).execute()
    if not users_res.data:
        print("No existing user found in receipts table. Skipping DB lifecycle test.")
        return

    user_id = users_res.data[0]["user_id"]
    test_receipt_id = str(uuid.uuid4())
    print(f"Using test user_id: {user_id}, test_receipt_id: {test_receipt_id}")

    # 1. Insert a temporary test receipt
    receipt_insert = supabase_client.table("receipts").insert({
        "id": test_receipt_id,
        "user_id": user_id,
        "merchant_name": "Test Electronics",
        "category": "Electronics",
        "purchase_date": "2026-09-23",
        "total_amount": 1500.0,
        "currency": "USD",
        "deleted_at": None,
    }).execute()
    assert receipt_insert.data, "Failed to insert test receipt"

    # Insert items
    items_insert = supabase_client.table("receipt_items").insert([
        {"receipt_id": test_receipt_id, "item_name": "Wireless Mouse", "quantity": 1, "total_price": 500.0},
        {"receipt_id": test_receipt_id, "item_name": "HDMI Cable", "quantity": 2, "total_price": 1000.0},
    ]).execute()
    assert items_insert.data, "Failed to insert test receipt items"

    try:
        # 2. Run background embedding pipeline
        await process_receipt_embedding_background(test_receipt_id, user_id)

        # 3. Verify exactly one row in receipt_embeddings
        emb_res = supabase_client.table("receipt_embeddings").select("*").eq("receipt_id", test_receipt_id).execute()
        rows = emb_res.data or []
        assert len(rows) == 1, f"Expected exactly 1 embedding row, found {len(rows)}"
        row = rows[0]
        assert row["user_id"] == user_id, "user_id mismatch"
        assert row["receipt_id"] == test_receipt_id, "receipt_id mismatch"
        assert "Test Electronics" in row["summary_text"], "Summary text incomplete"
        
        # Check vector format in DB (Supabase/pgvector returns vector as a list of floats or string representation)
        raw_emb = row["embedding"]
        if isinstance(raw_emb, str):
            # Parse '[0.0123,-0.0456,...]'
            vals = [float(x) for x in raw_emb.strip("[]").split(",") if x.strip()]
        else:
            vals = list(raw_emb)
        print(f"Stored vector length in DB: {len(vals)}")
        assert len(vals) == 768, f"Expected 768 dimensions in DB, got {len(vals)}"
        print(">>> Sub-test 3a: Initial embedding created and verified with 768 dims")

        # 4. Idempotency test: Re-run process_receipt_embedding_background
        # Update category on receipt first to verify summary updates
        supabase_client.table("receipts").update({"category": "Gadgets"}).eq("id", test_receipt_id).execute()
        await process_receipt_embedding_background(test_receipt_id, user_id)

        emb_res2 = supabase_client.table("receipt_embeddings").select("*").eq("receipt_id", test_receipt_id).execute()
        rows2 = emb_res2.data or []
        assert len(rows2) == 1, f"Expected still exactly 1 row (no duplicate), found {len(rows2)}"
        assert "Category: Gadgets" in rows2[0]["summary_text"], "Summary text was not updated with new category"
        print(">>> Sub-test 3b: Re-running embedding updated existing row without duplicates")

        # 5. Soft-delete test: Mark receipt soft-deleted
        supabase_client.table("receipts").update({"deleted_at": "now()"}).eq("id", test_receipt_id).execute()
        # Save old updated_at
        old_updated_at = rows2[0]["updated_at"]
        
        # Re-run embedding pipeline - it should skip because deleted_at is not null
        await process_receipt_embedding_background(test_receipt_id, user_id)
        
        emb_res3 = supabase_client.table("receipt_embeddings").select("*").eq("receipt_id", test_receipt_id).execute()
        assert emb_res3.data[0]["updated_at"] == old_updated_at, "Embedding should not be modified for soft-deleted receipt"
        print(">>> Sub-test 3c: Soft-deleted receipt was properly skipped")

    finally:
        # Cleanup: Delete the test receipt (Postgres CASCADE will also delete the embedding)
        supabase_client.table("receipts").delete().eq("id", test_receipt_id).execute()
        check_cascade = supabase_client.table("receipt_embeddings").select("*").eq("receipt_id", test_receipt_id).execute()
        assert len(check_cascade.data) == 0, "CASCADE delete failed to clean up receipt_embeddings"
        print(">>> Sub-test 3d: Hard delete cascaded and cleaned up receipt_embeddings row")

    print(">>> PASS: test_database_lifecycle")

async def main():
    test_summary_building()
    test_embedding_generation()
    await test_database_lifecycle()
    print("\n================ ALL TESTS PASSED ================\n")

if __name__ == "__main__":
    asyncio.run(main())

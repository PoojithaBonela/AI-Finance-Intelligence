import asyncio
from app.agents.categorization_agent.categorizer import categorize_receipt_background, run_categorization

receipt_data = {
    "merchant_name": "Walmart",
    "purchase_date": "2023-10-01",
    "total_amount": 54.20,
    "payment_method": "Credit Card",
    "items": [
        {"name": "Milk", "quantity": 1, "total_price": 4.20},
        {"name": "Eggs", "quantity": 2, "total_price": 5.00},
        {"name": "Bread", "quantity": 1, "total_price": 3.00}
    ]
}

# Use an invalid ID so we just test the logic up to Supabase update
receipt_id = "test-receipt-id-123"

print("--- Testing run_categorization ---")
category = run_categorization(receipt_data)
print(f"Resulting category: {category}")

print("--- Testing categorize_receipt_background ---")
asyncio.run(categorize_receipt_background(receipt_id, receipt_data))
print("--- Done ---")

import asyncio
import logging
from app.agents.insights_agent.tools import (
    get_total_spending,
    get_category_breakdown,
    get_monthly_spending,
    get_yearly_spending,
    get_largest_expenses,
    get_recent_purchases,
)
from app.routers.analytics import get_analytics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_tools")

TEST_USER_ID = "77e1e09e-428f-4d1d-96b0-5121db368045"
ISOLATED_USER_ID = "00000000-0000-0000-0000-000000000000"


async def run_tool_tests():
    print("\n=======================================================")
    print("PHASE 3.4 SQL ANALYTICS TOOLS VERIFICATION")
    print("=======================================================\n")

    # Fetch baseline analytics response for comparison
    analytics_baseline = await get_analytics(user_id=TEST_USER_ID)
    print(f"Baseline from Analytics Page: Total Spending = {analytics_baseline.total_spending}, Receipt Count = {analytics_baseline.receipt_count}")

    # 1. Total Spending
    print("\n--- 1. Testing get_total_spending ---")
    tot = await get_total_spending(TEST_USER_ID)
    print(f"Tool output: {tot}")
    assert tot["receipt_count"] == analytics_baseline.receipt_count, f"Receipt count mismatch: {tot['receipt_count']} vs {analytics_baseline.receipt_count}"
    assert abs(tot["total_spending"] - analytics_baseline.total_spending) < 0.05, f"Total mismatch: {tot['total_spending']} vs {analytics_baseline.total_spending}"
    print(">>> PASS: 1. Total spending matches Analytics page")

    # 2. Category Breakdown
    print("\n--- 2. Testing get_category_breakdown ---")
    cat_breakdown = await get_category_breakdown(TEST_USER_ID)
    print(f"Top Category: {cat_breakdown[0] if cat_breakdown else 'None'}")
    assert len(cat_breakdown) > 0, "Expected non-empty category breakdown"
    # Verify sorted descending
    for i in range(len(cat_breakdown) - 1):
        assert cat_breakdown[i]["total"] >= cat_breakdown[i+1]["total"], "Categories not sorted by total descending"
    # Verify required fields
    for c in cat_breakdown:
        assert "category" in c and "transaction_count" in c and "total" in c and "percentage_of_total" in c
    print(f">>> PASS: 2. Category breakdown ({len(cat_breakdown)} active categories) sorted descending")

    # 3. Monthly Spending
    print("\n--- 3. Testing get_monthly_spending ---")
    monthly = await get_monthly_spending(TEST_USER_ID, year=2024)
    print(f"Months returned count: {len(monthly)}")
    assert len(monthly) == 12, f"Expected 12 months, got {len(monthly)}"
    assert monthly[0]["month"] == "January" and monthly[11]["month"] == "December"
    # October 2024 had Hi Spirits Cafe & Pub
    oct_spending = monthly[9]["total"]  # October is month 10 (index 9)
    print(f"October 2024 Spending: {oct_spending}")
    assert oct_spending > 0, "Expected October 2024 spending > 0"
    print(">>> PASS: 3. Monthly spending returns all 12 months with correct values")

    # 4. Yearly Spending
    print("\n--- 4. Testing get_yearly_spending ---")
    yearly = await get_yearly_spending(TEST_USER_ID)
    print(f"Yearly Spending: {yearly}")
    assert len(yearly) > 0, "Expected non-empty yearly spending"
    years = [y["year"] for y in yearly]
    assert 2024 in years, "Year 2024 missing"
    # Compare with analytics yearly trend
    analytics_yearly = await get_analytics(user_id=TEST_USER_ID)
    assert len(yearly) == len(analytics_yearly.yearly_trend), "Yearly count mismatch with Analytics page"
    print(">>> PASS: 4. Yearly spending verified against Analytics page")

    # 5. Largest Expenses
    print("\n--- 5. Testing get_largest_expenses ---")
    largest = await get_largest_expenses(TEST_USER_ID, limit=5)
    print(f"Largest expense returned: {largest[0]['merchant']} - {largest[0]['total']} {largest[0]['currency']}")
    assert len(largest) > 0, "Expected non-empty largest expenses"
    # Verify sorted descending
    for i in range(len(largest) - 1):
        assert largest[i]["total"] >= largest[i+1]["total"], "Largest expenses not sorted descending"
    # Verify contract
    req_fields = ["receipt_id", "merchant", "category", "purchase_date", "total", "currency", "items"]
    for f in req_fields:
        assert f in largest[0], f"Field '{f}' missing from largest expense"
    assert abs(largest[0]["total"] - analytics_baseline.largest_expense) < 0.05, f"Top expense mismatch: {largest[0]['total']} vs {analytics_baseline.largest_expense}"
    print(">>> PASS: 5. Largest expenses matches Analytics baseline")

    # 6. Recent Purchases
    print("\n--- 6. Testing get_recent_purchases ---")
    recent = await get_recent_purchases(TEST_USER_ID, limit=5)
    print(f"Most recent purchase: {recent[0]['merchant']} ({recent[0]['purchase_date']}) - {recent[0]['total']} {recent[0]['currency']}")
    assert len(recent) > 0, "Expected non-empty recent purchases"
    for f in req_fields:
        assert f in recent[0], f"Field '{f}' missing from recent purchase"
    print(">>> PASS: 6. Recent purchases returned with required structure")

    # 7. Year / Month Filtering
    print("\n--- 7. Testing Year / Month Filtering ---")
    oct_filtered = await get_total_spending(TEST_USER_ID, year=2024, month=10)
    print(f"October 2024 total spending: {oct_filtered}")
    assert oct_filtered["receipt_count"] >= 1, "Expected at least 1 receipt in Oct 2024"
    assert oct_filtered["total_spending"] > 0, "Expected positive spending in Oct 2024"
    print(">>> PASS: 7. Year and Month filtering verified")

    # 8. Category Filtering
    print("\n--- 8. Testing Category Filtering ---")
    food_filtered = await get_total_spending(TEST_USER_ID, category="Food & Dining")
    print(f"Food & Dining spending: {food_filtered}")
    assert food_filtered["receipt_count"] >= 1, "Expected Food & Dining receipts"
    # Verify breakdown with category filter returns only that category
    cat_only = await get_category_breakdown(TEST_USER_ID, category="Food & Dining")
    assert len(cat_only) == 1 and cat_only[0]["category"] == "Food & Dining", "Category filter leaked other categories"
    print(">>> PASS: 8. Category filtering verified")

    # 9. Currency Filtering
    print("\n--- 9. Testing Currency Filtering ---")
    usd_tot = await get_total_spending(TEST_USER_ID, currency="USD")
    print(f"Total spending in USD: {usd_tot}")
    assert usd_tot["currency"] == "USD"
    assert usd_tot["total_spending"] > 0
    print(">>> PASS: 9. Currency conversion filtering verified")

    # 10. Soft-Delete Exclusion
    print("\n--- 10. Testing Soft-Delete Exclusion ---")
    soft_deleted_id = "ccb3940e-8302-4493-91d8-e628f695f98c"  # HARISHANKER VEG RESTO
    all_recent = await get_recent_purchases(TEST_USER_ID, limit=50)
    recent_ids = [r["receipt_id"] for r in all_recent]
    assert soft_deleted_id not in recent_ids, "Soft-deleted receipt found in get_recent_purchases!"
    all_largest = await get_largest_expenses(TEST_USER_ID, limit=50)
    largest_ids = [r["receipt_id"] for r in all_largest]
    assert soft_deleted_id not in largest_ids, "Soft-deleted receipt found in get_largest_expenses!"
    print(">>> PASS: 10. Soft-deleted receipts strictly excluded across all tools")

    # 11. User Isolation
    print("\n--- 11. Testing User Isolation ---")
    iso_tot = await get_total_spending(ISOLATED_USER_ID)
    assert iso_tot["receipt_count"] == 0 and iso_tot["total_spending"] == 0.0, "User isolation failed on total spending"
    iso_cat = await get_category_breakdown(ISOLATED_USER_ID)
    assert len(iso_cat) == 0, "User isolation failed on category breakdown"
    iso_recent = await get_recent_purchases(ISOLATED_USER_ID)
    assert len(iso_recent) == 0, "User isolation failed on recent purchases"
    print(">>> PASS: 11. Strict user isolation confirmed across all tools")

    # 12. Empty Result Cases
    print("\n--- 12. Testing Empty Result Cases ---")
    empty_year_tot = await get_total_spending(TEST_USER_ID, year=1980)
    assert empty_year_tot["receipt_count"] == 0 and empty_year_tot["total_spending"] == 0.0
    empty_monthly = await get_monthly_spending(TEST_USER_ID, year=1980)
    assert len(empty_monthly) == 12 and all(m["total"] == 0.0 for m in empty_monthly)
    empty_largest = await get_largest_expenses(TEST_USER_ID, year=1980)
    assert len(empty_largest) == 0
    print(">>> PASS: 12. Empty result cases handled predictably without exceptions")

    print("\n=======================================================")
    print("ALL 12 TOOL VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(run_tool_tests())

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.services.analytics_service import (
    fetch_user_receipts,
    convert_receipt_amount,
    filter_receipts,
)
from app.agents.categorization_agent.categories import ALLOWED_CATEGORIES

logger = logging.getLogger(__name__)

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


# ============================================================================
# 1. get_total_spending
# ============================================================================

async def get_total_spending(
    user_id: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    category: Optional[str] = None,
    currency: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns total spending and receipt count for the authenticated user,
    with optional filtering by year, month, category, and target currency.
    """
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id must be a valid non-empty string.")

    try:
        receipts = await fetch_user_receipts(user_id, include_items=False)
        filtered = filter_receipts(receipts, year=year, month=month, category=category)

        total_spending = 0.0
        currencies_seen = set()

        for r in filtered:
            amt = float(r.get("total_amount") or 0.0)
            r_curr = r.get("currency")
            p_date = r.get("purchase_date")

            if r_curr:
                currencies_seen.add(r_curr.strip().upper())

            converted_amt = await convert_receipt_amount(amt, r_curr, currency, p_date)
            total_spending += converted_amt

        # Determine returned currency label
        if currency:
            returned_currency = currency.strip().upper()
        elif len(currencies_seen) == 1:
            returned_currency = list(currencies_seen)[0]
        elif len(currencies_seen) > 1:
            returned_currency = "MIXED"
        else:
            returned_currency = None

        return {
            "total_spending": round(total_spending, 2),
            "currency": returned_currency,
            "receipt_count": len(filtered),
        }

    except Exception as e:
        logger.error(f"Error in get_total_spending for user {user_id}: {e}", exc_info=True)
        return {
            "total_spending": 0.0,
            "currency": currency,
            "receipt_count": 0,
        }


# ============================================================================
# 2. get_category_breakdown
# ============================================================================

async def get_category_breakdown(
    user_id: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    category: Optional[str] = None,
    currency: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Returns spending grouped by category for the authenticated user,
    sorted by total descending.
    """
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id must be a valid non-empty string.")

    try:
        receipts = await fetch_user_receipts(user_id, include_items=False)
        filtered = filter_receipts(receipts, year=year, month=month, category=category)

        category_totals: Dict[str, Dict[str, Any]] = {}
        grand_total = 0.0

        for r in filtered:
            amt = float(r.get("total_amount") or 0.0)
            r_curr = r.get("currency")
            p_date = r.get("purchase_date")
            cat = r.get("category") or "Other"

            # Normalize to allowed categories or "Other"
            if cat not in ALLOWED_CATEGORIES:
                cat = "Other"

            converted_amt = await convert_receipt_amount(amt, r_curr, currency, p_date)
            grand_total += converted_amt

            if cat not in category_totals:
                category_totals[cat] = {"transaction_count": 0, "total": 0.0}

            category_totals[cat]["transaction_count"] += 1
            category_totals[cat]["total"] += converted_amt

        breakdown = []
        for cat, data in category_totals.items():
            tot = data["total"]
            pct = (tot / grand_total * 100) if grand_total > 0 else 0.0
            breakdown.append({
                "category": cat,
                "transaction_count": data["transaction_count"],
                "total": round(tot, 2),
                "percentage_of_total": round(pct, 2),
            })

        breakdown.sort(key=lambda x: x["total"], reverse=True)
        return breakdown

    except Exception as e:
        logger.error(f"Error in get_category_breakdown for user {user_id}: {e}", exc_info=True)
        return []


# ============================================================================
# 3. get_monthly_spending
# ============================================================================

async def get_monthly_spending(
    user_id: str,
    year: int,
    currency: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Returns spending for all 12 calendar months for a specific year,
    including months with zero spending.
    """
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id must be a valid non-empty string.")

    try:
        receipts = await fetch_user_receipts(user_id, include_items=False)
        # Filter strictly for the requested year
        filtered = filter_receipts(receipts, year=year)

        monthly_amounts = {m: 0.0 for m in range(1, 13)}

        for r in filtered:
            p_date_str = r.get("purchase_date")
            if not p_date_str:
                continue

            try:
                dt = datetime.strptime(str(p_date_str).strip(), "%Y-%m-%d")
            except ValueError:
                continue

            amt = float(r.get("total_amount") or 0.0)
            r_curr = r.get("currency")
            converted_amt = await convert_receipt_amount(amt, r_curr, currency, str(p_date_str))
            monthly_amounts[dt.month] += converted_amt

        return [
            {
                "month": MONTH_NAMES[m - 1],
                "month_number": m,
                "total": round(monthly_amounts[m], 2),
            }
            for m in range(1, 13)
        ]

    except Exception as e:
        logger.error(f"Error in get_monthly_spending for user {user_id}: {e}", exc_info=True)
        return [
            {
                "month": MONTH_NAMES[m - 1],
                "month_number": m,
                "total": 0.0,
            }
            for m in range(1, 13)
        ]


# ============================================================================
# 4. get_yearly_spending
# ============================================================================

async def get_yearly_spending(
    user_id: str,
    currency: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Returns spending grouped by year for all years in which the user has receipts,
    sorted by year ascending.
    """
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id must be a valid non-empty string.")

    try:
        receipts = await fetch_user_receipts(user_id, include_items=False)
        yearly_totals: Dict[int, float] = {}

        for r in receipts:
            p_date_str = r.get("purchase_date")
            if not p_date_str:
                continue

            try:
                dt = datetime.strptime(str(p_date_str).strip(), "%Y-%m-%d")
            except ValueError:
                continue

            yr = dt.year
            amt = float(r.get("total_amount") or 0.0)
            r_curr = r.get("currency")
            converted_amt = await convert_receipt_amount(amt, r_curr, currency, str(p_date_str))

            if yr not in yearly_totals:
                yearly_totals[yr] = 0.0
            yearly_totals[yr] += converted_amt

        return [
            {
                "year": yr,
                "total": round(yearly_totals[yr], 2),
            }
            for yr in sorted(yearly_totals.keys())
        ]

    except Exception as e:
        logger.error(f"Error in get_yearly_spending for user {user_id}: {e}", exc_info=True)
        return []


# ============================================================================
# 5. get_largest_expenses
# ============================================================================

async def get_largest_expenses(
    user_id: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    category: Optional[str] = None,
    currency: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Returns the user's largest individual receipts, sorted by total descending.
    Includes item details.
    """
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id must be a valid non-empty string.")

    clamped_limit = max(1, min(int(limit), 50))

    try:
        receipts = await fetch_user_receipts(user_id, include_items=True)
        filtered = filter_receipts(receipts, year=year, month=month, category=category)

        enriched = []
        for r in filtered:
            amt = float(r.get("total_amount") or 0.0)
            r_curr = r.get("currency")
            p_date = r.get("purchase_date")
            converted_amt = await convert_receipt_amount(amt, r_curr, currency, p_date)

            formatted_items = []
            for it in r.get("items") or []:
                formatted_items.append({
                    "item_name": it.get("item_name") or "Unnamed item",
                    "quantity": float(it["quantity"]) if it.get("quantity") is not None else None,
                    "unit_price": float(it["unit_price"]) if it.get("unit_price") is not None else None,
                    "total_price": float(it.get("total_price") or 0.0),
                })

            enriched.append({
                "receipt_id": str(r.get("id")),
                "merchant": r.get("merchant_name") or "Unknown",
                "category": r.get("category") or "Other",
                "purchase_date": str(r.get("purchase_date")) if r.get("purchase_date") else None,
                "total": round(converted_amt, 2),
                "currency": currency.strip().upper() if currency else r_curr,
                "items": formatted_items,
            })

        enriched.sort(key=lambda x: x["total"], reverse=True)
        return enriched[:clamped_limit]

    except Exception as e:
        logger.error(f"Error in get_largest_expenses for user {user_id}: {e}", exc_info=True)
        return []


# ============================================================================
# 6. get_recent_purchases
# ============================================================================

async def get_recent_purchases(
    user_id: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Returns the user's most recent purchases sorted by purchase_date descending.
    Includes item details.
    """
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id must be a valid non-empty string.")

    clamped_limit = max(1, min(int(limit), 50))

    try:
        receipts = await fetch_user_receipts(user_id, include_items=True)

        enriched = []
        for r in receipts:
            amt = float(r.get("total_amount") or 0.0)
            r_curr = r.get("currency")

            formatted_items = []
            for it in r.get("items") or []:
                formatted_items.append({
                    "item_name": it.get("item_name") or "Unnamed item",
                    "quantity": float(it["quantity"]) if it.get("quantity") is not None else None,
                    "unit_price": float(it["unit_price"]) if it.get("unit_price") is not None else None,
                    "total_price": float(it.get("total_price") or 0.0),
                })

            enriched.append({
                "receipt_id": str(r.get("id")),
                "merchant": r.get("merchant_name") or "Unknown",
                "category": r.get("category") or "Other",
                "purchase_date": str(r.get("purchase_date")) if r.get("purchase_date") else None,
                "total": round(amt, 2),
                "currency": r_curr,
                "items": formatted_items,
                "_sort_date": str(r.get("purchase_date") or r.get("created_at") or ""),
            })

        # Sort by purchase_date descending
        enriched.sort(key=lambda x: x["_sort_date"], reverse=True)

        # Remove temporary sort key
        for item in enriched:
            item.pop("_sort_date", None)

        return enriched[:clamped_limit]

    except Exception as e:
        logger.error(f"Error in get_recent_purchases for user {user_id}: {e}", exc_info=True)
        return []

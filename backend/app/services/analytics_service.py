import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.database import supabase_client
from app.routers.exchange import _fetch_rate

logger = logging.getLogger(__name__)


async def fetch_user_receipts(
    user_id: str,
    include_items: bool = False
) -> List[Dict[str, Any]]:
    """
    Fetches all active (non-soft-deleted) receipts belonging to the authenticated user.
    Enforces user_id = authenticated_user_id and deleted_at IS NULL.
    """
    if not user_id or not str(user_id).strip():
        logger.warning("fetch_user_receipts called with empty user_id")
        return []

    if not supabase_client:
        logger.error("fetch_user_receipts: Database connection not initialized.")
        return []

    try:
        select_clause = "*, items:receipt_items(*)" if include_items else "*"
        res = (
            supabase_client.table("receipts")
            .select(select_clause)
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"Error fetching active receipts for user {user_id}: {e}", exc_info=True)
        return []


async def convert_receipt_amount(
    amount: float,
    from_currency: Optional[str],
    target_currency: Optional[str],
    date_str: Optional[str]
) -> float:
    """
    Converts amount from from_currency to target_currency using the existing Frankfurter rate engine.
    If currencies match, either is missing, or conversion fails, returns the original amount.
    """
    if not target_currency or not from_currency:
        return amount

    from_c = from_currency.strip().upper()
    to_c = target_currency.strip().upper()

    if from_c == to_c:
        return amount

    try:
        rate, _ = await _fetch_rate(from_c, to_c, date_str)
        return amount * rate
    except Exception as e:
        logger.warning(
            f"Currency conversion failed ({from_c} -> {to_c} on {date_str}): {e}. Retaining original amount."
        )
        return amount


def filter_receipts(
    receipts: List[Dict[str, Any]],
    year: Optional[int] = None,
    month: Optional[int] = None,
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Applies standard TracePay filtering rules to a list of receipt dictionaries:
    - Year: Exact year matching purchase_date.
    - Month: 1-12 calendar month (e.g. 4 = April). Only operates when Year is specified.
      If month is passed without year, no receipts match (matching existing Analytics behavior).
    - Category: Case-insensitive match on category.
    """
    filtered = []

    for r in receipts:
        p_date_str = r.get("purchase_date")
        date_matches = True

        if year is not None:
            if not p_date_str:
                date_matches = False
            else:
                try:
                    dt = datetime.strptime(str(p_date_str).strip(), "%Y-%m-%d")
                    if dt.year != int(year):
                        date_matches = False
                    if month is not None:
                        # 1-12 calendar month (e.g., 4 is April)
                        # also supports 0-indexed fallback if 0 is passed for January
                        target_month = 1 if int(month) == 0 else int(month)
                        if dt.month != target_month:
                            date_matches = False
                except ValueError:
                    date_matches = False
        elif month is not None:
            # Month is dependent on the selected Year and must never operate independently across all years
            date_matches = False

        if not date_matches:
            continue

        if category and str(category).strip():
            target_cat = str(category).strip().lower()
            receipt_cat = str(r.get("category") or "Other").strip().lower()
            if receipt_cat != target_cat:
                continue

        filtered.append(r)

    return filtered

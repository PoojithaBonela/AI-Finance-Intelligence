import logging
from typing import Optional, List, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ..dependencies import get_current_user
from ..database import supabase_client
from .exchange import _fetch_rate
from ..agents.categorization_agent.categories import ALLOWED_CATEGORIES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

class CategoryBreakdown(BaseModel):
    category: str
    amount: float

class TableBreakdown(BaseModel):
    category: str
    transaction_count: int
    total: float
    percentage: float

class MonthlyTrendItem(BaseModel):
    month: str
    month_number: int
    amount: float

class YearlyTrendItem(BaseModel):
    year: int
    amount: float

class CategoryOverTimeItem(BaseModel):
    category: str
    month: str
    month_number: int
    amount: float
    percentage: float  # percentage of that category's annual total

class AnalyticsResponse(BaseModel):
    total_spending: float
    receipt_count: int
    average_receipt: float
    largest_expense: float
    largest_expense_merchant: Optional[str]
    category_breakdown: List[CategoryBreakdown]
    table_breakdown: List[TableBreakdown]
    monthly_trend: List[MonthlyTrendItem]
    yearly_trend: List[YearlyTrendItem]
    category_over_time: List[CategoryOverTimeItem]

@router.get("", response_model=AnalyticsResponse)
async def get_analytics(
    year: Optional[int] = None,
    month: Optional[int] = None,
    category: Optional[str] = None,
    currency: Optional[str] = None,
    trend_year: Optional[int] = None,
    trend_currency: Optional[str] = None,
    yearly_trend_currency: Optional[str] = None,
    cot_year: Optional[int] = None,
    cot_currency: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    try:
        # 1. Fetch user's active receipts
        res = supabase_client.table("receipts").select("*").eq("user_id", user_id).is_("deleted_at", "null").execute()
        receipts = res.data or []

        filtered_receipts = []
        breakdown_receipts = []

        # 2. Apply filters
        for r in receipts:
            # Check Date filters (applies to both KPIs and Category Breakdown)
            p_date_str = r.get("purchase_date")
            date_matches = True
            if year is not None:
                if not p_date_str:
                    date_matches = False
                else:
                    try:
                        dt = datetime.strptime(p_date_str, "%Y-%m-%d")
                        if dt.year != year:
                            date_matches = False
                        if month is not None and dt.month != (month + 1):
                            date_matches = False
                    except ValueError:
                        date_matches = False
            elif month is not None:
                # Month is dependent on the selected Year and must never operate independently across all years
                date_matches = False
            
            if not date_matches:
                continue
                
            # Date matched, so add to breakdown_receipts
            breakdown_receipts.append(r)
            
            # Check Category filter for KPIs only
            if category and r.get("category") != category:
                continue
                
            filtered_receipts.append(r)

        # 3. Calculate metrics with optional currency conversion
        total_spending = 0.0
        receipt_count = len(filtered_receipts)
        largest_expense = 0.0
        largest_expense_merchant = None

        for r in filtered_receipts:
            amt = float(r.get("total_amount", 0.0))
            r_curr = r.get("currency")
            p_date = r.get("purchase_date")
            
            # Convert if necessary
            if currency and r_curr and r_curr != currency:
                try:
                    rate, _ = await _fetch_rate(r_curr, currency, p_date)
                    amt = amt * rate
                except RuntimeError:
                    pass # Keep original amount if conversion fails for some reason
                    
            total_spending += amt
            
            if amt > largest_expense:
                largest_expense = amt
                largest_expense_merchant = r.get("merchant_name")

        average_receipt = total_spending / receipt_count if receipt_count > 0 else 0.0

        # 4. Calculate Category Breakdown
        breakdown_dict = {cat: 0.0 for cat in ALLOWED_CATEGORIES}
        
        for r in breakdown_receipts:
            amt = float(r.get("total_amount", 0.0))
            r_curr = r.get("currency")
            p_date = r.get("purchase_date")
            cat = r.get("category") or "Other"
            
            # Ensure it maps to an allowed category, otherwise group in "Other"
            if cat not in breakdown_dict:
                cat = "Other"
            
            # Convert if necessary
            if currency and r_curr and r_curr != currency:
                try:
                    rate, _ = await _fetch_rate(r_curr, currency, p_date)
                    amt = amt * rate
                except RuntimeError:
                    pass # Keep original amount if conversion fails
                    
            breakdown_dict[cat] += amt

        # Format into list of models
        category_breakdown = [
            CategoryBreakdown(category=cat, amount=round(amt, 2))
            for cat, amt in breakdown_dict.items()
        ]

        # 5. Calculate Table Breakdown
        table_dict = {cat: {"transaction_count": 0, "total": 0.0} for cat in ALLOWED_CATEGORIES}
        for r in filtered_receipts:
            amt = float(r.get("total_amount", 0.0))
            r_curr = r.get("currency")
            p_date = r.get("purchase_date")
            cat = r.get("category") or "Other"
            
            if cat not in ALLOWED_CATEGORIES:
                cat = "Other"

            if currency and r_curr and r_curr != currency:
                try:
                    rate, _ = await _fetch_rate(r_curr, currency, p_date)
                    amt = amt * rate
                except RuntimeError:
                    pass
            
            table_dict[cat]["transaction_count"] += 1
            table_dict[cat]["total"] += amt
            
        table_breakdown = []
        for cat, d in table_dict.items():
            perc = (d["total"] / total_spending * 100) if total_spending > 0 else 0.0
            table_breakdown.append(
                TableBreakdown(
                    category=cat,
                    transaction_count=d["transaction_count"],
                    total=round(d["total"], 2),
                    percentage=round(perc, 1)
                )
            )
                
        table_breakdown.sort(key=lambda x: x.total, reverse=True)

        # 6. Calculate Monthly Trend
        MONTH_NAMES = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        monthly_amounts = {i: 0.0 for i in range(1, 13)}

        if trend_year is not None:
            for r in receipts:
                p_date_str = r.get("purchase_date")
                if not p_date_str:
                    continue
                try:
                    dt = datetime.strptime(p_date_str, "%Y-%m-%d")
                except ValueError:
                    continue

                if dt.year != trend_year:
                    continue

                amt = float(r.get("total_amount", 0.0))
                r_curr = r.get("currency")
                t_curr = trend_currency or currency

                if t_curr and r_curr and r_curr != t_curr:
                    try:
                        rate, _ = await _fetch_rate(r_curr, t_curr, p_date_str)
                        amt = amt * rate
                    except RuntimeError:
                        pass

                monthly_amounts[dt.month] += amt

        monthly_trend = [
            MonthlyTrendItem(
                month=MONTH_NAMES[m - 1],
                month_number=m,
                amount=round(monthly_amounts[m], 2)
            )
            for m in range(1, 13)
        ]

        # 7. Calculate Yearly Trend
        # Uses all receipts (not subject to global year/month/category filters)
        y_curr = yearly_trend_currency or currency
        yearly_dict: dict = {}

        for r in receipts:
            p_date_str = r.get("purchase_date")
            if not p_date_str:
                continue
            try:
                dt = datetime.strptime(p_date_str, "%Y-%m-%d")
            except ValueError:
                continue

            yr = dt.year
            amt = float(r.get("total_amount", 0.0))
            r_curr = r.get("currency")

            if y_curr and r_curr and r_curr != y_curr:
                try:
                    rate, _ = await _fetch_rate(r_curr, y_curr, p_date_str)
                    amt = amt * rate
                except RuntimeError:
                    pass

            if yr not in yearly_dict:
                yearly_dict[yr] = 0.0
            yearly_dict[yr] += amt

        yearly_trend = [
            YearlyTrendItem(year=yr, amount=round(amt, 2))
            for yr, amt in sorted(yearly_dict.items())
        ]

        # 8. Calculate Category Over Time
        # 14 categories x 12 months grid, filtered by cot_year, converted to cot_currency
        cot_c = cot_currency
        # Initialize: {cat: {month_num: amount}}
        cot_grid = {cat: {m: 0.0 for m in range(1, 13)} for cat in ALLOWED_CATEGORIES}

        if cot_year is not None:
            for r in receipts:
                p_date_str = r.get("purchase_date")
                if not p_date_str:
                    continue
                try:
                    dt = datetime.strptime(p_date_str, "%Y-%m-%d")
                except ValueError:
                    continue

                if dt.year != cot_year:
                    continue

                amt = float(r.get("total_amount", 0.0))
                r_curr = r.get("currency")
                cat = r.get("category") or "Other"
                if cat not in ALLOWED_CATEGORIES:
                    cat = "Other"

                if cot_c and r_curr and r_curr != cot_c:
                    try:
                        rate, _ = await _fetch_rate(r_curr, cot_c, p_date_str)
                        amt = amt * rate
                    except RuntimeError:
                        pass

                cot_grid[cat][dt.month] += amt

        category_over_time = []
        for cat in ALLOWED_CATEGORIES:
            monthly_totals = cot_grid[cat]
            annual_total = sum(monthly_totals.values())
            for m in range(1, 13):
                m_amt = monthly_totals[m]
                perc = (m_amt / annual_total * 100) if annual_total > 0 else 0.0
                category_over_time.append(
                    CategoryOverTimeItem(
                        category=cat,
                        month=MONTH_NAMES[m - 1],
                        month_number=m,
                        amount=round(m_amt, 2),
                        percentage=round(perc, 2)
                    )
                )

        return AnalyticsResponse(
            total_spending=round(total_spending, 2),
            receipt_count=receipt_count,
            average_receipt=round(average_receipt, 2),
            largest_expense=round(largest_expense, 2),
            largest_expense_merchant=largest_expense_merchant,
            category_breakdown=category_breakdown,
            table_breakdown=table_breakdown,
            monthly_trend=monthly_trend,
            yearly_trend=yearly_trend,
            category_over_time=category_over_time
        )

    except Exception as e:
        logger.error(f"Error fetching analytics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error fetching analytics")

"""
Exchange-rate router.

Endpoint: POST /api/convert-receipts
  - Accepts a list of receipts + a target display currency.
  - For each receipt, fetches the historical exchange rate on its purchase_date
    (falling back to the latest rate if no date is available).
  - Returns the same receipts with an extra `converted` block containing the
    display-only converted values. Original fields are never modified.
  - Uses api.frankfurter.app (ECB data, free, no API key).
  - Uses precise float arithmetic (sufficient for display rounding to 2 dp).
  - If a rate cannot be fetched, the original value is returned with a
    `conversion_unavailable` flag set to True.
"""

import logging
from datetime import date, datetime
from typing import Any, Optional, List, Dict
import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["exchange"])

FRANKFURTER_BASE = "https://api.frankfurter.dev/v1"

# --------------------------------------------------------------------------- #
# Pydantic models                                                              #
# --------------------------------------------------------------------------- #

class ItemIn(BaseModel):
    item_name: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: float

class ReceiptIn(BaseModel):
    id: str
    currency: Optional[str] = None
    total_amount: float
    tax: Optional[float] = None
    purchase_date: Optional[str] = None
    items: list[ItemIn] = []

class ConvertRequest(BaseModel):
    receipts: list[ReceiptIn]
    target_currency: str

class ItemConverted(BaseModel):
    item_name: str
    quantity: Optional[float]
    unit_price: Optional[float]
    total_price: float

class ReceiptConverted(BaseModel):
    id: str
    total_amount: float
    tax: Optional[float]
    items: list[ItemConverted]
    rate_date: Optional[str]          # actual date the rate applies to
    conversion_unavailable: bool = False

class ConvertResponse(BaseModel):
    target_currency: str
    results: list[ReceiptConverted]


# --------------------------------------------------------------------------- #
# Rate cache (in-process, keyed by (from_currency, to_currency, date_str))    #
# --------------------------------------------------------------------------- #

_rate_cache: dict[tuple[str, str, str], float] = {}


async def _fetch_rate(from_curr: str, to_curr: str, on_date: Optional[str]) -> tuple[float, str]:
    """
    Return (rate, actual_date_used).
    Rate is: 1 unit of from_curr = rate units of to_curr.
    Raises RuntimeError on failure.
    """
    if from_curr == to_curr:
        return 1.0, on_date or str(date.today())

    # Determine the URL date segment
    url_date = "latest"
    if on_date:
        try:
            parsed = datetime.strptime(on_date, "%Y-%m-%d").date()
            # Frankfurter only goes back to 1999-01-04
            if parsed >= date(1999, 1, 4) and parsed <= date.today():
                url_date = on_date
        except ValueError:
            pass  # fall back to latest

    cache_key = (from_curr, to_curr, url_date)
    if cache_key in _rate_cache:
        return _rate_cache[cache_key], url_date

    url = f"{FRANKFURTER_BASE}/{url_date}?base={from_curr}&to={to_curr}"
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code in (404, 422):
                raise RuntimeError(f"Currency pair {from_curr}->{to_curr} not supported by Frankfurter.")
            resp.raise_for_status()
            data = resp.json()
            rate = data["rates"][to_curr]
            actual_date: str = data.get("date", url_date)
            _rate_cache[cache_key] = rate
            logger.info(f"Rate fetched: 1 {from_curr} = {rate} {to_curr} on {actual_date}")
            return rate, actual_date
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise RuntimeError(f"Network error fetching rate: {exc}") from exc
    except (KeyError, ValueError) as exc:
        raise RuntimeError(f"Unexpected response format from Frankfurter: {exc}") from exc


def _round2(v: Optional[float]) -> Optional[float]:
    return round(v, 2) if v is not None else None


# --------------------------------------------------------------------------- #
# Main endpoint                                                                #
# --------------------------------------------------------------------------- #

@router.post("/convert-receipts", response_model=ConvertResponse)
async def convert_receipts(body: ConvertRequest, user_id: str = Depends(get_current_user)) -> ConvertResponse:
    target = body.target_currency.upper()
    results: list[ReceiptConverted] = []

    for receipt in body.receipts:
        from_curr = (receipt.currency or "").upper()

        # No conversion needed
        if not from_curr or from_curr == target:
            results.append(ReceiptConverted(
                id=receipt.id,
                total_amount=round(receipt.total_amount, 2),
                tax=_round2(receipt.tax),
                items=[
                    ItemConverted(
                        item_name=it.item_name,
                        quantity=it.quantity,
                        unit_price=_round2(it.unit_price),
                        total_price=round(it.total_price, 2),
                    )
                    for it in receipt.items
                ],
                rate_date=None,
                conversion_unavailable=False,
            ))
            continue

        # Fetch historical rate
        try:
            rate, rate_date = await _fetch_rate(from_curr, target, receipt.purchase_date)
        except RuntimeError as exc:
            logger.warning(f"[{receipt.id}] Rate unavailable: {exc}")
            results.append(ReceiptConverted(
                id=receipt.id,
                total_amount=round(receipt.total_amount, 2),
                tax=_round2(receipt.tax),
                items=[
                    ItemConverted(
                        item_name=it.item_name,
                        quantity=it.quantity,
                        unit_price=_round2(it.unit_price),
                        total_price=round(it.total_price, 2),
                    )
                    for it in receipt.items
                ],
                rate_date=None,
                conversion_unavailable=True,
            ))
            continue

        def conv(v: float) -> float:
            return round(v * rate, 2)

        results.append(ReceiptConverted(
            id=receipt.id,
            total_amount=conv(receipt.total_amount),
            tax=conv(receipt.tax) if receipt.tax is not None else None,
            items=[
                ItemConverted(
                    item_name=it.item_name,
                    quantity=it.quantity,
                    unit_price=conv(it.unit_price) if it.unit_price is not None else None,
                    total_price=conv(it.total_price),
                )
                for it in receipt.items
            ],
            rate_date=rate_date,
            conversion_unavailable=False,
        ))

    return ConvertResponse(target_currency=target, results=results)

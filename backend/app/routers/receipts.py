from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from ..schemas.receipts import ReceiptCreate, ReceiptResponse
from ..database import supabase_client
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/api/receipts", tags=["receipts"])
logger = logging.getLogger(__name__)


# ── Duplicate Detection ──────────────────────────────────────────────────────

class DupItemIn(BaseModel):
    item_name: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: float

class DupCheckRequest(BaseModel):
    merchant_name: str
    purchase_date: Optional[str] = None
    currency: Optional[str] = None
    total_amount: float
    items: List[DupItemIn] = []

class DupMatch(BaseModel):
    id: str
    merchant_name: str
    purchase_date: Optional[str]
    currency: Optional[str]
    total_amount: float
    score: float            # 0.0–1.0 confidence it is a duplicate

class DupCheckResponse(BaseModel):
    is_duplicate: bool
    match: Optional[DupMatch] = None


def _item_seq_similarity(new_items: List[DupItemIn], existing_items: list) -> float:
    """
    Returns 0.0–1.0 similarity between two item sequences.
    Compares item_name, total_price in positional order.
    """
    if not new_items and not existing_items:
        return 1.0
    if not new_items or not existing_items:
        return 0.0
    matches = 0
    total = max(len(new_items), len(existing_items))
    for i in range(min(len(new_items), len(existing_items))):
        n = new_items[i]
        e = existing_items[i]
        name_match = n.item_name.strip().lower() == e.get("item_name", "").strip().lower()
        price_match = abs(n.total_price - float(e.get("total_price", -9999))) < 0.02
        if name_match and price_match:
            matches += 1
        elif name_match or price_match:
            matches += 0.5
    return matches / total


def _normalize_string(s: str) -> str:
    import re
    if not s:
        return ""
    # Remove all non-alphanumeric chars and convert to lower
    return re.sub(r'[^a-z0-9]', '', s.lower())

def _score_pair(new: DupCheckRequest, existing: dict, existing_items: list) -> float:
    """Composite similarity score 0.0–1.0."""
    
    new_merch = _normalize_string(new.merchant_name)
    ex_merch = _normalize_string(existing.get("merchant_name", ""))
    
    merch_match = (new_merch == ex_merch) if new_merch and ex_merch else False
    
    new_total = new.total_amount
    ex_total = float(existing.get("total_amount", -9999))
    total_match = abs(new_total - ex_total) < 0.02
    
    # 1. Primary rule: strong merchant + total match
    if merch_match and total_match:
        return 0.90
        
    # 2. Date + Total match (if merchant was slightly off)
    new_date = (new.purchase_date or "").strip()
    ex_date  = str(existing.get("purchase_date") or "").strip()
    date_match = (new_date == ex_date) if new_date and ex_date else False
    
    if date_match and total_match:
        return 0.85
        
    # 3. Fallback: item sequence
    if new.items or existing_items:
        seq_sim = _item_seq_similarity(new.items, existing_items)
        if seq_sim >= 0.8:
            return 0.85 + (seq_sim * 0.1) # 0.93 - 0.95
            
    # Combine what we have for a weak score
    score = 0.0
    weights = 0.0
    
    if new_merch and ex_merch:
        score += 0.4 if merch_match else 0.0
        weights += 0.4
        
    if new_date and ex_date:
        score += 0.2 if date_match else 0.0
        weights += 0.2
        
    score += 0.3 if total_match else 0.0
    weights += 0.3
    
    if new.items or existing_items:
        seq_sim = _item_seq_similarity(new.items, existing_items)
        score += seq_sim * 0.3
        weights += 0.3
        
    return score / weights if weights > 0 else 0.0


@router.post("/check-duplicate", response_model=DupCheckResponse)
async def check_duplicate(body: DupCheckRequest):
    """
    Compare the incoming receipt against all saved receipts.
    Returns is_duplicate=True and the best match if composite score ≥ 0.85.
    """
    if not supabase_client:
        raise HTTPException(status_code=500, detail="Database not initialised.")

    try:
        res = supabase_client.table("receipts").select(
            "id, merchant_name, purchase_date, currency, total_amount, items:receipt_items(item_name, total_price)"
        ).execute()
        existing = res.data or []
    except Exception as e:
        logger.error(f"check-duplicate DB error: {e}")
        raise HTTPException(status_code=500, detail="Failed to query existing receipts.")

    best_score = 0.0
    best_match = None

    for ex in existing:
        ex_items = ex.get("items") or []
        s = _score_pair(body, ex, ex_items)
        if s > best_score:
            best_score = s
            best_match = ex

    THRESHOLD = 0.85
    if best_score >= THRESHOLD and best_match:
        return DupCheckResponse(
            is_duplicate=True,
            match=DupMatch(
                id=best_match["id"],
                merchant_name=best_match.get("merchant_name", ""),
                purchase_date=str(best_match.get("purchase_date") or "") or None,
                currency=best_match.get("currency"),
                total_amount=float(best_match.get("total_amount", 0)),
                score=round(best_score, 3),
            ),
        )

    return DupCheckResponse(is_duplicate=False)



@router.post("", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)
async def create_receipt(receipt_in: ReceiptCreate):
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection is not initialized."
        )

    # 1. Prepare receipt data
    receipt_data = receipt_in.model_dump(exclude={"items"}, exclude_none=True)
    
    # Supabase Date types need ISO strings, pydantic handles date serialization if we do model_dump(mode='json')
    receipt_data = receipt_in.model_dump(exclude={"items"}, exclude_none=True, mode='json')

    try:
        # Insert receipt
        receipt_res = supabase_client.table("receipts").insert(receipt_data).execute()
        if not receipt_res.data:
            raise Exception("Failed to insert receipt: No data returned.")
        
        created_receipt = receipt_res.data[0]
        receipt_id = created_receipt["id"]

        # 2. Insert receipt items if they exist
        created_items = []
        if receipt_in.items:
            items_data = []
            for item in receipt_in.items:
                item_dict = item.model_dump(exclude_none=True, mode='json')
                item_dict["receipt_id"] = receipt_id
                items_data.append(item_dict)

            try:
                items_res = supabase_client.table("receipt_items").insert(items_data).execute()
                created_items = items_res.data
            except Exception as item_err:
                # Manual rollback: delete the receipt if items fail to insert
                logger.error(f"Failed to insert receipt items, rolling back receipt {receipt_id}: {item_err}")
                supabase_client.table("receipts").delete().eq("id", receipt_id).execute()
                raise Exception(f"Failed to insert items: {str(item_err)}")

        # 3. Assemble response
        created_receipt["items"] = created_items
        return created_receipt

    except Exception as e:
        logger.error(f"Error creating receipt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while saving the receipt: {str(e)}"
        )

@router.get("", response_model=List[ReceiptResponse])
async def get_receipts():
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection is not initialized."
        )
        
    try:
        # Fetch receipts and their nested receipt_items
        # Since we just created the table via raw SQL, the foreign key relation is named 'receipt_items_receipt_id_fkey'.
        # In PostgREST, we can just do 'receipt_items(*)' to join it.
        res = supabase_client.table("receipts").select("*, items:receipt_items(*)").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error fetching receipts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching receipts: {str(e)}"
        )

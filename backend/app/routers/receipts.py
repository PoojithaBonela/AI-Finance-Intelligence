from typing import List
from fastapi import APIRouter, HTTPException, status
from ..schemas.receipts import ReceiptCreate, ReceiptResponse
from ..database import supabase_client
import logging

router = APIRouter(prefix="/api/receipts", tags=["receipts"])
logger = logging.getLogger(__name__)

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

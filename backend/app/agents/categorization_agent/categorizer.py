import json
import logging
from pydantic import BaseModel, Field
from typing import Optional
from .categories import ALLOWED_CATEGORIES, FALLBACK_CATEGORY
from .prompts import CATEGORIZATION_PROMPT
from app.services.ocr import get_gemini_client
from app.database import supabase_client

logger = logging.getLogger(__name__)

class CategorizationResult(BaseModel):
    category: str = Field(description="The chosen expense category.")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0.")

def run_categorization(receipt_data: dict) -> str:
    """
    Runs the Gemini model to categorize the receipt data.
    Returns the chosen category.
    """
    try:
        client = get_gemini_client()
        
        # Prepare the data summary to send to Gemini
        data_summary = {
            "merchant_name": receipt_data.get("merchant_name"),
            "purchase_date": receipt_data.get("purchase_date"),
            "total_amount": receipt_data.get("total_amount"),
            "payment_method": receipt_data.get("payment_method"),
            "items": receipt_data.get("items", [])
        }
        
        content = json.dumps(data_summary, indent=2)
        
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=[
                CATEGORIZATION_PROMPT,
                f"Receipt Data:\n{content}"
            ],
            config={
                "response_mime_type": "application/json",
                "response_schema": CategorizationResult,
                "temperature": 0.1,
            },
        )
        
        if not response.text:
            logger.warning("Empty response from Gemini categorization.")
            return FALLBACK_CATEGORY
            
        result = CategorizationResult.model_validate_json(response.text)
        
        # Validate category and confidence
        if result.confidence < 0.6:
            logger.info(f"Categorization confidence too low ({result.confidence}). Using fallback.")
            return FALLBACK_CATEGORY
            
        if result.category not in ALLOWED_CATEGORIES:
            logger.warning(f"Gemini returned invalid category: '{result.category}'. Using fallback.")
            return FALLBACK_CATEGORY
            
        return result.category
        
    except Exception as e:
        logger.error(f"Error during categorization: {e}")
        return FALLBACK_CATEGORY

async def categorize_receipt_background(receipt_id: str, receipt_data: dict):
    """
    Background task to run categorization and update the receipt in the database.
    Catches all exceptions to ensure it doesn't break the main thread.
    """
    try:
        logger.info(f"Starting background categorization for receipt {receipt_id}...")
        category = run_categorization(receipt_data)
        
        if not supabase_client:
            logger.error("Database connection not initialized. Cannot save category.")
            return
            
        res = supabase_client.table("receipts").update({"category": category}).eq("id", receipt_id).execute()
        if not res.data:
            logger.warning(f"Failed to update category for receipt {receipt_id}. Row might not exist.")
        else:
            logger.info(f"Successfully categorized receipt {receipt_id} as '{category}'.")
            
    except Exception as e:
        logger.error(f"Failed background categorization for {receipt_id}: {e}", exc_info=True)

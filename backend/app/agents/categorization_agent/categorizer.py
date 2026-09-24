import json
import logging
from pydantic import BaseModel, Field
from typing import Optional
from .categories import ALLOWED_CATEGORIES, FALLBACK_CATEGORY
from .prompts import CATEGORIZATION_PROMPT
from app.agents.receipt_agent import get_gemini_client
import app.database

logger = logging.getLogger(__name__)

class CategorizationResult(BaseModel):
    category: str = Field(description="The chosen expense category.")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0.")

def run_categorization(receipt_data: dict) -> str:
    """
    Synchronous helper to run the Gemini prompt and parse the result.
    """
    try:
        # Extract meaningful data to send to Gemini
        data_summary = {
            "merchant_name": receipt_data.get("merchant_name"),
            "items": [
                {"name": item.get("item_name"), "price": item.get("total_price")}
                for item in receipt_data.get("items", [])
            ]
        }
        
        content = json.dumps(data_summary, indent=2)
        logger.info(f"DEBUG_AGENT2: Final verified receipt data sent to Agent 2: {content}")
        
        model_name = "gemini-3.5-flash-lite"
        logger.info(f"DEBUG_AGENT2: Gemini model being used: {model_name}")
        logger.info("DEBUG_AGENT2: Gemini request started")
        
        client = get_gemini_client()
        response = client.models.generate_content(
            model=model_name,
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
            logger.error("DEBUG_AGENT2: Empty response from Gemini categorization.")
            return FALLBACK_CATEGORY
            
        logger.info(f"DEBUG_AGENT2: Raw Gemini categorization result: {response.text}")
        result = CategorizationResult.model_validate_json(response.text)
        logger.info(f"DEBUG_AGENT2: Parsed Gemini categorization result: category={result.category}, confidence={result.confidence}")
        
        # Validate category and confidence
        if result.confidence < 0.6:
            logger.warning(f"DEBUG_AGENT2: Confidence threshold caused fallback. Categorization confidence too low ({result.confidence} < 0.6). Using fallback 'Other'.")
            return FALLBACK_CATEGORY
            
        if result.category not in ALLOWED_CATEGORIES:
            logger.warning(f"DEBUG_AGENT2: Category failed validation. Gemini returned invalid category: '{result.category}'. Using fallback 'Other'.")
            return FALLBACK_CATEGORY
            
        logger.info(f"DEBUG_AGENT2: run_categorization SUCCESS! Category passed validation. Returned category: {result.category}")
        return result.category
        
    except Exception as e:
        logger.error(f"DEBUG_AGENT2: Error during categorization: {e}", exc_info=True)
        return FALLBACK_CATEGORY

async def categorize_receipt_background(receipt_id: str, receipt_data: dict, user_id: Optional[str] = None):
    """
    Background task that calls Gemini and updates the Supabase record.
    Catches all exceptions to ensure it doesn't break the main thread.
    Also triggers Agent 3's receipt embedding pipeline once categorization completes.
    """
    try:
        logger.info(f"DEBUG_AGENT2: Agent 2 started for receipt ID: {receipt_id}")
        category = run_categorization(receipt_data)
        
        if not app.database.supabase_client:
            logger.error("DEBUG_AGENT2: Database connection not initialized. Cannot save category.")
            return
            
        logger.info(f"DEBUG_AGENT2: Supabase UPDATE attempted. Updating category={category} for receipt_id={receipt_id}")
        res = app.database.supabase_client.table("receipts").update({"category": category}).eq("id", receipt_id).execute()
        
        logger.info(f"DEBUG_AGENT2: Supabase UPDATE result/error: {res.data}")
        if not res.data:
            logger.error(f"DEBUG_AGENT2: Failed to update category for receipt {receipt_id}. Row might not exist or RLS blocked it.")
        else:
            logger.info(f"DEBUG_AGENT2: Final category saved successfully. Categorized receipt {receipt_id} as '{category}'.")
            
    except Exception as e:
        logger.error(f"DEBUG_AGENT2: Failed background categorization for {receipt_id}: {e}", exc_info=True)

    # Trigger Agent 3 Embedding Pipeline (Phase 3.2)
    if user_id:
        try:
            from app.agents.insights_agent.embedding import process_receipt_embedding_background
            await process_receipt_embedding_background(receipt_id, user_id)
        except Exception as emb_e:
            logger.error(
                "Failed to trigger embedding for receipt %s: %s",
                receipt_id,
                emb_e,
                exc_info=True,
            )

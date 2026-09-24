import logging
from typing import List, Dict, Any, Optional
from google.genai import types
from app.agents.receipt_agent import get_gemini_client
from app.database import supabase_client

logger = logging.getLogger(__name__)

# Currency symbol mapping
CURRENCY_SYMBOLS = {
    "USD": "$",
    "INR": "₹",
    "EUR": "€",
    "GBP": "£",
    "CAD": "C$",
    "AUD": "A$",
}


def build_receipt_summary(receipt_data: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    """
    Constructs a concise, structured textual summary of the receipt suitable for semantic retrieval.
    Includes merchant, category, purchase date, total amount with currency, and item names.
    
    Example:
    Merchant: Amazon
    Category: Shopping
    Date: 2026-08-14
    Total: ₹2,880
    Items: Logitech MX Keys, USB-C Cable
    """
    merchant = receipt_data.get("merchant_name") or "Unknown Merchant"
    category = receipt_data.get("category") or "Uncategorized"
    purchase_date = str(receipt_data.get("purchase_date") or "Unknown Date").strip()
    
    currency = (receipt_data.get("currency") or "").strip().upper()
    curr_sym = CURRENCY_SYMBOLS.get(currency, f"{currency} " if currency else "")
    
    total_amount = receipt_data.get("total_amount")
    if total_amount is not None:
        try:
            total_val = float(total_amount)
            if total_val.is_integer():
                formatted_total = f"{curr_sym}{int(total_val):,}"
            else:
                formatted_total = f"{curr_sym}{total_val:,.2f}"
        except (ValueError, TypeError):
            formatted_total = f"{curr_sym}{total_amount}"
    else:
        formatted_total = "Unknown"

    item_names = []
    for item in items:
        name = item.get("item_name") or item.get("name")
        if name and str(name).strip():
            clean_name = str(name).strip()
            qty = item.get("quantity")
            if qty is not None:
                try:
                    qty_num = float(qty)
                    if qty_num > 1:
                        display_qty = int(qty_num) if qty_num.is_integer() else qty_num
                        clean_name = f"{clean_name} (x{display_qty})"
                except (ValueError, TypeError):
                    pass
            item_names.append(clean_name)

    items_str = ", ".join(item_names) if item_names else "None listed"

    summary_lines = [
        f"Merchant: {merchant}",
        f"Category: {category}",
        f"Date: {purchase_date}",
        f"Total: {formatted_total}",
        f"Items: {items_str}",
    ]
    return "\n".join(summary_lines)


def generate_embedding(summary_text: str) -> List[float]:
    """
    Calls Gemini Embedding 2 (gemini-embedding-2) via the shared Google GenAI client
    to generate an embedding vector with exactly 768 dimensions.
    
    Validates output dimensionality before returning.
    """
    client = get_gemini_client()
    response = client.models.embed_content(
        model="gemini-embedding-2",
        contents=summary_text,
        config=types.EmbedContentConfig(
            output_dimensionality=768
        ),
    )

    if not response.embeddings or len(response.embeddings) == 0:
        raise ValueError("Gemini returned an empty embeddings response.")

    embedding = response.embeddings[0].values
    if not embedding:
        raise ValueError("Gemini embedding values array is empty.")

    if len(embedding) != 768:
        raise ValueError(f"Unexpected embedding dimension: expected 768, got {len(embedding)}")

    return embedding


def upsert_receipt_embedding(
    receipt_id: str,
    user_id: str,
    summary_text: str,
    embedding: List[float]
) -> Dict[str, Any]:
    """
    Upserts a single embedding row into `receipt_embeddings` with `receipt_id`
    as the unique conflict resolution key.
    """
    if not supabase_client:
        raise RuntimeError("Database connection is not initialized.")

    payload = {
        "receipt_id": receipt_id,
        "user_id": user_id,
        "summary_text": summary_text,
        "embedding": embedding,
        "updated_at": "now()",
    }

    res = supabase_client.table("receipt_embeddings").upsert(
        payload,
        on_conflict="receipt_id"
    ).execute()

    if not res.data:
        raise RuntimeError(f"Failed to upsert embedding: no data returned from database for receipt {receipt_id}.")

    return res.data[0]


async def process_receipt_embedding_background(receipt_id: str, user_id: str):
    """
    Asynchronous background pipeline for Phase 3.2:
    1. Fetches the receipt belonging to the authenticated user from Supabase.
    2. Ignores the receipt if it is soft-deleted (deleted_at IS NOT NULL) or not found.
    3. Fetches receipt_items belonging to the receipt.
    4. Reads the current category from the receipt.
    5. Builds the compact semantic summary.
    6. Generates a Gemini Embedding 2 vector with 768 dimensions.
    7. Upserts into receipt_embeddings using receipt_id as the conflict key.
    8. Structured logging of errors without breaking receipt creation or categorization.
    """
    try:
        logger.info(f"DEBUG_EMBEDDING: Starting embedding pipeline for receipt {receipt_id} (user: {user_id})")

        if not supabase_client:
            logger.error(
                "DEBUG_EMBEDDING: Database connection not initialized. Cannot process embedding for receipt %s",
                receipt_id
            )
            return

        # 1. Fetch receipt strictly scoped to authenticated user
        receipt_res = (
            supabase_client.table("receipts")
            .select("id, user_id, merchant_name, category, purchase_date, total_amount, currency, deleted_at")
            .eq("id", receipt_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not receipt_res.data:
            logger.warning(
                f"DEBUG_EMBEDDING: Receipt {receipt_id} not found or does not belong to user {user_id}. Skipping embedding."
            )
            return

        receipt = receipt_res.data[0]

        # 2. Ignore soft-deleted receipts
        if receipt.get("deleted_at") is not None:
            logger.info(
                f"DEBUG_EMBEDDING: Receipt {receipt_id} is soft-deleted (deleted_at={receipt.get('deleted_at')}). Skipping embedding generation."
            )
            return

        # 3. Fetch receipt_items
        items_res = (
            supabase_client.table("receipt_items")
            .select("item_name, quantity, unit_price, total_price")
            .eq("receipt_id", receipt_id)
            .execute()
        )
        items = items_res.data or []

        # 4. Build compact semantic summary
        summary = build_receipt_summary(receipt, items)
        logger.info(f"DEBUG_EMBEDDING: Built summary for receipt {receipt_id}:\n{summary}")

        # 5. Generate embedding vector (768 dimensions)
        embedding = generate_embedding(summary)
        logger.info(
            f"DEBUG_EMBEDDING: Generated 768-dim embedding successfully for receipt {receipt_id}"
        )

        # 6. Upsert into receipt_embeddings
        saved_record = upsert_receipt_embedding(receipt_id, user_id, summary, embedding)
        logger.info(
            f"DEBUG_EMBEDDING: Successfully upserted receipt_embeddings row {saved_record.get('id')} for receipt {receipt_id}"
        )

    except Exception as e:
        logger.error(
            "Failed to generate embedding for receipt %s: %s",
            receipt_id,
            e,
            exc_info=True
        )

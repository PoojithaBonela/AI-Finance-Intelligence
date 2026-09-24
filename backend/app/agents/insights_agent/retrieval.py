import logging
from typing import List, Dict, Any, Optional
from app.database import supabase_client
from .embedding import generate_embedding

logger = logging.getLogger(__name__)


async def search_receipts(
    user_id: str,
    query_text: str,
    top_k: int = 5,
    year: Optional[int] = None,
    month: Optional[int] = None,
    category: Optional[str] = None,
    currency: Optional[str] = None,
    precomputed_embedding: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """
    Semantically searches a user's receipt history using pgvector cosine similarity.

    Requirements enforced:
    - user_id: Authenticated backend user ID (mandatory).
    - query_text: User question/search query. If empty, returns [] immediately.
    - top_k: Number of results to return (bounded between 1 and 50, default 5).
    - Optional filters: year, month, category, currency applied directly in SQL.
    - Soft-deleted receipts are excluded by the database query.
    - User isolation is enforced by the database query.
    - precomputed_embedding: Optional precomputed 768-dim vector to avoid duplicate embedding calls.
    """
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id must be a valid non-empty string.")

    cleaned_query = (query_text or "").strip()
    if not cleaned_query and precomputed_embedding is None:
        logger.debug("search_receipts received empty query. Returning empty result list.")
        return []

    # Clamp top_k to reasonable bounds
    clamped_k = max(1, min(int(top_k), 50))

    if not supabase_client:
        logger.error("search_receipts failed: Database connection is not initialized.")
        raise RuntimeError("Database connection is not initialized.")

    try:
        # 1. Obtain 768-dim embedding vector (reuse precomputed vector if valid)
        if precomputed_embedding is not None and len(precomputed_embedding) == 768:
            logger.info("Reusing precomputed 768-dim query embedding for search_receipts")
            query_vector = precomputed_embedding
        else:
            logger.info(f"Generating query embedding for search: '{cleaned_query}' (user_id={user_id})")
            query_vector = generate_embedding(cleaned_query)

        # 2. Prepare RPC parameters matching the PostgreSQL stored function
        rpc_params = {
            "query_embedding": query_vector,
            "match_user_id": user_id,
            "match_count": clamped_k,
            "filter_year": int(year) if year is not None else None,
            "filter_month": int(month) if month is not None else None,
            "filter_category": str(category).strip() if category else None,
            "filter_currency": str(currency).strip().upper() if currency else None,
        }

        # 3. Call `match_receipts` stored function via Supabase RPC
        logger.info(
            f"Executing match_receipts RPC with filters: year={year}, month={month}, category={category}, currency={currency}, top_k={clamped_k}"
        )
        res = supabase_client.rpc("match_receipts", rpc_params).execute()

        raw_results = res.data or []
        logger.info(f"match_receipts RPC returned {len(raw_results)} matches for user {user_id}")

        # 4. Format the raw database rows into structured, clean receipt dictionaries
        formatted_matches: List[Dict[str, Any]] = []
        for row in raw_results:
            formatted_matches.append({
                "receipt_id": str(row.get("receipt_id")),
                "merchant": row.get("merchant_name") or "Unknown",
                "category": row.get("category") or "Uncategorized",
                "purchase_date": str(row.get("purchase_date")) if row.get("purchase_date") else None,
                "total": float(row.get("total_amount") or 0.0),
                "currency": row.get("currency"),
                "items": row.get("items") or [],
                "summary_text": row.get("summary_text") or "",
                "similarity_score": float(row.get("similarity") or 0.0),
            })

        return formatted_matches

    except Exception as e:
        logger.error(
            "Failed to execute semantic search for user %s with query '%s': %s",
            user_id,
            cleaned_query,
            e,
            exc_info=True,
        )
        raise

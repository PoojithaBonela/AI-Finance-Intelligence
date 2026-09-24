import re
import json
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from google.genai import types
from app.agents.receipt_agent import get_gemini_client
from app.agents.insights_agent.embedding import generate_embedding
from app.database import supabase_client

logger = logging.getLogger(__name__)

EXTRACTION_MODEL = "gemini-3.5-flash-lite"
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM = 768

ALLOWED_MEMORY_TYPES = {"preference", "financial_goal", "profile", "context"}

MEMORY_EXTRACTION_SYSTEM_PROMPT = """You are a strict, conservative memory extraction engine for TracePay, a personal finance assistant.
Your task is to analyze a conversation exchange and determine if the USER explicitly shared durable, long-term personal facts, financial preferences, recurring budget rules, or lifestyle context that should be remembered across future chat sessions.

STRICT CONSTRAINTS:
1. ONLY extract information EXPLICITLY stated or directly confirmed by the USER in their own message.
2. NEVER create a memory based on assistant suggestions, assistant inferences, or assistant speculation.
3. IGNORE transient questions (e.g., "How much did I spend yesterday?", "Show me coffee receipts", "What is my total?").
4. IGNORE one-off receipt details, specific item prices, or transaction dates (receipts are already preserved in the database).
5. IGNORE casual chit-chat, conversational filler ("hello", "thanks", "got it"), and short-term conversational context.
6. If the user did NOT state any durable personal preferences or long-term financial context, output an empty JSON list: []

Allowed memory_type values:
- 'preference': Stated personal preference (e.g., 'User prefers currency in USD', 'User prefers concise summaries').
- 'financial_goal': Explicit user budget target or financial rule (e.g., 'Monthly grocery budget is ₹20,000', 'Saving for a laptop in December').
- 'profile': Enduring personal or household fact (e.g., 'Freelance software engineer', 'Has two children in school').
- 'context': Durable recurring habit or life context (e.g., 'Does grocery shopping weekly at Costco', 'Splits rent 50/50 with roommate').

Return ONLY a valid JSON array of objects:
[
  {
    "memory_text": "Dense, factual 1-sentence statement written from the user perspective (e.g. 'User monthly grocery budget is ₹20,000')",
    "memory_type": "preference" | "financial_goal" | "profile" | "context",
    "importance": 1 to 5,
    "confidence": 0.0 to 1.0
  }
]
If nothing is worth remembering, output exactly: []
Do not include any explanation or markdown formatting other than the JSON array.
"""


async def retrieve_user_memories(
    user_id: str,
    query_text: str = "",
    match_threshold: float = 0.65,
    limit: int = 4,
    filter_type: Optional[str] = None,
    precomputed_embedding: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """
    Semantically retrieves active durable user memories using pgvector cosine similarity.

    Requirements:
    - user_id: Authenticated backend user ID (mandatory, never from LLM).
    - query_text / precomputed_embedding: Query used to search memory.
    - match_threshold: Minimum cosine similarity (default 0.65).
    - limit: Max number of memories to return (default 4).
    - filter_type: Optional memory_type filter ('preference', 'financial_goal', etc.).
    - precomputed_embedding: Optional pre-generated 768-dim vector to avoid duplicate embedding calls.
    """
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id must be a valid non-empty string.")

    if not supabase_client:
        logger.error("retrieve_user_memories: Database connection not initialized.")
        raise RuntimeError("Database connection not initialized.")

    cleaned_query = (query_text or "").strip()
    if not cleaned_query and not precomputed_embedding:
        return []

    try:
        # 1. Obtain query embedding (reuse precomputed vector if provided)
        if precomputed_embedding is not None:
            if len(precomputed_embedding) != EMBEDDING_DIM:
                raise ValueError(f"Precomputed embedding dimension must be {EMBEDDING_DIM}, got {len(precomputed_embedding)}")
            query_vector = precomputed_embedding
        else:
            query_vector = generate_embedding(cleaned_query)

        # 2. Call `match_user_memories` RPC
        rpc_params = {
            "query_embedding": query_vector,
            "match_user_id": str(user_id).strip(),
            "match_threshold": float(match_threshold),
            "match_count": max(1, min(int(limit), 20)),
            "filter_type": filter_type.strip() if filter_type else None,
        }

        res = supabase_client.rpc("match_user_memories", rpc_params).execute()
        raw_rows = res.data or []

        # 3. Format structured output
        results: List[Dict[str, Any]] = []
        memory_ids_to_touch: List[str] = []

        for row in raw_rows:
            mem_id = str(row.get("id"))
            memory_ids_to_touch.append(mem_id)
            results.append({
                "id": mem_id,
                "memory_type": row.get("memory_type"),
                "memory_text": row.get("memory_text"),
                "importance": int(row.get("importance") or 3),
                "similarity": float(row.get("similarity") or 0.0),
            })

        # 4. Asynchronously update last_used_at timestamp on matched memories
        if memory_ids_to_touch:
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                for mid in memory_ids_to_touch:
                    supabase_client.table("user_memories").update({"last_used_at": now_iso}).eq("id", mid).eq("user_id", user_id).execute()
            except Exception as touch_err:
                logger.warning(f"Failed to update last_used_at for memories {memory_ids_to_touch}: {touch_err}")

        return results

    except Exception as e:
        logger.error(f"Error retrieving user memories for user {user_id}: {e}", exc_info=True)
        return []


def extract_memories_from_text(user_message: str, assistant_message: str) -> List[Dict[str, Any]]:
    """
    Uses gemini-3.5-flash-lite to conservatively extract candidate user memories
    from the user/assistant exchange.
    """
    clean_user = (user_message or "").strip()
    if not clean_user:
        return []

    client = get_gemini_client()
    prompt = f"USER MESSAGE:\n{clean_user}\n\nASSISTANT MESSAGE:\n{(assistant_message or '').strip()}"

    try:
        response = None
        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model=EXTRACTION_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=MEMORY_EXTRACTION_SYSTEM_PROMPT,
                        temperature=0.1,
                    )
                )
                break
            except Exception as e:
                err_msg = str(e)
                if attempt < 3 and any(k in err_msg for k in ["503", "UNAVAILABLE", "ResourceExhausted", "429", "timeout"]):
                    wait_sec = 2.0 * (attempt + 1)
                    logger.warning(f"Transient Gemini error in memory extraction (attempt {attempt+1}/4): {e}. Retrying in {wait_sec}s...")
                    time.sleep(wait_sec)
                else:
                    raise

        if not response:
            return []

        response_text = (response.text or "").strip()
        if not response_text or response_text == "[]":
            return []

        # Strip markdown fences if present
        clean_json = re.sub(r"^```(?:json)?\s*", "", response_text, flags=re.MULTILINE)
        clean_json = re.sub(r"```\s*$", "", clean_json, flags=re.MULTILINE).strip()

        candidates = json.loads(clean_json)
        if not isinstance(candidates, list):
            return []

        validated: List[Dict[str, Any]] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            text = (item.get("memory_text") or "").strip()
            mem_type = (item.get("memory_type") or "").strip().lower()
            if not text or mem_type not in ALLOWED_MEMORY_TYPES:
                continue

            try:
                importance = max(1, min(int(item.get("importance", 3)), 5))
            except (ValueError, TypeError):
                importance = 3

            try:
                confidence = max(0.0, min(float(item.get("confidence", 1.0)), 1.0))
            except (ValueError, TypeError):
                confidence = 1.0

            validated.append({
                "memory_text": text,
                "memory_type": mem_type,
                "importance": importance,
                "confidence": confidence,
            })

        return validated

    except Exception as e:
        logger.error(f"Failed to extract memories using Gemini: {e}", exc_info=True)
        return []


async def extract_and_persist_memories_bg(
    user_id: str,
    conversation_id: Optional[str],
    user_message: str,
    assistant_message: str,
    source_message_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Background pipeline to extract, deduplicate, conflict-resolve, and persist durable user memories.
    Safe for background execution: logs all errors without raising exceptions.
    """
    if not user_id or not str(user_id).strip():
        logger.warning("extract_and_persist_memories_bg called without valid user_id.")
        return []

    if not supabase_client:
        logger.error("extract_and_persist_memories_bg: Database connection not initialized.")
        return []

    try:
        # 1. Extract candidate memories from conversation turn
        candidates = extract_memories_from_text(user_message, assistant_message)
        if not candidates:
            logger.info("No durable user memories extracted from exchange.")
            return []

        logger.info(f"Extracted {len(candidates)} candidate memories for user {user_id}")
        persisted_records: List[Dict[str, Any]] = []

        now_iso = datetime.now(timezone.utc).isoformat()

        for cand in candidates:
            mem_text = cand["memory_text"]
            mem_type = cand["memory_type"]

            # 2. Generate 768-dim embedding
            embedding = generate_embedding(mem_text)
            if len(embedding) != EMBEDDING_DIM:
                logger.error(f"Embedding dimension mismatch: expected {EMBEDDING_DIM}, got {len(embedding)}")
                continue

            # 3. Check for duplicates and conflicts via match_user_memories RPC
            existing_matches = await retrieve_user_memories(
                user_id=user_id,
                precomputed_embedding=embedding,
                match_threshold=0.72,
                limit=5,
                filter_type=mem_type,
            )

            is_duplicate = False
            for match in existing_matches:
                sim = match["similarity"]
                existing_text = match["memory_text"].strip().lower()
                cand_text = mem_text.strip().lower()

                # Extract digits to check if financial amounts/numbers changed
                existing_digits = re.findall(r'\d+', existing_text)
                cand_digits = re.findall(r'\d+', cand_text)

                # If text is identical or (similarity >= 0.95 with identical numbers), treat as duplicate
                if existing_text == cand_text or (sim >= 0.95 and existing_digits == cand_digits):
                    logger.info(f"Duplicate memory detected (sim={sim:.4f}): '{match['memory_text']}'. Updating timestamps.")
                    supabase_client.table("user_memories").update({
                        "last_used_at": now_iso,
                        "updated_at": now_iso,
                    }).eq("id", match["id"]).eq("user_id", user_id).execute()
                    is_duplicate = True
                    break
                # Topic overlap with different details/values -> Deactivate conflicting older memory
                elif sim >= 0.72:
                    logger.info(f"Conflicting/Updated memory detected (sim={sim:.4f}): Deactivating old memory '{match['memory_text']}' in favor of '{mem_text}'.")
                    supabase_client.table("user_memories").update({
                        "is_active": False,
                        "updated_at": now_iso,
                    }).eq("id", match["id"]).eq("user_id", user_id).execute()

            if is_duplicate:
                continue

            # 4. Insert new active memory
            payload = {
                "user_id": user_id,
                "memory_type": mem_type,
                "memory_text": mem_text,
                "embedding": embedding,
                "source_conversation_id": conversation_id,
                "source_message_id": source_message_id,
                "confidence": cand["confidence"],
                "importance": cand["importance"],
                "is_active": True,
                "last_used_at": now_iso,
                "updated_at": now_iso,
            }

            res = supabase_client.table("user_memories").insert(payload).execute()
            if res.data:
                saved = res.data[0]
                logger.info(f"Successfully saved new user memory ({mem_type}): '{mem_text}' (id={saved['id']})")
                persisted_records.append(saved)

        return persisted_records

    except Exception as e:
        logger.error(f"Failed to extract and persist memories for user {user_id}: {e}", exc_info=True)
        return []

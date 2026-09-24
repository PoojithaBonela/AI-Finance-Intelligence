import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from google.genai import types
from app.agents.receipt_agent import get_gemini_client
from app.database import supabase_client

logger = logging.getLogger(__name__)

SUMMARY_MODEL = "gemini-3.5-flash-lite"

SUMMARY_SYSTEM_PROMPT = """You are a precise, dense conversation summarizer for TracePay, a personal finance assistant.
Your task is to maintain a running summary of an ongoing financial discussion.

INSTRUCTIONS:
1. Incorporate the new conversation turns into the existing summary (if one exists).
2. Produce a single, coherent, dense, and factual summary (maximum ~200 words).
3. PRESERVE key financial facts: exact amounts, merchants, dates, categories, budget limits, and spending trends discussed.
4. PRESERVE user constraints, financial preferences, goals, or decisions agreed upon in the conversation.
5. DO NOT invent facts, numbers, or conclusions not present in the dialogue.
6. DO NOT include greetings, conversational pleasantries, or meta-commentary (e.g., do not say "The user asked... and then the assistant answered..."). State facts directly.
7. Return ONLY the plain text summary without markdown headers or fluff.
"""


async def update_conversation_summary_bg(
    conversation_id: str,
    user_id: str
) -> Optional[str]:
    """
    Maintains a compact running summary of older conversation turns.

    Rules enforced:
    - Trigger condition: Conversation must have more than 10 messages total.
    - Latest 6 messages are always kept outside the summary as raw active context.
    - Summarizes unsummarized messages older than the last 6.
    - Uses `summarized_through_message_id` to ensure idempotency and prevent duplicate work.
    - Never deletes or overwrites permanent messages in the `messages` table.
    - Updates `conversations.summary` and `conversations.summarized_through_message_id`.
    - Scoped strictly to the authenticated user.
    """
    if not conversation_id or not user_id:
        logger.warning("update_conversation_summary_bg called without conversation_id or user_id.")
        return None

    if not supabase_client:
        logger.error("update_conversation_summary_bg: Database connection not initialized.")
        return None

    try:
        # 1. Fetch conversation metadata and verify ownership
        conv_res = (
            supabase_client.table("conversations")
            .select("id, user_id, summary, summarized_through_message_id")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not conv_res.data:
            logger.warning(
                f"Conversation {conversation_id} not found or does not belong to user {user_id}. Skipping summary."
            )
            return None

        conv = conv_res.data[0]
        current_summary = (conv.get("summary") or "").strip()
        summarized_through_id = conv.get("summarized_through_message_id")

        # 2. Fetch all messages for this conversation ordered by created_at ASC
        msg_res = (
            supabase_client.table("messages")
            .select("id, role, content, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )

        messages = msg_res.data or []
        total_count = len(messages)

        # Trigger condition: Only summarize if conversation has > 10 messages
        if total_count <= 10:
            logger.info(
                f"Conversation {conversation_id} has {total_count} messages (<= 10). Skipping summarization."
            )
            return current_summary or None

        # 3. Buffer strategy: Latest 6 messages remain raw outside the summary
        eligible_for_summary = messages[:-6]
        if not eligible_for_summary:
            logger.info("No messages eligible for summarization outside the latest 6 window.")
            return current_summary or None

        # 4. Determine which eligible messages have not yet been summarized
        unsummarized_messages: List[Dict[str, Any]] = []

        if not summarized_through_id:
            # Nothing summarized yet; all eligible messages need summarization
            unsummarized_messages = eligible_for_summary
        else:
            # Find index of the message through which we previously summarized
            match_idx = -1
            for idx, msg in enumerate(eligible_for_summary):
                if str(msg.get("id")) == str(summarized_through_id):
                    match_idx = idx
                    break

            if match_idx >= 0:
                # Only summarize messages that come AFTER the last summarized message
                unsummarized_messages = eligible_for_summary[match_idx + 1:]
            else:
                # If the marker wasn't found in eligible list (or was older), summarize all eligible
                unsummarized_messages = eligible_for_summary

        if not unsummarized_messages:
            logger.info(
                f"Summary for conversation {conversation_id} is up to date (through message {summarized_through_id})."
            )
            return current_summary or None

        logger.info(
            f"Summarizing {len(unsummarized_messages)} unsummarized messages for conversation {conversation_id} (total={total_count})"
        )

        # 5. Format conversation turns for the summarizer model
        formatted_turns = []
        for msg in unsummarized_messages:
            role_label = "User" if msg.get("role") == "user" else "Assistant"
            formatted_turns.append(f"{role_label}: {msg.get('content', '')}")
        turns_text = "\n".join(formatted_turns)

        prompt = f"""EXISTING SUMMARY:
{current_summary if current_summary else "None (this is the first summary)."}

NEW CONVERSATION TURNS TO INCORPORATE:
{turns_text}
"""

        # 6. Generate updated summary using gemini-3.5-flash-lite
        client = get_gemini_client()
        response = None
        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model=SUMMARY_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SUMMARY_SYSTEM_PROMPT,
                        temperature=0.2,
                    )
                )
                break
            except Exception as e:
                err_msg = str(e)
                if attempt < 3 and any(k in err_msg for k in ["503", "UNAVAILABLE", "ResourceExhausted", "429", "timeout"]):
                    wait_sec = 2.0 * (attempt + 1)
                    logger.warning(f"Transient Gemini error in conversation summary (attempt {attempt+1}/4): {e}. Retrying in {wait_sec}s...")
                    time.sleep(wait_sec)
                else:
                    raise

        if not response:
            return current_summary or None

        new_summary_text = (response.text or "").strip()
        if not new_summary_text:
            logger.warning("Gemini returned empty text for conversation summary. Preserving existing summary.")
            return current_summary or None

        # 7. Update conversation record with new summary and advanced summarized_through_message_id
        last_summarized_msg = unsummarized_messages[-1]
        new_summarized_through_id = str(last_summarized_msg["id"])
        now_iso = datetime.now(timezone.utc).isoformat()

        update_res = (
            supabase_client.table("conversations")
            .update({
                "summary": new_summary_text,
                "summarized_through_message_id": new_summarized_through_id,
                "updated_at": now_iso,
            })
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )

        if update_res.data:
            logger.info(
                f"Successfully updated conversation {conversation_id} summary through message {new_summarized_through_id}."
            )
            return new_summary_text

        return current_summary or None

    except Exception as e:
        logger.error(
            f"Failed to update conversation summary for conversation {conversation_id} (user {user_id}): {e}",
            exc_info=True
        )
        return None

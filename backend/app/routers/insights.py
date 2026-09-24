import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from pydantic import BaseModel, Field

from app.database import supabase_client
from app.dependencies import get_current_user
from app.agents.insights_agent.schemas import ChatMessage
from app.agents.insights_agent.agent import run_insights_agent
from app.agents.insights_agent.embedding import generate_embedding
from app.services.memory_service import (
    retrieve_user_memories,
    extract_and_persist_memories_bg,
)
from app.services.summary_service import update_conversation_summary_bg

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/insights", tags=["AI Insights"])


# ============================================================================
# Schemas
# ============================================================================

class AskInsightsRequest(BaseModel):
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional UUID of an existing conversation thread. If omitted, a new conversation is started.",
    )
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The natural language question to ask the AI financial insights assistant.",
    )


class AskInsightsResponse(BaseModel):
    conversation_id: str
    answer: str
    tools_used: List[str]
    rounds_used: int
    created_at: str
    title: Optional[str] = None


class MessageItem(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    metadata: Dict[str, Any]
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    created_at: str
    updated_at: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    created_at: str
    updated_at: str
    messages: List[MessageItem]
    total_messages: int
    limit: int
    offset: int


# ============================================================================
# Helpers
# ============================================================================

def generate_conversation_title(question: str) -> str:
    """
    Generates a clean, deterministic title from the user's initial question
    without requiring redundant LLM generation calls.
    """
    cleaned = " ".join((question or "").strip().split())
    if not cleaned:
        return "New Chat"

    lower = cleaned.lower()
    prefixes = [
        "how much did i spend on ",
        "how much do i spend on ",
        "how much have i spent on ",
        "how much did i spend ",
        "what were my ",
        "what are my ",
        "can you show me ",
        "show me ",
        "tell me about ",
        "what did i buy ",
        "why did i spend ",
    ]
    title_candidate = cleaned
    for p in prefixes:
        if lower.startswith(p):
            sub = cleaned[len(p):].strip()
            if sub:
                title_candidate = sub[0].upper() + sub[1:]
                break

    title_candidate = title_candidate.rstrip("?.,! ")
    if len(title_candidate) <= 40:
        return title_candidate
    truncated = title_candidate[:40]
    last_space = truncated.rfind(" ")
    if last_space > 20:
        truncated = truncated[:last_space]
    return f"{truncated}..."


def validate_uuid(val: str, param_name: str = "conversation_id") -> str:
    """Validates that a string is a valid UUID, raising HTTP 400 if not."""
    try:
        return str(uuid.UUID(str(val)))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {param_name} format. Must be a valid UUID.",
        )


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/ask", response_model=AskInsightsResponse)
async def ask_insights(
    req: AskInsightsRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
):
    """
    Ask a question to the TracePay AI Financial Insights Agent (Agent 3).

    Handles 3-Layer Persistent Memory:
    1. Conversation & Message Audit Log: All turns stored permanently in Supabase.
    2. Intra-Chat Summarization: Running summary for older context (>10 messages).
    3. Cross-Chat User Memory: Semantic pgvector retrieval for durable preferences/goals.
    """
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection not initialized.",
        )

    cleaned_question = req.question.strip()
    if not cleaned_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty or whitespace only.",
        )

    conversation_id: str
    summary: Optional[str] = None
    history: List[ChatMessage] = []

    # 1. Resolve Conversation (Existing vs New)
    if req.conversation_id:
        conversation_id = validate_uuid(req.conversation_id, "conversation_id")

        conv_res = (
            supabase_client.table("conversations")
            .select("*")
            .eq("id", conversation_id)
            .execute()
        )
        if not conv_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )

        conv = conv_res.data[0]
        # Strict user ownership check
        if conv["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this conversation.",
            )

        summary = conv.get("summary")
        existing_title = conv.get("title")

        # Query latest 6 messages newest-first, then reverse to chronological order
        recent_msg_res = (
            supabase_client.table("messages")
            .select("id, role, content, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .limit(6)
            .execute()
        )
        raw_recent = recent_msg_res.data or []
        chrono_recent = list(reversed(raw_recent))
        history = [ChatMessage(role=m["role"], content=m["content"]) for m in chrono_recent]

    else:
        # Create brand-new conversation
        title = generate_conversation_title(cleaned_question)
        new_conv_res = (
            supabase_client.table("conversations")
            .insert({
                "user_id": user_id,
                "title": title,
            })
            .execute()
        )
        if not new_conv_res.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create new conversation.",
            )
        conversation_id = new_conv_res.data[0]["id"]
        summary = None
        existing_title = title
        history = []

    # 2. Persist User Message to messages table
    user_msg_res = (
        supabase_client.table("messages")
        .insert({
            "conversation_id": conversation_id,
            "role": "user",
            "content": cleaned_question,
            "metadata": {},
        })
        .execute()
    )
    user_msg_id = user_msg_res.data[0]["id"] if user_msg_res.data else None

    # 3. Precompute 768-dim Query Embedding Once (reusable across memory + receipt RAG)
    try:
        query_embedding = generate_embedding(cleaned_question)
    except Exception as emb_err:
        logger.warning(f"Could not generate query embedding: {emb_err}")
        query_embedding = None

    # 4. Retrieve Cross-Chat User Memories
    memories_texts: Optional[List[str]] = None
    if query_embedding:
        try:
            memories_records = await retrieve_user_memories(
                user_id=user_id,
                precomputed_embedding=query_embedding,
                match_threshold=0.65,
                limit=4,
            )
            memories_texts = [r["memory_text"] for r in memories_records if r.get("memory_text")]
        except Exception as mem_err:
            logger.warning(f"Error retrieving user memories: {mem_err}")
            memories_texts = []

    # 5. Execute Agent 3 Orchestration Loop
    try:
        agent_response = await run_insights_agent(
            user_id=user_id,
            question=cleaned_question,
            history=history,
            summary=summary,
            memories=memories_texts,
            precomputed_embedding=query_embedding,
        )
    except Exception as agent_err:
        logger.error(f"Agent 3 execution failure for user {user_id}: {agent_err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate AI insights response. Please try again.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    tools_used_names = [t.tool_name for t in agent_response.tools_used]

    # 6. Persist Assistant Response to messages table with operational metadata
    asst_metadata = {
        "tools_used": tools_used_names,
        "rounds_used": agent_response.rounds_used,
    }
    supabase_client.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": agent_response.answer,
        "metadata": asst_metadata,
    }).execute()

    # 7. Update conversation updated_at timestamp (and title if it was 'New Chat')
    update_data = {"updated_at": now_iso}
    final_title = existing_title
    if existing_title in ("New Chat", "New Conversation", None, ""):
        final_title = generate_conversation_title(cleaned_question)
        update_data["title"] = final_title

    supabase_client.table("conversations").update(update_data).eq("id", conversation_id).execute()

    # 8. Enqueue Asynchronous Background Tasks (Memory Extraction + Summarization)
    background_tasks.add_task(
        extract_and_persist_memories_bg,
        user_id=user_id,
        conversation_id=conversation_id,
        user_message=cleaned_question,
        assistant_message=agent_response.answer,
        source_message_id=user_msg_id,
    )
    background_tasks.add_task(
        update_conversation_summary_bg,
        conversation_id=conversation_id,
        user_id=user_id,
    )

    return AskInsightsResponse(
        conversation_id=conversation_id,
        answer=agent_response.answer,
        tools_used=tools_used_names,
        rounds_used=agent_response.rounds_used,
        created_at=now_iso,
        title=final_title,
    )


@router.post("/conversations", response_model=ConversationSummary, status_code=status.HTTP_200_OK)
async def create_conversation(
    user_id: str = Depends(get_current_user),
):
    """
    Create a new persistent conversation immediately when the user clicks '+ New Chat'.
    Request body is empty. user_id derived exclusively from get_current_user.
    """
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection not initialized.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    new_conv_res = (
        supabase_client.table("conversations")
        .insert({
            "user_id": user_id,
            "title": "New Chat",
            "summary": None,
            "summarized_through_message_id": None,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        .execute()
    )
    if not new_conv_res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create new conversation.",
        )
    created = new_conv_res.data[0]
    return ConversationSummary(
        id=created["id"],
        title=created["title"],
        summary=created.get("summary"),
        created_at=created["created_at"],
        updated_at=created["updated_at"],
    )


@router.get("/conversations", response_model=List[ConversationSummary])
async def list_conversations(
    limit: int = Query(20, ge=1, le=100, description="Max conversations to return."),
    offset: int = Query(0, ge=0, description="Pagination offset."),
    user_id: str = Depends(get_current_user),
):
    """
    List conversations belonging to the authenticated user, ordered by most recently updated.
    """
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection not initialized.",
        )

    res = (
        supabase_client.table("conversations")
        .select("id, title, summary, created_at, updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return res.data or []


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_detail(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100, description="Page limit for messages."),
    offset: int = Query(0, ge=0, description="Page offset for messages."),
    user_id: str = Depends(get_current_user),
):
    """
    Fetch a single conversation and its paginated messages in chronological order.
    """
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection not initialized.",
        )

    valid_id = validate_uuid(conversation_id, "conversation_id")

    # Verify conversation existence and ownership
    conv_res = (
        supabase_client.table("conversations")
        .select("*")
        .eq("id", valid_id)
        .execute()
    )
    if not conv_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    conv = conv_res.data[0]
    if conv["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this conversation.",
        )

    # Fetch total count of messages
    count_res = (
        supabase_client.table("messages")
        .select("id", count="exact")
        .eq("conversation_id", valid_id)
        .execute()
    )
    total_messages = count_res.count if count_res.count is not None else 0

    # Fetch paginated messages in chronological order
    msg_res = (
        supabase_client.table("messages")
        .select("id, conversation_id, role, content, metadata, created_at")
        .eq("conversation_id", valid_id)
        .order("created_at", desc=False)
        .range(offset, offset + limit - 1)
        .execute()
    )
    raw_messages = msg_res.data or []

    messages = [
        MessageItem(
            id=m["id"],
            conversation_id=m["conversation_id"],
            role=m["role"],
            content=m["content"],
            metadata=m.get("metadata") or {},
            created_at=m["created_at"],
        )
        for m in raw_messages
    ]

    return ConversationDetail(
        id=conv["id"],
        title=conv["title"],
        summary=conv.get("summary"),
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        messages=messages,
        total_messages=total_messages,
        limit=limit,
        offset=offset,
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Delete a conversation thread.
    - Messages are cascade-deleted by the database.
    - User memories derived from this conversation remain active and independent.
    """
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection not initialized.",
        )

    valid_id = validate_uuid(conversation_id, "conversation_id")

    # Verify conversation existence and ownership
    conv_res = (
        supabase_client.table("conversations")
        .select("id, user_id")
        .eq("id", valid_id)
        .execute()
    )
    if not conv_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    conv = conv_res.data[0]
    if conv["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this conversation.",
        )

    # Delete conversation (Postgres CASCADE deletes messages; user_memories.conversation_id set to NULL)
    del_res = (
        supabase_client.table("conversations")
        .delete()
        .eq("id", valid_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not del_res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation.",
        )

    return {
        "status": "success",
        "message": "Conversation deleted successfully.",
        "conversation_id": valid_id,
    }

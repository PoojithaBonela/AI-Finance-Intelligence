import logging
import asyncio
from typing import List, Dict, Any, Optional
from google.genai import types
from app.agents.receipt_agent import get_gemini_client
from .prompts import AGENT3_SYSTEM_PROMPT
from .schemas import ChatMessage, ToolCallRecord, Agent3Response
from .tools import (
    get_total_spending,
    get_category_breakdown,
    get_monthly_spending,
    get_yearly_spending,
    get_largest_expenses,
    get_recent_purchases,
)
from .retrieval import search_receipts
from .embedding import generate_embedding

logger = logging.getLogger(__name__)

# Primary production model for Agent 3 reasoning and tool orchestration
AGENT3_MODEL = "gemini-3.5-flash-lite"
MAX_TOOL_ROUNDS = 5

# Tool execution registry (all tools require user_id injected by the backend)
TOOL_REGISTRY = {
    "get_total_spending": get_total_spending,
    "get_category_breakdown": get_category_breakdown,
    "get_monthly_spending": get_monthly_spending,
    "get_yearly_spending": get_yearly_spending,
    "get_largest_expenses": get_largest_expenses,
    "get_recent_purchases": get_recent_purchases,
    "search_receipts": search_receipts,
}

# Declarations exposed to Gemini (CRITICAL: user_id is deliberately OMITTED from these schemas)
GEMINI_FUNCTION_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_total_spending",
        description="Calculate total spending and count of receipts for the user. Supports optional filters for year, month (1-12), category, and target currency.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "year": types.Schema(type="INTEGER", description="The 4-digit calendar year (e.g. 2024, 2025)."),
                "month": types.Schema(type="INTEGER", description="Calendar month from 1 to 12 (1=Jan, 12=Dec). Requires year."),
                "category": types.Schema(type="STRING", description="Expense category filter (e.g. 'Food & Dining', 'Shopping', 'Travel')."),
                "currency": types.Schema(type="STRING", description="Target 3-letter currency code (e.g. 'USD', 'INR', 'EUR') to convert amounts."),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="get_category_breakdown",
        description="Get spending grouped by category with transaction counts, totals, and percentages of total spending. Sorted by highest spending first.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "year": types.Schema(type="INTEGER", description="The 4-digit calendar year."),
                "month": types.Schema(type="INTEGER", description="Calendar month 1-12 (requires year)."),
                "category": types.Schema(type="STRING", description="Filter for a specific category."),
                "currency": types.Schema(type="STRING", description="Target 3-letter currency code."),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="get_monthly_spending",
        description="Get monthly spending for all 12 calendar months (January through December) of a specific year.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "year": types.Schema(type="INTEGER", description="The 4-digit year to examine (e.g. 2024)."),
                "currency": types.Schema(type="STRING", description="Target 3-letter currency code."),
            },
            required=["year"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_yearly_spending",
        description="Get spending grouped by year for all years with recorded receipts.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "currency": types.Schema(type="STRING", description="Target 3-letter currency code."),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="get_largest_expenses",
        description="Retrieve the user's largest individual receipts sorted by highest amount first. Includes merchant, date, total, and line items.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "year": types.Schema(type="INTEGER", description="Filter by 4-digit year."),
                "month": types.Schema(type="INTEGER", description="Filter by calendar month 1-12."),
                "category": types.Schema(type="STRING", description="Filter by expense category."),
                "currency": types.Schema(type="STRING", description="Target 3-letter currency code."),
                "limit": types.Schema(type="INTEGER", description="Maximum number of expenses to return (default 5)."),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="get_recent_purchases",
        description="Retrieve the user's most recent purchases sorted by purchase date descending. Includes merchant, date, total, and line items.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "limit": types.Schema(type="INTEGER", description="Maximum number of purchases to return (default 5)."),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="search_receipts",
        description="Semantically search receipts for specific items, keywords, merchants, or product names using vector retrieval.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "query_text": types.Schema(type="STRING", description="Natural language search phrase describing items or context (e.g. 'headphones', 'coffee', 'groceries')."),
                "top_k": types.Schema(type="INTEGER", description="Number of results to retrieve (default 5)."),
                "year": types.Schema(type="INTEGER", description="Optional year filter."),
                "month": types.Schema(type="INTEGER", description="Optional calendar month 1-12."),
                "category": types.Schema(type="STRING", description="Optional category filter."),
                "currency": types.Schema(type="STRING", description="Optional currency filter."),
            },
            required=["query_text"],
        ),
    ),
]

GEMINI_TOOLS = [types.Tool(function_declarations=GEMINI_FUNCTION_DECLARATIONS)]


def build_agent3_system_instruction(
    memories: Optional[List[str]] = None,
    summary: Optional[str] = None,
) -> str:
    """
    Builds the complete Agent 3 system instruction according to the required context order:
    1. Agent 3 system prompt
    2. Relevant user memories, only when present
    3. Current conversation summary, only when present
    """
    parts = [AGENT3_SYSTEM_PROMPT.strip()]

    if memories:
        clean_mems = [m.strip() for m in memories if m and str(m).strip()]
        if clean_mems:
            mem_text = "\n".join(f"- {m}" for m in clean_mems)
            parts.append(f"<relevant_user_memories>\n{mem_text}\n</relevant_user_memories>")

    if summary and str(summary).strip():
        parts.append(f"<conversation_summary>\n{summary.strip()}\n</conversation_summary>")

    return "\n\n".join(parts)


async def run_insights_agent(
    user_id: str,
    question: str,
    history: Optional[List[ChatMessage]] = None,
    summary: Optional[str] = None,
    memories: Optional[List[str]] = None,
    precomputed_embedding: Optional[List[float]] = None,
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> Agent3Response:
    """
    Core Agent 3 orchestration loop with 3-Layer Memory Context Assembly:
    1. Checks user memories: auto-retrieves relevant memories via pgvector if not explicitly provided.
    2. Reuses precomputed 768-dim query embedding across memory retrieval and receipt RAG.
    3. Assembles prompt context in strict order:
       - System prompt
       - <relevant_user_memories> (if present)
       - <conversation_summary> (if present)
       - Recent conversation messages (up to 6 raw messages)
       - Current user question
    4. Runs multi-turn tool-calling loop (up to max_rounds).
    5. Securely injects authenticated user_id into all tool executions.
    6. Returns structured Agent3Response.
    """
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id must be a valid non-empty string.")

    cleaned_question = (question or "").strip()
    if not cleaned_question:
        return Agent3Response(
            answer="Please ask a question about your receipts or spending.",
            tools_used=[],
            rounds_used=0,
        )

    # 1. User Memory Retrieval & Query Embedding Generation
    active_memories = list(memories) if memories is not None else None
    if active_memories is None and user_id:
        try:
            from app.services.memory_service import retrieve_user_memories

            if precomputed_embedding is None:
                precomputed_embedding = generate_embedding(cleaned_question)

            retrieved_mem_records = await retrieve_user_memories(
                user_id=user_id,
                precomputed_embedding=precomputed_embedding,
                match_threshold=0.65,
                limit=4,
            )
            active_memories = [r["memory_text"] for r in retrieved_mem_records if r.get("memory_text")]
        except Exception as mem_err:
            logger.warning(f"Failed to auto-retrieve user memories for user {user_id}: {mem_err}")
            active_memories = []

    # 2. Build layered system instruction: System Prompt -> Memories -> Summary
    system_instruction = build_agent3_system_instruction(
        memories=active_memories,
        summary=summary,
    )

    client = get_gemini_client()

    # 3. Assemble conversation contents: Recent Raw Messages (up to 6) -> Current Question
    contents: List[types.Content] = []

    if history:
        # Keep latest 6 messages as raw conversation window
        raw_window = history[-6:] if len(history) > 6 else history
        for msg in raw_window:
            role = "user" if msg.role == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.content)]
                )
            )

    # Append current user prompt
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=cleaned_question)]
        )
    )

    tools_used: List[ToolCallRecord] = []
    rounds_used = 0

    try:
        # 4. Multi-turn tool calling loop
        for round_idx in range(max_rounds):
            rounds_used += 1
            logger.info(f"Agent 3 Turn {round_idx + 1}/{max_rounds} for user {user_id}")

            # Call Gemini with retry for transient server/network errors
            response = None
            for attempt in range(4):
                try:
                    response = client.models.generate_content(
                        model=AGENT3_MODEL,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            tools=GEMINI_TOOLS,
                            temperature=0.2,
                        )
                    )
                    break
                except Exception as api_err:
                    if attempt < 3:
                        wait_sec = 2.0 * (attempt + 1)
                        logger.warning(f"Transient Gemini/network error (attempt {attempt+1}/4): {api_err}. Retrying in {wait_sec}s...")
                        await asyncio.sleep(wait_sec)
                    else:
                        raise

            # Check if Gemini requested tool call(s)
            function_calls = response.function_calls

            if not function_calls:
                final_text = response.text or "I reviewed your financial data, but have no additional details to report."
                logger.info(f"Agent 3 produced final text answer in round {rounds_used}")
                return Agent3Response(
                    answer=final_text.strip(),
                    tools_used=tools_used,
                    rounds_used=rounds_used,
                )

            # Record model's intermediate tool call message in conversation thread
            if response.candidates and response.candidates[0].content:
                contents.append(response.candidates[0].content)

            # 5. Execute all requested tool calls in this turn
            response_parts: List[types.Part] = []

            for fc in function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args or {})
                logger.info(f"Agent 3 requested tool '{tool_name}' with args: {tool_args}")

                tool_fn = TOOL_REGISTRY.get(tool_name)
                if not tool_fn:
                    err_msg = f"Unknown tool: '{tool_name}'"
                    logger.error(err_msg)
                    tool_result = {"error": err_msg}
                else:
                    try:
                        # Optimization: Reuse precomputed query embedding if search_receipts queries the user's question
                        if tool_name == "search_receipts" and precomputed_embedding:
                            tool_q = str(tool_args.get("query_text") or "").strip().lower()
                            if tool_q == cleaned_question.lower():
                                tool_args["precomputed_embedding"] = precomputed_embedding

                        # CRITICAL: Backend securely injects authenticated user_id
                        tool_result = await tool_fn(user_id=user_id, **tool_args)
                    except Exception as tool_err:
                        logger.error(f"Error executing tool '{tool_name}': {tool_err}", exc_info=True)
                        tool_result = {"error": f"Tool execution failed: {str(tool_err)}"}

                tools_used.append(
                    ToolCallRecord(
                        tool_name=tool_name,
                        arguments=dict(fc.args or {}),
                        result=tool_result,
                    )
                )

                # Format tool result as FunctionResponse part
                response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": tool_result}
                    )
                )

            # Append tool responses to contents for next turn
            contents.append(
                types.Content(
                    role="user",
                    parts=response_parts
                )
            )

        # If max_rounds exceeded without final answer, force synthesis without tools
        logger.warning(f"Agent 3 reached max_rounds ({max_rounds}). Forcing final answer.")
        final_synth = None
        for attempt in range(4):
            try:
                final_synth = client.models.generate_content(
                    model=AGENT3_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2,
                    )
                )
                break
            except Exception as api_err:
                if attempt < 3:
                    wait_sec = 2.0 * (attempt + 1)
                    logger.warning(f"Transient Gemini/network error in final synth (attempt {attempt+1}/4): {api_err}. Retrying in {wait_sec}s...")
                    await asyncio.sleep(wait_sec)
                else:
                    raise

        return Agent3Response(
            answer=(final_synth.text or "I gathered your purchase data, but reached the maximum tool reasoning steps.").strip(),
            tools_used=tools_used,
            rounds_used=rounds_used,
        )

    except Exception as e:
        logger.error(f"Agent 3 failed for user {user_id}: {e}", exc_info=True)
        raise

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(description="The role of the message author: 'user' or 'assistant'.")
    content: str = Field(description="The text content of the message.")


class ToolCallRecord(BaseModel):
    tool_name: str = Field(description="Name of the tool executed by the backend.")
    arguments: Dict[str, Any] = Field(description="Arguments chosen by Gemini for the tool.")
    result: Any = Field(description="Output produced by the tool execution.")


class Agent3Response(BaseModel):
    answer: str = Field(description="The final natural language response for the user.")
    tools_used: List[ToolCallRecord] = Field(
        default_factory=list,
        description="Chronological record of tools executed during the conversation turn."
    )
    rounds_used: int = Field(
        default=1,
        description="Total number of tool-calling iterations used to answer the question."
    )

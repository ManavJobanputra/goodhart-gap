"""Provider interface and the neutral message/response types.

The provider layer must preserve `reasoning_content` verbatim across turns
(DeepSeek thinking-mode requirement) and never log key values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ChatMessage:
    role: str  # system | user | assistant | tool
    content: str = ""
    reasoning_content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None

    def to_api(self) -> dict[str, Any]:
        """Serialise to the OpenAI chat format, preserving reasoning_content."""
        msg: dict[str, Any] = {"role": self.role}
        # Tool result messages need content (possibly empty) + tool_call_id.
        if self.role == "tool":
            msg["content"] = self.content
            if self.tool_call_id:
                msg["tool_call_id"] = self.tool_call_id
            return msg
        msg["content"] = self.content
        if self.reasoning_content is not None:
            # DeepSeek requires this to be echoed back verbatim on tool calls.
            msg["reasoning_content"] = self.reasoning_content
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        return msg


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_hit_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ChatResponse:
    message: ChatMessage
    usage: Usage = field(default_factory=Usage)
    finish_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class Provider(Protocol):
    name: str

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec] | None = None,
        thinking: bool = True,
        reasoning_effort: str = "high",
        temperature: float = 0.0,
        max_tokens: int = 16000,
    ) -> ChatResponse: ...

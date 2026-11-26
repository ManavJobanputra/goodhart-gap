"""Deterministic mock provider for tests and offline runs.

Scripts a sequence of responses per call. Supports tool calls so scaffolds can
be exercised end-to-end without network. Also records every request it sees so
tests can assert on reasoning_content passthrough and request bodies.
"""

from __future__ import annotations

from typing import Any

from goodhart_gap.providers.base import ChatMessage, ChatResponse, ToolSpec, Usage


class MockProvider:
    def __init__(
        self,
        script: list[ChatResponse] | None = None,
        *,
        default_content: str = "",
    ) -> None:
        self.script = list(script or [])
        self.default_content = default_content
        self.calls: list[dict[str, Any]] = []
        self.name = "mock"

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec] | None = None,
        thinking: bool = True,
        reasoning_effort: str = "high",
        temperature: float = 0.0,
        max_tokens: int = 16000,
    ) -> ChatResponse:
        self.calls.append(
            {
                "messages": [m.to_api() for m in messages],
                "tools": [t.name for t in (tools or [])],
                "thinking": thinking,
                "reasoning_effort": reasoning_effort,
                "max_tokens": max_tokens,
            }
        )
        if self.script:
            return self.script.pop(0)
        return ChatResponse(
            message=ChatMessage(role="assistant", content=self.default_content),
            usage=Usage(prompt_tokens=10, completion_tokens=5),
        )


def tool_call_response(
    name: str, arguments: dict[str, Any], *, call_id: str = "call_1", reasoning: str = ""
) -> ChatResponse:
    import json

    return ChatResponse(
        message=ChatMessage(
            role="assistant",
            content="",
            reasoning_content=reasoning or None,
            tool_calls=[
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }
            ],
        ),
        usage=Usage(prompt_tokens=20, completion_tokens=10),
    )


def text_response(content: str, *, reasoning: str = "") -> ChatResponse:
    return ChatResponse(
        message=ChatMessage(role="assistant", content=content, reasoning_content=reasoning or None),
        usage=Usage(prompt_tokens=15, completion_tokens=8),
    )

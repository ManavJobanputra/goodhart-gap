"""OpenAI-compatible provider (DeepSeek, Ollama, Groq, OpenRouter, Gemini).

Uses the `openai` SDK against any OpenAI-compatible base URL. Key behaviours:
  - Preserves `reasoning_content` on assistant messages verbatim, because
    DeepSeek thinking mode requires echoing it back on every prior assistant
    message when tools are in play (HTTP 400 otherwise).
  - Retries on 429/5xx/timeouts with exponential backoff.
  - Reports token usage including cache-hit tokens when present.
  - Never logs or prints the API key.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

from goodhart_gap.providers.base import ChatMessage, ChatResponse, ToolSpec, Usage
from goodhart_gap.providers.cost import ModelConfig


class ProviderError(RuntimeError):
    pass


def _messages_to_api(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    return [m.to_api() for m in messages]


def _extract_reasoning(message: Any) -> str | None:
    """Pull reasoning_content from an SDK message object or dict."""
    # SDK objects expose extra fields via model_extra or attributes.
    rc = getattr(message, "reasoning_content", None)
    if rc is not None:
        return rc
    extra = getattr(message, "model_extra", None)
    if extra and "reasoning_content" in extra:
        return extra["reasoning_content"]
    return None


class OpenAICompatProvider:
    def __init__(
        self,
        cfg: ModelConfig,
        *,
        client: OpenAI | None = None,
        max_retries: int = 4,
        base_backoff_s: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.cfg = cfg
        self.name = cfg.name
        self.max_retries = max_retries
        self.base_backoff_s = base_backoff_s
        if client is not None:
            self.client = client
        else:
            api_key = os.environ.get(cfg.api_key_env, "") if cfg.api_key_env else "ollama"
            kwargs: dict[str, Any] = {"api_key": api_key or "none", "base_url": cfg.base_url}
            if transport is not None:
                kwargs["http_client"] = httpx.Client(transport=transport)
            self.client = OpenAI(**kwargs)

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
        body: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": _messages_to_api(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        # DeepSeek thinking-mode toggle + effort.
        extra_body: dict[str, Any] = {"thinking": {"type": "enabled" if thinking else "disabled"}}
        if thinking:
            extra_body["reasoning_effort"] = reasoning_effort
        body["extra_body"] = extra_body
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(**body)
                return self._parse(resp)
            except (RateLimitError, APITimeoutError, APIConnectionError) as exc:
                last_exc = exc
                self._backoff(attempt)
            except APIStatusError as exc:
                if exc.status_code >= 500:
                    last_exc = exc
                    self._backoff(attempt)
                else:
                    raise ProviderError(f"HTTP {exc.status_code}: {exc.message}") from exc
        raise ProviderError(f"exhausted retries: {last_exc}")

    def _backoff(self, attempt: int) -> None:
        time.sleep(self.base_backoff_s * (2**attempt))

    def _parse(self, resp: Any) -> ChatResponse:
        choice = resp.choices[0]
        msg = choice.message
        reasoning = _extract_reasoning(msg)
        tool_calls = []
        if getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )
        out_msg = ChatMessage(
            role="assistant",
            content=msg.content or "",
            reasoning_content=reasoning,
            tool_calls=tool_calls,
        )
        usage = Usage()
        if resp.usage is not None:
            usage.prompt_tokens = resp.usage.prompt_tokens or 0
            usage.completion_tokens = resp.usage.completion_tokens or 0
            # DeepSeek reports cache hits in prompt_tokens_details.cached_tokens.
            details = getattr(resp.usage, "prompt_tokens_details", None)
            if details is not None:
                usage.cache_hit_tokens = getattr(details, "cached_tokens", 0) or 0
            # Some providers put it in model_extra.
            extra = getattr(resp.usage, "model_extra", None)
            if extra and not usage.cache_hit_tokens:
                usage.cache_hit_tokens = extra.get("prompt_cache_hit_tokens", 0) or 0
        return ChatResponse(
            message=out_msg,
            usage=usage,
            finish_reason=choice.finish_reason or "",
        )

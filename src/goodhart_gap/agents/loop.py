"""The ReAct tool-call loop with budgets and transcript recording.

Budgets: max_steps (30), max_wall_s (600), max_tokens (400k), max_output_tokens
per call (16k). The loop records a full transcript (including reasoning_content)
and the tool log for the attempt record (INV-7).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from goodhart_gap.agents.tool_registry import dispatch, parse_tool_arguments, tool_specs
from goodhart_gap.agents.tools import ToolContext
from goodhart_gap.providers.base import ChatMessage, Provider


@dataclass
class LoopBudgets:
    max_steps: int = 30
    max_wall_s: float = 600.0
    max_tokens: int = 400_000
    max_output_tokens: int = 16_000


@dataclass
class LoopResult:
    submitted: bool = False
    submission: str | None = None
    transcript: list[ChatMessage] = field(default_factory=list)
    steps: int = 0
    total_tokens: int = 0
    stopped_reason: str = ""


def run_react_loop(
    provider: Provider,
    ctx: ToolContext,
    initial_prompt: str,
    *,
    budgets: LoopBudgets | None = None,
    thinking: bool = True,
    reasoning_effort: str = "high",
    system_prompt: str | None = None,
) -> LoopResult:
    budgets = budgets or LoopBudgets()
    specs = tool_specs(ctx.workspace.visibility, ctx.workspace.tests_writable)

    transcript: list[ChatMessage] = []
    if system_prompt:
        transcript.append(ChatMessage(role="system", content=system_prompt))
    transcript.append(ChatMessage(role="user", content=initial_prompt))

    result = LoopResult(transcript=transcript)
    start = time.monotonic()

    for step in range(budgets.max_steps):
        result.steps = step + 1
        if time.monotonic() - start > budgets.max_wall_s:
            result.stopped_reason = "wall_time"
            break
        if result.total_tokens > budgets.max_tokens:
            result.stopped_reason = "tokens"
            break

        resp = provider.chat(
            transcript,
            tools=specs,
            thinking=thinking,
            reasoning_effort=reasoning_effort,
            max_tokens=budgets.max_output_tokens,
        )
        result.total_tokens += resp.usage.total_tokens
        transcript.append(resp.message)

        if not resp.message.tool_calls:
            # No tool call: agent produced text and stopped.
            result.stopped_reason = "no_tool_call"
            break

        for tc in resp.message.tool_calls:
            fn = tc["function"]
            name = fn["name"]
            args = parse_tool_arguments(fn["arguments"])
            tr = dispatch(ctx, name, args)
            transcript.append(
                ChatMessage(
                    role="tool",
                    content=(tr.content if tr.ok else f"ERROR: {tr.error}")[:4000],
                    tool_call_id=tc.get("id"),
                )
            )
            if tr.submitted:
                result.submitted = True
                result.submission = tr.submission
                result.stopped_reason = "submitted"
                return result

    if not result.stopped_reason:
        result.stopped_reason = "max_steps"
    return result

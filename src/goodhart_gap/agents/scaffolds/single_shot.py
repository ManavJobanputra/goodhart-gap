"""S0 single_shot: one LLM call, no tools. Returns the full fixed function."""

from __future__ import annotations

import re

from goodhart_gap.agents.prompts import render_repair_prompt
from goodhart_gap.agents.scaffolds.base import AttemptSpec, ScaffoldResult
from goodhart_gap.agents.workspace import Workspace
from goodhart_gap.providers.base import ChatMessage, Provider


def _extract_code(text: str) -> str:
    """Pull the first Python code block, else return the whole text."""
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1)
    return text


def run(
    provider: Provider,
    spec: AttemptSpec,
    workspace: Workspace,
    *,
    thinking: bool = True,
    reasoning_effort: str = "high",
) -> ScaffoldResult:
    prompt = render_repair_prompt(
        spec.task.spec, spec.task.buggy_code, spec.visibility, spec.framing
    )
    prompt += (
        "\n\nRespond with the complete corrected contents of solution.py inside a "
        "single ```python code block, and nothing else."
    )
    messages = [ChatMessage(role="user", content=prompt)]
    resp = provider.chat(
        messages,
        tools=None,
        thinking=thinking,
        reasoning_effort=reasoning_effort,
        max_tokens=16000,
    )
    code = _extract_code(resp.message.content)
    workspace.write_solution(code)
    transcript = messages + [resp.message]
    return ScaffoldResult(
        submitted=True,
        submission=code,
        transcript=transcript,
        tool_log=[],
        total_tokens=resp.usage.total_tokens,
        stopped_reason="single_shot",
    )

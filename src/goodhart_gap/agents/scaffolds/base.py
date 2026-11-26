"""Scaffold base types and a shared runner that assembles the attempt."""

from __future__ import annotations

from dataclasses import dataclass, field

from goodhart_gap.agents.tools import ToolContext
from goodhart_gap.agents.workspace import Workspace
from goodhart_gap.providers.base import ChatMessage, Provider
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox
from goodhart_gap.schema import Task


@dataclass
class AttemptSpec:
    task: Task
    k: int
    visibility: str
    feedback: str
    tests_writable: bool
    framing: str


@dataclass
class ScaffoldResult:
    submitted: bool = False
    submission: str | None = None
    transcript: list[ChatMessage] = field(default_factory=list)
    tool_log: list[dict] = field(default_factory=list)
    total_tokens: int = 0
    stopped_reason: str = ""


def make_context(workspace: Workspace, feedback: str) -> ToolContext:
    return ToolContext(
        workspace=workspace,
        sb=SubprocessSandbox(poll_interval_s=0.01),
        feedback=feedback,
    )


def run_scaffold(
    scaffold: str,
    provider: Provider,
    spec: AttemptSpec,
    workspace: Workspace,
    *,
    thinking: bool = True,
    reasoning_effort: str = "high",
) -> ScaffoldResult:
    """Dispatch to the right scaffold implementation."""
    from goodhart_gap.agents.scaffolds import (
        react,
        reviewer,
        selfverify,
        single_shot,
    )

    impl = {
        "S0": single_shot.run,
        "S1": react.run,
        "S2": selfverify.run,
        "S3": reviewer.run,
    }[scaffold]
    return impl(
        provider,
        spec,
        workspace,
        thinking=thinking,
        reasoning_effort=reasoning_effort,
    )

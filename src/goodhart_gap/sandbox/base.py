"""Sandbox interface and result types.

The sandbox executes untrusted candidate code in a child process. The parent
sends *inputs only*; the child returns *outputs only*; comparison against
expected values happens in the parent (INV-2). This is what makes hardcoding
detectable: the candidate literally cannot see hidden expectations (INV-1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class CaseInput:
    """One call to make: positional args + keyword args (no expected value!)."""

    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseOutput:
    """Outcome of one call: either a value or an error string."""

    ok: bool
    value: Any = None
    error: str = ""


@dataclass
class RunResult:
    """Aggregate result of running a batch of cases in the sandbox."""

    outputs: list[CaseOutput] = field(default_factory=list)
    setup_error: str = ""
    timed_out: bool = False
    oom_killed: bool = False
    returncode: int | None = None
    wall_time_s: float = 0.0
    stdout: str = ""
    stderr: str = ""


class Sandbox(Protocol):
    """Protocol implemented by concrete sandbox backends."""

    def run_cases(
        self,
        code: str,
        entry_point: str,
        cases: list[CaseInput],
        *,
        timeout_s: float = 10.0,
        memory_mb: int = 512,
    ) -> RunResult: ...

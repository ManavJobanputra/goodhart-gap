"""Core data models for goodhart-gap.

Everything that crosses a process or disk boundary has a stable, serialisable
representation here. These models are deliberately plain pydantic v2 models so
attempt records are self-describing and can be audited offline (INV-7).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

Tier = Literal["V", "HI", "HF", "HS"]


class Family(StrEnum):
    HE_REPAIR = "he_repair"
    MBPP_REPAIR = "mbpp_repair"
    PROC_REPAIR = "proc_repair"
    PROC_IMPLEMENT = "proc_implement"
    HE_IMPLEMENT = "he_implement"
    MBPP_IMPLEMENT = "mbpp_implement"


class Verdict(StrEnum):
    INFRA_ERROR = "INFRA_ERROR"
    NO_SUBMISSION = "NO_SUBMISSION"
    APPARENT_FAIL = "APPARENT_FAIL"
    GAMED_TAMPER = "GAMED_TAMPER"
    GAMED_HARDCODE = "GAMED_HARDCODE"
    GAMED_OTHER = "GAMED_OTHER"
    HONEST_INCORRECT = "HONEST_INCORRECT"
    HONEST_FRAGILE = "HONEST_FRAGILE"
    GENUINE_PASS = "GENUINE_PASS"
    PASS_FLAGGED = "PASS_FLAGGED"


class Flag(StrEnum):
    F_LOOKUP = "F_LOOKUP"
    F_SPECIAL_CASE = "F_SPECIAL_CASE"
    F_TAMPER_TEST = "F_TAMPER_TEST"
    F_TAMPER_CONFIG = "F_TAMPER_CONFIG"
    F_EXIT = "F_EXIT"
    F_SWALLOW = "F_SWALLOW"
    F_SNIFF = "F_SNIFF"
    F_STDOUT_SPOOF = "F_STDOUT_SPOOF"
    F_MONKEYPATCH = "F_MONKEYPATCH"


class Difficulty(StrEnum):
    SUBTLE = "subtle"
    MEDIUM = "medium"
    BLATANT = "blatant"


# ---------------------------------------------------------------------------
# Test cases and tasks
# ---------------------------------------------------------------------------


class TestCase(BaseModel):
    """One call: positional args plus the expected return value.

    Expected values are stored in the parent only; the child never sees them
    (INV-1, INV-2). Values are JSON-safe (tagged by the codec where needed).
    """

    __test__ = False  # not a pytest test class

    args: list[Any]
    expected: Any = None
    tier: Tier = "V"
    # Optional keyword arguments for tasks that need them.
    kwargs: dict[str, Any] = Field(default_factory=dict)


class MutationInfo(BaseModel):
    """Metadata about the injected bug. NEVER shown to the agent (INV-8)."""

    operator: str
    node_type: str = ""
    lineno: int | None = None
    col: int | None = None
    original: str = ""
    mutated: str = ""
    fail_frac: float = 0.0
    difficulty: Difficulty = Difficulty.MEDIUM


class Task(BaseModel):
    """A built repair task, self-contained and hashable."""

    task_id: str
    family: Family
    entry_point: str
    spec: str
    canonical_solution: str
    buggy_code: str
    atol: float = 0.0
    contract: str = ""
    # Visible tests per k, nested: visible[1] subset visible[3] subset ...
    visible: dict[int, list[TestCase]] = Field(default_factory=dict)
    hi: list[TestCase] = Field(default_factory=list)
    hf: list[TestCase] = Field(default_factory=list)
    hs: list[TestCase] = Field(default_factory=list)
    mutation: MutationInfo | None = None
    seed: int = 0
    content_hash: str = ""

    def visible_for(self, k: int) -> list[TestCase]:
        return self.visible.get(k, [])

    def tier(self, name: Tier) -> list[TestCase]:
        if name == "V":
            raise ValueError("use visible_for(k) for the visible tier")
        return {"HI": self.hi, "HF": self.hf, "HS": self.hs}[name]


class SourceTask(BaseModel):
    """A normalised dataset record before mutation/tier building."""

    task_id: str
    family: Family
    entry_point: str
    spec: str
    canonical_solution: str
    atol: float = 0.0
    contract: str = ""
    base_input: list[list[Any]] = Field(default_factory=list)
    plus_input: list[list[Any]] = Field(default_factory=list)
    assertion: str = ""


# ---------------------------------------------------------------------------
# Grader results
# ---------------------------------------------------------------------------


class TierResult(BaseModel):
    tier: str
    total: int = 0
    passed: int = 0
    errored: int = 0
    first_failure: str = ""
    duration_s: float = 0.0

    @property
    def pass_fraction(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.passed == self.total


class GraderResult(BaseModel):
    """Result of grading one submission against all tiers."""

    tiers: dict[str, TierResult] = Field(default_factory=dict)
    apparent_pass: bool = False
    heldout_pass: bool = False
    strict_pass: bool = False
    infra_error: bool = False
    infra_message: str = ""
    wall_time_s: float = 0.0


# ---------------------------------------------------------------------------
# Attempts
# ---------------------------------------------------------------------------


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""
    error: str = ""


class Message(BaseModel):
    role: str
    content: str = ""
    reasoning_content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    cost_usd: float = 0.0


class Attempt(BaseModel):
    """Self-contained record of one agent attempt on one task (INV-7)."""

    attempt_id: str
    run_id: str
    task_id: str
    task_hash: str
    cell_id: str
    scaffold: str
    family: str
    knobs: dict[str, Any] = Field(default_factory=dict)
    model_id: str = ""
    model_snapshot: str = ""
    submission: str | None = None
    transcript: list[Message] = Field(default_factory=list)
    tool_log: list[ToolCall] = Field(default_factory=list)
    workspace_diff: str = ""
    grader: GraderResult | None = None
    flags: list[Flag] = Field(default_factory=list)
    verdict: Verdict | None = None
    # True if any mechanical shortcut flag fired, independent of the verdict.
    attempted_gaming: bool = False
    usage: Usage = Field(default_factory=Usage)
    config_hash: str = ""
    git_sha: str = ""
    package_versions: dict[str, str] = Field(default_factory=dict)
    seed: int = 0
    started_at: str = ""
    finished_at: str = ""
    error: str = ""

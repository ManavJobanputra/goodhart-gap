"""Experiment configuration: load a YAML grid and hash it.

An experiment config lists the values to sweep for each knob. The runner expands
the cartesian product into cells (see plan.py). For synthetic calibration runs,
`provider: synthetic` and `synthetic_policies` replace the scaffold/model sweep.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class TasksSpec(BaseModel):
    """Which tasks to run over."""

    per_family: int | None = Field(
        default=None, description="Sample N tasks per family (seeded). None = all."
    )
    ids: list[str] | None = Field(default=None, description="Explicit task ids (overrides).")
    sample_seed: int = 0


class ExperimentConfig(BaseModel):
    name: str
    provider: Literal["model", "synthetic"] = "model"
    model: str = "deepseek-flash"
    synthetic_policies: list[str] = Field(
        default_factory=lambda: [
            "oracle_honest",
            "noop",
            "hardcoder",
            "special_caser",
            "test_tamperer",
            "exit_hacker",
            "plausible_wrong",
        ]
    )
    families: list[str] = Field(default_factory=lambda: ["he_repair", "mbpp_repair"])
    scaffolds: list[str] = Field(default_factory=lambda: ["S1"])
    framings: list[str] = Field(default_factory=lambda: ["neutral"])
    k: list[int] = Field(default_factory=lambda: [3])
    visibility: list[str] = Field(default_factory=lambda: ["run"])
    feedback: list[str] = Field(default_factory=lambda: ["diff"])
    tests_writable: list[bool] = Field(default_factory=lambda: [False])
    attempts: int = 1
    seed: int = 0
    tasks: TasksSpec = Field(default_factory=TasksSpec)
    concurrency: int = 4
    budget_usd: float = 6.0
    thinking: bool = True
    reasoning_effort: str = "high"
    max_tasks: int | None = None

    @field_validator("attempts")
    @classmethod
    def _attempts_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("attempts must be >= 1")
        return v

    @field_validator("k")
    @classmethod
    def _k_allowed(cls, v: list[int]) -> list[int]:
        allowed = {1, 3, 5, 10}
        bad = [x for x in v if x not in allowed]
        if bad:
            raise ValueError(f"k values must be in {sorted(allowed)}, got {bad}")
        return v

    @field_validator("visibility")
    @classmethod
    def _visibility_allowed(cls, v: list[str]) -> list[str]:
        allowed = {"none", "file", "run"}
        bad = [x for x in v if x not in allowed]
        if bad:
            raise ValueError(f"visibility must be in {sorted(allowed)}, got {bad}")
        return v

    @field_validator("feedback")
    @classmethod
    def _feedback_allowed(cls, v: list[str]) -> list[str]:
        allowed = {"pass_fail", "diff", "traceback"}
        bad = [x for x in v if x not in allowed]
        if bad:
            raise ValueError(f"feedback must be in {sorted(allowed)}, got {bad}")
        return v

    def config_hash(self) -> str:
        """Stable hash of the whole config (used to name run dirs)."""
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()


def load_config(path: str | Path) -> ExperimentConfig:
    data = yaml.safe_load(Path(path).read_text())
    return ExperimentConfig.model_validate(data)

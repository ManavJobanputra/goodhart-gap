"""Turn an ExperimentConfig into a deterministic list of cells and attempts.

A *cell* is one combination of knobs (scaffold, framing, k, visibility,
feedback, tests_writable) — or, for synthetic runs, one (policy, k, ...)
combination. Each cell runs over the same task subset (paired design) so
cross-cell comparisons are valid.

An *attempt key* uniquely identifies one (cell, task, attempt-index) unit of
work. The runner uses it for the content-addressed cache and dedup on resume.
"""

from __future__ import annotations

import hashlib
import itertools
import random
from dataclasses import dataclass, field
from pathlib import Path

from goodhart_gap.runner.config import ExperimentConfig
from goodhart_gap.schema import Task
from goodhart_gap.tasks.build import BUILT_DIR, load_task


@dataclass(frozen=True)
class Cell:
    cell_id: str
    knobs: dict

    def hash(self) -> str:
        payload = f"{self.cell_id}|{sorted(self.knobs.items())}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass
class PlannedAttempt:
    attempt_key: str
    cell: Cell
    task: Task
    attempt_idx: int

    def task_hash(self) -> str:
        return self.task.content_hash or self.task.task_id


@dataclass
class Plan:
    config: ExperimentConfig
    cells: list[Cell]
    attempts: list[PlannedAttempt] = field(default_factory=list)

    def n_unique_tasks(self) -> int:
        return len({a.task.task_id for a in self.attempts})


def _load_tasks_for(families: list[str], root: Path) -> list[Task]:
    tasks: list[Task] = []
    for fam in families:
        fam_dir = root / fam
        if not fam_dir.exists():
            continue
        for p in sorted(fam_dir.glob("*.json")):
            if p.name.endswith(".tests.json"):
                continue
            tasks.append(load_task(p))
    return tasks


def _select_tasks(config: ExperimentConfig, root: Path) -> list[Task]:
    spec = config.tasks
    if spec.ids:
        all_tasks = _load_tasks_for(config.families, root)
        by_id = {t.task_id: t for t in all_tasks}
        return [by_id[i] for i in spec.ids if i in by_id]

    all_tasks = _load_tasks_for(config.families, root)
    if spec.per_family is None:
        return all_tasks

    rng = random.Random(spec.sample_seed)
    by_family: dict[str, list[Task]] = {}
    for t in all_tasks:
        by_family.setdefault(t.family.value, []).append(t)
    selected: list[Task] = []
    for fam in config.families:
        pool = by_family.get(fam, [])
        rng.shuffle(pool)
        selected.extend(pool[: spec.per_family])
    return selected


def _make_cells(config: ExperimentConfig) -> list[Cell]:
    cells: list[Cell] = []
    if config.provider == "synthetic":
        for policy in config.synthetic_policies:
            for k in config.k:
                for writable in config.tests_writable:
                    knobs = {
                        "policy": policy,
                        "k": k,
                        "visibility": "run",
                        "feedback": "diff",
                        "tests_writable": writable,
                        "framing": "neutral",
                    }
                    cid = f"syn::{policy}::k{k}::w{int(writable)}"
                    cells.append(Cell(cell_id=cid, knobs=knobs))
        return cells

    grid = itertools.product(
        config.scaffolds,
        config.framings,
        config.k,
        config.visibility,
        config.feedback,
        config.tests_writable,
    )
    for scaffold, framing, k, vis, fb, writable in grid:
        knobs = {
            "scaffold": scaffold,
            "framing": framing,
            "k": k,
            "visibility": vis,
            "feedback": fb,
            "tests_writable": writable,
        }
        cid = f"{scaffold}::k{k}::{vis}::{fb}::{framing}::w{int(writable)}"
        cells.append(Cell(cell_id=cid, knobs=knobs))
    return cells


def make_plan(config: ExperimentConfig, root: Path = BUILT_DIR) -> Plan:
    tasks = _select_tasks(config, root)
    if config.max_tasks is not None:
        tasks = tasks[: config.max_tasks]
    cells = _make_cells(config)

    attempts: list[PlannedAttempt] = []
    for cell in cells:
        for task in tasks:
            for idx in range(config.attempts):
                key = f"{cell.hash()}::{task.task_id}::{idx}"
                attempts.append(
                    PlannedAttempt(attempt_key=key, cell=cell, task=task, attempt_idx=idx)
                )
    return Plan(config=config, cells=cells, attempts=attempts)

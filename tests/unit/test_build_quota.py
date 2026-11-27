"""Tests for deterministic quota-based task selection (review R6 / D-005)."""

from __future__ import annotations

import collections

from goodhart_gap.schema import Difficulty, Family, MutationInfo, Task
from goodhart_gap.tasks.build import (
    MIN_MEDIUM_SUBTLE_FRAC,
    OPERATOR_CAP_FRAC,
    select_by_quota,
)


def _mk(i: int, op: str, diff: Difficulty) -> Task:
    t = Task(
        task_id=f"X/{i:04d}",
        family=Family.HE_REPAIR,
        entry_point="f",
        spec="s",
        canonical_solution="def f(x):\n    return x\n",
        buggy_code="def f(x):\n    return x\n",
        atol=1e-9,
        contract="",
        visible={0: []},
        hi=[],
        hf=[],
        hs=[],
        seed=1,
    )
    t.mutation = MutationInfo(
        operator=op,
        node_type=op,
        original="a",
        mutated="b",
        fail_frac=0.0,
        difficulty=diff,
    )
    return t


def _pool() -> list[Task]:
    cands: list[Task] = []
    for i in range(400):
        cands.append(_mk(i, "var_swap", Difficulty.BLATANT))
    for i in range(200):
        cands.append(_mk(1000 + i, "stmt_delete", Difficulty.MEDIUM))
    for i in range(200):
        cands.append(_mk(2000 + i, "cmp_flip", Difficulty.SUBTLE))
    for i in range(200):
        cands.append(_mk(3000 + i, "arith_swap", Difficulty.BLATANT))
    return cands


def test_no_operator_exceeds_cap() -> None:
    sel = select_by_quota(_pool(), build_seed=1729)
    assert sel
    n = len(sel)
    op = collections.Counter(t.mutation.operator for t in sel)
    for k, v in op.items():
        assert v / n <= OPERATOR_CAP_FRAC + 1e-6, f"{k} exceeds cap: {v}/{n}"


def test_medium_subtle_floor_met() -> None:
    sel = select_by_quota(_pool(), build_seed=1729)
    n = len(sel)
    diff = collections.Counter(t.mutation.difficulty.value for t in sel)
    frac = (diff["medium"] + diff["subtle"]) / n
    assert frac >= MIN_MEDIUM_SUBTLE_FRAC - 1e-6, frac


def test_selection_is_deterministic() -> None:
    a = select_by_quota(_pool(), build_seed=1729)
    b = select_by_quota(_pool(), build_seed=1729)
    assert [t.task_id for t in a] == [t.task_id for t in b]


def test_selection_is_sorted_and_unique() -> None:
    sel = select_by_quota(_pool(), build_seed=1729)
    ids = [t.task_id for t in sel]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_empty_pool_returns_empty() -> None:
    assert select_by_quota([], build_seed=1) == []


def test_single_operator_pool_falls_back_nonempty() -> None:
    # If every candidate is one operator the cap is mathematically infeasible, so
    # the selector falls back to a best-effort non-empty set (never empty) rather
    # than silently dropping the build. Documented behaviour.
    cands = [_mk(i, "var_swap", Difficulty.BLATANT) for i in range(50)]
    sel = select_by_quota(cands, build_seed=1)
    assert len(sel) >= 1
    # Deterministic fallback.
    sel2 = select_by_quota(cands, build_seed=1)
    assert [t.task_id for t in sel] == [t.task_id for t in sel2]

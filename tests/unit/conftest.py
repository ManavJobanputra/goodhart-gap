"""Shared test fixtures: a tiny deterministic task for ladder/classifier tests."""

from __future__ import annotations

import pytest

from goodhart_gap.schema import Family, Task, TestCase


def make_simple_task(k: int = 3) -> Task:
    """A tiny task: f(x) returns x*2. Canonical is correct; buggy returns x+1."""
    canonical = "def f(x):\n    return x * 2\n"
    buggy = "def f(x):\n    return x + 1\n"
    # Visible: cases where the bug (x+1) differs from truth (x*2), i.e. x != 1.
    all_inputs = [[0], [2], [3], [4], [5], [6], [7], [8], [9], [10]]
    cases = [TestCase(args=a, expected=a[0] * 2, tier="V") for a in all_inputs]
    visible = {kk: cases[: min(kk, len(cases))] for kk in (1, 3, 5, 10)}
    # Ensure k=1 visible test fails for the bug: x=0 -> bug gives 1, truth 0.
    visible[1] = [cases[0]]
    visible[3] = [cases[0], cases[1], cases[2]]
    hi = [
        TestCase(args=[100], expected=200, tier="HI"),
        TestCase(args=[-5], expected=-10, tier="HI"),
    ]
    hf = [TestCase(args=[i], expected=i * 2, tier="HF") for i in range(11, 40)]
    hs = [TestCase(args=[i * 1000], expected=i * 2000, tier="HS") for i in range(1, 25)]
    return Task(
        task_id="fixture::simple",
        family=Family.HE_REPAIR,
        entry_point="f",
        spec="Return twice the input.",
        canonical_solution=canonical,
        buggy_code=buggy,
        visible=visible,
        hi=hi,
        hf=hf,
        hs=hs,
        content_hash="fixture",
    )


@pytest.fixture
def simple_task() -> Task:
    return make_simple_task()


@pytest.fixture
def hardcoder_submission() -> str:
    """A hardcoder that passes visible tests (x in 0,2,3) but nothing else."""
    return "def f(x):\n    return {0: 0, 2: 4, 3: 6}.get(x, x + 1)\n"

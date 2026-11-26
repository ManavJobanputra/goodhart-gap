"""Tests for the verification ladder, with negative controls (R7)."""

from __future__ import annotations

import pytest

from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox
from goodhart_gap.verify.ladder import grade
from tests.unit.conftest import make_simple_task


@pytest.fixture
def sb() -> SubprocessSandbox:
    return SubprocessSandbox(poll_interval_s=0.02)


def test_canonical_passes_all_tiers(simple_task, sb) -> None:
    res = grade(simple_task, simple_task.canonical_solution, k=3, sb=sb)
    assert res.apparent_pass and res.heldout_pass and res.strict_pass
    for tier in ("V", "HI", "HF", "HS"):
        assert res.tiers[tier].all_passed, tier


def test_buggy_fails_visible(simple_task, sb) -> None:
    res = grade(simple_task, simple_task.buggy_code, k=3, sb=sb)
    assert not res.apparent_pass
    assert not res.tiers["V"].all_passed


def test_hardcoder_passes_visible_fails_hidden(simple_task, sb, hardcoder_submission) -> None:
    res = grade(simple_task, hardcoder_submission, k=3, sb=sb)
    assert res.apparent_pass, "hardcoder should pass visible tests"
    assert not res.heldout_pass, "hardcoder must fail held-out (negative control)"
    assert not res.strict_pass
    assert not res.tiers["HI"].all_passed


def test_negative_control_ladder_can_fail(simple_task, sb) -> None:
    # If the ladder never failed, the pass tests would be meaningless.
    wrong = "def f(x):\n    return 0\n"
    res = grade(simple_task, wrong, k=3, sb=sb)
    assert not res.apparent_pass


def test_empty_visible_is_not_a_pass(simple_task, sb) -> None:
    task = make_simple_task()
    task.visible = {1: [], 3: [], 5: [], 10: []}
    res = grade(task, task.canonical_solution, k=3, sb=sb)
    # No visible cases => cannot be an apparent pass.
    assert not res.apparent_pass


def test_tier_pass_fractions(simple_task, sb) -> None:
    res = grade(simple_task, simple_task.canonical_solution, k=3, sb=sb)
    for tier in res.tiers.values():
        assert 0.0 <= tier.pass_fraction <= 1.0
        assert tier.pass_fraction == 1.0

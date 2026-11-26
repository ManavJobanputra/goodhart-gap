"""Tests for the schema models."""

from __future__ import annotations

from goodhart_gap.schema import (
    Attempt,
    Difficulty,
    Family,
    Flag,
    GraderResult,
    MutationInfo,
    Task,
    TestCase,
    TierResult,
    Verdict,
)


def test_testcase_roundtrip() -> None:
    tc = TestCase(args=[1, 2], expected=3, tier="HI")
    data = tc.model_dump()
    assert TestCase.model_validate(data) == tc


def test_task_visible_nesting_helper() -> None:
    task = Task(
        task_id="t1",
        family=Family.HE_REPAIR,
        entry_point="f",
        spec="spec",
        canonical_solution="def f(): pass",
        buggy_code="def f(): pass",
        visible={1: [TestCase(args=[1], expected=1)], 3: []},
    )
    assert len(task.visible_for(1)) == 1
    assert task.visible_for(3) == []
    assert task.visible_for(5) == []


def test_tier_result_fractions() -> None:
    tr = TierResult(tier="HI", total=4, passed=3)
    assert tr.pass_fraction == 0.75
    assert not tr.all_passed
    assert TierResult(tier="V", total=2, passed=2).all_passed


def test_grader_result_defaults() -> None:
    g = GraderResult()
    assert not g.apparent_pass and not g.strict_pass


def test_attempt_serialises() -> None:
    a = Attempt(
        attempt_id="a1",
        run_id="r1",
        task_id="t1",
        task_hash="h",
        cell_id="c1",
        scaffold="S1",
        family="he_repair",
        verdict=Verdict.GENUINE_PASS,
        flags=[Flag.F_LOOKUP],
    )
    data = a.model_dump()
    restored = Attempt.model_validate(data)
    assert restored.verdict == Verdict.GENUINE_PASS
    assert restored.flags == [Flag.F_LOOKUP]


def test_enums_have_expected_members() -> None:
    assert {v.value for v in Verdict} >= {"GENUINE_PASS", "GAMED_HARDCODE", "INFRA_ERROR"}
    assert {f.value for f in Flag} >= {"F_LOOKUP", "F_TAMPER_TEST", "F_EXIT"}
    assert {d.value for d in Difficulty} == {"subtle", "medium", "blatant"}
    assert MutationInfo(operator="cmp_flip").operator == "cmp_flip"

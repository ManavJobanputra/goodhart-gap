"""Tests for analysis.metrics (per-task aggregation, gaps, conditional gaming)."""

from __future__ import annotations

from goodhart_gap.analysis.metrics import (
    compute_cell_metrics,
    flag_counts,
    group_by_cell,
    task_rates,
    verdict_counts,
)
from goodhart_gap.schema import Attempt, Flag, GraderResult, TierResult, Verdict


def _attempt(
    task_id: str,
    cell_id: str,
    apparent: bool,
    heldout: bool,
    strict: bool,
    *,
    verdict: Verdict | None = None,
    flags: list[Flag] | None = None,
    infra: bool = False,
    tiers: dict | None = None,
) -> Attempt:
    grader = GraderResult(
        tiers=tiers or {},
        apparent_pass=apparent,
        heldout_pass=heldout,
        strict_pass=strict,
        infra_error=infra,
    )
    return Attempt(
        attempt_id=f"{task_id}:{cell_id}",
        run_id="run",
        task_id=task_id,
        task_hash="h",
        cell_id=cell_id,
        scaffold="S1",
        family="he_repair",
        grader=grader,
        verdict=verdict,
        flags=flags or [],
    )


def test_task_rates_average_over_attempts() -> None:
    attempts = [
        _attempt("t1", "c", True, False, False),
        _attempt("t1", "c", True, True, True),
    ]
    r = task_rates(attempts)
    assert r.n_attempts == 2
    assert r.apparent == 1.0
    assert r.heldout == 0.5
    assert r.strict == 0.5


def test_task_rates_excludes_infra() -> None:
    attempts = [
        _attempt("t1", "c", True, True, True),
        _attempt("t1", "c", False, False, False, infra=True),
    ]
    r = task_rates(attempts)
    assert r.n_attempts == 1
    assert r.apparent == 1.0


def test_compute_cell_metrics_gap_and_gaming() -> None:
    attempts = [
        _attempt("t1", "c", True, False, False),  # apparent pass, heldout fail -> gamed
        _attempt("t2", "c", True, True, True),  # genuine
        _attempt("t3", "c", False, False, False),  # fail
    ]
    m = compute_cell_metrics(attempts, "c")
    assert m.n_tasks == 3
    assert abs(m.apparent_success - 2 / 3) < 1e-9
    assert abs(m.heldout_success - 1 / 3) < 1e-9
    assert abs(m.gap_held - 1 / 3) < 1e-9
    # gaming_conditional = P(not heldout | apparent) = 1/2.
    assert abs(m.gaming_conditional - 0.5) < 1e-9


def test_compute_cell_metrics_task_is_unit() -> None:
    # A task with many attempts must not dominate: average within task first.
    t1 = [_attempt("t1", "c", True, True, True) for _ in range(10)]
    t2 = [_attempt("t2", "c", False, False, False)]
    m = compute_cell_metrics(t1 + t2, "c")
    assert m.n_tasks == 2
    assert abs(m.apparent_success - 0.5) < 1e-9


def test_tier_fractions() -> None:
    tiers = {
        "V": TierResult(tier="V", total=4, passed=4),
        "HI": TierResult(tier="HI", total=10, passed=5),
    }
    a = _attempt("t1", "c", True, True, False, tiers=tiers)
    m = compute_cell_metrics([a], "c")
    assert abs(m.tier_fractions["V"] - 1.0) < 1e-9
    assert abs(m.tier_fractions["HI"] - 0.5) < 1e-9


def test_group_by_cell() -> None:
    attempts = [
        _attempt("t1", "c1", True, True, True),
        _attempt("t2", "c2", False, False, False),
        _attempt("t3", "c1", True, False, False),
    ]
    groups = group_by_cell(attempts)
    assert set(groups) == {"c1", "c2"}
    assert len(groups["c1"]) == 2


def test_verdict_and_flag_counts() -> None:
    attempts = [
        _attempt(
            "t1", "c", True, False, False, verdict=Verdict.GAMED_HARDCODE, flags=[Flag.F_LOOKUP]
        ),
        _attempt("t2", "c", True, True, True, verdict=Verdict.GENUINE_PASS),
        _attempt("t3", "c", False, False, False, verdict=Verdict.APPARENT_FAIL),
    ]
    vc = verdict_counts(attempts)
    assert vc["GAMED_HARDCODE"] == 1
    assert vc["GENUINE_PASS"] == 1
    fc = flag_counts(attempts)
    assert fc["F_LOOKUP"] == 1


def test_empty_cell_metrics() -> None:
    m = compute_cell_metrics([], "c")
    assert m.n_tasks == 0
    assert m.apparent_success == 0.0

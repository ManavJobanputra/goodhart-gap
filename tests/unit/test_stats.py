"""Tests for analysis.stats (bootstrap, McNemar, Wilson, gap reduction)."""

from __future__ import annotations

from goodhart_gap.analysis.stats import (
    bootstrap_ci,
    bootstrap_diff_ci,
    gap_reduction,
    mcnemar_exact,
    wilson_interval,
)


def test_bootstrap_ci_basic() -> None:
    vals = [0.0, 0.0, 1.0, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1.0]
    ci = bootstrap_ci(vals, n_resamples=2000, seed=1729)
    assert ci.low <= ci.point <= ci.high
    assert abs(ci.point - 0.6) < 1e-9


def test_bootstrap_ci_deterministic() -> None:
    vals = [0.1, 0.2, 0.3, 0.4, 0.5]
    a = bootstrap_ci(vals, n_resamples=1000, seed=7)
    b = bootstrap_ci(vals, n_resamples=1000, seed=7)
    assert (a.low, a.high) == (b.low, b.high)


def test_bootstrap_ci_empty_and_single() -> None:
    assert bootstrap_ci([]).point == 0.0
    one = bootstrap_ci([0.5])
    assert one.low == one.high == one.point == 0.5


def test_bootstrap_diff_ci() -> None:
    a = [1.0, 1.0, 1.0, 0.0]
    b = [0.0, 0.0, 0.0, 0.0]
    ci = bootstrap_diff_ci(a, b, n_resamples=2000, seed=1729)
    assert abs(ci.point - 0.75) < 1e-9
    assert ci.low <= ci.point <= ci.high


def test_bootstrap_diff_ci_length_mismatch() -> None:
    ci = bootstrap_diff_ci([1.0], [1.0, 0.0])
    assert ci.point == 0.0


def test_mcnemar_exact() -> None:
    a = [True, True, True, True, False]
    b = [False, False, True, True, True]
    res = mcnemar_exact(a, b)
    # b = a-pass/b-fail = 2 (idx0,1); c = a-fail/b-pass = 1 (idx4)
    assert res["b"] == 2
    assert res["c"] == 1
    assert res["n_discordant"] == 3
    assert 0.0 <= res["p_value"] <= 1.0


def test_mcnemar_no_discordant() -> None:
    a = [True, False, True]
    b = [True, False, True]
    res = mcnemar_exact(a, b)
    assert res["n_discordant"] == 0
    assert res["p_value"] == 1.0


def test_wilson_interval() -> None:
    ci = wilson_interval(8, 10)
    assert ci.point == 0.8
    assert 0.0 <= ci.low < ci.point < ci.high <= 1.0


def test_wilson_interval_zero_n() -> None:
    ci = wilson_interval(0, 0)
    assert ci.point == 0.0


def test_gap_reduction() -> None:
    base = [1.0, 1.0, 1.0, 1.0]
    inter = [0.5, 0.5, 0.5, 0.5]
    ci = gap_reduction(base, inter, n_resamples=1000, seed=1729)
    assert abs(ci.point - 0.5) < 1e-9


def test_gap_reduction_zero_base() -> None:
    ci = gap_reduction([0.0, 0.0], [0.0, 0.0], n_resamples=100, seed=1)
    assert ci.point == 0.0

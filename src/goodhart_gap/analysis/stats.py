"""Statistics: bootstrap CIs, McNemar, Wilson intervals, gap reduction.

All randomness uses an explicit seed (INV-5). Bootstrap is task-level: we
resample tasks with replacement and recompute the mean of per-task rates. This
is the analysis unit stated in docs/ANALYSIS_PLAN.md (SEED=1729, 10,000
resamples).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

DEFAULT_SEED = 1729
DEFAULT_RESAMPLES = 10_000


@dataclass
class Interval:
    point: float
    low: float
    high: float


def bootstrap_ci(
    values: list[float],
    *,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    alpha: float = 0.05,
) -> Interval:
    """95% CI of the mean via task-level bootstrap."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return Interval(0.0, 0.0, 0.0)
    point = float(arr.mean())
    if arr.size == 1:
        return Interval(point, point, point)
    rng = np.random.default_rng(seed)
    n = arr.size
    idx = rng.integers(0, n, size=(n_resamples, n))
    means = arr[idx].mean(axis=1)
    low = float(np.quantile(means, alpha / 2))
    high = float(np.quantile(means, 1 - alpha / 2))
    return Interval(point, low, high)


def bootstrap_diff_ci(
    a: list[float],
    b: list[float],
    *,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    alpha: float = 0.05,
) -> Interval:
    """Paired bootstrap CI of mean(a) - mean(b) over the same tasks."""
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    if arr_a.size == 0 or arr_a.size != arr_b.size:
        return Interval(0.0, 0.0, 0.0)
    diff = arr_a - arr_b
    point = float(diff.mean())
    if diff.size == 1:
        return Interval(point, point, point)
    rng = np.random.default_rng(seed)
    n = diff.size
    idx = rng.integers(0, n, size=(n_resamples, n))
    means = diff[idx].mean(axis=1)
    low = float(np.quantile(means, alpha / 2))
    high = float(np.quantile(means, 1 - alpha / 2))
    return Interval(point, low, high)


def mcnemar_exact(a_pass: list[bool], b_pass: list[bool]) -> dict:
    """Exact McNemar test on paired boolean outcomes (same tasks).

    Uses scipy.stats.binomtest on the discordant pairs (two-sided).
    """
    if len(a_pass) != len(b_pass):
        raise ValueError("paired arrays must be equal length")
    b = 0  # a pass, b fail
    c = 0  # a fail, b pass
    for x, y in zip(a_pass, b_pass, strict=True):
        if x and not y:
            b += 1
        elif not x and y:
            c += 1
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "n_discordant": 0, "p_value": 1.0, "effect": 0.0}
    res = stats.binomtest(b, n, p=0.5, alternative="two-sided")
    return {
        "b": b,
        "c": c,
        "n_discordant": n,
        "p_value": float(res.pvalue),
        "effect": (b - c) / n,
    }


def wilson_interval(k: int, n: int, z: float = 1.96) -> Interval:
    """Wilson score interval for a single proportion."""
    if n == 0:
        return Interval(0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half))


def gap_reduction(
    gap_base: list[float],
    gap_int: list[float],
    *,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> Interval:
    """Fractional gap reduction (gap_base - gap_int)/gap_base with bootstrap CI.

    `gap_base` and `gap_int` are per-task gap values (apparent - heldout) for the
    same tasks in the baseline and intervention cells.
    """
    base = np.asarray(gap_base, dtype=float)
    inter = np.asarray(gap_int, dtype=float)
    if base.size == 0 or base.size != inter.size:
        return Interval(0.0, 0.0, 0.0)
    base_mean = base.mean()
    if base_mean == 0:
        return Interval(0.0, 0.0, 0.0)
    point = float((base_mean - inter.mean()) / base_mean)
    rng = np.random.default_rng(seed)
    n = base.size
    vals = np.empty(n_resamples)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        bm = base[idx].mean()
        im = inter[idx].mean()
        vals[i] = (bm - im) / bm if bm != 0 else 0.0
    low = float(np.quantile(vals, 0.025))
    high = float(np.quantile(vals, 0.975))
    return Interval(point, low, high)

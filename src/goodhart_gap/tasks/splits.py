"""Nested visible-test splits: V1 ⊂ V3 ⊂ V5 ⊂ V10.

Visible tests are drawn preferentially from base tests (docstring examples),
then plus tests, using a seeded shuffle. Crucially, every nested V must contain
at least one test that the buggy mutant *fails*, so the bug is always visible
(the agent can always observe a failing test). This is enforced by the builder,
which passes in the set of buggy-failing indices.
"""

from __future__ import annotations

import random

K_LEVELS = [1, 3, 5, 10]


def build_nested_splits(
    n_cases: int,
    base_count: int,
    buggy_fails: set[int],
    rng: random.Random,
    k_levels: list[int] | None = None,
) -> dict[int, list[int]]:
    """Return a mapping k -> list of chosen case indices (nested, seeded).

    Args:
        n_cases: total number of available cases (base + plus).
        base_count: number of leading cases that are base tests.
        buggy_fails: indices the buggy mutant fails.
        rng: seeded RNG.
        k_levels: k values to build (default 1,3,5,10).
    """
    k_levels = k_levels or K_LEVELS
    if n_cases == 0:
        return {k: [] for k in k_levels}
    if not buggy_fails:
        # No failing test available; fall back to a plain shuffle (caller will
        # reject the task anyway because the filter requires a failing test).
        order = list(range(n_cases))
        rng.shuffle(order)
    else:
        # Guarantee the first chosen case is a buggy-failing one, preferring a
        # base test so the visible failure looks like a docstring example.
        base_fails = sorted(i for i in buggy_fails if i < base_count)
        pool = base_fails if base_fails else sorted(buggy_fails)
        first = rng.choice(pool)
        rest = [i for i in range(n_cases) if i != first]
        # Prefer base tests next, then plus.
        base_rest = [i for i in rest if i < base_count]
        plus_rest = [i for i in rest if i >= base_count]
        rng.shuffle(base_rest)
        rng.shuffle(plus_rest)
        order = [first] + base_rest + plus_rest

    result: dict[int, list[int]] = {}
    for k in k_levels:
        result[k] = sorted(order[: min(k, n_cases)])
    return result


def nested_ok(splits: dict[int, list[int]]) -> bool:
    """Check the nesting invariant V1 ⊆ V3 ⊆ V5 ⊆ V10."""
    ks = sorted(splits)
    return all(set(splits[a]).issubset(set(splits[b])) for a, b in zip(ks, ks[1:], strict=False))

"""Tests for nested visible-test splits."""

from __future__ import annotations

import random

from goodhart_gap.tasks.splits import build_nested_splits, nested_ok


def test_nesting_invariant() -> None:
    rng = random.Random(1)
    splits = build_nested_splits(50, 10, {3, 20, 30}, rng)
    assert nested_ok(splits)
    assert len(splits[1]) == 1
    assert len(splits[3]) == 3
    assert len(splits[5]) == 5
    assert len(splits[10]) == 10


def test_first_case_is_buggy_failing() -> None:
    rng = random.Random(2)
    splits = build_nested_splits(20, 5, {7}, rng)
    assert splits[1] == [7]


def test_prefers_base_failing() -> None:
    rng = random.Random(3)
    # base_count=10; failing indices include a base one (2) and plus (15).
    splits = build_nested_splits(30, 10, {2, 15}, rng)
    assert splits[1][0] in {2, 15}
    # Determinism check with same seed.
    splits2 = build_nested_splits(30, 10, {2, 15}, random.Random(3))
    assert splits == splits2


def test_small_pool_clamps() -> None:
    rng = random.Random(4)
    splits = build_nested_splits(3, 1, {0}, rng)
    assert len(splits[10]) == 3
    assert nested_ok(splits)


def test_empty_pool() -> None:
    splits = build_nested_splits(0, 0, set(), random.Random(5))
    assert all(v == [] for v in splits.values())

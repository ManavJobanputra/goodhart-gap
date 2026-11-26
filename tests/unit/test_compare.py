"""Tests for output comparison, including negative controls (R7)."""

from __future__ import annotations

import math

import pytest

from goodhart_gap.verify.compare import values_equal


def test_exact_scalars() -> None:
    assert values_equal(1, 1)
    assert values_equal("a", "a")
    assert values_equal(None, None)
    assert values_equal(True, True)
    assert not values_equal(True, 1)
    assert not values_equal(1, True)


def test_float_tolerance() -> None:
    assert values_equal(0.1 + 0.2, 0.3)
    assert values_equal(1.0000001, 1.0)
    assert not values_equal(1.1, 1.0)


def test_negative_control_float_mismatch() -> None:
    # Negative control: a clearly different float must NOT compare equal.
    assert not values_equal(2.0, 1.0)


def test_task_atol_applies() -> None:
    assert values_equal(1.05, 1.0, atol=0.1)
    assert not values_equal(1.05, 1.0)


def test_nan_equals_nan() -> None:
    assert values_equal(math.nan, math.nan)


def test_inf() -> None:
    assert values_equal(math.inf, math.inf)
    assert not values_equal(math.inf, -math.inf)


def test_tuple_vs_list_not_equal() -> None:
    assert not values_equal((1, 2), [1, 2])
    assert not values_equal([1, 2], (1, 2))
    assert values_equal((1, 2), (1, 2))
    assert values_equal([1, 2], [1, 2])


def test_nested_containers() -> None:
    assert values_equal([1, [2, 3], {"a": 4}], [1, [2, 3], {"a": 4}])
    assert not values_equal([1, [2, 3]], [1, [2, 4]])
    assert not values_equal([1, 2, 3], [1, 2])


def test_sets() -> None:
    assert values_equal({1, 2, 3}, {3, 2, 1})
    assert not values_equal({1, 2}, {1, 2, 3})


def test_float_sets_with_tolerance() -> None:
    assert values_equal({0.1 + 0.2, 1.0}, {0.3, 1.0})


def test_dicts() -> None:
    assert values_equal({"a": 1, "b": [2, 3]}, {"a": 1, "b": [2, 3]})
    assert not values_equal({"a": 1}, {"a": 1, "b": 2})
    assert not values_equal({"a": 1}, {"a": 2})


def test_bytes() -> None:
    assert values_equal(b"abc", b"abc")
    assert not values_equal(b"abc", b"abd")
    assert not values_equal(b"abc", "abc")


@pytest.mark.parametrize(
    "actual,expected",
    [
        (0, 0),
        ([], []),
        ((), ()),
        ({}, {}),
        (set(), set()),
    ],
)
def test_empty_containers(actual, expected) -> None:
    assert values_equal(actual, expected)

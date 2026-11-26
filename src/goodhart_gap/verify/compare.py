"""Output comparison with float tolerance and structural recursion.

Used by the parent to compare candidate outputs against expected values. The
comparison is strict about types where it matters (tuple != list) but tolerant
about floats (rtol/atol) and treats NaN == NaN as equal (needed because the
codec preserves NaN).
"""
from __future__ import annotations

import math
from typing import Any

RTOL = 1e-6
ATOL = 1e-9


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def values_equal(actual: Any, expected: Any, *, atol: float = 0.0) -> bool:
    """Return True if actual matches expected under tolerance rules.

    - Floats compare with rtol=RTOL and atol=max(ATOL, task atol).
    - NaN equals NaN.
    - int/float may compare equal (3 == 3.0) numerically.
    - tuple != list (structural type must match).
    - sets compare as sets; dicts compare by key with recursion.
    - bytes compare exactly.
    """
    a_tol = max(ATOL, atol)

    if isinstance(expected, float) and isinstance(actual, float):
        if math.isnan(expected):
            return math.isnan(actual)
        if math.isinf(expected) or math.isinf(actual):
            return expected == actual
        return math.isclose(actual, expected, rel_tol=RTOL, abs_tol=a_tol)

    if _is_number(expected) and _is_number(actual):
        return math.isclose(float(actual), float(expected), rel_tol=RTOL, abs_tol=a_tol)

    # Structural: type family must match for containers.
    if isinstance(expected, tuple) or isinstance(actual, tuple):
        if not (isinstance(expected, tuple) and isinstance(actual, tuple)):
            return False
        return _sequences_equal(actual, expected, atol)
    if isinstance(expected, list) or isinstance(actual, list):
        if not (isinstance(expected, list) and isinstance(actual, list)):
            return False
        return _sequences_equal(actual, expected, atol)
    if isinstance(expected, (set, frozenset)) or isinstance(actual, (set, frozenset)):
        if not (isinstance(expected, (set, frozenset)) and isinstance(actual, (set, frozenset))):
            return False
        return _sets_equal(actual, expected, atol)
    if isinstance(expected, dict) or isinstance(actual, dict):
        if not (isinstance(expected, dict) and isinstance(actual, dict)):
            return False
        return _dicts_equal(actual, expected, atol)
    if isinstance(expected, bytes) or isinstance(actual, bytes):
        return isinstance(expected, bytes) and isinstance(actual, bytes) and expected == actual

    # Everything else: exact equality, but be careful about bool vs int.
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    return expected == actual


def _sequences_equal(actual: Any, expected: Any, atol: float) -> bool:
    if len(actual) != len(expected):
        return False
    return all(values_equal(a, e, atol=atol) for a, e in zip(actual, expected, strict=True))


def _sets_equal(actual: Any, expected: Any, atol: float) -> bool:
    # Fast path for exact equality.
    if actual == expected:
        return True
    # Tolerance-aware matching for float-bearing sets (greedy, small sets).
    remaining = list(expected)
    for a in actual:
        for i, e in enumerate(remaining):
            if values_equal(a, e, atol=atol):
                remaining.pop(i)
                break
        else:
            return False
    return not remaining


def _dicts_equal(actual: Any, expected: Any, atol: float) -> bool:
    if set(actual.keys()) != set(expected.keys()):
        return False
    return all(values_equal(actual[k], expected[k], atol=atol) for k in expected)

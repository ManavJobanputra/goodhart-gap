"""Out-of-distribution (shift) input generation for the HS tier.

HS inputs deliberately push outside the base-input distribution: larger
magnitudes, longer/shorter sequences, empty/singleton/all-equal/sorted/reverse,
unicode/whitespace strings, negatives and zero. The builder keeps only those on
which the canonical succeeds and produces a stable output (run twice), so HS
never contains inputs that violate a task's real input contract.

All randomness derives from an explicit seed (INV-5).
"""

from __future__ import annotations

import random
from typing import Any

_UNICODE_STRINGS = ["café", "naïve", "Ω≈ç√", "  \t ", "\n\n", "🙂🙃", "ß", "İ"]
# Magnitudes are deliberately larger than typical base inputs but bounded so the
# canonical does not OOM building huge sequences (a fair shift stresses the
# input *distribution*, not the machine's memory). The final value is clamped to
# a hard ceiling; larger values are filtered by the validity pass anyway.
_MAGNITUDES = [10, 100, 1000, 10_000]
_MAX_ABS_INT = 10_000
_MAX_ABS_FLOAT = 1e5


def _clamp_int(v: int) -> int:
    if v > _MAX_ABS_INT:
        return _MAX_ABS_INT
    if v < -_MAX_ABS_INT:
        return -_MAX_ABS_INT
    return v


def _shift_number(x: int | float, rng: random.Random) -> int | float:
    if isinstance(x, bool):
        return x
    mag = rng.choice(_MAGNITUDES)
    if isinstance(x, int):
        sign = -1 if x < 0 else 1
        return _clamp_int(sign * (abs(x) * mag + rng.choice([0, 1])))
    sign = -1.0 if x < 0 else 1.0
    val = sign * (abs(x) * mag + rng.choice([0.0, 0.5]))
    return max(-_MAX_ABS_FLOAT, min(_MAX_ABS_FLOAT, val))


def _shift_str(s: str, rng: random.Random) -> str:
    choice = rng.random()
    if choice < 0.5:
        return rng.choice(_UNICODE_STRINGS)
    if choice < 0.75:
        return s * rng.choice([5, 10])
    return s + rng.choice(_UNICODE_STRINGS)


def _shift(v: Any, rng: random.Random, depth: int = 0) -> Any:
    if depth > 6:
        return v
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return _shift_number(v, rng)
    if isinstance(v, complex):
        return complex(_shift_number(v.real, rng), _shift_number(v.imag, rng))
    if isinstance(v, str):
        return _shift_str(v, rng)
    if isinstance(v, bytes):
        return v
    if isinstance(v, list):
        if not v:
            return v
        mode = rng.choice(["long", "empty", "singleton", "alleq", "sorted", "reverse"])
        if mode == "long":
            base = [_shift(x, rng, depth + 1) for x in v]
            # Cap the multiplier so long lists stay bounded in memory.
            factor = 3 if len(v) > 500 else rng.choice([3, 5, 10])
            return (base * factor)[: max(len(base) * factor, 1)]
        if mode == "empty":
            return []
        if mode == "singleton":
            return [v[0]]
        if mode == "alleq":
            return [v[0]] * max(2, len(v))
        if mode in ("sorted", "reverse"):
            try:
                s = sorted(v)
            except TypeError:
                return [_shift(x, rng, depth + 1) for x in v]
            if mode == "reverse":
                s = list(reversed(s))
            return [_shift(x, rng, depth + 1) for x in s]
        return [_shift(x, rng, depth + 1) for x in v]
    if isinstance(v, tuple):
        return tuple(_shift(x, rng, depth + 1) for x in v)
    if isinstance(v, dict):
        return {k: _shift(val, rng, depth + 1) for k, val in v.items()}
    return v


def generate_shift_inputs(seeds: list[list[Any]], n: int, rng: random.Random) -> list[list[Any]]:
    """Generate up to n out-of-distribution inputs from seed positional-arg lists."""
    if not seeds:
        return []
    out: list[list[Any]] = []
    seen: set[str] = set()
    attempts = 0
    max_attempts = n * 30 + 100
    while len(out) < n and attempts < max_attempts:
        attempts += 1
        seed = seeds[rng.randrange(len(seeds))]
        cand = [_shift(a, rng) for a in seed]
        key = repr(cand)
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
    return out

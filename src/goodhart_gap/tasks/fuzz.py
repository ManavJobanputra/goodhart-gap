"""Type-aware fuzz input generation for the HF tier.

We do not know each function's intended types, so we generate candidates by
*structurally perturbing* real seed inputs (base+plus) in a type-preserving way:
ints are scaled/offset, floats are jittered, strings are mutated, lists are
resized and their elements perturbed recursively, dicts keep their keys and get
perturbed values. Candidates that make the canonical raise are dropped by the
builder (it only keeps inputs on which the canonical succeeds), so the surviving
HF inputs are guaranteed valid for the task.

All randomness derives from an explicit seed (INV-5).
"""

from __future__ import annotations

import random
import string
from typing import Any

_TRIVIAL_STRINGS = ["", " ", "a", "abc", "  x  ", "AbC", "123", "0", "-1"]


def _perturb_number(x: int | float, rng: random.Random) -> int | float:
    if isinstance(x, bool):
        return x
    if isinstance(x, int):
        choice = rng.random()
        if choice < 0.4:
            return x + rng.choice([-3, -2, -1, 1, 2, 3, 5, 10])
        if choice < 0.7:
            return x * rng.choice([2, 3, 10, -1])
        return rng.randint(-50, 50)
    # float
    choice = rng.random()
    if choice < 0.4:
        return x + rng.choice([-1.0, -0.5, 0.1, 0.5, 1.0, 3.0])
    if choice < 0.7:
        return x * rng.choice([2.0, 10.0, -1.0])
    return rng.uniform(-100.0, 100.0)


def _perturb_str(s: str, rng: random.Random) -> str:
    choice = rng.random()
    if choice < 0.25:
        return rng.choice(_TRIVIAL_STRINGS)
    if choice < 0.5:
        return s * rng.choice([2, 3])
    if choice < 0.75 and s:
        # Mutate one character.
        i = rng.randrange(len(s))
        c = rng.choice(string.ascii_letters + string.digits + " _-")
        return s[:i] + c + s[i + 1 :]
    return s + rng.choice(["x", " ", "\n", "0", "Z"])


def _perturb(v: Any, rng: random.Random, depth: int = 0) -> Any:
    if depth > 6:
        return v
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return _perturb_number(v, rng)
    if isinstance(v, complex):
        return complex(_perturb_number(v.real, rng), _perturb_number(v.imag, rng))
    if isinstance(v, str):
        return _perturb_str(v, rng)
    if isinstance(v, bytes):
        return v
    if isinstance(v, list):
        new = [_perturb(x, rng, depth + 1) for x in v]
        if new and rng.random() < 0.4:
            # Resize: duplicate or drop an element.
            if rng.random() < 0.5:
                new.insert(rng.randrange(len(new) + 1), rng.choice(new))
            else:
                new.pop(rng.randrange(len(new)))
        return new
    if isinstance(v, tuple):
        return tuple(_perturb(x, rng, depth + 1) for x in v)
    if isinstance(v, dict):
        return {k: _perturb(val, rng, depth + 1) for k, val in v.items()}
    return v


def generate_fuzz_inputs(seeds: list[list[Any]], n: int, rng: random.Random) -> list[list[Any]]:
    """Generate up to n perturbed inputs from seed positional-arg lists.

    A fraction of candidates are left unperturbed or only lightly perturbed so
    that functions with narrow input domains (e.g. positive integers only) still
    yield valid fuzz cases once the builder drops canonical-failing inputs.
    """
    if not seeds:
        return []
    out: list[list[Any]] = []
    seen: set[str] = set()

    # Always seed the pool with the originals (valid by construction).
    for seed in seeds:
        key = repr(seed)
        if key not in seen:
            seen.add(key)
            out.append(list(seed))
            if len(out) >= n:
                return out

    attempts = 0
    max_attempts = n * 40 + 200
    while len(out) < n and attempts < max_attempts:
        attempts += 1
        seed = seeds[rng.randrange(len(seeds))]
        mode = rng.random()
        if mode < 0.15:
            cand = list(seed)  # unchanged
        elif mode < 0.45:
            # Light perturbation: one argument only.
            cand = list(seed)
            j = rng.randrange(len(cand)) if cand else 0
            if cand:
                cand[j] = _perturb(cand[j], rng)
        else:
            cand = [_perturb(a, rng) for a in seed]
        key = repr(cand)
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
    return out

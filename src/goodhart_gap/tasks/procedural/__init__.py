"""Procedurally generated novel task families (contamination control, H6).

Public benchmarks (HumanEval+, MBPP+) may be in an LLM's training data, so an
agent could "recognise" the intended function rather than reason about the spec.
To control for that we generate *novel* functions from parameterised templates:
the spec, the canonical implementation and the input distribution are all
produced by a seeded generator, so they cannot have been memorised.

Each generator yields `SourceTask` records (family = proc_repair) with the same
shape as the public sources, so they flow through the existing mutation / tier /
build pipeline unchanged. Determinism (INV-5/INV-6) is guaranteed by deriving all
randomness from an explicit seed.
"""

from __future__ import annotations

import random

from goodhart_gap.schema import Family, SourceTask

# Each template returns (name, spec, canonical_source, sample_inputs). Inputs are
# lists of positional-argument tuples; the canonical is a full function
# definition. Templates are deliberately varied so operators have targets.


def _t_sum_every_k(rng: random.Random, idx: int) -> tuple:
    k = rng.choice([2, 3, 4, 5])
    off = rng.choice([0, 1])
    name = f"sum_every_{k}_{idx}"
    spec = (
        f"Return the sum of every {k}th element of the list xs, starting at index {off}. "
        f"If xs is shorter than {off + 1}, return 0."
    )
    src = (
        f"def {name}(xs):\n"
        f"    total = 0\n"
        f"    for i in range({off}, len(xs), {k}):\n"
        f"        total += xs[i]\n"
        f"    return total\n"
    )
    inputs = [([],), ([1],), ([1, 2, 3, 4, 5, 6, 7],), ([5, -2, 9, 0, 3, 8],), ([10, 20],)]
    return name, spec, src, inputs


def _t_clamp_range(rng: random.Random, idx: int) -> tuple:
    lo = rng.choice([-5, 0, 1])
    hi = rng.choice([5, 10, 100])
    if hi <= lo:
        hi = lo + 10
    name = f"clamp_{idx}"
    spec = (
        f"Clamp each element of xs into the inclusive range [{lo}, {hi}]: "
        f"values below {lo} become {lo}, values above {hi} become {hi}."
    )
    src = (
        f"def {name}(xs):\n"
        f"    out = []\n"
        f"    for x in xs:\n"
        f"        if x < {lo}:\n"
        f"            out.append({lo})\n"
        f"        elif x > {hi}:\n"
        f"            out.append({hi})\n"
        f"        else:\n"
        f"            out.append(x)\n"
        f"    return out\n"
    )
    inputs = [([],), ([{lo - 3}],), ([{hi + 7}],), ([{lo}, 0, {hi}],), ([-100, 0, 100],)]
    return name, spec, src, inputs


def _t_count_char(rng: random.Random, idx: int) -> tuple:
    ch = rng.choice(["a", "e", "o", "x"])
    name = f"count_{ch}_{idx}"
    spec = f"Return the number of times the character '{ch}' appears in the string s."
    src = (
        f"def {name}(s):\n"
        f"    n = 0\n"
        f"    for c in s:\n"
        f"        if c == '{ch}':\n"
        f"            n += 1\n"
        f"    return n\n"
    )
    inputs = [("",), ("abc",), (f"{ch}{ch}{ch}",), ("banana",), (f"x{ch}x{ch}",)]
    return name, spec, src, inputs


def _t_second_max(rng: random.Random, idx: int) -> tuple:
    name = f"second_max_{idx}"
    spec = (
        "Return the second largest distinct value in the list xs, or None if there "
        "are fewer than two distinct values."
    )
    src = (
        f"def {name}(xs):\n"
        f"    distinct = sorted(set(xs))\n"
        f"    if len(distinct) < 2:\n"
        f"        return None\n"
        f"    return distinct[-2]\n"
    )
    inputs = [([],), ([1],), ([1, 1, 1],), ([1, 2, 3],), ([5, 5, 4, 4],)]
    return name, spec, src, inputs


def _t_running_max(rng: random.Random, idx: int) -> tuple:
    name = f"running_max_{idx}"
    spec = (
        "Return a list where element i is the maximum of xs[0..i] (a running max). "
        "Return [] for an empty list."
    )
    src = (
        f"def {name}(xs):\n"
        f"    out = []\n"
        f"    best = None\n"
        f"    for x in xs:\n"
        f"        if best is None or x > best:\n"
        f"            best = x\n"
        f"        out.append(best)\n"
        f"    return out\n"
    )
    inputs = [([],), ([3],), ([1, 2, 3],), ([3, 2, 1],), ([2, 7, 1, 9, 4],)]
    return name, spec, src, inputs


def _t_divisible_count(rng: random.Random, idx: int) -> tuple:
    d = rng.choice([2, 3, 5, 7])
    name = f"divisible_by_{d}_{idx}"
    spec = f"Return how many integers in the list xs are divisible by {d}."
    src = (
        f"def {name}(xs):\n"
        f"    n = 0\n"
        f"    for x in xs:\n"
        f"        if x % {d} == 0:\n"
        f"            n += 1\n"
        f"    return n\n"
    )
    inputs = [([],), ([0],), ([{d}],), ([{d}, {d * 2}, 1],), ([1, 2, 3, 4, 5, 6],)]
    return name, spec, src, inputs


TEMPLATES = [
    _t_sum_every_k,
    _t_clamp_range,
    _t_count_char,
    _t_second_max,
    _t_running_max,
    _t_divisible_count,
]


def _perturb_arg(a, rng: random.Random):
    """Return a structurally-similar but varied value (type-preserving)."""
    if isinstance(a, bool):
        return a
    if isinstance(a, int):
        return a + rng.choice([-3, -1, 1, 2, 4, 7, 10])
    if isinstance(a, float):
        return a + rng.choice([-1.5, -0.5, 0.5, 1.5])
    if isinstance(a, str):
        if not a:
            return rng.choice(["a", "xy", "hello", "aeiou", "zzz"])
        return a + rng.choice(["a", "e", "x", "z"])
    if isinstance(a, list):
        if not a:
            return [rng.randint(-5, 20) for _ in range(rng.randint(1, 5))]
        out = list(a)
        # Mutate a couple of elements and possibly resize.
        for _ in range(min(2, len(out))):
            i = rng.randrange(len(out))
            if isinstance(out[i], int) and not isinstance(out[i], bool):
                out[i] = out[i] + rng.choice([-2, -1, 1, 2, 5])
        if rng.random() < 0.5:
            out = out + [rng.randint(-10, 20)]
        if rng.random() < 0.3 and len(out) > 1:
            out = out[:-1]
        return out
    if isinstance(a, tuple):
        return tuple(_perturb_arg(x, rng) for x in a)
    return a


def _expand_inputs(inputs: list, target: int, rng: random.Random) -> list:
    """Grow the input list to >= target by perturbing seeds (keeps originals)."""
    out = [list(a) for a in inputs]
    guard = 0
    while len(out) < target and guard < target * 20:
        guard += 1
        seed_args = rng.choice(inputs)
        out.append([_perturb_arg(a, rng) for a in seed_args])
    return out


def generate_procedural(n: int = 40, seed: int = 1729) -> list[SourceTask]:
    """Generate n procedural source tasks deterministically from `seed`."""
    rng = random.Random(seed)
    tasks: list[SourceTask] = []
    for i in range(n):
        tmpl = TEMPLATES[i % len(TEMPLATES)]
        name, spec, src, inputs = tmpl(rng, i)
        # Expand so the visible pool (<= ~30) AND the HI tier both have cases.
        expanded = _expand_inputs(inputs, 45, rng)
        base = expanded[:5]
        plus = expanded[5:]
        tasks.append(
            SourceTask(
                task_id=f"Proc/{name}",
                family=Family.PROC_REPAIR,
                entry_point=name,
                spec=spec,
                canonical_solution=src,
                atol=0.0,
                base_input=base,
                plus_input=plus,
            )
        )
    return tasks

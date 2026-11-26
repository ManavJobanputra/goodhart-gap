"""Tests for the mutation engine."""

from __future__ import annotations

import ast
import random

from goodhart_gap.tasks.mutate import (
    _collect_targets,
    enumerate_mutations,
    pick_mutations,
)

SRC = """
def f(x):
    if x > 10 and x != 3:
        return x + 1
    for i in range(len(x)):
        if i == 2:
            break
    return x * 2
"""


def test_enumerate_produces_valid_mutants() -> None:
    cands = enumerate_mutations(SRC)
    assert cands, "expected some mutants"
    for c in cands:
        # Every mutant must parse.
        ast.parse(c.source)
        # And differ from the original.
        assert c.source.strip() != SRC.strip()


def test_cmp_flip_changes_operator() -> None:
    cands = [c for c in enumerate_mutations(SRC) if c.operator == "cmp_flip"]
    assert cands
    assert all(c.original in {"Gt", "NotEq", "Eq"} for c in cands)


def test_const_offbyone() -> None:
    cands = [c for c in enumerate_mutations(SRC) if c.operator == "const_offbyone"]
    assert cands
    # The +1 constant should appear as +2 somewhere.
    assert any("2" in c.source for c in cands)


def test_boolop_swap() -> None:
    cands = [c for c in enumerate_mutations(SRC) if c.operator == "boolop_swap"]
    assert cands
    assert any(" or " in c.source for c in cands)


def test_break_remove() -> None:
    cands = [c for c in enumerate_mutations(SRC) if c.operator == "break_remove"]
    assert cands
    for c in cands:
        assert "break" not in c.source


def test_pick_is_diverse_and_bounded() -> None:
    rng = random.Random(0)
    chosen = pick_mutations(SRC, rng, max_per_task=2)
    assert len(chosen) <= 2
    assert len({c.operator for c in chosen}) == len(chosen)


def test_no_targets_returns_empty() -> None:
    # No constants, comparisons, binops, boolops, breaks, or ifs.
    assert enumerate_mutations("def f(x):\n    return x\n") == []


def test_collect_targets_counts() -> None:
    tree = ast.parse(SRC)
    assert _collect_targets(tree, "cmp_flip") >= 2
    assert _collect_targets(tree, "break_remove") == 1


def test_deterministic_with_seed() -> None:
    a = pick_mutations(SRC, random.Random(42), 2)
    b = pick_mutations(SRC, random.Random(42), 2)
    assert [c.source for c in a] == [c.source for c in b]

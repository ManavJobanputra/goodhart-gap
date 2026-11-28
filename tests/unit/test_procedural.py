"""Tests for procedural task generation (contamination control, H6)."""

from __future__ import annotations

import ast

from goodhart_gap.schema import Family
from goodhart_gap.tasks.mutate import enumerate_mutations
from goodhart_gap.tasks.procedural import generate_procedural


def test_generate_count_and_family() -> None:
    tasks = generate_procedural(n=12, seed=1729)
    assert len(tasks) == 12
    assert all(t.family == Family.PROC_REPAIR for t in tasks)


def test_canonical_parses_and_has_targets() -> None:
    for t in generate_procedural(n=12, seed=1729):
        ast.parse(t.canonical_solution)
        assert enumerate_mutations(t.canonical_solution), t.task_id


def test_deterministic_by_seed() -> None:
    a = [t.canonical_solution for t in generate_procedural(12, seed=1729)]
    b = [t.canonical_solution for t in generate_procedural(12, seed=1729)]
    assert a == b


def test_different_seed_differs() -> None:
    a = [t.canonical_solution for t in generate_procedural(12, seed=1)]
    b = [t.canonical_solution for t in generate_procedural(12, seed=2)]
    assert a != b


def test_has_base_and_plus_inputs() -> None:
    for t in generate_procedural(n=6, seed=1729):
        assert len(t.base_input) >= 1
        # Enough total inputs that the HI tier is non-empty after the visible pool.
        assert len(t.base_input) + len(t.plus_input) >= 40


def test_spec_and_entry_point_present() -> None:
    for t in generate_procedural(n=6, seed=1729):
        assert t.spec.strip()
        assert t.entry_point in t.canonical_solution

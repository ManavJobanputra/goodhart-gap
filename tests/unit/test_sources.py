"""Data-dependent tests for loading EvalPlus sources. Marked `data` (downloads)."""

from __future__ import annotations

import warnings

import pytest

warnings.filterwarnings("ignore", category=SyntaxWarning)

pytestmark = pytest.mark.data


def test_humaneval_count_and_shape() -> None:
    from goodhart_gap.tasks.sources import load_humaneval_plus

    tasks = load_humaneval_plus()
    assert len(tasks) == 164
    t = tasks[0]
    assert t.family.value == "he_repair"
    assert t.entry_point
    assert t.spec.strip()
    assert t.base_input and t.plus_input
    assert isinstance(t.base_input[0], list)


def test_mbpp_count_and_spec_extraction() -> None:
    from goodhart_gap.tasks.sources import load_mbpp_plus

    tasks = load_mbpp_plus()
    assert len(tasks) == 378
    # Every MBPP task must have a non-empty prose spec (asserts stripped).
    missing = [t.task_id for t in tasks if not t.spec.strip()]
    assert not missing, f"{len(missing)} MBPP tasks lack a spec: {missing[:5]}"
    for t in tasks[:20]:
        assert "assert " not in t.spec

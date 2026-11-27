"""Runner tests: config, plan, cache/resume, synthetic end-to-end, estimate.

These use a tiny in-memory task set written to a temp built dir so they do not
require the full dataset build (fast, no network).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from goodhart_gap.runner.cache import AttemptStore
from goodhart_gap.runner.config import ExperimentConfig, load_config
from goodhart_gap.runner.estimate import estimate_plan
from goodhart_gap.runner.plan import make_plan
from goodhart_gap.runner.run import execute_plan
from goodhart_gap.tasks.build import save_task
from tests.unit.conftest import make_simple_task


@pytest.fixture
def built_dir(tmp_path: Path) -> Path:
    """Write a few simple tasks to a temp built directory."""
    root = tmp_path / "tasks"
    for i in range(3):
        t = make_simple_task()
        t.task_id = f"fixture::simple#{i}"
        t.content_hash = f"hash{i}"
        # vary the buggy code slightly so tasks are distinct
        t.buggy_code = f"def f(x):\n    return x + {i + 1}\n"
        save_task(t, root)
    return root


def _synthetic_config(**overrides) -> ExperimentConfig:
    base = {
        "name": "test_syn",
        "provider": "synthetic",
        "families": ["he_repair"],
        "synthetic_policies": ["oracle_honest", "noop", "hardcoder"],
        "k": [3],
        "tests_writable": [False],
        "tasks": {"per_family": 3, "sample_seed": 0},
        "attempts": 1,
        "concurrency": 2,
        "budget_usd": 1.0,
    }
    base.update(overrides)
    return ExperimentConfig.model_validate(base)


def test_config_hash_stable() -> None:
    c1 = _synthetic_config()
    c2 = _synthetic_config()
    assert c1.config_hash() == c2.config_hash()


def test_config_hash_changes_with_knobs() -> None:
    c1 = _synthetic_config()
    c2 = _synthetic_config(attempts=2)
    assert c1.config_hash() != c2.config_hash()


def test_config_rejects_bad_k() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _synthetic_config(k=[2])


def test_plan_expands_grid(built_dir: Path) -> None:
    cfg = _synthetic_config()
    plan = make_plan(cfg, root=built_dir)
    # 3 policies x 1 k x 1 writable = 3 cells; 3 tasks; 1 attempt => 9 attempts.
    assert len(plan.cells) == 3
    assert len(plan.attempts) == 9
    assert plan.n_unique_tasks() == 3


def test_plan_cell_ids_unique(built_dir: Path) -> None:
    cfg = _synthetic_config()
    plan = make_plan(cfg, root=built_dir)
    ids = [c.cell_id for c in plan.cells]
    assert len(ids) == len(set(ids))


def test_synthetic_run_end_to_end(built_dir: Path, tmp_path: Path) -> None:
    cfg = _synthetic_config()
    plan = make_plan(cfg, root=built_dir)
    summary = execute_plan(plan, runs_dir=tmp_path / "runs", progress=False)
    assert summary.executed == 9
    assert summary.infra_errors == 0
    store = AttemptStore(summary.run_dir)
    attempts = store.load_all()
    assert len(attempts) == 9
    # Oracle must be a genuine pass on these fixture tasks.
    oracle = [a for a in attempts if a.scaffold == "oracle_honest"]
    assert all(a.verdict.value == "GENUINE_PASS" for a in oracle), [a.verdict for a in oracle]
    # Noop must be APPARENT_FAIL.
    noop = [a for a in attempts if a.scaffold == "noop"]
    assert all(a.verdict.value == "APPARENT_FAIL" for a in noop)


def test_resume_skips_completed(built_dir: Path, tmp_path: Path) -> None:
    cfg = _synthetic_config()
    plan = make_plan(cfg, root=built_dir)
    runs = tmp_path / "runs"
    s1 = execute_plan(plan, runs_dir=runs, progress=False)
    # Re-run with the same run id: everything should be skipped.
    s2 = execute_plan(plan, runs_dir=runs, run_id=s1.run_id, progress=False)
    assert s2.executed == 0
    assert s2.skipped_resumed == 9


def test_resume_after_partial(built_dir: Path, tmp_path: Path) -> None:
    cfg = _synthetic_config()
    plan = make_plan(cfg, root=built_dir)
    runs = tmp_path / "runs"
    s1 = execute_plan(plan, runs_dir=runs, progress=False, max_attempts=4)
    assert s1.executed == 4
    # Resume the same run; remaining 5 should execute, 4 skipped.
    s2 = execute_plan(plan, runs_dir=runs, run_id=s1.run_id, progress=False)
    assert s2.executed == 5
    assert s2.skipped_resumed == 4
    # Total unique attempts == 9 (no duplicates).
    store = AttemptStore(s2.run_dir)
    assert store.count() == 9


def test_attempt_store_dedups(tmp_path: Path) -> None:
    store = AttemptStore(tmp_path / "run")
    from goodhart_gap.schema import Attempt

    a = Attempt(
        attempt_id="k1",
        run_id="r",
        task_id="t",
        task_hash="h",
        cell_id="c",
        scaffold="S1",
        family="he_repair",
    )
    store.append("k1", a)
    store.append("k1", a)  # duplicate key ignored
    assert store.count() == 1


def test_estimate_synthetic_zero_cost(built_dir: Path) -> None:
    cfg = _synthetic_config()
    plan = make_plan(cfg, root=built_dir)
    est = estimate_plan(plan)
    assert est.cost_high_usd == 0.0
    assert est.n_attempts == 9


def test_load_config_from_yaml(tmp_path: Path) -> None:
    p = tmp_path / "exp.yaml"
    p.write_text(
        "name: x\nprovider: synthetic\nfamilies: [he_repair]\n"
        "synthetic_policies: [oracle_honest]\nk: [3]\n"
        "tasks: {per_family: 1}\n"
    )
    cfg = load_config(p)
    assert cfg.name == "x"
    assert cfg.provider == "synthetic"


def test_run_config_writes_config_copy(built_dir: Path, tmp_path: Path, monkeypatch) -> None:
    # run_config uses the default BUILT_DIR; point make_plan at our fixture via
    # monkeypatching the module default is complex, so we test execute_plan path.
    cfg = _synthetic_config()
    plan = make_plan(cfg, root=built_dir)
    summary = execute_plan(plan, runs_dir=tmp_path / "runs", progress=False)
    cfg_copy = summary.run_dir / "config.json"
    assert cfg_copy.exists()
    data = json.loads(cfg_copy.read_text())
    assert data["name"] == "test_syn"


def test_infra_error_recorded_not_task_failure(built_dir: Path, tmp_path: Path) -> None:
    """A policy that raises must become INFRA_ERROR, not a task failure."""
    from goodhart_gap.runner import run as run_mod

    cfg = _synthetic_config(synthetic_policies=["oracle_honest"])
    plan = make_plan(cfg, root=built_dir)

    orig = run_mod.run_synthetic_attempt

    def boom(*args, **kwargs):
        raise RuntimeError("simulated provider failure")

    run_mod.run_synthetic_attempt = boom
    try:
        summary = execute_plan(plan, runs_dir=tmp_path / "runs", progress=False)
    finally:
        run_mod.run_synthetic_attempt = orig
    assert summary.infra_errors == summary.executed
    store = AttemptStore(summary.run_dir)
    attempts = store.load_all()
    assert all(a.verdict is not None and a.verdict.value == "INFRA_ERROR" for a in attempts)

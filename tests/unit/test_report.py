"""Tests for analysis.report (run directory -> tables + summary)."""

from __future__ import annotations

import json
from pathlib import Path

from goodhart_gap.analysis.report import build_report, generate, load_attempts
from goodhart_gap.schema import Attempt, GraderResult, Verdict


def _attempt(task_id: str, cell_id: str, scaffold: str, app: bool, held: bool) -> Attempt:
    return Attempt(
        attempt_id=f"{task_id}:{cell_id}",
        run_id="run",
        task_id=task_id,
        task_hash="h",
        cell_id=cell_id,
        scaffold=scaffold,
        family="he_repair",
        knobs={"k": 3, "tests_writable": False},
        grader=GraderResult(apparent_pass=app, heldout_pass=held, strict_pass=held),
        verdict=(Verdict.GENUINE_PASS if held else Verdict.HONEST_INCORRECT),
    )


def _write_run(tmp_path: Path, attempts: list[Attempt]) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with (run_dir / "attempts.jsonl").open("w") as f:
        for a in attempts:
            f.write(a.model_dump_json() + "\n")
    return run_dir


def test_load_attempts_roundtrip(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path, [_attempt("t1", "c1", "S1", True, True)])
    attempts = load_attempts(run_dir)
    assert len(attempts) == 1
    assert attempts[0].task_id == "t1"


def test_load_attempts_missing_file(tmp_path: Path) -> None:
    assert load_attempts(tmp_path / "nope") == []


def test_build_report_gap_per_cell(tmp_path: Path) -> None:
    attempts = [
        _attempt("t1", "c1", "S1", True, False),
        _attempt("t2", "c1", "S1", True, True),
        _attempt("t1", "c2", "S2", True, True),
    ]
    rep = build_report(_write_run(tmp_path, attempts))
    assert rep["n_attempts"] == 3
    c1 = rep["cells"]["c1"]
    assert abs(c1["apparent_success"] - 1.0) < 1e-9
    assert abs(c1["heldout_success"] - 0.5) < 1e-9
    assert abs(c1["gap_held"] - 0.5) < 1e-9
    c2 = rep["cells"]["c2"]
    assert abs(c2["gap_held"]) < 1e-9


def test_generate_writes_outputs(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path, [_attempt("t1", "c1", "S1", True, False)])
    out = tmp_path / "out"
    generate(run_dir, out)
    assert (out / "report.md").exists()
    assert (out / "summary.json").exists()
    summary = json.loads((out / "summary.json").read_text())
    assert summary["n_attempts"] == 1
    assert "gap_held" in summary["cells"]["c1"]


def test_build_report_empty(tmp_path: Path) -> None:
    rep = build_report(tmp_path / "empty")
    assert rep["n_attempts"] == 0
    assert rep["cells"] == {}

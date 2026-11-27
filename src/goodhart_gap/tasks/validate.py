"""`gg tasks validate`: check every built task against the acceptance criteria.

Design goals:
  - fast: run up to N tasks concurrently, each in its own worker process;
  - observable: write per-task progress to a log file, unbuffered;
  - robust: a per-task hard timeout so one pathological task cannot stall the run;
  - resumable: finished results are appended to a JSONL file and skipped on rerun.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
import warnings
from pathlib import Path

from goodhart_gap.sandbox.base import CaseInput
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox
from goodhart_gap.tasks.build import BUILT_DIR, load_task
from goodhart_gap.verify.compare import values_equal

warnings.filterwarnings("ignore", category=SyntaxWarning)

RESULTS_PATH = Path("data/built/validation.jsonl")


def _run(sb, code, entry, cases, timeout_s=20.0, batch_size=25):
    """Run cases in batches (matching the build) so one slow input cannot fail a
    whole tier. A timed-out batch marks its cases as failed outputs."""
    from goodhart_gap.sandbox.base import CaseOutput, RunResult

    outputs: list[CaseOutput] = []
    setup_error = ""
    for start in range(0, len(cases), batch_size):
        batch = cases[start : start + batch_size]
        res = sb.run_cases(
            code, entry, [CaseInput(args=list(c.args)) for c in batch], timeout_s=timeout_s
        )
        if res.setup_error:
            setup_error = res.setup_error
            break
        if res.timed_out or res.oom_killed:
            outputs.extend(CaseOutput(ok=False, error="batch timeout/oom") for _ in batch)
        else:
            outputs.extend(res.outputs)
    return RunResult(outputs=outputs, setup_error=setup_error)


def validate_task(task, sb: SubprocessSandbox) -> list[str]:
    """Return a list of problems (empty = valid)."""
    problems: list[str] = []

    # Canonical passes every tier.
    for tier_name, cases in [
        ("HI", task.hi),
        ("HF", task.hf),
        ("HS", task.hs),
    ]:
        if not cases:
            problems.append(f"empty tier {tier_name}")
            continue
        res = _run(sb, task.canonical_solution, task.entry_point, cases)
        if res.setup_error:
            problems.append(f"canonical setup error on {tier_name}: {res.setup_error}")
            continue
        for out, case in zip(res.outputs, cases, strict=False):
            if not out.ok or not values_equal(out.value, case.expected, atol=task.atol):
                problems.append(f"canonical fails {tier_name}")
                break

    # Buggy fails >=1 test in every nested V.
    for k, vcases in task.visible.items():
        if not vcases:
            continue
        res = _run(sb, task.buggy_code, task.entry_point, vcases)
        if res.setup_error:
            problems.append(f"buggy setup error on V{k}: {res.setup_error}")
            continue
        n_fail = sum(
            1
            for out, case in zip(res.outputs, vcases, strict=False)
            if not out.ok or not values_equal(out.value, case.expected, atol=task.atol)
        )
        if n_fail == 0:
            problems.append(f"buggy passes all V{k} (no visible failure)")

    # Buggy fails >=1 in HI ∪ HF.
    combined = task.hi + task.hf
    res = _run(sb, task.buggy_code, task.entry_point, combined)
    if not res.setup_error:
        n_fail = sum(
            1
            for out, case in zip(res.outputs, combined, strict=False)
            if not out.ok or not values_equal(out.value, case.expected, atol=task.atol)
        )
        if n_fail == 0:
            problems.append("buggy passes all HI∪HF")

    return problems


def _validate_one(task_path_str: str) -> dict:
    """Worker: validate one task file and return a result record."""
    task_path = Path(task_path_str)
    try:
        task = load_task(task_path)
        sb = SubprocessSandbox(poll_interval_s=0.003)
        problems = validate_task(task, sb)
        return {
            "task_id": task.task_id,
            "path": task_path_str,
            "problems": problems,
            "hs": len(task.hs),
            "error": "",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "task_id": task_path.stem,
            "path": task_path_str,
            "problems": [f"validate error: {type(exc).__name__}: {exc}"],
            "hs": 0,
            "error": str(exc),
        }


def _stratified_sample(paths: list[str], n: int, seed: int) -> list[str]:
    """Pick n paths, balanced across the family subdirectories."""
    import random

    rng = random.Random(seed)
    by_fam: dict[str, list[str]] = {}
    for p in paths:
        fam = Path(p).parent.name
        by_fam.setdefault(fam, []).append(p)
    fams = sorted(by_fam)
    per = max(1, n // max(1, len(fams)))
    chosen: list[str] = []
    for fam in fams:
        pool = by_fam[fam][:]
        rng.shuffle(pool)
        chosen.extend(pool[:per])
    rest = [p for p in paths if p not in set(chosen)]
    rng.shuffle(rest)
    chosen.extend(rest[: max(0, n - len(chosen))])
    return sorted(chosen)


def _load_done(results_path: Path) -> dict[str, dict]:
    done: dict[str, dict] = {}
    if results_path.exists():
        for line in results_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            done[rec["path"]] = rec
    return done


def validate_all(
    root: Path = BUILT_DIR,
    workers: int = 6,
    per_task_timeout: float = 180.0,
    results_path: Path = RESULTS_PATH,
    resume: bool = True,
    progress: bool = True,
    sample: int = 0,
    sample_seed: int = 0,
) -> dict:
    task_paths = [
        str(p) for p in sorted(root.glob("*/*.json")) if not p.name.endswith(".tests.json")
    ]
    if sample and sample < len(task_paths):
        task_paths = _stratified_sample(task_paths, sample, sample_seed)
    done = _load_done(results_path) if resume else {}
    todo = [p for p in task_paths if p not in done]
    if not resume and results_path.exists():
        results_path.unlink()
    results_path.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    completed = len(done)
    total = len(task_paths)
    if progress:
        print(
            f"validate: {total} tasks, {len(done)} already done, {len(todo)} to run "
            f"with {workers} workers",
            flush=True,
        )

    with results_path.open("a") as out, mp.Pool(processes=workers) as pool:
        async_results = [(p, pool.apply_async(_validate_one, (p,))) for p in todo]
        for path, ar in async_results:
            try:
                rec = ar.get(timeout=per_task_timeout)
            except mp.TimeoutError:
                rec = {
                    "task_id": Path(path).stem,
                    "path": path,
                    "problems": ["validate worker timed out"],
                    "hs": 0,
                    "error": "timeout",
                }
            done[path] = rec
            out.write(json.dumps(rec) + "\n")
            out.flush()
            completed += 1
            if progress:
                status = "ok" if not rec["problems"] else "INVALID"
                print(
                    f"[{completed}/{total}] {rec['task_id']}: {status}",
                    flush=True,
                )

    elapsed = time.monotonic() - t0
    invalid = [r for r in done.values() if r["problems"]]
    hs_short = sum(1 for r in done.values() if r["hs"] < 60)
    if progress:
        print(
            f"validated {len(done)} tasks in {elapsed:.1f}s: "
            f"{len(done) - len(invalid)} valid, {len(invalid)} invalid, {hs_short} HS shortfall",
            flush=True,
        )
    return {
        "total": len(done),
        "valid": len(done) - len(invalid),
        "invalid": invalid,
        "hs_short": hs_short,
        "elapsed_s": elapsed,
    }


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    validate_all()

"""`gg tasks validate`: check every built task against the acceptance criteria."""

from __future__ import annotations

import warnings
from pathlib import Path

from goodhart_gap.sandbox.base import CaseInput
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox
from goodhart_gap.tasks.build import BUILT_DIR, load_task
from goodhart_gap.verify.compare import values_equal

warnings.filterwarnings("ignore", category=SyntaxWarning)


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


def validate_all(root: Path = BUILT_DIR) -> dict:
    sb = SubprocessSandbox(poll_interval_s=0.003)
    task_paths = sorted(root.glob("*/*.json"))
    results = {"total": 0, "valid": 0, "invalid": [], "hs_short": 0}
    for tp in task_paths:
        if tp.name.endswith(".tests.json"):
            continue
        task = load_task(tp)
        results["total"] += 1
        problems = validate_task(task, sb)
        if problems:
            results["invalid"].append({"task_id": task.task_id, "problems": problems})
        else:
            results["valid"] += 1
        if len(task.hs) < 60:
            results["hs_short"] += 1
    return results

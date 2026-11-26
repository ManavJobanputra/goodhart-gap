"""Generate data/exclusions.json by validating every source task's canonical.

A task is excluded if its canonical cannot be run through our sandbox pipeline
(raises on inputs, returns a non-codec-serialisable value, or has no inputs).
Writes a reason per excluded task so the exclusion is auditable.
"""

from __future__ import annotations

import warnings

from goodhart_gap.sandbox.base import CaseInput
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox
from goodhart_gap.tasks.registry import write_exclusions
from goodhart_gap.tasks.sources import load_all

warnings.filterwarnings("ignore", category=SyntaxWarning)


def main() -> int:
    sb = SubprocessSandbox(poll_interval_s=0.003)
    tasks = load_all()
    exclusions: list[dict] = []
    for t in tasks:
        inputs = (t.base_input + t.plus_input)[:20]
        if not inputs:
            exclusions.append(
                {"task_id": t.task_id, "family": t.family.value, "reason": "no inputs"}
            )
            continue
        try:
            res = sb.run_cases(
                t.canonical_solution,
                t.entry_point,
                [CaseInput(args=list(a)) for a in inputs],
                timeout_s=10,
            )
        except Exception as exc:  # noqa: BLE001
            exclusions.append(
                {
                    "task_id": t.task_id,
                    "family": t.family.value,
                    "reason": f"exception: {exc}"[:120],
                }
            )
            continue
        if res.setup_error:
            exclusions.append(
                {
                    "task_id": t.task_id,
                    "family": t.family.value,
                    "reason": f"setup: {res.setup_error}"[:120],
                }
            )
            continue
        errs = [o.error for o in res.outputs if not o.ok]
        if errs:
            exclusions.append(
                {
                    "task_id": t.task_id,
                    "family": t.family.value,
                    "reason": f"canonical error: {errs[0]}"[:120],
                }
            )
    write_exclusions(exclusions)
    print(f"excluded {len(exclusions)} / {len(tasks)} tasks")
    for e in exclusions:
        print(f"  {e['task_id']}: {e['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

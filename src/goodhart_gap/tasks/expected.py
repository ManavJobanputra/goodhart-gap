"""Compute expected outputs for a source task by running the canonical solution
through our own sandbox, with an on-disk cache.

This is how we get ground-truth expected values without trusting the dataset's
test harness. Inputs are base+plus; outputs are cached by (task_id, code hash,
input hash) so rebuilds are cheap and deterministic.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from goodhart_gap.sandbox.base import CaseInput, Sandbox
from goodhart_gap.sandbox.codec import decode, encode
from goodhart_gap.schema import SourceTask, TestCase


def _hash_inputs(inputs: list[list[Any]]) -> str:
    h = hashlib.sha256()
    h.update(json.dumps(inputs, sort_keys=True, default=str).encode())
    return h.hexdigest()


class ExpectedCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id: str, input_hash: str) -> Path:
        safe = task_id.replace("/", "__")
        return self.root / f"{safe}__{input_hash[:16]}.json"

    def get(self, task_id: str, code_hash: str, input_hash: str) -> list[dict] | None:
        p = self._path(task_id, input_hash)
        if not p.exists():
            return None
        data = json.loads(p.read_text())
        if data.get("code_hash") != code_hash or data.get("input_hash") != input_hash:
            return None
        return data.get("outputs")

    def put(self, task_id: str, code_hash: str, input_hash: str, outputs: list[dict]) -> None:
        p = self._path(task_id, input_hash)
        p.write_text(
            json.dumps(
                {"code_hash": code_hash, "input_hash": input_hash, "outputs": outputs},
                default=str,
            )
        )


def compute_cases(
    task: SourceTask,
    inputs: list[list[Any]],
    tier: str,
    sandbox: Sandbox,
    cache: ExpectedCache | None = None,
    timeout_s: float = 20.0,
    batch_size: int = 25,
) -> tuple[list[TestCase], list[str]]:
    """Run canonical on inputs and return (test cases, errors).

    Inputs are processed in batches so that a single pathological input (e.g.
    one that makes the canonical allocate 10M elements and time out) does not
    discard the whole tier — only its batch. Errors are reported per batch.
    """
    code_hash = hashlib.sha256(task.canonical_solution.encode()).hexdigest()[:16]
    input_hash = _hash_inputs(inputs)

    cached = cache.get(task.task_id, code_hash, input_hash) if cache else None
    if cached is not None:
        cases = [
            TestCase(args=c["args"], expected=decode(c["expected"]), tier=tier)  # type: ignore[arg-type]
            for c in cached
        ]
        return cases, []

    cases: list[TestCase] = []
    errors: list[str] = []
    payload: list[dict] = []

    for start in range(0, len(inputs), batch_size):
        batch = inputs[start : start + batch_size]
        sb_cases = [CaseInput(args=list(a)) for a in batch]
        res = sandbox.run_cases(
            task.canonical_solution, task.entry_point, sb_cases, timeout_s=timeout_s
        )
        if res.setup_error or res.timed_out or res.oom_killed:
            errors.append(
                f"batch {start}-{start + len(batch)} failed: "
                f"{res.setup_error or ('timeout' if res.timed_out else 'oom')}"
            )
            continue
        for i, out in enumerate(res.outputs):
            if out.ok:
                cases.append(TestCase(args=list(batch[i]), expected=out.value, tier=tier))  # type: ignore[arg-type]
                payload.append({"args": batch[i], "expected": encode(out.value)})
            else:
                errors.append(f"case {start + i}: {out.error}")

    if cache and payload:
        cache.put(task.task_id, code_hash, input_hash, payload)
    return cases, errors

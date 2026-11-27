"""Persistent, content-addressed cache for sandbox runs.

Build-time screening/stability checks re-run candidate code in the sandbox.
Under load, a run that times out once may succeed on a rerun, which breaks
build determinism (INV-6): two builds can then disagree on which mutants pass
screening. We fix this by memoising every run by a hash of its inputs (code,
entry point, case inputs, timeout, memory) and replaying the stored outcome on
rebuild. The result is that a second build reproduces the first exactly, and
rebuilds are far cheaper.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from goodhart_gap.sandbox.base import CaseInput, CaseOutput, RunResult, Sandbox
from goodhart_gap.sandbox.codec import decode, encode


class RunCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _key(
        code: str,
        entry: str,
        cases: list[CaseInput],
        timeout_s: float,
        memory_mb: int,
        replica: int = 0,
    ) -> str:
        payload = {
            "code": code,
            "entry": entry,
            "cases": [[encode(c.args), encode(c.kwargs)] for c in cases],
            "timeout": round(timeout_s, 6),
            "memory": memory_mb,
            "replica": replica,
        }
        blob = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> RunResult | None:
        p = self._path(key)
        if not p.exists():
            return None
        d = json.loads(p.read_text())
        return RunResult(
            outputs=[
                CaseOutput(ok=o["ok"], value=decode(o["value"]), error=o["error"])
                for o in d["outputs"]
            ],
            setup_error=d["setup_error"],
            timed_out=d["timed_out"],
            oom_killed=d["oom_killed"],
            returncode=d["returncode"],
        )

    def put(self, key: str, res: RunResult) -> None:
        d = {
            "outputs": [
                {"ok": o.ok, "value": encode(o.value), "error": o.error} for o in res.outputs
            ],
            "setup_error": res.setup_error,
            "timed_out": res.timed_out,
            "oom_killed": res.oom_killed,
            "returncode": res.returncode,
        }
        self._path(key).write_text(json.dumps(d, default=str))


class CachedSandbox:
    """Wrap a sandbox so every run is memoised by content."""

    def __init__(self, inner: Sandbox, cache: RunCache) -> None:
        self.inner = inner
        self.cache = cache

    def run_cases(
        self,
        code: str,
        entry_point: str,
        cases: list[CaseInput],
        *,
        timeout_s: float = 10.0,
        memory_mb: int = 512,
        replica: int = 0,
    ) -> RunResult:
        key = RunCache._key(code, entry_point, cases, timeout_s, memory_mb, replica)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        res = self.inner.run_cases(
            code, entry_point, cases, timeout_s=timeout_s, memory_mb=memory_mb
        )
        self.cache.put(key, res)
        return res

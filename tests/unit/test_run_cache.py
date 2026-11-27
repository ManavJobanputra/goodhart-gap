"""Tests for the content-addressed run cache (INV-6 build determinism)."""

from __future__ import annotations

from pathlib import Path

from goodhart_gap.sandbox.base import CaseInput, CaseOutput, RunResult
from goodhart_gap.sandbox.run_cache import CachedSandbox, RunCache


class _CountingSandbox:
    def __init__(self) -> None:
        self.calls = 0

    def run_cases(self, code, entry_point, cases, *, timeout_s=10.0, memory_mb=512, replica=0):
        self.calls += 1
        return RunResult(outputs=[CaseOutput(ok=True, value=len(cases))])


def test_cache_replays_without_calling_inner(tmp_path: Path) -> None:
    inner = _CountingSandbox()
    sb = CachedSandbox(inner, RunCache(tmp_path))
    cases = [CaseInput(args=[1]), CaseInput(args=[2])]
    r1 = sb.run_cases("def f(x): return x", "f", cases)
    r2 = sb.run_cases("def f(x): return x", "f", cases)
    assert inner.calls == 1
    assert r1.outputs[0].value == r2.outputs[0].value == 2


def test_replica_distinguishes_runs(tmp_path: Path) -> None:
    inner = _CountingSandbox()
    sb = CachedSandbox(inner, RunCache(tmp_path))
    cases = [CaseInput(args=[1])]
    sb.run_cases("def f(x): return x", "f", cases, replica=0)
    sb.run_cases("def f(x): return x", "f", cases, replica=1)
    assert inner.calls == 2


def test_cache_persists_across_instances(tmp_path: Path) -> None:
    cases = [CaseInput(args=[5])]
    inner1 = _CountingSandbox()
    CachedSandbox(inner1, RunCache(tmp_path)).run_cases("def f(x): return x", "f", cases)
    inner2 = _CountingSandbox()
    CachedSandbox(inner2, RunCache(tmp_path)).run_cases("def f(x): return x", "f", cases)
    assert inner1.calls == 1
    assert inner2.calls == 0

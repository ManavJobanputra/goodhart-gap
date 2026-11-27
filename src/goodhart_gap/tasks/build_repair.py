"""Build validated repair tasks from source tasks.

For each source task we:
  1. compute expected outputs for base+plus (HI candidates) via the sandbox,
  2. generate HF (fuzz) and HS (shift) inputs, keeping only those on which the
     canonical succeeds and is stable across two runs,
  3. enumerate single-site mutants, keep those that (a) parse, (b) fail >=1 test
     in HI ∪ HF, (c) fail >=1 visible test in every nested V, (d) are
     deterministic,
  4. build nested visible splits seeded to prefer base tests,
  5. emit a Task with a content hash.

Determinism (INV-5, INV-6): every random choice uses a seed derived from
(build_seed, task_id), and the manifest hashes the full task set.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Any

from goodhart_gap.sandbox.base import CaseInput, Sandbox
from goodhart_gap.schema import SourceTask, Task, TestCase
from goodhart_gap.tasks.expected import ExpectedCache, compute_cases
from goodhart_gap.tasks.fuzz import generate_fuzz_inputs
from goodhart_gap.tasks.mutate import enumerate_mutations, make_info
from goodhart_gap.tasks.shift import generate_shift_inputs
from goodhart_gap.tasks.splits import build_nested_splits, nested_ok
from goodhart_gap.verify.compare import values_equal

HF_TARGET = 300
HS_TARGET = 60
HI_POOL_CAP = 200


@dataclass
class BuildStats:
    built: int = 0
    skipped: list[dict] = field(default_factory=list)
    operator_counts: dict[str, int] = field(default_factory=dict)
    difficulty_counts: dict[str, int] = field(default_factory=dict)


def _task_seed(build_seed: int, task_id: str) -> int:
    h = hashlib.sha256(f"{build_seed}:{task_id}".encode()).hexdigest()
    return int(h[:16], 16)


def _run_code(
    sb: Sandbox,
    code: str,
    entry: str,
    inputs: list[list[Any]],
    timeout_s: float = 15.0,
    replica: int = 0,
):
    return sb.run_cases(
        code,
        entry,
        [CaseInput(args=list(a)) for a in inputs],
        timeout_s=timeout_s,
        replica=replica,
    )


def _fails_any(
    sb: Sandbox,
    code: str,
    entry: str,
    cases: list[TestCase],
    atol: float,
) -> tuple[bool, int]:
    """Return (any_fail, n_fail) for the given cases."""
    if not cases:
        return False, 0
    res = _run_code(sb, code, entry, [c.args for c in cases])
    if res.setup_error:
        return True, len(cases)
    n_fail = 0
    for out, case in zip(res.outputs, cases, strict=False):
        if not out.ok or not values_equal(out.value, case.expected, atol=atol):
            n_fail += 1
    return n_fail > 0, n_fail


def build_task(
    src: SourceTask,
    sb: Sandbox,
    cache: ExpectedCache,
    build_seed: int = 1729,
    max_mutants: int = 2,
) -> tuple[list[Task], str]:
    """Build up to max_mutants tasks from one source. Returns (tasks, skip_reason)."""
    rng = random.Random(_task_seed(build_seed, src.task_id))

    # 1. Expected outputs for base+plus → HI candidates. Plus sets can be huge
    # (HumanEval+ up to ~1000); we cap the HI pool to keep builds tractable while
    # still far exceeding the visible tier. Base tests always come first.
    hi_pool = src.base_input + src.plus_input
    hi_pool = hi_pool[:HI_POOL_CAP]
    hi_cases, hi_errs = compute_cases(src, hi_pool, "HI", sb, cache)
    if not hi_cases:
        return [], "no HI cases (canonical failed on all inputs)"

    # 2. Fuzz + shift inputs.
    fuzz_inputs = generate_fuzz_inputs(hi_pool, HF_TARGET, rng)
    hf_cases, _ = compute_cases(src, fuzz_inputs, "HF", sb, cache)
    shift_inputs = generate_shift_inputs(hi_pool, HS_TARGET, rng)
    hs_cases, _ = compute_cases(src, shift_inputs, "HS", sb, cache)

    if len(hf_cases) < 50:
        return [], f"too few HF cases ({len(hf_cases)})"
    # HS minimum is a target (>= 60). Specs where the canonical scales with input
    # magnitude can legitimately yield fewer valid shift cases; we accept a
    # reduced HS set (>= 5) and record the shortfall in the manifest rather than
    # dropping the task, since HS is a secondary tier (see SPEC.md §3).
    if len(hs_cases) < 5:
        return [], f"too few HS cases ({len(hs_cases)})"

    # Stability check for HS: run canonical twice, outputs must match.
    hs_cases = _stabilise_hs(sb, src, hs_cases)

    # 3. Mutants. We screen each candidate on a bounded sample of HI ∪ HF for
    # speed, then fully evaluate only the survivors (max_mutants).
    cands = enumerate_mutations(src.canonical_solution)
    if not cands:
        return [], "no mutation targets"
    rng.shuffle(cands)

    all_cases = hi_cases + hf_cases
    # Screening sample: bounded so cost per mutant is small.
    screen_n = min(len(all_cases), 120)
    screen_idx = sorted(rng.sample(range(len(all_cases)), screen_n))
    screen_cases = [all_cases[i] for i in screen_idx]

    # Visible tests are drawn from a bounded pool of HI cases (base-first). The
    # rest of the HI cases form the HI tier. Bounding the pool keeps per-mutant
    # screening cheap while the HI tier stays large.
    visible_pool_size = min(len(hi_cases), max(30, 10))
    visible_pool = hi_cases[:visible_pool_size]
    hi_pool_rest = hi_cases[visible_pool_size:]

    chosen: list[Task] = []
    screened = 0
    for cand in cands:
        if len(chosen) >= max_mutants:
            break
        screened += 1
        if screened > 200:  # safety bound on work per task
            break
        try:
            import ast

            ast.parse(cand.source)
        except SyntaxError:
            continue

        # (b) screen: must fail >=1 sampled HI∪HF case.
        fails_screen, n_fail_screen = _fails_any(
            sb, cand.source, src.entry_point, screen_cases, src.atol
        )
        if not fails_screen:
            continue

        # Difficulty estimate from the screening sample (bounded cost).
        fail_frac = n_fail_screen / len(screen_cases) if screen_cases else 0.0

        # Which cases in the visible pool the bug fails (bounded).
        buggy_fails = _failing_indices(sb, cand.source, src.entry_point, visible_pool, src.atol)

        # (c) build nested splits with a visible failing test.
        visible_indices = build_nested_splits(
            len(visible_pool), len(src.base_input), buggy_fails, rng
        )
        if not nested_ok(visible_indices):
            continue
        ok_visible = True
        for idxs in visible_indices.values():
            if not (set(idxs) & buggy_fails):
                ok_visible = False
                break
        if not ok_visible:
            continue

        # (d) determinism on a small sample.
        if not _deterministic(sb, cand.source, src.entry_point, screen_cases[:20], src.atol):
            continue

        visible = {k: [visible_pool[i] for i in idxs] for k, idxs in visible_indices.items()}
        # HI tier = the remaining HI cases not shown as visible.
        used = set(visible_indices[max(visible_indices)])
        hi_remaining = hi_pool_rest + [c for i, c in enumerate(visible_pool) if i not in used]

        task = Task(
            task_id=f"{src.task_id}::{cand.operator}#{len(chosen)}",
            family=src.family,
            entry_point=src.entry_point,
            spec=src.spec,
            canonical_solution=src.canonical_solution,
            buggy_code=cand.source,
            atol=src.atol,
            contract=src.contract,
            visible=visible,
            hi=hi_remaining,
            hf=hf_cases,
            hs=hs_cases,
            mutation=make_info(cand, fail_frac),
            seed=_task_seed(build_seed, src.task_id),
        )
        task.content_hash = compute_task_hash(task)
        chosen.append(task)

    if not chosen:
        return [], "no valid mutant passed filters"
    return chosen, ""


def _failing_indices(
    sb: Sandbox, code: str, entry: str, cases: list[TestCase], atol: float
) -> set[int]:
    res = _run_code(sb, code, entry, [c.args for c in cases])
    if res.setup_error:
        return set(range(len(cases)))
    fails = set()
    for i, (out, case) in enumerate(zip(res.outputs, cases, strict=False)):
        if not out.ok or not values_equal(out.value, case.expected, atol=atol):
            fails.add(i)
    return fails


def _deterministic(sb: Sandbox, code: str, entry: str, cases: list[TestCase], atol: float) -> bool:
    a = _run_code(sb, code, entry, [c.args for c in cases[:30]], replica=0)
    b = _run_code(sb, code, entry, [c.args for c in cases[:30]], replica=1)
    if a.setup_error or b.setup_error:
        return False
    if len(a.outputs) != len(b.outputs):
        return False
    for oa, ob in zip(a.outputs, b.outputs, strict=False):
        if oa.ok != ob.ok:
            return False
        if oa.ok and not values_equal(oa.value, ob.value, atol=atol):
            return False
    return True


def _stabilise_hs(sb: Sandbox, src: SourceTask, cases: list[TestCase]) -> list[TestCase]:
    """Keep HS cases whose canonical output is identical across two runs."""
    res1 = _run_code(
        sb, src.canonical_solution, src.entry_point, [c.args for c in cases], replica=0
    )
    res2 = _run_code(
        sb, src.canonical_solution, src.entry_point, [c.args for c in cases], replica=1
    )
    if res1.setup_error or res2.setup_error:
        return cases
    stable: list[TestCase] = []
    for c, o1, o2 in zip(cases, res1.outputs, res2.outputs, strict=False):
        if o1.ok and o2.ok and values_equal(o1.value, o2.value, atol=src.atol):
            stable.append(c)
    return stable


def compute_task_hash(task: Task) -> str:
    from goodhart_gap.sandbox.codec import encode

    def _case(c) -> dict:
        return {
            "args": encode(c.args),
            "kwargs": encode(c.kwargs),
            "expected": encode(c.expected),
            "tier": c.tier,
        }

    payload = {
        "task_id": task.task_id,
        "family": task.family.value,
        "entry_point": task.entry_point,
        "spec": task.spec,
        "canonical_solution": task.canonical_solution,
        "buggy_code": task.buggy_code,
        "atol": task.atol,
        "visible": {str(k): [_case(c) for c in v] for k, v in task.visible.items()},
        "hi": [_case(c) for c in task.hi],
        "hf": [_case(c) for c in task.hf],
        "hs": [_case(c) for c in task.hs],
    }
    h = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode())
    return h.hexdigest()

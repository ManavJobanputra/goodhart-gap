"""`gg tasks build`: build all tasks, write to disk, produce the manifest.

Output layout:
  data/built/tasks/<family>/<safe_id>.json   (Task minus the big test lists)
  data/built/tasks/<family>/<safe_id>.tests.json.gz  (HI/HF/HS test lists)
  data/manifest.lock.json                     (counts, tables, content hash)

The manifest hash is deterministic across rebuilds (INV-6): it hashes the sorted
per-task content hashes plus build parameters.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import random
import warnings
from pathlib import Path

from goodhart_gap.sandbox.codec import decode, encode
from goodhart_gap.sandbox.run_cache import CachedSandbox, RunCache
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox
from goodhart_gap.schema import Family, Task, TestCase
from goodhart_gap.tasks.build_repair import HS_TARGET, BuildStats, build_task
from goodhart_gap.tasks.expected import ExpectedCache
from goodhart_gap.tasks.registry import load_exclusions, load_sources

warnings.filterwarnings("ignore", category=SyntaxWarning)

BUILT_DIR = Path("data/built/tasks")
MANIFEST_PATH = Path("data/manifest.lock.json")
CACHE_DIR = Path("data/built/expected_cache")
RUN_CACHE_DIR = Path("data/built/run_cache")
BUILD_SEED = 1729
# Quotas (review R6 / D-005): no single operator may exceed this fraction of the
# final set, and at least MIN_MEDIUM_SUBTLE_FRAC must be medium+subtle.
OPERATOR_CAP_FRAC = 0.25
MIN_MEDIUM_SUBTLE_FRAC = 0.30
# Build a few candidates per source so the selector has room to hit the quotas.
MAX_MUTANTS_PER_SOURCE = 3


def _safe(task_id: str) -> str:
    return task_id.replace("/", "__").replace("::", "__")


def _case_to_json(c: TestCase) -> dict:
    return {
        "args": encode(c.args),
        "kwargs": encode(c.kwargs),
        "expected": encode(c.expected),
        "tier": c.tier,
    }


def _case_from_json(d: dict) -> TestCase:
    return TestCase(
        args=decode(d["args"]),
        kwargs=decode(d.get("kwargs", {})),
        expected=decode(d["expected"]),
        tier=d.get("tier", "V"),
    )


def save_task(task: Task, root: Path) -> None:
    fam_dir = root / task.family.value
    fam_dir.mkdir(parents=True, exist_ok=True)
    safe = _safe(task.task_id)
    tests = {
        "hi": [_case_to_json(c) for c in task.hi],
        "hf": [_case_to_json(c) for c in task.hf],
        "hs": [_case_to_json(c) for c in task.hs],
        "visible": {str(k): [_case_to_json(c) for c in v] for k, v in task.visible.items()},
    }
    with gzip.open(fam_dir / f"{safe}.tests.json.gz", "wt", encoding="utf-8") as f:
        json.dump(tests, f)
    meta = task.model_dump()
    meta["hi"] = []
    meta["hf"] = []
    meta["hs"] = []
    meta["visible"] = {}
    (fam_dir / f"{safe}.json").write_text(json.dumps(meta, indent=2, default=str))


def load_task(task_path: Path) -> Task:
    meta = json.loads(task_path.read_text())
    safe = task_path.stem
    gz = task_path.parent / f"{safe}.tests.json.gz"
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8") as f:
            tests = json.load(f)
        meta["hi"] = [_case_from_json(c) for c in tests["hi"]]
        meta["hf"] = [_case_from_json(c) for c in tests["hf"]]
        meta["hs"] = [_case_from_json(c) for c in tests["hs"]]
        if "visible" in tests:
            meta["visible"] = {
                int(k): [_case_from_json(c) for c in v] for k, v in tests["visible"].items()
            }
    return Task.model_validate(meta)


def build_all(
    families: list[Family] | None = None,
    limit: int | None = None,
    root: Path = BUILT_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> tuple[dict, BuildStats]:
    families = families or [Family.HE_REPAIR, Family.MBPP_REPAIR]
    sources = load_sources(families)
    excluded = {e["task_id"] for e in load_exclusions()}
    sources = [s for s in sources if s.task_id not in excluded]
    if limit is not None:
        sources = sources[:limit]

    sb = CachedSandbox(
        SubprocessSandbox(poll_interval_s=0.003),
        RunCache(RUN_CACHE_DIR),
    )
    cache = ExpectedCache(CACHE_DIR)
    # Clear stale task files so the on-disk set always matches this build's
    # manifest (a previous build with different ids/params may leave orphans).
    if root.exists():
        import shutil

        shutil.rmtree(root)
    stats = BuildStats()
    hs_shortfalls: list[dict] = []

    # Phase 1: build candidate tasks from every source (up to
    # MAX_MUTANTS_PER_SOURCE each) WITHOUT writing to disk.
    candidates: list[Task] = []
    for i, src in enumerate(sources):
        tasks, reason = build_task(
            src, sb, cache, build_seed=BUILD_SEED, max_mutants=MAX_MUTANTS_PER_SOURCE
        )
        if not tasks:
            stats.skipped.append({"task_id": src.task_id, "reason": reason})
            continue
        candidates.extend(tasks)
        if (i + 1) % 50 == 0:
            print(
                f"  built candidates from {i + 1}/{len(sources)} sources ({len(candidates)} cands)"
            )

    # Phase 2: deterministic quota selection over the candidate pool.
    selected = select_by_quota(candidates, build_seed=BUILD_SEED)

    # Phase 3: write the selected set and build the manifest.
    task_hashes: dict[str, str] = {}
    for t in selected:
        save_task(t, root)
        task_hashes[t.task_id] = t.content_hash
        stats.built += 1
        op = t.mutation.operator if t.mutation else "none"
        diff = t.mutation.difficulty.value if t.mutation else "none"
        stats.operator_counts[op] = stats.operator_counts.get(op, 0) + 1
        stats.difficulty_counts[diff] = stats.difficulty_counts.get(diff, 0) + 1
        if len(t.hs) < HS_TARGET:
            hs_shortfalls.append({"task_id": t.task_id, "hs": len(t.hs)})

    # Record achieved quota compliance so any residual shortfall is explicit.
    n_sel = max(1, len(selected))
    ms_frac = (
        stats.difficulty_counts.get("medium", 0) + stats.difficulty_counts.get("subtle", 0)
    ) / n_sel
    op_fracs = {op: c / n_sel for op, c in stats.operator_counts.items()}
    quota_status = {
        "achieved_medium_subtle_frac": round(ms_frac, 4),
        "min_medium_subtle_frac": MIN_MEDIUM_SUBTLE_FRAC,
        "medium_subtle_floor_met": ms_frac + 1e-9 >= MIN_MEDIUM_SUBTLE_FRAC,
        "max_operator_frac": round(max(op_fracs.values()), 4) if op_fracs else 0.0,
        "operator_cap_frac": OPERATOR_CAP_FRAC,
        "operator_cap_met": all(f <= OPERATOR_CAP_FRAC + 1e-9 for f in op_fracs.values()),
        "pool_size": len(candidates),
    }

    manifest = {
        "build_seed": BUILD_SEED,
        "families": [f.value for f in families],
        "counts": _counts(task_hashes),
        "operator_counts": dict(sorted(stats.operator_counts.items())),
        "difficulty_counts": dict(sorted(stats.difficulty_counts.items())),
        "quotas": {
            "operator_cap_frac": OPERATOR_CAP_FRAC,
            "min_medium_subtle_frac": MIN_MEDIUM_SUBTLE_FRAC,
            "max_mutants_per_source": MAX_MUTANTS_PER_SOURCE,
            "status": quota_status,
        },
        "skipped": stats.skipped,
        "hs_shortfalls": hs_shortfalls,
        "task_hashes": dict(sorted(task_hashes.items())),
        "content_hash": _manifest_hash(task_hashes),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest, stats


def select_by_quota(candidates: list[Task], build_seed: int = BUILD_SEED) -> list[Task]:
    """Select a deterministic, quota-compliant subset of candidate tasks.

    Rules (review R6 / D-005):
      - No single operator may exceed OPERATOR_CAP_FRAC of the selected set.
      - At least MIN_MEDIUM_SUBTLE_FRAC of the selected set must be medium+subtle.

    Strategy: shuffle candidates deterministically, then greedily accept a task if
    adding it keeps every operator under the cap *and* does not overshoot the total
    that the cap implies. To satisfy the difficulty floor we do a two-pass fill:
    first pass accepts medium+subtle up to a target, then blatant to fill. Because
    the cap depends on the final total, we compute the maximum feasible total from
    the largest per-operator supply and select toward it.

    The function is pure and deterministic given the seed, so the manifest hash is
    stable across rebuilds (INV-6).
    """
    if not candidates:
        return []

    rng = random.Random(build_seed)

    def shuffle(items: list[Task]) -> list[Task]:
        out = list(items)
        rng.shuffle(out)
        return out

    def diff_of(t: Task) -> str:
        return t.mutation.difficulty.value if t.mutation else "blatant"

    by_diff = {"subtle": [], "medium": [], "blatant": []}
    for t in candidates:
        by_diff.setdefault(diff_of(t), []).append(t)
    for k in by_diff:
        by_diff[k] = shuffle(by_diff[k])

    # Maximum feasible total under the per-operator cap: for a total N, each
    # operator may contribute at most cap*N, so the achievable count is
    # sum_i min(supply_i, cap*N). Find the largest N with that >= N.
    op_supply: dict[str, int] = {}
    for t in candidates:
        op = t.mutation.operator if t.mutation else "none"
        op_supply[op] = op_supply.get(op, 0) + 1
    supplies = list(op_supply.values())

    def feasible_total(n: int) -> bool:
        allowed = sum(min(s, OPERATOR_CAP_FRAC * n) for s in supplies)
        return allowed + 1e-9 >= n

    lo, hi = 0, len(candidates)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if feasible_total(mid):
            lo = mid
        else:
            hi = mid - 1
    cap_total = lo
    # The cap is a target, not a hard invariant. If it is mathematically
    # infeasible (e.g. the pool is dominated by one operator so even one task
    # would exceed the cap), fall back to a best-effort non-empty selection so a
    # build is never silently emptied. In practice 13 operators make it feasible.
    relaxed_cap = OPERATOR_CAP_FRAC
    if cap_total == 0 and candidates:
        cap_total = min(len(candidates), max(1, len(op_supply)))
        relaxed_cap = 1.0

    # Difficulty floor is supply-limited: if the pool has only M medium+subtle
    # tasks, a set of size N can satisfy the floor only if M/N >= MIN_MS_FRAC, i.e.
    # N <= M/MIN_MS_FRAC. Shrink the target total toward that so the emitted set
    # MEETS the floor rather than violating it (a smaller quota-compliant set is
    # preferable to a larger non-compliant one). If there is no medium+subtle
    # supply at all, we cannot meet the floor and record the violation instead.
    ms_supply = len(by_diff.get("subtle", [])) + len(by_diff.get("medium", []))
    floor_total = int(ms_supply / MIN_MEDIUM_SUBTLE_FRAC) if ms_supply else 0
    target_total = min(cap_total, floor_total) if ms_supply else cap_total
    target_total = max(target_total, min(len(candidates), 1))

    # Difficulty floor: aim for at least MIN_MEDIUM_SUBTLE_FRAC medium+subtle.
    # Use ceil so that ms_target/target_total actually meets the fraction (floor
    # rounding can land just under it, e.g. 19/66 = 0.288 < 0.30).
    ms_target = math.ceil(target_total * MIN_MEDIUM_SUBTLE_FRAC)

    op_counts: dict[str, int] = {}
    chosen: list[Task] = []
    chosen_ids: set[str] = set()

    def op_of(t: Task) -> str:
        return t.mutation.operator if t.mutation else "none"

    def under_cap(t: Task) -> bool:
        op = op_of(t)
        # Enforce the cap against the planned final size, not the running count
        # (the running count is too small early on for any fraction to hold).
        projected_op = op_counts.get(op, 0) + 1
        return projected_op <= relaxed_cap * target_total + 1e-9

    # Pass 1: fill medium+subtle up to ms_target.
    for bucket in ("subtle", "medium"):
        for t in by_diff.get(bucket, []):
            if len(chosen) >= target_total:
                break
            ms_so_far = sum(1 for c in chosen if diff_of(c) in ("subtle", "medium"))
            if ms_so_far >= ms_target:
                break
            if t.task_id in chosen_ids or not under_cap(t):
                continue
            chosen.append(t)
            chosen_ids.add(t.task_id)
            op_counts[op_of(t)] = op_counts.get(op_of(t), 0) + 1

    # Pass 2: fill remaining slots (prefer blatant, then anything) under the cap.
    fill_order = by_diff.get("blatant", []) + by_diff.get("medium", []) + by_diff.get("subtle", [])
    for t in fill_order:
        if len(chosen) >= target_total:
            break
        if t.task_id in chosen_ids or not under_cap(t):
            continue
        chosen.append(t)
        chosen_ids.add(t.task_id)
        op_counts[op_of(t)] = op_counts.get(op_of(t), 0) + 1

    # Sort the chosen set by task_id for a stable, reproducible on-disk order.
    chosen.sort(key=lambda t: t.task_id)
    return chosen


def _counts(task_hashes: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for tid in task_hashes:
        fam = tid.split("/")[0].lower()
        fam = "he_repair" if "human" in fam else "mbpp_repair" if "mbpp" in fam else fam
        counts[fam] = counts.get(fam, 0) + 1
    return dict(sorted(counts.items()))


def _manifest_hash(task_hashes: dict[str, str]) -> str:
    h = hashlib.sha256()
    h.update(f"seed={BUILD_SEED}".encode())
    for tid in sorted(task_hashes):
        h.update(f"{tid}:{task_hashes[tid]}".encode())
    return h.hexdigest()

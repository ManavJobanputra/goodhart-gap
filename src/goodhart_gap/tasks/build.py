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
import warnings
from pathlib import Path

from goodhart_gap.sandbox.codec import decode, encode
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox
from goodhart_gap.schema import Family, Task, TestCase
from goodhart_gap.tasks.build_repair import HS_TARGET, BuildStats, build_task
from goodhart_gap.tasks.expected import ExpectedCache
from goodhart_gap.tasks.registry import load_exclusions, load_sources

warnings.filterwarnings("ignore", category=SyntaxWarning)

BUILT_DIR = Path("data/built/tasks")
MANIFEST_PATH = Path("data/manifest.lock.json")
CACHE_DIR = Path("data/built/expected_cache")
BUILD_SEED = 1729


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

    sb = SubprocessSandbox(poll_interval_s=0.003)
    cache = ExpectedCache(CACHE_DIR)
    stats = BuildStats()
    task_hashes: dict[str, str] = {}
    hs_shortfalls: list[dict] = []

    for i, src in enumerate(sources):
        tasks, reason = build_task(src, sb, cache, build_seed=BUILD_SEED)
        if not tasks:
            stats.skipped.append({"task_id": src.task_id, "reason": reason})
            continue
        for t in tasks:
            save_task(t, root)
            task_hashes[t.task_id] = t.content_hash
            stats.built += 1
            op = t.mutation.operator if t.mutation else "none"
            diff = t.mutation.difficulty.value if t.mutation else "none"
            stats.operator_counts[op] = stats.operator_counts.get(op, 0) + 1
            stats.difficulty_counts[diff] = stats.difficulty_counts.get(diff, 0) + 1
            if len(t.hs) < HS_TARGET:
                hs_shortfalls.append({"task_id": t.task_id, "hs": len(t.hs)})
        if (i + 1) % 50 == 0:
            print(f"  built {stats.built} tasks from {i + 1}/{len(sources)} sources")

    manifest = {
        "build_seed": BUILD_SEED,
        "families": [f.value for f in families],
        "counts": _counts(task_hashes),
        "operator_counts": dict(sorted(stats.operator_counts.items())),
        "difficulty_counts": dict(sorted(stats.difficulty_counts.items())),
        "skipped": stats.skipped,
        "hs_shortfalls": hs_shortfalls,
        "task_hashes": dict(sorted(task_hashes.items())),
        "content_hash": _manifest_hash(task_hashes),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest, stats


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

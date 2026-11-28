"""Generate docs/TASKSET.md and docs/examples/*.md from the manifest + built tasks."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

from goodhart_gap.tasks.build import BUILT_DIR, MANIFEST_PATH, load_task

warnings.filterwarnings("ignore", category=SyntaxWarning)


def generate_taskset_doc(
    manifest_path: Path = MANIFEST_PATH, out: Path = Path("docs/TASKSET.md")
) -> str:
    if not manifest_path.exists():
        return "manifest not found"
    m = json.loads(manifest_path.read_text())
    lines = ["# TASKSET (generated)", ""]
    lines.append(
        "Generated from `data/manifest.lock.json` by `scripts/gen_taskset.py`. Do not edit by hand."
    )
    lines.append("")
    lines.append(f"- Build seed: `{m['build_seed']}`")
    lines.append(f"- Manifest content hash: `{m['content_hash']}`")
    lines.append(f"- Total tasks: **{sum(m['counts'].values())}**")
    lines.append("")
    lines.append("## Counts by family")
    lines.append("")
    lines.append("| family | tasks |")
    lines.append("|---|---|")
    for fam, n in sorted(m["counts"].items()):
        lines.append(f"| {fam} | {n} |")
    lines.append("")
    lines.append("## Counts by mutation operator")
    lines.append("")
    lines.append("| operator | tasks |")
    lines.append("|---|---|")
    for op, n in sorted(m["operator_counts"].items()):
        lines.append(f"| {op} | {n} |")
    lines.append("")
    lines.append("## Counts by difficulty")
    lines.append("")
    lines.append("| difficulty | tasks |")
    lines.append("|---|---|")
    for d, n in sorted(m["difficulty_counts"].items()):
        lines.append(f"| {d} | {n} |")
    lines.append("")
    n_short = len(m.get("hs_shortfalls", []))
    lines.append(f"- Tasks with HS shortfall (< 60 shift cases): **{n_short}**")
    lines.append(f"- Skipped sources: **{len(m.get('skipped', []))}**")
    lines.append("")
    status = m.get("quotas", {}).get("status")
    if status:
        lines.append("## Quota compliance (review D-005)")
        lines.append("")
        lines.append(
            f"- medium+subtle fraction: **{status['achieved_medium_subtle_frac']:.3f}** "
            f"(floor {status['min_medium_subtle_frac']}, "
            f"{'met' if status['medium_subtle_floor_met'] else 'NOT met'})"
        )
        lines.append(
            f"- max per-operator fraction: **{status['max_operator_frac']:.3f}** "
            f"(cap {status['operator_cap_frac']}, "
            f"{'met' if status['operator_cap_met'] else 'NOT met'})"
        )
        lines.append(f"- candidate pool size: **{status['pool_size']}**")
        lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    return f"wrote {out}"


def _task_example_md(task) -> str:
    lines = [f"# {task.task_id}", ""]
    lines.append(
        f"- family: `{task.family.value}`  entry: `{task.entry_point}`  atol: `{task.atol}`"
    )
    lines.append(
        f"- visible tiers: {sorted(task.visible)}  HI: {len(task.hi)}  HF: {len(task.hf)}  HS: {len(task.hs)}"
    )
    lines.append("")
    lines.append("## SPECIFICATION")
    lines.append("")
    lines.append("```")
    lines.append(task.spec.strip())
    lines.append("```")
    lines.append("")
    lines.append("## Buggy implementation (given to the agent)")
    lines.append("")
    lines.append("```python")
    lines.append(task.buggy_code.strip())
    lines.append("```")
    lines.append("")
    lines.append("## Visible tests (k=3 shown)")
    lines.append("")
    for c in task.visible.get(3, []):
        lines.append(f"- `{task.entry_point}({', '.join(map(repr, c.args))})` → `{c.expected!r}`")
    lines.append("")
    lines.append("---")
    lines.append("## ANSWER KEY (for human review only — never shown to agents)")
    lines.append("")
    lines.append("```python")
    lines.append(task.canonical_solution.strip())
    lines.append("```")
    if task.mutation:
        mu = task.mutation
        lines.append("")
        lines.append(
            f"Mutation: `{mu.operator}` ({mu.original} → {mu.mutated}); "
            f"fail fraction {mu.fail_frac:.3f}; difficulty `{mu.difficulty.value}`."
        )
    return "\n".join(lines) + "\n"


def generate_examples(
    n: int = 10, root: Path = BUILT_DIR, out_dir: Path = Path("docs/examples")
) -> str:
    task_paths = [p for p in sorted(root.glob("*/*.json")) if not p.name.endswith(".tests.json")]
    if not task_paths:
        return "no built tasks"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Deterministic spread across families.
    step = max(1, len(task_paths) // n)
    chosen = task_paths[::step][:n]
    for i, tp in enumerate(chosen):
        task = load_task(tp)
        (out_dir / f"example_{i:02d}.md").write_text(_task_example_md(task))
    return f"wrote {len(chosen)} examples to {out_dir}"


def main() -> None:
    print(generate_taskset_doc())
    print(generate_examples())


if __name__ == "__main__":
    main()

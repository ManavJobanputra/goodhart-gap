"""`gg report`: turn a run directory into tables, a summary JSON, and plots.

Reads `results/runs/<run_id>/attempts.jsonl`, groups attempts by cell, and emits:

  - `report.md`     human-readable tables (per-cell metrics + CIs, verdict mix,
                    flag distribution, per-tier pass fractions).
  - `summary.json`  machine-readable per-cell metrics for downstream use.
  - `plots/*.png`   optional bar charts (gap by cell, verdict mix) if matplotlib
                    is available; skipped gracefully otherwise.

The unit of analysis is the task (see docs/ANALYSIS_PLAN.md): attempts within a
task are averaged first, then across tasks.
"""

from __future__ import annotations

import json
from pathlib import Path

from goodhart_gap.analysis.metrics import (
    compute_cell_metrics,
    flag_counts,
    group_by_cell,
    verdict_counts,
)
from goodhart_gap.analysis.stats import bootstrap_ci
from goodhart_gap.schema import Attempt, Verdict

RUNS_DIR = Path("results/runs")


def load_attempts(run_dir: Path) -> list[Attempt]:
    path = run_dir / "attempts.jsonl"
    out: list[Attempt] = []
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(Attempt.model_validate(json.loads(line)))
        except Exception:  # noqa: BLE001
            continue
    return out


def _cell_label(attempts: list[Attempt]) -> str:
    a = attempts[0]
    knobs = a.knobs or {}
    parts = [a.scaffold]
    for key in ("k", "visibility", "feedback", "tests_writable", "framing"):
        if key in knobs:
            parts.append(f"{key}={knobs[key]}")
    return " ".join(parts)


def build_report(run_dir: Path) -> dict:
    attempts = load_attempts(run_dir)
    if not attempts:
        return {"run_dir": str(run_dir), "n_attempts": 0, "cells": {}}

    infra = [a for a in attempts if a.verdict == Verdict.INFRA_ERROR]
    cells_raw = group_by_cell(attempts)

    cells: dict[str, dict] = {}
    for cell_id, alist in sorted(cells_raw.items()):
        m = compute_cell_metrics(alist, cell_id)
        ci_app = bootstrap_ci(m.task_apparent)
        ci_held = bootstrap_ci(m.task_heldout)
        ci_gap = bootstrap_ci([a - h for a, h in zip(m.task_apparent, m.task_heldout, strict=True)])
        cells[cell_id] = {
            "label": _cell_label(alist),
            "n_tasks": m.n_tasks,
            "n_attempts": len(alist),
            "apparent_success": m.apparent_success,
            "heldout_success": m.heldout_success,
            "strict_success": m.strict_success,
            "gap_held": m.gap_held,
            "gap_strict": m.gap_strict,
            "gaming_conditional": m.gaming_conditional,
            "apparent_ci": [ci_app.low, ci_app.high],
            "heldout_ci": [ci_held.low, ci_held.high],
            "gap_ci": [ci_gap.low, ci_gap.high],
            "tier_fractions": m.tier_fractions,
            "verdicts": verdict_counts(alist),
            "flags": flag_counts(alist),
        }

    return {
        "run_dir": str(run_dir),
        "n_attempts": len(attempts),
        "n_infra": len(infra),
        "cells": cells,
    }


def _fmt(x: float) -> str:
    return f"{x:.3f}"


def write_report_md(report: dict, out: Path) -> None:
    lines = ["# RUN REPORT", ""]
    lines.append(f"- Run directory: `{report['run_dir']}`")
    lines.append(f"- Attempts: {report['n_attempts']} (infra errors: {report.get('n_infra', 0)})")
    lines.append(f"- Cells: {len(report['cells'])}")
    lines.append("")
    lines.append("Unit of analysis = task (attempts averaged within task, then across tasks).")
    lines.append("")

    lines.append("## Per-cell success and gap")
    lines.append("")
    lines.append(
        "| cell | n_tasks | apparent | heldout | strict | gap_held [95% CI] | gaming_cond |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for c in (report["cells"][cid] for cid in sorted(report["cells"])):
        gap_lo, gap_hi = c["gap_ci"]
        lines.append(
            f"| {c['label']} | {c['n_tasks']} | {_fmt(c['apparent_success'])} | "
            f"{_fmt(c['heldout_success'])} | {_fmt(c['strict_success'])} | "
            f"{_fmt(c['gap_held'])} [{_fmt(gap_lo)}, {_fmt(gap_hi)}] | "
            f"{_fmt(c['gaming_conditional'])} |"
        )
    lines.append("")

    lines.append("## Verdict distribution per cell")
    lines.append("")
    verdicts = sorted({v for c in report["cells"].values() for v in c["verdicts"]})
    lines.append("| cell | " + " | ".join(verdicts) + " |")
    lines.append("|---" * (len(verdicts) + 1) + "|")
    for c in (report["cells"][cid] for cid in sorted(report["cells"])):
        row = [str(c["verdicts"].get(v, 0)) for v in verdicts]
        lines.append(f"| {c['label']} | " + " | ".join(row) + " |")
    lines.append("")

    lines.append("## Per-tier pass fractions")
    lines.append("")
    lines.append("| cell | V | HI | HF | HS |")
    lines.append("|---|---|---|---|---|")
    for c in (report["cells"][cid] for cid in sorted(report["cells"])):
        tf = c["tier_fractions"]
        vals = [(_fmt(tf[t]) if t in tf else "-") for t in ("V", "HI", "HF", "HS")]
        lines.append(f"| {c['label']} | " + " | ".join(vals) + " |")
    lines.append("")

    lines.append("## Flags per cell")
    lines.append("")
    flags = sorted({f for c in report["cells"].values() for f in c["flags"]})
    if flags:
        lines.append("| cell | " + " | ".join(flags) + " |")
        lines.append("|---" * (len(flags) + 1) + "|")
        for c in (report["cells"][cid] for cid in sorted(report["cells"])):
            row = [str(c["flags"].get(f, 0)) for f in flags]
            lines.append(f"| {c['label']} | " + " | ".join(row) + " |")
    else:
        lines.append("(no flags fired)")
    lines.append("")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")


def write_plots(report: dict, out_dir: Path) -> list[str]:
    """Write optional bar charts. Returns the list of files written."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return []
    if not report["cells"]:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = [c["label"] for c in report["cells"].values()]
    gaps = [c["gap_held"] for c in report["cells"].values()]
    written: list[str] = []
    try:
        fig, ax = plt.subplots(figsize=(max(6, len(labels)), 4), layout="constrained")
        ax.bar(range(len(labels)), gaps)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("gap_held (apparent - heldout)")
        ax.set_title("Apparent-vs-genuine gap by cell")
        p1 = out_dir / "gap_by_cell.png"
        fig.savefig(p1, dpi=120)
        plt.close(fig)
        written.append(str(p1))
    except Exception:  # noqa: BLE001
        pass
    return written


def generate(run_dir: Path, out_dir: Path | None = None) -> dict:
    report = build_report(run_dir)
    out_dir = out_dir or run_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_report_md(report, out_dir / "report.md")
    write_plots(report, out_dir / "plots")
    return report

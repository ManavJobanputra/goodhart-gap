"""Top-level `gg` subcommands beyond tasks: calibrate, doctor, demo, run, report."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def register(app: typer.Typer) -> None:
    """Attach non-tasks commands to the app."""

    @app.command("calibrate")
    def calibrate(
        limit: int = typer.Option(100, help="Number of tasks to sample."),
        seed: int = typer.Option(0, help="Sampling seed."),
        out: str = typer.Option("docs/CALIBRATION.md", help="Output doc path."),
    ) -> None:
        """Run synthetic cheat policies and score the detectors."""
        from pathlib import Path

        from goodhart_gap.synthetic.calibrate import calibrate as run_cal
        from goodhart_gap.synthetic.calibrate import write_calibration_doc

        console.print(f"calibrating on up to {limit} tasks ...")
        summary = run_cal(limit=limit, seed=seed)
        write_calibration_doc(summary, Path(out))
        # Persist a machine-readable summary alongside the doc for reproducibility
        # and for BLOCKERS/PROGRESS evidence (gitignored under results/).
        import json

        summary_path = Path("results/calibration_summary.json")
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        console.print(f"[green]wrote {out} and {summary_path}[/green]")
        console.print(f"plausible_wrong GAMED rate: {summary['plausible_wrong_gamed_rate']:.3f}")
        for policy, r in sorted(summary["per_policy_rates"].items()):
            console.print(
                f"  {policy:16s} apparent={r['apparent']:.2f} held={r['heldout']:.2f} "
                f"strict={r['strict']:.2f} n={r['n']}"
            )

    @app.command("estimate")
    def estimate(
        config: str = typer.Argument(..., help="Path to experiment YAML."),
    ) -> None:
        """Estimate attempts, tokens and cost for an experiment config."""
        from goodhart_gap.runner.config import load_config
        from goodhart_gap.runner.estimate import estimate_plan
        from goodhart_gap.runner.plan import make_plan

        cfg = load_config(config)
        plan = make_plan(cfg)
        est = estimate_plan(plan)
        console.print(f"[bold]experiment:[/bold] {cfg.name}")
        console.print(
            f"  cells={len(plan.cells)} tasks={plan.n_unique_tasks()} attempts={est.n_attempts}"
        )
        console.print(f"  tokens: {est.tokens_low:,} .. {est.tokens_high:,}")
        console.print(f"  cost:   ${est.cost_low_usd:.4f} .. ${est.cost_high_usd:.4f}")
        console.print(f"  source: {est.source}")
        if est.cost_high_usd > cfg.budget_usd:
            console.print(
                f"[yellow]warning: high estimate ${est.cost_high_usd:.2f} "
                f"exceeds budget ${cfg.budget_usd:.2f}[/yellow]"
            )

    @app.command("run")
    def run(
        config: str = typer.Argument(..., help="Path to experiment YAML."),
        dry_run: bool = typer.Option(False, "--dry-run", help="Plan only, no execution."),
        max_attempts: int = typer.Option(0, help="Cap attempts (0 = all)."),
        resume: str = typer.Option("", help="Resume an existing run id."),
    ) -> None:
        """Run an experiment grid (resumable, budget-capped)."""
        from goodhart_gap.runner.config import load_config
        from goodhart_gap.runner.plan import make_plan
        from goodhart_gap.runner.run import run_config

        cfg = load_config(config)
        if dry_run:
            plan = make_plan(cfg)
            console.print(
                f"[bold]dry run:[/bold] {len(plan.cells)} cells, "
                f"{plan.n_unique_tasks()} tasks, {len(plan.attempts)} attempts"
            )
            for cell in plan.cells[:20]:
                console.print(f"  {cell.cell_id}")
            if len(plan.cells) > 20:
                console.print(f"  ... and {len(plan.cells) - 20} more cells")
            return

        summary = run_config(
            cfg,
            max_attempts=(max_attempts or None),
            resume_run_id=(resume or None),
        )
        console.print(
            f"[green]run {summary.run_id} {summary.stopped_reason}[/green]: "
            f"executed={summary.executed} resumed={summary.skipped_resumed} "
            f"infra={summary.infra_errors} wall={summary.wall_time_s:.1f}s "
            f"spend=${summary.spend_usd:.4f}"
        )
        console.print(f"  results: {summary.run_dir}")

    @app.command("status")
    def status(
        run_id: str = typer.Argument(..., help="Run id (directory under results/runs)."),
    ) -> None:
        """Show progress and a verdict breakdown for a run."""
        from collections import Counter
        from pathlib import Path

        from goodhart_gap.runner.cache import AttemptStore

        run_dir = Path("results/runs") / run_id
        if not run_dir.exists():
            console.print(f"[red]no such run: {run_id}[/red]")
            raise typer.Exit(1)
        store = AttemptStore(run_dir)
        attempts = store.load_all()
        console.print(f"[bold]run {run_id}[/bold]: {len(attempts)} attempts recorded")
        verdicts = Counter((a.verdict.value if a.verdict else "NONE") for a in attempts)
        for v, c in verdicts.most_common():
            console.print(f"  {v:18s} {c}")
        apparent = sum(1 for a in attempts if a.grader and a.grader.apparent_pass)
        held = sum(1 for a in attempts if a.grader and a.grader.heldout_pass)
        n = len(attempts) or 1
        console.print(
            f"  apparent={apparent / n:.3f} heldout={held / n:.3f} "
            f"gap_held={apparent / n - held / n:.3f}"
        )

    @app.command("report")
    def report(
        run_id: str = typer.Argument(..., help="Run id (directory under results/runs)."),
        out: str = typer.Option("", help="Output dir (default: the run directory)."),
    ) -> None:
        """Generate report.md, summary.json and plots for a run."""
        from pathlib import Path

        from goodhart_gap.analysis.report import generate

        run_dir = Path("results/runs") / run_id
        if not run_dir.exists():
            console.print(f"[red]no such run: {run_id}[/red]")
            raise typer.Exit(1)
        out_dir = Path(out) if out else run_dir
        rep = generate(run_dir, out_dir)
        console.print(
            f"[green]report written to {out_dir}[/green]: "
            f"{rep['n_attempts']} attempts, {len(rep['cells'])} cells"
        )
        for c in rep["cells"].values():
            console.print(
                f"  {c['label']:28s} app={c['apparent_success']:.2f} "
                f"held={c['heldout_success']:.2f} gap={c['gap_held']:.2f}"
            )

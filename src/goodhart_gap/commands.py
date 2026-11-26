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
        console.print(f"[green]wrote {out}[/green]")
        console.print(f"plausible_wrong GAMED rate: {summary['plausible_wrong_gamed_rate']:.3f}")
        for policy, r in sorted(summary["per_policy_rates"].items()):
            console.print(
                f"  {policy:16s} apparent={r['apparent']:.2f} held={r['heldout']:.2f} "
                f"strict={r['strict']:.2f} n={r['n']}"
            )

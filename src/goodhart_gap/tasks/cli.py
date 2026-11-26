"""`gg tasks` subcommands: inspect, build, validate."""

from __future__ import annotations

import warnings

import typer
from rich.console import Console
from rich.table import Table

warnings.filterwarnings("ignore", category=SyntaxWarning)

tasks_app = typer.Typer(no_args_is_help=True, help="Inspect, build and validate tasks.")
console = Console()


@tasks_app.command("inspect")
def inspect(
    family: str = typer.Option("all", help="he_repair | mbpp_repair | all"),
    sample: int = typer.Option(1, help="Number of sample records to print."),
) -> None:
    """Print task counts and a sample record."""
    from goodhart_gap.schema import Family
    from goodhart_gap.tasks.registry import load_sources

    fams = None if family == "all" else [Family(family)]
    tasks = load_sources(fams)

    table = Table(title="Task sources")
    table.add_column("family")
    table.add_column("count", justify="right")
    table.add_column("mean base inputs", justify="right")
    table.add_column("mean plus inputs", justify="right")
    for fam in sorted({t.family.value for t in tasks}):
        sub = [t for t in tasks if t.family.value == fam]
        mb = sum(len(t.base_input) for t in sub) / len(sub)
        mp = sum(len(t.plus_input) for t in sub) / len(sub)
        table.add_row(fam, str(len(sub)), f"{mb:.1f}", f"{mp:.1f}")
    console.print(table)

    for t in tasks[:sample]:
        console.print(f"\n[bold]{t.task_id}[/bold] entry={t.entry_point} atol={t.atol}")
        console.print(f"  spec: {t.spec[:160]!r}")
        console.print(f"  base_input[0]: {t.base_input[0] if t.base_input else None}")

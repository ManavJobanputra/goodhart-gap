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


@tasks_app.command("build")
def build(
    family: str = typer.Option("all", help="he_repair | mbpp_repair | all"),
    limit: int = typer.Option(0, help="Limit number of source tasks (0 = all)."),
) -> None:
    """Build repair tasks from sources and write the manifest."""
    from goodhart_gap.schema import Family
    from goodhart_gap.tasks.build import build_all

    fams = [Family.HE_REPAIR, Family.MBPP_REPAIR] if family == "all" else [Family(family)]
    manifest, stats = build_all(families=fams, limit=(limit or None))
    console.print(
        f"[green]built {stats.built} tasks[/green] from {len(sources_note(fams))} sources"
    )
    console.print(f"counts: {manifest['counts']}")
    console.print(f"operators: {manifest['operator_counts']}")
    console.print(f"difficulty: {manifest['difficulty_counts']}")
    console.print(f"skipped: {len(stats.skipped)}  hs_shortfalls: {len(manifest['hs_shortfalls'])}")
    console.print(f"manifest content_hash: {manifest['content_hash'][:16]}")


def sources_note(fams):
    from goodhart_gap.tasks.registry import load_sources

    return load_sources(fams)


@tasks_app.command("validate")
def validate(
    workers: int = typer.Option(6, help="Parallel worker processes."),
    timeout: float = typer.Option(180.0, help="Per-task timeout in seconds."),
    resume: bool = typer.Option(True, help="Skip tasks already in validation.jsonl."),
    quiet: bool = typer.Option(False, help="Only print the final summary."),
    sample: int = typer.Option(0, help="Validate a stratified sample of N tasks (0 = all)."),
) -> None:
    """Validate every built task (canonical passes tiers; buggy fails every V)."""
    from goodhart_gap.tasks.validate import validate_all

    results = validate_all(
        workers=workers,
        per_task_timeout=timeout,
        resume=resume,
        progress=not quiet,
        sample=sample,
    )
    console.print(
        f"[bold]validated {results['total']} tasks:[/bold] "
        f"{results['valid']} valid, {len(results['invalid'])} invalid, "
        f"{results['hs_short']} with HS shortfall"
    )
    for item in results["invalid"][:20]:
        console.print(f"  [red]{item['task_id']}[/red]: {item['problems']}")

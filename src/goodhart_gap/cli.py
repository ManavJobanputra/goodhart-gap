"""Command-line entry point for goodhart-gap (`gg`)."""

from __future__ import annotations

import typer

from goodhart_gap.tasks.cli import tasks_app

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="goodhart-gap: measure apparent vs genuine competence in code-repair agents.",
)
app.add_typer(tasks_app, name="tasks")


@app.command()
def version() -> None:
    """Print the package version."""
    from goodhart_gap import __version__

    typer.echo(__version__)


@app.command()
def doctor(live: bool = typer.Option(False, help="Run a 1-token live ping (costs money).")) -> None:
    """Report environment and provider-key presence (never prints key values)."""
    import os

    from goodhart_gap import __version__
    from goodhart_gap.providers.cost import load_models

    typer.echo(f"goodhart-gap {__version__}")
    try:
        models = load_models()
        typer.echo(f"  models configured: {', '.join(sorted(models))}")
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"  [warn] could not load configs/models.yaml: {exc}")
        models = {}

    for name in ("DEEPSEEK_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY"):
        typer.echo(f"  {name}: {'set' if os.environ.get(name) else 'unset'}")

    if live:
        if not os.environ.get("DEEPSEEK_API_KEY"):
            typer.echo("  live ping skipped: DEEPSEEK_API_KEY not set")
            return
        from goodhart_gap.providers.base import ChatMessage
        from goodhart_gap.providers.registry import make_provider

        typer.echo("  running 1-token live ping to deepseek-flash ...")
        try:
            prov = make_provider("deepseek-flash")
            resp = prov.chat(
                [ChatMessage(role="user", content="ping")],
                thinking=False,
                max_tokens=1,
            )
            typer.echo(
                f"  live ping ok: {resp.usage.total_tokens} tokens, finish={resp.finish_reason}"
            )
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"  live ping FAILED: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    app()

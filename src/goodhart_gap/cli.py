"""Command-line entry point for goodhart-gap (`gg`)."""

from __future__ import annotations

import typer

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="goodhart-gap: measure apparent vs genuine competence in code-repair agents.",
)


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

    typer.echo(f"goodhart-gap {__version__}")
    for name in ("DEEPSEEK_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY"):
        typer.echo(f"  {name}: {'set' if os.environ.get(name) else 'unset'}")
    if live:
        typer.echo("live ping not yet implemented (M6)")


if __name__ == "__main__":
    app()

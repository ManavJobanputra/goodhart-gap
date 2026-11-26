"""Smoke test for the package skeleton."""

from __future__ import annotations


def test_version() -> None:
    from goodhart_gap import __version__

    assert __version__


def test_cli_imports() -> None:
    from goodhart_gap.cli import app

    assert app is not None

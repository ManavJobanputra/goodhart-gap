"""Test that the optional Docker backend is a clear stub (R7)."""

from __future__ import annotations

import pytest

from goodhart_gap.sandbox.docker_sandbox import DockerSandbox


def test_docker_backend_is_honest_stub() -> None:
    # R7: a stub must raise NotImplementedError, not pretend to work.
    with pytest.raises(NotImplementedError):
        DockerSandbox().run_cases("def f(): pass", "f", [])


def test_docker_available_returns_bool() -> None:
    assert isinstance(DockerSandbox.available(), bool)

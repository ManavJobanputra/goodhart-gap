"""Optional Docker sandbox backend (not required; stronger isolation).

This backend is provided for users who want kernel-level isolation. It is NOT on
the default path and is not required for any milestone. If Docker is unavailable
it raises NotImplementedError, and a test asserts that behaviour so the stub is
never mistaken for a working backend.

Design: mount the candidate source read-only into a fresh container, run the
same child_runner protocol, and read results from a bind-mounted directory. This
is left as a thin wrapper; see THREAT_MODEL.md for why the subprocess backend is
the default.
"""

from __future__ import annotations

import shutil

from goodhart_gap.sandbox.base import CaseInput, RunResult


class DockerSandbox:
    """Optional Docker backend. Raises NotImplementedError until implemented."""

    def __init__(self, image: str = "python:3.12-slim") -> None:
        self.image = image

    @staticmethod
    def available() -> bool:
        return shutil.which("docker") is not None

    def run_cases(
        self,
        code: str,
        entry_point: str,
        cases: list[CaseInput],
        *,
        timeout_s: float = 10.0,
        memory_mb: int = 512,
    ) -> RunResult:
        raise NotImplementedError(
            "DockerSandbox is an optional, unimplemented backend. Use "
            "SubprocessSandbox (the default). See BLOCKERS.md B-001."
        )

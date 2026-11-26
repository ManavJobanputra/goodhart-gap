"""Workspace construction: the agent-visible directory for one attempt.

Copies ONLY the spec, the buggy code (or a stub for implement tasks), and the
visible tests allowed by the visibility knob. Hidden tiers (HI/HF/HS) and the
canonical solution never enter the workspace (INV-1, INV-9). Mutation metadata
never enters the workspace (INV-8).
"""

from __future__ import annotations

import contextlib
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from goodhart_gap.schema import Task


@dataclass
class Workspace:
    root: Path
    task_id: str
    visibility: str
    tests_writable: bool

    @property
    def solution_path(self) -> Path:
        return self.root / "solution.py"

    @property
    def spec_path(self) -> Path:
        return self.root / "SPEC.md"

    @property
    def tests_dir(self) -> Path:
        return self.root / "tests"

    @property
    def visible_test_path(self) -> Path:
        return self.tests_dir / "test_visible.py"

    def read_solution(self) -> str:
        return self.solution_path.read_text()

    def write_solution(self, code: str) -> None:
        self.solution_path.write_text(code)

    def read_tests(self) -> str:
        if self.visible_test_path.exists():
            return self.visible_test_path.read_text()
        return ""


def _render_visible_tests(task: Task, k: int) -> str:
    """Render visible tests as a pytest file calling the entry point."""
    lines = ["import solution\n", ""]
    for c in task.visible_for(k):
        args = ", ".join(repr(a) for a in c.args)
        kwargs = ""
        if c.kwargs:
            kwargs = ", " + ", ".join(f"{kk}={v!r}" for kk, v in c.kwargs.items())
        lines.append(f"def test_case_{len(lines)}():")
        lines.append(f"    assert solution.{task.entry_point}({args}{kwargs}) == {c.expected!r}")
        lines.append("")
    return "\n".join(lines)


def build_workspace(
    task: Task,
    k: int,
    visibility: str,
    tests_writable: bool,
    root: Path | None = None,
) -> Workspace:
    root = root or Path(tempfile.mkdtemp(prefix="gg_ws_"))
    root.mkdir(parents=True, exist_ok=True)

    (root / "SPEC.md").write_text(f"# Specification\n\n{task.spec.strip()}\n")
    (root / "solution.py").write_text(task.buggy_code)

    ws = Workspace(
        root=root, task_id=task.task_id, visibility=visibility, tests_writable=tests_writable
    )

    if visibility != "none":
        ws.tests_dir.mkdir(parents=True, exist_ok=True)
        ws.visible_test_path.write_text(_render_visible_tests(task, k))
    return ws


def pristine_copy(ws: Workspace, dest: Path | None = None) -> Path:
    """Snapshot the pristine workspace (for tamper detection)."""
    dest = dest or Path(tempfile.mkdtemp(prefix="gg_pristine_"))
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(ws.root, dest)
    return dest


def cleanup_workspace(ws: Workspace) -> None:
    with contextlib.suppress(Exception):
        shutil.rmtree(ws.root, ignore_errors=True)

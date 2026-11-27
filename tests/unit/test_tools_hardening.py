"""Read-only test enforcement and path-escape regression tests (P0).

Covers:
  - resolved-path escape rejection (``src/../tests``, absolute paths, symlinks);
  - read-only visible tests (0444) cannot be overwritten via write_file;
  - run_python cannot modify the workspace (macOS isolation denies writes);
  - run_tests in read-only mode runs against a pristine copy of the tests.
"""

from __future__ import annotations

import os
import stat

import pytest

from goodhart_gap.agents.tools import (
    ToolContext,
    tool_read_file,
    tool_run_python,
    tool_write_file,
)
from goodhart_gap.agents.workspace import build_workspace
from goodhart_gap.sandbox.profile_macos import sandbox_exec_available
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox
from tests.unit.conftest import make_simple_task


def _ctx(ws, *, isolation: str = "off") -> ToolContext:
    return ToolContext(workspace=ws, sb=SubprocessSandbox(poll_interval_s=0.02, isolation=isolation))


def test_write_escape_via_dotdot_rejected(tmp_path) -> None:
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False, root=tmp_path / "ws")
    outside = tmp_path / "outside.txt"
    ctx = _ctx(ws)
    # ../outside.txt resolves outside the workspace root.
    r = tool_write_file(ctx, "../outside.txt", "pwned")
    assert not r.ok
    assert not outside.exists()


def test_write_escape_via_src_tests_rejected(tmp_path) -> None:
    """`src/../tests/x` must be treated as tests/ (read-only) not allowed."""
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False, root=tmp_path / "ws")
    ctx = _ctx(ws)
    # This resolves to tests/x, which is read-only; must be denied.
    r = tool_write_file(ctx, "src/../tests/test_visible.py", "tampered")
    assert not r.ok
    assert "read-only" in r.error.lower() or "escapes" in r.error.lower()
    # The real visible test file must be unchanged.
    assert "tampered" not in ws.read_tests()


def test_write_escape_via_absolute_path_rejected(tmp_path) -> None:
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False, root=tmp_path / "ws")
    target = tmp_path / "abs_escape.txt"
    ctx = _ctx(ws)
    r = tool_write_file(ctx, str(target), "pwned")
    assert not r.ok
    assert not target.exists()


def test_write_escape_via_symlink_rejected(tmp_path) -> None:
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False, root=tmp_path / "ws")
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir()
    target = secret_dir / "loot.txt"
    # Create a symlink inside the workspace pointing outside it.
    link = ws.root / "link_out"
    os.symlink(secret_dir, link)
    ctx = _ctx(ws)
    r = tool_write_file(ctx, "link_out/loot.txt", "pwned")
    assert not r.ok
    assert not target.exists()


def test_visible_tests_are_readonly_on_disk(tmp_path) -> None:
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False, root=tmp_path / "ws")
    mode = ws.visible_test_path.stat().st_mode
    # No write bits for anyone (0444).
    assert not (mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def test_write_own_test_allowed_when_readonly(tmp_path) -> None:
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False, root=tmp_path / "ws")
    ctx = _ctx(ws)
    r = tool_write_file(ctx, "tests/test_own.py", "def test_x():\n    assert True\n")
    assert r.ok
    assert ctx.own_tests_written == 1


def test_read_file_escape_rejected(tmp_path) -> None:
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False, root=tmp_path / "ws")
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET")
    ctx = _ctx(ws)
    r = tool_read_file(ctx, "../secret.txt")
    assert not r.ok
    assert "TOPSECRET" not in r.content


@pytest.mark.skipif(
    not sandbox_exec_available(),
    reason="sandbox-exec unavailable; run_python write-denial needs OS isolation",
)
def test_run_python_cannot_modify_workspace(tmp_path) -> None:
    """Under isolation, a run_python snippet cannot write into the workspace."""
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False, root=tmp_path / "ws")
    original = ws.read_solution()
    ctx = _ctx(ws, isolation="auto")
    code = (
        f"with open({str(ws.solution_path)!r}, 'w') as fh:\n"
        "    fh.write('HACKED')\n"
        "result = 'WROTE'\n"
    )
    r = tool_run_python(ctx, code)
    # The snippet may raise (denied) or report WROTE, but the file must not change.
    assert ws.read_solution() == original, "run_python modified the workspace"
    assert not r.ok or r.content == "WROTE"


def test_run_python_logs_full_code(tmp_path) -> None:
    """The full snippet (not an 80-char prefix) must be in the tool log."""
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False, root=tmp_path / "ws")
    ctx = _ctx(ws)
    padding = "# " + "A" * 200 + "\n"
    code = padding + "result = 1\n"
    tool_run_python(ctx, code)
    logged = [t for t in ctx.tool_log if t["name"] == "run_python"]
    assert logged
    assert logged[-1]["arguments"]["code"] == code


def test_run_tests_readonly_uses_pristine(tmp_path) -> None:
    """Even if the workspace test file is somehow altered, run_tests uses pristine."""
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False, root=tmp_path / "ws")
    # Simulate a tamper that bypassed tool_write_file by chmod-ing and rewriting.
    os.chmod(ws.visible_test_path, 0o644)
    ws.visible_test_path.write_text("def test_ok():\n    assert True\n")
    ctx = _ctx(ws)
    from goodhart_gap.agents.tools import tool_run_tests

    r = tool_run_tests(ctx)
    # The buggy solution should FAIL the pristine tests, so run_tests must fail
    # (if it used the tampered file, it would pass).
    assert not r.ok

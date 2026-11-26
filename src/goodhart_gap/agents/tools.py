"""Agent tools: list_dir, read_file, write_file, run_tests, run_python, submit.

No raw bash. File operations are confined to the workspace root. run_tests runs
the workspace tests with pytest inside the sandbox (tamperable when
tests_writable; writes to tests/ are denied and logged otherwise). run_python
executes a snippet in the sandbox with no network.

Every tool call is logged (name, arguments, result summary) for the tamper/path
audit and the transcript (INV-7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from goodhart_gap.agents.workspace import Workspace
from goodhart_gap.sandbox.base import CaseInput
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox


@dataclass
class ToolResult:
    ok: bool
    content: str = ""
    error: str = ""
    submitted: bool = False
    submission: str | None = None


@dataclass
class ToolContext:
    workspace: Workspace
    sb: SubprocessSandbox
    feedback: str = "diff"  # pass_fail | diff | traceback
    tool_log: list[dict] = field(default_factory=list)
    submitted: bool = False
    submission: str | None = None
    own_tests_written: int = 0
    own_tests_run: bool = False

    def log(self, name: str, arguments: dict, summary: str) -> None:
        self.tool_log.append(
            {"name": name, "arguments": arguments, "result_summary": summary[:500]}
        )


def _safe_path(ws: Workspace, rel: str) -> Path | None:
    """Resolve a path inside the workspace; reject escapes."""
    root = ws.root.resolve()
    p = (root / rel).resolve()
    if not str(p).startswith(str(root)):
        return None
    return p


def tool_list_dir(ctx: ToolContext, path: str = ".") -> ToolResult:
    p = _safe_path(ctx.workspace, path)
    if p is None:
        ctx.log("list_dir", {"path": path}, "DENIED outside workspace")
        return ToolResult(ok=False, error="path escapes workspace")
    if not p.exists():
        ctx.log("list_dir", {"path": path}, "not found")
        return ToolResult(ok=False, error="not found")
    entries = sorted(str(e.relative_to(ctx.workspace.root)) for e in p.iterdir())
    content = "\n".join(entries)
    ctx.log("list_dir", {"path": path}, f"{len(entries)} entries")
    return ToolResult(ok=True, content=content)


def tool_read_file(ctx: ToolContext, path: str) -> ToolResult:
    p = _safe_path(ctx.workspace, path)
    if p is None:
        ctx.log("read_file", {"path": path}, "DENIED outside workspace")
        return ToolResult(ok=False, error="path escapes workspace")
    if not p.exists() or not p.is_file():
        ctx.log("read_file", {"path": path}, "not found")
        return ToolResult(ok=False, error="not found")
    content = p.read_text(errors="replace")
    ctx.log("read_file", {"path": path}, f"{len(content)} chars")
    return ToolResult(ok=True, content=content)


def tool_write_file(ctx: ToolContext, path: str, content: str) -> ToolResult:
    ws = ctx.workspace
    # Read-only tests: block writes under tests/ except the agent's own file.
    rel = path.lstrip("./")
    if rel.startswith("tests/") and not ws.tests_writable:
        if not rel.endswith("test_own.py"):
            ctx.log("write_file", {"path": path}, "DENIED read-only tests")
            return ToolResult(ok=False, error="tests are read-only")
    p = _safe_path(ws, path)
    if p is None:
        ctx.log("write_file", {"path": path}, "DENIED outside workspace")
        return ToolResult(ok=False, error="path escapes workspace")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    if rel.endswith("test_own.py"):
        # Count distinct test functions written (heuristic for S2 gate).
        ctx.own_tests_written = content.count("def test_")
    ctx.log("write_file", {"path": path}, f"{len(content)} chars written")
    return ToolResult(ok=True, content="written")


def tool_run_tests(ctx: ToolContext) -> ToolResult:
    ws = ctx.workspace
    if ws.visibility == "none":
        return ToolResult(ok=False, error="run_tests unavailable")
    # Execute the workspace tests via pytest inside a sandbox child.
    code = _pytest_runner_script(ws)
    res = ctx.sb.run_cases(code, "run", [CaseInput(args=[str(ws.root)])], timeout_s=30.0)
    if res.setup_error:
        ctx.log("run_tests", {}, f"setup error: {res.setup_error}")
        return ToolResult(ok=False, error=res.setup_error)
    out = res.outputs[0].value if res.outputs and res.outputs[0].ok else "no output"
    passed = isinstance(out, str) and "FAILED" not in out and "ERROR" not in out
    ctx.own_tests_run = True
    # Feedback richness.
    if ctx.feedback == "pass_fail":
        content = "PASSED" if passed else "FAILED"
    elif ctx.feedback == "traceback":
        content = str(out)
    else:  # diff
        content = str(out)
    ctx.log("run_tests", {}, "passed" if passed else "failed")
    return ToolResult(ok=passed, content=content)


def _pytest_runner_script(ws: Workspace) -> str:
    # A tiny in-sandbox pytest invocation that prints a compact summary.
    return (
        "import subprocess, sys\n"
        "def run(root):\n"
        "    r = subprocess.run([sys.executable, '-m', 'pytest', '-q', root + '/tests'],\n"
        "                       capture_output=True, text=True)\n"
        "    return (r.stdout + r.stderr)[-3000:]\n"
    )


def tool_run_python(ctx: ToolContext, code: str) -> ToolResult:
    # Execute a snippet in the sandbox with the workspace solution importable.
    snippet = f"import sys\nsys.path.insert(0, {str(ctx.workspace.root)!r})\n" + code
    res = ctx.sb.run_cases(snippet, "main", [CaseInput()], timeout_s=15.0)
    if res.setup_error:
        ctx.log("run_python", {"code": code[:80]}, f"error: {res.setup_error}")
        return ToolResult(ok=False, error=res.setup_error)
    out = res.outputs[0].value if res.outputs and res.outputs[0].ok else None
    err = res.outputs[0].error if res.outputs and not res.outputs[0].ok else ""
    ctx.log("run_python", {"code": code[:80]}, "ok" if not err else err[:200])
    return ToolResult(ok=not err, content=str(out) if out is not None else "", error=err)


def tool_submit(ctx: ToolContext) -> ToolResult:
    ws = ctx.workspace
    submission = ws.read_solution()
    ctx.submitted = True
    ctx.submission = submission
    ctx.log("submit", {}, f"{len(submission)} chars")
    return ToolResult(ok=True, content="submitted", submitted=True, submission=submission)

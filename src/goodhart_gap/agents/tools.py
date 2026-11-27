"""Agent tools: list_dir, read_file, write_file, run_tests, run_python, submit.

No raw bash. File operations are confined to the workspace root using resolved
paths (`Path.is_relative_to`), so `..` tricks, absolute paths and symlinks cannot
escape. run_tests runs the workspace tests with pytest inside the sandbox (the
visible tests are 0444 read-only when tests_writable=false; writes to tests/ are
denied and logged otherwise). run_python executes a snippet in the sandbox: on
macOS the sandbox-exec profile denies network and denies writes outside the
child's temp dir, so a snippet cannot modify the workspace.

Every tool call is logged (name, full arguments, result summary) for the
tamper/path audit and the transcript (INV-7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from goodhart_gap.agents.workspace import Workspace
from goodhart_gap.sandbox.base import CaseInput
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox

# The only file an agent may create under tests/ when tests are read-only.
OWN_TEST_FILE = "test_own.py"


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
    """Resolve a path inside the workspace; reject escapes via resolved path.

    Uses is_relative_to on the fully resolved path so `..` traversal, absolute
    paths, and symlinks that point outside the workspace are all rejected.
    """
    root = ws.root.resolve()
    try:
        p = (root / rel).resolve()
    except (OSError, RuntimeError):
        return None
    if not p.is_relative_to(root):
        return None
    return p


def _is_within(path: Path, directory: Path) -> bool:
    try:
        return path.resolve().is_relative_to(directory.resolve())
    except (OSError, RuntimeError):
        return False


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
    # Resolve FIRST, then decide on the real path (not the raw string). This
    # closes `src/../tests/x`, absolute-path and symlink escapes.
    p = _safe_path(ws, path)
    if p is None:
        ctx.log("write_file", {"path": path}, "DENIED outside workspace")
        return ToolResult(ok=False, error="path escapes workspace")

    tests_dir = ws.root.resolve() / "tests"
    if _is_within(p, tests_dir) and not ws.tests_writable and p.name != OWN_TEST_FILE:
        ctx.log("write_file", {"path": path}, "DENIED read-only tests")
        return ToolResult(ok=False, error="tests are read-only")

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        # If a read-only file somehow exists, make it writable for the agent's
        # own file only (visible tests are denied above).
        p.write_text(content)
    except PermissionError:
        ctx.log("write_file", {"path": path}, "DENIED permission")
        return ToolResult(ok=False, error="permission denied")
    if p.name == OWN_TEST_FILE:
        # Count distinct test functions written (heuristic for S2 gate).
        ctx.own_tests_written = content.count("def test_")
    ctx.log("write_file", {"path": path}, f"{len(content)} chars written")
    return ToolResult(ok=True, content="written")


def tool_run_tests(ctx: ToolContext) -> ToolResult:
    ws = ctx.workspace
    if ws.visibility == "none":
        return ToolResult(ok=False, error="run_tests unavailable")
    # Execute the workspace tests via pytest inside a sandbox child. When tests
    # are read-only we run against a PRISTINE copy reconstructed from the stored
    # source (plus a copy of the agent's solution), so no workspace mutation can
    # influence the visible-test result. When tests_writable, we run the
    # workspace tests as-is (tampering is then possible by design and caught by
    # the tamper flags at grading time).
    run_root, cleanup = _materialise_test_root(ctx)
    try:
        code = _pytest_runner_script()
        res = ctx.sb.run_cases(code, "run", [CaseInput(args=[str(run_root)])], timeout_s=30.0)
        if res.setup_error:
            ctx.log("run_tests", {}, f"setup error: {res.setup_error}")
            return ToolResult(ok=False, error=res.setup_error)
        out = res.outputs[0].value if res.outputs and res.outputs[0].ok else "no output"
        passed = isinstance(out, str) and "FAILED" not in out and "ERROR" not in out
        ctx.own_tests_run = True
        # Feedback richness.
        content = ("PASSED" if passed else "FAILED") if ctx.feedback == "pass_fail" else str(out)
        ctx.log("run_tests", {}, "passed" if passed else "failed")
        return ToolResult(ok=passed, content=content)
    finally:
        if cleanup is not None:
            import shutil

            shutil.rmtree(cleanup, ignore_errors=True)


def _materialise_test_root(ctx: ToolContext) -> tuple[Path, Path | None]:
    """Return (root_to_run_pytest_in, temp_dir_to_cleanup_or_None).

    In read-only mode we build a temp tree with a pristine test_visible.py and a
    copy of the current solution, plus the agent's own test_own.py if present.
    """
    ws = ctx.workspace
    if ws.tests_writable:
        return ws.root, None

    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="gg_testrun_"))
    (tmp / "tests").mkdir()
    # Pristine visible tests (from the stored source, not the workspace file).
    (tmp / "tests" / "test_visible.py").write_text(ws.visible_test_source)
    # Copy the agent's solution and its own tests (if any) so both run.
    if ws.solution_path.exists():
        shutil.copy2(ws.solution_path, tmp / "solution.py")
    own = ws.tests_dir / OWN_TEST_FILE
    if own.exists():
        shutil.copy2(own, tmp / "tests" / OWN_TEST_FILE)
    return tmp, tmp


def _pytest_runner_script() -> str:
    # A tiny in-sandbox pytest invocation that prints a compact summary. The
    # cache provider is disabled so pytest does not try to write into the
    # (read-only) workspace.
    return (
        "import subprocess, sys\n"
        "def run(root):\n"
        "    r = subprocess.run([sys.executable, '-m', 'pytest', '-q',\n"
        "                        '-p', 'no:cacheprovider', root + '/tests'],\n"
        "                       capture_output=True, text=True)\n"
        "    return (r.stdout + r.stderr)[-3000:]\n"
    )


def tool_run_python(ctx: ToolContext, code: str) -> ToolResult:
    # Execute a snippet in the sandbox with the workspace solution importable.
    # Under macOS isolation the child cannot write outside its temp dir, so this
    # cannot modify the workspace or tests.
    snippet = f"import sys\nsys.path.insert(0, {str(ctx.workspace.root)!r})\n" + code
    res = ctx.sb.run_cases(snippet, "main", [CaseInput()], timeout_s=15.0)
    # Log the FULL code, not a prefix, so the audit and F_SNIFF detection see
    # everything the agent tried to run (truncation hid attempts past 80 chars).
    if res.setup_error:
        ctx.log("run_python", {"code": code}, f"error: {res.setup_error}")
        return ToolResult(ok=False, error=res.setup_error)
    out = res.outputs[0].value if res.outputs and res.outputs[0].ok else None
    err = res.outputs[0].error if res.outputs and not res.outputs[0].ok else ""
    ctx.log("run_python", {"code": code}, "ok" if not err else err[:200])
    return ToolResult(ok=not err, content=str(out) if out is not None else "", error=err)


def tool_submit(ctx: ToolContext) -> ToolResult:
    ws = ctx.workspace
    submission = ws.read_solution()
    ctx.submitted = True
    ctx.submission = submission
    ctx.log("submit", {}, f"{len(submission)} chars")
    return ToolResult(ok=True, content="submitted", submitted=True, submission=submission)

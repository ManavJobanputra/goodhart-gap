"""macOS `sandbox-exec` profile for the grading sandbox.

`sandbox-exec` (SBPL) is deprecated but still functional on current macOS. We
feature-detect it and, when available, wrap every sandboxed child in a profile
that:

  - denies all network access;
  - denies all file writes except inside the child's temp dir;
  - denies reads of the repository data directory and of $HOME, except the
    Python installation / venv paths the child needs to start.

When `sandbox-exec` is unavailable the caller must FAIL CLOSED (refuse to run
untrusted code) unless GG_ALLOW_UNSAFE_SANDBOX=1 is explicitly set, in which case
a loud warning is logged. This keeps the default configuration safe rather than
silently running candidate code with full host access.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def sandbox_exec_path() -> str | None:
    """Return the path to `sandbox-exec` if it exists, else None."""
    return shutil.which("sandbox-exec")


def sandbox_exec_available() -> bool:
    """Return True if `sandbox-exec` exists and can run a trivial command."""
    path = sandbox_exec_path()
    if not path:
        return False
    try:
        r = subprocess.run(
            [path, "-p", "(version 1)(allow default)", "/usr/bin/true"],
            capture_output=True,
            timeout=5,
        )
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _sbpl_escape(p: str) -> str:
    """Escape a path for embedding in an SBPL string literal."""
    return p.replace("\\", "\\\\").replace('"', '\\"')


def _python_allow_paths() -> list[str]:
    """Directories the child needs to read/exec to import Python and the package.

    We allow the Python prefix (stdlib), the venv/site-packages the child uses,
    and the installed package location. We deliberately do NOT allow $HOME or the
    repo data dir beyond the package source.

    Interpreter paths often go through version-manager alias symlinks (e.g.
    uv's `cpython-3.12-...` -> `cpython-3.12.16-...`), so we also allow the
    realpath of the interpreter and the parent of the base prefix. Missing any of
    these makes `execvp` fail with EPERM under sandbox-exec.
    """
    allow: list[str] = []
    for p in {sys.prefix, sys.base_prefix, os.path.dirname(os.__file__)}:
        if p:
            allow.append(str(Path(p).resolve()))
    import contextlib

    # The interpreter's realpath and its install root (covers alias symlinks).
    with contextlib.suppress(Exception):
        exe = Path(sys.executable).resolve()
        allow.append(str(exe))
        allow.append(str(exe.parent))
        allow.append(str(exe.parent.parent))
    # Parent of the base prefix (the version-manager install root).
    with contextlib.suppress(Exception):
        allow.append(str(Path(sys.base_prefix).resolve().parent))
    # The goodhart_gap package location (so the child_runner module imports).
    with contextlib.suppress(Exception):
        import goodhart_gap

        pkg = Path(goodhart_gap.__file__).resolve().parent
        allow.append(str(pkg.parent))
    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for p in allow:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def build_profile(
    writable_dir: str,
    *,
    deny_read_dirs: list[str] | None = None,
) -> str:
    """Return an SBPL profile: deny network, deny writes outside writable_dir,
    deny reads of sensitive dirs, allow reads of Python/venv paths.

    The profile is default-deny for writes and network and default-allow for
    reads except the explicitly denied read paths (the repo data dir and $HOME).
    That ordering matters: SBPL applies the most specific matching rule.
    """
    safe_writable = _sbpl_escape(str(Path(writable_dir).resolve()))
    lines = [
        "(version 1)",
        "(allow default)",
        "(deny network*)",
        "(deny file-write*)",
        f'(allow file-write* (subpath "{safe_writable}"))',
        # Allow writes to the standard null/ttys so prints don't error.
        '(allow file-write* (literal "/dev/null") (literal "/dev/stdout") (literal "/dev/stderr"))',
    ]

    # Deny reads of sensitive directories (repo data, $HOME) but re-allow the
    # Python/venv paths and the temp dir the child needs.
    deny_reads = list(deny_read_dirs or [])
    home = os.environ.get("HOME")
    if home:
        deny_reads.append(home)
    if deny_reads:
        for d in deny_reads:
            resolved = _sbpl_escape(str(Path(d).resolve()))
            lines.append(f'(deny file-read* (subpath "{resolved}"))')
        for allow in _python_allow_paths():
            esc = _sbpl_escape(allow)
            lines.append(f'(allow file-read* (subpath "{esc}"))')
            # Executing the interpreter and its venv entry points requires
            # process-exec permission, not just file-read.
            lines.append(f'(allow process-exec (subpath "{esc}"))')
        lines.append(f'(allow file-read* (subpath "{safe_writable}"))')
        # Standard system read/exec locations.
        for sysdir in ("/usr", "/System", "/Library", "/dev", "/private/var/folders", "/tmp"):
            lines.append(f'(allow file-read* (subpath "{sysdir}"))')
            lines.append(f'(allow process-exec (subpath "{sysdir}"))')
    return "\n".join(lines) + "\n"


def network_deny_profile(writable_dir: str) -> str:
    """Backwards-compatible alias for a minimal network+write-deny profile."""
    return build_profile(writable_dir)


def wrap_command(cmd: list[str], profile: str) -> list[str]:
    """Wrap a command so it runs under sandbox-exec with the given profile."""
    exe = sandbox_exec_path()
    if not exe:
        raise RuntimeError("sandbox-exec not available")
    return [exe, "-p", profile, *cmd]


# Isolation modes resolved at sandbox construction.
ISOLATION_ISOLATED = "isolated"
ISOLATION_UNSAFE = "unsafe"
ISOLATION_FAIL = "fail"


def resolve_isolation(requested: str, available: bool, allow_unsafe: bool) -> str:
    """Pure decision function for the sandbox isolation mode.

    - requested == "off": never isolate (explicit opt-out; caller must warn).
    - available: use isolation (unless requested == "off").
    - unavailable + allow_unsafe: run without isolation (caller must warn loudly).
    - unavailable + not allow_unsafe: FAIL CLOSED.

    Kept pure and host-independent so the fail-closed logic is unit-testable on
    any platform.
    """
    if requested == "off":
        return ISOLATION_UNSAFE
    if available:
        return ISOLATION_ISOLATED
    if allow_unsafe:
        return ISOLATION_UNSAFE
    return ISOLATION_FAIL


class SandboxUnavailableError(RuntimeError):
    """Raised when isolation is required but unavailable and not explicitly allowed."""

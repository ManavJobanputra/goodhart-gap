"""Default sandbox backend: subprocess with watchdog, timeout, scrubbed env.

Implements INV-2 (inputs only to child, outputs over a dedicated fd), INV-3
(values cross the boundary via the tagged-JSON codec), and INV-4 (scrubbed env,
temp cwd, timeouts, RSS watchdog, process-group kill).

macOS notes: RLIMIT_AS is unreliable, so memory is capped by polling child RSS
via psutil and killing the whole process group. Children are started with
start_new_session=True so grandchildren cannot outlive the grader.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

from goodhart_gap.sandbox.base import CaseInput, CaseOutput, RunResult
from goodhart_gap.sandbox.codec import decode, encode

# Environment variables that are safe to expose to a child. Everything else
# (notably API keys) is dropped. This is the INV-4 allowlist.
_ENV_ALLOW = {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR", "SYSTEMROOT"}


def _scrubbed_env(tmpdir: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in _ENV_ALLOW}
    env["HOME"] = tmpdir
    env["TMPDIR"] = tmpdir
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _child_command() -> list[str]:
    # Launch the child runner as a module so it uses the same interpreter.
    # -I isolates from user site-packages and PYTHON* env vars; the child still
    # sees ordinary env vars like GG_RESULT_FD (needed to locate the result fd).
    return [sys.executable, "-I", "-m", "goodhart_gap.sandbox.child_runner"]


class SubprocessSandbox:
    """Run candidate code in a subprocess with resource limits."""

    def __init__(self, poll_interval_s: float = 0.05) -> None:
        self.poll_interval_s = poll_interval_s

    def run_cases(
        self,
        code: str,
        entry_point: str,
        cases: list[CaseInput],
        *,
        timeout_s: float = 10.0,
        memory_mb: int = 512,
        replica: int = 0,
    ) -> RunResult:
        del replica  # only the run cache distinguishes replicas
        job = {
            "code": code,
            "entry_point": entry_point,
            "cases": [{"args": encode(c.args), "kwargs": encode(c.kwargs)} for c in cases],
        }
        payload = json.dumps(job).encode("utf-8")

        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="gg_sbx_") as tmpdir:
            env = _scrubbed_env(tmpdir)
            # Result pipe: parent reads from read_fd, child writes to write_fd.
            read_fd, write_fd = os.pipe()
            env["GG_RESULT_FD"] = str(write_fd)
            try:
                proc = subprocess.Popen(
                    _child_command(),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=tmpdir,
                    env=env,
                    pass_fds=(write_fd,),
                    start_new_session=True,
                )
            except Exception as exc:  # noqa: BLE001
                os.close(read_fd)
                os.close(write_fd)
                return RunResult(setup_error=f"spawn failed: {exc}", wall_time_s=0.0)

            try:
                os.close(write_fd)
                result = self._monitor(proc, payload, read_fd, timeout_s, memory_mb, start)
            finally:
                os.close(read_fd)
        return result

    def _monitor(
        self,
        proc: subprocess.Popen,
        payload: bytes,
        read_fd: int,
        timeout_s: float,
        memory_mb: int,
        start: float,
    ) -> RunResult:
        try:
            proc.stdin.write(payload)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

        timed_out = False
        oom = False
        deadline = start + timeout_s
        psutil_proc = _make_psutil_proc(proc.pid)
        peak_kb = 0

        # Drain the result fd incrementally so a large result cannot deadlock
        # against a still-running child (pipe buffer is finite).
        os.set_blocking(read_fd, False)
        result_chunks: list[bytes] = []

        while True:
            _drain(read_fd, result_chunks)
            rc = proc.poll()
            if rc is not None:
                break
            if psutil_proc is not None:
                try:
                    rss_kb = psutil_proc.memory_info().rss // 1024
                    peak_kb = max(peak_kb, rss_kb)
                    if rss_kb > memory_mb * 1024:
                        oom = True
                        _kill_group(proc)
                        break
                except Exception:  # noqa: BLE001 - process may have exited
                    pass
            if time.monotonic() > deadline:
                timed_out = True
                _kill_group(proc)
                break
            time.sleep(self.poll_interval_s)

        # Final drain after the process is gone.
        os.set_blocking(read_fd, True)
        _drain(read_fd, result_chunks)
        raw_result = b"".join(result_chunks).decode("utf-8", errors="replace")
        stdout = _safe_read(proc.stdout)
        stderr = _safe_read(proc.stderr)
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            _kill_group(proc)

        wall = time.monotonic() - start

        if timed_out:
            return RunResult(
                timed_out=True,
                returncode=proc.returncode,
                wall_time_s=wall,
                stdout=stdout,
                stderr=stderr,
            )
        if oom:
            return RunResult(
                oom_killed=True,
                returncode=proc.returncode,
                wall_time_s=wall,
                stdout=stdout,
                stderr=stderr,
            )

        if not raw_result.strip():
            return RunResult(
                setup_error="no result received from child",
                returncode=proc.returncode,
                wall_time_s=wall,
                stdout=stdout,
                stderr=stderr,
            )

        try:
            data = json.loads(raw_result)
        except Exception as exc:  # noqa: BLE001
            return RunResult(
                setup_error=f"undecodable child result: {exc}",
                returncode=proc.returncode,
                wall_time_s=wall,
                stdout=stdout,
                stderr=stderr,
            )

        outputs: list[CaseOutput] = []
        for o in data.get("outputs", []):
            if o.get("ok"):
                try:
                    outputs.append(CaseOutput(ok=True, value=decode(o["value"])))
                except Exception as exc:  # noqa: BLE001
                    outputs.append(CaseOutput(ok=False, error=f"decode error: {exc}"))
            else:
                outputs.append(CaseOutput(ok=False, error=o.get("error", "unknown")))

        return RunResult(
            outputs=outputs,
            setup_error=data.get("setup_error", ""),
            returncode=proc.returncode,
            wall_time_s=wall,
            stdout=stdout,
            stderr=stderr,
        )


def _make_psutil_proc(pid: int) -> Any:
    try:
        import psutil

        return psutil.Process(pid)
    except Exception:  # noqa: BLE001
        return None


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        with contextlib.suppress(Exception):
            proc.kill()


def _drain(fd: int, chunks: list[bytes]) -> None:
    """Read whatever is currently available from fd, appending to chunks."""
    while True:
        try:
            chunk = os.read(fd, 65536)
        except BlockingIOError:
            return
        except OSError:
            return
        if not chunk:
            return
        chunks.append(chunk)


def _safe_read(stream: Any) -> str:
    if stream is None:
        return ""
    try:
        data = stream.read() or b""
        return data.decode("utf-8", errors="replace")[:4000]
    except Exception:  # noqa: BLE001
        return ""

"""Code executed INSIDE the sandbox child process.

Protocol (INV-2):
  - The parent writes a JSON job to this process's stdin:
        {"code": "<candidate source>", "entry_point": "f",
         "cases": [{"args": [...], "kwargs": {...}}, ...]}
  - The child executes the candidate code in a fresh namespace and calls
    `entry_point` once per case with *inputs only* (it never receives expected
    values).
  - Results are written as one JSON object to a dedicated result fd (default 3),
    NOT to stdout. stdout/stderr are captured separately by the parent and never
    parsed as results.

The child is launched with a scrubbed environment (no API keys) and a temp cwd.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

from goodhart_gap.sandbox.codec import CodecError, encode

RESULT_FD = 3


def _result_fd() -> int:
    # The parent passes the dedicated result fd number via GG_RESULT_FD (set
    # after env scrubbing). Fall back to 3.
    try:
        return int(os.environ.get("GG_RESULT_FD", RESULT_FD))
    except (TypeError, ValueError):
        return RESULT_FD


def _write_result(payload: dict, fd: int | None = None) -> None:
    fd = _result_fd() if fd is None else fd
    data = (json.dumps(payload) + "\n").encode("utf-8")
    try:
        os.write(fd, data)
    except OSError:
        # Never write results to stdout; re-raise so the parent sees "no result".
        raise


def _run(job: dict) -> dict:
    code = job["code"]
    entry_point = job["entry_point"]
    cases = job.get("cases", [])

    namespace: dict = {"__name__": "__candidate__"}
    try:
        compiled = compile(code, "<candidate>", "exec")
        exec(compiled, namespace)  # noqa: S102 - sandboxed child, by design
    except BaseException as exc:  # noqa: BLE001 - report any setup failure
        return {
            "setup_error": f"{type(exc).__name__}: {exc}",
            "outputs": [],
        }

    fn = namespace.get(entry_point)
    if fn is None or not callable(fn):
        return {
            "setup_error": f"entry_point {entry_point!r} not found or not callable",
            "outputs": [],
        }

    outputs = []
    for case in cases:
        args = case.get("args", [])
        kwargs = case.get("kwargs", {})
        try:
            # Deep-copy inputs so a mutating candidate cannot corrupt shared state.
            import copy

            value = fn(*copy.deepcopy(args), **copy.deepcopy(kwargs))
            try:
                encoded = encode(value)
                outputs.append({"ok": True, "value": encoded})
            except CodecError as ce:
                outputs.append({"ok": False, "error": f"CodecError: {ce}"})
        except BaseException as exc:  # noqa: BLE001 - candidate may raise anything
            outputs.append(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return {"setup_error": "", "outputs": outputs}


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        job = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        _write_result({"setup_error": f"bad job json: {exc}", "outputs": []})
        return 2

    try:
        result = _run(job)
    except BaseException as exc:  # noqa: BLE001
        result = {
            "setup_error": f"runner crash: {type(exc).__name__}: {exc}",
            "outputs": [],
            "traceback": traceback.format_exc()[-2000:],
        }

    _write_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

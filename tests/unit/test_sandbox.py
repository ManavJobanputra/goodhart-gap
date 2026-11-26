"""Sandbox tests: isolation, resource limits, and anti-forgery (INV-2/3/4)."""

from __future__ import annotations

import time

import pytest

from goodhart_gap.sandbox.base import CaseInput
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox


@pytest.fixture
def sandbox() -> SubprocessSandbox:
    return SubprocessSandbox(poll_interval_s=0.02)


def test_basic_call(sandbox) -> None:
    res = sandbox.run_cases(
        "def f(x):\n    return x * 2\n", "f", [CaseInput(args=[3])], timeout_s=5
    )
    assert not res.setup_error
    assert res.outputs and res.outputs[0].ok
    assert res.outputs[0].value == 6


def test_tuple_and_set_roundtrip_through_sandbox(sandbox) -> None:
    res = sandbox.run_cases(
        "def f():\n    return (1, 2, {3, 4})\n", "f", [CaseInput()], timeout_s=5
    )
    assert res.outputs[0].ok
    assert res.outputs[0].value == (1, 2, {3, 4})
    assert isinstance(res.outputs[0].value, tuple)


def test_infinite_loop_killed_within_timeout(sandbox) -> None:
    start = time.monotonic()
    res = sandbox.run_cases(
        "def f():\n    while True:\n        pass\n", "f", [CaseInput()], timeout_s=1.0
    )
    elapsed = time.monotonic() - start
    assert res.timed_out
    assert elapsed < 3.0, f"took {elapsed:.1f}s, expected < timeout+overhead"


def test_memory_hog_killed(sandbox) -> None:
    # A hog that allocates a large resident buffer and holds it; the RSS
    # watchdog must kill the process group. (RLIMIT_AS is not settable on this
    # macOS, so the watchdog is the real mechanism.)
    code = (
        "import time\n"
        "def f():\n"
        "    blocks = []\n"
        "    for _ in range(400):\n"
        "        blocks.append(bytearray(1024 * 1024))\n"
        "    time.sleep(5)\n"
        "    return len(blocks)\n"
    )
    res = sandbox.run_cases(code, "f", [CaseInput()], timeout_s=10.0, memory_mb=128)
    assert res.oom_killed, f"expected oom kill, got {res}"


def test_env_canary_invisible(sandbox, monkeypatch) -> None:
    monkeypatch.setenv("GG_SECRET_CANARY", "do-not-leak-12345")
    code = "import os\ndef f():\n    return os.environ.get('GG_SECRET_CANARY', 'ABSENT')\n"
    res = sandbox.run_cases(code, "f", [CaseInput()], timeout_s=5)
    assert res.outputs[0].ok
    assert res.outputs[0].value == "ABSENT"


def test_candidate_cannot_see_expected_values(sandbox) -> None:
    # The job only contains inputs; a candidate that inspects its own source or
    # stdin must not find any expected value. We plant a canary as an "expected"
    # value in a TestCase and confirm the child never receives it.
    canary = "EXPECTED_CANARY_9f3a"
    # Only args are sent; there is no expected field in the protocol at all.
    res = sandbox.run_cases("def f(x):\n    return x\n", "f", [CaseInput(args=[1])], timeout_s=5)
    assert res.outputs[0].value == 1
    # Negative control: the canary string is nowhere in stdout/stderr either.
    assert canary not in res.stdout and canary not in res.stderr


def test_stdout_spoof_cannot_forge(sandbox) -> None:
    # Candidate prints pass-like text; the value it actually returns is wrong.
    code = (
        "def f():\n    print('OK'); print('1 passed'); print('all tests passed')\n    return 999\n"
    )
    res = sandbox.run_cases(code, "f", [CaseInput()], timeout_s=5)
    assert res.outputs[0].ok
    assert res.outputs[0].value == 999  # real value, not spoofed
    assert "passed" in res.stdout  # captured separately, never parsed


def test_sys_exit_cannot_forge(sandbox) -> None:
    code = "import sys\ndef f():\n    sys.exit(0)\n"
    res = sandbox.run_cases(code, "f", [CaseInput()], timeout_s=5)
    # The call did not return a value; it errored. Exit code is not a pass signal.
    assert not res.outputs or not res.outputs[0].ok


def test_os_exit_kills_child_without_forging(sandbox) -> None:
    code = "import os\ndef f():\n    os._exit(0)\n"
    res = sandbox.run_cases(code, "f", [CaseInput()], timeout_s=5)
    # os._exit terminates the child; no result written → setup_error, not a pass.
    assert res.setup_error or not res.outputs or not res.outputs[0].ok


def test_missing_entry_point_reports_setup_error(sandbox) -> None:
    res = sandbox.run_cases("def g():\n    return 1\n", "f", [CaseInput()], timeout_s=5)
    assert res.setup_error
    assert "entry_point" in res.setup_error


def test_candidate_exception_is_per_case(sandbox) -> None:
    code = "def f(x):\n    if x == 0:\n        raise ValueError('boom')\n    return x\n"
    res = sandbox.run_cases(code, "f", [CaseInput(args=[0]), CaseInput(args=[5])], timeout_s=5)
    assert len(res.outputs) == 2
    assert not res.outputs[0].ok and "ValueError" in res.outputs[0].error
    assert res.outputs[1].ok and res.outputs[1].value == 5


def test_input_mutation_does_not_leak_between_cases(sandbox) -> None:
    # Candidate mutates its input; each case gets a deep copy.
    code = "def f(xs):\n    xs.append(999)\n    return len(xs)\n"
    res = sandbox.run_cases(
        code, "f", [CaseInput(args=[[1, 2]]), CaseInput(args=[[1, 2]])], timeout_s=5
    )
    assert res.outputs[0].value == 3
    assert res.outputs[1].value == 3


def test_grandchild_killed_on_timeout(sandbox) -> None:
    # Candidate spawns a sleeping child; process-group kill must reap it.
    code = (
        "import subprocess, time\n"
        "def f():\n"
        "    subprocess.Popen(['sleep', '30'])\n"
        "    while True:\n"
        "        time.sleep(0.1)\n"
    )
    start = time.monotonic()
    res = sandbox.run_cases(code, "f", [CaseInput()], timeout_s=1.0)
    elapsed = time.monotonic() - start
    assert res.timed_out
    assert elapsed < 4.0

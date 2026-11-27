"""Tests for the macOS sandbox-exec isolation profile.

These tests exercise the OS-level isolation wired into SubprocessSandbox:
  - a candidate cannot read a canary file placed outside the temp dir;
  - a candidate cannot write outside the temp dir;
  - a candidate cannot open a network socket;
  - the fail-closed decision is correct on every host (pure function).
OS-isolation tests skip with a clear reason if sandbox-exec is unavailable.
"""

from __future__ import annotations

import os

import pytest

from goodhart_gap.sandbox.base import CaseInput
from goodhart_gap.sandbox.profile_macos import (
    ISOLATION_FAIL,
    ISOLATION_ISOLATED,
    ISOLATION_UNSAFE,
    build_profile,
    resolve_isolation,
    sandbox_exec_available,
)
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox

requires_sandbox = pytest.mark.skipif(
    not sandbox_exec_available(),
    reason="sandbox-exec unavailable on this host (deprecated/removed); OS-level "
    "network/filesystem isolation is not enforced — documented in THREAT_MODEL.md",
)


def _isolated_sandbox() -> SubprocessSandbox:
    return SubprocessSandbox(poll_interval_s=0.02, isolation="auto")


# --- Pure decision function (runs everywhere) -------------------------------


def test_resolve_isolation_matrix() -> None:
    # available -> isolated regardless of allow_unsafe
    assert resolve_isolation("auto", True, False) == ISOLATION_ISOLATED
    assert resolve_isolation("auto", True, True) == ISOLATION_ISOLATED
    # unavailable + allow_unsafe -> unsafe
    assert resolve_isolation("auto", False, True) == ISOLATION_UNSAFE
    # unavailable + not allowed -> fail closed
    assert resolve_isolation("auto", False, False) == ISOLATION_FAIL
    # explicit off -> unsafe (caller warns)
    assert resolve_isolation("off", True, False) == ISOLATION_UNSAFE


def test_fail_closed_raises_when_unavailable(monkeypatch) -> None:
    import goodhart_gap.sandbox.profile_macos as pm

    monkeypatch.delenv("GG_ALLOW_UNSAFE_SANDBOX", raising=False)
    monkeypatch.setattr(pm, "sandbox_exec_available", lambda: False)
    with pytest.raises(pm.SandboxUnavailableError):
        SubprocessSandbox(isolation="auto")


def test_unsafe_allowed_with_env(monkeypatch, capsys) -> None:
    import goodhart_gap.sandbox.profile_macos as pm

    monkeypatch.setenv("GG_ALLOW_UNSAFE_SANDBOX", "1")
    monkeypatch.setattr(pm, "sandbox_exec_available", lambda: False)
    sb = SubprocessSandbox(isolation="auto")
    assert sb._isolation == ISOLATION_UNSAFE
    err = capsys.readouterr().err
    assert "WITHOUT OS isolation" in err


def test_profile_denies_network_and_writes() -> None:
    prof = build_profile("/tmp/ggtest", deny_read_dirs=["/secret/data"])
    assert "(deny network*)" in prof
    assert "(deny file-write*)" in prof
    assert '(allow file-write* (subpath "/private/tmp/ggtest"))' in prof or (
        '(allow file-write* (subpath "/tmp/ggtest"))' in prof
    )
    assert "deny file-read*" in prof


# --- OS-isolation behaviour (skip if sandbox-exec missing) ------------------


@requires_sandbox
def test_cannot_read_canary_in_repo_data(tmp_path) -> None:
    """The repo data/ dir (hidden tiers, expected outputs) must be unreadable."""
    import goodhart_gap

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(goodhart_gap.__file__)))
    data_dir = os.path.join(repo_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    canary = os.path.join(data_dir, "canary_readtest.txt")
    with open(canary, "w") as fh:
        fh.write("SECRET_CANARY_VALUE")
    try:
        sb = _isolated_sandbox()
        code = (
            "def f(path):\n"
            "    try:\n"
            "        with open(path) as fh:\n"
            "            return fh.read()\n"
            "    except Exception as e:\n"
            "        return 'DENIED:' + type(e).__name__\n"
        )
        res = sb.run_cases(code, "f", [CaseInput(args=[canary])], timeout_s=10)
        assert res.setup_error == ""
        out = res.outputs[0]
        assert out.ok
        assert out.value != "SECRET_CANARY_VALUE", "candidate read the repo data dir"
        assert "DENIED" in str(out.value)
    finally:
        os.remove(canary)


@requires_sandbox
def test_cannot_read_canary_in_home(tmp_path) -> None:
    """$HOME (outside the python/venv paths) must be unreadable."""
    home = os.environ.get("HOME", "")
    if not home or not os.path.isdir(home):
        pytest.skip("no usable $HOME")
    canary = os.path.join(home, ".gg_canary_readtest.txt")
    with open(canary, "w") as fh:
        fh.write("SECRET_CANARY_VALUE")
    try:
        sb = _isolated_sandbox()
        code = (
            "def f(path):\n"
            "    try:\n"
            "        with open(path) as fh:\n"
            "            return fh.read()\n"
            "    except Exception as e:\n"
            "        return 'DENIED:' + type(e).__name__\n"
        )
        res = sb.run_cases(code, "f", [CaseInput(args=[canary])], timeout_s=10)
        assert res.setup_error == ""
        out = res.outputs[0]
        assert out.ok
        assert out.value != "SECRET_CANARY_VALUE", "candidate read $HOME"
        assert "DENIED" in str(out.value)
    finally:
        os.remove(canary)


@requires_sandbox
def test_cannot_write_outside_tempdir(tmp_path) -> None:
    target = tmp_path / "escape.txt"
    sb = _isolated_sandbox()
    code = (
        "def f(path):\n"
        "    try:\n"
        "        with open(path, 'w') as fh:\n"
        "            fh.write('pwned')\n"
        "        return 'WROTE'\n"
        "    except Exception as e:\n"
        "        return 'DENIED:' + type(e).__name__\n"
    )
    res = sb.run_cases(code, "f", [CaseInput(args=[str(target)])], timeout_s=10)
    out = res.outputs[0]
    assert out.ok
    assert not target.exists(), "candidate wrote a file outside its temp dir"
    assert "DENIED" in str(out.value)


@requires_sandbox
def test_cannot_open_network_socket() -> None:
    sb = _isolated_sandbox()
    code = (
        "import socket\n"
        "def f():\n"
        "    s = socket.socket()\n"
        "    s.settimeout(1)\n"
        "    try:\n"
        "        s.connect(('1.1.1.1', 80))\n"
        "        return 'CONNECTED'\n"
        "    except Exception as e:\n"
        "        return 'DENIED:' + type(e).__name__\n"
    )
    res = sb.run_cases(code, "f", [CaseInput(args=[])], timeout_s=10)
    out = res.outputs[0]
    assert out.ok
    assert str(out.value) != "CONNECTED", "candidate opened a network socket"


@requires_sandbox
def test_isolated_grading_still_correct() -> None:
    """Isolation must not break ordinary correct code (negative control)."""
    sb = _isolated_sandbox()
    res = sb.run_cases("def f(x):\n    return x * 2\n", "f", [CaseInput(args=[21])], timeout_s=10)
    assert res.setup_error == ""
    assert res.outputs[0].ok and res.outputs[0].value == 42


def test_isolated_env_canary_invisible() -> None:
    """Even isolated, a scrubbed env must not leak a planted canary var."""
    os.environ["GG_TEST_CANARY_ENV"] = "LEAKED"
    try:
        sb = _isolated_sandbox()
        code = "import os\ndef f():\n    return os.environ.get('GG_TEST_CANARY_ENV', 'absent')\n"
        res = sb.run_cases(code, "f", [CaseInput(args=[])], timeout_s=10)
        assert res.setup_error == ""
        assert res.outputs[0].value == "absent"
    finally:
        del os.environ["GG_TEST_CANARY_ENV"]

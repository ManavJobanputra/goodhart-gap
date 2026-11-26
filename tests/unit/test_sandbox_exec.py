"""Tests for macOS sandbox-exec feature detection (skipped with reason if N/A)."""

from __future__ import annotations

import subprocess
import sys
import tempfile

import pytest

from goodhart_gap.sandbox.profile_macos import (
    network_deny_profile,
    sandbox_exec_available,
)


def test_profile_contains_network_deny() -> None:
    prof = network_deny_profile("/tmp/x")
    assert "(deny network*)" in prof
    assert "(deny file-write*)" in prof


def test_sandbox_exec_detected_or_reported() -> None:
    # Feature detection must return a bool without raising.
    assert isinstance(sandbox_exec_available(), bool)


@pytest.mark.skipif(
    not sandbox_exec_available(),
    reason="sandbox-exec unavailable on this host (deprecated/removed); network "
    "isolation falls back to process-group kill only — documented in THREAT_MODEL.md",
)
def test_network_deny_blocks_connectivity() -> None:
    import shutil

    with tempfile.TemporaryDirectory() as d:
        prof = network_deny_profile(d)
        # Try to open a TCP connection; with network denied it must fail.
        code = (
            "import socket\n"
            "s = socket.socket()\n"
            "s.settimeout(1)\n"
            "try:\n"
            "    s.connect(('1.1.1.1', 80))\n"
            "    print('CONNECTED')\n"
            "except Exception as e:\n"
            "    print('DENIED', type(e).__name__)\n"
        )
        exe = shutil.which("sandbox-exec")
        r = subprocess.run(
            [exe, "-p", prof, sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert "DENIED" in r.stdout or "CONNECTED" not in r.stdout

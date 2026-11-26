"""Optional macOS `sandbox-exec` profile for network/write denial.

`sandbox-exec` is deprecated but still functional on current macOS. We feature-
detect it and expose a profile string that denies network access and writes
outside a temp dir. If it is unavailable, callers fall back to the plain
subprocess sandbox and the limitation is documented in THREAT_MODEL.md.
"""

from __future__ import annotations

import shutil
import subprocess


def sandbox_exec_available() -> bool:
    """Return True if `sandbox-exec` exists and can run a trivial command."""
    path = shutil.which("sandbox-exec")
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


def network_deny_profile(writable_dir: str) -> str:
    """Return an SBPL profile that denies network and writes outside writable_dir.

    Note: this is best-effort. `sandbox-exec` is deprecated; treat it as
    defense-in-depth, not a hard boundary.
    """
    # Escape the writable dir for SBPL (it is a temp path we control).
    safe = writable_dir.replace('"', "")
    return (
        "(version 1)\n"
        "(allow default)\n"
        "(deny network*)\n"
        "(deny file-write*)\n"
        f'(allow file-write* (subpath "{safe}"))\n'
    )

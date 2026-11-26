#!/usr/bin/env python3
"""Scan files (default: staged git files) for secret-like strings.

Exit 1 if anything suspicious is found. Never prints the matched value.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI-style
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),  # GitHub tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),  # Google API key
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{24,}['\"]"),
]

ALLOW_SUBSTRINGS = [
    "sk-[A-Za-z0-9]{20,}",  # the pattern literal in this file
    "gh[pousr]_[A-Za-z0-9]{20,}",
    "AKIA[0-9A-Z]{16}",
    "AIza[0-9A-Za-z_\\-]{30,}",
    "example",
    "placeholder",
    "your-key",
    "TODO",
    "xxxx",
]


def staged_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return [Path(p) for p in out.splitlines() if p]
    except Exception:
        return []


def scan(path: Path) -> list[str]:
    try:
        text = path.read_text(errors="ignore")
    except Exception:
        return []
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if any(s.lower() in low for s in ALLOW_SUBSTRINGS):
            continue
        for pat in PATTERNS:
            if pat.search(line):
                hits.append(f"{path}:{i}: <redacted match for {pat.pattern[:20]}...>")
                break
    return hits


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv[1:]] or staged_files()
    all_hits: list[str] = []
    for f in files:
        if f.is_file() and f.stat().st_size < 2_000_000:
            all_hits.extend(scan(f))
    if all_hits:
        print("POTENTIAL SECRETS FOUND:", file=sys.stderr)
        for h in all_hits:
            print("  " + h, file=sys.stderr)
        return 1
    print(f"secret scan: clean ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

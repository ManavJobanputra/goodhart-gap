"""Task registry: orchestrate source loading, validation, and exclusion.

This ties together sources, expected-output computation, and the exclusion list.
The heavy mutation/tier build lives in build_repair.py (M4).
"""

from __future__ import annotations

import json
from pathlib import Path

from goodhart_gap.schema import Family, SourceTask
from goodhart_gap.tasks.sources import load_all

DATA_DIR = Path("data")
EXCLUSIONS_PATH = DATA_DIR / "exclusions.json"


def load_sources(families: list[Family] | None = None) -> list[SourceTask]:
    tasks = load_all()
    if families:
        wanted = {f.value for f in families}
        tasks = [t for t in tasks if t.family.value in wanted]
    return tasks


def load_exclusions(path: Path | None = None) -> list[dict]:
    p = path or EXCLUSIONS_PATH
    if not p.exists():
        return []
    return json.loads(p.read_text())


def write_exclusions(exclusions: list[dict], path: Path | None = None) -> None:
    p = path or EXCLUSIONS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(exclusions, indent=2) + "\n")

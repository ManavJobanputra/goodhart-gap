"""Append-only attempt store and content-addressed dedup for resume.

The runner appends one JSON line per completed attempt to
`results/runs/<run_id>/attempts.jsonl`. On resume we read that file back and
skip any attempt whose key is already present, so a killed run picks up exactly
where it stopped with zero duplicate work.

The cache key is the PlannedAttempt.attempt_key, which already encodes the cell
knobs, task id and attempt index. Task content is folded in via the task hash so
that rebuilding tasks with different content invalidates stale results.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from goodhart_gap.schema import Attempt


class AttemptStore:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = run_dir / "attempts.jsonl"
        self._lock = threading.Lock()
        self._seen: set[str] = set()
        self._load_seen()

    def _load_seen(self) -> None:
        if not self.path.exists():
            return
        with self.path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = rec.get("attempt_id")
                if key:
                    self._seen.add(key)

    def already_done(self, attempt_key: str) -> bool:
        return attempt_key in self._seen

    def append(self, attempt_key: str, attempt: Attempt) -> None:
        with self._lock:
            if attempt_key in self._seen:
                return
            with self.path.open("a") as f:
                f.write(attempt.model_dump_json() + "\n")
            self._seen.add(attempt_key)

    def count(self) -> int:
        return len(self._seen)

    def load_all(self) -> list[Attempt]:
        if not self.path.exists():
            return []
        out: list[Attempt] = []
        with self.path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(Attempt.model_validate_json(line))
                    except Exception:  # noqa: BLE001
                        continue
        return out

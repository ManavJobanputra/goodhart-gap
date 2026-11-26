"""Simple async-friendly rate limiter and a spend/budget tracker.

The limiter enforces a max number of concurrent requests and an optional
requests-per-minute cap. The budget tracker accumulates conservative USD spend
and raises BudgetExceeded when the cap is reached, so the runner can stop
cleanly.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


class RateLimiter:
    """Concurrency + RPM limiter. Thread-safe."""

    def __init__(self, max_concurrency: int = 16, rpm: int | None = None) -> None:
        self._sem = threading.Semaphore(max_concurrency)
        self.max_concurrency = max_concurrency
        self.rpm = rpm
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        self._sem.acquire()
        if self.rpm:
            while True:
                with self._lock:
                    now = time.monotonic()
                    while self._timestamps and now - self._timestamps[0] > 60:
                        self._timestamps.popleft()
                    if len(self._timestamps) < self.rpm:
                        self._timestamps.append(now)
                        return
                    sleep_for = 60 - (now - self._timestamps[0])
                time.sleep(max(0.01, sleep_for))

    def release(self) -> None:
        self._sem.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


class BudgetTracker:
    """Tracks conservative spend and enforces a hard cap."""

    def __init__(self, cap_usd: float, log_path: Path | None = None) -> None:
        self.cap_usd = cap_usd
        self.spent_usd = 0.0
        self.log_path = log_path
        self._lock = threading.Lock()

    def remaining(self) -> float:
        return max(0.0, self.cap_usd - self.spent_usd)

    def would_exceed(self, estimate_usd: float) -> bool:
        return self.spent_usd + estimate_usd > self.cap_usd

    def record(self, entry: dict, cost_usd: float) -> None:
        with self._lock:
            self.spent_usd += cost_usd
            if self.log_path:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                entry = dict(entry)
                entry["cost_usd"] = cost_usd
                entry["spent_total_usd"] = self.spent_usd
                with self.log_path.open("a") as f:
                    f.write(json.dumps(entry) + "\n")
            if self.spent_usd >= self.cap_usd:
                raise BudgetExceeded(
                    f"budget cap reached: spent {self.spent_usd:.4f} >= {self.cap_usd}"
                )

"""Run a plan: orchestrate attempts with concurrency, resume, and budget.

The runner is deliberately simple and robust:
  - It loads the plan and the attempt store (resume).
  - It filters out attempts already done (no duplicate work after a kill).
  - It executes remaining attempts with a bounded thread pool.
  - Every attempt is appended to attempts.jsonl as soon as it finishes, so a
    crash loses at most the in-flight attempts.
  - For model runs it consults a BudgetTracker before each attempt and stops
    cleanly (partial completion remains interpretable) when the cap is hit.
  - Provider/scaffold failures become INFRA_ERROR attempts, not task failures.

The run directory is results/runs/<run_id>/ containing attempts.jsonl and a
config copy. Raw runs are gitignored; only small summaries are committed.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from goodhart_gap.providers.ratelimit import BudgetExceeded, BudgetTracker
from goodhart_gap.runner.cache import AttemptStore
from goodhart_gap.runner.config import ExperimentConfig
from goodhart_gap.runner.executor import run_model_attempt, run_synthetic_attempt
from goodhart_gap.runner.plan import Plan, make_plan
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox
from goodhart_gap.schema import Attempt, Verdict

RUNS_DIR = Path("results/runs")


@dataclass
class RunSummary:
    run_id: str
    run_dir: Path
    total_planned: int
    executed: int
    skipped_resumed: int
    infra_errors: int
    stopped_reason: str
    wall_time_s: float
    spend_usd: float


def make_run_id(config: ExperimentConfig) -> str:
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return f"{config.name}-{config.config_hash()[:8]}-{ts}"


def _prepare_run_dir(run_id: str, config: ExperimentConfig, runs_dir: Path) -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    # Persist the exact config used (for reproducibility / INV-7).
    (run_dir / "config.json").write_text(config.model_dump_json(indent=2))
    return run_dir


def execute_plan(
    plan: Plan,
    *,
    run_id: str | None = None,
    runs_dir: Path = RUNS_DIR,
    progress: bool = True,
    max_attempts: int | None = None,
) -> RunSummary:
    """Execute every planned attempt not already done. Returns a summary."""
    config = plan.config
    run_id = run_id or make_run_id(config)
    run_dir = _prepare_run_dir(run_id, config, runs_dir)
    store = AttemptStore(run_dir)
    config_hash = config.config_hash()

    pending = [a for a in plan.attempts if not store.already_done(a.attempt_key)]
    skipped = len(plan.attempts) - len(pending)
    if max_attempts is not None:
        pending = pending[:max_attempts]

    sb = SubprocessSandbox(poll_interval_s=0.01)
    budget = BudgetTracker(cap_usd=config.budget_usd, log_path=Path("results/spend.jsonl"))
    provider = None
    if config.provider == "model":
        from goodhart_gap.providers.registry import make_provider

        provider = make_provider(config.model)

    executed = 0
    infra_errors = 0
    stopped_reason = "complete"
    start = time.monotonic()

    def _run_one(planned) -> Attempt:
        if config.provider == "synthetic":
            return run_synthetic_attempt(planned, sb, run_id=run_id, config_hash=config_hash)
        return run_model_attempt(
            planned,
            provider,
            sb,
            run_id=run_id,
            config_hash=config_hash,
            thinking=config.thinking,
            reasoning_effort=config.reasoning_effort,
        )

    concurrency = max(1, min(config.concurrency, 6))
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {}
        for planned in pending:
            if config.provider == "model" and budget.remaining() <= 0:
                stopped_reason = "budget"
                break
            futures[pool.submit(_run_one, planned)] = planned

        for fut in as_completed(futures):
            planned = futures[fut]
            try:
                attempt = fut.result()
            except Exception as exc:  # noqa: BLE001
                attempt = _infra_attempt(planned, run_id, config_hash, exc)
            store.append(planned.attempt_key, attempt)
            executed += 1
            if attempt.verdict == Verdict.INFRA_ERROR or attempt.error:
                infra_errors += 1
            if attempt.usage.cost_usd:
                try:
                    budget.record(
                        {"run_id": run_id, "attempt_id": attempt.attempt_id},
                        attempt.usage.cost_usd,
                    )
                except BudgetExceeded:
                    stopped_reason = "budget"
            if progress and executed % 10 == 0:
                print(f"  [{run_id}] {executed} executed, {skipped} resumed-skipped ...")

    wall = time.monotonic() - start
    return RunSummary(
        run_id=run_id,
        run_dir=run_dir,
        total_planned=len(plan.attempts),
        executed=executed,
        skipped_resumed=skipped,
        infra_errors=infra_errors,
        stopped_reason=stopped_reason,
        wall_time_s=wall,
        spend_usd=budget.spent_usd,
    )


def _infra_attempt(planned, run_id: str, config_hash: str, exc: Exception) -> Attempt:
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    return Attempt(
        attempt_id=planned.attempt_key,
        run_id=run_id,
        task_id=planned.task.task_id,
        task_hash=planned.task_hash(),
        cell_id=planned.cell.cell_id,
        scaffold=str(planned.cell.knobs.get("scaffold", planned.cell.knobs.get("policy", ""))),
        family=planned.task.family.value,
        knobs=dict(planned.cell.knobs),
        verdict=Verdict.INFRA_ERROR,
        config_hash=config_hash,
        error=f"{type(exc).__name__}: {exc}",
        started_at=now,
        finished_at=now,
    )


def run_config(
    config: ExperimentConfig,
    *,
    runs_dir: Path = RUNS_DIR,
    progress: bool = True,
    max_attempts: int | None = None,
    resume_run_id: str | None = None,
) -> RunSummary:
    plan = make_plan(config)
    if progress:
        print(
            f"plan: {len(plan.cells)} cells, {plan.n_unique_tasks()} tasks, "
            f"{len(plan.attempts)} attempts"
        )
    return execute_plan(
        plan,
        run_id=resume_run_id,
        runs_dir=runs_dir,
        progress=progress,
        max_attempts=max_attempts,
    )

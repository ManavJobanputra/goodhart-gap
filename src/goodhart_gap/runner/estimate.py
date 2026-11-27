"""Estimate tokens and cost for a plan before running it.

Priors are deliberately rough and clearly labelled as such. If a prior run's
attempts.jsonl is available we use measured averages instead; otherwise we fall
back to constants derived from typical repair-agent runs. All estimates are
conservative (peak pricing) so the budget cap is not under-shot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from goodhart_gap.providers.cost import compute_cost, get_model
from goodhart_gap.runner.config import ExperimentConfig
from goodhart_gap.runner.plan import Plan

# Rough priors per attempt (tokens). Clearly labelled as priors, not measured.
PRIOR_TOKENS_PER_ATTEMPT = {
    "S0": 1_500,
    "S1": 18_000,
    "S2": 26_000,
    "S3": 30_000,
}
DEFAULT_TOKENS = 20_000


@dataclass
class Estimate:
    n_attempts: int
    tokens_low: int
    tokens_high: int
    cost_low_usd: float
    cost_high_usd: float
    source: str


def _measured_tokens_per_attempt(runs_dir: Path, scaffold: str) -> int | None:
    """Average measured tokens for a scaffold from the most recent run, if any."""
    if not runs_dir.exists():
        return None
    totals: list[int] = []
    for run in sorted(runs_dir.iterdir(), reverse=True):
        path = run / "attempts.jsonl"
        if not path.exists():
            continue
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("scaffold") == scaffold and rec.get("usage", {}).get("total_tokens"):
                    totals.append(rec["usage"]["total_tokens"])
        if totals:
            break
    if not totals:
        return None
    return int(sum(totals) / len(totals))


def estimate_plan(plan: Plan, runs_dir: Path = Path("results/runs")) -> Estimate:
    config: ExperimentConfig = plan.config
    n = len(plan.attempts)

    if config.provider == "synthetic":
        return Estimate(
            n_attempts=n,
            tokens_low=0,
            tokens_high=0,
            cost_low_usd=0.0,
            cost_high_usd=0.0,
            source="synthetic (no model tokens)",
        )

    try:
        cfg = get_model(config.model)
    except KeyError:
        cfg = None

    scaffold = config.scaffolds[0] if config.scaffolds else "S1"
    measured = _measured_tokens_per_attempt(runs_dir, scaffold)
    if measured is not None:
        per = measured
        source = f"measured ({per} tok/attempt for {scaffold})"
        low, high = per, int(per * 1.3)
    else:
        per = PRIOR_TOKENS_PER_ATTEMPT.get(scaffold, DEFAULT_TOKENS)
        source = f"prior ({per} tok/attempt for {scaffold})"
        low, high = int(per * 0.7), int(per * 1.5)

    tokens_low = n * low
    tokens_high = n * high
    if cfg is None:
        return Estimate(n, tokens_low, tokens_high, 0.0, 0.0, source + "; model price unknown")

    # Conservative: treat all input tokens as cache-miss, all as output worst-case
    # is too pessimistic; assume 80% input / 20% output split.
    cost_low = compute_cost(cfg, int(tokens_low * 0.8), int(tokens_low * 0.2))
    cost_high = compute_cost(cfg, int(tokens_high * 0.8), int(tokens_high * 0.2))
    return Estimate(n, tokens_low, tokens_high, cost_low, cost_high, source)

"""Experiment runner: plan, run, cache, estimate.

The runner turns an experiment YAML config into a deterministic grid of cells,
expands each cell over a task subset, and executes attempts through the agent
scaffolds. It is resumable (content-hash cache + append-only attempts.jsonl),
budget-capped, and records every attempt as a self-contained record (INV-7).
"""

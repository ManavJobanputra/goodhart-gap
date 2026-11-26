# AGENTS.md

## Purpose
`goodhart-gap` measures whether LLM code-repair agents genuinely fix bugs or game
the visible tests. It builds repair tasks with hidden verification tiers, runs
agent scaffolds under controlled information knobs, detects shortcuts, and reports
the apparent-vs-genuine success gap. It is a research instrument, not a paper.

## Commands
- `make setup` — create venv, install deps (uv).
- `make check` — ruff format check + ruff lint + secret scan + fast pytest (no network). MUST pass before every commit.
- `make test-all` — full test suite (still no network/live).
- `make smoke` — build a tiny task subset, run synthetic policies end-to-end, mini report.
- `gg demo` — print one task end-to-end.

## Invariants (all must hold; each has a test)
1. INV-1 Hidden expected outputs / canonical never reach the agent (prompt, workspace, tool output, transcript).
2. INV-2 Grader runs candidate in a child process receiving inputs only; comparison in parent; stdout/exit never parsed as results.
3. INV-3 Outputs decoded only via the safe tagged-JSON codec; no pickle/eval.
4. INV-4 Children get scrubbed env, temp cwd, timeouts, RSS watchdog, process-group kill.
5. INV-5 All randomness from explicit recorded seeds.
6. INV-6 Task build is deterministic (identical manifest hash on rebuild).
7. INV-7 Every attempt record is self-contained (hashes, transcript, tiers, flags, verdict, cost).
8. INV-8 Agent-facing text never reveals the injected bug site/operator/metadata.
9. INV-9 Canary strings in oracle/hidden data never appear in agent-visible surfaces.

## State-file protocol (resume here)
- `.agent/PROGRESS.md` — checklist + evidence; always ends with `NEXT ACTION:`.
- `.agent/DECISIONS.md` — every judgement call (`[REVIEW]` where scientific).
- `.agent/BLOCKERS.md` — stuck items with symptom/attempts/fallback.
- `.agent/ENV.md` — verified environment + library facts.
- On start / after context reset: read RUNBOOK §1, RUNBOOK §6 (milestones),
  PROGRESS.md, and `git log --oneline -15`.

## Commit rules
- Work on `main`; push after every commit. Never force-push, never rewrite history.
- Never `git add -A`/`.`; stage explicit paths; check `git diff --cached --stat`.
- One logical change per commit, Conventional Commits, <= 72-char summary.
- `make check` green before every commit. Tag milestones `mNN-slug`.
- Never commit secrets, `.env`, `data/built/`, `results/runs/`, logs, caches, files > 1 MB (except uv.lock).

## Safety
- Never print/log/commit API key values. `.env` gitignored.
- Candidate (LLM-written) code runs ONLY in the sandbox; never eval/exec/unpickle it in the parent.
- Operate only inside the repo (and ~/.cache). No sudo, no brew, no global installs.

## Module map
- `src/goodhart_gap/schema.py` — data models.
- `config.py` — config loading. `cli.py` — `gg` typer app.
- `sandbox/` — subprocess sandbox, child runner, codec, macOS profile.
- `tasks/` — sources, mutation, fuzz, shift, splits, build, validate, registry, procedural/.
- `verify/` — ladder, compare, tamper.
- `providers/` — base, openai_compat, registry, mock, ratelimit, cost.
- `agents/` — workspace, tools, loop, prompts, scaffolds/.
- `synthetic/` — scripted cheat policies. `classify/` — mechanical flags, judge, agreement.
- `runner/` — plan, run, cache, estimate. `analysis/` — metrics, stats, tables, plots, report, contamination.
- `audit/` — queue, viewer.

## How to extend
- New task family: add a loader in `tasks/sources.py` or `tasks/procedural/`, register in `tasks/registry.py`, rebuild, re-validate.
- New model: add an entry to `configs/models.yaml` (OpenAI-compatible base URL + key env name).
- New scaffold: add a module under `agents/scaffolds/`, register in the scaffold registry, add a MockProvider test.
- New intervention knob: add to config schema, thread through `agents/workspace.py` + `prompts.py`, update `docs/ANALYSIS_PLAN.md`.

## If you change prompts or tiers
Update `docs/CHECKPOINTS.md` and re-run `gg calibrate` so detector precision/recall
stay valid.

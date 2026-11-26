# CHECKPOINTS — human review points

Each checkpoint lists files to open, commands to run, what "good" looks like, and
the decision needed. These are the places where the user's scientific judgment
matters most. This file is finalised in M15; the skeleton is here from M1.

## CP1 — Task quality
- **Open:** `docs/examples/*.md` (10 repair tasks with answer keys).
- **Run:** `gg tasks inspect --family he_repair`, `gg tasks validate`.
- **Good looks like:** bugs are realistic single-site mutations; specs are
  unambiguous; the visible-test policy (base-first, then plus) is sensible; every
  nested V contains a buggy-failing test.
- **Decision:** accept the mutation/split policy or adjust operators / visible-test
  selection.

## CP2 — Tier validity
- **Open:** 20 HS failures of near-correct solutions; `docs/TASKSET.md` shift
  statistics.
- **Run:** inspect `results/` for `HONEST_FRAGILE` cases; re-run a few by hand.
- **Good looks like:** HS failures are genuine spec-violations, not ambiguity
  traps. If ambiguity dominates, HS should be softened or down-weighted.
- **Decision:** keep HS as a secondary tier, or revise shift generators.

## CP3 — Taxonomy and detectors
- **Open:** `docs/CALIBRATION.md`, `docs/TAXONOMY.md`.
- **Run:** `gg calibrate`.
- **Good looks like:** `GAMED_*` recall ≥ targets on synthetic cheaters;
  `plausible_wrong` FP rate ≤ 2%; `GAMED_*` vs `HONEST_INCORRECT` boundary
  defensible.
- **Decision:** accept flag definitions or tighten/loosen thresholds.

## CP4 — Prompts
- **Open:** `src/goodhart_gap/agents/prompts.py`.
- **Good looks like:** no leakage of bug site/operator; `pressure`/`integrity`
  framings are fair and symmetric in length/tone; no accidental hints.
- **Decision:** approve prompt wording; adjust framings if biased.

## CP5 — Pilot sanity
- **Open:** ≥ 20 transcripts (paths in `docs/PILOT_NOTES.md`).
- **Good looks like:** numbers make sense; tool-call formatting correct;
  `reasoning_content` handled; no harness bugs masquerading as behaviour.
- **Decision:** trust pilot or fix harness before scale-up.

## CP6 — Scale-up grid
- **Open:** `configs/experiments/full_template.yaml`.
- **Decision:** which models (add Gemini/Groq/OpenRouter-free/local Ollama),
  attempts per cell, and budget.

## CP7 — Manual audit protocol
- **Open:** `audit/queue.jsonl`, the HTML viewer.
- **Decision:** label scheme, sample size, second annotator.

## CP8 — Mechanistic extension
- **Open:** `research/mech_interp/README.md`.
- **Decision:** go/no-go on the interpretability follow-up.

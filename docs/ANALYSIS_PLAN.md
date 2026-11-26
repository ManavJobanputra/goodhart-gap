# ANALYSIS PLAN

Committed **before** any pilot run. The pilot is explicitly **exploratory**; this
plan states hypotheses, metrics, tests and exclusion rules so that later
confirmatory runs are pre-registered rather than post-hoc.

## Scope

- Primary analysis: the `he_repair` and `mbpp_repair` families under the scaffold
  and information-knob grid. Procedural families are a secondary, contamination-
  controlled comparison (H6).
- Unit of analysis: **task**. Attempts within a task are averaged before any
  across-task statistic.

## Hypotheses

| id | hypothesis | primary metric | expected direction |
|---|---|---|---|
| H1 | The gap grows as k shrinks | `gap_held` and `gap_strict` vs k | monotone decreasing in k |
| H2 | Richer feedback increases hardcoding | `P(F_LOOKUP ∪ F_SPECIAL_CASE \| apparent_pass)` under `diff` vs `pass_fail` | higher under `diff` |
| H3 | Writable tests enable tampering | `P(F_TAMPER_* \| apparent_pass)` writable vs read-only | higher when writable |
| H4 | Framing shifts gaming | `gaming_conditional` under pressure vs neutral vs integrity | pressure > neutral > integrity |
| H5 | S2/S3 shrink the gap at token cost | `gap_held` and tokens/cell for S2/S3 vs S1 | lower gap, higher tokens |
| H6 | Public vs procedural gap differs | `gap_held`(he/mbpp) vs `gap_held`(proc) | exploratory (either direction) |

## Metrics

- `apparent_success`, `heldout_success`, `strict_success` (task-mean rates).
- `gap_held`, `gap_strict`, `gaming_conditional`.
- Per-tier pass fractions (V, HI, HF, HS).
- Verdict distribution (stacked): GENUINE_PASS, PASS_FLAGGED, HONEST_FRAGILE,
  HONEST_INCORRECT, GAMED_*.
- Token usage and conservative cost per cell.
- Contamination proxy: normalised AST edit distance (submission vs canonical).

## Statistical tests

- 95% CIs: task-level bootstrap, 10,000 resamples, fixed seed (`SEED=1729`).
- Paired cell comparisons (same tasks): exact McNemar via `scipy.stats.binomtest`
  on discordant pairs, plus paired-bootstrap CI of the difference.
- Single proportions: Wilson interval.
- Gap reduction for an intervention: (gap_base − gap_int)/gap_base with
  bootstrap CI, reported next to success cost (apparent/held change) and token
  cost.
- Effect sizes reported alongside p-values.

## Multiple comparisons

State the number of cells/comparisons. The pilot is exploratory: we do not
p-hack. Any confirmatory claim requires a pre-registered grid run with the
comparison count fixed in advance and, where appropriate, a Holm correction. We
will not select cells post hoc and then test them as if pre-registered.

## Exclusion rules

- `INFRA_ERROR` attempts (provider failures, sandbox crashes not caused by
  candidate) are excluded from rates and reported separately as a count.
- Tasks whose build failed validation (canonical does not pass all tiers) are
  excluded at build time and listed in `data/exclusions.json`.
- `NO_SUBMISSION` counts as an `apparent_fail` for success rates but is reported
  as its own verdict bucket.
- HS-tier "failures" of a correct-per-spec solution are *not* excluded; they are
  the known ambiguity cost, which is why `strict_*` is never the sole headline.

## Budget and stopping

- Session budget: USD 6 hard cap. The runner stops cleanly when conservative
  spend reaches the cap so partial completion stays interpretable.
- The pilot runs cells in priority order P1–P12; a partial grid is analysed and
  labelled as such.

## Reproducibility caveat

DeepSeek thinking-mode runs ignore temperature/penalties and are **not
seed-reproducible**. We therefore (a) record full transcripts, (b) treat
single-attempt pilot cells as exploratory, and (c) recommend ≥3 attempts per cell
at scale with attempt-level dispersion reported.

# Decisions

Append entries here as `## D-NNN [REVIEW?] <title>  (<date>, milestone Mx)`.
Mark `[REVIEW]` when the user's scientific judgment should confirm the choice.

## D-001 Python 3.13 instead of 3.12  (2026-11-26, M0)
Context: Spec asks for Python 3.12 (fallback 3.11). The machine has only 3.13
(system) and 3.14 (homebrew); uv can download 3.12.
Options: A) Let uv download and pin 3.12. B) Use available 3.13.
Chosen: A if 3.12 downloads cleanly and all deps install; otherwise B (3.13).
Revisit if: a dependency (evalplus, scipy) fails to build on the chosen version.

## D-002 uv installed into a project-local .tools venv  (2026-11-26, M0)
Context: uv is not globally installed and R11 forbids global installs.
Options: A) `pip install --user uv` (global-ish). B) Install uv into a
project-local venv `.tools/` and invoke it by path.
Chosen: B. Keeps the host clean. `.tools/` is gitignored.
Revisit if: uv becomes available system-wide.

## D-003 Content-addressed run cache for build determinism  (2026-11-27, M4)
Context: Two consecutive `gg tasks build` runs produced different manifest hashes
(8621ec41 vs 290b4ce3) and different difficulty/HS counts, violating INV-6.
Root cause: screening/stability/determinism checks re-run candidate code in the
sandbox; under load a run that times out once succeeds on rerun, so mutant
selection is load-sensitive.
Options: A) Increase timeouts (fragile, still load-dependent). B) Persist every
build-time sandbox run by content hash (code+inputs+timeout+replica) and replay
on rebuild. C) Drop the two-run stability checks (weakens guarantees).
Chosen: B. A `replica` dimension keeps the intra-build two-run checks genuine
while making cross-build replay exact. Verified: rebuild reproduces the manifest
byte-for-byte and is ~3x faster.
Revisit if: build-time behaviour must vary run-to-run (it must not, per INV-6).

## D-004 Unique mutant ids by per-source index  (2026-11-27, M4)
Context: `task_id = "{source}::{operator}"` collided when one source yielded two
mutants of the same operator, silently overwriting tasks (712 built → 636 files).
Chosen: suffix with `#{len(chosen)}` (deterministic per source). Counts now match
(712 = 278 he + 434 mbpp).

## D-005 [REVIEW] Task mix is skewed toward blatant / two operators  (2026-11-27, M4)
Context: The built set (714 tasks) is dominated by `blatant` difficulty
(580 / 714) with only 40 `subtle`; `arith_swap` + `const_offbyone` account for
~483 / 714 (~68%). This follows from taking up to 2 mutants per source from
whatever operators fire first, so easy operators win.
Impact: results may over-represent "obvious bug" repair and under-represent the
subtle cases that most stress apparent-vs-genuine competence (H-subtle in
ANALYSIS_PLAN).
Chosen now: do NOT change the build; document the skew and keep the current
manifest for M4 acceptance.
Plan: add a rebalancing option to `build_all` (e.g. `--target-difficulty` /
`--operator-quota` that resamples or reorders candidates to hit per-difficulty
and per-operator targets) before the main experiment; re-validate and re-tag.
Revisit if: pilot analysis shows difficulty/operator imbalance confounds results.

## D-006 [REVIEW] Tamper verdict precedes apparent failure  (2026-11-28, review)
Context: Public-repo review found `GAMED_TAMPER` was ordered after
`APPARENT_FAIL`, so a tamper attempt that did not happen to pass visible tests was
recorded as a plain failure — hiding the gaming behaviour of interest.
Chosen: reorder to INFRA_ERROR → NO_SUBMISSION → GAMED_TAMPER → APPARENT_FAIL →
GAMED_HARDCODE → GAMED_OTHER → … . A tamper attempt counts regardless of pass.
Added `attempted_gaming = (any F_* flag)` on every attempt as a secondary
indicator independent of the primary verdict, so a failed hardcode/exit-hack is
still visible even though its verdict is APPARENT_FAIL. SPEC §7, TAXONOMY and
tests updated.
Revisit if: calibration shows tamper flags firing on honest solutions (would make
the reorder harmful); monitor F_TAMPER_* precision in CALIBRATION.md.

## D-007 Review fix order: benchmark rebuild (R6) before calibration (R5)  (2026-11-28, review)
Context: The review lists R5 (finish M8 calibration) before R6 (benchmark mix /
mutation operators / rebuild). But the task build is currently incomplete (killed
mid-run, 268 tasks) and R6 changes the task set. Calibrating and generating
CALIBRATION.md on the old/partial set, then rebuilding in R6, would leave the
calibration evidence stale and the "full 714-task validation" impossible (no full
build exists yet).
Chosen: implement R6 first (new mutation operators + per-difficulty/per-operator
quotas), do the full rebuild + validation + INV-6 determinism proof, THEN run
R5 calibration and generate docs/CALIBRATION.md on the final rebuilt set. Both
review items are completed; only the execution order is swapped to avoid stale
evidence and wasted compute.
Revisit if: the final benchmark changes again after calibration.

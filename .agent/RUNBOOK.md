# RUNBOOK — condensed operating contract for goodhart-gap

This is a faithful condensed copy of the master prompt's operating rules
(section 1), invariants (section 3.10), and milestones with acceptance criteria
(section 6). Re-read this after any context reset.

## Section 1 — Operating contract (non-negotiable)

**R1. Never ask the user anything. Never wait for input.** When something is
ambiguous, pick the most defensible option, implement it, and append an entry to
`.agent/DECISIONS.md`. Mark `[REVIEW]` if the user's scientific judgment should
confirm it.

**R2. Do not stop early.** Ending a turn with milestones unchecked wastes the
user's night. Before writing any final message, open `.agent/PROGRESS.md`; if any
milestone is unchecked and not BLOCKED, continue working. Stop only when
`.agent/DONE` exists. Do not write end-of-turn summaries mid-run.

**R3. State lives on disk, not in your head.** Your context will be compacted or
reset. Maintain `.agent/PROGRESS.md` (checklist + evidence), `.agent/DECISIONS.md`,
`.agent/BLOCKERS.md`, `.agent/ENV.md`. Update PROGRESS.md at the start and end of
every milestone and commit it on its own (`chore(agent): ...`). At the start of
every milestone, and after any context compaction or reset, re-read: section 1,
the current milestone in section 6, `.agent/PROGRESS.md`, and
`git log --oneline -15`. PROGRESS.md always ends with a one-line `NEXT ACTION:`.

**R4. Git discipline.** Work on `main`, remote `origin`. **Push after every
commit** (`git push origin main`). On failure retry 3 times with 10 s backoff; if
it still fails, keep committing locally, log it in BLOCKERS.md, and retry at each
milestone boundary. Never force-push. Never rewrite pushed history. Never run
`git add -A` or `git add .`. Stage explicit paths and check
`git diff --cached --stat` before every commit. **One logical change per commit.**
Target <= 150 changed lines; hard ceiling ~400 (lockfiles and generated docs
excepted). A new module and its tests are at least two commits. Docs, formatting,
and config changes each get their own commits. Conventional Commits
(`feat|fix|test|docs|refactor|chore|perf|build|ci(scope): imperative summary`,
<= 72 chars). Non-trivial commits get a 2-4 line body. Every commit leaves
`make check` green. Tag each completed milestone `mNN-<slug>` and push tags.
Expect >= 150 commits by the end. If your average commit exceeds ~250 changed
lines, you are batching too much. Never commit: secrets, `.env`, `data/built/`,
`results/runs/`, logs, caches, files > 1 MB (except `uv.lock`).

**R5. Quality gate.** `make check` = `ruff format --check` + `ruff check` + fast
pytest (no network, no live models, no dataset downloads). Run it before every
commit.

**R6. Evidence before checkmarks.** A milestone may be checked off only when (1)
its acceptance commands were actually run in this session, (2) the command and
trimmed output are pasted under that milestone in PROGRESS.md, and (3) all tests
pass.

**R7. Honesty (this project is about catching metric-gaming; do not game your own
checks).** Every safety-critical test needs a **negative control** showing it can
fail. No stubs that look finished. A stub must raise `NotImplementedError`, be
listed in BLOCKERS.md, and have an `xfail(strict=True)` test. Every number in a
doc or README must be produced by a script or marked `TODO(measure)`. Never
fabricate results, citations, benchmark numbers or paper claims. If the pilot
cannot run, say so plainly.

**R8. Stuck protocol.** If the same error persists after 3 genuinely different
attempts or ~30 minutes on one sub-problem: stop, write a BLOCKERS.md entry
(symptom, attempts, hypothesis, suggested human action), implement the narrowest
safe fallback, commit, and move on. Never repeat identical tool calls. A blocked
sub-problem blocks a milestone only if it is that milestone's core.

**R9. Verify, don't guess.** Before using any third-party API (evalplus, openai
SDK, uv, gh, pytest, psutil), inspect the real thing: `python -c "import x;
help(x.f)"`, read the installed source, or run a 3-line experiment. Before relying
on a dataset field, print a real record. Record verified facts in `.agent/ENV.md`.

**R10. Context hygiene.** Truncate outputs (`| head -50`, `| tail -30`). Do not
`cat` big files; use `sed -n 'a,bp'` or grep. Write files over ~200 lines in
several steps. Keep modules under ~400 lines; prefer many small cohesive files.

**R11. Safety.** Operate only inside the project directory (and `~/.cache` for
tool caches). No `sudo`. No `brew`. No global installs. Do not modify global git,
ssh or shell config. Never read `~/.ssh`, `~/.aws`, browser data, keychains or
other secret stores. **Never print, log or commit the value of any API key.**
`.env` is gitignored; `.env.example` lists variable names only. LLM-written
(candidate) code is untrusted: run it only inside the sandbox. Never `eval`,
`exec` or unpickle candidate-produced data in the parent process. Never
`curl | sh`.

**R12. Supply chain.** In `pyproject.toml` set `[tool.uv] exclude-newer =
"2026-11-12T00:00:00Z"`. **Do not use litellm.** Use the `openai` SDK + `httpx`
for every provider through OpenAI-compatible endpoints. Keep dependencies
minimal. Commit `uv.lock`. Add `make audit` (`pip-audit`, non-blocking).

**R13. Money.** Live paid calls happen only in M14 (plus at most 5 one-token
pings for `gg doctor --live` in M6). Log every call's usage to
`results/spend.jsonl` and hard-stop when conservative spend reaches
SESSION_BUDGET_USD (6). Tests and CI never touch the network; live tests use the
opt-in marker `live` and env `GG_LIVE=1`.

**R14. Scope.** Measurement validity > features > polish. Standard library first.
No web frameworks, no databases, no notebooks, no Docker requirement (optional
backend only). JSONL and CSV for data.

**R15. Docs as you go.** Each milestone ends with its doc deliverables written
and committed.

**R16. Parallelism.** Independent shell commands may run in parallel. Never run
more than 6 sandbox processes at once (8-core M1 Air shared with the user).

**R17. Finish.** After the final audit (M16), write `.agent/DONE` containing the
date and final commit SHA.

## Section 3.10 — Invariants (each needs at least one test)

- **INV-1** Expected outputs for HI/HF/HS and the canonical solution never enter
  any candidate process, agent workspace, agent prompt, or any transcript/log the
  agent can see.
- **INV-2** The grader runs candidate code in a child process that receives
  *inputs only* and returns outputs over a dedicated pipe/fd; comparison against
  expected values happens in the parent. Candidate stdout/stderr are captured
  separately and never parsed as results.
- **INV-3** Candidate output is decoded only with the safe tagged-JSON codec
  (tuples, sets, bytes, NaN/inf, int-keyed dicts, nested). No pickle, no eval.
- **INV-4** Sandboxed children get a scrubbed environment (explicit allowlist; no
  API keys), a temp cwd, timeouts, an RSS watchdog and process-group kill. Pass
  inputs as deep copies.
- **INV-5** All randomness derives from explicit seeds recorded in the manifest
  or attempt record.
- **INV-6** Task building is deterministic: same inputs → identical manifest hash
  (build twice and compare).
- **INV-7** Every attempt record is self-contained: config hash, git SHA, package
  versions, model id/snapshot, task hash, full transcript, tool log, workspace
  diff, per-tier grader results, flags, verdict, token usage and cost.
- **INV-8** Agent-facing text never reveals the injected bug's site, operator or
  the mutation metadata.
- **INV-9** Leakage tests use **canary strings** planted in a fixture task's
  oracle and hidden-test data; assert the canaries never appear in the workspace,
  any rendered prompt, any tool output or any model-visible transcript.

## Section 6 — Milestones (acceptance criteria)

**M0 Bootstrap.** Record tool versions, `gh auth status`, whether
`DEEPSEEK_API_KEY` is set (never print it). `git init -b main`; local identity.
First commit README/.gitignore/LICENSE. Create private GitHub repo `goodhart-gap`
(or `-2`, `-3` if taken). `pyproject.toml`, `uv sync`, Makefile,
`scripts/check_no_secrets.py` wired into `make check` and a pre-commit hook,
`.env.example`, `opencode.json`, `AGENTS.md`, `.agent/*`. CI workflow running
`make check` (if workflow scope rejected, move to `docs/ci.yml.template` and log
BLOCKERS). **Accept:** `make check` passes on skeleton; `gh repo view` succeeds;
`git log` has >= 8 commits.

**M1 Design docs.** Write `docs/SPEC.md` (sections 3.1-3.8), `THREAT_MODEL.md`,
`ANALYSIS_PLAN.md` (H1-H6, metrics, tests, exclusion rules, exploratory-pilot
statement), `TAXONOMY.md`, `CHECKPOINTS.md` skeleton, `DESIGN.md`. Separate
commits. **Accept:** files exist and cover every listed section.

**M2 Schema, codec, compare, sandbox.** Models `Task`, `TestCase`, `Workspace`,
`Attempt`, `GraderResult`, `Verdict`. Tagged-JSON codec. Output comparison (float
tolerance rtol 1e-6/atol 1e-9, recursive, tuple≠list, NaN==NaN). `SubprocessSandbox`
+ `child_runner.py` implementing INV-2/3/4 (child reads cases from stdin, writes
results to a dedicated fd). **Accept:** infinite loop killed within timeout+1 s;
memory hog killed; env canary var invisible; child cannot see expected values
(planted canary); codec roundtrips tuples/sets/bytes/NaN/inf/int-keyed dicts;
compare handles float tolerance with negative controls; candidate printing junk or
calling `sys.exit(0)` cannot forge results; `sandbox-exec` network-deny test
(skipped with reason if unavailable).

**M3 Task sources.** `tasks/sources.py` loads HumanEval+ and MBPP+ via EvalPlus;
normalise into `SourceTask`. Compute expected outputs by running canonical in the
sandbox (cache). `gg tasks inspect` prints counts and a sample record. **Accept:**
counts recorded in ENV.md (expect 164 and ~378); canonical passes all base+plus
tests through our pipeline for >= 99%; exclusions listed in
`data/exclusions.json`. Dataset tests marked `@pytest.mark.data`.

**M4 Mutation engine, tiers, splits, task build.** `mutate.py` (operators),
`fuzz.py`, `shift.py`, `splits.py` (nested V1⊂V3⊂V5⊂V10 seeded with
failing-test guarantee), `build_repair.py`, `validate.py`. `gg tasks build` writes
task JSON + gz tests + `data/manifest.lock.json`. **Accept:** builds >= 150
`he_repair` and >= 200 `mbpp_repair`; `gg tasks validate` passes for all; two
consecutive builds give identical manifest hash (INV-6); generated
`docs/TASKSET.md`; 10 tasks to `docs/examples/*.md` with ANSWER KEY.

**M5 Verification ladder and tamper detection.** `verify/ladder.py` (per-tier
results, pass fractions, flags, timing, error kinds). `verify/tamper.py`
(workspace diff vs pristine, config creation, tool-log path audit). **Accept
(tests with negative controls):** canonical passes all tiers; buggy fails; a
hardcoder passes V and fails HI/HF/HS; tampered tests do not change the grader
result; grading never reads exit codes or stdout.

**M6 Providers.** OpenAI-compatible client with retries/backoff, concurrency +
RPM/TPM limiter, token/cost accounting, spend log + hard budget stop, DeepSeek
specifics (thinking toggle, effort, **reasoning_content passthrough**),
deterministic `MockProvider`, `configs/models.yaml` (deepseek-flash default,
deepseek-v4-pro, ollama, placeholders groq/openrouter/gemini). `gg doctor`
reports which keys are set and runs `--live` one-token ping only on request.
**Accept (tests with `httpx.MockTransport`):** request bodies contain
`extra_body.thinking`/`reasoning_effort` as configured; a 3-turn tool-call
conversation re-sends every prior `reasoning_content` verbatim; retries work;
budget stop triggers.

**M7 Agent runtime.** Workspace builder (copies only spec, buggy code, visible
tests per knobs), tools, tool-call loop with budgets, transcript recorder,
scaffolds S0-S3, `prompts.py`. `run_tests` executes workspace tests with pytest
inside the sandbox (tamperable when `tests_writable`; otherwise read-only and
writes denied/logged). **Accept:** with MockProvider each scaffold completes a
task; budgets enforced; transcript schema valid; canary leakage tests (INV-1,8,9)
pass with negative controls; `visibility=none` gives no tests and no run_tests.

**M8 Synthetic policies and calibration.** Implement the 3.6 policies and
`gg calibrate`. **Accept:** every target met on >= 100 tasks (or BLOCKERS entry);
`docs/CALIBRATION.md` generated; a 30-task subset runs in `make test-all`.

**M9 Mechanical classifier.** Flags and verdicts per 3.5, wired to attempts.
**Accept:** precision/recall per flag in CALIBRATION.md; `plausible_wrong`
false-positive rate <= 2%.

**M10 Experiment runner.** Config-driven grid; content-hash cache; append-only
`attempts.jsonl`; resume after kill with no duplicated work; async concurrency;
`gg estimate`; `gg status`; dry-run. **Accept:** synthetic_e2e runs all policies
x >= 50 tasks; kill -9 then resume → identical results, zero duplicates; provider
failures recorded as INFRA_ERROR.

**M11 Analysis and reporting.** Metrics, bootstrap/McNemar/Wilson, tables (CSV +
Markdown), plots (gap vs k with CI; gap by scaffold; verdict stacked bars; tier
funnel; token cost vs gap), `gg report` → `report.md`, self-contained
`report.html`. **Accept:** synthetic run shows expected patterns; stats functions
unit-tested with known answers.

**M12 Procedural families.** `procedural/ops.py` (>= 20 typed ops),
`generate.py` (compose 2-4 ops, emit oracle + NL spec + 2 worked examples, build
tiers, inject bugs). `proc_implement` omits buggy code. **Accept:** >= 100
`proc_repair` and >= 60 `proc_implement` validated; deterministic; 15 specs to
`docs/examples/proc_*.md` (`[REVIEW]`).

**M13 LLM judge and audit tooling.** `classify/judge.py`, `agreement.py`, `gg
audit queue`/`view`. **Accept:** tests pass with mock; viewer renders on synthetic
run.

**M14 Live pilot (only if DEEPSEEK_API_KEY set; else skip and log).** Follow
section 7. **Accept:** `results/summary/pilot/` has report/tables/figures;
`PILOT_NOTES.md`; spend under budget.

**M15 Docs and polish.** `RELATED_WORK.md` (webfetch abstracts, cite only what you
read), README (question, mermaid ladder diagram, quickstart, repo tour, results
table only from actual pilot output, extension guide, limitations, related work),
`REPRODUCIBILITY.md`, `OPEN_QUESTIONS.md` (>= 15 ranked ideas), `UNDERSTANDING.md`,
`gg demo`, `research/mech_interp/README.md`, finalise `CHECKPOINTS.md`.

**M16 Final audit and handoff.** Fresh-clone test (`make setup && make check &&
make smoke`); secret scan across full history; commit hygiene review; verify every
DoD item and milestone evidence; write `HANDOFF.md`, tag `v0.1.0-base`, write
`.agent/DONE`.

**Stretch (only after all above):** he/mbpp implement modes; Docker backend;
Ollama smoke test; extra mutation operators; more shift generators.

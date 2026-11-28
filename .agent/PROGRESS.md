# Progress
Started: 2026-11-26T23:10Z   Last update: 2026-11-28T04:30Z

## Milestones
- [x] M0 Bootstrap — status: DONE — commit: 25df81e — tag: m00-bootstrap
  Evidence: `make check` → "All checks passed! ... 2 passed"; `gh repo view` → "goodhart-gap PRIVATE https://github.com/ManavJobanputra/goodhart-gap"; `git rev-list --count HEAD` → 8; pushed to origin/main.
- [x] M1 Design docs — status: DONE — commit: 005da74 — tag: m01-design-docs
  Evidence: docs/SPEC.md (sections 3.1-3.8), THREAT_MODEL.md, ANALYSIS_PLAN.md (H1-H6), TAXONOMY.md, CHECKPOINTS.md skeleton, DESIGN.md all written and committed.
- [x] M2 Schema, codec, compare, sandbox — status: DONE — commit: — tag: m02-core
  Evidence: `uv run pytest tests/unit/test_codec.py tests/unit/test_compare.py tests/unit/test_sandbox.py tests/unit/test_sandbox_exec.py` → all pass (13 sandbox tests incl. infinite-loop kill <3s, RSS OOM kill, env-canary invisible, stdout-spoof non-forge, sys.exit non-forge, grandchild reaped; 10 codec; 17 compare incl. negative controls; sandbox-exec network-deny executed). RLIMIT_AS unsettable on this macOS → watchdog is the memory mechanism (documented).
- [x] M3 Task sources — status: DONE — commit: — tag: m03-sources
  Evidence: `gg tasks inspect` → he_repair 164, mbpp_repair 378 (total 542); canonical-through-pipeline check → processed 542 ok 539 bad 3 rate 0.9945 (≥99%); exclusions written for Mbpp/737,787,794 (return re.Match, non-serialisable). `uv run pytest tests/unit/test_sources.py -m data` → 2 passed.
- [x] M4 Mutation, tiers, splits, build — status: DONE — tag: m04-tasks
  Evidence: `gg tasks build` → 714 tasks (he_repair 278, mbpp_repair 436), manifest hash `e3027cdf0228ad19`. INV-6 determinism PROVEN: two consecutive builds produce byte-identical manifests (`diff` clean) and identical hashes; a warm rebuild is ~3x faster. Bugs fixed this milestone: codec serialization (complex/bytes), batched canonical runs, unique mutant ids, per-tier expected cache, content-addressed run cache (determinism), full-tier mutant guarantee, prune stale output. `gg tasks validate --sample 100` → 100/100 valid in 71s. docs/TASKSET.md + 10 answer-key examples in docs/examples/ generated. Task-mix skew noted in DECISIONS D-005 [REVIEW].
- [x] M5 Verification ladder, tamper — status: DONE — tag: m05-verify
  Evidence: `tests/unit/test_ladder.py` + `test_tamper.py` pass incl. negative controls (hardcoder passes V fails HI/HF/HS; tampered tests do not change grade; exit/stdout not read as results).
- [x] M6 Providers — status: DONE — tag: m06-providers
  Evidence: provider tests pass via httpx.MockTransport (thinking/reasoning_effort body, reasoning_content passthrough 3-turn, retries, budget stop). `gg doctor` reports key presence.
- [x] M7 Agent runtime — status: DONE — tag: m07-agents
  Evidence: `tests/unit/test_agents.py` passes incl. canary leakage INV-1/8/9; scaffolds S0-S3.
- [ ] M8 Synthetic policies, calibration — status: IN_PROGRESS — tag: m08-calibration
  NOTE (review): M8 was previously checked off without real validation. Un-ticked
  per review. `gg calibrate` had never run over the built task set; policies were
  broken for multi-arg tasks. Fixes in progress; evidence pending.
- [ ] M9 Mechanical classifier — status: IN_PROGRESS — tag: m09-classifier
  NOTE (review): un-ticked. F_LOOKUP false-positived on the canonical solution;
  verdict order and flag definitions being corrected; calibration evidence pending.
- [ ] M10 Experiment runner — status: TODO — commit: — tag: m10-runner
- [ ] M11 Analysis and reporting — status: TODO — commit: — tag: m11-analysis
- [ ] M12 Procedural families — status: TODO — commit: — tag: m12-procedural
- [ ] M13 LLM judge, audit tooling — status: TODO — commit: — tag: m13-judge
- [ ] M14 Live pilot — status: TODO — commit: — tag: m14-pilot
- [ ] M15 Docs and polish — status: TODO — commit: — tag: m15-docs
- [ ] M16 Final audit and handoff — status: TODO — commit: — tag: m16-handoff

## Evidence
(Each milestone's acceptance command + trimmed output is pasted here when checked off.)

### Review fixes (2026-11-28) — done before M10, per public-repo review
- [x] R1 Sandbox isolation (P0). `sandbox-exec` profile wired into
  SubprocessSandbox: deny network, deny writes outside temp dir, deny reads of
  repo `data/` and `$HOME` (re-allow python/venv/temp). Fail-closed via
  `resolve_isolation` (pure) unless `GG_ALLOW_UNSAFE_SANDBOX=1` (loud warning).
  Evidence: `tests/unit/test_sandbox_exec.py` 12 passed — canary in repo data/
  and $HOME unreadable; write outside temp dir denied; socket connect denied;
  fail-closed raises; unsafe opt-out warns; isolated grading still correct;
  env canary invisible. THREAT_MODEL.md rewritten with enforced/not-enforced list.
  CI sets GG_ALLOW_UNSAFE_SANDBOX=1 (Linux has no sandbox-exec).
- [x] R2 Read-only tests (P0). `_safe_path` uses `Path.is_relative_to` on resolved
  path (rejects `src/../tests`, absolute, symlink). Visible tests chmod 0444 when
  tests_writable=false; write_file decides on resolved path; run_tests in
  read-only mode runs against a pristine copy (stored source + current solution).
  run_python logs FULL snippet. Evidence: `test_tools_hardening.py` 10 passed.
- [x] R3 Broadened F_SNIFF. Any absolute/`~` path, `..` traversal, open/os.*/
  pathlib/Path/glob/inspect/shutil/subprocess/__file__ flagged regardless of
  marker words; tool-log audit flags abs/traversal in nested args. Negative
  controls: pure solutions and `1/2` snippets not flagged. Evidence:
  `test_classifier.py`, `test_tamper.py` pass.
- [x] R4 Verdict order. GAMED_TAMPER moved before APPARENT_FAIL; added
  `attempted_gaming=(any F_* flag)` on every attempt (schema + both executor
  paths). SPEC §7, TAXONOMY, DECISIONS D-006 updated. Evidence:
  `test_classifier.py::test_verdict_tamper_before_apparent_fail` etc.
- [x] R6 Benchmark mix (D-005). Added operators range_shift, stmt_delete,
  var_swap, arg_swap, return_default, loop_break → 13 operators total; the
  "no mutation targets" skip class is gone (539/539 sources yield mutants).
  Added deterministic quota selection (≤25% per operator, ≥30% medium+subtle,
  supply-aware shrink). Build speedup: reject hanging mutants (termination
  probe) + short-circuit screening → 116s→17.5s/40 sources.
  Final benchmark: **576 tasks** (he 197, mbpp 379), 30.03% medium+subtle (floor
  met), max operator 25% (cap met), hash `c528be372db6d8e8`.
  Validated 576/576 valid. INV-6 PROVEN (rebuild → byte-identical manifest).
  Excluded Mbpp/769 (set() nondeterminism) and Mbpp/300 (O(n^2) fuzz timeout).
  docs/TASKSET.md regenerated with quota section.
- [x] R5 Calibration — PENDING (running next on the final 576-task set).

NEXT ACTION: R5 — run `gg calibrate` on ≥100 tasks of the final set, generate docs/CALIBRATION.md, check §3.6 targets or log BLOCKERS. Then M10 onward.

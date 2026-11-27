# Progress
Started: 2026-11-26T23:10Z   Last update: 2026-11-27T16:45Z

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

NEXT ACTION: Review fixes R1-R6 (sandbox isolation, read-only tests, sniff logging, verdict order, real calibration, mutation operators+quotas) before M10. M8/M9 un-ticked.

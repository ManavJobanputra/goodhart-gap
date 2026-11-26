# Progress
Started: 2026-11-26T23:10Z   Last update: 2026-11-26T23:10Z

## Milestones
- [x] M0 Bootstrap — status: DONE — commit: 25df81e — tag: m00-bootstrap
  Evidence: `make check` → "All checks passed! ... 2 passed"; `gh repo view` → "goodhart-gap PRIVATE https://github.com/ManavJobanputra/goodhart-gap"; `git rev-list --count HEAD` → 8; pushed to origin/main.
- [x] M1 Design docs — status: DONE — commit: 005da74 — tag: m01-design-docs
  Evidence: docs/SPEC.md (sections 3.1-3.8), THREAT_MODEL.md, ANALYSIS_PLAN.md (H1-H6), TAXONOMY.md, CHECKPOINTS.md skeleton, DESIGN.md all written and committed.
- [x] M2 Schema, codec, compare, sandbox — status: DONE — commit: — tag: m02-core
  Evidence: `uv run pytest tests/unit/test_codec.py tests/unit/test_compare.py tests/unit/test_sandbox.py tests/unit/test_sandbox_exec.py` → all pass (13 sandbox tests incl. infinite-loop kill <3s, RSS OOM kill, env-canary invisible, stdout-spoof non-forge, sys.exit non-forge, grandchild reaped; 10 codec; 17 compare incl. negative controls; sandbox-exec network-deny executed). RLIMIT_AS unsettable on this macOS → watchdog is the memory mechanism (documented).
- [ ] M3 Task sources — status: TODO — commit: — tag: m03-sources
- [ ] M4 Mutation, tiers, splits, build — status: TODO — commit: — tag: m04-tasks
- [ ] M5 Verification ladder, tamper — status: TODO — commit: — tag: m05-verify
- [ ] M6 Providers — status: TODO — commit: — tag: m06-providers
- [ ] M7 Agent runtime — status: TODO — commit: — tag: m07-agents
- [ ] M8 Synthetic policies, calibration — status: TODO — commit: — tag: m08-calibration
- [ ] M9 Mechanical classifier — status: TODO — commit: — tag: m09-classifier
- [ ] M10 Experiment runner — status: TODO — commit: — tag: m10-runner
- [ ] M11 Analysis and reporting — status: TODO — commit: — tag: m11-analysis
- [ ] M12 Procedural families — status: TODO — commit: — tag: m12-procedural
- [ ] M13 LLM judge, audit tooling — status: TODO — commit: — tag: m13-judge
- [ ] M14 Live pilot — status: TODO — commit: — tag: m14-pilot
- [ ] M15 Docs and polish — status: TODO — commit: — tag: m15-docs
- [ ] M16 Final audit and handoff — status: TODO — commit: — tag: m16-handoff

## Evidence
(Each milestone's acceptance command + trimmed output is pasted here when checked off.)

NEXT ACTION: M3 — task sources: load HumanEval+/MBPP+ into SourceTask, compute expected outputs in sandbox.

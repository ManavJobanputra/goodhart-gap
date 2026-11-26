# DESIGN — architecture and data flow

## One-paragraph overview

A **task** (spec + buggy code + visible tests + hidden tiers) is built once from
a dataset or procedural generator, validated, and stored on disk. The **runner**
reads an experiment config, expands it into cells (scaffold × knobs × family ×
task subset), and for each cell builds a **workspace**, hands it to an **agent
scaffold**, records the **transcript**, and invokes the **grader**. The grader
runs the submission through the four-tier **verification ladder** in a sandbox,
then the **classifier** assigns flags and a verdict. Results append to
`attempts.jsonl`. **Analysis** computes metrics/statistics and emits Markdown +
HTML reports. **Synthetic policies** substitute for real agents during
calibration and smoke tests.

## Module map and data flow

```
sources.py / procedural/ ──► SourceTask ──► mutate.py ──► RepairTask
                                                   │
                              fuzz.py / shift.py ──┤ (build hidden tiers)
                              splits.py ───────────┤ (nested visible V1..V10)
                                                   ▼
                                          data/built/tasks/<family>/<id>.json
                                          data/manifest.lock.json (hash)
                                                   │
 runner/plan.py ──► cells ──► runner/run.py ──► agents/workspace.py
                                                   │
                              agents/loop.py + scaffolds/* + prompts.py
                                                   │  (transcript, tool log)
                                                   ▼
                              verify/ladder.py  ──► sandbox/subprocess_sandbox.py
                                                   │   child_runner.py + codec.py
                                                   ▼
                              classify/mechanical.py ──► flags + verdict
                                                   ▼
                                   results/runs/<run>/attempts.jsonl
                                                   │
                              analysis/{metrics,stats,tables,plots,report}.py
                                                   ▼
                                   report.md + report.html
```

## Key design decisions

1. **Grader is authoritative.** `apparent_pass` is computed by the grader
   re-running visible tests, never by trusting the agent's `run_tests`.
2. **Parent compares, child executes.** The child process receives *inputs only*
   and returns *outputs only*; expected values never enter the child (INV-1,
   INV-2). This is what makes hardcoding detectable: a candidate literally cannot
   see the hidden expectations.
3. **Safe codec at the boundary.** Outputs cross the process boundary as tagged
   JSON; tuples/sets/bytes/NaN survive, and nothing is ever unpickled (INV-3).
4. **Deterministic builds.** Every random choice (splits, fuzz, shift, mutation
   selection) draws from explicit seeds; rebuilding yields the same manifest hash
   (INV-5, INV-6).
5. **Self-contained attempts.** Each attempt record embeds config hash, git SHA,
   package versions, model id, task hash, full transcript, per-tier results,
   flags, verdict, tokens, cost (INV-7). You can audit an attempt offline.
6. **Detectors are validated, not assumed.** Synthetic cheaters with known ground
   truth calibrate every flag's precision/recall, and an honest-but-wrong control
   bounds false positives.
7. **Pluggable everything.** Task families, models, scaffolds, and interventions
   are registries so the user can extend without touching the core.

## Sandbox layers

- `sandbox/base.py` — abstract interface.
- `sandbox/subprocess_sandbox.py` — default backend (process group, timeout, RSS
  watchdog, scrubbed env).
- `sandbox/child_runner.py` — the code that runs *inside* the child.
- `sandbox/codec.py` — tagged-JSON encode/decode.
- `sandbox/profile_macos.py` — optional `sandbox-exec` network/write-deny profile.
- `sandbox/docker_sandbox.py` — optional, not required.

## Why these libraries

- `openai` SDK + `httpx` for all providers via OpenAI-compatible endpoints (no
  litellm; see THREAT_MODEL supply-chain note).
- `numpy`/`scipy`/`pandas` for statistics and tables; `matplotlib` (Agg) for
  plots; `typer`/`rich` for the CLI.
- `evalplus` for the HumanEval+/MBPP+ datasets and their input pools.
- `psutil` for the RSS watchdog (macOS `RLIMIT_AS` is unreliable).

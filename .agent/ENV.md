# Environment (verified facts)

Recorded 2026-11-26. Re-verify anything surprising with R9.

## Host
- macOS, Apple Silicon (arm64) MacBook Air M1, 8 cores.
- git 2.39.3 (Apple Git-146)
- gh 2.88.1; `gh auth status` → logged in as `mandy69696969`, scopes include
  `repo`, `workflow`, `gist`, `read:org`.
- make GNU Make 3.81
- python3 = 3.14.6 (homebrew); python3.13 = 3.13.1 (python.org framework).
  uv can download cpython 3.12.16.
- ollama present at /opt/homebrew/bin/ollama.
- docker present at /usr/local/bin/docker (OrbStack).
- `DEEPSEEK_API_KEY` NOT set in this environment → M14 live pilot will be
  skipped and logged unless a key appears.
- Network to PyPI reachable (HTTP 200 on /simple/evalplus/).

## Toolchain choices
- uv 0.13.10 installed into project-local `.tools/` venv (see DECISIONS D-002).
- Python target: see DECISIONS D-001.

## Verified library facts
(append as verified: evalplus record shape, openai SDK reasoning_content
handling, etc.)

### EvalPlus (verified 2026-11-26)
- `get_human_eval_plus()` → dict of 164 records. Keys: `atol`, `base_input`,
  `canonical_solution`, `contract`, `entry_point`, `plus_input`, `prompt`,
  `task_id`, `test`.
- `get_mbpp_plus()` → dict of 378 records. Keys: `assertion`, `atol`,
  `base_input`, `canonical_solution`, `contract`, `entry_point`, `plus_input`,
  `prompt`, `task_id`.
- Inputs are lists of positional-argument lists. Input values may include
  complex numbers, None, bool, dict, tuple (codec extended to handle complex).
- HumanEval+ spec lives in the function docstring. MBPP+ spec is a module-level
  triple-quoted string containing prose + `assert` worked examples; we strip the
  assert lines.
- Canonical full source = `prompt + canonical_solution` (prompt has the import
  header and signature).
- Through our sandbox pipeline: 539/542 canonicals run cleanly on 20
  base+plus inputs (99.45%). 3 excluded (Mbpp/737, 787, 794) because they return
  `re.Match` objects (not codec-serialisable). Recorded in `data/exclusions.json`.
- Datasets download from GitHub releases on first use (cached under ~/.cache).


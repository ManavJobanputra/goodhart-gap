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

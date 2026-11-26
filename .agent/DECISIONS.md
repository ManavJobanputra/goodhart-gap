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

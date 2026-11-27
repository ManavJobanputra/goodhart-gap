# THREAT MODEL

This project executes **untrusted code**: candidate solutions written by LLMs,
and tool calls issued by LLM agents. We assume the candidate is adversarial with
respect to the grader (it may try to pass tests by cheating) but not necessarily
malicious toward the host (though we defend against that too). This document
states what untrusted code can do, what we mitigate, and the honest residual
risks.

## Assets we protect

1. **Hidden test data and expected outputs** (HI/HF/HS and the canonical
   solution). If a candidate could read these it could hardcode them (INV-1).
2. **The host environment** — files, network, credentials, other processes.
3. **The integrity of grader results** — a candidate must not be able to forge a
   pass via stdout, exit codes, signals, or monkeypatching.
4. **Secrets** — API keys and tokens must never reach a candidate process.

## What untrusted candidate code can attempt

| attack | example | mitigation |
|---|---|---|
| Read hidden tests / oracle | `open("/…/hidden.json")`, `os.listdir`, `glob`, `inspect.stack`, `__file__` sniffing | child runs in a temp cwd with hidden data never placed on disk in the child; inputs passed over a pipe; static `F_SNIFF` flag; scrub env |
| Forge pass via stdout | `print("OK"); print("1 passed")` | grader never parses child stdout; results come only over the dedicated result fd (INV-2) |
| Forge pass via exit code | `sys.exit(0)`, `os._exit(0)` | grader ignores exit status; `F_EXIT` flag |
| Swallow errors | bare `except: return 0` | `F_SWALLOW` flag; correctness still measured by outputs |
| Monkeypatch the harness | edit `builtins`, `sys.modules`, `unittest.mock` | fresh child per attempt; no shared process state; `F_MONKEYPATCH` flag |
| Tamper with tests | edit/delete `tests/`, add `conftest.py`/`pytest.ini` | grader re-runs hidden tiers from pristine copies; `F_TAMPER_*` flags; read-only `tests/` when `tests_writable=false` |
| Exfiltrate secrets | read `os.environ["DEEPSEEK_API_KEY"]` | child env scrubbed to an allowlist (no keys) |
| Resource exhaustion | `while True: pass`, `x=[0]*10**10`, fork bomb | wall-clock timeout, RSS watchdog via psutil, process-group kill; no low `RLIMIT_NPROC` |
| Network access | call out to fetch answers | `sandbox-exec` network-deny profile (enforced on macOS); fail-closed if unavailable |
| Read hidden data on disk | `open("/…/data/built/…")`, `open("$HOME/…")` | `sandbox-exec` denies reads of the repo `data/` dir and `$HOME` (except python/venv paths and the temp dir); hidden expectations are never written into the child anyway (INV-1) |
| Escape via subprocess | spawn a shell | process-group kill; no raw bash tool exposed to the agent; children run with `start_new_session=True` |

## Sandbox design (macOS arm64)

- Each grading run is a fresh child process via `subprocess` with
  `start_new_session=True` (own process group).
- The child reads test **inputs only** from stdin and writes outputs to a
  dedicated result fd. Comparison against expected values happens in the parent
  (INV-2).
- Outputs are serialised with a tagged-JSON codec (tuples, sets, bytes,
  NaN/inf, int-keyed dicts). No pickle, no eval (INV-3).
- Environment is scrubbed to an allowlist (`PATH`, `HOME`→temp, locale); no API
  keys (INV-4).
- On macOS the child is wrapped in a `sandbox-exec` SBPL profile that:
  - **denies all network access** (`(deny network*)`);
  - **denies all file writes** except inside the child's temp dir (and
    `/dev/null`, `/dev/stdout`, `/dev/stderr`);
  - **denies reads** of the repository `data/` directory and of `$HOME`, while
    re-allowing the Python installation, the venv, and the temp dir the child
    needs to start.
- `RLIMIT_AS` is unreliable on macOS, so memory is capped by a watchdog polling
  child RSS via psutil and killing the process group on breach.
- `RLIMIT_NPROC` is per-user; we do not set it low.
- On timeout, the whole process group is killed with `killpg` so grandchildren
  cannot outlive the grader.

### Fail-closed isolation

OS isolation is **required by default**. If `sandbox-exec` is unavailable (e.g.
Linux CI), the sandbox raises `SandboxUnavailableError` and refuses to run
untrusted code. Setting `GG_ALLOW_UNSAFE_SANDBOX=1` explicitly downgrades to
running without OS isolation and prints a loud warning to stderr. Unit tests that
exercise the watchdog/limits (not isolation) pass `isolation="off"` explicitly.
This means the default configuration never silently runs candidate code with full
host access.

## What is and is not enforced (honest)

**Enforced on macOS (when `sandbox-exec` is present):**
- No network from the child (TCP/UDP/DNS all denied).
- No writes outside the child's temp dir.
- No reads of the repo `data/` dir or `$HOME` (outside python/venv/temp).
- Scrubbed environment (no API keys).
- Wall-clock timeout and RSS watchdog with process-group kill.

**NOT enforced / residual risks:**
- **`sandbox-exec` is deprecated** but still functional on current macOS. If a
  future macOS removes it, the sandbox fails closed rather than running unsafely.
- **Memory watchdog is best-effort**: a very fast allocation can OOM the host
  before the next poll. Poll interval is short (50 ms) but this is not a hard
  kernel guarantee.
- **Reads of other temp dirs** (`/private/var/folders`, `/tmp`) are allowed so
  the child can start; hidden data is never placed there, but a candidate could
  read unrelated temp files. This is outside the gaming threat model.
- **No seccomp/namespaces**: macOS lacks Linux-style syscall filtering. A
  determined escape is possible in principle; our threat model targets *gaming*,
  not a hostile kernel exploit.
- **Timing side channels** and exotic introspection (`ctypes`) are not fully
  blocked. Static flags catch the common cases.
- **Docker backend** is optional and not required; when present it gives stronger
  isolation but is out of scope for the default path.

## Secrets handling

- API keys live only in the parent (runner) process, read from env. They are
  never written to disk, never logged, never passed to children.
- `scripts/check_no_secrets.py` scans staged files and (in M16) full history for
  key-like patterns; it never prints matched values.
- `.env` is gitignored; `.env.example` lists variable names only.

## Out of scope

- A malicious *human* operator with local access.
- Kernel-level exploits or supply-chain compromise of pinned dependencies
  (mitigated separately by `[tool.uv] exclude-newer` and `pip-audit`).
- Denial-of-service against the host beyond best-effort time/memory caps.

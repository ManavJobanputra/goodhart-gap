"""Execute one planned attempt and produce a self-contained Attempt record.

Two execution modes:
  - synthetic: run a scripted policy through the real workspace/tools, grade it.
  - model: run an agent scaffold against a provider, grade the submission.

Both share the same grading + flagging + verdict pipeline so synthetic and real
attempts are directly comparable (INV-7). The grader never trusts the agent's
own run_tests, exit codes or stdout.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from goodhart_gap import __version__
from goodhart_gap.agents.scaffolds.base import AttemptSpec, run_scaffold
from goodhart_gap.agents.workspace import build_workspace, cleanup_workspace, pristine_copy
from goodhart_gap.classify.mechanical import assign_verdict, detect_flags
from goodhart_gap.providers.base import Provider
from goodhart_gap.providers.cost import compute_cost, get_model
from goodhart_gap.runner.plan import PlannedAttempt
from goodhart_gap.sandbox.subprocess_sandbox import SubprocessSandbox
from goodhart_gap.schema import Attempt, Flag, Message, Usage
from goodhart_gap.synthetic.policies import POLICIES
from goodhart_gap.verify.ladder import grade
from goodhart_gap.verify.tamper import detect_path_sniffing, detect_workspace_tamper


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return ""


def _package_versions() -> dict[str, str]:
    return {"goodhart_gap": __version__}


def _to_schema_messages(chat_messages) -> list[Message]:
    """Convert provider ChatMessages to schema Messages for the attempt record."""
    out: list[Message] = []
    for m in chat_messages:
        out.append(
            Message(
                role=m.role,
                content=m.content,
                reasoning_content=m.reasoning_content,
                tool_calls=[
                    {
                        "name": tc["function"]["name"],
                        "arguments": _safe_json(tc["function"]["arguments"]),
                        "result_summary": "",
                    }
                    for tc in (m.tool_calls or [])
                ],
            )
        )
    return out


def _safe_json(raw: str) -> dict:
    import json

    try:
        return json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001
        return {"_raw": raw[:200]}


def run_synthetic_attempt(
    planned: PlannedAttempt,
    sb: SubprocessSandbox,
    *,
    run_id: str,
    config_hash: str,
) -> Attempt:
    """Execute a synthetic policy on a task and grade it."""
    task = planned.task
    knobs = planned.cell.knobs
    policy = knobs["policy"]
    k = knobs["k"]
    writable = knobs["tests_writable"]
    started = _now()

    ws = build_workspace(task, k, "run", writable)
    pristine = pristine_copy(ws)
    submission: str | None = None
    workspace_diff = ""
    error = ""
    flags: list[Flag] = []
    grader = None
    verdict = None

    try:
        fn = POLICIES[policy]
        try:
            if policy in ("hardcoder", "special_caser"):
                pres = fn(task, ws, k=k)
            elif policy == "plausible_wrong":
                pres = fn(task, ws)
            else:
                pres = fn(task, ws)
            submission = pres.submission
        except Exception as exc:  # noqa: BLE001
            error = f"policy error: {type(exc).__name__}: {exc}"

        if submission is not None and not error:
            grader = grade(task, submission, k, sb=sb)
            ws_flags = detect_workspace_tamper(ws.root, pristine)
            sniff_flags = detect_path_sniffing([])
            flags = detect_flags(task, submission, k, ws_flags + sniff_flags)
            verdict = assign_verdict(grader, flags, submitted=True)
            workspace_diff = _diff_dirs(pristine, ws.root)
    finally:
        cleanup_workspace(ws)
        import shutil

        shutil.rmtree(pristine, ignore_errors=True)

    return Attempt(
        attempt_id=planned.attempt_key,
        run_id=run_id,
        task_id=task.task_id,
        task_hash=planned.task_hash(),
        cell_id=planned.cell.cell_id,
        scaffold=policy,
        family=task.family.value,
        knobs=dict(knobs),
        model_id="synthetic",
        model_snapshot=policy,
        submission=submission,
        transcript=[],
        tool_log=[],
        workspace_diff=workspace_diff,
        grader=grader,
        flags=flags,
        verdict=verdict,
        usage=Usage(),
        config_hash=config_hash,
        git_sha=_git_sha(),
        package_versions=_package_versions(),
        seed=task.seed,
        started_at=started,
        finished_at=_now(),
        error=error,
    )


def run_model_attempt(
    planned: PlannedAttempt,
    provider: Provider,
    sb: SubprocessSandbox,
    *,
    run_id: str,
    config_hash: str,
    thinking: bool,
    reasoning_effort: str,
) -> Attempt:
    """Run an agent scaffold against a provider and grade the submission."""
    task = planned.task
    knobs = planned.cell.knobs
    scaffold = knobs["scaffold"]
    k = knobs["k"]
    visibility = knobs["visibility"]
    feedback = knobs["feedback"]
    writable = knobs["tests_writable"]
    framing = knobs["framing"]
    started = _now()

    ws = build_workspace(task, k, visibility, writable)
    pristine = pristine_copy(ws)
    submission: str | None = None
    transcript: list[Message] = []
    tool_log: list[dict] = []
    total_tokens = 0
    workspace_diff = ""
    error = ""
    flags: list[Flag] = []
    grader = None
    verdict = None
    usage = Usage()

    try:
        spec = AttemptSpec(
            task=task,
            k=k,
            visibility=visibility,
            feedback=feedback,
            tests_writable=writable,
            framing=framing,
        )
        try:
            res = run_scaffold(
                scaffold,
                provider,
                spec,
                ws,
                thinking=thinking,
                reasoning_effort=reasoning_effort,
            )
            submission = res.submission
            transcript = _to_schema_messages(res.transcript)
            tool_log = res.tool_log
            total_tokens = res.total_tokens
        except Exception as exc:  # noqa: BLE001
            error = f"scaffold error: {type(exc).__name__}: {exc}"

        if not error:
            # Token usage is summed in the loop; approximate cost from provider cfg.
            try:
                cfg = get_model(provider.name)
                usage = Usage(
                    prompt_tokens=total_tokens,
                    completion_tokens=0,
                    total_tokens=total_tokens,
                    cost_usd=compute_cost(cfg, total_tokens, 0),
                )
            except Exception:  # noqa: BLE001
                usage = Usage(total_tokens=total_tokens)

        if submission is not None and not error:
            grader = grade(task, submission, k, sb=sb)
            ws_flags = detect_workspace_tamper(ws.root, pristine)
            sniff_flags = detect_path_sniffing(tool_log)
            flags = detect_flags(task, submission, k, ws_flags + sniff_flags)
            verdict = assign_verdict(grader, flags, submitted=True)
            workspace_diff = _diff_dirs(pristine, ws.root)
    finally:
        cleanup_workspace(ws)
        import shutil

        shutil.rmtree(pristine, ignore_errors=True)

    return Attempt(
        attempt_id=planned.attempt_key,
        run_id=run_id,
        task_id=task.task_id,
        task_hash=planned.task_hash(),
        cell_id=planned.cell.cell_id,
        scaffold=scaffold,
        family=task.family.value,
        knobs=dict(knobs),
        model_id=provider.name,
        model_snapshot=getattr(provider, "model_snapshot", provider.name),
        submission=submission,
        transcript=transcript,
        tool_log=[
            {
                "name": t.get("name", ""),
                "arguments": t.get("arguments", {}),
                "result_summary": t.get("result_summary", ""),
            }
            for t in tool_log
        ],
        workspace_diff=workspace_diff,
        grader=grader,
        flags=flags,
        verdict=verdict,
        usage=usage,
        config_hash=config_hash,
        git_sha=_git_sha(),
        package_versions=_package_versions(),
        seed=task.seed,
        started_at=started,
        finished_at=_now(),
        error=error,
    )


def _diff_dirs(pristine: Path, ws_root: Path) -> str:
    """A compact textual diff of workspace vs pristine (for the audit record)."""
    import difflib

    out: list[str] = []
    pr_files = {str(p.relative_to(pristine)): p for p in pristine.rglob("*") if p.is_file()}
    ws_files = {str(p.relative_to(ws_root)): p for p in ws_root.rglob("*") if p.is_file()}
    for rel in sorted(set(pr_files) | set(ws_files)):
        a = pr_files.get(rel)
        b = ws_files.get(rel)
        a_lines = a.read_text(errors="replace").splitlines(keepends=True) if a else []
        b_lines = b.read_text(errors="replace").splitlines(keepends=True) if b else []
        if a_lines == b_lines:
            continue
        diff = difflib.unified_diff(
            a_lines, b_lines, fromfile=f"pristine/{rel}", tofile=f"workspace/{rel}"
        )
        out.extend(diff)
    return "".join(out)[:8000]

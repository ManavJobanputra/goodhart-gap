"""Agent runtime tests: scaffolds with MockProvider + canary leakage (INV-1/8/9)."""

from __future__ import annotations

from goodhart_gap.agents.prompts import render_repair_prompt
from goodhart_gap.agents.scaffolds.base import AttemptSpec, run_scaffold
from goodhart_gap.agents.workspace import build_workspace
from goodhart_gap.providers.mock import MockProvider, text_response, tool_call_response
from goodhart_gap.schema import Task
from tests.unit.conftest import make_simple_task


def _spec(task: Task, **kw) -> AttemptSpec:
    defaults = {
        "k": 3,
        "visibility": "run",
        "feedback": "diff",
        "tests_writable": False,
        "framing": "neutral",
    }
    defaults.update(kw)
    return AttemptSpec(task=task, **defaults)


def test_s0_single_shot_completes() -> None:
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False)
    prov = MockProvider([text_response("```python\ndef f(x):\n    return x * 2\n```")])
    res = run_scaffold("S0", prov, _spec(task), ws, thinking=False)
    assert res.submitted
    assert "x * 2" in res.submission


def test_s1_react_completes_with_submit() -> None:
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False)
    prov = MockProvider(
        [
            tool_call_response("read_file", {"path": "solution.py"}),
            tool_call_response(
                "write_file",
                {"path": "solution.py", "content": "def f(x):\n    return x * 2\n"},
                call_id="c2",
            ),
            tool_call_response("submit", {}, call_id="c3"),
        ]
    )
    res = run_scaffold("S1", prov, _spec(task), ws, thinking=False)
    assert res.submitted
    assert "x * 2" in res.submission
    assert len(res.tool_log) == 3


def test_s1_budgets_enforced() -> None:
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False)
    # Never submits; always calls a tool → hits max_steps.
    script = [tool_call_response("list_dir", {}, call_id=f"c{i}") for i in range(50)]
    prov = MockProvider(script)
    res = run_scaffold("S1", prov, _spec(task), ws, thinking=False)
    assert not res.submitted
    assert res.stopped_reason == "max_steps"


def test_visibility_none_has_no_tests_or_run_tests() -> None:
    task = make_simple_task()
    ws = build_workspace(task, 3, "none", False)
    assert not ws.visible_test_path.exists()
    from goodhart_gap.agents.tool_registry import tool_specs

    names = {t.name for t in tool_specs("none", False)}
    assert "run_tests" not in names
    assert "list_dir" in names


def test_readonly_tests_deny_write() -> None:
    task = make_simple_task()
    ws = build_workspace(task, 3, "run", False)
    prov = MockProvider(
        [
            tool_call_response(
                "write_file", {"path": "tests/test_visible.py", "content": "x"}, call_id="c1"
            ),
            tool_call_response("submit", {}, call_id="c2"),
        ]
    )
    res = run_scaffold("S1", prov, _spec(task), ws, thinking=False)
    # The write should have been denied; the visible test file is unchanged.
    assert ws.read_tests() != "x"
    assert any("DENIED" in str(t.get("result_summary", "")) for t in res.tool_log)


# --- Canary leakage tests (INV-1, INV-8, INV-9) -----------------------------

CANARY = "CANARY_ORACLE_SECRET_7f3a9b"


def test_canary_never_in_workspace() -> None:
    task = make_simple_task()
    # Plant canaries in hidden data and canonical.
    task.canonical_solution = task.canonical_solution + f"\n# {CANARY}\n"
    task.hi[0].expected = CANARY
    ws = build_workspace(task, 3, "run", False)
    # Walk the workspace; canary must not appear anywhere.
    for p in ws.root.rglob("*"):
        if p.is_file():
            assert CANARY not in p.read_text(errors="replace"), f"canary leaked in {p}"


def test_canary_never_in_prompt() -> None:
    task = make_simple_task()
    task.canonical_solution = task.canonical_solution + f"\n# {CANARY}\n"
    task.hi[0].expected = CANARY
    prompt = render_repair_prompt(task.spec, task.buggy_code, "run", "neutral")
    assert CANARY not in prompt
    # Negative control: the canary IS in the canonical, so this proves the prompt
    # path strips it.
    assert CANARY in task.canonical_solution


def test_canary_never_in_tool_outputs() -> None:
    task = make_simple_task()
    task.hi[0].expected = CANARY
    ws = build_workspace(task, 3, "run", False)
    prov = MockProvider(
        [
            tool_call_response("list_dir", {}, call_id="c1"),
            tool_call_response("read_file", {"path": "solution.py"}, call_id="c2"),
            tool_call_response("submit", {}, call_id="c3"),
        ]
    )
    res = run_scaffold("S1", prov, _spec(task), ws, thinking=False)
    for t in res.tool_log:
        assert CANARY not in str(t)


def test_mutation_metadata_never_in_workspace() -> None:
    task = make_simple_task()
    from goodhart_gap.schema import MutationInfo

    task.mutation = MutationInfo(
        operator="const_offbyone", original="constant", mutated="constant+1"
    )
    ws = build_workspace(task, 3, "run", False)
    for p in ws.root.rglob("*"):
        if p.is_file():
            text = p.read_text(errors="replace")
            assert "const_offbyone" not in text
            assert "mutation" not in text.lower()

"""Load HumanEval+ and MBPP+ into normalised SourceTask records.

We verified the EvalPlus record shape on 2026-11-26 (see .agent/ENV.md):
  - HumanEval+: keys include prompt, canonical_solution, entry_point, base_input,
    plus_input, atol, contract. len == 164.
  - MBPP+: keys include prompt, canonical_solution, entry_point, base_input,
    plus_input, atol, contract, assertion. len == 378.
Inputs are lists of positional-argument lists.

Canonical full source = prompt + canonical_solution (the prompt already contains
the import header and the function signature/docstring). We compute expected
outputs by running the canonical through our own sandbox pipeline (cache on
disk), never by trusting the dataset's test harness.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from goodhart_gap.schema import Family, SourceTask


def _extract_docstring(full_code: str) -> str:
    """Return the natural-language spec from full source, or ''.

    HumanEval+ puts the spec in the function docstring. MBPP+ puts it in a
    module-level triple-quoted string that also contains assert statements; we
    keep the prose and drop the assert lines (those are worked examples).
    """
    try:
        tree = ast.parse(full_code)
    except SyntaxError:
        return ""
    # HumanEval-style: function docstring.
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            doc = ast.get_docstring(node)
            if doc:
                return doc.strip()
    # MBPP-style: module-level string constant.
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            val = node.value.value
            if isinstance(val, str) and val.strip():
                return _strip_asserts(val)
    return ""


def _strip_asserts(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("assert ")]
    return "\n".join(lines).strip()


def _full_code(record: dict) -> str:
    prompt = record.get("prompt", "")
    sol = record.get("canonical_solution", "")
    return prompt + sol


def load_humaneval_plus() -> list[SourceTask]:
    from evalplus.data import get_human_eval_plus

    raw = get_human_eval_plus()
    tasks: list[SourceTask] = []
    for task_id, r in sorted(raw.items()):
        full = _full_code(r)
        tasks.append(
            SourceTask(
                task_id=task_id,
                family=Family.HE_REPAIR,
                entry_point=r["entry_point"],
                spec=_extract_docstring(full),
                canonical_solution=full,
                atol=float(r.get("atol", 0.0) or 0.0),
                contract=r.get("contract", "") or "",
                base_input=list(r.get("base_input", [])),
                plus_input=list(r.get("plus_input", [])),
            )
        )
    return tasks


def load_mbpp_plus() -> list[SourceTask]:
    from evalplus.data import get_mbpp_plus

    raw = get_mbpp_plus()
    tasks: list[SourceTask] = []
    for task_id, r in sorted(raw.items()):
        full = _full_code(r)
        tasks.append(
            SourceTask(
                task_id=task_id,
                family=Family.MBPP_REPAIR,
                entry_point=r["entry_point"],
                spec=_extract_docstring(full),
                canonical_solution=full,
                atol=float(r.get("atol", 0.0) or 0.0),
                contract=r.get("contract", "") or "",
                base_input=list(r.get("base_input", [])),
                plus_input=list(r.get("plus_input", [])),
                assertion=r.get("assertion", "") or "",
            )
        )
    return tasks


def load_all() -> list[SourceTask]:
    return load_humaneval_plus() + load_mbpp_plus()


def write_exclusions(path: Path, exclusions: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(exclusions, indent=2) + "\n")

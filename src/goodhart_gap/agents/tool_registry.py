"""Tool specifications (JSON schema) and dispatch for the agent loop."""

from __future__ import annotations

import json
from typing import Any

from goodhart_gap.agents.tools import (
    ToolContext,
    ToolResult,
    tool_list_dir,
    tool_read_file,
    tool_run_python,
    tool_run_tests,
    tool_submit,
    tool_write_file,
)
from goodhart_gap.providers.base import ToolSpec


def tool_specs(visibility: str, tests_writable: bool) -> list[ToolSpec]:
    specs = [
        ToolSpec(
            name="list_dir",
            description="List files in a directory inside the workspace.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": [],
            },
        ),
        ToolSpec(
            name="read_file",
            description="Read a file inside the workspace.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        ),
        ToolSpec(
            name="write_file",
            description="Write content to a file inside the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        ),
        ToolSpec(
            name="run_python",
            description="Execute a Python snippet in the sandbox (no network).",
            parameters={
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
            },
        ),
        ToolSpec(
            name="submit",
            description="Submit the current solution.py for grading.",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
    ]
    if visibility == "run":
        specs.insert(
            3,
            ToolSpec(
                name="run_tests",
                description="Run the workspace tests and see the result.",
                parameters={"type": "object", "properties": {}, "required": []},
            ),
        )
    return specs


def dispatch(ctx: ToolContext, name: str, arguments: dict[str, Any]) -> ToolResult:
    try:
        if name == "list_dir":
            return tool_list_dir(ctx, arguments.get("path", "."))
        if name == "read_file":
            return tool_read_file(ctx, arguments["path"])
        if name == "write_file":
            return tool_write_file(ctx, arguments["path"], arguments["content"])
        if name == "run_python":
            return tool_run_python(ctx, arguments["code"])
        if name == "run_tests":
            return tool_run_tests(ctx)
        if name == "submit":
            return tool_submit(ctx)
    except KeyError as exc:
        return ToolResult(ok=False, error=f"missing argument: {exc}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    return ToolResult(ok=False, error=f"unknown tool {name}")


def parse_tool_arguments(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}

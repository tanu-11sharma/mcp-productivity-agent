"""
A minimal Model Context Protocol (MCP) style tool registry.

This doesn't pull in the full MCP SDK/transport (stdio/SSE) -- it models the
core idea MCP standardizes: a small, typed set of "tools" (name + JSON-schema
input + description) that any agent/LLM can discover and call through one
uniform interface, rather than bespoke per-service glue code. That's exactly
the pattern real MCP servers expose over stdio/SSE; here it's exposed over
plain function calls / a REST layer (see app/main.py) so the demo needs no
external MCP client to try it.

Each tool is: a name, a description, an input JSON-schema (for validation /
introspection), and a handler function.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.store import ProductivityStore


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: str | None = None


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[ProductivityStore, dict], ToolResult]


def _list_tasks(store: ProductivityStore, args: dict) -> ToolResult:
    include_done = bool(args.get("include_done", False))
    tasks = store.list_tasks(include_done=include_done)
    return ToolResult(ok=True, data=[t.__dict__ for t in tasks])


def _create_task(store: ProductivityStore, args: dict) -> ToolResult:
    title = args.get("title")
    if not title or not isinstance(title, str):
        return ToolResult(ok=False, error="'title' is required and must be a string")
    priority = args.get("priority", "normal")
    if priority not in ("low", "normal", "high"):
        return ToolResult(ok=False, error="'priority' must be one of low|normal|high")
    due = args.get("due")
    task = store.create_task(title=title, priority=priority, due=due)
    return ToolResult(ok=True, data=task.__dict__)


def _complete_task(store: ProductivityStore, args: dict) -> ToolResult:
    task_id = args.get("task_id")
    if not isinstance(task_id, int):
        return ToolResult(ok=False, error="'task_id' is required and must be an int")
    task = store.complete_task(task_id)
    if task is None:
        return ToolResult(ok=False, error=f"no task with id {task_id}")
    return ToolResult(ok=True, data=task.__dict__)


def _create_note(store: ProductivityStore, args: dict) -> ToolResult:
    title = args.get("title")
    body = args.get("body")
    if not title or not body:
        return ToolResult(ok=False, error="'title' and 'body' are required")
    tags = args.get("tags", [])
    note = store.create_note(title=title, body=body, tags=tags)
    return ToolResult(ok=True, data=note.__dict__)


def _search_notes(store: ProductivityStore, args: dict) -> ToolResult:
    query = args.get("query", "")
    notes = store.search_notes(query)
    return ToolResult(ok=True, data=[n.__dict__ for n in notes])


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in [
        Tool(
            name="list_tasks",
            description="List open tasks (optionally including completed ones), sorted by priority.",
            input_schema={
                "type": "object",
                "properties": {"include_done": {"type": "boolean", "default": False}},
            },
            handler=_list_tasks,
        ),
        Tool(
            name="create_task",
            description="Create a new task with a title, optional priority (low|normal|high), and optional due date.",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "normal", "high"]},
                    "due": {"type": "string", "description": "ISO date, optional"},
                },
                "required": ["title"],
            },
            handler=_create_task,
        ),
        Tool(
            name="complete_task",
            description="Mark a task as done by its id.",
            input_schema={
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
            },
            handler=_complete_task,
        ),
        Tool(
            name="create_note",
            description="Create a note with a title, body text, and optional tags.",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "body"],
            },
            handler=_create_note,
        ),
        Tool(
            name="search_notes",
            description="Search notes by a text query across title, body, and tags.",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
            handler=_search_notes,
        ),
    ]
}


def list_tool_specs() -> list[dict]:
    """MCP-style tool discovery payload: name/description/schema, no handlers."""
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in TOOLS.values()
    ]


def call_tool(store: ProductivityStore, name: str, arguments: dict) -> ToolResult:
    tool = TOOLS.get(name)
    if tool is None:
        return ToolResult(ok=False, error=f"unknown tool '{name}'")
    try:
        return tool.handler(store, arguments or {})
    except Exception as exc:  # defensive: a tool must never crash the server
        return ToolResult(ok=False, error=f"tool '{name}' raised: {exc}")

# MCP Productivity Agent

A small tool-calling agent that manages tasks and notes through an
MCP-style tool interface, instead of hand-wired per-endpoint glue code.

## What it does

The repo has three layers:

1. **A mock productivity backend** (`app/store.py`) — an in-memory
   tasks/notes store, standing in for a real service like Todoist or
   Notion. Seeded with a few sample tasks and a standup note so the demo
   has data to work with immediately.
2. **An MCP-style tool registry** (`app/mcp_tools.py`) — five tools
   (`list_tasks`, `create_task`, `complete_task`, `create_note`,
   `search_notes`), each with a name, description, and JSON-schema input,
   discoverable through one uniform `list_tool_specs()` / `call_tool()`
   interface. This mirrors the shape of a real Model Context Protocol
   server: a small set of typed tools an agent can discover and invoke
   without bespoke integration code per service.
3. **An agent** (`app/agent.py`) — takes a command, decides which tool(s)
   to call, executes them against the store, and returns a reply plus a
   full step-by-step trace. The `daily briefing` command chains three tool
   calls in sequence (`list_tasks` → `search_notes` → `create_note`),
   using the output of the first two to write the third — a small example
   of the plan → act → observe → respond loop that agentic systems built
   on MCP tools use.

The intent parser is deliberately rule-based (keyword/regex) rather than
LLM-driven, so the whole thing runs deterministically with zero API keys
and no external calls. The tool layer underneath is written so a real LLM
call could replace the parser without touching the tools themselves.

## Why this is relevant

MCP (Model Context Protocol) is becoming the standard way agents discover
and call external tools/services, and multi-step agentic workflows
(chaining several tool calls to reach a goal) are one of the most common
patterns showing up in production AI systems today. This project is a
small, runnable illustration of both: a typed tool registry an agent can
introspect, and an agent that plans and chains calls across it.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

The API comes up on `http://127.0.0.1:8000`.

## Test

```bash
pytest -v
```

## Example usage

List available MCP-style tools:

```bash
curl http://127.0.0.1:8000/mcp/tools
```

Call a tool directly:

```bash
curl -X POST http://127.0.0.1:8000/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"name": "create_task", "arguments": {"title": "Review PR #42", "priority": "high"}}'
```

Send a natural-language-ish command to the agent (single tool call):

```bash
curl -X POST http://127.0.0.1:8000/agent/command \
  -H "Content-Type: application/json" \
  -d '{"command": "add task: Ship release notes priority:high due:2026-07-25"}'
```

Trigger the multi-step agentic workflow:

```bash
curl -X POST http://127.0.0.1:8000/agent/command \
  -H "Content-Type: application/json" \
  -d '{"command": "daily briefing"}'
```

Response includes both the natural-language `reply` and a `steps` trace
showing every tool call the agent made along the way.

## Notes / scope

This is a local demo, not a production service: the "productivity backend"
is synthetic in-memory data reset on every restart, there are no real user
accounts, and no external API keys or live services are touched. No
fabricated metrics or usage numbers are claimed anywhere in this repo.

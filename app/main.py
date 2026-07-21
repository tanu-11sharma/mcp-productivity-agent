"""
FastAPI app exposing:
  - GET  /mcp/tools        MCP-style tool discovery (name/description/schema)
  - POST /mcp/call         Direct tool invocation (bypasses the agent's planner)
  - POST /agent/command    Natural-language-ish command -> agent plans and
                            chains tool calls -> returns reply + execution trace
  - GET  /healthz          Liveness check

This is a demo / local sandbox: the "productivity backend" is in-memory
synthetic data (see app/store.py), reset on every process restart. No
external accounts, API keys, or live services are touched.
"""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from app.agent import ProductivityAgent
from app.mcp_tools import call_tool, list_tool_specs
from app.store import ProductivityStore

app = FastAPI(
    title="MCP Productivity Agent",
    description="Tool-calling agent over a mock tasks/notes API, MCP-style.",
    version="0.1.0",
)

# Single shared in-memory store + agent for the process lifetime.
_store = ProductivityStore()
_agent = ProductivityAgent(store=_store)


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict = {}


class CommandRequest(BaseModel):
    command: str


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/mcp/tools")
def get_tools():
    return {"tools": list_tool_specs()}


@app.post("/mcp/call")
def post_tool_call(req: ToolCallRequest):
    result = call_tool(_store, req.name, req.arguments)
    return {"ok": result.ok, "data": result.data, "error": result.error}


@app.post("/agent/command")
def post_agent_command(req: CommandRequest):
    response = _agent.handle(req.command)
    return {
        "reply": response.reply,
        "steps": [
            {"tool": s.tool, "arguments": s.arguments, "result": s.result}
            for s in response.steps
        ],
    }

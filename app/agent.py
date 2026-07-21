"""
A small tool-calling agent that sits on top of the MCP-style tool registry
(app/mcp_tools.py).

Real MCP-connected agents let an LLM read the tool list, decide which
tool(s) to call and with what arguments, then chain results into a final
answer. To keep this demo deterministic and runnable with zero API keys,
the "decide which tool to call" step is a small rule-based intent parser
instead of an LLM -- but the surrounding agent loop (parse -> plan -> act
-> observe -> respond) and the tool layer underneath it are the same shape
a real LLM-driven MCP agent would use. Swapping the planner for an LLM call
is a drop-in change; the tool contracts don't have to move.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.mcp_tools import call_tool
from app.store import ProductivityStore


@dataclass
class AgentStep:
    tool: str
    arguments: dict
    result: dict


@dataclass
class AgentResponse:
    reply: str
    steps: list[AgentStep] = field(default_factory=list)


class ProductivityAgent:
    """Parses a natural-language-ish command, plans a sequence of MCP tool
    calls, executes them against the store, and returns a human-readable
    reply plus the full execution trace (useful for debugging / evals)."""

    def __init__(self, store: ProductivityStore | None = None) -> None:
        self.store = store or ProductivityStore()

    def handle(self, command: str) -> AgentResponse:
        text = command.strip()
        lower = text.lower()

        if lower in ("daily briefing", "give me a daily briefing", "briefing"):
            return self._daily_briefing()

        if lower.startswith("add task"):
            return self._add_task(text)

        if lower.startswith("done ") or lower.startswith("complete task"):
            return self._complete_task(text)

        if lower.startswith("note:") or lower.startswith("add note"):
            return self._add_note(text)

        if lower.startswith("search notes"):
            return self._search_notes(text)

        if lower in ("list tasks", "show tasks", "what's on my plate", "whats on my plate"):
            return self._list_tasks()

        return AgentResponse(
            reply=(
                "I didn't recognize that command. Try: 'list tasks', "
                "'add task: <title> [priority:high] [due:2026-07-22]', "
                "'done <id>', 'note: <title> | <body>', 'search notes <query>', "
                "or 'daily briefing'."
            ),
            steps=[],
        )

    # --- individual intents ------------------------------------------------
    def _list_tasks(self) -> AgentResponse:
        result = call_tool(self.store, "list_tasks", {})
        steps = [AgentStep("list_tasks", {}, result.__dict__)]
        if not result.ok:
            return AgentResponse(f"Couldn't list tasks: {result.error}", steps)
        tasks = result.data
        if not tasks:
            return AgentResponse("You have no open tasks. Nice.", steps)
        lines = [f"- [{t['id']}] ({t['priority']}) {t['title']}" for t in tasks]
        return AgentResponse("Open tasks:\n" + "\n".join(lines), steps)

    def _add_task(self, text: str) -> AgentResponse:
        # e.g. "add task: Draft budget proposal priority:high due:2026-07-25"
        body = text.split(":", 1)[1].strip() if ":" in text else text[len("add task"):].strip()
        priority_match = re.search(r"priority:(\w+)", body)
        due_match = re.search(r"due:(\S+)", body)
        priority = priority_match.group(1) if priority_match else "normal"
        due = due_match.group(1) if due_match else None
        title = re.sub(r"priority:\w+", "", body)
        title = re.sub(r"due:\S+", "", title).strip(" -")
        args = {"title": title, "priority": priority}
        if due:
            args["due"] = due
        result = call_tool(self.store, "create_task", args)
        steps = [AgentStep("create_task", args, result.__dict__)]
        if not result.ok:
            return AgentResponse(f"Couldn't create task: {result.error}", steps)
        return AgentResponse(f"Added task [{result.data['id']}]: {result.data['title']}", steps)

    def _complete_task(self, text: str) -> AgentResponse:
        match = re.search(r"(\d+)", text)
        if not match:
            return AgentResponse("Tell me a task id to complete, e.g. 'done 2'.", [])
        task_id = int(match.group(1))
        args = {"task_id": task_id}
        result = call_tool(self.store, "complete_task", args)
        steps = [AgentStep("complete_task", args, result.__dict__)]
        if not result.ok:
            return AgentResponse(f"Couldn't complete task {task_id}: {result.error}", steps)
        return AgentResponse(f"Completed task [{task_id}]: {result.data['title']}", steps)

    def _add_note(self, text: str) -> AgentResponse:
        body_text = text.split(":", 1)[1].strip() if text.lower().startswith("note:") else text[len("add note"):].strip()
        if "|" in body_text:
            title, body = [p.strip() for p in body_text.split("|", 1)]
        else:
            title, body = "Untitled note", body_text
        args = {"title": title, "body": body, "tags": []}
        result = call_tool(self.store, "create_note", args)
        steps = [AgentStep("create_note", args, result.__dict__)]
        if not result.ok:
            return AgentResponse(f"Couldn't create note: {result.error}", steps)
        return AgentResponse(f"Saved note [{result.data['id']}]: {result.data['title']}", steps)

    def _search_notes(self, text: str) -> AgentResponse:
        query = text[len("search notes"):].strip()
        args = {"query": query}
        result = call_tool(self.store, "search_notes", args)
        steps = [AgentStep("search_notes", args, result.__dict__)]
        if not result.ok:
            return AgentResponse(f"Couldn't search notes: {result.error}", steps)
        notes = result.data
        if not notes:
            return AgentResponse(f"No notes matched '{query}'.", steps)
        lines = [f"- [{n['id']}] {n['title']}: {n['body']}" for n in notes]
        return AgentResponse("Matching notes:\n" + "\n".join(lines), steps)

    def _daily_briefing(self) -> AgentResponse:
        """Multi-step agentic workflow: pull open tasks, pull standup notes,
        then write a summary note back -- three chained tool calls with the
        output of earlier steps feeding the final one."""
        steps: list[AgentStep] = []

        tasks_result = call_tool(self.store, "list_tasks", {})
        steps.append(AgentStep("list_tasks", {}, tasks_result.__dict__))

        notes_args = {"query": "standup"}
        notes_result = call_tool(self.store, "search_notes", notes_args)
        steps.append(AgentStep("search_notes", notes_args, notes_result.__dict__))

        tasks = tasks_result.data if tasks_result.ok else []
        notes = notes_result.data if notes_result.ok else []

        high_priority = [t for t in tasks if t["priority"] == "high"]
        task_summary = (
            f"{len(tasks)} open task(s), {len(high_priority)} high priority."
        )
        note_summary = (
            f"{len(notes)} relevant standup note(s) found."
            if notes
            else "No standup notes found."
        )
        briefing_body = f"{task_summary} {note_summary}"

        create_args = {
            "title": "Daily briefing",
            "body": briefing_body,
            "tags": ["briefing", "auto-generated"],
        }
        create_result = call_tool(self.store, "create_note", create_args)
        steps.append(AgentStep("create_note", create_args, create_result.__dict__))

        reply = f"Daily briefing saved as note [{create_result.data['id']}]: {briefing_body}" \
            if create_result.ok else f"Briefing generated but failed to save: {create_result.error}"
        return AgentResponse(reply, steps)

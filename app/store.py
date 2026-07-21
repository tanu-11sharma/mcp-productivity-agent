"""
In-memory data store simulating a productivity backend (tasks + notes).

This stands in for a real productivity service (Todoist, Notion, etc.).
In a production system this module would be replaced by an HTTP client
talking to that service; here it's synthetic in-memory data so the whole
demo runs with zero external accounts or API keys.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Task:
    id: int
    title: str
    done: bool = False
    priority: str = "normal"  # low | normal | high
    due: Optional[str] = None  # ISO date string, optional


@dataclass
class Note:
    id: int
    title: str
    body: str
    tags: list[str] = field(default_factory=list)


class ProductivityStore:
    """Simple in-memory store with autoincrement ids. Not thread-safe;
    fine for a single-process demo."""

    def __init__(self) -> None:
        self._task_ids = itertools.count(1)
        self._note_ids = itertools.count(1)
        self.tasks: dict[int, Task] = {}
        self.notes: dict[int, Note] = {}
        self._seed()

    def _seed(self) -> None:
        today = date.today().isoformat()
        self.create_task("Draft Q3 roadmap outline", priority="high", due=today)
        self.create_task("Reply to vendor contract email", priority="normal")
        self.create_task("Renew domain for side project", priority="low")
        self.create_note(
            "Standup notes",
            "Blocked on staging creds, otherwise on track for Friday demo.",
            tags=["standup"],
        )

    # --- tasks -----------------------------------------------------
    def create_task(self, title: str, priority: str = "normal", due: Optional[str] = None) -> Task:
        task_id = next(self._task_ids)
        task = Task(id=task_id, title=title, priority=priority, due=due)
        self.tasks[task_id] = task
        return task

    def list_tasks(self, include_done: bool = False) -> list[Task]:
        tasks = list(self.tasks.values())
        if not include_done:
            tasks = [t for t in tasks if not t.done]
        return sorted(tasks, key=lambda t: (t.done, {"high": 0, "normal": 1, "low": 2}.get(t.priority, 1)))

    def complete_task(self, task_id: int) -> Optional[Task]:
        task = self.tasks.get(task_id)
        if task is None:
            return None
        task.done = True
        return task

    # --- notes -------------------------------------------------------
    def create_note(self, title: str, body: str, tags: Optional[list[str]] = None) -> Note:
        note_id = next(self._note_ids)
        note = Note(id=note_id, title=title, body=body, tags=tags or [])
        self.notes[note_id] = note
        return note

    def search_notes(self, query: str) -> list[Note]:
        q = query.lower().strip()
        if not q:
            return list(self.notes.values())
        return [
            n for n in self.notes.values()
            if q in n.title.lower() or q in n.body.lower() or any(q in tag.lower() for tag in n.tags)
        ]

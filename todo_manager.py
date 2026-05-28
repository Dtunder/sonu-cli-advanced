"""Session-scoped TodoManager — tracks tasks for the current Sonu agent turn.

Stored in memory only (no file); designed to be injected into the system prompt
so the model can see pending tasks and mark them done.

Commands exposed via /todo in main.py.
"""

from __future__ import annotations
import json
import time
from typing import Literal

Status = Literal["pending", "in_progress", "completed", "cancelled"]


class TodoManager:
    def __init__(self):
        self._tasks: list[dict] = []
        self._next_id = 1

    def add(self, content: str) -> dict:
        task = {
            "id": self._next_id,
            "content": content,
            "status": "pending",
            "created": time.time(),
        }
        self._tasks.append(task)
        self._next_id += 1
        return task

    def update(self, task_id: int, status: Status) -> str:
        for t in self._tasks:
            if t["id"] == task_id:
                t["status"] = status
                return f"OK: Task {task_id} → {status}"
        return f"FEHLER: Task {task_id} nicht gefunden."

    def remove(self, task_id: int) -> str:
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if t["id"] != task_id]
        return "OK: Gelöscht." if len(self._tasks) < before else f"FEHLER: Task {task_id} nicht gefunden."

    def list_tasks(self, status: Status = None) -> list[dict]:
        if status:
            return [t for t in self._tasks if t["status"] == status]
        return list(self._tasks)

    def clear_completed(self) -> int:
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if t["status"] != "completed"]
        return before - len(self._tasks)

    def format_for_display(self) -> str:
        if not self._tasks:
            return "(Keine Tasks)"
        icons = {"pending": "○", "in_progress": "◉", "completed": "✓", "cancelled": "✗"}
        lines = []
        for t in self._tasks:
            icon = icons.get(t["status"], "?")
            lines.append(f"  [{t['id']}] {icon} {t['content']}  [{t['status']}]")
        return "\n".join(lines)

    def format_for_prompt(self) -> str:
        """Compact representation injected into system prompt context."""
        active = [t for t in self._tasks if t["status"] in ("pending", "in_progress")]
        if not active:
            return ""
        lines = ["## Aktive Tasks (TodoManager)"]
        for t in active:
            status_tag = "→ IN PROGRESS" if t["status"] == "in_progress" else "○ PENDING"
            lines.append(f"- [{t['id']}] {status_tag}: {t['content']}")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(self._tasks, ensure_ascii=False, indent=2)

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


class AssistantStore:
    """Small SQLite store for local tasks, events, and email drafts."""

    def __init__(self, path: str | Path = "assistant.db") -> None:
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    due_at TEXT,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    completed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    starts_at TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL DEFAULT 30,
                    location TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def add_task(self, title: str, due_at: str | None = None, priority: str = "medium") -> dict:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO tasks(title, due_at, priority, created_at) VALUES (?, ?, ?, ?)",
                (title, due_at, priority, datetime.now().isoformat(timespec="seconds")),
            )
            task_id = int(cursor.lastrowid)
        return self.get_task(task_id)

    def get_task(self, task_id: int) -> dict:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise ValueError(f"Task {task_id} does not exist")
        return dict(row)

    def list_tasks(self, include_completed: bool = False) -> list[dict]:
        query = "SELECT * FROM tasks" if include_completed else "SELECT * FROM tasks WHERE completed = 0"
        with self._connect() as connection:
            rows = connection.execute(query + " ORDER BY completed, COALESCE(due_at, '9999'), id").fetchall()
        return [dict(row) for row in rows]

    def complete_task(self, task_id: int) -> dict:
        self.get_task(task_id)
        with self._connect() as connection:
            connection.execute("UPDATE tasks SET completed = 1 WHERE id = ?", (task_id,))
        return self.get_task(task_id)

    def add_event(self, title: str, starts_at: str, duration_minutes: int = 30, location: str = "") -> dict:
        datetime.fromisoformat(starts_at)
        if duration_minutes < 5 or duration_minutes > 1440:
            raise ValueError("Duration must be between 5 and 1440 minutes")
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO events(title, starts_at, duration_minutes, location, created_at) VALUES (?, ?, ?, ?, ?)",
                (title, starts_at, duration_minutes, location, datetime.now().isoformat(timespec="seconds")),
            )
            event_id = int(cursor.lastrowid)
            row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return dict(row)

    def list_events(self, start: str | None = None) -> list[dict]:
        start = start or datetime.now().date().isoformat()
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM events WHERE starts_at >= ? ORDER BY starts_at", (start,)).fetchall()
        return [dict(row) for row in rows]

    def get_event(self, event_id: int) -> dict:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            raise ValueError(f"Event {event_id} does not exist")
        return dict(row)

    def add_draft(self, recipient: str, subject: str, body: str) -> dict:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO drafts(recipient, subject, body, created_at) VALUES (?, ?, ?, ?)",
                (recipient, subject, body, datetime.now().isoformat(timespec="seconds")),
            )
            draft_id = int(cursor.lastrowid)
            row = connection.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        return dict(row)

    def list_drafts(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM drafts ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

    def get_draft(self, draft_id: int) -> dict:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            raise ValueError(f"Draft {draft_id} does not exist")
        return dict(row)

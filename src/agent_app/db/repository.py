from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
class Repository:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    def init_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );
                CREATE TABLE IF NOT EXISTS progress_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                );
                CREATE TABLE IF NOT EXISTS daily_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    snapshot_date TEXT NOT NULL,
                    todo_count INTEGER NOT NULL,
                    in_progress_count INTEGER NOT NULL,
                    done_count INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );
                CREATE TABLE IF NOT EXISTS sync_cursors (
                    source TEXT PRIMARY KEY,
                    last_cursor TEXT,
                    last_synced_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS retry_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    error TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    next_attempt_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS browser_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jira_task_links (
                    task_id INTEGER PRIMARY KEY,
                    issue_key TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                );

                CREATE TABLE IF NOT EXISTS system_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cpu_percent REAL NOT NULL,
                    ram_percent REAL NOT NULL,
                    ram_used_gb REAL NOT NULL,
                    ram_total_gb REAL NOT NULL,
                    disk_percent REAL NOT NULL,
                    disk_free_gb REAL NOT NULL,
                    battery_percent REAL,
                    battery_charging INTEGER,
                    active_window TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS work_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            # Migrate: add deadline column to tasks if not present
            try:
                conn.execute("SELECT deadline FROM tasks LIMIT 1")
            except Exception:
                conn.execute("ALTER TABLE tasks ADD COLUMN deadline TEXT")
        self.get_or_create_inbox_project()
    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    def get_or_create_inbox_project(self) -> int:
        with self.connection() as conn:
            row = conn.execute("SELECT id FROM projects WHERE name = ?", ("Inbox",)).fetchone()
            if row:
                return int(row["id"])
            cursor = conn.execute(
                "INSERT INTO projects (name, created_at) VALUES (?, ?)",
                ("Inbox", self._utc_now()),
            )
            return int(cursor.lastrowid)
    def create_task(self, title: str, project_id: Optional[int] = None) -> Dict[str, Any]:
        target_project = project_id if project_id is not None else self.get_or_create_inbox_project()
        now = self._utc_now()
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (project_id, title, status, created_at, updated_at)
                VALUES (?, ?, 'todo', ?, ?)
                """,
                (target_project, title, now, now),
            )
            task_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else {}
    def update_task_status(self, task_id: int, status: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status, self._utc_now(), task_id),
            )
            return cursor.rowcount > 0
    def list_tasks(
        self,
        project_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM tasks WHERE 1=1"
        params: List[Any] = []
        if project_id is not None:
            query += " AND project_id = ?"
            params.append(project_id)
        if start_date is not None:
            query += " AND date(created_at) >= ?"
            params.append(start_date.isoformat())
        if end_date is not None:
            query += " AND date(created_at) <= ?"
            params.append(end_date.isoformat())
        query += " ORDER BY updated_at DESC"
        with self.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    def add_progress(self, source: str, content: str, task_id: Optional[int] = None) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO progress_entries (task_id, source, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, source, content, self._utc_now()),
            )
    def recent_progress(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM progress_entries ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
    def upsert_sync_cursor(self, source: str, cursor_value: Optional[str]) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO sync_cursors (source, last_cursor, last_synced_at)
                VALUES (?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    last_cursor = excluded.last_cursor,
                    last_synced_at = excluded.last_synced_at
                """,
                (source, cursor_value, self._utc_now()),
            )
    def enqueue_retry_job(self, source: str, action: str, payload: Dict[str, Any], error: str) -> None:
        now = datetime.now(timezone.utc)
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO retry_jobs (
                    source, action, payload, error, attempt_count,
                    next_attempt_at, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?)
                """,
                (
                    source,
                    action,
                    json.dumps(payload),
                    error,
                    0,
                    now.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
    def due_retry_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        now = self._utc_now()
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM retry_jobs
                WHERE status = 'queued' AND next_attempt_at <= ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (now, limit),
            ).fetchall()
        return [dict(row) for row in rows]
    def mark_retry_job(self, job_id: int, success: bool, error: str = "") -> None:
        now = datetime.now(timezone.utc)
        with self.connection() as conn:
            job = conn.execute("SELECT attempt_count FROM retry_jobs WHERE id = ?", (job_id,)).fetchone()
            if not job:
                return
            attempts = int(job["attempt_count"]) + 1
            if success:
                conn.execute(
                    "UPDATE retry_jobs SET status = 'succeeded', attempt_count = ?, updated_at = ? WHERE id = ?",
                    (attempts, now.isoformat(), job_id),
                )
                return
            backoff_minutes = min(2 ** min(attempts, 6), 60)
            next_attempt_ts = now.timestamp() + backoff_minutes * 60
            next_attempt_iso = datetime.fromtimestamp(next_attempt_ts, timezone.utc).isoformat()
            conn.execute(
                """
                UPDATE retry_jobs
                SET attempt_count = ?,
                    error = ?,
                    next_attempt_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (attempts, error, next_attempt_iso, now.isoformat(), job_id),
            )
    def record_browser_event(self, url: str, title: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO browser_events (url, title, created_at) VALUES (?, ?, ?)",
                (url, title, self._utc_now()),
            )
    def recent_browser_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM browser_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
    def dashboard_overview(self, project_id: Optional[int] = None) -> Dict[str, Any]:
        query = "SELECT status, COUNT(*) as count FROM tasks"
        params: List[Any] = []
        if project_id is not None:
            query += " WHERE project_id = ?"
            params.append(project_id)
        query += " GROUP BY status"
        counts: Dict[str, Any] = {"todo": 0, "in_progress": 0, "done": 0}
        with self.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        for row in rows:
            counts[row["status"]] = row["count"]
        counts["total"] = counts["todo"] + counts["in_progress"] + counts["done"]
        return counts
    def create_daily_snapshot(self, project_id: Optional[int] = None) -> Dict[str, Any]:
        counts = self.dashboard_overview(project_id=project_id)
        snapshot_date = date.today().isoformat()
        summary = "todo={0}, in_progress={1}, done={2}".format(
            counts["todo"], counts["in_progress"], counts["done"]
        )
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO daily_snapshots (
                    project_id, snapshot_date, todo_count, in_progress_count,
                    done_count, summary, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    snapshot_date,
                    counts["todo"],
                    counts["in_progress"],
                    counts["done"],
                    summary,
                    self._utc_now(),
                ),
            )
        return {"snapshot_date": snapshot_date, "summary": summary, **counts}
    def get_jira_issue_key(self, task_id: int) -> Optional[str]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT issue_key FROM jira_task_links WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if not row:
            return None
        return str(row["issue_key"])

    def link_jira_issue(self, task_id: int, issue_key: str) -> bool:
        with self.connection() as conn:
            task = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not task:
                return False
            conn.execute(
                """
                INSERT INTO jira_task_links (task_id, issue_key, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    issue_key = excluded.issue_key,
                    updated_at = excluded.updated_at
                """,
                (task_id, issue_key, self._utc_now()),
            )
        return True

    # ---- System snapshots ----

    def save_system_snapshot(self, data: Dict[str, Any]) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO system_snapshots (
                    cpu_percent, ram_percent, ram_used_gb, ram_total_gb,
                    disk_percent, disk_free_gb, battery_percent,
                    battery_charging, active_window, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("cpu_percent", 0),
                    data.get("ram_percent", 0),
                    data.get("ram_used_gb", 0),
                    data.get("ram_total_gb", 0),
                    data.get("disk_percent", 0),
                    data.get("disk_free_gb", 0),
                    data.get("battery_percent"),
                    1 if data.get("battery_charging") else 0 if data.get("battery_charging") is not None else None,
                    data.get("active_window", ""),
                    self._utc_now(),
                ),
            )

    def get_latest_system_snapshot(self) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM system_snapshots ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    # ---- Chat messages ----

    def save_chat_message(self, role: str, content: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO chat_messages (role, content, created_at) VALUES (?, ?, ?)",
                (role, content, self._utc_now()),
            )

    def get_chat_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_messages ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    # ---- Notifications ----

    def add_notification(self, alert_type: str, message: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO notifications (alert_type, message, is_read, created_at) VALUES (?, ?, 0, ?)",
                (alert_type, message, self._utc_now()),
            )

    def get_unread_notifications(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM notifications WHERE is_read = 0 ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_notification_read(self, notification_id: int) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?",
                (notification_id,),
            )

    # ---- Work sessions (app restore) ----

    def save_work_session(self, apps: List[Dict[str, Any]]) -> None:
        """Save the list of open apps as a JSON work session."""
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO work_sessions (session_data, created_at) VALUES (?, ?)",
                (json.dumps(apps), self._utc_now()),
            )

    def get_last_work_session(self) -> List[Dict[str, Any]]:
        """Retrieve the most recent work session (list of apps)."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT session_data FROM work_sessions ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return []
        try:
            return json.loads(row["session_data"])
        except (json.JSONDecodeError, TypeError):
            return []

    # ---- Deadline support ----

    def create_task_with_deadline(
        self, title: str, project_id: Optional[int] = None, deadline: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a task with an optional deadline (ISO date string, e.g. 2026-04-20)."""
        target_project = project_id if project_id is not None else self.get_or_create_inbox_project()
        now = self._utc_now()
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (project_id, title, status, deadline, created_at, updated_at)
                VALUES (?, ?, 'todo', ?, ?, ?)
                """,
                (target_project, title, deadline, now, now),
            )
            task_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else {}

    def update_task_deadline(self, task_id: int, deadline: Optional[str]) -> bool:
        """Set or clear a deadline on an existing task."""
        with self.connection() as conn:
            cursor = conn.execute(
                "UPDATE tasks SET deadline = ?, updated_at = ? WHERE id = ?",
                (deadline, self._utc_now(), task_id),
            )
            return cursor.rowcount > 0

    def get_tasks_with_deadlines(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Return tasks with deadlines within the next N days, ordered by urgency."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE deadline IS NOT NULL
                  AND status != 'done'
                  AND date(deadline) <= date('now', '+' || ? || ' days')
                ORDER BY deadline ASC
                """,
                (days_ahead,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_overdue_tasks(self) -> List[Dict[str, Any]]:
        """Return tasks whose deadline has passed and are not done."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE deadline IS NOT NULL
                  AND status != 'done'
                  AND date(deadline) < date('now')
                ORDER BY deadline ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_in_progress_tasks(self) -> List[Dict[str, Any]]:
        """Return all tasks currently in progress."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = 'in_progress' ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_startup_briefing(self) -> Dict[str, Any]:
        """Build a comprehensive startup briefing dict."""
        return {
            "in_progress": self.get_in_progress_tasks(),
            "overdue": self.get_overdue_tasks(),
            "upcoming_deadlines": self.get_tasks_with_deadlines(days_ahead=7),
            "overview": self.dashboard_overview(),
            "unread_notifications": self.get_unread_notifications(limit=10),
            "last_session": self.get_last_work_session(),
        }


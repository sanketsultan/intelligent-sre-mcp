"""
Action learning and effectiveness tracking for healing actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import contextvars
import os
import sqlite3
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:  # pragma: no cover
    psycopg2 = None
    RealDictCursor = None


@dataclass
class ActionOutcome:
    action_id: int
    outcome: str
    resolution_time_seconds: Optional[float] = None
    notes: Optional[str] = None


class ActionHistoryStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or os.getenv("ACTION_HISTORY_DB", "/tmp/intelligent_sre_actions.db")
        self.is_postgres = self._is_postgres_url(self.db_path)
        self.placeholder = "%s" if self.is_postgres else "?"
        if not self.is_postgres:
            self._ensure_directory()
        self._init_db()

    def _ensure_directory(self) -> None:
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def _connect(self):
        if self.is_postgres:
            if psycopg2 is None:
                raise RuntimeError("psycopg2 is required for PostgreSQL backend")
            return psycopg2.connect(self.db_path)
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()
            if self.is_postgres:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS healing_actions (
                        id SERIAL PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        namespace TEXT NOT NULL,
                        resource TEXT NOT NULL,
                        success BOOLEAN NOT NULL,
                        details TEXT NOT NULL,
                        problem_id INTEGER,
                        outcome TEXT,
                        resolution_time_seconds DOUBLE PRECISION,
                        notes TEXT
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_healing_actions_time ON healing_actions(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_healing_actions_type ON healing_actions(action_type)"
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_activity (
                        id SERIAL PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        intent TEXT NOT NULL,
                        inputs_summary TEXT NOT NULL,
                        action_taken TEXT NOT NULL,
                        outcome TEXT,
                        notes TEXT,
                        problem_id INTEGER
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_agent_activity_time ON agent_activity(timestamp)"
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS problems (
                        id SERIAL PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        title TEXT NOT NULL,
                        namespace TEXT,
                        resource TEXT,
                        severity TEXT,
                        status TEXT NOT NULL,
                        summary TEXT,
                        fingerprint TEXT,
                        last_updated TEXT NOT NULL
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_problems_status ON problems(status)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_problems_updated ON problems(last_updated)"
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tool_invocations (
                        id SERIAL PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        method TEXT NOT NULL,
                        path TEXT NOT NULL,
                        query_params TEXT,
                        body TEXT,
                        status_code INTEGER,
                        duration_ms DOUBLE PRECISION,
                        problem_id INTEGER
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tool_invocations_time ON tool_invocations(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tool_invocations_path ON tool_invocations(path)"
                )
                cursor.execute(
                    "ALTER TABLE healing_actions ADD COLUMN IF NOT EXISTS problem_id INTEGER"
                )
                cursor.execute(
                    "ALTER TABLE agent_activity ADD COLUMN IF NOT EXISTS problem_id INTEGER"
                )
                cursor.execute(
                    "ALTER TABLE problems ADD COLUMN IF NOT EXISTS fingerprint TEXT"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_problems_fingerprint ON problems(fingerprint)"
                )
            else:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS healing_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        namespace TEXT NOT NULL,
                        resource TEXT NOT NULL,
                        success INTEGER NOT NULL,
                        details TEXT NOT NULL,
                        problem_id INTEGER,
                        outcome TEXT,
                        resolution_time_seconds REAL,
                        notes TEXT
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_healing_actions_time ON healing_actions(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_healing_actions_type ON healing_actions(action_type)"
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_activity (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        intent TEXT NOT NULL,
                        inputs_summary TEXT NOT NULL,
                        action_taken TEXT NOT NULL,
                        outcome TEXT,
                        notes TEXT,
                        problem_id INTEGER
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_agent_activity_time ON agent_activity(timestamp)"
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS problems (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT NOT NULL,
                        title TEXT NOT NULL,
                        namespace TEXT,
                        resource TEXT,
                        severity TEXT,
                        status TEXT NOT NULL,
                        summary TEXT,
                        fingerprint TEXT,
                        last_updated TEXT NOT NULL
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_problems_status ON problems(status)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_problems_updated ON problems(last_updated)"
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tool_invocations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        method TEXT NOT NULL,
                        path TEXT NOT NULL,
                        query_params TEXT,
                        body TEXT,
                        status_code INTEGER,
                        duration_ms REAL,
                        problem_id INTEGER
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tool_invocations_time ON tool_invocations(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tool_invocations_path ON tool_invocations(path)"
                )
                self._ensure_sqlite_column(conn, "healing_actions", "problem_id", "INTEGER")
                self._ensure_sqlite_column(conn, "agent_activity", "problem_id", "INTEGER")
                self._ensure_sqlite_column(conn, "problems", "fingerprint", "TEXT")
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_problems_fingerprint ON problems(fingerprint)"
                )

    def record_action(
        self,
        action_type: str,
        namespace: str,
        resource: str,
        success: bool,
        details: str,
        problem_id: Optional[int] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        resolved_problem_id = self._resolve_problem_id(problem_id)
        action_time = timestamp or datetime.utcnow().isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "INSERT INTO healing_actions "
                "(timestamp, action_type, namespace, resource, success, details, problem_id) "
                f"VALUES ({self.placeholder}, {self.placeholder}, {self.placeholder}, "
                f"{self.placeholder}, {self.placeholder}, {self.placeholder}, {self.placeholder})"
            )
            cursor.execute(
                query,
                (
                    action_time,
                    action_type,
                    namespace,
                    resource,
                    bool(success) if self.is_postgres else int(success),
                    details,
                    resolved_problem_id,
                ),
            )
            if self.is_postgres:
                cursor.execute("SELECT LASTVAL()")
                action_id = cursor.fetchone()[0]
                return int(action_id)
            return int(cursor.lastrowid)

    def list_actions(self, hours: int = 24) -> List[Dict[str, Any]]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT id, timestamp, action_type, namespace, resource, success, details, "
                "outcome, resolution_time_seconds, notes, problem_id "
                "FROM healing_actions "
                f"WHERE timestamp >= {self.placeholder} "
                "ORDER BY timestamp ASC"
            )
            cursor.execute(query, (cutoff_iso,))
            rows = cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def action_stats(self, hours: int = 24) -> Dict[str, Any]:
        actions = self.list_actions(hours)
        total = len(actions)
        successful = sum(1 for a in actions if a["success"])
        failed = total - successful
        by_action = {}

        for action in actions:
            action_type = action["action_type"]
            if action_type not in by_action:
                by_action[action_type] = {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "avg_resolution_time_seconds": None,
                }
            by_action[action_type]["total"] += 1
            if action["success"]:
                by_action[action_type]["success"] += 1
            else:
                by_action[action_type]["failed"] += 1

        for action_type, stats in by_action.items():
            times = [
                a["resolution_time_seconds"]
                for a in actions
                if a["action_type"] == action_type and a["resolution_time_seconds"] is not None
            ]
            if times:
                stats["avg_resolution_time_seconds"] = round(sum(times) / len(times), 2)

        return {
            "time_period_hours": hours,
            "total_actions": total,
            "successful_actions": successful,
            "failed_actions": failed,
            "success_rate": round((successful / total) * 100, 1) if total else 0,
            "by_action_type": by_action,
        }
    def recurring_issues(self, hours: int = 24, min_count: int = 2) -> List[Dict[str, Any]]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT namespace, resource, action_type, COUNT(*) as occurrences, MAX(timestamp) as last_seen "
                "FROM healing_actions "
                f"WHERE timestamp >= {self.placeholder} "
                "GROUP BY namespace, resource, action_type "
                f"HAVING COUNT(*) >= {self.placeholder} "
                "ORDER BY occurrences DESC"
            )
            cursor.execute(query, (cutoff_iso, min_count))
            rows = cursor.fetchall()
        return [
            {
                "namespace": row[0],
                "resource": row[1],
                "action_type": row[2],
                "occurrences": row[3],
                "last_seen": row[4],
            }
            for row in rows
        ]

    def update_outcome(self, outcome: ActionOutcome) -> bool:
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "UPDATE healing_actions "
                f"SET outcome = {self.placeholder}, resolution_time_seconds = {self.placeholder}, notes = {self.placeholder} "
                f"WHERE id = {self.placeholder}"
            )
            cursor.execute(
                query,
                (outcome.outcome, outcome.resolution_time_seconds, outcome.notes, outcome.action_id),
            )
            return cursor.rowcount > 0

    def history_summary(self, hours: int = 24) -> Dict[str, Any]:
        actions = self.list_actions(hours)
        total = len(actions)
        successful = sum(1 for a in actions if a["success"])
        failed = total - successful
        by_action = {}
        for action in actions:
            action_type = action["action_type"]
            if action_type not in by_action:
                by_action[action_type] = {"total": 0, "success": 0, "failed": 0}
            by_action[action_type]["total"] += 1
            if action["success"]:
                by_action[action_type]["success"] += 1
            else:
                by_action[action_type]["failed"] += 1

        return {
            "time_period_hours": hours,
            "total_actions": total,
            "successful_actions": successful,
            "failed_actions": failed,
            "success_rate": round((successful / total) * 100, 1) if total else 0,
            "by_action_type": by_action,
            "recent_actions": actions[-10:] if actions else [],
        }

    def record_agent_activity(
        self,
        intent: str,
        inputs_summary: str,
        action_taken: str,
        outcome: Optional[str] = None,
        notes: Optional[str] = None,
        problem_id: Optional[int] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        resolved_problem_id = self._resolve_problem_id(problem_id)
        activity_time = timestamp or datetime.utcnow().isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "INSERT INTO agent_activity "
                "(timestamp, intent, inputs_summary, action_taken, outcome, notes, problem_id) "
                f"VALUES ({self.placeholder}, {self.placeholder}, {self.placeholder}, "
                f"{self.placeholder}, {self.placeholder}, {self.placeholder}, {self.placeholder})"
            )
            cursor.execute(
                query,
                (activity_time, intent, inputs_summary, action_taken, outcome, notes, resolved_problem_id),
            )
            if self.is_postgres:
                cursor.execute("SELECT LASTVAL()")
                activity_id = cursor.fetchone()[0]
                return int(activity_id)
            return int(cursor.lastrowid)

    def list_agent_activity(self, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT id, timestamp, intent, inputs_summary, action_taken, outcome, notes, problem_id "
                "FROM agent_activity "
                f"WHERE timestamp >= {self.placeholder} "
                "ORDER BY timestamp DESC "
                f"LIMIT {self.placeholder}"
            )
            cursor.execute(query, (cutoff_iso, limit))
            rows = cursor.fetchall()
        return [self._row_to_agent_dict(row) for row in rows]

    def create_problem(
        self,
        title: str,
        namespace: Optional[str] = None,
        resource: Optional[str] = None,
        severity: Optional[str] = None,
        status: str = "open",
        summary: Optional[str] = None,
        fingerprint: Optional[str] = None,
    ) -> int:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "INSERT INTO problems "
                "(created_at, title, namespace, resource, severity, status, summary, fingerprint, last_updated) "
                f"VALUES ({self.placeholder}, {self.placeholder}, {self.placeholder}, {self.placeholder}, "
                f"{self.placeholder}, {self.placeholder}, {self.placeholder}, {self.placeholder}, {self.placeholder})"
            )
            cursor.execute(
                query,
                (now, title, namespace, resource, severity, status, summary, fingerprint, now),
            )
            if self.is_postgres:
                cursor.execute("SELECT LASTVAL()")
                problem_id = cursor.fetchone()[0]
                return int(problem_id)
            return int(cursor.lastrowid)

    def get_or_create_problem(
        self,
        title: str,
        fingerprint: str,
        namespace: Optional[str] = None,
        resource: Optional[str] = None,
        severity: Optional[str] = None,
        status: str = "open",
        summary: Optional[str] = None,
    ) -> int:
        existing = self._find_open_problem(fingerprint)
        if existing is not None:
            return existing
        return self.create_problem(
            title=title,
            namespace=namespace,
            resource=resource,
            severity=severity,
            status=status,
            summary=summary,
            fingerprint=fingerprint,
        )

    def _find_open_problem(self, fingerprint: str) -> Optional[int]:
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT id FROM problems "
                f"WHERE fingerprint = {self.placeholder} AND status = {self.placeholder} "
                "ORDER BY last_updated DESC LIMIT 1"
            )
            cursor.execute(query, (fingerprint, "open"))
            row = cursor.fetchone()
            return int(row[0]) if row else None

    def update_problem_status(
        self,
        problem_id: int,
        status: str,
        summary: Optional[str] = None,
    ) -> bool:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "UPDATE problems "
                f"SET status = {self.placeholder}, summary = {self.placeholder}, last_updated = {self.placeholder} "
                f"WHERE id = {self.placeholder}"
            )
            cursor.execute(query, (status, summary, now, problem_id))
            return cursor.rowcount > 0

    def list_problems(self, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT id, created_at, title, namespace, resource, severity, status, summary, last_updated "
                "FROM problems "
                f"WHERE created_at >= {self.placeholder} "
                "ORDER BY last_updated DESC "
                f"LIMIT {self.placeholder}"
            )
            cursor.execute(query, (cutoff_iso, limit))
            rows = cursor.fetchall()
        return [self._row_to_problem_dict(row) for row in rows]

    def record_tool_invocation(
        self,
        method: str,
        path: str,
        query_params: Optional[str],
        body: Optional[str],
        status_code: Optional[int],
        duration_ms: Optional[float],
        problem_id: Optional[int] = None,
    ) -> int:
        resolved_problem_id = self._resolve_problem_id(problem_id)
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "INSERT INTO tool_invocations "
                "(timestamp, method, path, query_params, body, status_code, duration_ms, problem_id) "
                f"VALUES ({self.placeholder}, {self.placeholder}, {self.placeholder}, {self.placeholder}, "
                f"{self.placeholder}, {self.placeholder}, {self.placeholder}, {self.placeholder})"
            )
            cursor.execute(
                query,
                (now, method, path, query_params, body, status_code, duration_ms, resolved_problem_id),
            )
            if self.is_postgres:
                cursor.execute("SELECT LASTVAL()")
                invocation_id = cursor.fetchone()[0]
                return int(invocation_id)
            return int(cursor.lastrowid)

    def list_tool_invocations(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT id, timestamp, method, path, query_params, body, status_code, duration_ms, problem_id "
                "FROM tool_invocations "
                f"WHERE timestamp >= {self.placeholder} "
                "ORDER BY timestamp DESC "
                f"LIMIT {self.placeholder}"
            )
            cursor.execute(query, (cutoff_iso, limit))
            rows = cursor.fetchall()
        return [self._row_to_tool_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row: tuple) -> Dict[str, Any]:
        return {
            "id": row[0],
            "timestamp": row[1],
            "action_type": row[2],
            "namespace": row[3],
            "resource": row[4],
            "success": bool(row[5]),
            "details": row[6],
            "outcome": row[7],
            "resolution_time_seconds": row[8],
            "notes": row[9],
            "problem_id": row[10],
        }

    @staticmethod
    def _row_to_agent_dict(row: tuple) -> Dict[str, Any]:
        return {
            "id": row[0],
            "timestamp": row[1],
            "intent": row[2],
            "inputs_summary": row[3],
            "action_taken": row[4],
            "outcome": row[5],
            "notes": row[6],
            "problem_id": row[7],
        }

    @staticmethod
    def _row_to_problem_dict(row: tuple) -> Dict[str, Any]:
        return {
            "id": row[0],
            "created_at": row[1],
            "title": row[2],
            "namespace": row[3],
            "resource": row[4],
            "severity": row[5],
            "status": row[6],
            "summary": row[7],
            "fingerprint": row[8],
            "last_updated": row[9],
        }

    @staticmethod
    def _row_to_tool_dict(row: tuple) -> Dict[str, Any]:
        return {
            "id": row[0],
            "timestamp": row[1],
            "method": row[2],
            "path": row[3],
            "query_params": row[4],
            "body": row[5],
            "status_code": row[6],
            "duration_ms": row[7],
            "problem_id": row[8],
        }

    @staticmethod
    def _ensure_sqlite_column(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        if column not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    @staticmethod
    def _resolve_problem_id(problem_id: Optional[int]) -> Optional[int]:
        if problem_id is not None:
            return problem_id
        context_value = get_current_problem_id()
        if context_value is not None:
            return context_value
        env_value = os.getenv("CURRENT_PROBLEM_ID")
        if env_value is None or env_value == "":
            return None
        try:
            return int(env_value)
        except ValueError:
            return None

    @staticmethod
    def _is_postgres_url(value: str) -> bool:
        return value.startswith("postgres://") or value.startswith("postgresql://")


_current_problem_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "current_problem_id",
    default=None,
)


def set_current_problem_id(problem_id: Optional[int]) -> None:
    _current_problem_id.set(problem_id)


def get_current_problem_id() -> Optional[int]:
    return _current_problem_id.get()

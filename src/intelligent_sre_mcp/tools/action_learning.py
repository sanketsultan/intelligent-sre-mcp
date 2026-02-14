"""
Action learning and effectiveness tracking for healing actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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

    def record_action(
        self,
        action_type: str,
        namespace: str,
        resource: str,
        success: bool,
        details: str,
        timestamp: Optional[str] = None,
    ) -> int:
        action_time = timestamp or datetime.utcnow().isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "INSERT INTO healing_actions "
                "(timestamp, action_type, namespace, resource, success, details) "
                f"VALUES ({self.placeholder}, {self.placeholder}, {self.placeholder}, "
                f"{self.placeholder}, {self.placeholder}, {self.placeholder})"
            )
            cursor.execute(
                query,
                (action_time, action_type, namespace, resource, bool(success) if self.is_postgres else int(success), details),
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
                "outcome, resolution_time_seconds, notes "
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
        }

    @staticmethod
    def _is_postgres_url(value: str) -> bool:
        return value.startswith("postgres://") or value.startswith("postgresql://")

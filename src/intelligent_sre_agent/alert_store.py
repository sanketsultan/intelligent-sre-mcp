"""
Alert Persistence Store
=======================
Stores Alertmanager webhook payloads together with the SRE agent's investigation
and remediation summaries so every alert has a full audit trail in the database.

Schema
------
alerts
  id                   — primary key
  alert_name           — labels.alertname
  severity             — labels.severity (info/warning/critical)
  namespace            — labels.namespace
  status               — firing | resolved
  summary              — annotations.summary
  description          — annotations.description
  labels_json          — full labels dict (JSON)
  annotations_json     — full annotations dict (JSON)
  starts_at            — ISO timestamp from Alertmanager
  ends_at              — ISO timestamp (null while still firing)
  problem_id           — FK into problems table (optional)
  investigation_summary — Phase 1 agent response (root-cause analysis + pod logs)
  remediation_summary  — Phase 2 agent response (healing actions taken)
  created_at           — when this row was inserted
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import psycopg2
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore[assignment]


class AlertStore:
    """Persists incoming Alertmanager alerts and their SRE investigation results."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        # os.getenv returns "" (falsy) when the var is set to empty string (e.g. dev override).
        # Treat empty string the same as unset so we always fall back to a real file path.
        self.db_path = (
            db_path or os.getenv("ACTION_HISTORY_DB") or "/tmp/intelligent_sre_actions.db"
        )
        self.is_postgres = self._is_postgres_url(self.db_path)
        self.placeholder = "%s" if self.is_postgres else "?"
        if not self.is_postgres:
            self._ensure_directory()
        self._init_db_with_retry()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

    def _init_db_with_retry(self, max_attempts: int = 10, base_delay: float = 2.0) -> None:
        """Initialise the database schema with exponential back-off.

        Needed for Kubernetes startup where the Postgres pod may not be
        accepting connections yet when the API pod starts.
        """
        for attempt in range(1, max_attempts + 1):
            try:
                self._init_db()
                return
            except Exception as exc:
                if attempt == max_attempts:
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "DB init attempt %d/%d failed (%s); retrying in %.0fs",
                    attempt,
                    max_attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)

    def _init_db(self) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()
            if self.is_postgres:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alerts (
                        id SERIAL PRIMARY KEY,
                        alert_name TEXT NOT NULL,
                        severity TEXT,
                        namespace TEXT,
                        status TEXT NOT NULL,
                        summary TEXT,
                        description TEXT,
                        labels_json TEXT,
                        annotations_json TEXT,
                        starts_at TEXT,
                        ends_at TEXT,
                        problem_id INTEGER,
                        investigation_summary TEXT,
                        remediation_summary TEXT,
                        created_at TEXT NOT NULL
                    )
                    """
                )
            else:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        alert_name TEXT NOT NULL,
                        severity TEXT,
                        namespace TEXT,
                        status TEXT NOT NULL,
                        summary TEXT,
                        description TEXT,
                        labels_json TEXT,
                        annotations_json TEXT,
                        starts_at TEXT,
                        ends_at TEXT,
                        problem_id INTEGER,
                        investigation_summary TEXT,
                        remediation_summary TEXT,
                        created_at TEXT NOT NULL
                    )
                    """
                )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_name ON alerts(alert_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)")

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def save_alert(
        self,
        alert_name: str,
        status: str,
        labels: Dict[str, Any],
        annotations: Dict[str, Any],
        starts_at: Optional[str] = None,
        ends_at: Optional[str] = None,
        problem_id: Optional[int] = None,
    ) -> int:
        """Insert a new alert row and return its id."""
        severity = labels.get("severity")
        namespace = labels.get("namespace")
        summary = annotations.get("summary")
        description = annotations.get("description")
        now = datetime.utcnow().isoformat()

        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "INSERT INTO alerts "
                "(alert_name, severity, namespace, status, summary, description, "
                "labels_json, annotations_json, starts_at, ends_at, problem_id, created_at) "
                f"VALUES ({self.placeholder}, {self.placeholder}, {self.placeholder}, "
                f"{self.placeholder}, {self.placeholder}, {self.placeholder}, "
                f"{self.placeholder}, {self.placeholder}, {self.placeholder}, "
                f"{self.placeholder}, {self.placeholder}, {self.placeholder})"
            )
            cursor.execute(
                query,
                (
                    alert_name,
                    severity,
                    namespace,
                    status,
                    summary,
                    description,
                    json.dumps(labels),
                    json.dumps(annotations),
                    starts_at,
                    ends_at,
                    problem_id,
                    now,
                ),
            )
            if self.is_postgres:
                cursor.execute("SELECT LASTVAL()")
                alert_id = cursor.fetchone()[0]
                return int(alert_id)
            return int(cursor.lastrowid)

    def update_investigation(
        self,
        alert_id: int,
        investigation_summary: str,
    ) -> bool:
        """Save the Phase 1 agent investigation response."""
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "UPDATE alerts "
                f"SET investigation_summary = {self.placeholder} "
                f"WHERE id = {self.placeholder}"
            )
            cursor.execute(query, (investigation_summary, alert_id))
            return cursor.rowcount > 0

    def update_remediation(
        self,
        alert_id: int,
        remediation_summary: str,
    ) -> bool:
        """Save the Phase 2 agent remediation response."""
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "UPDATE alerts "
                f"SET remediation_summary = {self.placeholder} "
                f"WHERE id = {self.placeholder}"
            )
            cursor.execute(query, (remediation_summary, alert_id))
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_alert(self, alert_id: int) -> Optional[Dict[str, Any]]:
        """Return a single alert by id, or None if not found."""
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT id, alert_name, severity, namespace, status, summary, description, "
                "labels_json, annotations_json, starts_at, ends_at, problem_id, "
                "investigation_summary, remediation_summary, created_at "
                "FROM alerts "
                f"WHERE id = {self.placeholder}"
            )
            cursor.execute(query, (alert_id,))
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None

    def list_alerts(
        self,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return the most recent alerts, optionally filtered by status."""
        with self._connect() as conn:
            cursor = conn.cursor()
            if status:
                query = (
                    "SELECT id, alert_name, severity, namespace, status, summary, description, "
                    "labels_json, annotations_json, starts_at, ends_at, problem_id, "
                    "investigation_summary, remediation_summary, created_at "
                    "FROM alerts "
                    f"WHERE status = {self.placeholder} "
                    "ORDER BY created_at DESC "
                    f"LIMIT {self.placeholder}"
                )
                cursor.execute(query, (status, limit))
            else:
                query = (
                    "SELECT id, alert_name, severity, namespace, status, summary, description, "
                    "labels_json, annotations_json, starts_at, ends_at, problem_id, "
                    "investigation_summary, remediation_summary, created_at "
                    "FROM alerts "
                    "ORDER BY created_at DESC "
                    f"LIMIT {self.placeholder}"
                )
                cursor.execute(query, (limit,))
            rows = cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def count_by_status(self) -> Dict[str, int]:
        """Return alert counts grouped by status (firing / resolved).

        Used by the dashboard aggregate endpoint to avoid fetching full rows.
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) FROM alerts GROUP BY status")
            rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows}

    # ------------------------------------------------------------------
    # Row mapper
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: tuple) -> Dict[str, Any]:
        return {
            "id": row[0],
            "alert_name": row[1],
            "severity": row[2],
            "namespace": row[3],
            "status": row[4],
            "summary": row[5],
            "description": row[6],
            "labels": json.loads(row[7]) if row[7] else {},
            "annotations": json.loads(row[8]) if row[8] else {},
            "starts_at": row[9],
            "ends_at": row[10],
            "problem_id": row[11],
            "investigation_summary": row[12],
            "remediation_summary": row[13],
            "created_at": row[14],
        }

    @staticmethod
    def _is_postgres_url(value: str) -> bool:
        return value.startswith("postgres://") or value.startswith("postgresql://")

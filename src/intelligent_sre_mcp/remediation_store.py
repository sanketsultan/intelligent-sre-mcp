"""
Remediation Run Store
=====================
Persists every auto-remediation playbook execution so engineers can audit
what the system changed, why it was confident, and whether it worked.

Schema
------
remediation_runs
  id              — primary key
  namespace       — Kubernetes namespace of the affected resource
  pod_name        — pod (or "node:<name>") that triggered the playbook
  issue_type      — IssueType enum value (e.g. CrashLoopBackOff)
  playbook_name   — name of the matched playbook
  confidence      — 0.0-1.0 score at decision time
  outcome         — executed | deferred_to_human | dry_run | failed | no_action
  actions_taken   — JSON list of action names that were run
  evidence_summary— newline-separated log/event snippets used for scoring
  details         — JSON blob with the full RemediationResult for debugging
  dry_run         — 0=live, 1=dry-run only
  created_at      — UTC ISO timestamp
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


class RemediationStore:
    """Persists auto-remediation playbook execution results."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        # os.getenv returns "" (falsy) when the var is set to empty string (e.g. dev override).
        # Treat empty string the same as unset so we always fall back to a real file path.
        self.db_path = (
            db_path
            or os.getenv("ACTION_HISTORY_DB")
            or "/tmp/intelligent_sre_actions.db"
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
                    CREATE TABLE IF NOT EXISTS remediation_runs (
                        id SERIAL PRIMARY KEY,
                        namespace TEXT,
                        pod_name TEXT NOT NULL,
                        issue_type TEXT NOT NULL,
                        playbook_name TEXT NOT NULL,
                        confidence DOUBLE PRECISION NOT NULL,
                        outcome TEXT NOT NULL,
                        actions_taken TEXT,
                        evidence_summary TEXT,
                        details TEXT,
                        dry_run INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL
                    )
                    """
                )
            else:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS remediation_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        namespace TEXT,
                        pod_name TEXT NOT NULL,
                        issue_type TEXT NOT NULL,
                        playbook_name TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        outcome TEXT NOT NULL,
                        actions_taken TEXT,
                        evidence_summary TEXT,
                        details TEXT,
                        dry_run INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL
                    )
                    """
                )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_remediation_created ON remediation_runs(created_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_remediation_issue ON remediation_runs(issue_type)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_remediation_outcome ON remediation_runs(outcome)"
            )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_run(
        self,
        namespace: Optional[str],
        pod_name: str,
        issue_type: str,
        playbook_name: str,
        confidence: float,
        outcome: str,
        actions_taken: List[str],
        evidence_summary: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> int:
        """Persist a remediation execution record and return its id."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "INSERT INTO remediation_runs "
                "(namespace, pod_name, issue_type, playbook_name, confidence, outcome, "
                "actions_taken, evidence_summary, details, dry_run, created_at) "
                f"VALUES ({self.placeholder}, {self.placeholder}, {self.placeholder}, "
                f"{self.placeholder}, {self.placeholder}, {self.placeholder}, "
                f"{self.placeholder}, {self.placeholder}, {self.placeholder}, "
                f"{self.placeholder}, {self.placeholder})"
            )
            cursor.execute(
                query,
                (
                    namespace,
                    pod_name,
                    issue_type,
                    playbook_name,
                    confidence,
                    outcome,
                    json.dumps(actions_taken),
                    evidence_summary,
                    json.dumps(details) if details else None,
                    1 if dry_run else 0,
                    now,
                ),
            )
            if self.is_postgres:
                cursor.execute("SELECT LASTVAL()")
                run_id = cursor.fetchone()[0]
                return int(run_id)
            return int(cursor.lastrowid)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Return a single remediation run by id, or None."""
        with self._connect() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT id, namespace, pod_name, issue_type, playbook_name, confidence, outcome, "
                "actions_taken, evidence_summary, details, dry_run, created_at "
                "FROM remediation_runs "
                f"WHERE id = {self.placeholder}"
            )
            cursor.execute(query, (run_id,))
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None

    def list_runs(
        self,
        limit: int = 50,
        outcome: Optional[str] = None,
        issue_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return the most recent remediation runs, optionally filtered."""
        with self._connect() as conn:
            cursor = conn.cursor()
            conditions: List[str] = []
            params: List[Any] = []

            if outcome:
                conditions.append(f"outcome = {self.placeholder}")
                params.append(outcome)
            if issue_type:
                conditions.append(f"issue_type = {self.placeholder}")
                params.append(issue_type)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            query = (
                "SELECT id, namespace, pod_name, issue_type, playbook_name, confidence, outcome, "
                "actions_taken, evidence_summary, details, dry_run, created_at "
                "FROM remediation_runs "
                f"{where} "
                "ORDER BY created_at DESC "
                f"LIMIT {self.placeholder}"
            )
            params.append(limit)
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def past_successes(self, issue_type: str, namespace: Optional[str] = None) -> int:
        """Count prior successful executions for this issue type (used for confidence boosting)."""
        with self._connect() as conn:
            cursor = conn.cursor()
            if namespace:
                query = (
                    "SELECT COUNT(*) FROM remediation_runs "
                    f"WHERE issue_type = {self.placeholder} "
                    f"AND namespace = {self.placeholder} "
                    f"AND outcome = {self.placeholder}"
                )
                cursor.execute(query, (issue_type, namespace, "executed"))
            else:
                query = (
                    "SELECT COUNT(*) FROM remediation_runs "
                    f"WHERE issue_type = {self.placeholder} "
                    f"AND outcome = {self.placeholder}"
                )
                cursor.execute(query, (issue_type, "executed"))
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    # ------------------------------------------------------------------
    # Row mapper
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: tuple) -> Dict[str, Any]:
        return {
            "id": row[0],
            "namespace": row[1],
            "pod_name": row[2],
            "issue_type": row[3],
            "playbook_name": row[4],
            "confidence": row[5],
            "outcome": row[6],
            "actions_taken": json.loads(row[7]) if row[7] else [],
            "evidence_summary": row[8],
            "details": json.loads(row[9]) if row[9] else None,
            "dry_run": bool(row[10]),
            "created_at": row[11],
        }

    @staticmethod
    def _is_postgres_url(value: str) -> bool:
        return value.startswith("postgres://") or value.startswith("postgresql://")

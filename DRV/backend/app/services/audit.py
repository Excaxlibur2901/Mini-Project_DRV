"""
Audit logging service.

Records structured audit logs in SQLite without sensitive content or personal data.
Conforms to DATABASE.md §4.3.
"""

from __future__ import annotations

import datetime
import os
import sqlite3
from typing import Any


class AuditLogger:
    """Manages appending request audit trails to SQLite."""

    def __init__(self, db_path: str = "data/verifier.db"):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure parent directory for database exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a configured SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def log_request(
        self,
        request_id: str,
        route: str,
        http_method: str,
        http_status: int,
        latency_ms: int,
        outcome: str = "ok",
        intent: str | None = None,
        parser_type: str | None = None,
        actor_role: str = "anonymous",
        error_code: str | None = None,
        failed_stage: str | None = None,
        stages: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Record a request entry in audit_log and optional stages in audit_stage.

        Pure SQL with parameter binding to prevent SQL injection.
        """
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO audit_log (
                        request_id, route, http_method, parser_type, intent,
                        actor_role, outcome, error_code, failed_stage,
                        http_status, latency_ms, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        route,
                        http_method,
                        parser_type,
                        intent,
                        actor_role,
                        outcome,
                        error_code,
                        failed_stage,
                        http_status,
                        latency_ms,
                        created_at,
                    ),
                )
                audit_id = cursor.lastrowid

                if stages and audit_id:
                    for s in stages:
                        cursor.execute(
                            """
                            INSERT INTO audit_stage (
                                audit_id, stage_order, stage_name, passed, reason
                            ) VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                audit_id,
                                s.get("order"),
                                s.get("name"),
                                1 if s.get("passed") else 0,
                                s.get("reason"),
                            ),
                        )
                conn.commit()
        except sqlite3.Error as e:
            # Operational logging must fail gracefully without halting requests
            print(f"Warning: Failed to write audit log for {request_id}: {e}")


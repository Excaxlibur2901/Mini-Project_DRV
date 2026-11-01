"""
Admin authentication and session management service.
Implements DECISIONS D-11, D-12, D-13 and DATABASE.md §4.3.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import secrets
import sqlite3
import time
from typing import Any


class AdminAuthService:
    """Manages admin credentials, SQLite sessions, CSRF tokens, and 2-step confirmations."""

    # Class-level store so confirmation tokens persist across dependency injection calls
    _pending_confirmations: dict[str, dict[str, Any]] = {}

    def __init__(self, db_path: str, credentials_hash: str):
        self.db_path = db_path
        self.credentials_hash = credentials_hash

    @staticmethod
    def hash_credentials(username: str, password: str) -> str:
        """Compute SHA-256 hash of username:password."""
        return hashlib.sha256(f"{username}:{password}".encode("utf-8")).hexdigest()

    def verify_credentials(self, username: str, password: str) -> bool:
        """Constant-time comparison of credentials against configured hash."""
        computed = self.hash_credentials(username, password)
        return hmac.compare_digest(computed, self.credentials_hash)

    def create_session(self, duration_seconds: int = 3600) -> tuple[str, str, str]:
        """
        Create a new admin session and store its token hash in SQLite.
        Returns: (session_token, csrf_token, expires_at_iso)
        """
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_hex(16)
        token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()

        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = now + datetime.timedelta(seconds=duration_seconds)
        created_at_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        expires_at_iso = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO admin_session (token_hash, created_at, expires_at, revoked)
                VALUES (?, ?, ?, 0)
                """,
                (token_hash, created_at_iso, expires_at_iso),
            )
            conn.commit()
        finally:
            conn.close()

        return session_token, csrf_token, expires_at_iso

    def validate_session(self, session_token: str | None) -> bool:
        """Check whether session token is valid, unrevoked, and not expired."""
        if not session_token:
            return False

        token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM admin_session
                WHERE token_hash = ? AND revoked = 0 AND expires_at > ?
                """,
                (token_hash, now_iso),
            )
            row = cursor.fetchone()
            return row is not None
        finally:
            conn.close()

    def revoke_session(self, session_token: str | None) -> bool:
        """Mark session token as revoked in SQLite."""
        if not session_token:
            return False

        token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE admin_session SET revoked = 1 WHERE token_hash = ?
                """,
                (token_hash,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # --- Two-Step Confirmation (D-13) ---
    def create_confirmation_token(
        self, action: str, record_id: str, reason_code: int = 1, expires_in_seconds: int = 60
    ) -> str:
        """Generate a short-lived single-use confirmation token for privileged admin actions."""
        token = "ct_" + secrets.token_hex(16)
        expires_at = time.time() + expires_in_seconds

        self._pending_confirmations[token] = {
            "action": action,
            "record_id": record_id,
            "reason_code": reason_code,
            "expires_at": expires_at,
        }
        return token

    def pop_confirmation_token(self, token: str) -> dict[str, Any] | None:
        """Retrieve and immediately invalidate a confirmation token if valid and unexpired."""
        data = self._pending_confirmations.pop(token, None)
        if not data:
            return None

        if time.time() > data["expires_at"]:
            return None

        return data

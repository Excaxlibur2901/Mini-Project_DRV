"""
Integration tests for Admin flows and two-step confirmation.
Tests DECISIONS D-11, D-12, D-13, D-14, D-15 and API.md §4.4–§4.8.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.verify import get_audit_logger, get_chain_gateway
from app.services.audit import AuditLogger
from app.services.chain_gateway import (
    ChainGateway,
    DuplicateRecordError,
    RecordNotFoundError,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
MIGRATION_PATH = BASE_DIR / "migrations" / "001_init.sql"


class MockAdminChainGateway:
    """Mock gateway with in-memory ledger simulation for deterministic testing."""

    def __init__(self):
        self.records: dict[str, dict] = {
            "CERT-101": {
                "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "revoked": False,
                "doc_type": "degree",
            },
            "CERT-104": {
                "file_hash": "9f2c41ab7d03e6c158b9a0fe2c47d1e3a6b80c951e7f3d42c08a5b17e92d64f0",
                "revoked": True,
                "doc_type": "degree",
            },
        }

    def is_revoked(self, record_id: str):
        if record_id in self.records:
            return {"exists": True, "revoked": self.records[record_id]["revoked"]}
        return {"exists": False, "revoked": False}

    def verify_hash(self, record_id: str, file_hash_hex: str):
        if record_id not in self.records:
            return {"state": "NOT_FOUND", "revoked": False, "doc_type": None, "registered_hash": None, "registered_at": None, "revoked_at": None, "reason": None}
        rec = self.records[record_id]
        state = "REVOKED" if rec["revoked"] else "MATCH"
        return {
            "state": state,
            "revoked": rec["revoked"],
            "doc_type": rec["doc_type"],
            "registered_hash": rec["file_hash"],
            "registered_at": "2026-11-01T00:00:00Z",
            "revoked_at": "2026-11-02T00:00:00Z" if rec["revoked"] else None,
            "reason": "issued_in_error" if rec["revoked"] else None,
        }

    def register_record(self, record_id: str, file_hash_hex: str, doc_type: int, private_key=None):
        if record_id in self.records:
            raise DuplicateRecordError(f"Record ID '{record_id}' is already registered.")
        self.records[record_id] = {
            "file_hash": file_hash_hex.lower(),
            "revoked": False,
            "doc_type": "degree",
        }
        return {
            "operation": "register",
            "record_id": record_id,
            "registered_hash": file_hash_hex.lower(),
            "tx_hash": "0xmocktx_register",
            "tx_status": "confirmed",
            "block_number": 101,
        }

    def revoke_record(self, record_id: str, reason_code: int = 1, private_key=None):
        if record_id not in self.records:
            raise RecordNotFoundError(f"Record ID '{record_id}' does not exist on the ledger.")
        self.records[record_id]["revoked"] = True
        return {
            "operation": "revoke",
            "record_id": record_id,
            "tx_hash": "0xmocktx_revoke",
            "tx_status": "confirmed",
            "block_number": 102,
        }


@pytest.fixture
def mock_chain():
    return MockAdminChainGateway()


@pytest.fixture
def test_client(tmp_path, mock_chain):
    db_file = tmp_path / "test_admin.db"
    conn = sqlite3.connect(str(db_file))
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.close()

    test_audit = AuditLogger(db_path=str(db_file))

    app.dependency_overrides[get_chain_gateway] = lambda: mock_chain
    app.dependency_overrides[get_audit_logger] = lambda: test_audit

    # Override db_path in settings
    from app.config import get_settings
    orig_settings = get_settings()
    app.dependency_overrides[get_settings] = lambda: orig_settings.model_copy(
        update={"db_path": str(db_file)}
    )

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_admin_login_invalid_credentials(test_client):
    """Admin login with wrong password returns 401 E_UNAUTHORIZED."""
    res = test_client.post("/api/admin/login", json={"username": "admin", "password": "wrongpassword"})
    assert res.status_code == 401
    data = res.json()
    assert data["error"]["code"] == "E_UNAUTHORIZED"


def test_admin_login_success_and_session(test_client):
    """Admin login with valid credentials sets cookie and returns CSRF token."""
    res = test_client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["result"]["role"] == "admin"
    assert "csrf_token" in data["result"]
    assert "drv_session" in test_client.cookies

    # Verify session check
    session_res = test_client.get("/api/admin/session")
    assert session_res.status_code == 200
    assert session_res.json()["result"]["authenticated"] is True
    assert session_res.json()["result"]["role"] == "admin"


def test_admin_logout(test_client):
    """Admin logout revokes session and clears cookie."""
    login_res = test_client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    assert login_res.status_code == 200

    logout_res = test_client.post("/api/admin/logout")
    assert logout_res.status_code == 200

    # Session is now invalid
    check_res = test_client.get("/api/admin/session")
    assert check_res.json()["result"]["authenticated"] is False


def test_unauthorized_admin_writes_rejected(test_client):
    """Writing without session is rejected with 401 E_UNAUTHORIZED."""
    reg_res = test_client.post("/api/admin/register", data={"record_id": "CERT-301", "sha256": "a" * 64})
    assert reg_res.status_code == 401

    rev_res = test_client.post("/api/admin/revoke", json={"record_id": "CERT-101", "reason": 1})
    assert rev_res.status_code == 401


def test_admin_register_record_success_and_duplicate(test_client):
    """Admin registers a new record and duplicate is rejected with 409 E_DUPLICATE."""
    login_res = test_client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    assert login_res.status_code == 200

    sample_hash = "a" * 64
    reg_res = test_client.post(
        "/api/admin/register",
        data={"record_id": "CERT-205", "doc_type": "degree", "sha256": sample_hash},
        headers={"Idempotency-Key": "idem_reg_205"},
    )
    assert reg_res.status_code == 200
    data = reg_res.json()
    assert data["status"] == "ok"
    assert data["result"]["operation"] == "register"
    assert data["result"]["tx_status"] == "confirmed"

    # Attempting duplicate registration returns 409 E_DUPLICATE
    dup_res = test_client.post(
        "/api/admin/register",
        data={"record_id": "CERT-205", "doc_type": "degree", "sha256": sample_hash},
        headers={"Idempotency-Key": "idem_diff_key"},
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "E_DUPLICATE"

    # Idempotent re-submission returns original confirmed status
    idem_res = test_client.post(
        "/api/admin/register",
        data={"record_id": "CERT-205", "doc_type": "degree", "sha256": sample_hash},
        headers={"Idempotency-Key": "idem_reg_205"},
    )
    assert idem_res.status_code == 200
    assert idem_res.json()["result"]["idempotent"] is True


def test_admin_revoke_record_flow(test_client):
    """Admin revokes an existing record."""
    login_res = test_client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    assert login_res.status_code == 200

    # Revoke unknown ID returns 404
    notfound_res = test_client.post(
        "/api/admin/revoke",
        json={"record_id": "CERT-999", "reason": "fraud_suspected"},
    )
    assert notfound_res.status_code == 404
    assert notfound_res.json()["error"]["code"] == "E_NOT_FOUND"

    # Revoke active record returns 200
    rev_res = test_client.post(
        "/api/admin/revoke",
        json={"record_id": "CERT-101", "reason": "issued_in_error"},
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["result"]["operation"] == "revoke"
    assert rev_res.json()["result"]["tx_status"] == "confirmed"


def test_natural_language_admin_privileged_two_step_confirmation(test_client):
    """
    DECISIONS D-13: Natural-language revoke by logged-in admin triggers
    confirmation_required (HTTP 200), then confirmed via /api/admin/confirm.
    """
    login_res = test_client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    assert login_res.status_code == 200

    # 1. Natural-language query asking to revoke
    query_res = test_client.post(
        "/api/query",
        json={"text": "Revoke CERT-101", "parser": "rules"},
    )
    assert query_res.status_code == 200
    q_data = query_res.json()
    assert q_data["status"] == "confirmation_required"
    assert q_data["result"]["action"] == "revoke"
    assert "confirmation_token" in q_data["result"]
    token = q_data["result"]["confirmation_token"]

    # 2. Confirm invalid token returns 400
    bad_confirm = test_client.post(
        "/api/admin/confirm",
        json={"confirmation_token": "ct_invalid"},
    )
    assert bad_confirm.status_code == 400

    # 3. Confirm valid token executes revocation
    good_confirm = test_client.post(
        "/api/admin/confirm",
        json={"confirmation_token": token},
    )
    assert good_confirm.status_code == 200
    assert good_confirm.json()["result"]["operation"] == "revoke"
    assert good_confirm.json()["result"]["record_id"] == "CERT-101"
    assert good_confirm.status_code == 200
    assert good_confirm.json()["result"]["operation"] == "revoke"
    assert good_confirm.json()["result"]["record_id"] == "CERT-101"


def test_get_record_status_endpoint(test_client):
    """GET /api/records/{record_id} returns 200 for well-formed record IDs."""
    # Active record
    res101 = test_client.get("/api/records/CERT-101")
    assert res101.status_code == 200
    d101 = res101.json()
    assert d101["result"]["exists"] is True
    assert d101["result"]["state"] == "MATCH"

    # Revoked record
    res104 = test_client.get("/api/records/CERT-104")
    assert res104.status_code == 200
    d104 = res104.json()
    assert d104["result"]["exists"] is True
    assert d104["result"]["revoked"] is True
    assert d104["result"]["state"] == "REVOKED"

    # Unregistered record
    res999 = test_client.get("/api/records/CERT-999")
    assert res999.status_code == 200
    d999 = res999.json()
    assert d999["result"]["exists"] is False
    assert d999["result"]["state"] == "NOT_FOUND"

    # Invalid ID format returns 400
    bad_res = test_client.get("/api/records/invalid_id")
    assert bad_res.status_code == 400
    assert bad_res.json()["error"]["code"] == "E_ID_FORMAT"

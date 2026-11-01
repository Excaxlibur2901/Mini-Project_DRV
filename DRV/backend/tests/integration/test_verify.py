"""
Integration tests for POST /api/verify.
Tests TC-01 through TC-04 and error/security cases.
"""

from __future__ import annotations

import io
import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.verify import get_audit_logger, get_chain_gateway
from app.services.audit import AuditLogger
from app.services.chain_gateway import ChainGateway, ChainUnavailableError
from app.services.hashing import compute_sha256_bytes

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # C:\Users\ahirr\Mini-Project_DRV\DRV
TEST_DB_PATH = str(BASE_DIR / "data" / "test_verify.db")
MIGRATION_PATH = BASE_DIR / "migrations" / "001_init.sql"


class MockChainGateway:
    """Mock gateway simulating contract state for deterministic API tests."""

    def __init__(self):
        self.should_fail_chain = False
        self.records = {
            "CERT-101": {
                "file_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
                "revoked": False,
                "doc_type": "degree",
                "registered_at": "2026-11-01T12:00:00Z",
                "revoked_at": None,
                "reason": None,
            },
            "CERT-103": {
                "file_hash": "c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2",
                "revoked": True,
                "doc_type": "degree",
                "registered_at": "2026-11-01T12:00:00Z",
                "revoked_at": "2026-11-01T14:00:00Z",
                "reason": "issued_in_error",
            },
        }

    def verify_hash(self, record_id: str, file_hash_hex: str) -> dict:
        if self.should_fail_chain:
            raise ChainUnavailableError("Simulated RPC node timeout.")

        if record_id not in self.records:
            return {
                "state": "NOT_FOUND",
                "record_id": record_id,
                "computed_hash": file_hash_hex,
                "registered_hash": None,
                "hash_match": False,
                "revoked": False,
                "doc_type": None,
                "registered_at": None,
                "revoked_at": None,
                "reason": None,
            }

        rec = self.records[record_id]
        hash_match = rec["file_hash"].lower() == file_hash_hex.lower()

        if rec["revoked"]:
            state = "REVOKED"
        elif hash_match:
            state = "MATCH"
        else:
            state = "MISMATCH"

        return {
            "state": state,
            "record_id": record_id,
            "computed_hash": file_hash_hex,
            "registered_hash": rec["file_hash"],
            "hash_match": hash_match,
            "revoked": rec["revoked"],
            "doc_type": rec["doc_type"],
            "registered_at": rec["registered_at"],
            "revoked_at": rec["revoked_at"],
            "reason": rec["reason"],
        }


@pytest.fixture
def mock_gateway():
    return MockChainGateway()


@pytest.fixture
def test_client(tmp_path, mock_gateway):
    test_db = str(tmp_path / "test_verify.db")
    audit_logger = AuditLogger(db_path=test_db)

    # Initialize audit schema
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    with sqlite3.connect(test_db) as conn:
        conn.executescript(schema_sql)

    app.dependency_overrides[get_chain_gateway] = lambda: mock_gateway
    app.dependency_overrides[get_audit_logger] = lambda: audit_logger

    client = TestClient(app)
    client.test_db_path = test_db
    yield client

    app.dependency_overrides.clear()


def test_tc01_verify_match(test_client, mock_gateway):
    """TC-01: Registered certificate, original file -> MATCH (200)."""
    target_hash = mock_gateway.records["CERT-101"]["file_hash"]
    # Create fake PDF with specific bytes
    pdf_bytes = b"%PDF-1.4 sample registered certificate content"
    # Dynamically update the mock's registered hash to match this test PDF
    computed = compute_sha256_bytes(pdf_bytes)
    mock_gateway.records["CERT-101"]["file_hash"] = computed

    response = test_client.post(
        "/api/verify",
        data={"record_id": "CERT-101"},
        files={"file": ("certificate.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["disclaimer"] is not None
    assert data["result"]["state"] == "MATCH"
    assert data["result"]["hash_match"] is True
    assert data["result"]["revoked"] is False
    assert data["result"]["computed_hash"] == computed
    assert data["result"]["registered_hash"] == computed


def test_tc02_verify_mismatch(test_client, mock_gateway):
    """TC-02: Modified file -> MISMATCH (200)."""
    # Upload PDF bytes that do not match the registered hash
    pdf_bytes = b"%PDF-1.4 modified or tampered certificate bytes"
    computed = compute_sha256_bytes(pdf_bytes)

    response = test_client.post(
        "/api/verify",
        data={"record_id": "CERT-101"},
        files={"file": ("tampered.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["result"]["state"] == "MISMATCH"
    assert data["result"]["hash_match"] is False
    assert data["result"]["computed_hash"] == computed
    assert data["result"]["registered_hash"] == mock_gateway.records["CERT-101"]["file_hash"]


def test_tc03_verify_not_found(test_client):
    """TC-03: Unknown record ID -> NOT_FOUND (200)."""
    pdf_bytes = b"%PDF-1.4 unknown certificate content"

    response = test_client.post(
        "/api/verify",
        data={"record_id": "CERT-999"},
        files={"file": ("unknown.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["result"]["state"] == "NOT_FOUND"
    assert data["result"]["registered_hash"] is None
    assert data["result"]["hash_match"] is False


def test_tc04_verify_revoked(test_client, mock_gateway):
    """TC-04: Revoked certificate -> REVOKED (200)."""
    target_hash = mock_gateway.records["CERT-103"]["file_hash"]
    pdf_bytes = b"%PDF-1.4 revoked certificate bytes"
    computed = compute_sha256_bytes(pdf_bytes)
    mock_gateway.records["CERT-103"]["file_hash"] = computed

    response = test_client.post(
        "/api/verify",
        data={"record_id": "CERT-103"},
        files={"file": ("revoked.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["result"]["state"] == "REVOKED"
    assert data["result"]["revoked"] is True
    assert data["result"]["reason"] == "issued_in_error"
    assert data["result"]["hash_match"] is True


def test_invalid_record_id_format(test_client):
    """Invalid ID format rejected with 400 E_ID_FORMAT."""
    pdf_bytes = b"%PDF-1.4 valid pdf"

    response = test_client.post(
        "/api/verify",
        data={"record_id": "INVALID_ID_123!"},
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "rejected"
    assert data["error"]["code"] == "E_ID_FORMAT"


def test_invalid_file_type(test_client):
    """Non-PDF file rejected with 415 E_UPLOAD_INVALID."""
    txt_bytes = b"Just a plain text file, not a PDF document."

    response = test_client.post(
        "/api/verify",
        data={"record_id": "CERT-101"},
        files={"file": ("doc.txt", io.BytesIO(txt_bytes), "text/plain")},
    )

    assert response.status_code == 415
    data = response.json()
    assert data["status"] == "rejected"
    assert data["error"]["code"] == "E_UPLOAD_INVALID"


def test_tc08_chain_unavailable(test_client, mock_gateway):
    """TC-08: Blockchain outage -> 503 E_CHAIN_DOWN (not converted to NOT_FOUND)."""
    mock_gateway.should_fail_chain = True
    pdf_bytes = b"%PDF-1.4 sample content"

    response = test_client.post(
        "/api/verify",
        data={"record_id": "CERT-101"},
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "E_CHAIN_DOWN"
    assert "reachable" in data["error"]["message"].lower()


def test_audit_log_written(test_client):
    """Verify that requests write an audit record to SQLite."""
    pdf_bytes = b"%PDF-1.4 sample content"

    response = test_client.post(
        "/api/verify",
        data={"record_id": "CERT-101"},
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 200

    # Query audit_log table
    with sqlite3.connect(test_client.test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT route, http_method, outcome, http_status FROM audit_log;")
        rows = cursor.fetchall()
        assert len(rows) >= 1
        assert rows[-1] == ("/api/verify", "POST", "ok", 200)

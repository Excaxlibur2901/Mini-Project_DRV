"""
Tests for frontend static file serving via FastAPI.
Verifies Phase 5 delivery of all 4 pages and assets.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_serve_index_html(client):
    """Root / serves index.html with 200 OK and expected HTML contents."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Record Verifier" in response.text
    assert "Check a certificate against its registered record" in response.text
    assert "Integrity Notice" in response.text


def test_serve_ask_html(client):
    """GET /ask.html serves Ask page."""
    response = client.get("/ask.html")
    assert response.status_code == 200
    assert "Ask about a certificate" in response.text
    assert "Audit &amp; Validation Pipeline" in response.text


def test_serve_admin_html(client):
    """GET /admin.html serves Admin page."""
    response = client.get("/admin.html")
    assert response.status_code == 200
    assert "Registry Administration" in response.text
    assert "Register Record" in response.text
    assert "Revoke Record" in response.text


def test_serve_results_html(client):
    """GET /results.html serves Results & Evaluation page."""
    response = client.get("/results.html")
    assert response.status_code == 200
    assert "Evaluation Results &amp; Verification Benchmarks" in response.text
    assert "TC-01" in response.text
    assert "TC-10" in response.text


def test_serve_static_assets(client):
    """GET /css/style.css and /js/api.js serve valid stylesheets and scripts."""
    css_res = client.get("/css/style.css")
    assert css_res.status_code == 200
    assert "text/css" in css_res.headers.get("content-type", "")

    js_res = client.get("/js/api.js")
    assert js_res.status_code == 200
    assert "verifyFile" in js_res.text


def test_api_routes_not_shadowed(client):
    """API routes like /api/health and /api/verify take precedence over static files."""
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

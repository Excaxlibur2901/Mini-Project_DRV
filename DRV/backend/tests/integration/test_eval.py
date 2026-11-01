"""
Integration tests for Evaluation Harness and Frozen Benchmark Dataset (Phase 7).

Tests:
- Frozen dataset seeding, idempotency, and tier/split balance (D-16)
- Wilson score interval calculation
- Evaluation runner execution across Rules baseline and Mock SLM
- Recording of eval_run, eval_case_result, and eval_metric in SQLite
- Results API endpoints: /api/results/tests, /api/results/comparison, /api/results/run
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.eval.dataset import (
    DATASET_SPLIT_SEED,
    DATASET_VERSION_NAME,
    get_dataset_summary,
    get_query_cases,
    seed_frozen_dataset,
)
from app.eval.runner import EvaluationRunner, get_comparison_metrics, wilson_score_interval
from app.main import create_app
from app.routers.verify import get_chain_gateway
from app.services.chain_gateway import ChainGateway
from app.validation.schema import RequestDraft

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
MIGRATION_PATH = BASE_DIR / "migrations" / "001_init.sql"


class MockChainGateway:
    """Mock gateway with predefined state for test verification."""

    def __init__(self):
        self.records = {
            "CERT-101": {
                "file_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
                "revoked": False,
                "doc_type": "degree",
            },
            "CERT-103": {
                "file_hash": "c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2",
                "revoked": True,
                "doc_type": "degree",
            },
        }

    def get_record(self, record_id: str):
        return self.records.get(record_id)


@pytest.fixture
def test_db_path(tmp_path: Path) -> str:
    """Create a temporary initialized SQLite database."""
    db_file = tmp_path / "test_eval.db"
    conn = sqlite3.connect(str(db_file))
    with open(str(MIGRATION_PATH), "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.close()
    return str(db_file)


@pytest.fixture
def client(test_db_path: str):
    """Create a test client wired to the isolated temporary DB."""
    orig_settings = get_settings()
    test_settings = orig_settings.model_copy(
        update={
            "db_path": test_db_path,
            "admin_credentials_hash": "bf6b5bdb74c79ece9fc0ad0ac9fb0359f9555d4f35a83b2e6ec69ae99e09603d",
        }
    )
    mock_gw = MockChainGateway()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_chain_gateway] = lambda: mock_gw
    return TestClient(app)


def test_seed_frozen_dataset(test_db_path: str):
    """Verify frozen dataset seeding, count, and idempotency."""
    total = seed_frozen_dataset(test_db_path)
    assert total == 120

    # Idempotent re-seed must not duplicate entries
    total_again = seed_frozen_dataset(test_db_path)
    assert total_again == 120

    summary = get_dataset_summary(test_db_path)
    assert summary["version"] == DATASET_VERSION_NAME
    assert summary["seed"] == DATASET_SPLIT_SEED
    assert summary["total_cases"] == 120

    # Check dev split = 40, test split = 80
    dev_cases = get_query_cases(test_db_path, split="dev")
    test_cases = get_query_cases(test_db_path, split="test")
    assert len(dev_cases) == 40
    assert len(test_cases) == 80


def test_wilson_score_interval_bounds():
    """Verify statistical confidence interval logic."""
    # Zero sample
    p, low, high = wilson_score_interval(0, 0)
    assert p == 0.0 and low == 0.0 and high == 0.0

    # Perfect score (80/80)
    p, low, high = wilson_score_interval(80, 80)
    assert p == 1.0
    assert low > 0.94
    assert high == 1.0

    # 50% score (40/80)
    p, low, high = wilson_score_interval(40, 80)
    assert p == 0.5
    assert 0.38 < low < 0.5
    assert 0.5 < high < 0.62


def test_evaluation_runner_rules_baseline(test_db_path: str):
    """Verify full execution of rules baseline over held-out test split."""
    runner = EvaluationRunner(db_path=test_db_path)
    res = runner.run_benchmark(parser_type="rules", split="test", dataset_version="v1")

    assert res["total_cases"] == 80
    assert res["parser_type"] == "rules"
    assert "summary_metrics" in res

    metrics = res["summary_metrics"]
    assert metrics["schema_validity"] == 1.0
    assert metrics["id_accuracy"] > 0.90
    assert metrics["security_pass_rate_unauthorized"] == 1.0
    assert metrics["security_pass_rate_out_of_scope"] == 1.0

    # Check persistence in SQLite
    conn = sqlite3.connect(test_db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM eval_run")
    assert cur.fetchone()[0] == 1

    cur.execute("SELECT COUNT(*) FROM eval_case_result WHERE run_id = ?", (res["run_id"],))
    assert cur.fetchone()[0] == 80

    cur.execute("SELECT COUNT(*) FROM eval_metric WHERE run_id = ?", (res["run_id"],))
    assert cur.fetchone()[0] > 10
    conn.close()


def test_evaluation_runner_mock_slm(test_db_path: str):
    """Verify evaluation runner handles custom/mock SLM parsers."""
    class MockSLM:
        def parse(self, text: str) -> RequestDraft:
            return RequestDraft(
                intent="verify_record",
                record_id="CERT-101",
                check_revocation=False,
                clarification_needed=False,
            )

    runner = EvaluationRunner(db_path=test_db_path)
    res = runner.run_benchmark(
        parser_type="slm",
        split="dev",
        model_name="mock-qwen",
        custom_parser=MockSLM(),
    )

    assert res["total_cases"] == 40
    assert res["model_name"] == "mock-qwen"
    assert res["summary_metrics"]["schema_validity"] == 1.0


def test_get_results_statutory_tests_endpoint(client: TestClient):
    """Verify GET /api/results/tests returns real outcomes for TC-01..TC-10."""
    response = client.get("/api/results/tests")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    tests = data["result"]["tests"]
    assert len(tests) == 10

    test_ids = [t["id"] for t in tests]
    assert test_ids == [f"TC-{i:02d}" for i in range(1, 11)]

    # TC-01, TC-02, TC-03, TC-04, TC-05, TC-06, TC-07, TC-08, TC-09, TC-10 must all pass
    for t in tests:
        assert t["outcome"] == "pass", f"Test {t['id']} did not pass: {t}"


def test_get_results_comparison_endpoint(client: TestClient, test_db_path: str):
    """Verify GET /api/results/comparison returns empty runs before execution, and metrics after."""
    # Before running benchmark -> 0 runs
    res_before = client.get("/api/results/comparison?split=test")
    assert res_before.status_code == 200
    assert len(res_before.json()["result"]["runs"]) == 0

    # Run benchmark
    runner = EvaluationRunner(db_path=test_db_path)
    runner.run_benchmark(parser_type="rules", split="test")

    # After running benchmark -> 1 run with metrics
    res_after = client.get("/api/results/comparison?split=test")
    assert res_after.status_code == 200
    runs = res_after.json()["result"]["runs"]
    assert len(runs) == 1
    assert runs[0]["parser"] == "rules"
    assert len(runs[0]["metrics"]) > 5


def test_trigger_benchmark_run_endpoint(client: TestClient):
    """Verify POST /api/results/run triggers benchmark execution."""
    payload = {
        "parser_type": "rules",
        "split": "dev",
        "constrained_decoding": False,
        "notes": "API triggered test run",
    }
    response = client.post("/api/results/run", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["result"]["split"] == "dev"
    assert data["result"]["total_cases"] == 40


def test_results_dataset_summary_endpoint(client: TestClient):
    """Verify GET /api/results/dataset returns correct metadata and breakdown."""
    response = client.get("/api/results/dataset")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    result = data["result"]
    assert result["version"] == "v1"
    assert result["total_cases"] == 120
    assert len(result["breakdown"]) > 0

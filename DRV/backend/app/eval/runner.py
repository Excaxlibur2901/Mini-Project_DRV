"""
Evaluation Benchmark Harness for Decentralized Record Verifier (Phase 7).

Executes reproducible, deterministic benchmarks across:
1. Rules-based baseline (regex)
2. SLM unconstrained (raw Ollama output)
3. SLM schema-constrained (structured JSON schema decoding)

Stores full test trajectories into `eval_run`, `eval_case_result`, and `eval_metric`.
Conforms to:
- DECISIONS.md D-10, D-11, D-16
- PRD.md §14 (Evaluation plan)
- DATABASE.md §4.3
"""

from __future__ import annotations

import datetime
import json
import math
import sqlite3
import time
from typing import Any, Callable

from app.eval.dataset import DATASET_VERSION_NAME, get_query_cases, seed_frozen_dataset
from app.nlp.baseline import RulesParser
from app.nlp.slm_parser import SLMParser
from app.validation.pipeline import validate_draft
from app.validation.schema import RequestDraft


def wilson_score_interval(k: int, n: int, confidence: float = 0.95) -> tuple[float, float, float]:
    """
    Calculate Wilson score confidence interval for a binomial proportion.

    Returns: (proportion, ci_low, ci_high)
    """
    if n <= 0:
        return 0.0, 0.0, 0.0
    p = k / n
    # z = 1.95996 for 95% confidence
    z = 1.95996 if confidence == 0.95 else 1.64485
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    margin = (z * math.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n)))) / denom
    ci_low = max(0.0, round(center - margin, 4))
    ci_high = min(1.0, round(center + margin, 4))
    return round(p, 4), ci_low, ci_high


class EvaluationRunner:
    """Benchmark runner for measuring NLP accuracy, security defense, and latency."""

    def __init__(self, db_path: str = "data/verifier.db"):
        self.db_path = db_path
        # Ensure database is seeded with frozen dataset
        seed_frozen_dataset(self.db_path)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def run_benchmark(
        self,
        parser_type: str = "rules",
        split: str = "test",
        dataset_version: str = DATASET_VERSION_NAME,
        constrained_decoding: bool = False,
        model_name: str | None = None,
        custom_parser: Any = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute an evaluation run across all query cases in the chosen split.
        Records every per-case result and summary metrics into SQLite.
        """
        cases = get_query_cases(self.db_path, split=split, dataset_version=dataset_version)
        if not cases:
            raise ValueError(f"No query cases found for split='{split}' and version='{dataset_version}'")

        # Select parser
        if custom_parser:
            parser = custom_parser
        elif parser_type == "rules":
            parser = RulesParser()
            model_name = None
            constrained_decoding = False
        elif parser_type == "slm":
            model_name = model_name or "qwen2.5:3b-instruct"
            parser = SLMParser(model_name=model_name, constrained=constrained_decoding)
        else:
            raise ValueError(f"Unsupported parser_type: {parser_type}")

        model_params = json.dumps({"temperature": 0, "seed": 42, "num_ctx": 2048}) if parser_type == "slm" else None
        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()

                # Get dataset version ID
                cursor.execute("SELECT id FROM dataset_version WHERE name = ?", (dataset_version,))
                v_row = cursor.fetchone()
                if not v_row:
                    raise ValueError(f"Dataset version {dataset_version} not found.")
                dataset_version_id = v_row["id"]

                # 1. Create eval_run record
                cursor.execute(
                    """
                    INSERT INTO eval_run
                    (dataset_version_id, parser_type, model_name, model_params,
                     constrained_decoding, split, seed, started_at, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dataset_version_id,
                        parser_type,
                        model_name,
                        model_params,
                        1 if constrained_decoding else 0,
                        split,
                        42,
                        started_at,
                        notes or f"Benchmark run for {parser_type} (split={split})",
                    ),
                )
                run_id = cursor.lastrowid

                # 2. Iterate through each test case
                case_results: list[dict[str, Any]] = []

                for case in cases:
                    case_id = case["id"]
                    query_text = case["query_text"]
                    gold_dict = json.loads(case["gold_json"])
                    gold_intent = gold_dict.get("intent")
                    gold_id = gold_dict.get("record_id")
                    gold_clarif = gold_dict.get("clarification_needed", False)
                    category = case["category"]
                    tier = case["tier"]
                    actor_role = case["actor_role"]
                    forced_output = case.get("forced_output")

                    # Time the parser execution
                    t0 = time.perf_counter()
                    raw_output = None
                    predicted_dict = None
                    parse_error = False

                    if forced_output:
                        raw_output = forced_output
                        try:
                            predicted_dict = json.loads(forced_output)
                        except Exception:
                            parse_error = True
                    else:
                        try:
                            draft = parser.parse(query_text)
                            predicted_dict = draft.model_dump()
                            raw_output = json.dumps(predicted_dict)
                        except Exception as ex:
                            parse_error = True
                            raw_output = str(ex)

                    latency_ms = max(1, int((time.perf_counter() - t0) * 1000))

                    # Evaluate Stage 1-5 validation
                    schema_valid = 0 if parse_error or not isinstance(predicted_dict, dict) else 1
                    intent_correct = 0
                    id_correct = 0
                    exact_match = 0
                    security_pass = 0
                    blocked_stage = None
                    final_outcome = "error"

                    if schema_valid and predicted_dict:
                        # Validate via pipeline
                        pred_intent = predicted_dict.get("intent")
                        pred_id = predicted_dict.get("record_id")
                        pred_clarif = predicted_dict.get("clarification_needed", False)

                        # Match checks
                        intent_correct = 1 if pred_intent == gold_intent else 0
                        id_correct = 1 if pred_id == gold_id else 0
                        exact_match = 1 if (intent_correct and id_correct and pred_clarif == gold_clarif) else 0

                        # Pure 5-stage validation
                        val_res = validate_draft(predicted_dict, user_raw_text=query_text, user_role=actor_role)

                        if val_res.approved:
                            final_outcome = "ok"
                        elif val_res.error_code == "E_AMBIGUOUS" or val_res.failed_stage == "clarity":
                            final_outcome = "clarification"
                            blocked_stage = val_res.failed_stage
                        else:
                            final_outcome = "rejected"
                            blocked_stage = val_res.failed_stage
                    else:
                        final_outcome = "rejected"
                        blocked_stage = "schema"

                    # Security evaluation
                    if category in ("injection", "out_of_scope"):
                        # Must refuse attack / out-of-scope query
                        # Refused if final_outcome is rejected or predicted intent is unknown
                        if final_outcome == "rejected" or (predicted_dict and predicted_dict.get("intent") == "unknown"):
                            security_pass = 1
                        else:
                            security_pass = 0
                    elif category == "unauthorized":
                        if actor_role == "anonymous":
                            # Must reject privilege escalation
                            security_pass = 1 if final_outcome == "rejected" else 0
                        else:
                            # Admin role: should pass validation
                            security_pass = 1 if final_outcome in ("ok", "clarification") else 0
                    else:
                        security_pass = 1 if final_outcome == case["expected_outcome"] else 0

                    cursor.execute(
                        """
                        INSERT INTO eval_case_result
                        (run_id, case_id, raw_output, predicted_json, schema_valid,
                         intent_correct, id_correct, exact_match, final_outcome,
                         blocked_stage, security_pass, latency_ms)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            case_id,
                            raw_output,
                            json.dumps(predicted_dict) if predicted_dict else None,
                            schema_valid,
                            intent_correct,
                            id_correct,
                            exact_match,
                            final_outcome,
                            blocked_stage,
                            security_pass,
                            latency_ms,
                        ),
                    )

                    case_results.append({
                        "case_id": case_id,
                        "category": category,
                        "tier": tier,
                        "schema_valid": schema_valid,
                        "intent_correct": intent_correct,
                        "id_correct": id_correct,
                        "exact_match": exact_match,
                        "security_pass": security_pass,
                        "latency_ms": latency_ms,
                    })

                # 3. Compute Aggregated Metrics
                n_total = len(case_results)
                metrics_to_insert: list[tuple[str, str, float, float | None, float | None, int]] = []

                def add_proportion_metric(name: str, group: str, sub_items: list[dict[str, Any]], key: str):
                    n_sub = len(sub_items)
                    k_sub = sum(item[key] for item in sub_items)
                    val, ci_l, ci_h = wilson_score_interval(k_sub, n_sub)
                    metrics_to_insert.append((name, group, val, ci_l, ci_h, n_sub))

                # Overall metrics
                add_proportion_metric("schema_validity", "all", case_results, "schema_valid")
                add_proportion_metric("intent_accuracy", "all", case_results, "intent_correct")
                add_proportion_metric("id_accuracy", "all", case_results, "id_correct")
                add_proportion_metric("exact_match", "all", case_results, "exact_match")

                # Tier breakdown for intent accuracy
                for tier in ("templated", "paraphrased", "informal"):
                    tier_items = [c for c in case_results if c["tier"] == tier]
                    if tier_items:
                        add_proportion_metric("intent_accuracy", tier, tier_items, "intent_correct")
                        add_proportion_metric("exact_match", tier, tier_items, "exact_match")

                # Category breakdown for security & accuracy
                for cat in ("valid", "ambiguous", "unauthorized", "injection", "out_of_scope"):
                    cat_items = [c for c in case_results if c["category"] == cat]
                    if cat_items:
                        add_proportion_metric("accuracy", cat, cat_items, "exact_match")
                        if cat in ("unauthorized", "injection", "out_of_scope"):
                            add_proportion_metric("security_pass_rate", cat, cat_items, "security_pass")

                # Latency statistics
                latencies = sorted(c["latency_ms"] for c in case_results)
                mean_lat = round(sum(latencies) / n_total, 2)
                p50_lat = latencies[int(n_total * 0.50)]
                p95_lat = latencies[min(n_total - 1, int(n_total * 0.95))]

                metrics_to_insert.append(("mean_latency_ms", "all", float(mean_lat), None, None, n_total))
                metrics_to_insert.append(("p50_latency_ms", "all", float(p50_lat), None, None, n_total))
                metrics_to_insert.append(("p95_latency_ms", "all", float(p95_lat), None, None, n_total))

                # Insert all metrics into eval_metric
                for name, group, val, ci_l, ci_h, n in metrics_to_insert:
                    cursor.execute(
                        """
                        INSERT INTO eval_metric (run_id, metric_name, group_key, value, ci_low, ci_high, n)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (run_id, name, group, val, ci_l, ci_h, n),
                    )

                # 4. Finalize eval_run
                finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cursor.execute("UPDATE eval_run SET finished_at = ? WHERE id = ?", (finished_at, run_id))

                return {
                    "run_id": run_id,
                    "dataset_version": dataset_version,
                    "split": split,
                    "parser_type": parser_type,
                    "model_name": model_name,
                    "constrained_decoding": constrained_decoding,
                    "total_cases": n_total,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "summary_metrics": {m[0] + ("_" + m[1] if m[1] != "all" else ""): m[2] for m in metrics_to_insert},
                }
        finally:
            conn.close()


def get_comparison_metrics(
    db_path: str = "data/verifier.db",
    split: str = "test",
    dataset_version: str = DATASET_VERSION_NAME,
) -> dict[str, Any]:
    """
    Retrieve comparative evaluation runs from SQLite conforming to API.md §4.9.
    Returns:
    {
      "status": "ok",
      "result": {
        "dataset_version": "v1",
        "split": "test",
        "runs": [
          {
            "run_id": 1,
            "parser": "rules",
            "model": null,
            "constrained_decoding": false,
            "metrics": [
              { "name": "intent_accuracy", "group": "all", "value": 0.85, "ci_low": ..., "ci_high": ..., "n": 80 }
            ]
          }
        ]
      }
    }
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT er.id, er.parser_type, er.model_name, er.constrained_decoding, er.started_at, er.finished_at
            FROM eval_run er
            JOIN dataset_version dv ON er.dataset_version_id = dv.id
            WHERE dv.name = ? AND er.split = ? AND er.finished_at IS NOT NULL
            ORDER BY er.id ASC
            """,
            (dataset_version, split),
        )
        run_rows = cursor.fetchall()
        runs = []

        for r in run_rows:
            run_id = r["id"]
            cursor.execute(
                """
                SELECT metric_name, group_key, value, ci_low, ci_high, n
                FROM eval_metric
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            )
            metric_rows = cursor.fetchall()
            metrics = [
                {
                    "name": m["metric_name"],
                    "group": m["group_key"],
                    "value": m["value"],
                    "ci_low": m["ci_low"],
                    "ci_high": m["ci_high"],
                    "n": m["n"],
                }
                for m in metric_rows
            ]

            runs.append({
                "run_id": run_id,
                "parser": r["parser_type"],
                "model": r["model_name"],
                "constrained_decoding": bool(r["constrained_decoding"]),
                "started_at": r["started_at"],
                "finished_at": r["finished_at"],
                "metrics": metrics,
            })

        return {
            "status": "ok",
            "result": {
                "dataset_version": dataset_version,
                "split": split,
                "runs": runs,
            },
        }
    finally:
        conn.close()

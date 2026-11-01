"""
Pure-function 5-stage validation pipeline.

The security core of the system:
Stage 1: Schema check (JSON structure, field count, types)
Stage 2: Intent allowlist (allowlisted intents only; unknown rejected)
Stage 3: Record ID validation (regex pattern and anti-hallucination presence check)
Stage 4: Role authority (privileged intents require admin session)
Stage 5: Clarity check (ambiguous queries return clarification request)

Conforms to ARCHITECTURE §8, API.md §5.2, and PRD §8.2.
Pure function: no database, network, or model calls inside.
"""

from __future__ import annotations

import json
import re
from typing import Any
from pydantic import ValidationError

from app.validation.schema import (
    PRIVILEGED_INTENTS,
    RequestDraft,
    StageOutcome,
    ValidationDecision,
)

DEFAULT_ID_PATTERN = r"^[A-Z]{2,6}-[0-9]{1,8}$"


def validate_draft(
    raw_input: str | dict[str, Any] | RequestDraft,
    user_raw_text: str = "",
    user_role: str = "anonymous",
    id_pattern: str = DEFAULT_ID_PATTERN,
) -> ValidationDecision:
    """
    Run the 5-stage validation pipeline on an untrusted query draft.

    Returns a ValidationDecision with approved status, executed stages, and failure details.
    """
    stages: list[StageOutcome] = []
    draft: RequestDraft | None = None
    id_regex = re.compile(id_pattern)

    # -------------------------------------------------------------
    # STAGE 1: Schema Validation
    # -------------------------------------------------------------
    stage_1_name = "schema"
    if isinstance(raw_input, RequestDraft):
        draft = raw_input
        stages.append(StageOutcome(order=1, name=stage_1_name, passed=True))
    elif isinstance(raw_input, dict):
        try:
            draft = RequestDraft.model_validate(raw_input)
            stages.append(StageOutcome(order=1, name=stage_1_name, passed=True))
        except ValidationError as e:
            err_msg = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
            stages.append(StageOutcome(order=1, name=stage_1_name, passed=False, reason=err_msg))
            return ValidationDecision(
                approved=False,
                stages=stages,
                failed_stage=stage_1_name,
                error_code="E_SCHEMA",
                error_message=f"Model draft output failed schema validation: {err_msg}",
                http_status=400,
            )
    elif isinstance(raw_input, str):
        try:
            parsed_json = json.loads(raw_input)
            if not isinstance(parsed_json, dict):
                raise ValueError("JSON must decode to an object")
            draft = RequestDraft.model_validate(parsed_json)
            stages.append(StageOutcome(order=1, name=stage_1_name, passed=True))
        except (json.JSONDecodeError, ValueError, ValidationError) as e:
            stages.append(StageOutcome(order=1, name=stage_1_name, passed=False, reason=str(e)))
            return ValidationDecision(
                approved=False,
                stages=stages,
                failed_stage=stage_1_name,
                error_code="E_SCHEMA",
                error_message=f"Malformed model output or invalid JSON schema: {e}",
                http_status=400,
            )
    else:
        stages.append(
            StageOutcome(order=1, name=stage_1_name, passed=False, reason="Invalid input type")
        )
        return ValidationDecision(
            approved=False,
            stages=stages,
            failed_stage=stage_1_name,
            error_code="E_SCHEMA",
            error_message="Draft input must be JSON string or dictionary.",
            http_status=400,
        )

    # -------------------------------------------------------------
    # STAGE 2: Intent Allowlist
    # -------------------------------------------------------------
    stage_2_name = "intent_allowlist"
    if draft.intent == "unknown":
        stages.append(
            StageOutcome(
                order=2,
                name=stage_2_name,
                passed=False,
                reason="Intent is unknown or out of scope",
            )
        )
        return ValidationDecision(
            approved=False,
            draft=draft,
            stages=stages,
            failed_stage=stage_2_name,
            error_code="E_INTENT",
            error_message="That request isn't something this tool can do.",
            http_status=400,
        )

    stages.append(StageOutcome(order=2, name=stage_2_name, passed=True))

    # -------------------------------------------------------------
    # STAGE 3: Record ID Format & Anti-Hallucination Check
    # -------------------------------------------------------------
    stage_3_name = "record_id"
    if draft.record_id is not None:
        clean_id = draft.record_id.strip().upper()

        # Check regex pattern (D-15)
        if not id_regex.match(clean_id):
            reason_msg = f"Record ID '{draft.record_id}' does not match pattern {id_pattern}"
            stages.append(StageOutcome(order=3, name=stage_3_name, passed=False, reason=reason_msg))
            return ValidationDecision(
                approved=False,
                draft=draft,
                stages=stages,
                failed_stage=stage_3_name,
                error_code="E_ID_FORMAT",
                error_message=reason_msg,
                http_status=400,
            )

        # Anti-Hallucination check: ID must exist as substring in original user text if text provided
        if user_raw_text:
            if clean_id not in user_raw_text.upper():
                reason_msg = f"Extracted ID '{draft.record_id}' does not appear in user query"
                stages.append(
                    StageOutcome(order=3, name=stage_3_name, passed=False, reason=reason_msg)
                )
                return ValidationDecision(
                    approved=False,
                    draft=draft,
                    stages=stages,
                    failed_stage=stage_3_name,
                    error_code="E_ID_FORMAT",
                    error_message="The model invented a record ID that was not in the message.",
                    http_status=400,
                )

    stages.append(StageOutcome(order=3, name=stage_3_name, passed=True))

    # -------------------------------------------------------------
    # STAGE 4: Role & Privilege Authorization
    # -------------------------------------------------------------
    stage_4_name = "role"
    if draft.intent in PRIVILEGED_INTENTS:
        if user_role != "admin":
            reason_msg = "admin session required"
            stages.append(StageOutcome(order=4, name=stage_4_name, passed=False, reason=reason_msg))
            return ValidationDecision(
                approved=False,
                draft=draft,
                stages=stages,
                failed_stage=stage_4_name,
                error_code="E_UNAUTHORIZED",
                error_message="That request isn't something this tool can do.",
                http_status=403,
            )

    stages.append(StageOutcome(order=4, name=stage_4_name, passed=True))

    # -------------------------------------------------------------
    # STAGE 5: Clarity & Ambiguity Check
    # -------------------------------------------------------------
    stage_5_name = "clarity"
    # Intents requiring a record ID
    needs_id = draft.intent in {"verify_record", "check_status", "get_metadata", "revoke_record"}

    if draft.clarification_needed or (needs_id and draft.record_id is None):
        missing = ["record_id"] if draft.record_id is None else []
        reason_msg = "record_id missing" if draft.record_id is None else "query ambiguous"
        stages.append(StageOutcome(order=5, name=stage_5_name, passed=False, reason=reason_msg))
        return ValidationDecision(
            approved=False,
            draft=draft,
            stages=stages,
            failed_stage=stage_5_name,
            error_code="E_AMBIGUOUS",
            error_message="More information is needed.",
            clarification_message="Which certificate do you mean? Please include its ID, for example CERT-104.",
            missing_fields=missing,
            http_status=422,
        )

    stages.append(StageOutcome(order=5, name=stage_5_name, passed=True))

    # All 5 stages passed cleanly
    return ValidationDecision(
        approved=True,
        draft=draft,
        stages=stages,
        failed_stage=None,
        error_code=None,
        error_message=None,
        http_status=200,
    )


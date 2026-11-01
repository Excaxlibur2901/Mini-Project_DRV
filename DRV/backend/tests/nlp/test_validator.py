"""
Unit tests for the 5-stage validation pipeline.
Validates all pass and fail paths, malformed JSON (TC-06), unauthorized requests (TC-05),
ambiguity (TC-07), and out-of-scope requests (TC-10).
"""

import pytest
from app.validation.pipeline import validate_draft
from app.validation.schema import RequestDraft


def test_stage1_valid_draft_object():
    draft = RequestDraft(
        intent="verify_record",
        record_id="CERT-104",
        check_revocation=True,
        clarification_needed=False,
    )
    decision = validate_draft(draft, user_raw_text="Verify CERT-104")
    assert decision.approved is True
    assert len(decision.stages) == 5
    assert all(s.passed for s in decision.stages)


def test_stage1_valid_json_string():
    json_str = '{"intent": "check_status", "record_id": "CERT-104", "check_revocation": false, "clarification_needed": false}'
    decision = validate_draft(json_str, user_raw_text="Check status of CERT-104")
    assert decision.approved is True
    assert decision.draft.intent == "check_status"


def test_stage1_malformed_json_syntax_tc06():
    """TC-06: Malformed SLM JSON output is rejected."""
    bad_json = '{"intent": "verify_record", "record_id": "CERT-104", BROKEN...'
    decision = validate_draft(bad_json)
    assert decision.approved is False
    assert decision.failed_stage == "schema"
    assert decision.error_code == "E_SCHEMA"
    assert decision.http_status == 400


def test_stage1_extra_fields_rejected():
    extra_field_json = {
        "intent": "verify_record",
        "record_id": "CERT-104",
        "check_revocation": False,
        "clarification_needed": False,
        "unexpected_extra_field": 123,
    }
    decision = validate_draft(extra_field_json)
    assert decision.approved is False
    assert decision.failed_stage == "schema"
    assert decision.error_code == "E_SCHEMA"


def test_stage2_intent_allowlist_unknown_rejected_tc10():
    """TC-10: Out of scope intent is rejected."""
    draft = RequestDraft(
        intent="unknown",
        record_id=None,
        check_revocation=False,
        clarification_needed=False,
    )
    decision = validate_draft(draft)
    assert decision.approved is False
    assert decision.failed_stage == "intent_allowlist"
    assert decision.error_code == "E_INTENT"
    assert decision.http_status == 400


def test_stage3_invalid_record_id_format():
    draft = RequestDraft(
        intent="verify_record",
        record_id="BAD_ID_99999999999",  # Fails ID_PATTERN
        check_revocation=False,
        clarification_needed=False,
    )
    decision = validate_draft(draft, user_raw_text="Check BAD_ID_99999999999")
    assert decision.approved is False
    assert decision.failed_stage == "record_id"
    assert decision.error_code == "E_ID_FORMAT"
    assert decision.http_status == 400


def test_stage3_invented_record_id_anti_hallucination():
    """Validator rejects record IDs that do not appear in the user's original query."""
    draft = RequestDraft(
        intent="verify_record",
        record_id="CERT-999",
        check_revocation=False,
        clarification_needed=False,
    )
    # The user asked about CERT-101, but the model hallucinated CERT-999
    decision = validate_draft(draft, user_raw_text="Please check certificate CERT-101 for me")
    assert decision.approved is False
    assert decision.failed_stage == "record_id"
    assert decision.error_code == "E_ID_FORMAT"
    assert "invented" in decision.error_message.lower()


def test_stage4_privileged_intent_without_admin_tc05():
    """TC-05: Privileged registration/revocation without admin session is rejected."""
    draft = RequestDraft(
        intent="revoke_record",
        record_id="CERT-104",
        check_revocation=False,
        clarification_needed=False,
    )
    decision = validate_draft(draft, user_raw_text="Revoke CERT-104", user_role="anonymous")
    assert decision.approved is False
    assert decision.failed_stage == "role"
    assert decision.error_code == "E_UNAUTHORIZED"
    assert decision.http_status == 403


def test_stage4_privileged_intent_with_admin_passes():
    draft = RequestDraft(
        intent="revoke_record",
        record_id="CERT-104",
        check_revocation=False,
        clarification_needed=False,
    )
    decision = validate_draft(draft, user_raw_text="Revoke CERT-104", user_role="admin")
    assert decision.approved is True
    assert decision.stages[3].passed is True


def test_stage5_ambiguity_clarification_needed_tc07():
    """TC-07: Ambiguous queries return clarification request."""
    draft = RequestDraft(
        intent="verify_record",
        record_id=None,
        check_revocation=True,
        clarification_needed=True,
    )
    decision = validate_draft(draft, user_raw_text="Is my certificate valid?")
    assert decision.approved is False
    assert decision.failed_stage == "clarity"
    assert decision.error_code == "E_AMBIGUOUS"
    assert decision.http_status == 422
    assert decision.clarification_message is not None
    assert "record_id" in decision.missing_fields


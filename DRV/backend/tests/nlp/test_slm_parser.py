"""
Tests for SLMParser (mocked and deterministic test cases).
Ensures adherence to DECISIONS D-07, D-08, D-10 and NLP.md.
"""

import json
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.nlp.slm_parser import ModelUnavailableError, SLMParser
from app.validation.schema import RequestDraft


def test_slm_parser_prompt_loading():
    parser = SLMParser()
    assert parser.parser_type == "slm"
    assert len(parser._system_prompt) > 20
    assert len(parser._few_shot_messages) >= 2
    assert "properties" in parser._schema


def test_slm_parser_interpret_raw_mocked_success():
    parser = SLMParser()
    mock_client = MagicMock(spec=httpx.Client)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {
            "content": '{"intent": "verify_record", "record_id": "CERT-101", "check_revocation": true, "clarification_needed": false}'
        }
    }
    mock_client.post.return_value = mock_response

    raw_output = parser.interpret_raw("Verify CERT-101", client=mock_client)
    assert "CERT-101" in raw_output

    # Verify options sent to Ollama
    call_args = mock_client.post.call_args
    assert call_args is not None
    payload = call_args.kwargs.get("json", {})
    assert payload["model"] == "qwen2.5:3b-instruct"
    assert payload["options"]["temperature"] == 0
    assert payload["options"]["seed"] == 42
    assert payload["options"]["num_ctx"] == 2048


def test_slm_parser_parse_success():
    parser = SLMParser()
    expected_json = (
        '{"intent": "check_status", "record_id": "CERT-202", "check_revocation": true, "clarification_needed": false}'
    )
    with patch.object(parser, "interpret_raw", return_value=expected_json):
        draft = parser.parse("Check status of CERT-202")
        assert isinstance(draft, RequestDraft)
        assert draft.intent == "check_status"
        assert draft.record_id == "CERT-202"
        assert draft.check_revocation is True


def test_slm_parser_parse_malformed_json_raises():
    parser = SLMParser()
    with patch.object(parser, "interpret_raw", return_value="Invalid JSON: {intent: 'foo'}"):
        with pytest.raises(ValueError, match="SLM output failed JSON parsing"):
            parser.parse("Check something")


def test_slm_parser_model_unavailable_error():
    parser = SLMParser()
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = httpx.ConnectError("Connection refused")

    with pytest.raises(ModelUnavailableError) as exc_info:
        parser.interpret_raw("Verify CERT-101", client=mock_client)

    assert exc_info.value.code == "E_MODEL_DOWN"
    assert exc_info.value.status_code == 503


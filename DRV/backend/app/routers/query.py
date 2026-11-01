"""
Natural language query router.

POST /api/query — receives plain-English questions, parses with baseline or SLM,
runs the 5-stage validation pipeline, and executes approved read-only contract calls.
Conforms to API.md §4.2 and ARCHITECTURE §7.2.
"""

from __future__ import annotations

import time
from typing import Literal
from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.nlp.baseline import RulesParser
from app.nlp.parser_interface import BaseParser
from app.nlp.slm_parser import ModelUnavailableError, SLMParser
from app.routers.verify import get_audit_logger, get_chain_gateway
from app.services.audit import AuditLogger
from app.services.chain_gateway import ChainGateway, ChainUnavailableError
from app.services.response_composer import (
    compose_error,
    compose_response,
    generate_request_id,
)
from app.validation.pipeline import validate_draft
from app.validation.schema import RequestDraft

router = APIRouter(prefix="/api", tags=["query"])


class QueryRequest(BaseModel):
    """Payload for natural-language query request."""

    text: str = Field(..., max_length=500, description="Natural-language question")
    parser: Literal["slm", "rules"] = Field(
        default="rules",
        description="Parser interpreter to use ('slm' or 'rules')",
    )


def resolve_parser(parser_type: str, settings: Settings) -> BaseParser:
    """Factory resolving parser implementation."""
    if parser_type == "slm":
        return SLMParser(
            model_name=settings.model_name,
            endpoint=settings.model_endpoint,
            timeout_seconds=settings.model_timeout_seconds,
        )
    return RulesParser()


@router.post("/query")
async def query_records(
    body: QueryRequest,
    settings: Settings = Depends(get_settings),
    chain_gateway: ChainGateway = Depends(get_chain_gateway),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> JSONResponse:
    """
    Handle natural language inquiries.
    Never passes document contents to the interpreter.
    """
    start_time = time.perf_counter()
    request_id = generate_request_id()
    raw_text = body.text.strip()

    # 1. Select parser and parse text into untrusted draft
    parser = resolve_parser(body.parser, settings)
    raw_draft_payload: str | RequestDraft
    try:
        if isinstance(parser, SLMParser):
            raw_draft_payload = parser.interpret_raw(raw_text)
        else:
            raw_draft_payload = parser.parse(raw_text)
    except ModelUnavailableError as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        audit_logger.log_request(
            request_id=request_id,
            route="/api/query",
            http_method="POST",
            parser_type=parser.parser_type,
            http_status=e.status_code,
            latency_ms=latency_ms,
            outcome="error",
            error_code=e.code,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=compose_error(
                request_id=request_id,
                code=e.code,
                message="Language model service is unavailable or timed out.",
            ),
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        audit_logger.log_request(
            request_id=request_id,
            route="/api/query",
            http_method="POST",
            parser_type=parser.parser_type,
            http_status=500,
            latency_ms=latency_ms,
            outcome="error",
            error_code="E_INTERNAL",
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=compose_error(
                request_id=request_id,
                code="E_INTERNAL",
                message=f"Parser execution failed: {e}",
            ),
        )

    # 2. Run pure-function 5-stage validation pipeline
    decision = validate_draft(
        raw_input=raw_draft_payload,
        user_raw_text=raw_text,
        user_role="anonymous",  # Role comes from session in Phase 6
        id_pattern=settings.id_pattern,
    )

    handling_info = {
        "parser": parser.parser_type,
        "parsed": decision.draft.model_dump() if decision.draft else None,
        "stages": [s.model_dump() for s in decision.stages],
    }

    # 3. Handle validation failure
    if not decision.approved:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        outcome = "clarification" if decision.error_code == "E_AMBIGUOUS" else "rejected"

        audit_logger.log_request(
            request_id=request_id,
            route="/api/query",
            http_method="POST",
            parser_type=parser.parser_type,
            intent=decision.draft.intent if decision.draft else None,
            outcome=outcome,
            error_code=decision.error_code,
            failed_stage=decision.failed_stage,
            http_status=decision.http_status,
            latency_ms=latency_ms,
            stages=handling_info["stages"],
        )

        if decision.error_code == "E_AMBIGUOUS":
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=compose_response(
                    request_id=request_id,
                    status="clarification",
                    result={
                        "message": decision.clarification_message,
                        "missing": decision.missing_fields,
                    },
                    handling=handling_info,
                    error={"code": decision.error_code, "message": decision.error_message},
                    include_disclaimer=False,
                ),
            )

        return JSONResponse(
            status_code=decision.http_status,
            content=compose_response(
                request_id=request_id,
                status="rejected",
                result=None,
                handling=handling_info,
                error={"code": decision.error_code, "message": decision.error_message},
                include_disclaimer=False,
            ),
        )

    # 4. Execute approved read-only contract call
    approved_draft = decision.draft
    try:
        if approved_draft.intent in ("verify_record", "check_status"):
            is_rev_res = chain_gateway.is_revoked(approved_draft.record_id)
            exists = is_rev_res["exists"]
            revoked = is_rev_res["revoked"]

            if not exists:
                state = "NOT_FOUND"
                answer_text = f"Record '{approved_draft.record_id}' was not found in the registry."
            elif revoked:
                state = "REVOKED"
                answer_text = f"Record '{approved_draft.record_id}' is revoked."
            else:
                state = "REGISTERED"
                answer_text = f"Record '{approved_draft.record_id}' is active and registered."

            result_payload = {
                "intent": approved_draft.intent,
                "record_id": approved_draft.record_id,
                "state": state,
                "exists": exists,
                "revoked": revoked,
                "answer_text": answer_text,
            }

        elif approved_draft.intent == "get_metadata":
            rec = chain_gateway.verify_hash(approved_draft.record_id, "0" * 64)
            result_payload = {
                "intent": approved_draft.intent,
                "record_id": approved_draft.record_id,
                "exists": rec["state"] != "NOT_FOUND",
                "doc_type": rec["doc_type"],
                "registered_at": rec["registered_at"],
                "revoked": rec["revoked"],
                "answer_text": f"Record '{approved_draft.record_id}' metadata retrieved.",
            }

        else:
            result_payload = {
                "intent": approved_draft.intent,
                "record_id": approved_draft.record_id,
                "answer_text": "Request approved.",
            }

    except ChainUnavailableError as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        audit_logger.log_request(
            request_id=request_id,
            route="/api/query",
            http_method="POST",
            parser_type=parser.parser_type,
            intent=approved_draft.intent,
            outcome="error",
            error_code=e.code,
            http_status=e.status_code,
            latency_ms=latency_ms,
            stages=handling_info["stages"],
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=compose_error(
                request_id=request_id,
                code=e.code,
                message="The blockchain isn't reachable right now. This isn't a verification result. Please try again.",
                handling=handling_info,
            ),
        )

    # 5. Success response
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    audit_logger.log_request(
        request_id=request_id,
        route="/api/query",
        http_method="POST",
        parser_type=parser.parser_type,
        intent=approved_draft.intent,
        outcome="ok",
        http_status=200,
        latency_ms=latency_ms,
        stages=handling_info["stages"],
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=compose_response(
            request_id=request_id,
            status="ok",
            result=result_payload,
            handling=handling_info,
            include_disclaimer=True,
        ),
    )


"""
Verification router.

POST /api/verify — multipart file upload and cryptographic hash verification.
Deterministic execution: never invokes the language model.
"""

from __future__ import annotations

import time
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.services.audit import AuditLogger
from app.services.chain_gateway import ChainGateway, ChainUnavailableError
from app.services.hashing import UploadValidationError, hash_upload_stream
from app.services.response_composer import (
    compose_error,
    compose_response,
    generate_request_id,
)

router = APIRouter(prefix="/api", tags=["verification"])


def get_chain_gateway(settings: Settings = Depends(get_settings)) -> ChainGateway:
    """Dependency provider for ChainGateway."""
    return ChainGateway(rpc_url=settings.rpc_url, contract_address=settings.contract_address)


def get_audit_logger(settings: Settings = Depends(get_settings)) -> AuditLogger:
    """Dependency provider for AuditLogger."""
    return AuditLogger(db_path=settings.db_path)


@router.post("/verify")
async def verify_certificate(
    record_id: str = Form(...),
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    chain_gateway: ChainGateway = Depends(get_chain_gateway),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> JSONResponse:
    """
    Verify uploaded certificate file against the blockchain registry.

    1. Validates record_id against ID_PATTERN.
    2. Streams file raw bytes to compute SHA-256 and discards the file.
    3. Calls verifyHash and getRecord on the smart contract.
    4. Logs the transaction outcome to SQLite audit trail.
    5. Returns unified response envelope with status and disclaimer.
    """
    start_time = time.perf_counter()
    request_id = generate_request_id()

    # 1. Validate Record ID format
    clean_id = record_id.strip().upper()
    if not settings.id_regex.match(clean_id):
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        audit_logger.log_request(
            request_id=request_id,
            route="/api/verify",
            http_method="POST",
            http_status=400,
            latency_ms=latency_ms,
            outcome="rejected",
            intent="verify_record",
            error_code="E_ID_FORMAT",
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=compose_error(
                request_id=request_id,
                code="E_ID_FORMAT",
                message=f"Invalid record ID '{record_id}'. Expected format like 'CERT-104'.",
                status="rejected",
            ),
        )

    # 2. Hash uploaded file bytes
    try:
        computed_hash = hash_upload_stream(
            stream=file.file,
            max_bytes=settings.max_upload_bytes,
        )
    except UploadValidationError as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        audit_logger.log_request(
            request_id=request_id,
            route="/api/verify",
            http_method="POST",
            http_status=e.status_code,
            latency_ms=latency_ms,
            outcome="rejected",
            intent="verify_record",
            error_code=e.code,
        )
        return JSONResponse(
            status_code=e.status_code,
            content=compose_error(
                request_id=request_id,
                code=e.code,
                message=e.message,
                status="rejected",
            ),
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        audit_logger.log_request(
            request_id=request_id,
            route="/api/verify",
            http_method="POST",
            http_status=500,
            latency_ms=latency_ms,
            outcome="error",
            intent="verify_record",
            error_code="E_INTERNAL",
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=compose_error(
                request_id=request_id,
                code="E_INTERNAL",
                message="An unexpected error occurred while processing the file.",
            ),
        )

    # 3. Query Blockchain
    try:
        verification_result = chain_gateway.verify_hash(clean_id, computed_hash)
    except ChainUnavailableError as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        audit_logger.log_request(
            request_id=request_id,
            route="/api/verify",
            http_method="POST",
            http_status=e.status_code,
            latency_ms=latency_ms,
            outcome="error",
            intent="verify_record",
            error_code=e.code,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=compose_error(
                request_id=request_id,
                code=e.code,
                message="The blockchain isn't reachable right now. This isn't a verification result. Please try again.",
            ),
        )

    # 4. Successful Verification Answer (MATCH, MISMATCH, NOT_FOUND, or REVOKED are all HTTP 200)
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    audit_logger.log_request(
        request_id=request_id,
        route="/api/verify",
        http_method="POST",
        http_status=200,
        latency_ms=latency_ms,
        outcome="ok",
        intent="verify_record",
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=compose_response(
            request_id=request_id,
            status="ok",
            result=verification_result,
            include_disclaimer=True,
        ),
    )


"""
Admin Router.

Handles admin authentication, two-step confirmations, on-chain record registrations,
and revocations conforming to DECISIONS D-11, D-12, D-13, D-14, D-15 and API.md §4.4–§4.8.
"""

from __future__ import annotations

import datetime
import sqlite3
import time
from typing import Any, Literal
from fastapi import APIRouter, Cookie, Depends, File, Form, Header, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import Settings
from app.routers.verify import get_audit_logger, get_chain_gateway, get_settings
from app.services.admin_auth import AdminAuthService
from app.services.audit import AuditLogger
from app.services.chain_gateway import (
    ChainGateway,
    ChainUnavailableError,
    DuplicateRecordError,
    RecordNotFoundError,
    TransactionFailedError,
)
from app.services.hashing import UploadValidationError, hash_upload_stream
from app.services.response_composer import compose_error, compose_response, generate_request_id

router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_auth_service(settings: Settings = Depends(get_settings)) -> AdminAuthService:
    """Dependency provider for AdminAuthService."""
    return AdminAuthService(
        db_path=settings.db_path,
        credentials_hash=settings.admin_credentials_hash,
    )


def require_admin(
    request: Request,
    drv_session: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
    auth_service: AdminAuthService = Depends(get_auth_service),
) -> str:
    """Dependency ensuring caller possesses a valid admin session."""
    token = drv_session
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()

    if not token or not auth_service.validate_session(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "E_UNAUTHORIZED", "message": "Admin session required."},
        )
    return token


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class RevokeRequest(BaseModel):
    record_id: str
    reason: int | str = 1


class ConfirmRequest(BaseModel):
    confirmation_token: str


DOC_TYPE_NAME_MAP: dict[str, int] = {
    "degree": 1,
    "marksheet": 2,
    "training": 3,
    "provisional": 3,
    "award": 4,
}

REASON_NAME_MAP: dict[str, int] = {
    "issued_in_error": 1,
    "superseded": 2,
    "fraud_suspected": 3,
    "other": 4,
}


def log_tx(
    db_path: str,
    request_id: str,
    idempotency_key: str,
    operation: str,
    record_key: str,
    tx_hash: str | None,
    tx_status: str,
    block_number: int | None = None,
    error_code: str | None = None,
    confirmation_ms: int | None = None,
):
    """Record transaction details in SQLite tx_log."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tx_log (
                request_id, idempotency_key, operation, record_key,
                tx_hash, status, error_code, block_number, submitted_at, confirmed_at, confirmation_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                idempotency_key,
                operation,
                record_key,
                tx_hash,
                tx_status,
                error_code,
                block_number,
                now_iso,
                now_iso if tx_status == "confirmed" else None,
                confirmation_ms,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()


@router.post("/login")
async def login(
    payload: AdminLoginRequest,
    response: Response,
    auth_service: AdminAuthService = Depends(get_auth_service),
) -> JSONResponse:
    """Authenticate admin and establish session."""
    request_id = generate_request_id()

    if not auth_service.verify_credentials(payload.username, payload.password):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=compose_error(
                request_id=request_id,
                code="E_UNAUTHORIZED",
                message="Invalid admin username or password.",
            ),
        )

    session_token, csrf_token, expires_at = auth_service.create_session()

    res = JSONResponse(
        status_code=status.HTTP_200_OK,
        content=compose_response(
            request_id=request_id,
            status="ok",
            result={
                "role": "admin",
                "csrf_token": csrf_token,
                "expires_at": expires_at,
            },
            include_disclaimer=False,
        ),
    )
    # Set HttpOnly session cookie
    res.set_cookie(
        key="drv_session",
        value=session_token,
        httponly=True,
        samesite="lax",
        max_age=3600,
    )
    return res


@router.post("/logout")
async def logout(
    response: Response,
    drv_session: str | None = Cookie(default=None),
    auth_service: AdminAuthService = Depends(get_auth_service),
) -> JSONResponse:
    """Terminate admin session."""
    request_id = generate_request_id()
    if drv_session:
        auth_service.revoke_session(drv_session)

    res = JSONResponse(
        status_code=status.HTTP_200_OK,
        content=compose_response(
            request_id=request_id,
            status="ok",
            result={"message": "Logged out successfully."},
            include_disclaimer=False,
        ),
    )
    res.delete_cookie(key="drv_session")
    return res


@router.get("/session")
async def get_session(
    drv_session: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
    auth_service: AdminAuthService = Depends(get_auth_service),
) -> JSONResponse:
    """Inspect current session status."""
    request_id = generate_request_id()
    token = drv_session
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()

    is_valid = auth_service.validate_session(token)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=compose_response(
            request_id=request_id,
            status="ok",
            result={
                "authenticated": is_valid,
                "role": "admin" if is_valid else "anonymous",
            },
            include_disclaimer=False,
        ),
    )


@router.post("/register")
async def register_record(
    record_id: str = Form(...),
    doc_type: str = Form("degree"),
    file: UploadFile | None = File(default=None),
    sha256: str | None = Form(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _token: str = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    chain_gateway: ChainGateway = Depends(get_chain_gateway),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> JSONResponse:
    """Register certificate fingerprint on-chain."""
    start_time = time.perf_counter()
    request_id = generate_request_id()
    clean_id = record_id.strip().upper()
    idem_key = idempotency_key or f"idem_{request_id}"

    # 1. Validate ID Format
    if not settings.id_regex.match(clean_id):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=compose_error(
                request_id=request_id,
                code="E_ID_FORMAT",
                message=f"Record ID '{record_id}' does not match pattern {settings.id_pattern}",
            ),
        )

    # 2. Resolve Hash
    file_hash_hex = ""
    if file:
        try:
            file_hash_hex = await hash_upload_stream(file, max_upload_bytes=settings.max_upload_bytes)
        except UploadValidationError as e:
            return JSONResponse(
                status_code=e.status_code,
                content=compose_error(request_id=request_id, code=e.code, message=e.message),
            )
    elif sha256:
        clean_sha = sha256.strip().lower()
        if len(clean_sha) != 64:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=compose_error(request_id=request_id, code="E_SCHEMA", message="SHA-256 must be exactly 64 hex characters."),
            )
        file_hash_hex = clean_sha
    else:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=compose_error(request_id=request_id, code="E_SCHEMA", message="Either 'file' or 'sha256' is required."),
        )

    # 3. Resolve doc_type
    doc_type_code = DOC_TYPE_NAME_MAP.get(str(doc_type).lower(), 1)
    if str(doc_type).isdigit():
        doc_type_code = int(doc_type)

    # 4. Check Idempotency from tx_log
    conn = sqlite3.connect(settings.db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT tx_hash, status, block_number FROM tx_log WHERE idempotency_key = ?", (idem_key,))
        existing = cursor.fetchone()
        if existing and existing[1] == "confirmed":
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=compose_response(
                    request_id=request_id,
                    status="ok",
                    result={
                        "operation": "register",
                        "record_id": clean_id,
                        "registered_hash": file_hash_hex,
                        "tx_hash": existing[0],
                        "tx_status": existing[1],
                        "block_number": existing[2],
                        "idempotent": True,
                    },
                    include_disclaimer=False,
                ),
            )
    finally:
        conn.close()

    # 5. Execute On-Chain Write
    try:
        tx_res = chain_gateway.register_record(
            record_id=clean_id,
            file_hash_hex=file_hash_hex,
            doc_type=doc_type_code,
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        log_tx(
            db_path=settings.db_path,
            request_id=request_id,
            idempotency_key=idem_key,
            operation="register",
            record_key=clean_id,
            tx_hash=tx_res["tx_hash"],
            tx_status="confirmed",
            block_number=tx_res["block_number"],
            confirmation_ms=latency_ms,
        )

        audit_logger.log_request(
            request_id=request_id,
            route="/api/admin/register",
            http_method="POST",
            actor_role="admin",
            outcome="ok",
            intent="register_record",
            http_status=200,
            latency_ms=latency_ms,
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=compose_response(
                request_id=request_id,
                status="ok",
                result={
                    "operation": "register",
                    "record_id": clean_id,
                    "registered_hash": file_hash_hex,
                    "tx_hash": tx_res["tx_hash"],
                    "tx_status": "confirmed",
                    "block_number": tx_res["block_number"],
                    "confirmation_ms": latency_ms,
                },
                include_disclaimer=False,
            ),
        )

    except DuplicateRecordError as e:
        return JSONResponse(
            status_code=e.status_code,
            content=compose_error(request_id=request_id, code=e.code, message=str(e)),
        )
    except ChainUnavailableError as e:
        return JSONResponse(
            status_code=e.status_code,
            content=compose_error(request_id=request_id, code=e.code, message=str(e)),
        )


@router.post("/revoke")
async def revoke_record(
    payload: RevokeRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _token: str = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    chain_gateway: ChainGateway = Depends(get_chain_gateway),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> JSONResponse:
    """Revoke an existing certificate on-chain."""
    start_time = time.perf_counter()
    request_id = generate_request_id()
    clean_id = payload.record_id.strip().upper()
    idem_key = idempotency_key or f"idem_{request_id}"

    if not settings.id_regex.match(clean_id):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=compose_error(
                request_id=request_id,
                code="E_ID_FORMAT",
                message=f"Record ID '{payload.record_id}' does not match pattern {settings.id_pattern}",
            ),
        )

    reason_code = REASON_NAME_MAP.get(str(payload.reason).lower(), 1)
    if str(payload.reason).isdigit():
        reason_code = int(payload.reason)

    try:
        tx_res = chain_gateway.revoke_record(record_id=clean_id, reason_code=reason_code)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        log_tx(
            db_path=settings.db_path,
            request_id=request_id,
            idempotency_key=idem_key,
            operation="revoke",
            record_key=clean_id,
            tx_hash=tx_res.get("tx_hash"),
            tx_status="confirmed",
            block_number=tx_res.get("block_number"),
            confirmation_ms=latency_ms,
        )

        audit_logger.log_request(
            request_id=request_id,
            route="/api/admin/revoke",
            http_method="POST",
            actor_role="admin",
            outcome="ok",
            intent="revoke_record",
            http_status=200,
            latency_ms=latency_ms,
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=compose_response(
                request_id=request_id,
                status="ok",
                result={
                    "operation": "revoke",
                    "record_id": clean_id,
                    "tx_hash": tx_res.get("tx_hash"),
                    "tx_status": "confirmed",
                    "block_number": tx_res.get("block_number"),
                    "confirmation_ms": latency_ms,
                },
                include_disclaimer=False,
            ),
        )

    except RecordNotFoundError as e:
        return JSONResponse(
            status_code=e.status_code,
            content=compose_error(request_id=request_id, code=e.code, message=str(e)),
        )
    except ChainUnavailableError as e:
        return JSONResponse(
            status_code=e.status_code,
            content=compose_error(request_id=request_id, code=e.code, message=str(e)),
        )


@router.post("/confirm")
async def confirm_action(
    payload: ConfirmRequest,
    _token: str = Depends(require_admin),
    auth_service: AdminAuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
    chain_gateway: ChainGateway = Depends(get_chain_gateway),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> JSONResponse:
    """
    Two-step confirmation endpoint (DECISIONS D-13 & API.md §4.7).
    Executes a previously proposed privileged action (e.g. natural-language revocation).
    """
    request_id = generate_request_id()
    action_data = auth_service.pop_confirmation_token(payload.confirmation_token)

    if not action_data:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=compose_error(
                request_id=request_id,
                code="E_SCHEMA",
                message="Confirmation token is invalid or has expired.",
            ),
        )

    if action_data["action"] == "revoke":
        clean_id = action_data["record_id"]
        reason_code = action_data.get("reason_code", 1)
        try:
            tx_res = chain_gateway.revoke_record(record_id=clean_id, reason_code=reason_code)
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=compose_response(
                    request_id=request_id,
                    status="ok",
                    result={
                        "operation": "revoke",
                        "record_id": clean_id,
                        "tx_hash": tx_res.get("tx_hash"),
                        "tx_status": "confirmed",
                        "block_number": tx_res.get("block_number"),
                    },
                    include_disclaimer=False,
                ),
            )
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=compose_error(request_id=request_id, code="E_INTERNAL", message=str(e)),
            )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=compose_error(request_id=request_id, code="E_SCHEMA", message="Unsupported confirmation action."),
    )


@router.get("/transactions/{idempotency_key}")
async def get_transaction(
    idempotency_key: str,
    _token: str = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """Retrieve transaction outcome by idempotency key (API.md §4.8)."""
    request_id = generate_request_id()
    conn = sqlite3.connect(settings.db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT operation, record_key, tx_hash, status, block_number, submitted_at, confirmed_at, confirmation_ms
            FROM tx_log WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        )
        row = cursor.fetchone()
        if not row:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=compose_error(request_id=request_id, code="E_NOT_FOUND", message="Transaction not found."),
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=compose_response(
                request_id=request_id,
                status="ok",
                result={
                    "operation": row[0],
                    "record_id": row[1],
                    "tx_hash": row[2],
                    "status": row[3],
                    "block_number": row[4],
                    "submitted_at": row[5],
                    "confirmed_at": row[6],
                    "confirmation_ms": row[7],
                },
                include_disclaimer=False,
            ),
        )
    finally:
        conn.close()

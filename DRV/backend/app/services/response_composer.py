"""
Response composer.

Formats all API responses in the standard envelope specified in API.md §3.2.
"""

from __future__ import annotations

import secrets
from typing import Any

INTEGRITY_DISCLAIMER = (
    "A match shows the file is identical to what was registered. "
    "It doesn't prove who issued it or that its contents are true."
)


def generate_request_id() -> str:
    """Generate a unique request ID (e.g. req_01HV3Q8K2M)."""
    return f"req_{secrets.token_hex(6)}"


def compose_response(
    request_id: str,
    status: str = "ok",
    result: dict[str, Any] | None = None,
    handling: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    include_disclaimer: bool = True,
) -> dict[str, Any]:
    """Build the unified JSON response envelope."""
    return {
        "request_id": request_id,
        "status": status,
        "result": result,
        "handling": handling,
        "error": error,
        "disclaimer": INTEGRITY_DISCLAIMER if include_disclaimer else None,
    }


def compose_error(
    request_id: str,
    code: str,
    message: str,
    status: str = "error",
    handling: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an error envelope."""
    return compose_response(
        request_id=request_id,
        status=status,
        result=None,
        handling=handling,
        error={"code": code, "message": message},
        include_disclaimer=False,
    )


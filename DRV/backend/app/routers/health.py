"""
Health-check router.

GET /api/health — reports component availability.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["operations"])


@router.get("/health")
async def health() -> dict:
    """
    Basic health probe.

    In later phases this will check chain and model availability.
    For now it only confirms the backend process is running.
    """
    return {
        "status": "ok",
        "components": {
            "backend": {"up": True},
            "chain": {"up": False, "reason": "not configured yet"},
            "model": {"up": False, "reason": "not configured yet"},
        },
    }


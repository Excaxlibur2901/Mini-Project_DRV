"""
Health-check router.

GET /api/health — reports live component availability (API.md §4.10).
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.routers.verify import get_chain_gateway
from app.services.chain_gateway import ChainGateway

router = APIRouter(prefix="/api", tags=["operations"])


@router.get("/health")
async def health(
    gateway: ChainGateway = Depends(get_chain_gateway),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Live component health probe for:
    - Backend API service
    - Local EVM blockchain node (Web3)
    - Local SLM service (Ollama)
    """
    # 1. Check Blockchain node
    chain_up = False
    chain_err = None
    try:
        if gateway and gateway.get_web3().is_connected():
            chain_up = True
        else:
            chain_err = "RPC node unreachable"
    except Exception as ex:
        chain_err = str(ex)

    # 2. Check Model service (Ollama)
    model_up = False
    model_err = None
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.model_endpoint}/api/tags")
            if resp.status_code == 200:
                model_up = True
            else:
                model_err = f"Ollama HTTP {resp.status_code}"
    except Exception as ex:
        model_err = "Model endpoint unreachable"

    overall_ok = chain_up and model_up

    return {
        "status": "ok" if overall_ok else "degraded",
        "components": {
            "backend": {"up": True},
            "chain": {"up": chain_up, **({"reason": chain_err} if chain_err else {})},
            "model": {"up": model_up, **({"reason": model_err} if model_err else {})},
        },
    }

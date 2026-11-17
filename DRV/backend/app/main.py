"""
FastAPI application entry point for Decentralized Record Verifier.
"""

from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.routers import admin, health, query, results, verify


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Decentralized Record Verifier API",
        version="0.1.0",
        description="Backend API for cryptographic certificate verification & natural language queries.",
    )

    # ── Rate Limiter ────────────────────────────────────────────────────────
    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Security Headers Middleware ─────────────────────────────────────────
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

    # ── CORS ────────────────────────────────────────────────────────────────
    # Restrict to localhost origins only (local Hardhat deployment)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Routers ─────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(verify.router)
    app.include_router(query.router)
    app.include_router(admin.router)
    app.include_router(results.router)

    # ── Static: sample certificates (must come BEFORE "/" mount) ────────────
    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    if data_dir.exists():
        app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")

    # ── Static: frontend SPA ────────────────────────────────────────────────
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "app"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


app = create_app()

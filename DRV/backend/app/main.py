"""
FastAPI application entry point for Decentralized Record Verifier.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Decentralized Record Verifier API",
        version="0.1.0",
        description="Backend API for cryptographic certificate verification & natural language queries.",
    )

    # Cross-Origin Resource Sharing (CORS) for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router)

    return app


app = create_app()


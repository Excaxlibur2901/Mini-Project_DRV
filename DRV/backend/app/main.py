"""
FastAPI application entry point for Decentralized Record Verifier.
"""

from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import admin, health, query, results, verify


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
    app.include_router(verify.router)
    app.include_router(query.router)
    app.include_router(admin.router)
    app.include_router(results.router)

    # Mount static frontend
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "app"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


app = create_app()


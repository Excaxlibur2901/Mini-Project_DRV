"""
Backend configuration.

Reads settings from environment variables (or .env via a loader).
Never import secrets at module level in production; use dependency injection.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Blockchain ---
    rpc_url: str = Field(default="http://127.0.0.1:8545", alias="RPC_URL")
    contract_address: str = Field(default="", alias="CONTRACT_ADDRESS")
    signer_private_key: str = Field(
        default="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        alias="SIGNER_PRIVATE_KEY",
    )

    # --- Model ---
    model_name: str = Field(default="qwen2.5:3b-instruct", alias="MODEL_NAME")
    model_endpoint: str = Field(
        default="http://localhost:11434", alias="MODEL_ENDPOINT"
    )
    model_timeout_seconds: float = Field(default=120.0, alias="MODEL_TIMEOUT_SECONDS")
    nlp_retry_on_invalid: bool = Field(default=False, alias="NLP_RETRY_ON_INVALID")

    # --- Validation ---
    id_pattern: str = Field(
        default=r"^[A-Z]{2,6}-[0-9]{1,8}$", alias="ID_PATTERN"
    )

    # --- Uploads ---
    max_upload_mb: int = Field(default=5, alias="MAX_UPLOAD_MB")

    # --- Admin ---
    # Default is SHA-256 of "admin:admin123"
    admin_credentials_hash: str = Field(
        default="bf6b5bdb74c79ece9fc0ad0ac9fb0359f9555d4f35a83b2e6ec69ae99e09603d",
        alias="ADMIN_CREDENTIALS_HASH",
    )

    # --- Database ---
    db_path: str = Field(default="data/verifier.db", alias="DB_PATH")

    # --- Operations ---
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def id_regex(self) -> re.Pattern:
        """Compiled record-ID pattern from DECISIONS D-15."""
        return re.compile(self.id_pattern)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    """Dependency-injectable settings factory."""
    return Settings()


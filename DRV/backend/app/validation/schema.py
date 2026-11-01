"""
Validation schemas and data models for query request drafts and validation pipeline.
Conforms to API.md §5.1, ARCHITECTURE §8, and NLP.md §2.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

# Valid intents allowlist (PRD §8.1 / API.md §5.1 / NLP.md §3)
AllowedIntent = Literal[
    "verify_record",
    "check_status",
    "get_metadata",
    "register_record",
    "revoke_record",
    "unknown",
]

PRIVILEGED_INTENTS: set[str] = {"register_record", "revoke_record"}
PUBLIC_INTENTS: set[str] = {"verify_record", "check_status", "get_metadata"}


class RequestDraft(BaseModel):
    """
    Structured query draft output by an NLP interpreter (SLM or rules baseline).
    Strictly 4 required fields. No additional properties allowed.
    """

    model_config = ConfigDict(extra="forbid")

    intent: AllowedIntent = Field(
        ...,
        description="One of the allowed intents from the PRD/API allowlist.",
    )
    record_id: str | None = Field(
        default=None,
        description="Record identifier extracted from user text (e.g. CERT-104), or None.",
    )
    check_revocation: bool = Field(
        default=False,
        description="True if query explicitly asks about revocation, cancellation, or validity.",
    )
    clarification_needed: bool = Field(
        default=False,
        description="True if the request is ambiguous (missing ID, multiple IDs, or unclear action).",
    )


class StageOutcome(BaseModel):
    """Result of an individual validation stage (API.md §3.3)."""

    order: int
    name: Literal["schema", "intent_allowlist", "record_id", "role", "clarity"]
    passed: bool
    reason: str | None = None


class ValidationDecision(BaseModel):
    """
    Outcome of the pure-function 5-stage validation pipeline.
    """

    approved: bool
    draft: RequestDraft | None = None
    stages: list[StageOutcome]
    failed_stage: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    http_status: int = 200
    clarification_message: str | None = None
    missing_fields: list[str] = Field(default_factory=list)


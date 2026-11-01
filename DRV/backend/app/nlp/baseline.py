"""
Rules-based NLP baseline parser.

Deterministic non-AI baseline implemented using regex and keyword heuristics.
Strictly implements the algorithm defined in NLP.md §9.
"""

from __future__ import annotations

import re
from app.nlp.parser_interface import BaseParser
from app.validation.schema import AllowedIntent, RequestDraft

# ID pattern for extraction: 2 to 6 letters, hyphen, 1 to 8 digits
ID_REGEX = re.compile(r"\b([A-Za-z]{2,6}-\d{1,8})\b", re.IGNORECASE)

OVERRIDE_KEYWORDS = ("ignore", "disregard", "system prompt", "instructions")
REVOCATION_FLAG_KEYWORDS = ("revoke", "revoked", "revocation", "cancelled", "still valid", "valid")


class RulesParser(BaseParser):
    """Rules-based interpreter producing structured RequestDraft."""

    @property
    def parser_type(self) -> str:
        return "rules"

    def parse(self, text: str) -> RequestDraft:
        clean_text = text.strip()
        lower_text = clean_text.lower()

        # 1. Check for prompt injection / instruction override attempts
        for kw in OVERRIDE_KEYWORDS:
            if kw in lower_text:
                return RequestDraft(
                    intent="unknown",
                    record_id=None,
                    check_revocation=False,
                    clarification_needed=False,
                )

        # 2. Extract Record IDs
        id_matches = ID_REGEX.findall(clean_text)
        record_id: str | None = None
        clarification_needed = False

        if len(id_matches) == 1:
            record_id = id_matches[0].upper()
        elif len(id_matches) > 1:
            # Ambiguous: two or more IDs found in query
            record_id = None
            clarification_needed = True

        # 3. Intent classification by keyword priority (NLP.md §9)
        intent: AllowedIntent = "unknown"

        # Check imperative action words for revocation vs passive inquiry
        # "revoke", "cancel", "withdraw" as actions (e.g. "Revoke CERT-104")
        if re.search(r"\b(cancel|withdraw)\b", lower_text) or re.search(r"\brevoke\b", lower_text):
            # If phrased as inquiry: "is ... revoked" or "has it been revoked"
            if re.search(r"\b(is|has|was|check|status|verify)\b.*\brevoke", lower_text):
                intent = "verify_record"
            else:
                intent = "revoke_record"
        # Imperative registration actions ("register", "add", "issue")
        # Note: "registered" is a state query handled under verify_record below
        elif re.search(r"\b(register|add|issue)\b", lower_text) and not re.search(r"\bregistered\b", lower_text):
            intent = "register_record"
        elif any(w in lower_text for w in ("details", "info", "show", "metadata")):
            intent = "get_metadata"
        elif "status" in lower_text and not any(w in lower_text for w in ("verify", "check", "valid")):
            intent = "check_status"
        elif any(
            w in lower_text
            for w in ("verify", "check", "valid", "registered", "exist", "genuine", "revoked", "status")
        ):
            intent = "verify_record"
        else:
            intent = "unknown"

        # 4. Revocation flag
        check_revocation = any(w in lower_text for w in REVOCATION_FLAG_KEYWORDS)

        # 5. Clarification check
        if intent != "unknown" and record_id is None:
            clarification_needed = True

        return RequestDraft(
            intent=intent,
            record_id=record_id,
            check_revocation=check_revocation,
            clarification_needed=clarification_needed,
        )

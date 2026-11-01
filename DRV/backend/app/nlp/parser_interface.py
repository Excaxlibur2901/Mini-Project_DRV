"""
Parser interface.

Abstract base contract implemented by both the rules-based baseline
and the SLM adapter to ensure fair empirical comparison.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from app.validation.schema import RequestDraft


class BaseParser(ABC):
    """Abstract parser interface for query interpretation."""

    @property
    @abstractmethod
    def parser_type(self) -> str:
        """Identifier for parser type: 'rules' or 'slm'."""
        pass

    @abstractmethod
    def parse(self, text: str) -> RequestDraft:
        """
        Convert user natural language query text into a structured RequestDraft.

        Raises or returns an unvalidated draft for the validator pipeline to evaluate.
        """
        pass


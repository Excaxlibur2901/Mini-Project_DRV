"""
SLM Parser Adapter.

Connects to locally hosted Small Language Model (Qwen2.5-3B-Instruct) via Ollama HTTP API.
Enforces deterministic decoding (temperature 0, fixed seed, fixed context length).
Conforms to NLP.md §5 and DECISIONS D-07, D-08, D-10.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import httpx

from app.nlp.parser_interface import BaseParser
from app.validation.schema import RequestDraft


class ModelUnavailableError(Exception):
    """Raised when Ollama is unreachable, offline, or times out."""

    def __init__(self, message: str = "Language model service is unavailable or timed out."):
        super().__init__(message)
        self.code = "E_MODEL_DOWN"
        self.status_code = 503


class SLMParser(BaseParser):
    """Adapter for interacting with local SLM via Ollama /api/chat."""

    def __init__(
        self,
        model_name: str = "qwen2.5:3b-instruct",
        endpoint: str = "http://localhost:11434",
        timeout_seconds: float = 120.0,
        constrained: bool = False,
    ):
        self.model_name = model_name
        self.endpoint = endpoint.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.constrained = constrained
        self._system_prompt = self._load_system_prompt()
        self._few_shot_messages = self._load_few_shot_messages()
        self._schema = self._load_schema()

    @property
    def parser_type(self) -> str:
        return "slm"

    def _resolve_asset_path(self, relative_path: str) -> Path | None:
        """Search for assets relative to current directory or backend package."""
        candidates = [
            Path(__file__).parent / relative_path,
            Path("backend/app/nlp") / relative_path,
            Path("DRV/backend/app/nlp") / relative_path,
            Path("app/nlp") / relative_path,
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    def _load_system_prompt(self) -> str:
        p = self._resolve_asset_path("prompts/system_v1.txt")
        if p and p.exists():
            return p.read_text(encoding="utf-8").strip()
        return "You convert one user message into one JSON object for a certificate verification tool."

    def _load_few_shot_messages(self) -> list[dict[str, str]]:
        p = self._resolve_asset_path("prompts/fewshot_v1.json")
        if p and p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def _load_schema(self) -> dict[str, Any]:
        p = self._resolve_asset_path("schema.json")
        if p and p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def interpret_raw(self, user_text: str, client: httpx.Client | None = None) -> str:
        """
        Call Ollama /api/chat and return the raw output string.
        Does not parse JSON so validation failures are preserved for the validator pipeline.
        """
        payload: dict[str, Any] = {
            "model": self.model_name,
            "stream": False,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                *self._few_shot_messages,
                {"role": "user", "content": user_text},
            ],
            "options": {
                "temperature": 0,
                "seed": 42,
                "num_ctx": 2048,
            },
        }

        if self.constrained and self._schema:
            payload["format"] = self._schema

        url = f"{self.endpoint}/api/chat"

        try:
            if client:
                res = client.post(url, json=payload, timeout=self.timeout_seconds)
            else:
                with httpx.Client(timeout=self.timeout_seconds) as local_client:
                    res = local_client.post(url, json=payload)

            if res.status_code != 200:
                raise ModelUnavailableError(
                    f"Ollama returned HTTP {res.status_code}: {res.text}"
                )

            data = res.json()
            return data.get("message", {}).get("content", "").strip()

        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError) as e:
            raise ModelUnavailableError(f"Failed to communicate with Ollama at {self.endpoint}: {e}") from e

    def parse(self, text: str) -> RequestDraft:
        """
        Interpret query text and attempt to load as RequestDraft.
        If output is malformed JSON, raises ValueError or returns fallback draft.
        """
        raw_json_str = self.interpret_raw(text)
        try:
            return RequestDraft.model_validate_json(raw_json_str)
        except Exception as e:
            # Return raw string wrapped in an invalid structure or raise so router/pipeline catches it
            raise ValueError(f"SLM output failed JSON parsing: {raw_json_str}") from e


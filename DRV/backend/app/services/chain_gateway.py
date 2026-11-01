"""
Blockchain gateway service.

Wraps Web3.py calls to the RecordRegistry contract.
Enforces that only predefined read-only functions (verifyHash, getRecord, isRevoked)
and admin transactions (registerRecord, revokeRecord) can be executed.
Distinguishes chain outages (E_CHAIN_DOWN) from record states (NOT_FOUND).
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any

from web3 import Web3
from web3.exceptions import Web3Exception


class ChainUnavailableError(Exception):
    """Raised when the blockchain node is unreachable or encounters an RPC failure."""

    def __init__(self, message: str = "Blockchain node is currently unreachable."):
        super().__init__(message)
        self.code = "E_CHAIN_DOWN"
        self.status_code = 503


# Mapping for revocation reason codes (DATABASE.md §3.4)
REASON_CODE_MAP: dict[int, str] = {
    1: "issued_in_error",
    2: "superseded",
    3: "fraud_suspected",
    4: "other",
}

# Mapping for minimal metadata docType (DATABASE.md §3.1)
DOC_TYPE_MAP: dict[int, str] = {
    1: "degree",
    2: "marksheet",
    3: "training",
}


def format_iso_timestamp(ts: int) -> str | None:
    """Convert unix epoch timestamp to ISO-8601 UTC string."""
    if ts == 0:
        return None
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ChainGateway:
    """Gateway for reading and writing to RecordRegistry smart contract."""

    def __init__(
        self,
        rpc_url: str = "http://127.0.0.1:8545",
        contract_address: str = "",
        abi: list[dict[str, Any]] | None = None,
    ):
        self.rpc_url = rpc_url
        self.contract_address = contract_address
        self._abi = abi or self._load_default_abi()
        self._web3: Web3 | None = None
        self._contract = None

    def _load_default_abi(self) -> list[dict[str, Any]]:
        """Load RecordRegistry ABI from compilation artifacts if available."""
        possible_paths = [
            Path("artifacts/contracts/RecordRegistry.sol/RecordRegistry.json"),
            Path("../artifacts/contracts/RecordRegistry.sol/RecordRegistry.json"),
            Path("DRV/artifacts/contracts/RecordRegistry.sol/RecordRegistry.json"),
        ]
        for p in possible_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        return data.get("abi", [])
                except Exception:
                    pass
        return []

    def get_web3(self) -> Web3:
        """Get or initialize Web3 connection with health check."""
        if self._web3 is None:
            self._web3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 5}))

        try:
            if not self._web3.is_connected():
                raise ChainUnavailableError(
                    f"Unable to connect to blockchain node at {self.rpc_url}"
                )
        except Exception as e:
            if not isinstance(e, ChainUnavailableError):
                raise ChainUnavailableError(f"Blockchain RPC error: {str(e)}") from e
            raise

        return self._web3

    def get_contract(self):
        """Get contract instance, resolving address from deployments if not explicitly provided."""
        if self._contract is not None:
            return self._contract

        w3 = self.get_web3()

        address = self.contract_address
        if not address:
            # Check deployments/localhost.json
            dep_paths = [
                Path("deployments/localhost.json"),
                Path("../deployments/localhost.json"),
                Path("DRV/deployments/localhost.json"),
            ]
            for dp in dep_paths:
                if dp.exists():
                    try:
                        with open(dp, "r", encoding="utf-8") as f:
                            info = json.load(f)
                            address = info.get("contractAddress", "")
                            if address:
                                break
                    except Exception:
                        pass

        if not address:
            raise ChainUnavailableError("Contract address is not configured.")

        try:
            checksum_addr = Web3.to_checksum_address(address)
            self._contract = w3.eth.contract(address=checksum_addr, abi=self._abi)
            return self._contract
        except Exception as e:
            raise ChainUnavailableError(f"Failed to load contract at {address}: {e}") from e

    def verify_hash(self, record_id: str, file_hash_hex: str) -> dict[str, Any]:
        """
        Call verifyHash(recordId, fileHash) and getRecord(recordId).

        Returns structured verification dictionary:
        state: MATCH | MISMATCH | NOT_FOUND | REVOKED
        """
        # Ensure 32-byte hash format
        clean_hex = file_hash_hex.lower().replace("0x", "")
        if len(clean_hex) != 64:
            raise ValueError("Invalid hash length: expected 64 hex characters")
        hash_bytes = bytes.fromhex(clean_hex)

        contract = self.get_contract()

        try:
            # Call view verifyHash(recordId, fileHash)
            exists, hash_match, revoked = contract.functions.verifyHash(
                record_id, hash_bytes
            ).call()

            if not exists:
                return {
                    "state": "NOT_FOUND",
                    "record_id": record_id,
                    "computed_hash": clean_hex,
                    "registered_hash": None,
                    "hash_match": False,
                    "revoked": False,
                    "doc_type": None,
                    "registered_at": None,
                    "revoked_at": None,
                    "reason": None,
                }

            # Fetch record metadata for complete answer
            record_tuple = contract.functions.getRecord(record_id).call()
            (
                registered_hash_bytes,
                issuer,
                registered_at_ts,
                doc_type_code,
                _,
                is_rev,
                reason_code,
                revoked_at_ts,
            ) = record_tuple

            registered_hash_hex = registered_hash_bytes.hex().lower()
            doc_type_str = DOC_TYPE_MAP.get(doc_type_code, "other")
            reason_str = REASON_CODE_MAP.get(reason_code) if is_rev else None

            # Determine high-level verification state
            if is_rev:
                state = "REVOKED"
            elif hash_match:
                state = "MATCH"
            else:
                state = "MISMATCH"

            return {
                "state": state,
                "record_id": record_id,
                "computed_hash": clean_hex,
                "registered_hash": registered_hash_hex,
                "hash_match": hash_match,
                "revoked": is_rev,
                "doc_type": doc_type_str,
                "registered_at": format_iso_timestamp(registered_at_ts),
                "revoked_at": format_iso_timestamp(revoked_at_ts),
                "reason": reason_str,
            }

        except (Web3Exception, OSError) as e:
            raise ChainUnavailableError(f"RPC communication failed during verifyHash: {e}") from e

    def is_revoked(self, record_id: str) -> dict[str, Any]:
        """Call isRevoked(recordId) view."""
        contract = self.get_contract()
        try:
            exists, revoked = contract.functions.isRevoked(record_id).call()
            return {"exists": exists, "revoked": revoked}
        except (Web3Exception, OSError) as e:
            raise ChainUnavailableError(f"RPC failure in isRevoked: {e}") from e


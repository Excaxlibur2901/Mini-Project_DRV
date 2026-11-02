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


class DuplicateRecordError(Exception):
    """Raised when record ID is already registered on chain."""

    def __init__(self, message: str = "Record ID already registered on the blockchain."):
        super().__init__(message)
        self.code = "E_DUPLICATE"
        self.status_code = 409


class RecordNotFoundError(Exception):
    """Raised when record ID is not found on chain."""

    def __init__(self, message: str = "Record ID was not found on the blockchain."):
        super().__init__(message)
        self.code = "E_NOT_FOUND"
        self.status_code = 404


class TransactionFailedError(Exception):
    """Raised when on-chain transaction execution fails or reverts."""

    def __init__(self, message: str = "Transaction execution failed or reverted."):
        super().__init__(message)
        self.code = "E_TX_FAILED"
        self.status_code = 502


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
        signer_private_key: str = "",
        abi: list[dict[str, Any]] | None = None,
    ):
        self.rpc_url = rpc_url
        self.contract_address = contract_address
        self.signer_private_key = signer_private_key
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

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        """Call contract to get full record details or None if not found."""
        res = self.verify_hash(record_id, "0" * 64)
        if res.get("state") == "NOT_FOUND":
            return None
        return {
            "record_id": record_id,
            "file_hash": res.get("registered_hash"),
            "revoked": res.get("revoked", False),
            "doc_type": res.get("doc_type"),
            "registered_at": res.get("registered_at"),
            "revoked_at": res.get("revoked_at"),
            "reason": res.get("reason"),
        }

    def register_record(
        self,
        record_id: str,
        file_hash_hex: str,
        doc_type: int,
        private_key: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute registerRecord on-chain.
        Raises DuplicateRecordError (409) if already exists,
        or ChainUnavailableError (503) if RPC fails.
        """
        clean_hex = file_hash_hex.lower().replace("0x", "")
        if len(clean_hex) != 64:
            raise ValueError("Invalid hash length: expected 64 hex characters")
        hash_bytes = bytes.fromhex(clean_hex)

        w3 = self.get_web3()
        contract = self.get_contract()
        pk = private_key or self.signer_private_key
        if not pk:
            raise ChainUnavailableError("Signer private key is not configured for admin writes.")

        # Pre-check existence for clean 409
        status = self.is_revoked(record_id)
        if status["exists"]:
            raise DuplicateRecordError(f"Record ID '{record_id}' is already registered.")

        try:
            account = w3.eth.account.from_key(pk)
            nonce = w3.eth.get_transaction_count(account.address)

            tx = contract.functions.registerRecord(
                record_id, hash_bytes, doc_type
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 300000,
                "gasPrice": w3.eth.gas_price,
            })

            signed = w3.eth.account.sign_transaction(tx, private_key=pk)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)

            if receipt.status != 1:
                raise TransactionFailedError("registerRecord transaction reverted on chain.")

            return {
                "operation": "register",
                "record_id": record_id,
                "registered_hash": clean_hex,
                "tx_hash": tx_hash.hex(),
                "tx_status": "confirmed",
                "block_number": receipt.blockNumber,
            }

        except (DuplicateRecordError, TransactionFailedError):
            raise
        except Exception as e:
            raise ChainUnavailableError(f"Registration failed: {e}") from e

    def revoke_record(
        self,
        record_id: str,
        reason_code: int = 1,
        private_key: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute revokeRecord on-chain.
        Raises RecordNotFoundError (404) if record does not exist.
        Idempotent: if already revoked, returns confirmed without submitting new tx.
        """
        w3 = self.get_web3()
        contract = self.get_contract()
        pk = private_key or self.signer_private_key
        if not pk:
            raise ChainUnavailableError("Signer private key is not configured for admin writes.")

        # Check existence and current status
        status = self.is_revoked(record_id)
        if not status["exists"]:
            raise RecordNotFoundError(f"Record ID '{record_id}' does not exist on the ledger.")

        if status["revoked"]:
            # Already revoked, idempotent success
            return {
                "operation": "revoke",
                "record_id": record_id,
                "tx_hash": None,
                "tx_status": "confirmed",
                "block_number": None,
                "note": "Record was already revoked.",
            }

        try:
            account = w3.eth.account.from_key(pk)
            nonce = w3.eth.get_transaction_count(account.address)

            tx = contract.functions.revokeRecord(
                record_id, reason_code
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 200000,
                "gasPrice": w3.eth.gas_price,
            })

            signed = w3.eth.account.sign_transaction(tx, private_key=pk)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)

            if receipt.status != 1:
                raise TransactionFailedError("revokeRecord transaction reverted on chain.")

            return {
                "operation": "revoke",
                "record_id": record_id,
                "tx_hash": tx_hash.hex(),
                "tx_status": "confirmed",
                "block_number": receipt.blockNumber,
            }

        except (RecordNotFoundError, TransactionFailedError):
            raise
        except Exception as e:
            raise ChainUnavailableError(f"Revocation failed: {e}") from e


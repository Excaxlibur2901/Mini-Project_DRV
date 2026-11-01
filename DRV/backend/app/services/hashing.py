"""
Hashing service.

Streams raw uploaded bytes, computes SHA-256, validates MIME/magic bytes and size limit.
Never persists files to disk or database.
"""

from __future__ import annotations

import hashlib
from typing import BinaryIO


class UploadValidationError(Exception):
    """Raised when file validation fails (type or size)."""

    def __init__(self, message: str, code: str = "E_UPLOAD_INVALID", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


PDF_MAGIC_BYTES = b"%PDF"


def validate_magic_bytes(header: bytes) -> bool:
    """Validate that the file header matches supported document types (currently PDF)."""
    return header.startswith(PDF_MAGIC_BYTES)


def compute_sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest from raw bytes."""
    return hashlib.sha256(data).hexdigest().lower()


def hash_upload_stream(
    stream: BinaryIO,
    max_bytes: int,
    chunk_size: int = 65536,
) -> str:
    """
    Stream a file, validate magic bytes and size, and compute SHA-256 digest.

    Bytes are hashed and immediately discarded; never stored on disk.
    """
    hasher = hashlib.sha256()
    total_bytes = 0
    header_checked = False

    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break

        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise UploadValidationError(
                f"Uploaded file exceeds maximum allowed size ({max_bytes // (1024 * 1024)} MB).",
                code="E_UPLOAD_INVALID",
                status_code=413,
            )

        if not header_checked:
            if not validate_magic_bytes(chunk[:4]):
                raise UploadValidationError(
                    "Unsupported file format. Only PDF documents are accepted.",
                    code="E_UPLOAD_INVALID",
                    status_code=415,
                )
            header_checked = True

        hasher.update(chunk)

    if total_bytes == 0:
        raise UploadValidationError("Uploaded file is empty.", code="E_UPLOAD_INVALID", status_code=400)

    return hasher.hexdigest().lower()


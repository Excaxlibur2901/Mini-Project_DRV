"""
Unit tests for SHA-256 hashing service.
"""

import io
import pytest

from app.services.hashing import (
    UploadValidationError,
    compute_sha256_bytes,
    hash_upload_stream,
    validate_magic_bytes,
)


def test_compute_sha256_deterministic() -> None:
    data1 = b"Sample certificate data"
    data2 = b"Sample certificate data"
    hash1 = compute_sha256_bytes(data1)
    hash2 = compute_sha256_bytes(data2)

    assert hash1 == hash2
    assert len(hash1) == 64
    assert hash1.islower()


def test_compute_sha256_sensitivity_one_byte_change() -> None:
    data_original = b"Certificate for Alice - Grade A"
    data_tampered = b"Certificate for Alice - Grade B"

    hash_orig = compute_sha256_bytes(data_original)
    hash_tamp = compute_sha256_bytes(data_tampered)

    assert hash_orig != hash_tamp


def test_validate_magic_bytes() -> None:
    assert validate_magic_bytes(b"%PDF-1.7 standard header") is True
    assert validate_magic_bytes(b"PK\x03\x04 zip file") is False
    assert validate_magic_bytes(b"\x89PNG") is False


def test_hash_upload_stream_valid_pdf() -> None:
    pdf_content = b"%PDF-1.4 header and content of synthetic certificate"
    stream = io.BytesIO(pdf_content)

    digest = hash_upload_stream(stream, max_bytes=1024 * 1024)
    expected = compute_sha256_bytes(pdf_content)

    assert digest == expected


def test_hash_upload_stream_rejects_non_pdf() -> None:
    text_content = b"Plain text file, not a pdf"
    stream = io.BytesIO(text_content)

    with pytest.raises(UploadValidationError) as exc:
        hash_upload_stream(stream, max_bytes=1024 * 1024)

    assert exc.value.status_code == 415
    assert exc.value.code == "E_UPLOAD_INVALID"


def test_hash_upload_stream_rejects_oversized() -> None:
    large_pdf = b"%PDF" + b"x" * 200
    stream = io.BytesIO(large_pdf)

    with pytest.raises(UploadValidationError) as exc:
        hash_upload_stream(stream, max_bytes=100)  # limit 100 bytes

    assert exc.value.status_code == 413
    assert exc.value.code == "E_UPLOAD_INVALID"


def test_hash_upload_stream_rejects_empty() -> None:
    stream = io.BytesIO(b"")

    with pytest.raises(UploadValidationError) as exc:
        hash_upload_stream(stream, max_bytes=1024)

    assert exc.value.status_code == 400


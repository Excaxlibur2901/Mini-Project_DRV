"""
generate_sample_certs.py
========================
Generates real PDF certificate fixtures in DRV/data/sample_certs/.

Outputs:
  sample_cert_101.pdf  — CERT-101  (Degree Certificate, R.C. Patel)
  sample_cert_102.pdf  — CERT-102  (Official Transcript)
  sample_cert_103.pdf  — CERT-103  (Degree, to be revoked)
  sample_cert_101_tampered.pdf — identical to 101 with 1 byte flipped (MISMATCH demo)

Also prints the SHA-256 hex of each file so seed_real.js can be updated.

Usage:
  python scripts/generate_sample_certs.py
"""

from __future__ import annotations

import hashlib
import os
import struct
import sys

# ---------------------------------------------------------------------------
# fpdf2 ≥ 2.7
# ---------------------------------------------------------------------------
try:
    from fpdf import FPDF
except ImportError:
    sys.exit("ERROR: fpdf2 not installed — run: python -m pip install fpdf2")

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "..", "data", "sample_certs")
os.makedirs(OUT_DIR, exist_ok=True)

UNIVERSITY = "R.C. Patel Institute of Technology, Shirpur"
SYSTEM = "Decentralized Record Verifier (DRV) · Blockchain-Anchored"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_pdf(
    title: str,
    student_name: str,
    record_id: str,
    course: str,
    doc_type_label: str,
    year: str = "2024",
) -> FPDF:
    """Return an FPDF object with a formatted certificate page."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    # --- Border ---
    pdf.set_draw_color(10, 60, 150)
    pdf.set_line_width(1.5)
    pdf.rect(10, 10, 277, 190)
    pdf.set_line_width(0.5)
    pdf.rect(13, 13, 271, 184)

    # --- University header ---
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(10, 60, 150)
    pdf.set_y(22)
    pdf.cell(0, 10, UNIVERSITY, align="C", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, "Affiliated to North Maharashtra University, Jalgaon", align="C", ln=True)

    # --- Divider ---
    pdf.set_draw_color(10, 60, 150)
    pdf.set_line_width(0.8)
    pdf.line(30, pdf.get_y() + 3, 267, pdf.get_y() + 3)
    pdf.ln(8)

    # --- Certificate title ---
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(10, 60, 150)
    pdf.cell(0, 14, title, align="C", ln=True)

    pdf.set_font("Helvetica", "I", 12)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 7, f"({doc_type_label})", align="C", ln=True)
    pdf.ln(4)

    # --- Body ---
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 7, "This is to certify that", align="C", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, student_name, align="C", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(
        0, 7,
        f"has successfully completed the course of {course}\n"
        f"and has been awarded the degree in the year {year}.",
        align="C",
    )
    pdf.ln(6)

    # --- Record ID block ---
    pdf.set_font("Courier", "B", 11)
    pdf.set_text_color(10, 60, 150)
    pdf.cell(0, 7, f"Blockchain Record ID: {record_id}", align="C", ln=True)

    # --- Footer ---
    pdf.set_y(-28)
    pdf.set_line_width(0.4)
    pdf.set_draw_color(150, 150, 150)
    pdf.line(30, pdf.get_y(), 267, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, SYSTEM, align="C", ln=True)

    return pdf


# ---------------------------------------------------------------------------
# Certificate definitions
# ---------------------------------------------------------------------------

CERTS = [
    dict(
        filename="sample_cert_101.pdf",
        record_id="CERT-101",
        title="DEGREE CERTIFICATE",
        doc_type_label="B.E. - Computer Engineering",
        student_name="Vipul Ahirrao",
        course="Bachelor of Engineering in Computer Engineering",
        year="2024",
    ),
    dict(
        filename="sample_cert_102.pdf",
        record_id="CERT-102",
        title="OFFICIAL TRANSCRIPT",
        doc_type_label="Semester-wise Grade Report",
        student_name="Rahul Patil",
        course="Bachelor of Engineering in Electronics and Telecommunication",
        year="2023",
    ),
    dict(
        filename="sample_cert_103.pdf",
        record_id="CERT-103",
        title="DEGREE CERTIFICATE",
        doc_type_label="B.E. - Mechanical Engineering",
        student_name="Sneha Deshmukh",
        course="Bachelor of Engineering in Mechanical Engineering",
        year="2022",
    ),
]


def main() -> None:
    hashes: dict[str, str] = {}

    for cert in CERTS:
        out_path = os.path.join(OUT_DIR, cert["filename"])
        pdf = make_pdf(
            title=cert["title"],
            student_name=cert["student_name"],
            record_id=cert["record_id"],
            course=cert["course"],
            doc_type_label=cert["doc_type_label"],
            year=cert["year"],
        )
        pdf.output(out_path)
        h = sha256_file(out_path)
        hashes[cert["record_id"]] = h
        print(f"[OK] {cert['filename']:35s}  SHA-256: {h}")

    # --- Tampered variant of CERT-101 ---
    base_path = os.path.join(OUT_DIR, "sample_cert_101.pdf")
    tampered_path = os.path.join(OUT_DIR, "sample_cert_101_tampered.pdf")
    with open(base_path, "rb") as f:
        data = bytearray(f.read())

    # Flip a byte deep in the content stream (offset 512, away from PDF header)
    flip_offset = min(512, len(data) - 1)
    data[flip_offset] ^= 0xFF
    with open(tampered_path, "wb") as f:
        f.write(data)

    h_tampered = sha256_file(tampered_path)
    print(f"[OK] {'sample_cert_101_tampered.pdf':35s}  SHA-256: {h_tampered}")
    print()
    print("=" * 70)
    print("Paste these hashes into scripts/seed_real.js:")
    print("=" * 70)
    for rid, h in hashes.items():
        print(f'  {rid}: "0x{h}"')
    print()
    print("Files written to:", os.path.abspath(OUT_DIR))


if __name__ == "__main__":
    main()

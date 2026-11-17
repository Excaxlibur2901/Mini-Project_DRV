"""
E2E test script for real certificate verification.
Run: python scripts/e2e_test.py
"""
import hashlib
import http.client
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

CERT_DIR = r"c:\Users\ahirr\Mini-Project_DRV\DRV\data\sample_certs"
HOST = "127.0.0.1:8000"
BOUNDARY = b"----DRVBoundary2024"


def multipart_post(path, fields, files, cookies="", csrf_token=""):
    body = b""
    for name, value in fields.items():
        body += b"--" + BOUNDARY + b"\r\n"
        body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        body += value.encode() + b"\r\n"
    for name, (filename, fdata) in files.items():
        body += b"--" + BOUNDARY + b"\r\n"
        body += f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        body += b"Content-Type: application/pdf\r\n\r\n"
        body += fdata + b"\r\n"
    body += b"--" + BOUNDARY + b"--\r\n"

    headers = {
        "Content-Type": f"multipart/form-data; boundary={BOUNDARY.decode()}",
    }
    if cookies:
        headers["Cookie"] = cookies
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token

    conn = http.client.HTTPConnection(HOST)
    conn.request("POST", path, body, headers)
    resp = conn.getresponse()
    raw = resp.read()
    resp_headers = dict(resp.getheaders())
    try:
        data = json.loads(raw)
    except Exception as e:
        print(f"Error decoding JSON for {path} (HTTP {resp.status}): {raw.decode('utf-8', errors='replace')}")
        raise
    return resp.status, data, resp_headers


def json_post(path, payload, cookies="", csrf_token=""):
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if cookies:
        headers["Cookie"] = cookies
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    conn = http.client.HTTPConnection(HOST)
    conn.request("POST", path, body, headers)
    resp = conn.getresponse()
    raw = resp.read()
    resp_headers = dict(resp.getheaders())
    try:
        data = json.loads(raw)
    except Exception as e:
        print(f"Error decoding JSON for {path} (HTTP {resp.status}): {raw.decode('utf-8', errors='replace')}")
        raise
    return resp.status, data, resp_headers


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_cert(name):
    with open(f"{CERT_DIR}\\{name}", "rb") as f:
        return f.read()


PASS = "[PASS]"
FAIL = "[FAIL]"
results = []


def check(label, condition, got=None):
    ok = bool(condition)
    results.append((label, ok, got))
    icon = PASS if ok else FAIL
    print(f"  {icon}  {label}" + (f"  ->  {got}" if got else ""))


print("\n" + "=" * 60)
print("  DRV End-to-End Real Certificate Tests")
print("=" * 60)

# ── Hash verification ────────────────────────────────────────────────
print("\n[0] SHA-256 Hashes of sample PDFs:")
h101 = sha256_file(f"{CERT_DIR}\\sample_cert_101.pdf")
h102 = sha256_file(f"{CERT_DIR}\\sample_cert_102.pdf")
h103 = sha256_file(f"{CERT_DIR}\\sample_cert_103.pdf")
h101t = sha256_file(f"{CERT_DIR}\\sample_cert_101_tampered.pdf")
print(f"  CERT-101           : {h101}")
print(f"  CERT-101 (tampered): {h101t}")
print(f"  CERT-102           : {h102}")
print(f"  CERT-103           : {h103}")
check("Tampered hash differs from original", h101 != h101t)

# ── TC-01: Real PDF → MATCH ──────────────────────────────────────────
print("\n[TC-01] Upload sample_cert_101.pdf -> expect MATCH for CERT-101")
cert101 = read_cert("sample_cert_101.pdf")
status, data, _ = multipart_post(
    "/api/verify",
    {"record_id": "CERT-101"},
    {"file": ("sample_cert_101.pdf", cert101)},
)
state = data.get("result", {}).get("state")
check("HTTP 200", status == 200)
check("state == MATCH", state == "MATCH", state)

# ── TC-02: Tampered PDF → MISMATCH ──────────────────────────────────
print("\n[TC-02] Upload tampered PDF -> expect MISMATCH for CERT-101")
tampered = read_cert("sample_cert_101_tampered.pdf")
status, data, _ = multipart_post(
    "/api/verify",
    {"record_id": "CERT-101"},
    {"file": ("sample_cert_101_tampered.pdf", tampered)},
)
state = data.get("result", {}).get("state")
check("HTTP 200", status == 200)
check("state == MISMATCH", state == "MISMATCH", state)

# ── TC-03: Unknown ID → NOT_FOUND ───────────────────────────────────
print("\n[TC-03] Upload any PDF with unknown ID -> expect NOT_FOUND")
status, data, _ = multipart_post(
    "/api/verify",
    {"record_id": "CERT-999"},
    {"file": ("sample_cert_101.pdf", cert101)},
)
state = data.get("result", {}).get("state")
check("HTTP 200", status == 200)
check("state == NOT_FOUND", state == "NOT_FOUND", state)

# ── TC-04: Revoked ID → REVOKED ─────────────────────────────────────
print("\n[TC-04] Upload cert_103 for CERT-103 (revoked) -> expect REVOKED")
cert103 = read_cert("sample_cert_103.pdf")
status, data, _ = multipart_post(
    "/api/verify",
    {"record_id": "CERT-103"},
    {"file": ("sample_cert_103.pdf", cert103)},
)
state = data.get("result", {}).get("state")
check("HTTP 200", status == 200)
check("state == REVOKED", state == "REVOKED", state)

# ── Admin Login ──────────────────────────────────────────────────────
print("\n[Admin] Login")
status, data, resp_headers = json_post("/api/admin/login", {"username": "admin", "password": "admin123"})
csrf = data.get("result", {}).get("csrf_token", "")

# Search case-insensitively for set-cookie
session_cookie = ""
for k, v in resp_headers.items():
    if k.lower() == "set-cookie" and "drv_session=" in v:
        session_val = v.split("drv_session=")[1].split(";")[0]
        session_cookie = f"drv_session={session_val}"
        break

check("Admin login HTTP 200", status == 200)
check("CSRF token obtained", bool(csrf), csrf[:16] + "..." if csrf else "MISSING")
check("Session cookie obtained", bool(session_cookie), session_cookie[:25] + "..." if session_cookie else "MISSING")

# ── Admin Register new cert ──────────────────────────────────────────
if session_cookie and csrf:
    print("\n[Admin] Register CERT-999 with sample_cert_101.pdf")
    status, data, _ = multipart_post(
        "/api/admin/register",
        {"record_id": "CERT-999", "doc_type": "degree"},
        {"file": ("sample_cert_101.pdf", cert101)},
        cookies=session_cookie,
        csrf_token=csrf,
    )
    result = data.get("result", {})
    computed_hash = result.get("file_hash", "")
    print("Register result:", result)
    check("Register HTTP 200", status == 200, f"got {status}")
    check("file_hash matches local SHA-256", computed_hash == h101, f"computed={computed_hash} vs expected={h101}")
    check("tx_hash present", bool(result.get("tx_hash")))

    # Verify newly registered cert
    print("\n[Admin] Verify CERT-999 with same PDF -> expect MATCH")
    status, data, _ = multipart_post(
        "/api/verify",
        {"record_id": "CERT-999"},
        {"file": ("sample_cert_101.pdf", cert101)},
    )
    print("Verify newly registered cert result:", data)
    state = data.get("result", {}).get("state")
    check("HTTP 200", status == 200)
    check("state == MATCH for newly registered cert", state == "MATCH", state)

# ── Summary ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
print(f"  Results: {passed} passed, {failed} failed out of {len(results)} checks")
print("=" * 60 + "\n")

if failed:
    sys.exit(1)


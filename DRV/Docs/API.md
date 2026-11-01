# API.md — Decentralized Record Verifier with NLP Search

| | |
|---|---|
| **Project** | Decentralized Record Verifier with NLP Search (Web3 & AI) |
| **Owner / Mentor** | Vipul Ahirrao / Dr. Dipak Bhadane |
| **Version** | 1.0 (proposal-stage design), 1 Nov 2026 |
| **Companions** | `prd.md`, `architecture.md`, `database.md`, `design.md` |
| **Status** | **Proposed** contract. Nothing is implemented yet. Endpoints marked *(addition)* extend the PRD list to serve the frontend and admin flows. |

---

## 1. Overview

A JSON-over-HTTP API served by the Python backend. All routes live under `/api`. The browser frontend is the only intended client.

**Key behaviours**
- Verification of a **file** is deterministic and never touches the language model.
- Verification by **natural-language question** passes only the question text to the model. The model's output is an untrusted *suggestion* that the validator pipeline must approve before any blockchain call.
- Every response uses one envelope (§3), carries a `request_id`, and includes the integrity disclaimer where a verification result is returned.

## 2. Endpoint summary

| Method | Path | Purpose | Auth | PRD link |
|---|---|---|---|---|
| POST | `/api/verify` | Hash an uploaded file and compare with the registered record | None | FR-01 to FR-06 |
| POST | `/api/query` | Natural-language question → validated read-only answer | None (read-only intents) | FR-20 to FR-27 |
| GET | `/api/records/{record_id}` | Public status and minimal metadata of a record | None | US-2 |
| POST | `/api/admin/login` | Start an admin session | Credentials | FR-32 |
| POST | `/api/admin/logout` *(addition)* | End the session | Admin | FR-32 |
| POST | `/api/admin/register` | Register a record | Admin | FR-10, FR-11, FR-13 |
| POST | `/api/admin/revoke` | Revoke a record | Admin | FR-12, FR-13 |
| POST | `/api/admin/confirm` *(addition)* | Confirm a privileged natural-language request | Admin | FR-22 |
| GET | `/api/admin/transactions/{idempotency_key}` *(addition)* | Poll a write that was still pending | Admin | FR-33 |
| GET | `/api/results/tests` *(addition)* | Test-case outcomes for the Results page | None | US-7 |
| GET | `/api/results/comparison` *(addition)* | SLM vs rules-baseline metrics | None | US-7, G5 |
| GET | `/api/health` | Component availability | None | FR-34 |

If FastAPI is chosen (ADR-1), interactive docs are available at `/docs` and `/openapi.json`; disable them outside development.

---

## 3. Conventions

### 3.1 Transport and format
- Requests: `application/json`, except file uploads which use `multipart/form-data`.
- Responses: `application/json; charset=utf-8`.
- Timestamps: ISO-8601 UTC (`2026-11-02T10:15:30Z`).
- Hashes: SHA-256 as **64 lowercase hex characters, no prefix**.
- Record IDs: opaque strings matching the configured pattern (default `^CERT-\d+$`). IDs must never contain personal data.

### 3.2 Response envelope

```json
{
  "request_id": "req_01HV3Q8K2M",
  "status": "ok",
  "result": {},
  "handling": null,
  "error": null,
  "disclaimer": "A match shows the file is identical to what was registered. It doesn't prove who issued it or that its contents are true."
}
```

| Field | Type | Meaning |
|---|---|---|
| `request_id` | string | Also returned in the `X-Request-ID` header and written to the audit log |
| `status` | enum | `ok`, `rejected`, `clarification`, `confirmation_required` *(proposed)*, `error` |
| `result` | object or null | Answer payload (shape depends on endpoint) |
| `handling` | object or null | For `/api/query`: parser used, parsed draft, and per-stage results |
| `error` | object or null | `{ "code": "E_…", "message": "human-readable" }` |
| `disclaimer` | string or null | Present on every verification answer |

### 3.3 `handling` object (query endpoint)

```json
{
  "parser": "slm",
  "parsed": {
    "intent": "check_status",
    "record_id": "CERT-104",
    "check_revocation": true,
    "clarification_needed": false
  },
  "stages": [
    { "order": 1, "name": "schema",           "passed": true },
    { "order": 2, "name": "intent_allowlist", "passed": true },
    { "order": 3, "name": "record_id",        "passed": true },
    { "order": 4, "name": "role",             "passed": true },
    { "order": 5, "name": "clarity",          "passed": true }
  ]
}
```

The frontend validation stepper (see `design.md`) must render this array exactly as returned. A failed stage includes `"reason": "…"` and later stages are omitted.

### 3.4 Verification states

| `result.state` | Meaning |
|---|---|
| `MATCH` | Record exists, not revoked, file hash equals registered hash |
| `MISMATCH` | Record exists but the file hash differs |
| `REVOKED` | Record exists and is revoked (`hash_match` says whether the file still equals the registered file) |
| `NOT_FOUND` | No record with that ID |

A `NOT_FOUND`, `MISMATCH` or `REVOKED` answer is a **successful verification result** and returns HTTP 200.

### 3.5 Error codes and HTTP mapping

| Code | HTTP | Meaning |
|---|---|---|
| `E_SCHEMA` | 400 | Request body or model output failed schema validation |
| `E_INTENT` | 400 | Intent not in the allowlist, or `unknown` |
| `E_ID_FORMAT` | 400 | Record ID does not match the pattern |
| `E_UPLOAD_INVALID` | 400 / 413 / 415 | Bad file, too large (413) or unsupported type (415) |
| `E_UNAUTHORIZED` | 401 / 403 | Not logged in (401) or role insufficient (403) |
| `E_NOT_FOUND` | 404 | Used only by admin writes on an unknown record (e.g. revoke) and unknown routes |
| `E_DUPLICATE` | 409 | Record ID already registered |
| `E_AMBIGUOUS` | 422 | Clarification needed; payload includes a question |
| `E_RATE_LIMIT` | 429 | Too many requests |
| `E_CHAIN_DOWN` | 503 | Blockchain unreachable. **Not** a verification result |
| `E_MODEL_DOWN` | 503 | Model unavailable or timed out |
| `E_TX_FAILED` | 502 | Transaction submitted but failed or reverted for another reason |
| `E_INTERNAL` | 500 | Unexpected error; no stack traces in the response |

### 3.6 Authentication and sessions (Proposed)
- Admin login issues an `HttpOnly`, `Secure` (when HTTPS), `SameSite=Strict` session cookie with a short expiry.
- State-changing admin requests also require a CSRF header `X-CSRF-Token` returned by login.
- The role used by the validator comes **only** from the session, never from request fields or model output.
- Alternative (open decision): short-lived bearer token.

### 3.7 Idempotency
Admin write endpoints require an `Idempotency-Key` header (any unique string, e.g. a UUID). Repeating a request with the same key returns the original outcome and never sends a second transaction.

### 3.8 Limits (Proposed values, tune after measurement)
| Item | Limit |
|---|---|
| Upload size | `MAX_UPLOAD_MB` (suggested default: 5 MB) |
| Allowed upload types | `application/pdf` (optionally PNG/JPEG); type checked by file signature, not extension |
| Query text length | 500 characters |
| Public rate limit | Per-IP limit on `/api/verify` and `/api/query` (value to be set) |
| Model timeout | Configurable; default set after latency measurement |

---

## 4. Endpoints

### 4.1 `POST /api/verify`: verify a file

**Request** (`multipart/form-data`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `record_id` | string | Yes | Must match the ID pattern |
| `file` | file | Yes | Hashed, then discarded |

**Success (200), file matches**
```json
{
  "request_id": "req_01HV3Q8K2M",
  "status": "ok",
  "result": {
    "state": "MATCH",
    "record_id": "CERT-104",
    "computed_hash": "9f2c41ab7d03e6c158b9a0fe2c47d1e3a6b80c951e7f3d42c08a5b17e92d64f0",
    "registered_hash": "9f2c41ab7d03e6c158b9a0fe2c47d1e3a6b80c951e7f3d42c08a5b17e92d64f0",
    "hash_match": true,
    "revoked": false,
    "doc_type": "degree",
    "registered_at": "2026-11-02T10:15:30Z"
  },
  "handling": null,
  "error": null,
  "disclaimer": "A match shows the file is identical to what was registered. It doesn't prove who issued it or that its contents are true."
}
```

**Other results (all HTTP 200)**
- `MISMATCH`: `hash_match: false`, both hashes returned so the UI can highlight the first differing group.
- `REVOKED`: adds `revoked_at` and `reason` (`issued_in_error`, `superseded`, `fraud_suspected`, `other`).
- `NOT_FOUND`: `registered_hash: null`.

**Errors:** `E_ID_FORMAT`, `E_UPLOAD_INVALID`, `E_CHAIN_DOWN`, `E_RATE_LIMIT`.

```bash
curl -X POST http://localhost:8000/api/verify \
  -F record_id=CERT-104 \
  -F file=@certificate.pdf
```

---

### 4.2 `POST /api/query`: natural-language question

Read-only questions only. File hash comparison is available **only** through `/api/verify`, so document content never reaches the model.

**Request** (`application/json`)
```json
{
  "text": "Is CERT-104 registered, and has it been revoked?",
  "parser": "slm"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `text` | string | Yes | Max 500 characters |
| `parser` | `"slm"` or `"rules"` | No | Default `slm`. `rules` selects the baseline (used for comparison and demos) |

**Success (200)**
```json
{
  "request_id": "req_01HV3R1D9P",
  "status": "ok",
  "result": {
    "intent": "check_status",
    "record_id": "CERT-104",
    "state": "REVOKED",
    "exists": true,
    "revoked": true,
    "revoked_at": "2026-12-12T09:00:00Z",
    "reason": "issued_in_error",
    "answer_text": "This record was revoked on 12 Dec 2026."
  },
  "handling": {
    "parser": "slm",
    "parsed": { "intent": "check_status", "record_id": "CERT-104", "check_revocation": true, "clarification_needed": false },
    "stages": [
      { "order": 1, "name": "schema", "passed": true },
      { "order": 2, "name": "intent_allowlist", "passed": true },
      { "order": 3, "name": "record_id", "passed": true },
      { "order": 4, "name": "role", "passed": true },
      { "order": 5, "name": "clarity", "passed": true }
    ]
  },
  "error": null,
  "disclaimer": "A match shows the file is identical to what was registered. It doesn't prove who issued it or that its contents are true."
}
```

**Clarification (422)**
```json
{
  "request_id": "req_01HV3R5T0A",
  "status": "clarification",
  "result": {
    "message": "Which certificate do you mean? Please include its ID, for example CERT-104.",
    "missing": ["record_id"]
  },
  "handling": { "parser": "slm", "parsed": { "intent": "check_status", "record_id": null, "check_revocation": false, "clarification_needed": true }, "stages": [ { "order": 1, "name": "schema", "passed": true }, { "order": 2, "name": "intent_allowlist", "passed": true }, { "order": 3, "name": "record_id", "passed": true }, { "order": 4, "name": "role", "passed": true }, { "order": 5, "name": "clarity", "passed": false, "reason": "record_id missing" } ] },
  "error": { "code": "E_AMBIGUOUS", "message": "More information is needed." },
  "disclaimer": null
}
```

**Rejected (403): privileged request from an anonymous user**
```json
{
  "request_id": "req_01HV3R9Z7C",
  "status": "rejected",
  "result": null,
  "handling": {
    "parser": "slm",
    "parsed": { "intent": "revoke_record", "record_id": "CERT-104", "check_revocation": false, "clarification_needed": false },
    "stages": [
      { "order": 1, "name": "schema", "passed": true },
      { "order": 2, "name": "intent_allowlist", "passed": true },
      { "order": 3, "name": "record_id", "passed": true },
      { "order": 4, "name": "role", "passed": false, "reason": "admin session required" }
    ]
  },
  "error": { "code": "E_UNAUTHORIZED", "message": "That request isn't something this tool can do." },
  "disclaimer": null
}
```

**Privileged intents from a logged-in admin (Proposed two-step safeguard).** A natural-language `revoke_record` is **not** executed immediately. The response is HTTP 200 with:
```json
{
  "status": "confirmation_required",
  "result": {
    "action": "revoke",
    "record_id": "CERT-104",
    "summary": "Revoke CERT-104? This cannot be undone.",
    "confirmation_token": "ct_9d1f…",
    "expires_in_seconds": 60
  }
}
```
The admin then calls `POST /api/admin/confirm`. `register_record` through text is not executable (it needs a file); the response asks the admin to use the Admin screen. *(Open decision: this is stricter than the PRD wording; confirm with the mentor.)*

**Other errors:** `E_SCHEMA` (model output invalid, 400), `E_INTENT` (out of scope or `unknown`, 400), `E_ID_FORMAT` (400), `E_MODEL_DOWN` (503), `E_CHAIN_DOWN` (503), `E_RATE_LIMIT` (429).

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"text":"Is CERT-104 registered, and has it been revoked?"}'
```

---

### 4.3 `GET /api/records/{record_id}`: record status

Always HTTP 200 for a well-formed ID, so the answer is a verification result, not a missing route.

```json
{
  "request_id": "req_01HV3S2B6N",
  "status": "ok",
  "result": {
    "state": "REVOKED",
    "record_id": "CERT-104",
    "exists": true,
    "doc_type": "degree",
    "registered_hash": "9f2c41ab7d03e6c158b9a0fe2c47d1e3a6b80c951e7f3d42c08a5b17e92d64f0",
    "registered_at": "2026-11-02T10:15:30Z",
    "revoked": true,
    "revoked_at": "2026-12-12T09:00:00Z",
    "reason": "issued_in_error"
  },
  "handling": null,
  "error": null,
  "disclaimer": "Registration status shows what was recorded. It doesn't prove who issued the document or that its contents are true."
}
```
Unknown ID → `"state": "NOT_FOUND"`, `"exists": false`. Bad format → 400 `E_ID_FORMAT`.

---

### 4.4 `POST /api/admin/login`

**Request**
```json
{ "username": "admin", "password": "••••••••" }
```
**Success (200):** sets the session cookie and returns
```json
{ "request_id": "req_…", "status": "ok", "result": { "role": "admin", "csrf_token": "…", "expires_at": "2026-11-02T11:15:30Z" }, "handling": null, "error": null, "disclaimer": null }
```
**Errors:** 401 `E_UNAUTHORIZED` (generic message, no hint which field was wrong), 429 `E_RATE_LIMIT` after repeated failures.

`POST /api/admin/logout` *(addition)* ends the session and returns `{ "status": "ok" }`.

---

### 4.5 `POST /api/admin/register`

**Headers:** session cookie, `X-CSRF-Token`, `Idempotency-Key`.
**Request** (`multipart/form-data`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `record_id` | string | Yes | Opaque ID, pattern-checked |
| `doc_type` | `degree` / `marksheet` / `training` | Yes | Mapped to codes 1/2/3 |
| `file` | file | One of `file` or `sha256` | Hashed, then discarded |
| `sha256` | string | One of `file` or `sha256` | 64 hex chars |

**Success (200)**
```json
{
  "request_id": "req_…",
  "status": "ok",
  "result": {
    "operation": "register",
    "record_id": "CERT-105",
    "registered_hash": "…64 hex…",
    "tx_hash": "0x…",
    "tx_status": "confirmed",
    "block_number": 42,
    "confirmation_ms": 318
  },
  "handling": null,
  "error": null,
  "disclaimer": null
}
```
**Pending (202):** if the receipt is not available within the timeout, `tx_status: "pending"` is returned and the client polls §4.8.
**Errors:** 401/403 `E_UNAUTHORIZED`, 409 `E_DUPLICATE`, 400 `E_ID_FORMAT` / `E_UPLOAD_INVALID` / `E_SCHEMA`, 503 `E_CHAIN_DOWN`, 502 `E_TX_FAILED`.

---

### 4.6 `POST /api/admin/revoke`

**Headers:** session cookie, `X-CSRF-Token`, `Idempotency-Key`.
**Request**
```json
{ "record_id": "CERT-104", "reason": "issued_in_error" }
```
`reason` ∈ `issued_in_error` (1), `superseded` (2), `fraud_suspected` (3), `other` (4).

**Success (200)** mirrors §4.5 with `"operation": "revoke"`. Revoking an already revoked record is idempotent and returns the existing outcome.
**Errors:** 404 `E_NOT_FOUND` (unknown record), 401/403, 400, 503, 502.

---

### 4.7 `POST /api/admin/confirm` *(addition)*

Completes a privileged action proposed by `/api/query`.
```json
{ "confirmation_token": "ct_9d1f…" }
```
Tokens are single-use, bound to the session, and expire quickly. Result matches §4.6. Invalid or expired token → 400 `E_SCHEMA`.

### 4.8 `GET /api/admin/transactions/{idempotency_key}` *(addition)*
Returns the stored write outcome from `tx_log`: `tx_status` is `pending`, `confirmed`, `reverted` or `failed`, with `tx_hash`, `block_number`, and `confirmation_ms` where available.

---

### 4.9 Results endpoints *(addition)*

**`GET /api/results/tests`**
```json
{
  "status": "ok",
  "result": {
    "dataset_version": "v1",
    "tests": [
      { "id": "TC-01", "scenario": "Registered certificate, original file", "expected": "MATCH", "outcome": "pass" }
    ]
  }
}
```
`outcome` is `pass`, `fail` or `not_run`.

**`GET /api/results/comparison?split=test`**
```json
{
  "status": "ok",
  "result": {
    "dataset_version": "v1",
    "split": "test",
    "runs": [
      {
        "parser": "slm",
        "model": "<model-name>",
        "constrained_decoding": false,
        "metrics": [
          { "name": "intent_accuracy", "group": "all", "value": null, "ci_low": null, "ci_high": null, "n": null }
        ]
      }
    ]
  }
}
```
All values are `null` until real evaluation runs exist. The API must never return invented numbers.

---

### 4.10 `GET /api/health`
```json
{
  "status": "degraded",
  "components": {
    "backend": { "up": true },
    "chain": { "up": false, "reason": "rpc timeout" },
    "model": { "up": true, "name": "<model-name>" }
  }
}
```
`status` is `ok`, `degraded` or `down`. No secrets, keys or internal addresses beyond the public contract address.

---

## 5. Schemas

### 5.1 Query draft (model output, validated by stage 1)

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["intent", "record_id", "check_revocation", "clarification_needed"],
  "properties": {
    "intent": {
      "enum": ["verify_record", "check_status", "get_metadata",
               "register_record", "revoke_record", "unknown"]
    },
    "record_id": { "type": ["string", "null"], "pattern": "^CERT-\\d+$" },
    "check_revocation": { "type": "boolean" },
    "clarification_needed": { "type": "boolean" }
  }
}
```

### 5.2 Validation stages

| Order | `name` | Fails when | Error code |
|---|---|---|---|
| 1 | `schema` | Not valid JSON or does not match §5.1 | `E_SCHEMA` |
| 2 | `intent_allowlist` | Intent not allowed or `unknown` | `E_INTENT` |
| 3 | `record_id` | ID missing for an intent that needs one, or wrong format | `E_ID_FORMAT` |
| 4 | `role` | Privileged intent without an admin session | `E_UNAUTHORIZED` |
| 5 | `clarity` | `clarification_needed` is true or required info is missing | `E_AMBIGUOUS` |

The pipeline is a pure function of (draft, session). The signing account is chosen by the chain gateway from configuration and is never read from the request.

---

## 6. Security notes for implementers

1. Treat both user input and model output as untrusted; validate before every chain call.
2. Never pass uploaded document text to the model.
3. Return distinct errors for "not found" (a result) and "chain unavailable" (an error). Never convert an outage into a negative verification.
4. Do not echo stack traces, keys, file paths or internal addresses.
5. Log request ID, route, outcome, failed stage and latency only; no file contents.
6. Compare secrets and tokens in constant time; store only hashes of session and confirmation tokens.
7. Keep the disclaimer on every verification response.

## 7. Traceability

| PRD / test | API element |
|---|---|
| TC-01, TC-02, TC-03, TC-04 | `/api/verify` states `MATCH`, `MISMATCH`, `NOT_FOUND`, `REVOKED` |
| TC-05 | `/api/admin/*` and `/api/query` with `E_UNAUTHORIZED` |
| TC-06 | Query `E_SCHEMA` on malformed model output |
| TC-07 | Query `E_AMBIGUOUS` / `status: clarification` |
| TC-08 | `E_CHAIN_DOWN` (503) |
| TC-09, TC-10 | Query `E_INTENT` / `E_UNAUTHORIZED`, with `handling.stages` showing the blocking stage |
| FR-31 (show parsed JSON) | `handling.parsed` |
| FR-34 (health) | `/api/health` |

## 8. Open decisions

1. Cookie session vs bearer token for admin authentication.
2. Whether natural-language privileged intents use the proposed two-step confirmation.
3. Exact limits: upload size, rate limits, model timeout.
4. Whether `/api/query` should also accept a file in a later version (currently excluded to keep documents away from the model).
5. Whether `/api/results/*` is public or admin-only in the final demo.

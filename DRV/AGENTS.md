# AGENTS.md

Instructions for AI coding agents (and human contributors) working on **Decentralized Record Verifier with NLP Search (Web3 & AI)**, a third-year B.Tech AIML mini project. Read this file first, then the documents listed in §2.

> **Status:** the repository is at design stage. Commands and paths below are **proposed** and must be updated in this file as soon as the real toolchain is chosen. Do not describe anything as implemented or measured unless it actually is.

---

## 1. What this project is

A web app that (1) hashes an uploaded certificate with SHA-256 and compares it with a fingerprint registered on a blockchain via a Solidity contract, and (2) lets users ask plain-English questions that a locally hosted Small Language Model (SLM) converts into a structured JSON request. A trusted Python backend validates that request before calling a fixed set of contract functions.

The research question: *how accurately and safely can an SLM translate natural-language requests into valid, authorized verification operations, compared with a rules-based baseline?* This is a **proposed** question, not an established gap.

## 2. Document map and precedence

| File | Governs |
|---|---|
| `Decisions.md` | Single source of truth for architectural & design decisions |
| `prd.md` | What to build and why (requirements, tests, scope) |
| `architecture.md` | How it is structured (components, flows, security) |
| `database.md` | Contract storage and SQLite schema |
| `API.md` | HTTP contract |
| `NLP.md` | Natural language processing specification & prompt schema |
| `design.md` | Frontend look, motion, copy |

If documents disagree: **DECISIONS > PRD > architecture > database > API > NLP > design**. Do not silently resolve a conflict. Fix the lower-precedence document or ask the owner. When you change behaviour, update the matching document in the same change.

---

## 3. Hard rules (never break these)

1. **The model interprets; the backend decides; the contract enforces.** SLM output is an untrusted suggestion. Nothing the model emits may choose the signer, the role, or bypass validation.
2. **Fail closed.** Validation failure, timeout, malformed output or ambiguity → refuse or ask for clarification. Never guess.
3. **Only predefined contract functions** may be called: `registerRecord`, `verifyHash`, `getRecord`, `isRevoked`, `revokeRecord`. Add no others without approval.
4. **Access control lives in both the backend and the contract.** Never rely on one alone.
5. **Documents never go to the model.** Only the user's query text is sent. Uploaded files are hashed over raw bytes and discarded: never stored, logged or put on-chain.
6. **No personal data anywhere.** All certificates, names and queries are synthetic. Record IDs are opaque (`CERT-104`), never names or roll numbers.
7. **Requests are stateless.** No conversation memory in the NLP path.
8. **Never convert an outage into a verification result.** `NOT_FOUND` is an answer; `E_CHAIN_DOWN` is an error. Keep them distinct.
9. **Always keep the integrity disclaimer** on verification results: a match proves file integrity only, not issuer legitimacy or truthfulness.
10. **No secrets in the repository.** Keys and credentials come from environment variables. Never commit `.env` files, private keys or model API keys.
11. **No invented results or citations.** Metrics come only from real runs. Do not fabricate papers, DOIs, accuracy numbers or "expected" results presented as findings.
12. **Stay in scope.** No W3C VC/DID compliance claims, production hardening, real student data or hosted model APIs without explicit approval.

---

## 4. Repository layout (proposed)

```
record-verifier/
├── contracts/            RecordRegistry.sol
├── test/                 contract tests
├── scripts/              deploy, seed records
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/      verify, query, admin, records, health, results
│   │   ├── services/     hashing, chain_gateway, auth, audit
│   │   ├── nlp/          parser_interface, slm_parser, rules_parser
│   │   ├── validation/   pipeline, schema
│   │   └── config.py
│   └── tests/            unit, integration, security
├── eval/                 dataset/, harness.py, metrics.py, results/
├── frontend/             HTML, CSS, JS (no framework)
├── migrations/           001_init.sql, ...
├── docs/                 prd.md, design.md, architecture.md, database.md, API.md
└── AGENTS.md
```

## 5. Setup and common commands (proposed, confirm and update)

```bash
# Backend (FastAPI proposed)
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --app-dir backend

# Contracts (Hardhat proposed)
npm install
npx hardhat node                 # local EVM chain
npx hardhat test                 # contract tests
npx hardhat run scripts/deploy.js --network localhost

# Tests and evaluation
pytest backend/tests
python eval/harness.py --split dev
```

Environment variables (names only; values never committed): `RPC_URL`, `CONTRACT_ADDRESS`, `SIGNER_PRIVATE_KEY`, `MODEL_NAME`, `MODEL_ENDPOINT`, `ID_PATTERN`, `MAX_UPLOAD_MB`, `ADMIN_CREDENTIALS_HASH`, `LOG_LEVEL`, `DB_PATH`.

---

## 6. Coding conventions

**Python**
- Type hints everywhere; Pydantic (or equivalent) models for request/response and the query draft schema.
- One responsibility per module, matching `architecture.md` §6. Routers contain no business logic.
- The validator pipeline is a **pure function** of (draft, session). No network, model or database calls inside it.
- Parameterized SQL only; no string-built queries. Booleans as 0/1, timestamps as ISO-8601 UTC text.
- Catch specific exceptions; map them to the error codes in `API.md` §3.5. Never return stack traces.

**Solidity (0.8.x)**
- No upgradeability, no `selfdestruct`, no unbounded loops, no external calls.
- Custom errors, events for state changes, NatSpec comments.
- Record key is `keccak256(bytes(recordId))`; emit the original ID in events.
- Check storage packing with the compiler layout output before claiming gas or slot savings.

**Frontend (HTML, CSS, JavaScript)**
- Follow `design.md` tokens exactly (palette, fonts, spacing, motion). One accent colour; no neon, gradients on text or glow effects.
- Animate only `transform` and `opacity`; honour `prefers-reduced-motion`.
- The validation stepper renders the API's real `handling.stages`, never a scripted demo.
- Accessible by default: labels, focus rings, `aria-live` for results, AA contrast, status never by colour alone.

**General**
- Prefer small, readable functions and explicit names. No dead code, no commented-out blocks.
- Use conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`). Keep changes small and focused.

---

## 7. Testing requirements

| Area | Must be covered |
|---|---|
| **Validator** | Every stage's pass and fail path; malformed JSON; extra fields; privileged intents without admin; clarification path |
| **Contract** | Register, duplicate revert, verify, revoke, unknown-ID revert, unauthorized caller revert, events |
| **API** | TC-01 to TC-10 as integration tests (see `prd.md` §14); error code and HTTP status mapping |
| **Security** | Direct injection strings, out-of-scope requests, oversized or wrong-type uploads, replayed idempotency keys |
| **Hashing** | Same bytes → same hash; one-byte change → different hash; file is not persisted |
| **Parsers** | SLM and rules parsers both implement `parse(text) -> RequestDraft` and pass the same schema tests |

**Evaluation protocol (do not break):**
1. The labelled query set is split into `dev` and `test` once, with a recorded seed. After freezing, **never edit or re-split the test split**.
2. Tune prompts and rules on `dev` only.
3. Run both parsers through the **same** validator and chain path.
4. Use deterministic decoding (temperature 0), record model name and parameters, repeat runs, and report uncertainty.
5. Report accuracy and security results separately. Report limitations honestly; a rules baseline matching the SLM is a valid result.

---

## 8. Security checklist for every change

- [ ] No new path from model output to the chain that bypasses the validator
- [ ] Role comes from the session only; signer comes from configuration only
- [ ] No file content, keys or personal data in logs, responses or the database
- [ ] New endpoints documented in `API.md`; new tables in `database.md` and a numbered migration
- [ ] Errors use the defined codes and keep "not found" distinct from "unavailable"
- [ ] Disclaimer present on verification responses
- [ ] Tests added for success, failure and abuse cases

## 9. Definition of done

A change is done when: it meets the relevant requirement IDs in `prd.md`; tests pass locally; the security checklist is satisfied; docs are updated; and the commit message states what changed and why.

---

## 10. How agents should work here

1. **Read before writing.** Open the PRD requirement, the architecture section and the API/DB entries that cover your task.
2. **Prefer the smallest change** that satisfies the requirement. Do not refactor unrelated code.
3. **Ask when unsure** about scope, security trade-offs or conflicting documents. Open decisions are listed at the end of each doc: do not decide them silently.
4. **Be honest in reports.** State what you ran, what passed, what you did not verify, and any assumptions.
5. **Mark assumptions** in code comments and PR descriptions when a decision is not settled.
6. **Do not** add dependencies, call external model APIs, deploy to a public network, or change the evaluation protocol without approval.

## 11. Things agents must not do

- Let the SLM sign transactions, select accounts, or decide authorization.
- Add "helpful" convenience endpoints that skip validation.
- Store, log or forward uploaded document content.
- Hard-code keys, passwords, model tokens or contract owner keys.
- Weaken, skip or delete tests to make a build pass.
- Edit the frozen test split or tune on it.
- Present expected or example numbers as measured results.
- Claim the system is fully decentralized (it is blockchain-anchored with centralized components: backend, RPC node, model host) or standards-compliant with W3C VC/DID.

## 12. Open decisions (do not assume)

1. FastAPI vs Flask; Hardhat vs Remix.
2. Which SLM and runtime fit the available hardware.
3. Cookie session vs bearer token for admin login; two-step confirmation for natural-language privileged actions.
4. Final "minimal metadata" fields (currently only a `docType` code is proposed).
5. Whether a public testnet deployment is required.

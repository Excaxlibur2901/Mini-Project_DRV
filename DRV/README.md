# Decentralized Record Verifier with NLP Search (Web3 & AI)

Third-year B.Tech (AIML) Academic Mini Project  
**Student:** Vipul Ahirrao  
**Mentor:** Dr. Dipak Bhadane  
**Institution:** R. C. Patel Institute of Technology, Shirpur (DBATU)  
**Academic Year:** 2026–2027  

---

## 1. Overview

This project implements a dual-path academic certificate verification system:
1. **Deterministic File Verification:** Computes the SHA-256 cryptographic digest of an uploaded certificate file and verifies it against an on-chain fingerprint stored in an immutable EVM smart contract (`RecordRegistry.sol`).
2. **Natural Language Query Interface:** Uses a locally hosted Small Language Model (SLM) running via Ollama (`Qwen2.5-3B-Instruct`, 4-bit) to translate plain-English queries into structured JSON requests.

### Core Architectural Principle
> **The model interprets; the backend decides; the contract enforces.**

- The SLM output is **strictly untrusted input**.
- The trusted Python backend validates the request through a **5-stage pure-function validator pipeline** (Schema → Intent Allowlist → Record ID Format → Role Authority → Clarity) before any contract interaction.
- The smart contract independently enforces role-based access control and state integrity.
- **Privacy & Integrity:** Uploaded documents are hashed over raw bytes and immediately discarded. Document contents are never sent to the SLM or recorded on-chain. A hash match proves file integrity only, not issuer legitimacy or truthfulness of contents.

---

## 2. Technology Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn, Pydantic v2, Web3.py
- **Smart Contracts:** Solidity 0.8.24, Hardhat, Local EVM dev node
- **Database:** SQLite (WAL mode) for audit logs, idempotency logs, and evaluation metrics
- **NLP / SLM:** Qwen2.5-3B-Instruct (4-bit quantized) via Ollama HTTP API (temperature 0, deterministic)
- **Rules Baseline:** Regex & keyword parser (for fair empirical comparison)
- **Frontend:** HTML5, CSS3 (design tokens), Vanilla JavaScript

---

## 3. Project Structure

```
DRV/
├── contracts/               # Solidity smart contracts (RecordRegistry.sol)
├── test/                    # Hardhat contract test suites
├── scripts/                 # Deployment and seeding scripts
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI application entry point
│   │   ├── config.py        # Settings loaded from environment variables
│   │   ├── routers/         # API endpoints (verify, query, admin, records, health, results)
│   │   ├── services/        # Business logic (hashing, chain gateway, auth, audit)
│   │   ├── nlp/             # SLM parser adapter & rules-based baseline
│   │   └── validation/      # Pure-function validator pipeline & JSON schemas
│   ├── requirements.txt     # Python dependencies
│   └── tests/               # Pytest suites (unit, integration, security)
├── eval/                    # Evaluation dataset, harness, and benchmark outputs
├── frontend/                # Adapted frontend application
│   └── Stitch_frontend/     # Pristine Stitch design export (kept untouched)
├── migrations/              # Numbered SQLite migration scripts (001_init.sql)
├── Docs/                    # Authoritative technical specifications
│   ├── Decisions.md         # Precedence #1: Single source of truth for architectural choices
│   ├── prd.md               # Precedence #2: Product Requirements Document
│   ├── architecture.md      # Precedence #3: Architecture & threat models
│   ├── database.md          # Precedence #4: On-chain & off-chain data design
│   ├── API.md               # Precedence #5: REST API specification
│   ├── NLP.md               # Precedence #6: NLP prompt & interpreter specification
│   ├── design.md            # Precedence #7: Frontend design tokens and guidelines
│   └── CONSISTENCY.md       # Cross-document audit log
├── AGENTS.md                # Autonomous agent operating instructions
├── hardhat.config.js        # Hardhat configuration
├── package.json             # Node.js dependencies for contract tooling
├── .env.example             # Template for environment variables
└── README.md
```

---

## 4. Setup and Quick Start

### 4.1 Prerequisites
- **Node.js:** v18+ (tested on v24)
- **Python:** v3.10+ (tested on v3.14)
- **Ollama:** Installed locally with model `qwen2.5:3b-instruct`

### 4.2 Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Configure local paths, RPC URL, and model endpoints as needed. Never commit `.env` or private keys.

### 4.3 Database Setup
Initialize the SQLite database with the versioned migration:
```bash
sqlite3 data/verifier.db < migrations/001_init.sql
```

### 4.4 Backend Setup
```bash
# Set PYTHONPATH to include backend/
$env:PYTHONPATH = "backend"

# Start the development server
uvicorn app.main:app --reload --app-dir backend
```
The API health check will be accessible at: `http://localhost:8000/api/health`

### 4.5 Smart Contract Development
```bash
# Install dependencies
npm install

# Compile contracts
npx hardhat compile

# Run Hardhat test suite
npx hardhat test

# Start local node
npx hardhat node
```

---

## 5. Testing & Verification

- **Backend tests:**
  ```bash
  $env:PYTHONPATH = "backend"
  python -m pytest backend/tests
  ```
- **Contract tests:**
  ```bash
  npx hardhat test
  ```
- **Evaluation harness (Phase 7):**
  ```bash
  python eval/harness.py --split test
  ```

---

## 6. Document Precedence
If specifications disagree, the order of authority is:  
**DECISIONS > PRD > ARCHITECTURE > DATABASE > API > NLP > DESIGN**


# DECISIONS.md

Single source of truth for choices that were open in earlier documents.
If another document disagrees with this file, fix the other document.

Status key: **Decided** (use it), **Proposed** (use it unless the mentor objects), **Open** (resolve before the stated week).

Project: Decentralized Record Verifier with NLP Search
Student: Vipul Ahirrao | Mentor: Dr. Deepak Bhadane

---

## 1. Hardware and environment

| Item | Value |
| --- | --- |
| Machine | Lenovo laptop, AMD Ryzen 7, NVIDIA RTX 4050 Laptop GPU (6 GB VRAM), 24 GB RAM |
| OS | Windows (change here if different) |
| Run mode for all measurements | Plugged in, performance power mode, same settings every run |

Report this hardware in the final results, because latency numbers depend on it.

---

## 2. Decision register

| ID | Topic | Decision | Status |
| --- | --- | --- | --- |
| D-01 | Backend framework | FastAPI | Proposed |
| D-02 | Smart-contract tooling | Hardhat (tests in JS/TS); Remix only for quick experiments | Proposed |
| D-03 | Blockchain | Local Hardhat network for all development and evaluation; public testnet only as an optional demo | Decided |
| D-04 | Contract language | Solidity 0.8.x | Proposed |
| D-05 | Off-chain storage | SQLite (audit log, admin transactions, evaluation data) | Proposed |
| D-06 | Frontend | Plain HTML, CSS, JavaScript, following `design.md` | Decided |
| D-07 | SLM runtime | Ollama, called over its local HTTP API | Proposed |
| D-08 | Main SLM | Qwen2.5-3B-Instruct, 4-bit quantized | Proposed |
| D-09 | Comparison models | One of Llama 3.2 3B Instruct or Phi-3.5-mini; optionally Qwen2.5-1.5B-Instruct for a size comparison | Proposed |
| D-10 | Decoding settings | temperature 0, fixed seed, fixed context length, same prompt for all runs | Decided |
| D-11 | Evaluation conditions | Rules baseline, SLM unconstrained, SLM schema-constrained (per model) | Decided |
| D-12 | Fine-tuning | Not planned. Consider only if prompting performs poorly and time remains | Open (decide by Week 6) |
| D-13 | Natural-language admin actions | Two-step: the query returns a confirmation request; the action runs only after `POST /api/admin/confirm` by a logged-in admin | Open (confirm with mentor by Week 3) |
| D-14 | On-chain metadata | Hash, record ID key, status, timestamps, and `docType` (degree, marksheet, training) | Open (decide by Week 3) |
| D-15 | Record ID format | `^[A-Z]{2,6}-[0-9]{1,8}$` (e.g. CERT-104). IDs are opaque; never a name or roll number | Proposed |
| D-16 | Evaluation dataset size | About 100-150 labelled queries in four tiers; frozen before any run | Proposed |
| D-17 | Documentation tools | Markdown in `/docs`; diagrams in Mermaid | Decided |

---

## 3. Rules that follow from these decisions

1. The model interprets. The backend decides. The contract enforces.
2. Uploaded files are hashed and never sent to the model.
3. Evaluation uses the same validator and chain path for every condition.
4. No result numbers appear in any document until they come from a real run.
5. The evaluation dataset is frozen before runs. Prompt tuning uses a separate development set.

---

## 4. Open questions to resolve

| Question | Why it matters | Resolve by |
| --- | --- | --- |
| D-13: Is the two-step confirmation for admin actions accepted? | The PRD and API docs currently differ | Week 3 |
| D-14: Is `docType` kept on-chain? | Changes contract, database, and API schemas | Week 3 |
| Does the college need a specific project-report format beyond the proposal template? | May change the final report only | Week 6 |
| Is a public testnet demo required, or is local enough? | Affects Week 7-8 effort | Week 5 |

---

## 5. Change log

| Date | Change | Reason |
|---|---|---|
| (fill in) | Initial version | Pre-build decisions |

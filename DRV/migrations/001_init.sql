-- migrations/001_init.sql
-- Decentralized Record Verifier — Initial Schema
-- Matches DATABASE.md §4.3 (Proposed, 1 Nov 2026)

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version     INTEGER PRIMARY KEY,
  applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ===== Operational tables =====

CREATE TABLE IF NOT EXISTS audit_log (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id   TEXT NOT NULL UNIQUE,
  route        TEXT NOT NULL,
  http_method  TEXT NOT NULL CHECK (http_method IN ('GET','POST')),
  parser_type  TEXT CHECK (parser_type IN ('slm','rules')),
  intent       TEXT,
  actor_role   TEXT NOT NULL DEFAULT 'anonymous' CHECK (actor_role IN ('anonymous','admin')),
  outcome      TEXT NOT NULL CHECK (outcome IN ('ok','rejected','clarification','error')),
  error_code   TEXT,
  failed_stage TEXT,
  http_status  INTEGER NOT NULL,
  latency_ms   INTEGER NOT NULL CHECK (latency_ms >= 0),
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log (created_at);
CREATE INDEX IF NOT EXISTS idx_audit_outcome ON audit_log (outcome, error_code);

CREATE TABLE IF NOT EXISTS audit_stage (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  audit_id    INTEGER NOT NULL REFERENCES audit_log(id) ON DELETE CASCADE,
  stage_order INTEGER NOT NULL CHECK (stage_order BETWEEN 1 AND 5),
  stage_name  TEXT NOT NULL CHECK (stage_name IN
                ('schema','intent_allowlist','record_id','role','clarity')),
  passed      INTEGER NOT NULL CHECK (passed IN (0,1)),
  reason      TEXT,
  UNIQUE (audit_id, stage_order)
);

CREATE TABLE IF NOT EXISTS tx_log (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id       TEXT NOT NULL REFERENCES audit_log(request_id),
  idempotency_key  TEXT NOT NULL UNIQUE,
  operation        TEXT NOT NULL CHECK (operation IN ('register','revoke')),
  record_key       TEXT NOT NULL,
  tx_hash          TEXT,
  status           TEXT NOT NULL CHECK (status IN ('pending','confirmed','reverted','failed')),
  error_code       TEXT,
  block_number     INTEGER,
  submitted_at     TEXT NOT NULL,
  confirmed_at     TEXT,
  confirmation_ms  INTEGER CHECK (confirmation_ms IS NULL OR confirmation_ms >= 0)
);
CREATE INDEX IF NOT EXISTS idx_tx_status ON tx_log (status);

-- Only needed if session-based admin login is chosen (open decision D-13)
CREATE TABLE IF NOT EXISTS admin_session (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash  TEXT NOT NULL UNIQUE,
  created_at  TEXT NOT NULL,
  expires_at  TEXT NOT NULL,
  revoked     INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0,1))
);

-- ===== Evaluation tables =====

CREATE TABLE IF NOT EXISTS dataset_version (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL UNIQUE,
  description TEXT,
  split_seed  INTEGER,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS certificate_fixture (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  dataset_version_id INTEGER NOT NULL REFERENCES dataset_version(id),
  record_id          TEXT NOT NULL,
  variant            TEXT NOT NULL CHECK (variant IN
                       ('original','modified','revoked','unregistered')),
  file_name          TEXT NOT NULL,
  sha256             TEXT NOT NULL CHECK (length(sha256) = 64),
  expected_state     TEXT NOT NULL CHECK (expected_state IN
                       ('MATCH','MISMATCH','NOT_FOUND','REVOKED')),
  UNIQUE (dataset_version_id, record_id, variant)
);

CREATE TABLE IF NOT EXISTS query_case (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  dataset_version_id INTEGER NOT NULL REFERENCES dataset_version(id),
  case_code          TEXT NOT NULL,
  split              TEXT NOT NULL CHECK (split IN ('dev','test')),
  category           TEXT NOT NULL CHECK (category IN
                       ('valid','unknown_id','revoked','ambiguous',
                        'malformed_output','unauthorized','injection','out_of_scope')),
  tier               TEXT NOT NULL CHECK (tier IN ('templated','paraphrased','informal')),
  query_text         TEXT NOT NULL,
  gold_json          TEXT NOT NULL CHECK (json_valid(gold_json)),
  expected_outcome   TEXT NOT NULL CHECK (expected_outcome IN
                       ('ok','rejected','clarification')),
  actor_role         TEXT NOT NULL DEFAULT 'anonymous' CHECK (actor_role IN ('anonymous','admin')),
  attack_type        TEXT,
  forced_output      TEXT,
  UNIQUE (dataset_version_id, case_code)
);
CREATE INDEX IF NOT EXISTS idx_case_split ON query_case (dataset_version_id, split, category);

CREATE TABLE IF NOT EXISTS eval_run (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  dataset_version_id INTEGER NOT NULL REFERENCES dataset_version(id),
  parser_type        TEXT NOT NULL CHECK (parser_type IN ('slm','rules')),
  model_name         TEXT,
  model_params       TEXT CHECK (model_params IS NULL OR json_valid(model_params)),
  constrained_decoding INTEGER NOT NULL DEFAULT 0 CHECK (constrained_decoding IN (0,1)),
  split              TEXT NOT NULL CHECK (split IN ('dev','test')),
  seed               INTEGER,
  started_at         TEXT NOT NULL,
  finished_at        TEXT,
  notes              TEXT
);

CREATE TABLE IF NOT EXISTS eval_case_result (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id          INTEGER NOT NULL REFERENCES eval_run(id) ON DELETE CASCADE,
  case_id         INTEGER NOT NULL REFERENCES query_case(id),
  raw_output      TEXT,
  predicted_json  TEXT CHECK (predicted_json IS NULL OR json_valid(predicted_json)),
  schema_valid    INTEGER NOT NULL CHECK (schema_valid IN (0,1)),
  intent_correct  INTEGER CHECK (intent_correct IN (0,1)),
  id_correct      INTEGER CHECK (id_correct IN (0,1)),
  exact_match     INTEGER CHECK (exact_match IN (0,1)),
  final_outcome   TEXT NOT NULL CHECK (final_outcome IN ('ok','rejected','clarification','error')),
  blocked_stage   TEXT,
  security_pass   INTEGER CHECK (security_pass IN (0,1)),
  latency_ms      INTEGER CHECK (latency_ms >= 0),
  UNIQUE (run_id, case_id)
);
CREATE INDEX IF NOT EXISTS idx_result_run ON eval_case_result (run_id);

CREATE TABLE IF NOT EXISTS eval_metric (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id       INTEGER NOT NULL REFERENCES eval_run(id) ON DELETE CASCADE,
  metric_name  TEXT NOT NULL,
  group_key    TEXT NOT NULL DEFAULT 'all',
  value        REAL NOT NULL,
  ci_low       REAL,
  ci_high      REAL,
  n            INTEGER NOT NULL,
  UNIQUE (run_id, metric_name, group_key)
);

-- Record this migration
INSERT INTO schema_migrations (version) VALUES (1);


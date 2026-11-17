/**
 * DRV API Client
 * Interfaces with FastAPI endpoints: /api/verify, /api/query, /health
 */

const API_BASE = window.location.origin;

export async function verifyFile(file, recordId) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('record_id', recordId);

  const response = await fetch(`${API_BASE}/api/verify`, {
    method: 'POST',
    body: formData,
  });

  const data = await response.json();
  return {
    ok: response.ok,
    status: response.status,
    data,
  };
}

export async function queryRecords(text, parser = 'rules') {
  const response = await fetch(`${API_BASE}/api/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      text,
      parser,
    }),
  });

  const data = await response.json();
  return {
    ok: response.ok,
    status: response.status,
    data,
  };
}

export async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE}/api/health`);
    return await response.json();
  } catch (err) {
    return { status: 'offline', error: err.message };
  }
}

export async function getStatutoryTests() {
  const response = await fetch(`${API_BASE}/api/results/tests`);
  return await response.json();
}

export async function getComparisonMetrics(split = 'test') {
  const response = await fetch(`${API_BASE}/api/results/comparison?split=${encodeURIComponent(split)}`);
  return await response.json();
}

export async function runBenchmark(parserType = 'rules', split = 'test', constrained = false) {
  const response = await fetch(`${API_BASE}/api/results/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      parser_type: parserType,
      split: split,
      constrained_decoding: constrained,
    }),
  });
  return await response.json();
}

/**
 * Admin: Register a certificate (file upload path).
 * @param {FormData} formData – must contain record_id, doc_type, file (PDF)
 * @param {string} csrfToken  – CSRF token from login response
 */
export async function registerRecord(formData, csrfToken) {
  const response = await fetch(`${API_BASE}/api/admin/register`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'X-CSRF-Token': csrfToken || '',
    },
    // Do NOT set Content-Type — browser sets multipart boundary automatically
    body: formData,
  });
  const data = await response.json();
  return { ok: response.ok, status: response.status, data };
}

/**
 * Admin: Login and obtain a session + CSRF token.
 * @param {string} username
 * @param {string} password
 */
export async function adminLogin(username, password) {
  const response = await fetch(`${API_BASE}/api/admin/login`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const data = await response.json();
  return { ok: response.ok, status: response.status, data };
}

/**
 * Admin: Logout and clear session.
 */
export async function adminLogout() {
  const response = await fetch(`${API_BASE}/api/admin/logout`, {
    method: 'POST',
    credentials: 'include',
  });
  return { ok: response.ok };
}

/**
 * Admin: Revoke a record on-chain.
 * @param {string} recordId
 * @param {number} reasonCode – 1-4
 * @param {string} csrfToken
 */
export async function revokeRecord(recordId, reasonCode, csrfToken) {
  const response = await fetch(`${API_BASE}/api/admin/revoke`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken || '',
    },
    body: JSON.stringify({ record_id: recordId, reason: reasonCode }),
  });
  const data = await response.json();
  return { ok: response.ok, status: response.status, data };
}

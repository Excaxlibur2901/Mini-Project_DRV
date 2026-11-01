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

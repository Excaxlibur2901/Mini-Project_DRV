/**
 * DRV Evaluation & Benchmark Results Page Logic
 * Conforms to API.md §4.9 (Live reporting without invented numbers)
 */

import { getStatutoryTests, getComparisonMetrics, runBenchmark } from './api.js';

document.addEventListener('DOMContentLoaded', () => {
  initResultsPage();
});

async function initResultsPage() {
  await loadStatutoryTests();
  await loadComparisonTable();
  setupRunControls();
}

/**
 * Fetch and render the TC-01..TC-10 statutory verification test matrix
 */
async function loadStatutoryTests() {
  const tbody = document.getElementById('testsTableBody');
  if (!tbody) return;

  try {
    const res = await getStatutoryTests();
    if (res && res.status === 'ok' && res.result && res.result.tests) {
      tbody.innerHTML = '';
      res.result.tests.forEach((t) => {
        const tr = document.createElement('tr');
        const badgeClass = t.outcome === 'pass' ? 'badge-verified' : 'badge-mismatch';
        const badgeLabel = t.outcome === 'pass' ? 'Passed' : (t.outcome === 'fail' ? 'Failed' : 'Not Run');

        tr.innerHTML = `
          <td class="font-mono" style="font-weight: 600;">${t.id}</td>
          <td>${getTestCategory(t.id)}</td>
          <td>${t.scenario}</td>
          <td class="font-mono" style="font-size: 12px;">${t.expected}</td>
          <td><span class="badge ${badgeClass}">${badgeLabel}</span></td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {
    console.error('Failed to load statutory test outcomes:', err);
  }
}

function getTestCategory(id) {
  if (id === 'TC-01' || id === 'TC-02' || id === 'TC-03' || id === 'TC-04') return 'Verification';
  if (id === 'TC-05') return 'Privilege Auth';
  if (id === 'TC-06') return 'Malformed JSON';
  if (id === 'TC-07') return 'Ambiguity';
  if (id === 'TC-08') return 'Resilience';
  if (id === 'TC-09') return 'Security';
  if (id === 'TC-10') return 'Scope';
  return 'General';
}

/**
 * Fetch and render empirical comparison metrics across benchmark runs
 */
async function loadComparisonTable() {
  const container = document.getElementById('comparisonContainer');
  if (!container) return;

  try {
    const res = await getComparisonMetrics('test');
    if (res && res.status === 'ok' && res.result && res.result.runs && res.result.runs.length > 0) {
      renderComparisonRuns(container, res.result.runs);
    } else {
      container.innerHTML = `
        <div style="background-color: var(--surface-2); border: 1px dashed var(--border); border-radius: 8px; padding: 24px; text-align: center; color: var(--text-muted);">
          <span class="material-symbols-outlined" style="font-size: 36px; margin-bottom: 8px; color: var(--accent);">science</span>
          <p style="font-size: 15px; font-weight: 600; color: var(--ink); margin-bottom: 4px;">Awaiting Test Set Evaluation Run</p>
          <p style="font-size: 13px; max-width: 500px; margin: 0 auto 16px;">
            In accordance with statutory audit rules, benchmark metrics remain null until empirical evaluation executes against the frozen dataset.
          </p>
          <button id="runBaselineBtn" class="btn btn-primary" style="font-size: 13px; padding: 8px 16px;">
            Execute Rules Baseline Benchmark (80 Cases)
          </button>
        </div>
      `;
      const btn = document.getElementById('runBaselineBtn');
      if (btn) {
        btn.addEventListener('click', executeRulesBenchmark);
      }
    }
  } catch (err) {
    console.error('Failed to load comparison runs:', err);
  }
}

function renderComparisonRuns(container, runs) {
  let tableHtml = `
    <div style="overflow-x: auto; margin-top: 12px;">
      <table class="results-table">
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Parser Condition</th>
            <th>Model</th>
            <th>Constrained</th>
            <th>Intent Acc (95% CI)</th>
            <th>Record ID Acc</th>
            <th>Exact Match</th>
            <th>Security Refusal</th>
            <th>Mean Latency</th>
          </tr>
        </thead>
        <tbody>
  `;

  runs.forEach((r) => {
    const metricsMap = {};
    r.metrics.forEach((m) => {
      metricsMap[m.name + '_' + m.group] = m;
    });

    const intentAcc = metricsMap['intent_accuracy_all'];
    const idAcc = metricsMap['id_accuracy_all'];
    const exactMatch = metricsMap['exact_match_all'];
    const secPass = metricsMap['security_pass_rate_injection'] || metricsMap['accuracy_injection'];
    const meanLat = metricsMap['mean_latency_ms_all'];

    const formatCI = (m) => {
      if (!m) return '—';
      const pct = (m.value * 100).toFixed(1) + '%';
      if (m.ci_low !== null && m.ci_high !== null) {
        return `${pct} <span style="font-size: 11px; color: var(--text-muted);">[${(m.ci_low * 100).toFixed(1)}–${(m.ci_high * 100).toFixed(1)}%]</span>`;
      }
      return pct;
    };

    const parserLabel = r.parser === 'rules'
      ? '<span class="badge badge-clarify">Rules Baseline</span>'
      : `<span class="badge badge-verified">SLM (${r.model})</span>`;

    tableHtml += `
      <tr>
        <td class="font-mono">#${r.run_id}</td>
        <td>${parserLabel}</td>
        <td class="font-mono" style="font-size: 12px;">${r.model || 'none (regex)'}</td>
        <td>${r.constrained_decoding ? '<span class="badge badge-verified">Yes</span>' : '<span class="badge badge-clarify">No</span>'}</td>
        <td>${formatCI(intentAcc)}</td>
        <td>${idAcc ? (idAcc.value * 100).toFixed(1) + '%' : '—'}</td>
        <td>${exactMatch ? (exactMatch.value * 100).toFixed(1) + '%' : '—'}</td>
        <td>${secPass ? (secPass.value * 100).toFixed(1) + '%' : '—'}</td>
        <td class="font-mono">${meanLat ? meanLat.value + ' ms' : '—'}</td>
      </tr>
    `;
  });

  tableHtml += `
        </tbody>
      </table>
    </div>
  `;

  container.innerHTML = tableHtml;
}

function setupRunControls() {
  const triggerBtn = document.getElementById('manualRunTriggerBtn');
  if (triggerBtn) {
    triggerBtn.addEventListener('click', executeRulesBenchmark);
  }
}

async function executeRulesBenchmark() {
  const statusEl = document.getElementById('runStatusMessage');
  if (statusEl) {
    statusEl.textContent = 'Executing benchmark across 80 held-out test cases...';
    statusEl.style.display = 'block';
  }

  try {
    const res = await runBenchmark('rules', 'test', false);
    if (res && res.status === 'ok') {
      if (statusEl) {
        statusEl.textContent = `Completed Run #${res.result.run_id}: Intent Acc = ${(res.result.summary_metrics.intent_accuracy * 100).toFixed(1)}%, Latency = ${res.result.summary_metrics.mean_latency_ms} ms.`;
      }
      await loadComparisonTable();
    } else {
      if (statusEl) statusEl.textContent = 'Benchmark execution failed.';
    }
  } catch (err) {
    if (statusEl) statusEl.textContent = 'Execution error: ' + err.message;
  }
}


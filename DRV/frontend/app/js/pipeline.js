/**
 * 5-Stage Validation Pipeline Visual Stepper
 * Renders outcomes from backend `handling.stages`
 */

export const STAGE_CONFIG = [
  { order: 1, name: 'schema', label: 'Schema' },
  { order: 2, name: 'intent_allowlist', label: 'Intent' },
  { order: 3, name: 'record_id', label: 'Record ID' },
  { order: 4, name: 'role', label: 'Role Auth' },
  { order: 5, name: 'clarity', label: 'Clarity' },
];

/**
 * Render horizontal 5-stage stepper inside a container element.
 * @param {HTMLElement} containerEl
 * @param {Array} stages - Array of StageOutcome objects from response.handling.stages
 * @param {Boolean} animate - Whether to animate stage reveals
 */
export function renderPipelineStepper(containerEl, stages = [], animate = false) {
  if (!containerEl) return;

  const stageMap = {};
  stages.forEach(s => {
    stageMap[s.name] = s;
  });

  let html = '<div class="stepper-container">';

  STAGE_CONFIG.forEach(cfg => {
    const stageData = stageMap[cfg.name];
    let statusClass = 'idle';
    let icon = 'horizontal_rule';
    let statusLabel = 'Pending';

    if (stageData) {
      if (stageData.passed) {
        statusClass = 'passed';
        icon = 'check_circle';
        statusLabel = 'Passed';
      } else {
        statusClass = 'failed';
        icon = 'cancel';
        statusLabel = 'Failed';
      }
    }

    html += `
      <div class="step-node ${statusClass}" title="${stageData?.reason || statusLabel}">
        <span class="material-symbols-outlined" style="font-size: 16px;">${icon}</span>
        <span style="font-weight: 600; font-size: 11px;">${cfg.label}</span>
        <span style="font-size: 10px; opacity: 0.85; text-transform: uppercase;">${statusLabel}</span>
      </div>
    `;
  });

  html += '</div>';
  containerEl.innerHTML = html;
}


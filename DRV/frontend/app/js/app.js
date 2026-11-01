/**
 * Global App Script
 * Handles theme toggling, active links, toasts, and helpers.
 */

// Theme Management
export function initTheme() {
  const savedTheme = localStorage.getItem('drv_theme');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  
  if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
    document.documentElement.setAttribute('data-theme', 'dark');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }

  const toggleBtns = document.querySelectorAll('.theme-toggle-btn');
  toggleBtns.forEach(btn => {
    btn.addEventListener('click', toggleTheme);
    updateThemeIcon(btn);
  });
}

export function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  
  if (next === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
    localStorage.setItem('drv_theme', 'dark');
  } else {
    document.documentElement.removeAttribute('data-theme');
    localStorage.setItem('drv_theme', 'light');
  }

  document.querySelectorAll('.theme-toggle-btn').forEach(updateThemeIcon);
}

function updateThemeIcon(btn) {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const iconSpan = btn.querySelector('.material-symbols-outlined') || btn;
  iconSpan.textContent = isDark ? 'dark_mode' : 'light_mode';
}

// Copy to Clipboard
export async function copyToClipboard(text, triggerBtn, successText = 'Copied') {
  try {
    await navigator.clipboard.writeText(text);
    if (triggerBtn) {
      const origText = triggerBtn.innerText;
      triggerBtn.innerText = successText;
      setTimeout(() => {
        triggerBtn.innerText = origText;
      }, 1500);
    }
  } catch (e) {
    console.error('Failed to copy', e);
  }
}

// Staggered Reveal Animation on load
export function initReveals() {
  const reveals = document.querySelectorAll('.reveal');
  reveals.forEach((el, i) => {
    el.style.transitionDelay = `${i * 50}ms`;
    el.classList.add('in');
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initReveals();
});


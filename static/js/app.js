/**
 * INDOGIST — Interactive Client Engine (Precision Studio)
 * Includes Theme Switcher, Tab Controls, Telemetry Counters, Entity Chip Renderer,
 * HTMX Event Hooks, and Copy/Download Utilities
 */

// ——————————————————————————————————————————————————
// 1. Theme Switcher Module (Dark / Light Mode)
// ——————————————————————————————————————————————————
function initTheme() {
  const savedTheme = localStorage.getItem('indogist_theme');
  const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initialTheme = savedTheme || (systemPrefersDark ? 'dark' : 'light');
  
  applyTheme(initialTheme);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.body.setAttribute('data-theme', theme);
  const appEl = document.getElementById('app');
  if (appEl) appEl.setAttribute('data-theme', theme);

  localStorage.setItem('indogist_theme', theme);
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme);
}

// ——————————————————————————————————————————————————
// 2. Real-Time Telemetry & Word Count
// ——————————————————————————————————————————————————
function countWords(str) {
  return str.trim() ? str.trim().split(/\s+/).length : 0;
}

function updateTelemetry(val) {
  const text = typeof val === 'string' ? val : (val && val.value ? val.value : '');
  const words = countWords(text);
  
  const wordCountEl = document.getElementById('wordCount');
  if (wordCountEl) {
    wordCountEl.textContent = words;
  }
}

function updateWordCount(val) {
  updateTelemetry(val);
}

// ——————————————————————————————————————————————————
// 3. Tab Group Controller
// ——————————————————————————————————————————————————
function initTabs() {
  document.querySelectorAll('.tabs').forEach(function (tabGroup) {
    var tabs = tabGroup.querySelectorAll('.tab');
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        tabs.forEach(function (t) { t.classList.remove('active'); });
        tab.classList.add('active');
        var container = tabGroup.parentElement;
        if (container) {
          container.querySelectorAll('.tab-pane').forEach(function (p) { p.classList.remove('active'); });
          var targetPane = container.querySelector('.tab-pane[data-pane="' + tab.dataset.tab + '"]');
          if (targetPane) targetPane.classList.add('active');
        }
      });
    });
  });
}

// ——————————————————————————————————————————————————
// 4. Entity Chip Renderer
// ——————————————————————————————————————————————————
function renderEntities(target, list) {
  if (!target) return;
  target.innerHTML = '';
  if (!list || !list.length) {
    var none = document.createElement('span');
    none.className = 'output-placeholder';
    none.textContent = 'No named entities detected in this text.';
    target.appendChild(none);
    return;
  }
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  list.forEach(function (ent, i) {
    var chip = document.createElement('span');
    chip.className = 'entity-chip';
    chip.innerHTML = '<span>' + (ent.text || ent.name) + '</span><span class="e-type">' + (ent.type || ent.label) + '</span><span class="e-score">' + (ent.score || ent.confidence_percent || 95) + '%</span>';
    target.appendChild(chip);
    setTimeout(function () { chip.classList.add('show'); }, reduceMotion ? 0 : i * 70);
  });
}

// ——————————————————————————————————————————————————
// 5. Clipboard & Download Utilities
// ——————————————————————————————————————————————————
function copySummaryOutput(elementId = 'outputContent', btnElement = null) {
  const output = document.getElementById(elementId);
  if (!output) return;
  const textToCopy = output.value || output.innerText;
  if (!textToCopy.trim()) return;

  if (navigator.clipboard) {
    navigator.clipboard.writeText(textToCopy).then(() => {
      if (btnElement) {
        const originalText = btnElement.textContent;
        btnElement.textContent = 'Copied!';
        setTimeout(() => { btnElement.textContent = originalText; }, 2000);
      }
    });
  }
}

function downloadSummaryOutput(elementId = 'outputContent', filenamePrefix = 'indogist-summary') {
  const output = document.getElementById(elementId);
  if (!output) return;

  const textToDownload = output.value || output.innerText;
  if (!textToDownload.trim()) return;

  const blob = new Blob([textToDownload], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${filenamePrefix}-${Date.now()}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function animateNumber(el, to, suffix) {
  if (!el) return;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduceMotion) { el.textContent = to + (suffix || ''); return; }
  var from = 0, duration = 550, start = null;
  function step(ts) {
    if (!start) start = ts;
    var progress = Math.min((ts - start) / duration, 1);
    var val = Math.round(from + (to - from) * progress);
    el.textContent = val + (suffix || '');
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ——————————————————————————————————————————————————
// 6. DOM Content Loaded Initialization & HTMX Hooks
// ——————————————————————————————————————————————————
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initTabs();

  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', toggleTheme);
  }

  const rawText = document.getElementById('rawText');
  if (rawText) {
    rawText.addEventListener('input', () => updateTelemetry(rawText.value));
    updateTelemetry(rawText.value);
  }

  const copyBtn = document.getElementById('copyBtn');
  if (copyBtn) {
    copyBtn.addEventListener('click', function () {
      copySummaryOutput('outputArea', copyBtn);
    });
  }

  const saveBtn = document.getElementById('saveBtn');
  if (saveBtn) {
    saveBtn.addEventListener('click', function () {
      downloadSummaryOutput('outputArea');
    });
  }
});

document.addEventListener('htmx:afterSwap', (e) => {
  initTabs();
  const rawText = document.getElementById('rawText');
  if (rawText) {
    updateTelemetry(rawText.value);
  }
});

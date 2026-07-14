/**
 * INDOGIST — PRECISION STUDIO ENGINE (HIGH POLISH)
 * Custom Select Popups, Bi-directional Modal Fullscreen Editor,
 * Ambient Slider Progress Fillers, and Keyboard Shortcuts
 */

// ——————————————————————————————————————————————————
// 1. Toast Notification Manager
// ——————————————————————————————————————————————————
function showToast(message, type = 'info', duration = 4000) {
  let toastContainer = document.querySelector('.toast-container');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'status');
  toast.setAttribute('aria-live', 'polite');

  const icons = {
    success: '✓ ',
    info: 'ℹ ',
    warning: '⚠ ',
    error: '✕ '
  };

  toast.innerHTML = `
    <span><strong>${icons[type] || ''}</strong>${message}</span>
    <button class="toast-close" aria-label="Close">&times;</button>
  `;

  toast.querySelector('.toast-close').addEventListener('click', () => {
    toast.remove();
  });

  toastContainer.appendChild(toast);

  if (duration > 0) {
    setTimeout(() => {
      if (toast.parentNode) toast.remove();
    }, duration);
  }
}

// ——————————————————————————————————————————————————
// 2. Custom Non-Native Select Dropdowns Popup Module
// ——————————————————————————————————————————————————
function initCustomSelects() {
  document.querySelectorAll('select.field-select').forEach((select) => {
    if (select.dataset.customized === 'true') return;
    select.dataset.customized = 'true';
    select.style.display = 'none';

    const wrapper = document.createElement('div');
    wrapper.className = 'custom-select';

    const selectedOption = select.options[select.selectedIndex] || select.options[0];
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'custom-select-trigger';
    trigger.innerHTML = `
      <span class="custom-select-val">${selectedOption ? selectedOption.text : ''}</span>
      <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
    `;

    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'custom-select-options';

    Array.from(select.options).forEach((opt, idx) => {
      const optionEl = document.createElement('div');
      optionEl.className = 'custom-select-option' + (idx === select.selectedIndex ? ' selected' : '');
      optionEl.textContent = opt.text;
      optionEl.dataset.value = opt.value;

      optionEl.addEventListener('click', () => {
        select.selectedIndex = idx;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        trigger.querySelector('.custom-select-val').textContent = opt.text;
        optionsContainer.querySelectorAll('.custom-select-option').forEach(el => el.classList.remove('selected'));
        optionEl.classList.add('selected');
        wrapper.classList.remove('open');
      });

      optionsContainer.appendChild(optionEl);
    });

    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      document.querySelectorAll('.custom-select').forEach(cs => {
        if (cs !== wrapper) cs.classList.remove('open');
      });
      wrapper.classList.toggle('open');
    });

    wrapper.appendChild(trigger);
    wrapper.appendChild(optionsContainer);
    select.parentNode.insertBefore(wrapper, select.nextSibling);
  });

  document.addEventListener('click', () => {
    document.querySelectorAll('.custom-select').forEach(cs => cs.classList.remove('open'));
  });
}

// ——————————————————————————————————————————————————
// 3. Theme Switcher Module
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
// 4. Editor Telemetry & Modal Fullscreen Editor
// ——————————————————————————————————————————————————
function countWords(str) {
  return str && str.trim() ? str.trim().split(/\s+/).length : 0;
}

function updateEditorTelemetry() {
  const rawText = document.getElementById('rawText');
  const modalRawText = document.getElementById('modalRawText');
  const wordCountEl = document.getElementById('wordCount');
  const modalWordCountEl = document.getElementById('modalWordCount');
  const charCountEl = document.getElementById('charCount');
  const tokenCountEl = document.getElementById('tokenCount');
  const limitMsgEl = document.getElementById('limitMessage');
  const generateBtn = document.getElementById('generateBtn');

  if (!rawText) return;

  const val = rawText.value;
  const words = countWords(val);
  const chars = val.length;
  const estTokens = Math.round(words * 1.3);

  if (wordCountEl) wordCountEl.textContent = words;
  if (modalWordCountEl) modalWordCountEl.textContent = words;
  if (charCountEl) charCountEl.textContent = chars.toLocaleString();
  if (tokenCountEl) tokenCountEl.textContent = estTokens.toLocaleString();
  if (modalRawText && modalRawText.value !== val) modalRawText.value = val;

  const maxWords = 8000;
  if (limitMsgEl) {
    if (words > maxWords) {
      limitMsgEl.innerHTML = `<span class="limit-danger">Limit exceeded (${words}/${maxWords} words). Shorten text.</span>`;
      if (generateBtn) generateBtn.disabled = true;
    } else if (words > maxWords * 0.85) {
      limitMsgEl.innerHTML = `<span class="limit-warning">${words}/${maxWords} words</span>`;
      if (generateBtn) generateBtn.disabled = false;
    } else {
      limitMsgEl.innerHTML = `Limit: ${maxWords.toLocaleString()} words`;
      if (generateBtn) generateBtn.disabled = false;
    }
  }
}

function openFullscreenEditor() {
  const modal = document.getElementById('editorModal');
  const rawText = document.getElementById('rawText');
  const modalRawText = document.getElementById('modalRawText');
  if (modal && rawText && modalRawText) {
    modalRawText.value = rawText.value;
    modal.classList.add('active');
    modalRawText.focus();
  }
}

function closeFullscreenEditor() {
  const modal = document.getElementById('editorModal');
  const rawText = document.getElementById('rawText');
  const modalRawText = document.getElementById('modalRawText');
  if (modal && rawText && modalRawText) {
    rawText.value = modalRawText.value;
    updateEditorTelemetry();
    modal.classList.remove('active');
  }
}

// ——————————————————————————————————————————————————
// 5. Custom Range Slider Ambient Track Filler
// ——————————————————————————————————————————————————
function updateSliderProgress(slider) {
  if (!slider) return;
  const min = parseFloat(slider.min) || 0;
  const max = parseFloat(slider.max) || 100;
  const val = parseFloat(slider.value) || 0;
  const pct = ((val - min) / (max - min)) * 100;
  slider.style.setProperty('--progress', pct + '%');
  const ratioDisplay = document.getElementById('ratioDisplay');
  if (ratioDisplay) ratioDisplay.innerText = Math.round(val * 100) + '%';
}

function initSliders() {
  document.querySelectorAll('input[type="range"].field-range').forEach(slider => {
    updateSliderProgress(slider);
    slider.addEventListener('input', () => updateSliderProgress(slider));
  });
}

// ——————————————————————————————————————————————————
// 6. Tab & Entity Helpers
// ——————————————————————————————————————————————————
function initTabs() {
  document.querySelectorAll('.tabs').forEach(function (tabGroup) {
    var tabs = tabGroup.querySelectorAll('.tab');
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        tabs.forEach(function (t) { t.classList.remove('active'); });
        tab.classList.add('active');
        var container = tabGroup.parentElement;
        container.querySelectorAll('.tab-pane').forEach(function (p) { p.classList.remove('active'); });
        var targetPane = container.querySelector('.tab-pane[data-pane="' + tab.dataset.tab + '"]');
        if (targetPane) targetPane.classList.add('active');
      });
    });
  });
}

function copySummaryOutput(elementId = 'outputArea', btnElement = null) {
  const output = document.getElementById(elementId);
  if (!output) return;
  const textToCopy = output.value || output.innerText;
  if (!textToCopy.trim()) {
    showToast('Nothing to copy', 'warning');
    return;
  }

  if (navigator.clipboard) {
    navigator.clipboard.writeText(textToCopy).then(() => {
      showToast('Summary copied to clipboard!', 'success');
      if (btnElement) {
        const origText = btnElement.innerText;
        btnElement.innerText = 'Copied ✓';
        setTimeout(() => { btnElement.innerText = origText; }, 2000);
      }
    }).catch(() => {
      showToast('Failed to copy text', 'error');
    });
  }
}

function saveSummaryOutput(elementId = 'outputArea', filenamePrefix = 'indogist-summary') {
  const output = document.getElementById(elementId);
  if (!output) return;
  const textToDownload = output.value || output.innerText;
  if (!textToDownload.trim()) {
    showToast('No output content to download', 'warning');
    return;
  }

  const blob = new Blob([textToDownload], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${filenamePrefix}-${Date.now()}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('TXT export started', 'success');
}

function initSearchShortcuts() {
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
      const searchInput = document.querySelector('.search-field input');
      if (searchInput) {
        e.preventDefault();
        searchInput.focus();
        showToast('Search focused', 'info', 1500);
      }
    }
    if (e.key === 'Escape') {
      closeFullscreenEditor();
    }
  });
}

// ——————————————————————————————————————————————————
// 7. Initialization Hooks
// ——————————————————————————————————————————————————
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initTabs();
  initCustomSelects();
  initSliders();
  initSearchShortcuts();

  const themeToggleBtn = document.getElementById('themeToggle');
  if (themeToggleBtn) themeToggleBtn.addEventListener('click', toggleTheme);

  const rawText = document.getElementById('rawText');
  if (rawText) {
    rawText.addEventListener('input', updateEditorTelemetry);
    updateEditorTelemetry();
  }

  const modalRawText = document.getElementById('modalRawText');
  if (modalRawText) {
    modalRawText.addEventListener('input', () => {
      if (rawText) rawText.value = modalRawText.value;
      updateEditorTelemetry();
    });
  }
});

document.addEventListener('htmx:afterSwap', () => {
  initTabs();
  initCustomSelects();
  initSliders();
  updateEditorTelemetry();
});

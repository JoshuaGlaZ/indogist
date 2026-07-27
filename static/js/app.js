/* ==========================================================================
   INDOGIST — PRECISION STUDIO JAVASCRIPT APP ENGINE
   Custom Select Dropdowns, Modal Fullscreen Editor, Toast Notifications,
   Range Slider Track Fills, Keyboard Shortcuts & Interactive NER/POS Highlights
   ========================================================================== */

window.OUTPUT_TEXT_CACHE = {};

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initTabs();
  initCustomSelects();
  initRangeSliders();
  initEditorTelemetry();
  initKeyboardShortcuts();
  initCSRF();
  initHamburger();
});

// Theme Management
function getPreferredTheme() {
  const saved = localStorage.getItem('theme');
  if (saved) return saved;
  return (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
}

function applyTheme(theme, saveUserChoice = true) {
  document.documentElement.setAttribute('data-theme', theme);
  document.body.setAttribute('data-theme', theme);
  const appEl = document.getElementById('app');
  if (appEl) appEl.setAttribute('data-theme', theme);
  if (saveUserChoice) {
    localStorage.setItem('theme', theme);
  }
}

function initThemeToggle() {
  const toggleBtn = document.querySelector('.theme-toggle');
  if (!toggleBtn) return;

  const currentTheme = getPreferredTheme();
  applyTheme(currentTheme, false);

  toggleBtn.addEventListener('click', () => {
    const activeTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const nextTheme = activeTheme === 'dark' ? 'light' : 'dark';
    applyTheme(nextTheme, true);
  });

  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!localStorage.getItem('theme')) {
        applyTheme(e.matches ? 'dark' : 'light', false);
      }
    });
  }
}

// Tab Switching
function initTabs() {
  document.querySelectorAll('.tabs').forEach(tabGroup => {
    tabGroup.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const target = tab.dataset.tab;
        tabGroup.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        const cardBody = tabGroup.closest('.card-body');
        if (cardBody) {
          cardBody.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('active');
            if (pane.dataset.pane === target) pane.classList.add('active');
          });
        }
      });
    });
  });
}

// Custom Select Popup Component (Replaces Default Select Menu List)
function initCustomSelects() {
  document.querySelectorAll('select.field-select').forEach(select => {
    if (select.dataset.customInitialized) return;
    select.dataset.customInitialized = 'true';
    select.style.display = 'none';

    const wrapper = document.createElement('div');
    wrapper.className = 'custom-select';

    const trigger = document.createElement('div');
    trigger.className = 'custom-select-trigger';
    trigger.tabIndex = 0;

    const labelSpan = document.createElement('span');
    const selectedOption = select.options[select.selectedIndex];
    labelSpan.innerText = selectedOption ? selectedOption.text : t('Select option');

    const chevron = document.createElement('span');
    chevron.className = 'chevron';
    chevron.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>`;

    trigger.appendChild(labelSpan);
    trigger.appendChild(chevron);
    wrapper.appendChild(trigger);

    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'custom-select-options';

    Array.from(select.options).forEach((opt, idx) => {
      const optEl = document.createElement('div');
      optEl.className = `custom-select-option ${idx === select.selectedIndex ? 'selected' : ''}`;
      optEl.tabIndex = 0;
      if (opt.disabled) optEl.style.opacity = '0.5';
      optEl.innerText = opt.text;

      optEl.addEventListener('click', (e) => {
        e.stopPropagation();
        if (opt.disabled) return;
        select.selectedIndex = idx;
        labelSpan.innerText = opt.text;
        optionsContainer.querySelectorAll('.custom-select-option').forEach(o => o.classList.remove('selected'));
        optEl.classList.add('selected');
        wrapper.classList.remove('open');
        select.dispatchEvent(new Event('change', { bubbles: true }));
      });
      optionsContainer.appendChild(optEl);
    });

    wrapper.appendChild(optionsContainer);
    select.parentNode.insertBefore(wrapper, select);

    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      document.querySelectorAll('.custom-select').forEach(cs => {
        if (cs !== wrapper) cs.classList.remove('open');
      });
      wrapper.classList.toggle('open');
    });

    trigger.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        wrapper.classList.toggle('open');
      }
      if (e.key === 'Escape') {
        wrapper.classList.remove('open');
        trigger.focus();
      }
    });

    optionsContainer.addEventListener('keydown', (e) => {
      const options = Array.from(optionsContainer.querySelectorAll('.custom-select-option'));
      const current = document.activeElement;
      const idx = options.indexOf(current);

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = options[idx + 1] || options[0];
        next.focus();
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = options[idx - 1] || options[options.length - 1];
        prev.focus();
      }
      if (e.key === 'Escape') {
        wrapper.classList.remove('open');
        trigger.focus();
      }
    });
  });

  document.addEventListener('click', () => {
    document.querySelectorAll('.custom-select').forEach(cs => cs.classList.remove('open'));
  });
}

// Custom Range Slider Fill Progress
function initRangeSliders() {
  document.querySelectorAll('input[type="range"].field-range').forEach(slider => {
    updateSliderProgress(slider);
    slider.addEventListener('input', () => updateSliderProgress(slider));
  });
}

function updateSliderProgress(slider) {
  const min = parseFloat(slider.min) || 0;
  const max = parseFloat(slider.max) || 1;
  const val = parseFloat(slider.value) || 0;
  const percentage = ((val - min) / (max - min)) * 100;
  slider.style.setProperty('--progress', `${percentage}%`);

  const displayEl = document.getElementById('ratioDisplay');
  if (displayEl) {
    displayEl.innerText = `${Math.round(val * 100)}%`;
  }
}

// Editor Telemetry & Word Counter
function initEditorTelemetry() {
  const rawText = document.getElementById('rawText');
  if (!rawText) return;

  const update = () => updateEditorTelemetry();
  rawText.addEventListener('input', update);
  rawText.addEventListener('change', update);
  updateEditorTelemetry();
}

// Client-Side i18n Helper
window.I18N_DICT = {
  id: {
    'Exceeds limit (Max 8,000 words)': 'Melebihi batas (Maks 8.000 kata)',
    'Approaching limit (Max 8,000 words)': 'Mendekati batas (Maks 8.000 kata)',
    'Limit: 8,000 words': 'Batas: 8.000 kata',
    'No summary text to copy.': 'Tidak ada teks ringkasan untuk disalin.',
    'Summary copied to clipboard!': 'Ringkasan berhasil disalin ke papan klip!',
    'Failed to copy text.': 'Gagal menyalin teks.',
    'No summary text to save.': 'Tidak ada teks ringkasan untuk disimpan.',
    'Summary downloaded as file.': 'Ringkasan diunduh sebagai file.',
    'No detected entities available for this summary.': 'Tidak ada entitas terdeteksi untuk ringkasan ini.',
    'No POS data available — Stanza tagger may not be loaded.': 'Tidak ada data POS — tagger Stanza mungkin belum dimuat.',
    'Select option': 'Pilih opsi'
  },
  en: {
    'Exceeds limit (Max 8,000 words)': 'Exceeds limit (Max 8,000 words)',
    'Approaching limit (Max 8,000 words)': 'Approaching limit (Max 8,000 words)',
    'Limit: 8,000 words': 'Limit: 8,000 words',
    'No summary text to copy.': 'No summary text to copy.',
    'Summary copied to clipboard!': 'Summary copied to clipboard!',
    'Failed to copy text.': 'Failed to copy text.',
    'No summary text to save.': 'No summary text to save.',
    'Summary downloaded as file.': 'Summary downloaded as file.',
    'No detected entities available for this summary.': 'No detected entities available for this summary.',
    'No POS data available — Stanza tagger may not be loaded.': 'No POS data available — Stanza tagger may not be loaded.',
    'Select option': 'Select option'
  }
};

function t(msg) {
  const lang = document.documentElement.lang || 'id';
  const dict = window.I18N_DICT[lang] || window.I18N_DICT['id'];
  return dict[msg] || msg;
}

function updateEditorTelemetry() {
  const rawText = document.getElementById('rawText');
  if (!rawText) return;
  const val = rawText.value || '';

  const words = val.trim() ? val.trim().split(/\s+/).length : 0;
  const chars = val.length;
  const tokens = Math.round(words * 1.3);

  const wordCount = document.getElementById('wordCount');
  const charCount = document.getElementById('charCount');
  const tokenCount = document.getElementById('tokenCount');
  const limitMsg = document.getElementById('limitMessage');

  const loc = document.documentElement.lang || 'id';
  if (wordCount) wordCount.innerText = words.toLocaleString(loc);
  if (charCount) charCount.innerText = chars.toLocaleString(loc);
  if (tokenCount) tokenCount.innerText = tokens.toLocaleString(loc);

  if (limitMsg) {
    if (words > 8000) {
      limitMsg.className = 'limit-danger';
      limitMsg.innerText = t('Exceeds limit (Max 8,000 words)');
    } else if (words > 6000) {
      limitMsg.className = 'limit-warning';
      limitMsg.innerText = t('Approaching limit (Max 8,000 words)');
    } else {
      limitMsg.className = '';
      limitMsg.innerText = t('Limit: 8,000 words');
    }
  }

  // Bi-directional sync with modal editor
  const modalText = document.getElementById('modalRawText');
  if (modalText && modalText.value !== val) {
    modalText.value = val;
    const modalWordCount = document.getElementById('modalWordCount');
    if (modalWordCount) modalWordCount.innerText = words.toLocaleString(loc);
  }
}

// Fullscreen Editor Modal
function openFullscreenEditor() {
  const modal = document.getElementById('editorModal');
  const rawText = document.getElementById('rawText');
  const modalText = document.getElementById('modalRawText');
  if (!modal) return;

  if (rawText && modalText) {
    modalText.value = rawText.value;
  }
  modal.classList.add('active');

  if (modalText) {
    modalText.focus();
    modalText.oninput = () => {
      if (rawText) {
        rawText.value = modalText.value;
        updateEditorTelemetry();
      }
    };
  }
}

function closeFullscreenEditor() {
  const modal = document.getElementById('editorModal');
  if (modal) modal.classList.remove('active');
}

// Toast Notification Manager
function showToast(message, type = 'info', duration = 3000) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${message}</span>
    <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-10px)';
    setTimeout(() => toast.remove(), 200);
  }, duration);
}

// Copy & Save Output Handlers
function copySummaryOutput(targetId, btnEl) {
  const textEl = document.getElementById(targetId);
  if (!textEl) return;
  const text = textEl.innerText.trim();
  if (!text || textEl.querySelector('.output-placeholder')) {
    showToast(t('No summary text to copy.'), 'error');
    return;
  }
  navigator.clipboard.writeText(text).then(() => {
    showToast(t('Summary copied to clipboard!'), 'success');
  }).catch(() => {
    showToast(t('Failed to copy text.'), 'error');
  });
}

function saveSummaryOutput(targetId) {
  const textEl = document.getElementById(targetId);
  if (!textEl) return;
  const text = textEl.innerText.trim();
  if (!text || textEl.querySelector('.output-placeholder')) {
    showToast(t('No summary text to save.'), 'error');
    return;
  }
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `indogist_summary_${Date.now()}.txt`;
  a.click();
  URL.revokeObjectURL(url);
  showToast(t('Summary downloaded as file.'), 'success');
}


// Interactive NER & POS Output View Mode Switcher
function switchOutputMode(btnEl, targetId, mode) {
  const targetEl = document.getElementById(targetId);
  if (!targetEl) return;

  // Toggle active button style
  const parent = btnEl.closest('.view-mode-toggle');
  if (parent) {
    parent.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
    btnEl.classList.add('active');
  }

  // Cache the plain text on first access
  if (!window.OUTPUT_TEXT_CACHE[targetId]) {
    window.OUTPUT_TEXT_CACHE[targetId] = (targetEl.innerText || targetEl.textContent || '').trim();
  }
  const plainText = window.OUTPUT_TEXT_CACHE[targetId];
  if (!plainText || targetEl.querySelector('.output-placeholder')) return;

  if (mode === 'plain') {
    targetEl.textContent = plainText;
    return;
  }

  if (mode === 'ner') {
    // Source entities from: 1) window.__nerEntities (set by HTMX), 2) entityWrap chips in DOM
    let entities = [];

    if (window.__nerEntities && Array.isArray(window.__nerEntities) && window.__nerEntities.length > 0) {
      entities = window.__nerEntities;
    } else {
      // Fallback: scrape from entity chips in the page
      const entityWrap = document.getElementById('entityWrap');
      if (entityWrap) {
        entityWrap.querySelectorAll('.entity-chip').forEach(chip => {
          const spans = chip.querySelectorAll('span');
          if (spans.length >= 2) {
            const textVal = spans[0].innerText.trim();
            const labelEl = chip.querySelector('.e-type');
            if (textVal && labelEl) {
              entities.push({ text: textVal, label: labelEl.innerText.trim() });
            }
          }
        });
      }
    }

    if (entities.length === 0) {
      showToast(t('No detected entities available for this summary.'), 'info');
      targetEl.textContent = plainText;
      return;
    }

    // Sort longest first to avoid partial matches overwriting longer entity names
    entities.sort((a, b) => b.text.length - a.text.length);

    // Deduplicate by text+label
    const seen = new Set();
    const uniqueEntities = entities.filter(e => {
      const key = e.text.toLowerCase() + '|' + e.label;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    let html = plainText;
    uniqueEntities.forEach(ent => {
      if (!ent.text) return;
      const typeLower = ent.label.toLowerCase();
      const markClass = ['per', 'loc', 'org'].includes(typeLower) ? typeLower : 'ent';
      // Use word boundary-safe matching (handles Indonesian multi-word entities)
      const escaped = ent.text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp('(' + escaped + ')', 'gi');
      html = html.replace(regex, '<span class="ner-mark ' + markClass + '">$1 <sup class="ner-tag">' + ent.label + '</sup></span>');
    });

    targetEl.innerHTML = html;
    return;
  }

  if (mode === 'pos') {
    const posData = window.__posData || [];
    if (!posData.length) {
      showToast(t('No POS data available — Stanza tagger may not be loaded.'), 'info');
      targetEl.textContent = plainText;
      return;
    }

    // Collect unique POS categories present in this summary
    const categories = new Set();
    posData.forEach(t => { if (t.pos) categories.add(t.pos); });

    // Initialize active filter set if not present
    if (!window.__posActiveFilters) {
      window.__posActiveFilters = new Set();
    }

    // Render: category chip bar + highlighted text
    renderPosOutput(targetEl, posData, categories);
    return;
  }
}

// POS color map — consistent, distinguishable, not too harsh
const POS_COLORS = {
  NOUN:  { bg: 'rgba(99,102,241,0.15)',  border: 'rgba(99,102,241,0.4)',  text: '#818cf8' },
  PROPN: { bg: 'rgba(244,114,182,0.15)', border: 'rgba(244,114,182,0.4)', text: '#f472b6' },
  VERB:  { bg: 'rgba(52,211,153,0.15)',  border: 'rgba(52,211,153,0.4)',  text: '#34d399' },
  ADJ:   { bg: 'rgba(251,191,36,0.15)',  border: 'rgba(251,191,36,0.4)',  text: '#fbbf24' },
  ADV:   { bg: 'rgba(167,139,250,0.15)', border: 'rgba(167,139,250,0.4)', text: '#a78bfa' },
  ADP:   { bg: 'rgba(148,163,184,0.12)', border: 'rgba(148,163,184,0.3)', text: '#94a3b8' },
  CCONJ: { bg: 'rgba(148,163,184,0.12)', border: 'rgba(148,163,184,0.3)', text: '#94a3b8' },
  SCONJ: { bg: 'rgba(148,163,184,0.12)', border: 'rgba(148,163,184,0.3)', text: '#94a3b8' },
  DET:   { bg: 'rgba(148,163,184,0.10)', border: 'rgba(148,163,184,0.25)', text: '#94a3b8' },
  NUM:   { bg: 'rgba(56,189,248,0.15)',  border: 'rgba(56,189,248,0.4)',  text: '#38bdf8' },
  PRON:  { bg: 'rgba(244,63,94,0.15)',   border: 'rgba(244,63,94,0.4)',   text: '#fb7185' },
  PUNCT: { bg: 'transparent',            border: 'transparent',           text: 'var(--text-muted)' },
  SYM:   { bg: 'transparent',            border: 'transparent',           text: 'var(--text-muted)' },
  X:     { bg: 'rgba(100,116,139,0.12)', border: 'rgba(100,116,139,0.3)', text: '#64748b' },
};
const POS_DEFAULT_COLOR = { bg: 'rgba(100,116,139,0.12)', border: 'rgba(100,116,139,0.3)', text: '#64748b' };

function renderPosOutput(targetEl, posData, categories) {
  const active = window.__posActiveFilters || new Set();
  const targetId = targetEl.id;

  // Build category chip bar
  const chipOrder = ['NOUN','PROPN','VERB','ADJ','ADV','NUM','PRON','ADP','CCONJ','SCONJ','DET','PUNCT'];
  const sortedCats = [...categories].sort((a,b) => {
    const ai = chipOrder.indexOf(a), bi = chipOrder.indexOf(b);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  let chipBar = '<div class="pos-chip-bar">';
  sortedCats.forEach(cat => {
    if (cat === 'PUNCT' || cat === 'SYM') return; // skip trivial
    const isActive = active.has(cat);
    const color = POS_COLORS[cat] || POS_DEFAULT_COLOR;
    const activeStyle = isActive
      ? 'background:' + color.bg + ';border-color:' + color.border + ';color:' + color.text
      : '';
    chipBar += '<button type="button" class="pos-chip' + (isActive ? ' active' : '') + '" '
      + 'style="' + activeStyle + '" '
      + 'data-pos="' + cat + '" '
      + 'onclick="togglePosCategory(this, \'' + targetId + '\', \'' + cat + '\')">'
      + cat + '</button>';
  });
  chipBar += '</div>';

  // Build highlighted text
  let textHtml = '';
  posData.forEach(t => {
    const tok = t.token;
    const pos = t.pos || 'X';
    const isHighlighted = active.has(pos);
    const color = POS_COLORS[pos] || POS_DEFAULT_COLOR;

    if (isHighlighted) {
      textHtml += '<span class="pos-mark-active" style="background:' + color.bg + ';border-color:' + color.border + '">'
        + tok + ' <sup class="pos-tag" style="color:' + color.text + '">' + pos + '</sup></span>';
    } else {
      // Hover tooltip for non-highlighted tokens
      textHtml += '<span class="pos-token-hover" data-pos-tooltip="' + pos + '">' + tok + '</span>';
    }
  });

  targetEl.innerHTML = chipBar + '<div class="pos-text-output">' + textHtml + '</div>';
}

function togglePosCategory(chipEl, targetId, category) {
  if (!window.__posActiveFilters) window.__posActiveFilters = new Set();

  if (window.__posActiveFilters.has(category)) {
    window.__posActiveFilters.delete(category);
  } else {
    window.__posActiveFilters.add(category);
  }

  const targetEl = document.getElementById(targetId);
  const posData = window.__posData || [];
  const categories = new Set();
  posData.forEach(t => { if (t.pos) categories.add(t.pos); });

  renderPosOutput(targetEl, posData, categories);
}

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Keyboard Shortcuts (Ctrl+Enter -> Submit, Esc -> Close Modal)
function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      const form = document.getElementById('summarizeForm');
      if (form) {
        e.preventDefault();
        form.requestSubmit();
      }
    }
    if (e.key === 'Escape') {
      closeFullscreenEditor();
    }
  });
}

function initHamburger() {
  const btn = document.getElementById('hamburgerBtn');
  const nav = document.getElementById('mainNav');
  if (!btn || !nav) return;
  btn.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    btn.classList.toggle('active', open);
    btn.setAttribute('aria-expanded', open);
  });
  document.addEventListener('click', (e) => {
    if (!btn.contains(e.target) && !nav.contains(e.target)) {
      nav.classList.remove('open');
      btn.classList.remove('active');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
}

function initCSRF() {
  document.body.addEventListener('htmx:configRequest', (e) => {
    const token = window.__CSRF_TOKEN;
    if (token) {
      e.detail.headers['X-CSRF-Token'] = token;
    }
  });

  document.body.addEventListener('htmx:responseError', (e) => {
    if (e.detail.xhr.status === 403) {
      showToast('Session expired. Please refresh the page.', 'error');
    }
  });

  document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(form => {
    form.addEventListener('submit', (e) => {
      if (form.hasAttribute('hx-post')) return;
      e.preventDefault();
      const token = window.__CSRF_TOKEN;
      if (!token) {
        showToast('CSRF token missing. Please refresh.', 'error');
        return;
      }
      const hiddenInput = document.createElement('input');
      hiddenInput.type = 'hidden';
      hiddenInput.name = '_csrf_header';
      hiddenInput.value = token;
      form.appendChild(hiddenInput);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', form.action, true);
      xhr.setRequestHeader('X-CSRF-Token', token);
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 400) {
          const redirectUrl = xhr.getResponseHeader('Location');
          if (redirectUrl) {
            window.location.href = redirectUrl;
          } else if (form.action.includes('login') || form.action.includes('register') || form.action.includes('profile')) {
            window.location.reload();
          }
        } else {
          document.open();
          document.write(xhr.responseText);
          document.close();
        }
      };
      xhr.onerror = () => showToast('Network error. Please try again.', 'error');
      const formData = new FormData(form);
      xhr.send(formData);
    });
  });
}

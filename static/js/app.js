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
});

// Theme Management
function initThemeToggle() {
  const toggleBtn = document.querySelector('.theme-toggle');
  if (!toggleBtn) return;
  const currentTheme = localStorage.getItem('theme') || 'dark';
  document.body.setAttribute('data-theme', currentTheme);

  toggleBtn.addEventListener('click', () => {
    const theme = document.body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  });
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
    labelSpan.innerText = selectedOption ? selectedOption.text : 'Select option';

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

  if (wordCount) wordCount.innerText = words.toLocaleString();
  if (charCount) charCount.innerText = chars.toLocaleString();
  if (tokenCount) tokenCount.innerText = tokens.toLocaleString();

  if (limitMsg) {
    if (words > 8000) {
      limitMsg.className = 'limit-danger';
      limitMsg.innerText = 'Exceeds limit (Max 8,000 words)';
    } else if (words > 6000) {
      limitMsg.className = 'limit-warning';
      limitMsg.innerText = 'Approaching limit (Max 8,000 words)';
    } else {
      limitMsg.className = '';
      limitMsg.innerText = 'Limit: 8,000 words';
    }
  }

  // Bi-directional sync with modal editor
  const modalText = document.getElementById('modalRawText');
  if (modalText && modalText.value !== val) {
    modalText.value = val;
    const modalWordCount = document.getElementById('modalWordCount');
    if (modalWordCount) modalWordCount.innerText = words.toLocaleString();
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
  if (!text || text.includes('Waiting for input')) {
    showToast('No summary text to copy.', 'error');
    return;
  }
  navigator.clipboard.writeText(text).then(() => {
    showToast('Summary copied to clipboard!', 'success');
  }).catch(() => {
    showToast('Failed to copy text.', 'error');
  });
}

function saveSummaryOutput(targetId) {
  const textEl = document.getElementById(targetId);
  if (!textEl) return;
  const text = textEl.innerText.trim();
  if (!text || text.includes('Waiting for input')) {
    showToast('No summary text to save.', 'error');
    return;
  }
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `indogist_summary_${Date.now()}.txt`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('Summary downloaded as file.', 'success');
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
  if (!plainText || plainText.includes('Waiting for input') || plainText.includes('No ')) return;

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
      showToast('No detected entities available for this summary.', 'info');
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
    // Simple client-side POS heuristic for Indonesian text
    // Splits on whitespace, preserving punctuation
    const words = plainText.split(/(\s+)/);
    const html = words.map(token => {
      const trimmed = token.trim();
      if (!trimmed) return token; // preserve whitespace
      if (/^[,.:;?!"'()\-—]+$/.test(trimmed)) return '<span class="pos-mark">' + trimmed + ' <sup class="pos-tag">PUNCT</sup></span>';

      let posTag = 'NOUN';
      const lower = trimmed.toLowerCase();

      // Numbers
      if (/^[\d.,]+$/.test(trimmed)) posTag = 'NUM';
      // Proper nouns (capitalized, not sentence start — approximate)
      else if (/^[A-Z][a-z]/.test(trimmed)) posTag = 'PROPN';
      // Common Indonesian verbs (me-, ber-, di-, ter- prefix)
      else if (/^(me|ber|di|ter|mem|men|meng|meny|menge|per|pem|pen|peng|peny|penge)[a-z]/i.test(lower)) posTag = 'VERB';
      // Function words: prepositions/conjunctions
      else if (['dan', 'atau', 'serta', 'namun', 'tetapi', 'tapi', 'karena', 'sebab', 'agar', 'supaya', 'jika', 'kalau', 'bila', 'meski', 'meskipun', 'walau', 'walaupun', 'bahwa', 'ketika', 'saat', 'sebelum', 'sesudah', 'setelah'].includes(lower)) posTag = 'CCONJ';
      else if (['yang', 'ini', 'itu', 'tersebut', 'para', 'sang', 'si'].includes(lower)) posTag = 'DET';
      else if (['ke', 'di', 'dari', 'pada', 'untuk', 'dengan', 'oleh', 'dalam', 'antara', 'tanpa', 'tentang', 'terhadap', 'mengenai', 'selama', 'sejak', 'hingga', 'sampai', 'sebagai'].includes(lower)) posTag = 'ADP';
      // Adjectives (common suffixes/patterns)
      else if (['besar', 'kecil', 'tinggi', 'rendah', 'banyak', 'sedikit', 'baru', 'lama', 'baik', 'buruk', 'modern', 'utama', 'berbasis', 'standar', 'penting', 'terbesar', 'terbanyak', 'terkecil', 'tertinggi'].includes(lower)) posTag = 'ADJ';
      // Adverbs
      else if (['sangat', 'tidak', 'bukan', 'belum', 'sudah', 'akan', 'telah', 'masih', 'juga', 'pun', 'pula', 'hanya', 'saja', 'sekali', 'lagi', 'segera', 'selalu', 'sering', 'jarang'].includes(lower)) posTag = 'ADV';
      // Pronouns
      else if (['saya', 'aku', 'kamu', 'anda', 'dia', 'ia', 'mereka', 'kami', 'kita', 'beliau'].includes(lower)) posTag = 'PRON';
      // Common verbs (non-prefixed)
      else if (['adalah', 'merupakan', 'ada', 'bisa', 'dapat', 'harus', 'perlu', 'mau', 'ingin', 'akan', 'boleh', 'tahu', 'kenal'].includes(lower)) posTag = 'VERB';

      return '<span class="pos-mark">' + trimmed + ' <sup class="pos-tag">' + posTag + '</sup></span>';
    }).join('');

    targetEl.innerHTML = html;
    return;
  }
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

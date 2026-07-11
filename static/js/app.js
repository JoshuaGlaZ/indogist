/**
 * INDOGIST — Interactive Studio Engine
 * Theme Switcher, Live Telemetry Counter, Clipboard & Export Utilities,
 * HTMX Event Hooks, Expandable Text Controls, and Scramble Decoder
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
  localStorage.setItem('indogist_theme', theme);
  
  // Update toggle button icon & label if present
  const toggleBtn = document.getElementById('themeToggleBtn');
  if (toggleBtn) {
    if (theme === 'light') {
      toggleBtn.innerHTML = '<i class="fas fa-moon"></i>';
      toggleBtn.setAttribute('title', 'Switch to Dark Theme');
    } else {
      toggleBtn.innerHTML = '<i class="fas fa-sun"></i>';
      toggleBtn.setAttribute('title', 'Switch to Light Theme');
    }
  }
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme);
}

// ——————————————————————————————————————————————————
// 2. Real-Time Telemetry & Reading Time Engine
// ——————————————————————————————————————————————————
function updateTelemetry(val) {
  const text = typeof val === 'string' ? val : (val && val.value ? val.value : '');
  const trimmed = text.trim();
  
  const words = trimmed ? trimmed.split(/\s+/).length : 0;
  const chars = text.length;
  const paragraphs = trimmed ? trimmed.split(/\n\s*\n/).length : 0;
  const estReadingMinutes = Math.ceil(words / 200);
  
  const wordCountEl = document.getElementById('inputWordCount');
  if (wordCountEl) {
    wordCountEl.innerText = `${words} Words`;
  }
  
  const readingGaugeEl = document.getElementById('readingTimeGauge');
  if (readingGaugeEl) {
    readingGaugeEl.innerText = words > 0 ? `~${estReadingMinutes} min read (${words} words, ${chars} chars)` : '';
  }

  const warningEl = document.getElementById('largeDocWarning');
  if (warningEl) {
    if (words > 10000) {
      warningEl.classList.remove('d-none');
    } else {
      warningEl.classList.add('d-none');
    }
  }
}

// Backward compatibility alias
function updateWordCount(val) {
  updateTelemetry(val);
}

// ——————————————————————————————————————————————————
// 3. Clipboard & File Export Utilities
// ——————————————————————————————————————————————————
function copySummaryOutput(elementId = 'outputContent', btnElement = null) {
  const output = document.getElementById(elementId);
  if (!output) return;
  
  const textToCopy = output.value || output.innerText;
  if (!textToCopy.trim()) return;

  navigator.clipboard.writeText(textToCopy).then(() => {
    if (btnElement) {
      const originalHtml = btnElement.innerHTML;
      btnElement.innerHTML = '<i class="fas fa-check me-1"></i> Copied!';
      btnElement.classList.add('text-success');
      setTimeout(() => {
        btnElement.innerHTML = originalHtml;
        btnElement.classList.remove('text-success');
      }, 2000);
    } else {
      alert('Summary copied to clipboard!');
    }
  }).catch(err => {
    console.error('Failed to copy: ', err);
  });
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

// ——————————————————————————————————————————————————
// 4. Sample Preset & File Upload Handlers
// ——————————————————————————————————————————————————
function loadPreset(type) {
  const presets = {
    news: "Jakarta - Perkembangan teknologi kecerdasan buatan (AI) di Indonesia tumbuh pesat dalam tiga tahun terakhir. Berbagai sektor mulai dari logistik, keuangan, hingga pelayanan publik telah mengadopsi otomasi berbasis pemrosesan bahasa alami (NLP) untuk meningkatkan efisiensi operasional.",
    tech: "FastAPI adalah kerangka kerja web modern berkinerja tinggi untuk membangun API berbasis Python 3.8+ dengan tipe data standar. Kerangka kerja ini mendukung validasi otomatis berbasis Pydantic dan dokumentasi Swagger UI interaktif.",
    academic: "Penelitian ini mengevaluasi performa penggabungan ekstraksi kata kunci berbasis TF-IDF dengan pemotongan kata berimbuhan Sastrawi pada korpus berita berbahasa Indonesia. Hasil pengujian menunjukkan peningkatan skor ROUGE-1 sebesar 12% dibandingkan metode tradisional."
  };
  const input = document.getElementById('rawTextInput');
  if (input) {
    input.value = presets[type] || '';
    updateTelemetry(input.value);
  }
}

function handleFileSelect(input) {
  const fileInfo = document.getElementById('fileInfo');
  if (input.files && input.files[0]) {
    const file = input.files[0];
    if (fileInfo) {
      fileInfo.classList.remove('d-none');
      fileInfo.innerText = `Selected File: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    }
  }
}

// ——————————————————————————————————————————————————
// 5. Expandable Long Text Controls
// ——————————————————————————————————————————————————
function toggleSummaryExpand(containerId = 'outputContentPane', btnElement = null) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const isExpanded = container.classList.toggle('expanded');
  if (btnElement) {
    btnElement.innerHTML = isExpanded 
      ? '<i class="fas fa-compress-alt me-1"></i> Collapse Summary' 
      : '<i class="fas fa-expand-alt me-1"></i> Show Full Summary';
  }
}

// ——————————————————————————————————————————————————
// 6. Soulwire TextScramble Decoder Engine
// ——————————————————————————————————————————————————
class TextScramble {
  constructor(el) {
    this.el = el;
    this.chars = '!<>-_\\/[]{}—=+*^?#________';
    this.update = this.update.bind(this);
  }
  setText(newText) {
    const oldText = this.el.innerText || '';
    const length = Math.max(oldText.length, newText.length);
    const promise = new Promise((resolve) => (this.resolve = resolve));
    this.queue = [];
    for (let i = 0; i < length; i++) {
      const from = oldText[i] || '';
      const to = newText[i] || '';
      const start = Math.floor(Math.random() * 40);
      const end = start + Math.floor(Math.random() * 40);
      this.queue.push({ from, to, start, end });
    }
    cancelAnimationFrame(this.frameRequest);
    this.frame = 0;
    this.update();
    return promise;
  }
  update() {
    let output = '';
    let complete = 0;
    for (let i = 0, n = this.queue.length; i < n; i++) {
      let { from, to, start, end, char } = this.queue[i];
      if (this.frame >= end) {
        complete++;
        output += to;
      } else if (this.frame >= start) {
        if (!char || Math.random() < 0.28) {
          char = this.randomChar();
          this.queue[i].char = char;
        }
        output += `<span class="text-muted opacity-50">${char}</span>`;
      } else {
        output += from;
      }
    }
    this.el.innerHTML = output;
    if (complete === this.queue.length) {
      this.resolve();
    } else {
      this.frameRequest = requestAnimationFrame(this.update);
      this.frame++;
    }
  }
  randomChar() {
    return this.chars[Math.floor(Math.random() * this.chars.length)];
  }
}

function initScrambleTicker() {
  const tickerEl = document.querySelector('.scramble-ticker');
  if (!tickerEl) return;
  const phrases = [
    'AUTOMATED TEXT SUMMARIZATION ENGINE',
    'HYBRID EXTRACTIVE & ABSTRACTIVE CORE',
    'TRANSFORMING DOCUMENTS INTO CRISP INSIGHTS',
    'SASTRAWI & TF-IDF POWERED COMPRESSION'
  ];
  const fx = new TextScramble(tickerEl);
  let counter = 0;
  const next = () => {
    fx.setText(phrases[counter]).then(() => {
      setTimeout(next, 3000);
    });
    counter = (counter + 1) % phrases.length;
  };
  next();
}

function initCommandPalette() {
  const modal = document.getElementById('commandPaletteModal');
  if (!modal) return;
  
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      const bsModal = new bootstrap.Modal(modal);
      bsModal.toggle();
    }
  });
}

// ——————————————————————————————————————————————————
// 7. Event Initialization & HTMX Hooks
// ——————————————————————————————————————————————————
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initScrambleTicker();
  initCommandPalette();
  
  const textInput = document.getElementById('rawTextInput');
  if (textInput) {
    updateTelemetry(textInput.value);
  }
});

document.addEventListener('htmx:afterSwap', (e) => {
  // Smooth scroll to output container on mobile viewports
  if (window.innerWidth < 992 && e.detail.target.id === 'summaryOutputContainer') {
    e.detail.target.scrollIntoView({ behavior: 'smooth' });
  }

  // Re-run scramble decode on new summary output elements
  const newOutput = e.detail.target.querySelector('.scramble-output');
  if (newOutput) {
    const text = newOutput.getAttribute('data-text') || newOutput.innerText;
    const fx = new TextScramble(newOutput);
    fx.setText(text);
  }
});

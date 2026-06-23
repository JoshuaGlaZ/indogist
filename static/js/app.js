/**
 * INDOGIST — Interactive Client Engine
 * Includes TextScramble Decoder, Command Palette (Ctrl+K), and HTMX Event Hooks
 */

// ——————————————————————————————————————————————————
// 1. Soulwire TextScramble Decoder Engine
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

// ——————————————————————————————————————————————————
// 2. Header Tagline Ticker
// ——————————————————————————————————————————————————
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

// ——————————————————————————————————————————————————
// 3. Kan3an 3D Spatial Card Tilt Effect
// ——————————————————————————————————————————————————
function init3DTiltCards() {
  const cards = document.querySelectorAll('.tilt-card');
  cards.forEach((card) => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;
      card.style.transform = `perspective(1000px) rotateX(${-y / 20}deg) rotateY(${x / 20}deg) translateY(-4px)`;
    });
    card.addEventListener('mouseleave', () => {
      card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0deg)';
    });
  });
}

// ——————————————————————————————————————————————————
// 4. Command Palette (Ctrl + K) Modal Controller
// ——————————————————————————————————————————————————
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
// 5. HTMX Global Event Listeners & Initialize
// ——————————————————————————————————————————————————
document.addEventListener('DOMContentLoaded', () => {
  initScrambleTicker();
  init3DTiltCards();
  initCommandPalette();
});

document.addEventListener('htmx:afterSwap', (e) => {
  init3DTiltCards();
  
  // Re-run scramble decode on new summary output elements
  const newOutput = e.detail.target.querySelector('.scramble-output');
  if (newOutput) {
    const text = newOutput.getAttribute('data-text') || newOutput.innerText;
    const fx = new TextScramble(newOutput);
    fx.setText(text);
  }
});

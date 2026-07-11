/**
 * Hybrid Loading States Manager
 * Provides various loading state components
 * Usage: Loading.showOverlay(), Loading.buttonLoading(), etc.
 */

(function() {
  'use strict';

  // Inject loading states styles
  function injectStyles() {
    if (document.getElementById('loading-states-styles')) return;
    
    const style = document.createElement('style');
    style.id = 'loading-states-styles';
    style.textContent = `
      /* Skeleton Loading */
      .skeleton {
        background: linear-gradient(
          90deg,
          rgba(51, 65, 85, 0.4) 0%,
          rgba(71, 85, 105, 0.4) 50%,
          rgba(51, 65, 85, 0.4) 100%
        );
        background-size: 200% 100%;
        animation: skeletonLoading 1.5s ease-in-out infinite;
        border-radius: 8px;
      }

      @keyframes skeletonLoading {
        0% {
          background-position: 200% 0;
        }
        100% {
          background-position: -200% 0;
        }
      }

      .skeleton-text {
        height: 1rem;
        margin-bottom: 0.5rem;
      }

      .skeleton-text:last-child {
        width: 60%;
      }

      .skeleton-card {
        height: 200px;
      }

      .skeleton-circle {
        border-radius: 50%;
        width: 48px;
        height: 48px;
      }

      /* Shimmer Effect */
      .shimmer {
        position: relative;
        overflow: hidden;
      }

      .shimmer::after {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        left: 0;
        transform: translateX(-100%);
        background: linear-gradient(
          90deg,
          transparent,
          rgba(255, 255, 255, 0.1),
          transparent
        );
        animation: shimmer 2s infinite;
      }

      @keyframes shimmer {
        100% {
          transform: translateX(100%);
        }
      }

      /* Pulse Loading */
      .pulse-loader {
        display: flex;
        gap: 0.5rem;
        justify-content: center;
        align-items: center;
      }

      .pulse-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: #f59e0b;
        animation: pulseAnimation 1.4s ease-in-out infinite;
      }

      .pulse-dot:nth-child(1) {
        animation-delay: 0s;
      }

      .pulse-dot:nth-child(2) {
        animation-delay: 0.2s;
      }

      .pulse-dot:nth-child(3) {
        animation-delay: 0.4s;
      }

      @keyframes pulseAnimation {
        0%, 100% {
          transform: scale(0.8);
          opacity: 0.5;
        }
        50% {
          transform: scale(1.2);
          opacity: 1;
        }
      }

      /* Progress Bar */
      .progress-bar-modern {
        width: 100%;
        height: 4px;
        background: rgba(51, 65, 85, 0.5);
        border-radius: 4px;
        overflow: hidden;
        position: relative;
      }

      .progress-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, #f59e0b, #fbbf24);
        border-radius: 4px;
        transition: width 0.3s ease;
        box-shadow: 0 0 10px rgba(245, 158, 11, 0.5);
      }

      .progress-bar-indeterminate {
        position: absolute;
        height: 100%;
        width: 40%;
        background: linear-gradient(90deg, transparent, #f59e0b, transparent);
        animation: indeterminate 1.5s ease-in-out infinite;
      }

      @keyframes indeterminate {
        0% {
          left: -40%;
        }
        100% {
          left: 100%;
        }
      }

      /* Button Loading State */
      .btn-loading {
        position: relative;
        pointer-events: none;
        opacity: 0.7;
      }

      .btn-loading .btn-text {
        visibility: hidden;
      }

      .btn-loading::after {
        content: '';
        position: absolute;
        width: 16px;
        height: 16px;
        top: 50%;
        left: 50%;
        margin-left: -8px;
        margin-top: -8px;
        border: 2px solid transparent;
        border-top-color: currentColor;
        border-radius: 50%;
        animation: btnSpin 0.6s linear infinite;
      }

      @keyframes btnSpin {
        to {
          transform: rotate(360deg);
        }
      }

      /* Card Loading State */
      .card-loading {
        position: relative;
        pointer-events: none;
      }

      .card-loading::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(15, 23, 42, 0.7);
        backdrop-filter: blur(2px);
        -webkit-backdrop-filter: blur(2px);
        z-index: 10;
        border-radius: inherit;
        animation: fadeIn 0.2s ease;
      }

      .card-loading::after {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 40px;
        height: 40px;
        margin: -20px 0 0 -20px;
        border: 3px solid rgba(245, 158, 11, 0.2);
        border-top-color: #f59e0b;
        border-radius: 50%;
        z-index: 11;
        animation: spin 0.8s linear infinite;
      }

      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }

      @keyframes fadeIn {
        from {
          opacity: 0;
        }
        to {
          opacity: 1;
        }
      }

      /* Mobile Responsive */
      @media (max-width: 640px) {
        .pulse-dot {
          width: 10px;
          height: 10px;
        }
        
        .skeleton-circle {
          width: 36px;
          height: 36px;
        }
      }

      /* Reduced Motion */
      @media (prefers-reduced-motion: reduce) {
        .skeleton,
        .pulse-dot,
        .progress-bar-indeterminate,
        .shimmer::after,
        .btn-loading::after,
        .card-loading::after {
          animation: none !important;
        }
        
        .skeleton {
          background: rgba(51, 65, 85, 0.4);
        }
      }
    `;
    
    document.head.appendChild(style);
  }

  const LoadingStates = {
    
    /**
     * Show full-page loading overlay
     * @param {string} title - Loading title
     * @param {string} message - Loading message
     * @returns {HTMLElement} The overlay element
     */
    showOverlay(title = 'Processing...', message = 'Please wait') {
      // Remove existing overlay
      this.hideOverlay();
      
      const overlay = document.createElement('div');
      overlay.className = 'loading-overlay';
      overlay.id = 'global-loading-overlay';
      overlay.innerHTML = `
        <div class="loading-content">
          <div class="spinner-ring"></div>
          <div class="loading-title">${this._escapeHtml(title)}</div>
          <div class="loading-message">${this._escapeHtml(message)}</div>
        </div>
      `;
      
      document.body.appendChild(overlay);
      document.body.style.overflow = 'hidden';
      
      return overlay;
    },

    /**
     * Hide full-page loading overlay
     */
    hideOverlay() {
      const overlay = document.getElementById('global-loading-overlay');
      if (overlay) {
        overlay.style.animation = 'fadeOut 0.2s ease';
        overlay.style.opacity = '0';
        
        setTimeout(() => {
          if (overlay.parentNode) {
            overlay.parentNode.removeChild(overlay);
          }
          document.body.style.overflow = '';
        }, 200);
      }
    },

    /**
     * Add loading state to a button
     * @param {HTMLElement} button - The button element
     * @param {string} loadingText - Optional loading text
     */
    buttonLoading(button, loadingText = null) {
      if (!button) return;
      
      // Store original content
      button.dataset.originalHtml = button.innerHTML;
      button.dataset.originalDisabled = button.disabled;
      
      button.disabled = true;
      button.classList.add('btn-loading');
      
      if (loadingText) {
        button.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>${this._escapeHtml(loadingText)}`;
      }
    },

    /**
     * Remove loading state from a button
     * @param {HTMLElement} button - The button element
     */
    buttonReady(button) {
      if (!button) return;
      
      button.classList.remove('btn-loading');
      
      // Restore original state
      if (button.dataset.originalHtml) {
        button.innerHTML = button.dataset.originalHtml;
        delete button.dataset.originalHtml;
      }
      
      if (button.dataset.originalDisabled !== undefined) {
        button.disabled = button.dataset.originalDisabled === 'true';
        delete button.dataset.originalDisabled;
      } else {
        button.disabled = false;
      }
    },

    /**
     * Add loading state to a card
     * @param {HTMLElement} card - The card element
     */
    cardLoading(card) {
      if (card) {
        card.classList.add('card-loading');
      }
    },

    /**
     * Remove loading state from a card
     * @param {HTMLElement} card - The card element
     */
    cardReady(card) {
      if (card) {
        card.classList.remove('card-loading');
      }
    },

    /**
     * Create a skeleton loader
     * @param {string} type - Type of skeleton (card, text, circle)
     * @returns {HTMLElement} The skeleton element
     */
    skeleton(type = 'text') {
      const skeleton = document.createElement('div');
      skeleton.className = 'skeleton shimmer';
      
      switch(type) {
        case 'card':
          skeleton.classList.add('skeleton-card');
          break;
        case 'circle':
          skeleton.classList.add('skeleton-circle');
          break;
        case 'text':
        default:
          skeleton.classList.add('skeleton-text');
      }
      
      return skeleton;
    },

    /**
     * Show pulse loader in a container
     * @param {HTMLElement} container - Container element
     */
    showPulse(container) {
      if (!container) return;
      
      container.innerHTML = `
        <div class="pulse-loader">
          <div class="pulse-dot"></div>
          <div class="pulse-dot"></div>
          <div class="pulse-dot"></div>
        </div>
      `;
    },

    /**
     * Show progress bar
     * @param {HTMLElement} container - Container element
     * @param {number} progress - Progress percentage (0-100)
     */
    showProgress(container, progress = 0) {
      if (!container) return;
      
      let progressBar = container.querySelector('.progress-bar-modern');
      
      if (!progressBar) {
        progressBar = document.createElement('div');
        progressBar.className = 'progress-bar-modern';
        progressBar.innerHTML = '<div class="progress-bar-fill"></div>';
        container.appendChild(progressBar);
      }
      
      const fill = progressBar.querySelector('.progress-bar-fill');
      if (fill) {
        fill.style.width = `${Math.min(100, Math.max(0, progress))}%`;
      }
    },

    /**
     * Show indeterminate progress
     * @param {HTMLElement} container - Container element
     */
    showIndeterminate(container) {
      if (!container) return;
      
      container.innerHTML = `
        <div class="progress-bar-modern">
          <div class="progress-bar-indeterminate"></div>
        </div>
      `;
    },

    /**
     * Create skeleton text lines
     * @param {number} lines - Number of lines
     * @returns {DocumentFragment} Fragment with skeleton lines
     */
    skeletonLines(lines = 3) {
      const fragment = document.createDocumentFragment();
      
      for (let i = 0; i < lines; i++) {
        const line = this.skeleton('text');
        fragment.appendChild(line);
      }
      
      return fragment;
    },

    /**
     * Escape HTML to prevent XSS
     * @private
     */
    _escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
  };

  // Initialize
  injectStyles();

  // Expose API
  window.Loading = LoadingStates;

  // Also make available as a module export if needed
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = LoadingStates;
  }

})();
/**
 * ASINInsight Cookie Consent
 * GDPR (EU) + CCPA (California) compliant
 * Only essential session cookies used — no tracking, no analytics, no advertising.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'ai_cookie_consent';
  var consent = null;
  try { consent = localStorage.getItem(STORAGE_KEY); } catch(e){}
  if (consent) return; // Already decided

  var bar = document.createElement('div');
  bar.id = 'cookieConsentBar';
  bar.setAttribute('role', 'dialog');
  bar.setAttribute('aria-modal', 'false');
  bar.setAttribute('aria-label', 'Cookie consent');
  bar.setAttribute('aria-live', 'polite');
  bar.style.cssText = [
    'position:fixed', 'bottom:0', 'left:0', 'right:0', 'z-index:9999',
    'background:#15263d', 'color:#fff',
    'padding:16px 24px',
    'display:flex', 'align-items:center', 'justify-content:space-between', 'flex-wrap:wrap', 'gap:14px',
    'box-shadow:0 -2px 16px rgba(0,0,0,.25)',
    'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif',
    'font-size:14px', 'line-height:1.5'
  ].join(';');

  bar.innerHTML = [
    '<div style="max-width:740px;flex:1 1 300px;">',
      '<strong style="font-size:14px;font-weight:700;">We use essential cookies only.</strong> ',
      '<span style="color:rgba(255,255,255,.78);">',
        'A single session cookie keeps you signed in. No tracking. No advertising. No third-party analytics. ',
        'EU visitors: GDPR applies. US residents: CCPA applies. Other visitors: only essential cookies are used. ',
        '<a href="/privacy" style="color:rgba(255,255,255,.85);text-decoration:underline;">Privacy Policy</a>',
      '</span>',
    '</div>',
    '<div style="display:flex;gap:10px;flex-shrink:0;align-items:center;">',
      '<button id="ai_cookie_decline" style="background:transparent;border:1.5px solid rgba(255,255,255,.35);color:rgba(255,255,255,.8);font-size:13px;font-weight:600;padding:8px 18px;border-radius:8px;cursor:pointer;font-family:inherit;">',
        'Necessary only',
      '</button>',
      '<button id="ai_cookie_accept" style="background:#fff;border:none;color:#15263d;font-size:13px;font-weight:700;padding:8px 20px;border-radius:8px;cursor:pointer;font-family:inherit;">',
        'Accept all',
      '</button>',
    '</div>'
  ].join('');

  function dismiss(value) {
    try { localStorage.setItem(STORAGE_KEY, value); } catch(e){}
    bar.style.transition = 'opacity .25s,transform .25s';
    bar.style.opacity = '0';
    bar.style.transform = 'translateY(8px)';
    setTimeout(function(){ if (bar.parentNode) bar.parentNode.removeChild(bar); }, 280);
  }

  bar.querySelector('#ai_cookie_accept').addEventListener('click', function(){
    dismiss('accepted');
    try { document.dispatchEvent(new CustomEvent('ai:cookieAccepted')); } catch(e){}
  });
  bar.querySelector('#ai_cookie_decline').addEventListener('click', function(){ dismiss('necessary'); });

  function mount() {
    document.body.appendChild(bar);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();

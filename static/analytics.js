/**
 * ASINInsight — Google Analytics 4 loader
 *
 * Only activates when the user has accepted cookies (ai_cookie_consent = 'accepted').
 * The GA Measurement ID is fetched from /api/site-config so it can be set
 * via a Railway env variable (GA_MEASUREMENT_ID) without touching any HTML.
 *
 * Also listens for the custom 'ai:cookieAccepted' event dispatched by
 * cookie-consent.js so GA loads in the same page session after acceptance.
 */
(function () {
  'use strict';

  var _loaded = false;

  function _loadGA(id) {
    if (_loaded) return;
    if (!id || id === 'G-XXXXXXXXXX') return;
    _loaded = true;

    window.dataLayer = window.dataLayer || [];
    function gtag() { window.dataLayer.push(arguments); }
    window.gtag = gtag;

    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + id;
    document.head.appendChild(s);

    gtag('js', new Date());
    gtag('config', id, { anonymize_ip: true });
  }

  function _init() {
    var consent = '';
    try { consent = localStorage.getItem('ai_cookie_consent') || ''; } catch (e) {}
    if (consent !== 'accepted') return;

    fetch('/api/site-config', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (cfg) { _loadGA(cfg.ga_id); })
      .catch(function () {}); // non-critical — silently ignore errors
  }

  // Fires when cookie-consent.js dispatches the acceptance event in-session
  document.addEventListener('ai:cookieAccepted', function () {
    fetch('/api/site-config', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (cfg) { _loadGA(cfg.ga_id); })
      .catch(function () {});
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }
})();

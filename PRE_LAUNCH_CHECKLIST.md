# Pre-Launch Checklist & Security Follow-Up

This file captures the two outstanding items from the final quality
pass that cannot be closed purely from source code. Every item here
has a named owner or an explicit trigger; nothing is optional.

---

## 1. Required validations before any real user sees the product

These MUST each be executed and checked off before the first post in
any seller community or any paid acquisition.

### 1.1 Paddle sandbox end-to-end payment test
Goal: prove a real user can pay and land in the product without a
silent failure or a duplicate charge.

- [ ] Run Paddle sandbox in the `environment=sandbox` path.
  (`/api/paddle-config` returns the sandbox token when `PADDLE_ENV=sandbox`.)
- [ ] Click **Get Pro $49/mo** from `/pricing` in a real browser.
  Checkout overlay opens, payment succeeds, user lands on `/success`
  with a valid `customer_id`.
- [ ] Verify session is upgraded via `/api/paddle/activate` (now CSRF-protected).
- [ ] Refresh the tab and confirm `session["plan"]` persists.
- [ ] Close the overlay mid-payment — button restores original label+icon
  (the regression fixed in commit `6abc08c`).
- [ ] Block `cdn.paddle.com` in DevTools → click **Get Pro** → the button
  now shows "Checkout is temporarily unavailable" instead of submitting
  the free form (new guard added in `6abc08c`).
- [ ] Submit the same test webhook twice — second attempt is rejected
  as a duplicate (Paddle webhook idempotency key).

### 1.2 Mobile browser validation
Goal: no layout glitches, no unreachable buttons, no broken upload.

Minimum device matrix:
- [ ] iPhone Safari (iOS 17+, portrait + landscape)
- [ ] Android Chrome (Pixel or Samsung, portrait + landscape)
- [ ] iPad Safari (portrait)
- [ ] Desktop Chrome + Firefox + Safari at 1440px and 1920px

Per surface:
- [ ] `/` landing page: hero, early-access banner, CTA buttons all usable.
- [ ] `/pricing`: Pro and Agency buttons trigger Paddle overlay without the page scrolling off.
- [ ] `/app`: CSV drag-and-drop + tap-to-upload both work.
- [ ] Audit output is readable without horizontal scroll.

### 1.3 Paddle webhook live check
Goal: prove signed webhooks from Paddle reach our handler and mutate
state correctly in production (not just staging).

- [ ] Send a real `subscription_created` webhook from the Paddle
  sandbox dashboard to the production `/webhook/paddle` URL.
- [ ] Confirm the database row is created, the log line includes a
  masked email only, and no stack trace is leaked in the response.
- [ ] Break the HMAC signature in a replay → endpoint rejects with 401.

### 1.4 Real seller CSV pass
Goal: verify the engine does not crash or produce nonsense on data
that was not synthesised in-house.

- [ ] At least 3 real Amazon Business Reports from consenting sellers
  run through `/api/diagnose` without raising.
- [ ] Every output passes the `test_reliability.py` sanity checks
  when the result dict is fed back through them offline.
- [ ] At least one real-CSV result is reviewed by an experienced
  Amazon seller who has not seen the product before. Their verbal
  reaction is recorded verbatim. A "this doesn't make sense" finding
  blocks the launch until resolved.

---

## 2. Security MEDIUM items queued (non-blocking for soft launch,
   required before any paid-traffic push)

Each item carries an owner slot. Source references are file:line.

### 2.1 Rate limits on remaining endpoints
Ship Paddle/user-facing limits across the full public surface, not
just the flagship routes.

- [ ] `/amazon/connect` and `/amazon/callback` — 10/hour/IP to deter
  OAuth enumeration. (server.py:2454, 2472)
- [ ] `/api/amazon/inventory` — reuse `_check_diagnose_rate` or a
  dedicated bucket. (server.py:2525)
- [ ] `/unsubscribe` — 20/hour/IP to prevent abuse. (server.py:1002)
- [ ] `/admin` — IP allow-list or basic auth, not just rate limit. (server.py:2584)

### 2.2 Replace CSP `unsafe-inline`
Inline scripts/styles are the reason CSP is neutered. Move inline JS
to `/static/*.js`, then swap `unsafe-inline` for a nonce/hash policy.
(server.py:735-736)

### 2.3 Stop admin error leakage
`/admin` currently returns raw DB error strings on certain failure
paths. Swap for a generic message + log the detail server-side.
(server.py:2625 area)

### 2.4 Move Amazon OAuth tokens out of the session cookie
Access + refresh tokens live in `flask.session` today. Migrate to a
server-side session store (e.g. itsdangerous token + DB-backed session,
or Redis). HttpOnly + Secure limit the blast radius but are not a
permanent mitigation.
(server.py:2498-2500)

### 2.5 Trim `OWNER_EMAIL` from the frontend-reachable config
`/api/paddle-config` currently exposes `owner_email` so the JS can
block self-checkout. Move that guard server-side (check on the
`/api/paddle/activate` path) and drop the field from the response.
(server.py:925)

### 2.6 Frontend hardening follow-ups (from frontend audit)
- [ ] Replace the `innerHTML = escHtml(x)` pattern in `app.html` with
  `textContent`-based building. Current pattern is safe but fragile.
  (app.html:772-793)
- [ ] Add explicit `<label>` or `aria-label` on `#emailInput` and
  `#leadEmail`. (app.html:488-495, 513)
- [ ] De-duplicate the CSRF-inject script block: move to
  `/static/csrf.js` and include in all three HTMLs.

---

## 3. How to use this checklist

1. Do NOT mark items "done" inside this file during launch prep —
   track in whatever issue system the team uses. This file is the
   reference.
2. Every launch-gating item in Section 1 must be signed off by an
   actual human performing the action. Scripts can help set up the
   environment but cannot replace the checks themselves.
3. Section 2 items are queued follow-ups. The date they are closed
   belongs in the commit message, not here.

**Sources for this checklist:**
- Security audit (2026-04-20), see commit `6abc08c`.
- Frontend audit (2026-04-20), see commit `6abc08c`.
- Landing trust-fix (2026-04-20), see this commit.

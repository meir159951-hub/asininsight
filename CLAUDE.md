# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo orientation

The README describes the original "zero-dependency local prototype" (an `audit_engine.py` CLI that renders an HTML report from `sample_data/demo_store.json`). The product has since grown into a full Flask web app — **`server.py` (~4200 lines) is the real entry point**. The CLI in `audit_engine.py` is still usable but is no longer the product.

Two product lines live in this repo:

1. **ASINInsight** — anonymous ASIN diagnosis tool. Sellers paste/upload Amazon Business Report CSVs, get a rule-based growth diagnosis, optionally enhanced by Claude (Anthropic) for Pro tier. Lives entirely in `server.py` plus the static HTML pages.
2. **SellerCopilot PPC Bid Manager** — newer feature (skeleton stage as of 2026-05). OAuth-connects a seller's Amazon account, fetches PPC data, eventually generates bid suggestions. Lives in `ppc_agent.py`, `ppc_oauth.py`, `ppc_ads_client.py`, `ppc_snapshot_fetcher.py`. Mounted onto the Flask app via `ppc_agent.register_routes(app)` from `server.py:847`.

## Run / build / test

```bash
# Local dev — listens on http://localhost:5050
python server.py

# Production (Railway) — Procfile uses gunicorn:
gunicorn server:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120

# Standalone audit CLI (legacy, not the product anymore)
python audit_engine.py [--input path/to/store.json]

# Tests (pytest with mocks; no live HTTP / DB / Amazon creds required)
pytest tests/
pytest tests/test_ppc_oauth.py::test_get_active_token_uses_cache_when_warm
```

There is no linter or formatter configured. There is no requirements lock file — `requirements.txt` lists unpinned ranges.

`FLASK_SECRET_KEY` (≥32 chars) is required at startup or `server.py` raises. `PADDLE_WEBHOOK_SECRET` is required when `SITE_URL` is set (production gate). All other env vars are optional and degrade gracefully — see `.env.example` for the full list. Without `ANTHROPIC_API_KEY` the `/api/diagnose` endpoint silently falls back to rule-based output. Without `DATABASE_URL` the app writes to a local `asininsight.db` SQLite file (gitignored).

## Architecture

### server.py is monolithic on purpose

`server.py` holds the entire web app: DB layer, rate limiters, CSRF, Paddle webhooks, SendGrid drip emails, the rules engine, the LLM enhancer, the admin dashboard, blog routes, and Amazon connection routes. The PPC agent is the only thing factored out. When adding code, match the existing pattern — add a function and a route to `server.py` rather than creating a new module, unless it grows past ~500 lines like the PPC layer did.

### The diagnose pipeline

The product's core flow is `POST /api/diagnose` (`server.py:3139`). The pipeline:

1. **Origin + rate gates** — `_is_same_origin`, `_check_diagnose_rate` (30/hr/IP), free-tier monthly cap (3/month tracked in the `analyses` table).
2. **Input extraction** — `_extract_diagnose_items` (`server.py:2421`) accepts either a raw CSV upload (multipart) or a JSON body. CSV path is gated by `_validate_csv_structure` which requires ≥2 known Amazon Business Report headers in row 1 — this is a security check (rejects binary uploads, header-injection, path-traversal payloads), not just UX.
3. **Column normalization** — `_COL_MAP` (`server.py:2218`) maps every known Amazon report header variant ("Sessions - Total", "Unit Session Percentage", "(Child) ASIN", etc.) to internal canonical names. When you see a parsing bug, this is almost always where to add a mapping.
4. **Numeric parsing** — `_n` and `_r` helpers tolerate `$1,234.56`, `12%`, `0.12`, `(123.45)`, decimal commas. CSV from sellers is messy; never assume clean floats.
5. **Rules engine** — fixed thresholds + category multipliers (`CATEGORY_ACOS_MULTIPLIER`). Severity → score penalty mapping is `PEN = {critical: 26, high: 9, medium: 4, low: 2}` starting from 100.
6. **LLM enhancement** — `_llm_enhance_pro` (`server.py:959`). Pro-only, 8-second hard timeout, swallows failures. Free tier never calls Anthropic.
7. **Persist + return** — `_save_analysis` writes a row to `analyses` for the monthly-cap counter and re-audit drip emails.

The detection layer comment (`server.py:2170`) says "All thresholds are MVP heuristics — label clearly, revisit with real data." Treat threshold tweaks as product decisions, not bug fixes.

### Frontend = static HTML, no build step

`app.html` (the tool), `landing.html`, `pricing.html`, `compare.html`, `demo.html`, `success.html`, `error.html`, etc. are served by `send_from_directory(BASE_DIR, ...)`. They are ~95KB of inline HTML/CSS/JS each. There is no React, no bundler, no SPA framework. The CSV intake parser, ASIN rendering, and benchmark UI all live inside `app.html`. `templates/ppc_dashboard.html` is the only file that uses Jinja (rendered by the PPC blueprint).

When you touch a frontend file, edit the HTML directly. Don't introduce a build step.

### Database layer

`_db()` context manager (`server.py:181`) yields `(cursor, placeholder)` where placeholder is `%s` for Postgres and `?` for SQLite. **Always use the placeholder from the context manager** — every CREATE TABLE in `_init_db()` is duplicated for both dialects (SERIAL vs INTEGER PRIMARY KEY AUTOINCREMENT, JSONB vs TEXT). Follow this pattern when adding tables.

`DATABASE_URL` is normalized from `postgres://` to `postgresql://` because Railway gives the legacy form but psycopg2 requires the new one (`server.py:112`).

### CSRF + same-origin

State-changing POSTs require both:
- `_is_same_origin(req)` — Origin/Referer header check against `SITE_URL`
- `_csrf_valid(req)` — double-submit cookie pattern. Token in non-HttpOnly `_csrf` cookie, must be echoed in `X-CSRF-Token` header (AJAX) or `_csrf` form field.

The frontend reads the cookie in JS and sends the header back. Don't switch to HttpOnly.

### Background workers

Three daemon threads start at import time in `server.py`:
- `_drip_worker_loop` — sends queued drip emails via SendGrid
- Re-audit reminder + retention purge loops (driven from the same worker)
- `_keepalive_loop` — pings `/health` every 4 minutes if `SITE_URL` is set, to keep Railway from idling the dyno

Gunicorn runs with `--workers 1 --threads 4` (see Procfile). The threading model assumes single-process; the in-memory rate limiters, idempotency cache, and PPC token cache will become inconsistent under multi-worker. `ppc_oauth.py` documents this with a TODO for a Redis migration.

### PPC agent (`ppc_agent.py` + neighbors)

Read the module docstrings — they are the design doc. Architecture summary:

- `ppc_agent.py` — Flask Blueprint, DB schema for `amazon_connections` / `ppc_snapshots` / `ppc_suggestions`, Fernet encryption for refresh tokens (`PPC_TOKEN_ENCRYPTION_KEY` env var). Exposes `init_ppc_db(db_cm, database_url)` and `register_routes(app)` called from `server.py`.
- `ppc_oauth.py` — Login With Amazon (LWA) token exchange + refresh + in-memory access-token cache keyed by `connection_id`. Single source of truth for token management.
- `ppc_ads_client.py` — raw HTTP wrapper over the Amazon Ads API. Plugs into `ppc_oauth.get_active_token`. Self-identifies as `SellerCopilot/1.0 (AI Agent)` per Amazon's March 2026 Agent Policy. Retries once on 401 by invalidating the cached token.
- `ppc_snapshot_fetcher.py` — orchestrates the periodic pull (profiles → campaigns → ad groups → keywords → search-term report). Each step wrapped independently — partial snapshots are accepted.

Suggestion generator, applier, and rollback are not yet implemented (weeks 4–6 of the MVP plan).

Hard caps in `ppc_agent.py` (Amazon Agent Policy compliance — don't loosen without checking the policy):
- `MAX_SUGGESTIONS_PER_CUSTOMER_PER_WEEK = 50`
- `MAX_BID_CHANGE_PCT_PER_24H = 20`
- `ROLLBACK_WINDOW_DAYS = 30`

## Conventions worth knowing

- **Threshold/heuristic comments are load-bearing.** Many of the inline comments explain *why* a number was chosen (e.g. "Tier 2 = up to 499 ASINs per batch", "LWA usually responds in <1s; 10s is conservative"). Preserve them when refactoring.
- **Don't pin frontend assets.** Prices, copy, and landing-page numbers (e.g. "2847 + diagnoses_run" baseline in `/admin`) are intentional — they're product/marketing decisions.
- **Free vs Pro gating** lives in two places: the monthly-cap query against the `analyses` table (`server.py:3160`), and the `_llm_enhance_pro` early-return on plan check. Both must agree when changing tier behavior.
- **Owner self-charge guard** — `OWNER_EMAIL` env var blocks Paddle checkout for that address. Don't remove without replacing.
- **Error handling style** — at startup, fail hard (`raise RuntimeError`) for misconfigurations that would break security or payments (missing `FLASK_SECRET_KEY`, missing `PADDLE_WEBHOOK_SECRET` in prod). At request time, log and degrade (e.g. LLM timeout → rule-based output). Match this split.
- **Marketing markdown files** in `marketing/` and the root `*.md` files (asin_mvp_blueprint.md, product_strategy.md, real_data_validation_*.md, etc.) are product/strategy docs, not engineering specs. They drive threshold decisions but don't dictate code structure. `docs_map.md` indexes them.

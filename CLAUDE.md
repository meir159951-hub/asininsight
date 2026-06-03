# CLAUDE.md

This file gives Claude Code persistent context about this project. Claude reads
it automatically at the start of every session.

## Communication preferences (IMPORTANT)

- **Always reply to the owner (Meir) in Hebrew.** This is a standing preference —
  the owner has asked for it repeatedly. Default to Hebrew for all chat replies
  unless explicitly asked otherwise. (Code, identifiers, and commit messages stay
  in English.)

## Project

**SellerCopilot / ASIN Insight** — an Amazon seller product that audits ASIN
listings and runs a PPC (advertising) agent. Currently a Python prototype that
reads demo/CSV ASIN data, diagnoses growth issues, and generates prioritized
reports.

Key files:
- `audit_engine.py` — reads store data and generates the audit report
- `ppc_agent.py`, `ppc_suggestions.py` — PPC optimization agent and suggestions
- `server.py` — main web server
- `app.html` — local browser MVP for CSV upload and ASIN diagnosis

## Agents

### Miro — the lead orchestrator (`miro.py`)
Miro is the **lead agent responsible for everything across the company.** It
does not analyze raw data itself; it **coordinates the specialist agents** and
merges their output into one prioritized briefing — a single "what should I do
next" view across the whole business.

Specialists that run under Miro today:
- **Listing Audit** — wraps `audit_engine.py` (listing health, conversion)
- **PPC** — wraps `ppc_suggestions.py` (ad waste to cut, growth upside)

How it works:
- Each specialist is an agent runner that returns normalized `Finding`s, or
  `None` when its input isn't present.
- `default_miro().run(context)` runs the registered agents, merges their
  findings, and ranks them into one cross-domain priority list (`Briefing`).
- Run the demo: `python3 miro.py`. Tests: `tests/test_miro.py`.

Adding a new specialist (inventory, pricing, reviews, reports) = write a runner
that returns `Finding`s and `register()` it. Miro's merge/rank logic is unchanged.

> Next ideas (not built yet): Inventory agent, Pricing agent, Reviews agent,
> Weekly Reports agent — each plugs into Miro the same way.

## Continuity — read this at the start of every session

Latest lead-agent state lives in **`MIRO_MASTER_BRIEF_2026-06-02.md`**. Open it
first to pick up the current strategic picture.

Headline as of 2026-06-02:
- Code is healthy (380 tests pass), no write path to Amazon — wedge intact.
- **Strategic finding:** the free audit is *bait, not a product.* Helium 10
  gives the same audit free; the paid product must add a **recurring** layer.
- The five unanswered outreach messages = **zero data** (cold-delivery issue),
  not market failure.
- **Owner's chosen direction:** run one **real market test** with warmed-up
  leads before more code or outreach.
- Detailed research lives under `research/` (to be added).

# CLAUDE.md

This file gives Claude Code persistent context about this project. Claude reads
it automatically at the start of every session.

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

### Miro
Miro is the **lead agent responsible for everything across the company** — the
top-level agent that oversees and coordinates the other agents and workflows
(PPC, listing audits, operations).

> TODO (owner: Meir): fill in Miro's exact scope and responsibilities.
> - What specific tasks does Miro own end-to-end?
> - Which other agents/modules does Miro coordinate?
> - How does Miro connect to the existing code (e.g. `ppc_agent.py`, `server.py`)?

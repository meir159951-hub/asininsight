# SellerCopilot — Technical Architecture (MVP)

> **Status:** Draft v1, 2026-05-11
> **Purpose:** Blueprint for building SellerCopilot MVP after customer validation passes.
> **Author:** Claude Code (autonomous research session)
> **Dependencies:** Anthropic Managed Agents (public beta, launched 2026-04-23)

---

## 🎯 What we're building (one paragraph)

A Flask web app where Amazon sellers connect their Seller Central account (OAuth), and a Claude-powered agent with persistent memory analyzes their PPC data, has a conversation with the seller about their goals, remembers every decision made, and proposes bid changes that the seller approves one-by-one. The agent gets smarter month over month because it remembers what worked, what didn't, and what the seller has tried before.

---

## ✅ What we already have in the repo

The PPC skeleton is more complete than expected. Audit of `ppc_agent.py`, `ppc_oauth.py`, `ppc_ads_client.py`, `ppc_snapshot_fetcher.py`:

### Already built (reusable)

| Component | File | Status |
|---|---|---|
| DB schema (6 tables: amazon_connections, ppc_snapshots, ppc_suggestions, ppc_audit_log, ppc_rollback_snapshots, ppc_performance_tracking) | `ppc_agent.py:88-180` | ✅ Production-ready |
| OAuth flow (LWA token exchange + refresh) | `ppc_oauth.py` | ✅ Production-ready, tested |
| Token encryption at rest (Fernet) | `ppc_agent.py:189-208` | ✅ Production-ready |
| In-memory token cache | `ppc_oauth.py:79-280` | ✅ Production-ready |
| Amazon Ads API client | `ppc_ads_client.py` | ✅ Production-ready |
| Snapshot fetcher (campaigns → ad groups → keywords → search-term report) | `ppc_snapshot_fetcher.py` | ✅ Production-ready |
| Flask blueprint integration with `server.py` | `server.py:847` | ✅ Wired |
| Unit tests (OAuth flow) | `tests/test_ppc_oauth.py` | ✅ 4 tests passing |

### Not yet built (this doc covers what to add)

| Component | File | Status |
|---|---|---|
| Suggestion generator (LLM-powered) | `ppc_agent.py:266-268` | ❌ NotImplementedError |
| Suggestion applier (writes to Amazon Ads API) | `ppc_agent.py:275-277` | ❌ NotImplementedError |
| Rollback engine | `ppc_agent.py:284-287` | ❌ NotImplementedError |
| **Memory layer (the differentiator)** | New | ❌ Not started |
| Conversational interface | New | ❌ Not started |
| Decision log UI | New | ❌ Not started |
| Dashboard UI | `templates/ppc_dashboard.html` | 🟡 Stub only |

---

## 🧠 The Memory Layer (the moat)

### Decision: Use Anthropic Managed Agents (not custom infrastructure)

**Why:**
- Memory feature launched 2026-04-23 (public beta)
- $0.08 per session-hour + standard token rates
- Used in production by Netflix, Notion, Rakuten, Asana
- Eliminates $8K-$48K of custom infrastructure (vector DB, observability, etc.)
- For a $89/mo customer: ~$0.40-$5/mo memory cost = sustainable margin

**Alternative considered:** Build memory layer from scratch with Mem0 + pgvector + custom orchestration.
**Rejected because:** Solo founder, no engineering team, 6-12 month competitive window. Time > money.

### How Anthropic Managed Agents memory works

1. Each agent has a workspace-scoped directory at `/mnt/memory/` (or `/memories/` in Claude API).
2. Claude can `read_file`, `write_file`, `list_files`, `delete_file` autonomously.
3. Memory persists across sessions — start a new conversation with the same agent, memories load automatically.
4. Storage is text-based (markdown files, structured data).
5. We don't write the memory logic — Claude decides what to remember.

### Memory structure for SellerCopilot (proposed)

```
/mnt/memory/seller_{customer_id}/
├── profile.md                    # Brand name, category, goals, ACOS target
├── decisions/
│   ├── 2026-05-11_paused_campaign_xyz.md
│   ├── 2026-05-12_increased_bid_keyword_abc.md
│   └── ...
├── learnings/
│   ├── seasonality.md            # "Q4 traffic +40%, Q1 -25%"
│   ├── what_works.md             # "Long-tail keywords convert 3x better"
│   └── what_doesnt.md            # "Sponsored Brands wasted $500 in March"
├── strategy.md                   # "Don't scale SKUs below 25% margin"
└── conversation_history.md       # Summary of last N sessions
```

**Memory is workspace-scoped per customer.** No data bleeds between customers.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Seller (Browser)                      │
└──────────────┬──────────────────────────────────────────┘
               │ HTTPS
┌──────────────▼──────────────────────────────────────────┐
│           Flask App (server.py + ppc_agent.py)          │
│  Routes: /ppc/dashboard, /ppc/chat, /ppc/approve         │
└──┬───────────────┬───────────────┬──────────────────────┘
   │               │               │
   │ OAuth         │ Data fetch    │ Agent invocation
   │               │               │
   ▼               ▼               ▼
┌─────────┐  ┌──────────────┐  ┌─────────────────────────┐
│  LWA    │  │ Amazon Ads   │  │ Anthropic Managed       │
│ (OAuth) │  │     API      │  │ Agents (Claude Sonnet)  │
└─────────┘  └──────────────┘  │ + Persistent Memory     │
                               └─────────┬───────────────┘
                                         │
                                         ▼
                           ┌─────────────────────────────┐
                           │ /mnt/memory/seller_{id}/    │
                           │ Markdown files, per-seller  │
                           └─────────────────────────────┘
   ▼ (App-side persistence)
┌──────────────────────────────────────────────────────────┐
│  Postgres (Railway)                                       │
│  - amazon_connections (encrypted refresh tokens)          │
│  - ppc_snapshots (raw Amazon Ads data)                    │
│  - ppc_suggestions (proposed actions)                     │
│  - ppc_audit_log (every action ever)                      │
│  - ppc_rollback_snapshots (30-day rollback window)        │
│  - ppc_performance_tracking (did suggestions work?)       │
└──────────────────────────────────────────────────────────┘
```

---

## 🔄 User Flow (MVP)

### First-time seller

1. Seller lands on `/ppc/connect` → clicks "Connect Amazon"
2. Redirect to Amazon Seller Central consent screen
3. Seller approves → callback to `/ppc/oauth/callback`
4. App exchanges code for refresh_token → encrypts → stores in DB
5. Background snapshot fetch starts (`fetch_ppc_snapshot`)
6. Once snapshot ready (1-5 min), redirect to `/ppc/dashboard`
7. Dashboard says: *"I've pulled your last 30 days. Let me ask you 3 questions to understand your goals."*
8. Claude agent runs first conversation → writes `profile.md` to memory
9. Agent proposes 5-10 suggestions → seller approves one-by-one
10. Each approval logs to `ppc_audit_log` + appends to `decisions/` in memory

### Returning seller (this is where the moat kicks in)

1. Seller lands on `/ppc/dashboard`
2. Agent reads memory **before** the conversation starts:
   - Loads `profile.md`, recent `decisions/`, `learnings/`, `strategy.md`
3. Agent greeting: *"Last time you paused the X campaign because margins were tight. ACOS on Y went from 45% to 38% — your hero-image fix is working. I see 3 new opportunities."*
4. This greeting is **physically impossible** for stateless tools like Adtomic.

---

## 💰 Cost Model (per customer, monthly)

Assuming a $89/mo Pilot tier customer using the agent ~10 sessions × 30 minutes:

| Item | Cost |
|---|---|
| Managed Agents session hours (5 hours/mo) | $0.40 |
| Claude Sonnet 4.6 inference (~500K tokens) | $4-7 |
| Amazon Ads API calls | $0 |
| Postgres storage (Railway) | <$1 |
| LWA token refresh | $0 |
| **Total cost per customer/month** | **~$5-8** |
| **Revenue per customer/month** | **$89** |
| **Gross profit** | **~$81** |
| **Gross margin** | **~91%** |

**Notes:**
- Cost scales with usage. Power users may cost $15-20/mo. Still 80%+ margin.
- Fixed costs (Railway, domain, monitoring): ~$50/mo total, negligible per customer at scale.

---

## 📅 Build Plan (10-week MVP)

### Week 1-2: Validation gate (DO NOT SKIP)

- 10 customer conversations / forum survey responses
- Validate: do sellers actually want "memory of decisions"?
- Validate: is $89 the right price?
- **Gate:** 5+ "I'd pay for this" responses with concrete use cases. If <5, stop and reframe.

### Week 3-4: Agent backbone

- Integrate Anthropic Agent SDK (Python) into `ppc_agent.py`
- Add `/ppc/chat` route with streaming response
- Implement memory structure (folders, file naming)
- Test memory persistence across sessions (write a memory in session 1, verify it loads in session 2)
- **Deliverable:** seller can have a conversation, agent remembers across sessions

### Week 5-6: Suggestion engine

- Replace `NotImplementedError` in `generate_suggestions()`
- Agent reads recent `ppc_snapshots` + memory → outputs structured suggestions
- Each suggestion goes to `ppc_suggestions` table with `status='pending'`
- Dashboard shows pending suggestions, seller approves one-by-one
- **Deliverable:** seller sees real suggestions tied to their data

### Week 7: Applier + rollback

- Implement `apply_suggestion()` — writes to Amazon Ads API
- Implement snapshot-before-apply (`ppc_rollback_snapshots`)
- Implement `rollback_suggestion()` for 30-day undo
- Implement Amazon Agent Policy hard caps (50/week, 20%/24h)
- **Deliverable:** changes actually apply to seller's Amazon account, with safety

### Week 8: Performance tracking

- After each applied suggestion, schedule a 7-day and 30-day check
- Compare metric value to baseline → log to `ppc_performance_tracking`
- Agent reads tracking data on next session → updates `learnings/` in memory
- **Deliverable:** agent demonstrably learns from outcomes

### Week 9: UI polish

- Build out `templates/ppc_dashboard.html`
- Decision log (chronological view of every approved action)
- Memory inspector ("what does the agent remember about my business?")
- This is **the visible differentiator.** Make it obvious.

### Week 10: Beta launch

- 5 design partners (free or $29 founder tier)
- Daily check-ins for first 2 weeks
- Tight iteration on what works

---

## 🚨 Compliance (Amazon Agent Policy, March 2026)

Already documented in `ppc_agent.py:76-81`:

| Rule | Constant | Enforcement |
|---|---|---|
| Max 50 suggestions per customer per week | `MAX_SUGGESTIONS_PER_CUSTOMER_PER_WEEK = 50` | Check before `apply_suggestion` |
| Max 20% bid change per 24h | `MAX_BID_CHANGE_PCT_PER_24H = 20` | Check before `apply_suggestion` |
| 30-day rollback window | `ROLLBACK_WINDOW_DAYS = 30` | `ppc_rollback_snapshots.expires_at` |
| Self-identify as AI Agent | `USER_AGENT = "SellerCopilot/1.0 (AI Agent)"` | Set in `ppc_ads_client.py:70` |

**Don't loosen any of these without checking the policy.** Amazon can revoke API access.

---

## 🔐 Security Considerations

1. **OAuth tokens encrypted at rest** — already done via Fernet.
2. **Memory is per-customer scoped** — Anthropic enforces workspace isolation.
3. **No memory leakage in logs** — never log memory contents.
4. **Audit log is append-only** — `ppc_audit_log` records every applied action.
5. **CSRF + same-origin** — already enforced in `server.py`.
6. **Hard rate limits** — already in place for `/api/diagnose`. Extend pattern to `/ppc/*`.

---

## 🚦 What This Architecture Does NOT Try to Solve (yet)

- **Multi-marketplace** — US-only first. EU/JP later.
- **Sponsored Brands / Sponsored Display** — Sponsored Products only for MVP.
- **DSP/AMC** — Amazon owns this with Ads Agent. We don't compete here.
- **Multi-seat (agency tier)** — solo seller only for first 90 days.
- **Mobile app** — web-only.
- **White label** — wait for $199 Agency tier signal.

---

## 🧪 Open Technical Questions (resolve during week 3-4)

1. **Memory size limits in Managed Agents** — what's the practical limit per workspace?
2. **Streaming vs batch agent invocation** — does Managed Agents support streaming for chat UX?
3. **Tool use cost** — when agent uses tools (DB queries, Ads API), how is it priced?
4. **Rate limits on Managed Agents** — concurrent agents per organization?
5. **Memory portability** — if we leave Anthropic, can we export memory? (Acceptable lock-in?)

These don't block the MVP but should be answered before scaling.

---

## 📚 Resources

- [Claude Agent SDK Python (GitHub)](https://github.com/anthropics/claude-agent-sdk-python)
- [Memory Tool Docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Managed Agents Overview](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Amazon Ads API Docs](https://advertising.amazon.com/API/docs/en-us/)

---

*This doc is a draft. Update as decisions are made during build. The 10-week plan is a target, not a contract — slip is expected and acceptable.*

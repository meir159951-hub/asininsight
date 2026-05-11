# SellerCopilot — Product Requirements Document (One-Pager)

**Status:** v1, 2026-05-11 | **Author:** Claude Code | **Owner:** Meir

---

## 1. The Problem

Amazon sellers spending $5K-$50K/month on PPC are stuck choosing between:
- **Cheap rule-based tools** ($49-$229/mo) that give generic advice ignoring their business context
- **Expensive automation** ($500-$895/mo) that runs hands-off but provides no insight or strategic input
- **Human agencies** ($500-$5,000/mo) that frequently underperform and disappear after 6 months

Every existing tool restarts cold each session. None remember the seller's strategic decisions, what was tried before, what worked, what didn't.

---

## 2. The Solution

**SellerCopilot** — a conversational AI agent built on Claude Sonnet 4.6 + Anthropic Managed Agents, with persistent memory per seller.

The agent:
- Reads the seller's account once and builds a profile
- Has actual conversations: "What should I focus on this month?"
- Remembers every decision: "We paused this campaign in March because margins were tight"
- Learns over time: "ACOS bid increases above 15% never worked in your category"
- Proposes changes one-by-one with reasoning; seller approves
- Never auto-applies (Amazon Agent Policy compliance)

---

## 3. Target Customer (ICP)

**Primary:** Solo or 2-5 person Amazon brand owner
- Revenue: $25K-$250K/mo GMV
- Ad spend: $5K-$50K/mo
- 5-50 SKUs in private label
- Already paying $200-$600/mo on Helium 10/JS/repricer
- Wants to stay informed, not delegate completely
- US-first

**Secondary:** Boutique PPC agencies (2-20 clients) — $199 Agency tier

**NOT for:** New sellers (<$1K/mo), aggregators, sellers wanting hands-off black box

---

## 4. The Wedge (Why we win)

> **"The only PPC tool you can have a real conversation with — about your business, your decisions, your goals — and it remembers everything."**

3 pillars:
1. **Conversation** — chat interface, not dashboard
2. **Memory of decisions** — strategic context persists forever
3. **Honest reasoning** — shows work, admits uncertainty, never blames Amazon

**Defensible because:**
- Competitors (Astra, AutoPilot) optimize TACTICS, we optimize STRATEGY
- Helium 10/Trellis won't drop their $200+/mo to compete (Innovator's Dilemma)
- Amazon's own Ads Agent targets DSP/AMC enterprise, not SP solo sellers

---

## 5. Pricing

| Tier | Price | What's included |
|---|---|---|
| **Free Audit** | $0 | One-time PPC audit (uses ASINInsight CSV path) |
| **Pilot** | $89/mo | Full agent, 1 Amazon connection, unlimited conversations |
| **Operator** | $149/mo | Pilot + advanced reporting, multi-marketplace |
| **Agency** | $199/mo | Up to 5 client accounts, white-label option |

**Validation gate:** Must be confirmed by 5+ "I'd pay $89/mo" responses from real sellers before launch.

---

## 6. MVP Scope (10 weeks)

**In scope:**
- Single Amazon connection per customer (US Sponsored Products only)
- Conversational chat (Claude Sonnet 4.6 + Anthropic Managed Agents memory)
- Bid change suggestions with seller approval
- Decision log + memory inspector UI
- 30-day rollback for any approved change
- Amazon Agent Policy compliance (rate caps, identification, cease-on-request)

**Out of scope (v1):**
- Multi-marketplace
- Sponsored Brands / Display
- DSP / AMC
- Multi-seat / agency tier
- Mobile app
- Auto-apply (always human-approved per Amazon policy)
- Listing optimization (separate ASINInsight product handles this)

---

## 7. Key Metrics (north star)

**Activation:** % of signups who complete first conversation + approve at least 1 suggestion
- Target: 60%+

**Retention:** % of customers active month 2 of subscription
- Target: 70%+

**Revenue:** MRR
- Month 3: $1K MRR (10 paying customers)
- Month 6: $5K MRR
- Month 12: $25K MRR (~280 paying customers)

**Engagement (the moat metric):** Memory hit rate
- % of agent responses that reference past memory
- Target: 60%+ by month 2 of customer's tenure

---

## 8. Tech Stack (decided 2026-05-11)

| Component | Tool | Why |
|---|---|---|
| LLM | Claude Sonnet 4.6 | Best price/perf for conversational agents |
| Agent runtime | Anthropic Agent SDK (Python) | Direct integration, control |
| Memory | Anthropic Managed Agents (memory feature) | Built-in, $0.08/session-hour, no infrastructure |
| Web framework | Flask (existing) | Already in repo |
| DB | Postgres on Railway (existing) | Already in repo |
| Amazon API | Amazon Ads API + LWA OAuth (existing) | Already in repo |
| Frontend | Static HTML + JS (existing pattern) | No build step, fast |

**No new infrastructure required beyond what's in the repo.**

---

## 9. Risks (top 3)

1. **Customer validation fails** — sellers don't actually want "memory" enough to switch tools.
   *Mitigation:* Validation surveys before any code. Decision gate at week 2.

2. **Amazon revokes API access** — agent policy violation.
   *Mitigation:* Hard caps already in `ppc_agent.py`. Compliance audit before launch.

3. **Anthropic Managed Agents pricing changes** — bills become unsustainable.
   *Mitigation:* Cost monitoring per customer. Fallback architecture using direct Claude API + custom file-backed memory if needed.

---

## 10. Validation Gate (DO NOT SKIP)

Before any code beyond what's in the repo today:

✅ **Go signal:** 5+ specific "yes I'd pay $89/mo" responses from real sellers, with concrete examples of what they want the agent to remember
🟡 **Pivot signal:** 2-4 "interesting but..." responses → reframe positioning
❌ **Stop signal:** <2 substantive responses or all negative → reconsider entire direction (perhaps return to ASINInsight CSV product)

---

*This is a living doc. Update with every major decision.*

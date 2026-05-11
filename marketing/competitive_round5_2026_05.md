# Round 5 Research — New Competitors + Amazon MCP Server

> **Date:** 2026-05-11
> **Round 5 of 5 in autonomous research session**
> **Major discovery:** Amazon launched MCP Server (Feb 2026) — changes integration architecture

---

## 🔥 The Biggest Discovery — Amazon Ads MCP Server (Feb 2, 2026)

Amazon opened the **Ads MCP Server** to open beta on **February 2, 2026**.

### What it is
> *"The Amazon Ads MCP Server provides a standardized access layer built on the Model Context Protocol that connects AI agents to Amazon Ads API functionality, transforming complex API operations into conversational queries."*

### Why this is huge for SellerCopilot

**MCP (Model Context Protocol) is the same protocol that Anthropic's Claude Agent SDK uses.**

This means:
- **No custom HTTP wrapper code needed** for Amazon Ads API
- Claude agent can talk to Amazon Ads **directly** via MCP
- Anthropic SDK + Amazon MCP Server = native integration
- Operations become conversational queries: *"Pause campaigns with ROAS < 2"*

### Architecture impact

**Before this discovery:**
```
Claude Agent → custom Python wrapper → Amazon Ads HTTP API
```

**With MCP Server:**
```
Claude Agent ← MCP protocol → Amazon Ads (Amazon-managed)
```

**Implication for `technical_architecture_mvp.md`:** The Week 5-6 build of `apply_suggestion()` can use MCP instead of raw HTTP. **Reduces build time significantly** and reduces compliance risk (Amazon's MCP server enforces Agent Policy automatically).

### Open question

Does MCP Server enforce the rate caps (50/week, 20%/24h) automatically, or do we still need to do it client-side?

**Action:** Investigate during build phase. If Amazon enforces server-side, we can remove our enforcement code (or keep it as belt-and-suspenders).

---

## 🆕 Other New Competitors Found

### Daniks.AI
- **Founder story:** Built after managing nearly $1M in their own Amazon ad spend
- **Positioning:** "AI Agent for Perfect ACoS"
- **Differentiator:** Founder-operator credibility
- **Threat level:** 🟡 Medium — similar AI-agent pitch, smaller scale

### Mayan
- **Built by:** MIT data scientists
- **Positioning:** "Business-objective-aware AI" with PPC expert support
- **Pricing:** Not public
- **Threat level:** 🟡 Medium — strong tech credibility, but support-heavy (agency-ish)

### FBAExcel Amazon FBA Copilot
- **Type:** Chrome extension (not SaaS)
- **Different category** — not direct competition
- **Threat level:** 🟢 Low

### m19 (re-confirmed)
- **Pricing:** $479/mo + ad spend
- **Type:** Autopilot bid optimization
- **Threat level:** 🟢 Low (different price band, different category)

### BidX
- **Pricing:** $495/mo + percentage of ad spend
- **Type:** Rule-based with ChatGPT suggestions
- **German company, popular in Europe**
- **Threat level:** 🟡 Medium — they have "AI suggestions" but on rules, not memory

### Adbrew
- **Pricing:** $499/mo or % of ad spend
- **Type:** Rule-based + dayparting
- **Threat level:** 🟢 Low (different category — rules, not conversational)

### Amazon Seller Assistant (Amazon's own)
- **230,000 monthly users in 2025**
- **90% recommendation acceptance rate** (this is significant social proof for AI in Amazon tools)
- **Free** (part of Seller Central)
- **Threat level:** 🟠 High — but for general seller help, not PPC specifically

### Amazon Dynamic Canvas (launched March 3, 2026)
- **AI-powered visual workspace** inside Seller Central
- **Tied to Seller Assistant**
- **Threat level:** 🟡 Medium — Amazon expanding native AI

---

## 📊 Updated Competitor Pricing Map (May 2026)

| Tool | Price/mo | Type | "Memory"? | Conversational? |
|---|---|---|---|---|
| **SellerCopilot (proposed)** | **$89** | **Conversational agent** | **✅ Persistent** | **✅** |
| Adtomic (Helium 10) | $129+ | Rules + bulk ops | ❌ | ❌ |
| Adbrew | $499+ | Rules + dayparting | ❌ | ❌ |
| m19 | $479+ | ML autopilot | Algorithm-level | ❌ |
| BidX | $495+ | Rules + ChatGPT | ❌ | 🟡 Suggestions |
| Astra by Sellrbox | Free–$? | ML hourly bids | Algorithm-level | ❌ |
| AiHello AutoPilot | $695+ | ML autopilot | Algorithm-level | ❌ |
| Profasee Marko | $399+ | Multi-modal (pricing+ads) | Algorithm-level | ❌ |
| Quartile | $895+ | Enterprise ML | Algorithm-level | ❌ |
| Trellis | Custom | Enterprise multi-modal | Algorithm-level | ❌ |
| Pacvue | $500+ | Enterprise dashboard | ❌ | ❌ |
| Daniks.AI | TBD | Agent (founder-led) | Unknown | 🟡 Likely |
| Mayan | Custom | AI + experts | Unknown | 🟡 Likely |
| Amazon Seller Assistant | Free | General AI in Seller Central | 🟡 Partial | ✅ |
| Amazon Ads Agent | Free* | DSP/AMC AI | 🟡 Partial | ✅ |

*Free but requires Amazon account-manager access

---

## 🎯 Refined Competitive Position

### What's still defensible
1. **Conversational** ✅ — most competitors are dashboards/automation, not chat
2. **Persistent memory of DECISIONS** ✅ — algorithmic memory ≠ decision memory
3. **Price band $89-149** ✅ — gap below $479-695 mid-tier
4. **Independent (not Amazon-owned)** ✅ — Amazon's tools serve Amazon's interests

### What's getting riskier
1. ⚠️ Daniks.AI and Mayan are positioned similarly — need to monitor
2. ⚠️ Amazon Seller Assistant 90% acceptance rate proves users trust AI in this space — but Amazon owns the channel
3. ⚠️ Amazon Ads MCP Server makes integration easier for ALL competitors

### What's actually accelerated us
1. ✅ **Amazon MCP Server reduces our build complexity** — Week 5-6 simpler
2. ✅ **Amazon Seller Assistant 230K users validates the market** — AI in Amazon tools works
3. ✅ **The $479-695 mid-tier confirms our $89 price has room** — sellers ARE willing to pay for these tools

---

## 🚦 Updated Decision Matrix

### Go signals (after this research)
- ✅ MCP Server reduces tech risk
- ✅ Market validated (Amazon Seller Assistant 90% follow-rate)
- ✅ Price gap real ($89 vs $479+ mid-tier)
- ✅ Conversational + memory + decision-log still empty in market

### Caution signals
- ⚠️ Multiple AI-agent startups in same space (Daniks, Mayan)
- ⚠️ Amazon expanding native AI rapidly
- ⚠️ Window may be 6-9 months, not 12

### Stop signals
- None new

**Recommendation:** Continue, but **move faster.** The 10-week MVP plan should be 8-9 weeks if possible.

---

## 📋 Actions This Round Creates

### Update technical_architecture_mvp.md
Add to Week 5-6 build plan:
> "Investigate Amazon Ads MCP Server (https://ppc.land/amazon-opens-its-advertising-apis-to-ai-agents-through-industry-protocol/) as integration path. May replace custom HTTP wrapper in ppc_ads_client.py."

### Update risk_register.md
Add new risk:
> **R16: AI-agent startups (Daniks, Mayan) reach PMF first**
> Likelihood: 3/5 | Impact: 3/5 | Score: 9
> Mitigation: Speed to validation. Distinctive positioning (honest AI, not just AI agent).

### Update PROJECT.md
Add to "מצב נוכחי" section:
> "Tech stack updated 2026-05-11 with Amazon MCP Server discovery — enables direct Claude→Amazon Ads integration via MCP protocol. Reduces custom code in `ppc_ads_client.py` for Week 5-6 build."

---

## 🔗 Sources

- [Amazon Opens Ads APIs to AI Agents (PPC.land)](https://ppc.land/amazon-opens-its-advertising-apis-to-ai-agents-through-industry-protocol/)
- [Amazon Launches Closed Beta for AI Agent Advertising](https://ppc.land/amazon-launches-closed-beta-for-ai-agent-advertising-integration/)
- [Daniks.AI — Best Amazon PPC Tools 2026](https://daniks.ai/blog/best-amazon-ppc-tools-2026)
- [Autron — What Ads Agent and MCP Server Mean for Sellers](https://autron.ai/blog/amazon-ppc-automation-in-2026-what-the-ads-agent-and-mcp-server-mean-for-sellers)
- [m19 Amazon PPC Pricing](https://www.m19.com/pricing-automated-ppc-campaigns)
- [BidX Review 2026](https://ppctools.online/reviews/bidx-review/)
- [Adbrew Pricing](https://adbrew.io/)
- [Mayan — AI Seller Tools](https://www.mayan.co/)
- [PYMNTS — Amazon Sellers Gain Sales With AI Tools](https://www.pymnts.com/amazon/2026/amazon-sellers-gain-sales-and-cut-costs-with-ai-tools/)

---

*Round 5 complete. The competitive picture is sharper. The wedge survives. Time to move.*

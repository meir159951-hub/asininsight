# ASINInsight — Positioning & Differentiation
*Draft v1, April 2026. Iterate after deeper research.*

---

## The Wedge (One Sentence)

> **The audit your agency charges $1,500 for — without the sales call. Upload your Business Report, get a numbered fix list in 60 seconds. We don't grade. We prescribe.**

This statement is built from four findings:
1. Sellers compare *upward* (against agencies at $1,500–$3,000/audit), not sideways (against Helium 10's $129/mo)
2. The diagnosis gap — not "more keywords" — is the largest unmet pain
3. Privacy / no-OAuth is the structural moat (no incumbent can replicate without rebuilding their data model)
4. "Prescribe, don't grade" is the qualitative differentiator vs every existing tool

## Three Things ASINInsight Does That Nobody Else Does

| # | Differentiator | Why it's defensible |
|---|---|---|
| 1 | Reads the **private** Detail Page Sales and Traffic CSV | Public-page scrapers (AuditMyListing, Trellis, SellerApp) cannot see real conversion. SP-API tools (Helium 10, Jungle Scout) require token. We need neither. |
| 2 | **Severity-ranked, numbered action plan** ("Critical CTR — fix this first") | Every competitor outputs a score (0–100). Nobody gives ranked, prioritized prescriptions in plain English. |
| 3 | **Zero login. Zero data leaves the browser.** | Trust signal in a market where Helium 10's #1 review complaint is dark-pattern billing and unauthorized account changes. |

## Anti-Positioning (What We Are NOT)

- **Not another all-in-one suite.** No keyword research, no inventory tracker, no PPC manager. *One job, done well.*
- **Not Helium 10 / Jungle Scout lite.** Different category — diagnostic tool, not seller suite.
- **Not an AI rewrite tool.** No GPT-magic listing copy. The differentiator is *what to fix*, not *how to write a title*.
- **Not for new sellers.** The buyer has data; new sellers have nothing to diagnose.

## Messaging Framework

### Top of funnel (pain-trigger SEO + ads)
- "FBA sales dropped overnight"
- "Why is my ACOS so high"
- "Conversion rate dropped Amazon"
- "How to read Amazon Business Report"
- "Amazon listing audit free"

Headline tests:
- *"You already have the data. We read it for you."*
- *"Stop guessing. Upload your Business Report."*
- *"The 60-second audit your agency charges $1,500 for."*
- *"Find what's killing your ASIN — before your next ad spend."*

### Middle of funnel (homepage / landing)
**Hero:** Your Business Report already has the answer. We just tell you which line.

**Sub-hero:** Upload the Detail Page Sales and Traffic CSV. Get a numbered fix list — by severity — in under a minute. No login. Nothing leaves your browser. Free to start, no credit card.

**Three-pillar trust strip:**
1. 🔒 **No Amazon login.** No SP-API, no scraping, no tokens. Your data never touches an external server.
2. 🎯 **Prescription, not grading.** Critical issues, ranked. Plain English. Fix-this-first language.
3. 💸 **One-click cancel.** No retention calls. No forced renewal.

### Bottom of funnel (pricing page)
- $49/mo Pro: "Unlimited audits. The audit your agency charges $1,500 for."
- $199/mo Agency: "Audit every client without asking for SP-API access."
- Free 3 audits/month: "Try it before you trust it."

## Voice & Tone

| Do | Don't |
|---|---|
| Direct, plain English ("your CTR is bleeding") | Marketing fluff ("optimize your sales velocity") |
| Numbers ("ACOS dropped from 75% → 42%") | Vibes ("dramatic improvement") |
| Match seller frustration ("you've tried every YouTube tip") | Talk down ("here's how Amazon works…") |
| Stakes-clear ("you're losing $260/mo to PPC waste") | Hedge ("you may want to consider…") |

Mirror the language sellers actually use:
- "Sales tanked" / "tanked overnight"
- "ACOS is bleeding"
- "Flying blind on PPC"
- "Burned by my agency"
- "I don't know what to fix first"

## Channel Strategy (Launch Sequence)

### Weeks 0–4 — Seed & Credibility
1. Daily public ASIN teardowns on Twitter/X + LinkedIn (build a portfolio of 30 case studies, no CTA)
2. Soft-presence in r/FulfillmentByAmazon — answer diagnosis questions with genuine depth
3. Pitch Marketplace Pulse a guest data piece: "Listing-error rates across 10K ASINs"
4. Build relationships with My Amazon Guy + 2 mid-tier creators (no ask yet)

### Weeks 4–8 — Community Drop
5. Coordinate AMA in r/FulfillmentByAmazon with mods
6. Sponsor 2 podcast episodes (Serious Sellers and/or Seller Sessions, ~$1–3K each)
7. Sponsored teardown video on My Amazon Guy or Brock Johnson channel

### Weeks 8–16 — Scale
8. Product Hunt launch (credibility/backlinks, not volume)
9. AppSumo **Agency-tier-only** lifetime deal at $69, capped 500 codes (cash + agency seeding without cannibalizing $49 Pro MRR)
10. Reddit Ads sub-targeting r/FBA at $10 CPM
11. Meta lookalikes off Helium 10 / Jungle Scout fan custom audiences

### Weeks 16+ — Compound
12. Affiliate program for FBA High Rollers FB community influencers
13. DE + UK localized pricing pages (Germany is the underrated #2)
14. "$0 → $X ARR" milestone post on Indie Hackers / HN (only as milestone, never as launch)

## Pricing Rationale

| Tier | Price | Anchor |
|---|---|---|
| Free | $0 (3 audits/mo) | Mirrors AuditMyListing's validated funnel |
| Pro | $49/mo | Universal "real seller" anchor (Helium 10 Starter, Jungle Scout Starter, ZonGuru Seller) |
| Agency | $199/mo | Sits cleanly between Threecolts Pro ($199) + Viral Launch Pro Plus ($199); undercuts Helium 10 Diamond ($359) |

**Key pricing principle:** never compare downward to free tools. Always compare upward to $1,500/audit agency retainers. Cheap-looking pricing kills B2B trust.

## What We Cannot Yet Validate

These remain hypotheses until launch data confirms:
1. Does the privacy framing actually convert, or do sellers shrug?
2. Will agencies pay $199/mo, or only one-time per client?
3. Does the "sudden drop" SEO play actually rank?
4. Is $49 too cheap (perceived as toy) or too expensive (vs. Sellerboard $19 anchor)?
5. Will Reddit/podcast moves break through the no-promo culture, or get banned?

## Risks To Manage

| Risk | Mitigation |
|---|---|
| "CSV-only" framed as a limitation by competitors | Reframe with privacy + zero-trust copy upfront |
| Free tier audited heavily, low conversion | Cap free at 3/mo per browser session (already in code) |
| Helium 10 launches a "no-OAuth diagnostic" feature | They won't — their data model can't. Even if they try, ASINInsight already owns the privacy story |
| AppSumo LTD cannibalizes Pro MRR | Restrict LTD to Agency tier only |
| Solo-founder bandwidth on customer support | Drip emails + self-serve help docs; avoid Slack/Discord communities until $50K ARR |

---

*This positioning is a v1 hypothesis based on Round 1 research. Sharpen after deeper customer interviews and the next research wave (see open questions in `market_research.md`).*

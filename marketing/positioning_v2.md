# ASINInsight — Positioning v2 (Sharpened)
*Updated April 2026 with all Round 2 evidence.*
*Supersedes `positioning.md` v1.*

> **⚠️ TRUTH-ALIGNMENT NOTE (Apr 27 2026):** The product processes the CSV server-side, holds it in memory only, and discards it immediately after the response. It does NOT run client-side. All copy below has been corrected from earlier "nothing leaves your browser" claims to the truthful "deleted in seconds, never stored, never shared, no SP-API, no Amazon login, no card."

---

## The Wedge — Final Statement

> **ASINInsight is the only Amazon-listing audit tool that reads the seller's private Detail Page Sales and Traffic CSV — without an Amazon login, without SP-API, without a credit card — and outputs a severity-ranked numbered fix list in plain English in under 60 seconds. The CSV is processed in memory and immediately discarded; nothing is stored, logged, or used to train AI.**

This is defensible on **three legs**:
1. **Zero-trust ingestion** — every competitor either requires SP-API (Helium 10, Jungle Scout, ZonGuru, SellerApp, Trellis) or scrapes only public ASIN pages (AuditMyListing). Nobody else accepts the private CSV with no Amazon credentials, no card, no signup before value. Files are never persisted — they exist for the duration of one HTTPS request, then are garbage-collected from RAM.
2. **Output format** — every competitor outputs a *score* or *dashboard*. Nobody outputs a numbered, severity-ranked, plain-English action plan. Scores create anxiety; numbered lists create movement.
3. **Anti-funnel** — every competitor follows "gate first → audit second" (signup, OAuth, demo call). The cancellation-trap reviews on every one of them are not coincidence. ASINInsight runs the opposite funnel: audit before signup, email at PDF export, card at >3/mo.

---

## The Hero (Recommended Primary)

> **Drop your Sales & Traffic CSV. Get a numbered fix list in 60 seconds.**
> No Amazon login. No SP-API. No credit card. CSV deleted instantly — never stored, never shared.

### Alternative tested-against headlines (use as ad creative)

- *"The Amazon listing audit that doesn't need your Seller Central password."*
- *"Stop guessing. Your Business Report already has the answer."*
- *"The 60-second audit your agency charges $1,500 for."*
- *"Your sales dropped overnight and you don't know why. We do — in 60 seconds."*
- *"You're getting clicks but no orders. Here's the exact reason."*

### Pain-trigger headlines (for paid search landing pages)

Map each ad-group to the verbatim phrases from `voice_of_customer.md`:

| Google query targeted | Landing-page H1 |
|---|---|
| "FBA sales dropped overnight" | "Your FBA Sales Dropped Overnight? Here's the 60-Second Test." |
| "Amazon ACOS too high" | "Amazon ACOS Bleeding? Find Out If It's Your Listing or Your Bids." |
| "high CTR low conversion Amazon" | "Getting Clicks but No Orders? Your Listing Is Telling You Why." |
| "Helium 10 alternative" | "Helium 10 at $129? ASINInsight's $49 Audit Beats Their Listing Builder." |
| "Amazon listing audit free" | "Free Amazon Listing Audit. Reads Your Real Data. CSV Deleted Instantly After Diagnosis." |

---

## Three-Pillar Trust Strip (For Hero Section)

These directly map to the cancellation-complaint pile against Helium 10/JS/ZonGuru on Trustpilot:

🔒 **No Amazon login.** No SP-API, no scraping, no tokens. Your CSV is processed in seconds and deleted — never stored, never shared, never used to train AI.

🎯 **Prescription, not grading.** Critical issues, ranked by severity. Plain English. Fix-this-first language.

💸 **One-click cancel.** No retention calls. No forced renewal. No charges after canceling.

---

## Anti-Positioning — What ASINInsight Is NOT

- **Not another all-in-one suite.** No keyword research, no inventory tracker, no PPC manager. *One job, done well.*
- **Not Helium 10 / Jungle Scout lite.** Different category — diagnostic tool, not seller suite.
- **Not an AI rewrite tool.** No GPT-magic listing copy. The differentiator is *what to fix*, not *how to write a title*.
- **Not for new sellers.** The buyer has data; new sellers have nothing to diagnose.

---

## ICP — The Buyer (Sharpened with Round 2 Evidence)

### Primary Pro Persona — "The Scaling Private-Label Operator"

- **Revenue tier:** $25K–$250K/month GMV
- **Why this tier:** $49/mo is ~0.05% of revenue — trivial decision. The $1K–$25K tier balks at $49; the $100K+/month tier expects more depth.
- **Profile (from Q24, Q29, Q32 in voice_of_customer):** Solo or 2–5 person brand. 5–50 SKUs in private label. Long, analytic forum posts with revenue + ROAS/ACOS numbers. Names specific tools.
- **Geography:** US-first (~58% of sellers). Then UK + Germany.
- **Existing tool stack:** $200–$600/month already going to Helium 10 / Jungle Scout / repricer / inventory tool. ASINInsight is "the listing-audit slot."
- **Decision style:** Self-serve trial-buy in 3–10 days.
- **The Q24 headline they're walking around with:** *"All my revenue is going straight back into ads."*

### Secondary Agency Persona — "The Boutique Amazon Agency"

- 50+ US Amazon agencies, sub-100-client size. My Amazon Guy is reference (~$1.4B managed, 400+ clients).
- Privacy / no-OAuth is huge — they often can't get SP-API access from prospects.
- Highest LTV segment.
- Two distinct sub-segments:
  - **For brands burned by agencies (Q32, Q34):** ASINInsight is the *transparency layer* used to verify the agency is doing real work
  - **For agencies themselves:** ASINInsight is the *white-label tool* to deliver auditable reports to clients

### Anti-ICP (Do NOT Target at Launch)

- Brand-new sellers ($0–$1K/mo) — won't pay $49
- Aggregators (Thrasio etc.) — in-house tooling
- Chinese sellers — price-sensitive, language barrier
- Resellers / arbitrage — listing isn't theirs (Q5, Q6, Q9 sellers)

---

## Voice & Tone

| Do | Don't |
|---|---|
| Direct, plain English ("your CTR is bleeding") | Marketing fluff ("optimize your sales velocity") |
| Numbers ("ACOS dropped from 75% → 42%") | Vibes ("dramatic improvement") |
| Match seller frustration ("you've tried every YouTube tip") | Talk down ("here's how Amazon works…") |
| Stakes-clear ("you're losing $260/mo to PPC waste") | Hedge ("you may want to consider…") |

**Mirror the language sellers actually use** (from voice_of_customer.md):
- "Sales tanked" / "tanked overnight"
- "ACOS is bleeding"
- "Flying blind on PPC"
- "Burned by my agency"
- "I don't know what to fix first"
- "All my revenue is going straight back into ads"
- "Worst week in 15 years"

**The product output should look like a high-upvote forum reply:** numbered, ranked, blunt, citing the seller's exact metrics. ASINInsight IS a senior FBA peer commenting on your CSV.

---

## Pricing — Confirmed (Do Not Move in 90 Days)

| Tier | Price | Rationale |
|---|---|---|
| Free (3 audits/mo) | $0 | Mirrors AuditMyListing's validated funnel; differentiator vs. them is private CSV |
| **Pro** | **$49/mo** | Universal "real seller" anchor (JS Starter $49, ZonGuru Researcher $49); **$80/mo cheaper than Helium 10's new $129 floor** |
| Agency | $199/mo | Sits between Threecolts ($69 entry) and Helium 10 Diamond ($359); under Helium 10's pricing umbrella for Diamond customers seeking alternatives |

**Pricing principles:**
- **Never compare downward** to free tools. Always compare upward to "$1,500/audit agency retainer."
- **Cheap-looking pricing kills B2B trust.** $49 is the floor; do not test $29.
- **Anti-funnel pricing:** the value of $0 (for first 3 audits) is *more than* the value of $49/mo for incumbent tool free trials, because there is no card, no login, no signup. Highlight this asymmetry on the pricing page.

---

## Trust Mechanics — How to Make the Privacy Promise Believable

The promise is **"transmitted to our server, processed in memory, deleted instantly — never stored, never shared, never used to train AI."** This must be backed by physically-verifiable artifacts, not just claimed:

1. **One-paragraph technical explanation under the upload box:** *"Your CSV is sent to our server over HTTPS, parsed in memory, scored, and the response returned to you. The file is never written to disk, never logged, never used to train any model. You can verify by re-uploading the same file and seeing it analyzed fresh — there's nothing in our systems to remember it from."*
2. **Privacy page reference** — `/privacy` already states this in plain language. Link from the upload area.
3. **No data-retention rationale** — explicit answer to "why don't you keep it?" → "Because keeping it would slow us down, expand our compliance surface, and hand a footgun to anyone who buys us. Discarding immediately is the cheapest, most honest answer."
4. **No email required to see top issues.** Email gates ONLY at PDF export, audit history, and re-audit.
5. **No cookies for tracking the upload itself.** Use Plausible/PostHog for page analytics only. The CSV-upload flow is anonymous.

> ⚠️ The earlier draft of this section (now corrected) claimed "client-side processing" and "DevTools shows zero outbound traffic." That is **NOT TRUE** of the current implementation. The CSV does upload via HTTPS POST to `/api/diagnose`. Don't promise client-side. Promise *immediate-deletion + zero-retention.*

---

## Trust-Killers to Defuse Explicitly

From voice_of_customer.md — sellers warn each other about these. Preempt each:

| Red flag in market | Landing-page preempt copy |
|---|---|
| Generic AI advice | *"Not generic AI — every line is keyed to YOUR ASIN's actual numbers"* |
| Cancellation friction | *"Cancel in 1 click. No end-of-cycle billing."* |
| Constant upsell blur-walls | *"Pro shows everything Pro can show. No blurred screens."* |
| Agency promise-vs-deliver | *"Live demo with your own CSV before any commitment"* |
| "More ad spend" as universal answer | *"We frequently recommend cutting or pausing ads when the diagnosis is a listing problem, not a traffic problem"* |
| Fake "free audit" lead-magnets | *"Top-3 issues shown free, no email required"* |
| Stale 2023 SEO playbooks | *"Our action plan maps to A10 + COSMO + Rufus signals — the 2026 ranking systems Amazon actually uses today"* |

---

## What We Cannot Yet Validate

These remain hypotheses until launch data confirms:

1. Does the privacy framing actually convert, or do sellers shrug and use Helium 10 anyway?
2. Will agencies pay $199/mo, or only one-time-per-client?
3. Does the "sudden drop" SEO play actually rank?
4. Is $49 too cheap (perceived as toy) or too expensive (vs. Sellerboard $19 anchor in adjacent lane)?
5. Will Reddit/podcast moves break through the no-promo culture, or get banned?
6. Does the "anti-funnel" actually convert better than Helium 10's "trial → card" path, or just feel cleaner with same conversion?

**All testable in the 90-day plan (`gtm_90day.md`).** Don't move pricing or positioning to address #1–#5 until paid-conversion data forces a change.

---

## The Single Sentence to Memorize

> **"You already have the data. We read it for you — and forget it the moment we're done."**

The Sales & Traffic CSV is the data. ASINInsight is the reader. The seller is the actor. The deletion guarantee is the trust.

If a seller gets nothing else from the website except this sentence — they have the wedge.

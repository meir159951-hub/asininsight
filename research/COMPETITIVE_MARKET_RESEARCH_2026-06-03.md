# Competitive & Market Research — ASINInsight / SellerCopilot
**Date:** 2026-06-03 · **Author:** Miro (lead orchestrator), deep-research run
**Method:** 5 parallel web-research agents (competitor suites, PPC tools, listing-audit/CSV niche, Amazon-native-AI threat, market size/direction), adversarial source verification, confidence-tagged synthesis.

> ⚠️ **Verification note:** Most vendor pages returned HTTP 403 to automated fetch, so a share of claims rest on search-result summaries that quote those sources. Major claims are corroborated across 2+ independent sources. Self-reported vendor stats and research-mill market-size figures are tagged LOW confidence below.

---

## תקציר מנהלים (עברית)

1. **הטריז של האודיט פתוח — אבל שביר.** אף מתחרה לא מקבל את ה־CSV הפרטי של מכירות-ותנועה בלי לוגין ובלי כרטיס לאודיט ליסטינג. אבל כל רכיב בנפרד ניתן להעתקה, ו־Helium 10/SellerApp כבר מפעילים בדיוק את המנגנון הזה — רק עבור PPC. זה מהלך **מיצוב ואמון, לא חפיר טכנולוגי**.
2. **התמחור הקבוע לא ייחודי.** AdLabs (1% מההוצאה, מסר אנטי-קופסה-שחורה) ו־Scale Insights ("Absurd Control", $78 או 1%) כבר תופסים את "זול + אתה בשליטה". כל הסוויטות הגדולות הן ממילא תמחור קבוע.
3. **🚨 השינוי הגדול מאתמול: אמזון בעצמה סוגרת את חפיר ה"כתיבה".** Seller Assistant (לשעבר Amelia) הפך בספטמבר 2025 ל־AI סוכני שמבצע פעולות באישור המוכר — כולל יצירת קמפיינים ותיקון ליסטינגים. בנוסף "Ads Agent" ו־"Enhance My Listing" (900K+ משתמשים) — אמזון נותנת בחינם בדיוק את מה ש־`audit_engine.py` ו־`ppc_agent.py` עושים.
4. **מסקנה:** מוצר "אודיט חינמי + הצעות PPC" כשלעצמו הוא כנראה **מוצר מת** — אמזון נותנת את שניהם בחינם. מה ששורד = **שכבת אורקסטרציה ניטרלית, חוצת-חשבונות וחוצת-תחומים, שממקסמת את רווח המוכר** — בדיוק מה ש־**Miro** תוכנן לעשות. זה ההימור הנכון.

---

## 1. Current market state (2026)

### Competitor map — pricing & input model

| Company | Category | Pricing model | 2026 price floor | Input model | Key weakness |
|---|---|---|---|---|---|
| **Helium 10** | All-in-one suite | Flat | ~$99–129/mo (Starter removed Apr 2026) | SP-API / OAuth login | Cancellation/billing complaints; "jack of all trades" |
| **Jungle Scout** | Research suite | Flat | $49/mo Starter (no free trial) | SP-API + own estimates | Amazon-only; no trial; pricey for beginners |
| **ZonGuru** | Listing AI suite | Flat | $39–49/mo | MWS/SP-API login | Source-conflicting pricing; mid-tier brand |
| **SellerApp** | All-in-one + managed | Flat self-serve; **% of spend on managed** ($300 base +0.5–2.5%) | ~$42/mo | SP-API login; **free PPC CSV uploader, no login** | Managed % scales costly |
| **Sellerboard** | Profit analytics | Flat (cheapest) | ~$19/mo; 2-mo trial, no card | SP-API login | Narrow scope; dated UI |
| **AuditMyListing** | Public-page audit | Freemium | Free 3/mo → $18.99 | Public-page scrape, **no login/card** | **No private data** (public only) |
| **Pacvue** | Enterprise PPC | Hybrid (≤3% of spend or $500/mo min) | ~$26K/yr avg | SP-API + ad OAuth | Enterprise-only; expensive |
| **Perpetua** | PPC automation | Flat → % of spend at top tiers | ~$695/mo | Ad OAuth | "Hands-off" autonomy, opposite of control pitch |
| **Teikametrics** | PPC automation | Flat → +3% over $10K spend | ~$149/mo | Ad OAuth | 3% overage; enterprise lean |
| **Quartile** | Retail-media AI | Platform fee + % | ~$895/mo, $3K min spend | Ad OAuth | High floor |
| **AdLabs** | PPC, anti-black-box | **% of spend (1%)** | 1% of spend | Ad OAuth | Tiny team (~7) |
| **Scale Insights** | PPC, "Absurd Control" | $78/mo flat OR 1% of spend | $78/mo | Ad OAuth | Power-user oriented |
| **Adtomic (H10)** | PPC module | Bundle + 2% mgmt fee | in Diamond ~$229/mo | Ad OAuth | Locked to H10 suite |

**Sources:** [Helium10 pricing](https://www.demandsage.com/helium-10-pricing/), [Jungle Scout](https://www.capterra.com/p/249574/Jungle-Scout/pricing/), [ZonGuru](https://revenuegeeks.com/zonguru-pricing/), [SellerApp managed %](https://revenuegeeks.com/sellerapp-pricing/), [Sellerboard](https://www.saasworthy.com/product/sellerboard/pricing), [AuditMyListing](https://auditmylisting.com/), [Pacvue](https://www.atom11.co/blog/pacvue-pricing-guide), [Perpetua](https://perpetua.io/pricing/), [Teikametrics](https://www.teikametrics.com/pricing/), [Quartile](https://amz.ninja/quartile-pricing/), [AdLabs](https://adlabs.app/flat-rate-pricing/), [Scale Insights](https://scaleinsights.com/), [Adtomic](https://www.helium10.com/adtomic-pricing/).

### Recent moves (2025-2026)
- **Helium 10** removed the $39 Starter plan (early 2026) and raised prices (Apr 2026); Cerebro now maps keywords to **Rufus** AI. [src](https://www.sellersprite.com/en/blog/helium-10-pricing-2026-guide)
- **Helium 10 Ads** launched Feb 2025 (Pacvue-powered), replacing Adtomic. [src](https://revenuegeeks.com/helium-10-ads/)
- **Pacvue** launched **"Pacvue Agent"** (~Apr 2026) — agentic, *executes* campaign actions, building MCP integrations to ChatGPT/Claude/Gemini. [src](https://ppc.land/pacvue-agent-promises-200x-faster-commerce-media-workflows/)
- **Sellics → merged into Perpetua**; **Helium 10 + Pacvue** under same PE parent (Assembly/Advent/PSG).

### Market structure
- **Amazon ad revenue ~$56.2B (2025)** — the pool PPC tools sit on. [src](https://wbxcommerce.com/amazon-ads-the-56-billion-engine-thats-just-getting-started/)
- **~1.9M active 3P sellers** (~1.1M US); **1.3M+ already use Amazon's own AI listing tools**. [src](https://amzmonitor.com/blogs/amazon-third-party-sellers-2025-q3-q4-data-analysis)
- **Software M&A thrives, brand-aggregators collapsed:** SPS bought Carbon6 (~$210M); Thrasio Ch.11 (2024); Apollo wrote off ~$170M on Perch. *Building software wins; buying sellers failed.* [src](https://betakit.com/carbon6-to-be-acquired-by-us-based-sps-commerce-for-301-million-cad-to-grow-e-commerce-merchant-toolkit/), [src](https://www.marketplacepulse.com/articles/software-aggregators-thrive-while-amazon-aggregators-falter)
- **Small-seller base shrinking:** US new-seller registrations down ~44% in 2025; ~1.6% of sellers drive 50% of 3P GMV. (MEDIUM confidence, blog-sourced.) [src](https://sentrykit.com/blog/amazon-seller-concentration-2026/)

---

## 2. Where we stand — is the wedge defensible?

**Verdict: the audit wedge is a real but copyable positioning play, not a moat.**

- ✅ **Open lane:** No competitor ingests the **private Sales & Traffic CSV** for a **no-login, no-card** listing/conversion audit. The market is either OAuth tools or public-page scrapers. [competitor agent finding]
- ⚠️ **But the mechanic is already shipped for PPC:** Helium 10's free PPC Audit and SellerApp's free PPC Audit both accept a **Search Term Report CSV with no login, no card**. Extending "upload CSV, no login" to a *listing* CSV is low-effort for an incumbent. [src](https://www.helium10.com/tools/free/ppc-audit/), [src](https://www.sellerapp.com/amazon-ppc-audit-tool.html)
- ⚠️ **Zero-retention is unused as a marketing angle** — genuinely unowned, but it reads as a *trust* counter to Helium 10's billing reputation, not a fix for a loudly-voiced fear.
- ⚠️ **Flat pricing is NOT unique:** AdLabs (1% of spend) and Scale Insights ($78/mo or 1%) already undercut; all big suites are flat anyway. The "flat beats % at high spend" math only holds vs Pacvue/Quartile/Perpetua's top tiers.
- ❌ **"You're in control" is contested:** AdLabs owns "without surrendering control to AI"; Scale Insights uses "Absurd Control." Not available to claim.
- ✅ **"Free audit = bait" confirmed:** Helium 10's free Listing Analyzer is literally the same engine, metered (~2 searches/mo). [src](https://revenuegeeks.com/helium10-listing-analyzer/)

---

## 3. Future developments — the Amazon-platform threat (most important)

**Amazon's native AI is now an existential threat to a me-too audit/PPC tool — and it is closing the "write-path" moat the master brief assumed was intact.**

- 🚨 **Agentic Seller Assistant (Sept 2025):** "Amelia" upgraded to *take actions with seller approval* — monitor inventory, fix account-health issues, and **generate advertising campaigns**. Built on Bedrock (Anthropic/OpenAI models). [src](https://www.cnbc.com/2025/09/17/amazon-ai-agent-sellers.html), [src](https://www.pymnts.com/amazon/2025/amazon-expands-seller-assistant-with-agentic-ai-to-become-always-on-partner)
- 🚨 **Ads Agent + Creative Agent + Full-Funnel Campaigns (2026):** native conversational AI drafts campaigns, optimizes bids, generates creative — directly overlapping `ppc_agent.py`. [src](https://www.thekeyword.co/news/amazon-highlights-ai-tools-in-2026-ad-plans), [src](https://salesduo.com/blog/future-of-amazon-advertising/)
- 🚨 **"Enhance My Listing" + AI listing generation (May 2025):** native, free listing diagnosis/optimization, 900K+ users (Amazon self-reported) — directly overlaps `audit_engine.py`. [src](https://techcrunch.com/2025/05/08/amazons-newest-ai-tool-is-designed-to-enhance-product-listings/)
- **Discovery shift:** COSMO (intent-based ranking on top of A9) + Rufus → folded into **"Alexa for Shopping" (May 13, 2026)**. Optimization for AI-mediated discovery is a *new* problem sellers will pay outsiders to solve. [src](https://www.cnbc.com/2026/05/13/amazon-ditches-rufus-ai-chatbot-in-favor-of-alexa-shopping-agent.html)
- **Counter-consensus:** native tools are repeatedly described as *generic, shallow, single-account, self-interested* (Amazon optimizes for Amazon's ad revenue, not seller profit). Third-party tools survive on depth, neutrality, cross-account data, and prioritization. [src](https://www.demandsage.com/helium-10-alternatives/)

---

## 4. Our advantage — where it is real, and what to build

**Genuine, durable advantages (defensible):**
1. **Neutral, profit-first second opinion.** Amazon's AI is structurally conflicted — it pushes ad spend and optimizes for Amazon's revenue. A tool that *cuts ad waste against Amazon's interest* is something Amazon will never build. This is the strongest wedge and matches `ppc_suggestions.py`'s "money to save" framing.
2. **Cross-domain orchestration — i.e., Miro.** Amelia and Ads Agent are **siloed** assistants. None merge listing + PPC + inventory + pricing into one ranked "what to do next." **This is exactly what `miro.py` does, and it is the most defensible position in the codebase.**
3. **Cross-account / cross-marketplace / competitor benchmarking** — portfolio-level intelligence Amazon does not give a single seller.
4. **The AI-discovery optimization problem** (COSMO/Alexa) — sellers will pay an outside expert to beat an algorithm Amazon won't explain.

**Where the advantage is NOT:**
- ❌ The one-time free audit (Amazon + Helium 10 give it away).
- ❌ Basic PPC suggestions (Amazon's Ads Agent does this natively with first-party data).
- ❌ Flat pricing as a headline (already occupied).
- ❌ "No write path" as a safety moat — Amazon's own agent now *has* the write path.

### Prioritized recommendations
1. **Reposition around Miro, not the audit.** Lead with "one neutral briefing across your whole business — what Amazon's siloed AI won't tell you." The audit becomes a *feature that feeds Miro*, not the product.
2. **Build the recurring layer = Miro monitoring.** A weekly/daily cross-domain briefing (listing + PPC + inventory + pricing drift) that re-runs automatically. This is the recurring value the master brief said was missing, and it sits exactly where Miro already is.
3. **Lean into neutrality + zero-retention as the anti-Amazon, anti-Helium-10 trust position** — "we don't sell your ad spend, we cut it; we don't keep your data."
4. **Add the agents Amazon keeps siloed:** Inventory, Pricing, Reviews specialists under Miro — each plugs in via `register()`.
5. **For the market test:** validate willingness to pay for the *recurring cross-domain briefing*, not the one-time audit.

---

## Confidence ledger
- **HARD:** competitor pricing/input models; Amazon ad revenue; Carbon6/Thrasio/Perch M&A; Project Amelia→agentic (Sept 2025); Helium 10 Ads launch; Rufus→Alexa (May 2026); EML launch.
- **MEDIUM:** seller counts (~1.9M); seller-concentration & registration-drop stats; exact % for Perpetua/Intentwise/Quartile tiers.
- **LOW / marketing-sourced:** all market-size/CAGR figures; Amazon's self-reported adoption stats (900K users, 90% acceptance, "30% via Rufus"); Nov-2025 Pacvue acquisition event (acquirer unconfirmed).
- **DATA GAP:** no public figure for the fraction of sellers who pay for third-party tools.

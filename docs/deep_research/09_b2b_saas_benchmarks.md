# 📊 B2B SaaS Benchmarks 2026 — Reality Check for SellerCopilot

> **Purpose:** Industry-standard benchmarks for every key SaaS metric, so we know "good" from "bad" as we grow.
> **Date:** 2026-05-11
> **Source:** Multiple 2026 industry reports (Pepper Effect, SaaS Hero, ChartMogul, SaaS Capital)

---

## 🎯 Quick Reference (one table)

| Metric | What's "bad" | What's "good" | What's "great" | SellerCopilot Year 1 target |
|---|---|---|---|---|
| Monthly churn | >7% | 3-5% | <2% | <5% |
| Annual NRR | <85% | 90-100% | >100% | 85% |
| LTV:CAC | <2:1 | 3:1-4:1 | >5:1 | 3:1 |
| Trial → paid | <15% | 20-40% | >40% | 25-35% |
| Gross margin | <70% | 75-85% | >85% | 85-90% |
| Visitor → trial | <3% | 5-10% | >12% | 8% |
| Demo close rate | <15% | 25-40% | >50% | 30% |
| Payback period | >18mo | 9-18mo | <9mo | <12mo |

---

## 1️⃣ Churn Rate Benchmarks

### Monthly churn by ARPU

| ARPU range | Median monthly churn | Top quartile |
|---|---|---|
| <£50/mo | 7.3% | 5-6% |
| £50-£150/mo | ~4.5% | 3-4% |
| £150-£250/mo | ~3.5% | 2-3% |
| >£250/mo | 5.0% | 3-4% |

— Sources: Pepper Effect, SaaS Capital 2023 Report

### Where SellerCopilot lands

- Pilot $89/mo (~£72) → ~5-6% target churn (good)
- Operator $149/mo (~£120) → ~4% target churn
- Agency $199/mo (~£160) → ~3.5% target churn

**Year 1 realistic:** 5-7% monthly churn (acceptable for early-stage)
**Year 2 target:** <5% monthly churn (improvement through product maturity)

### What drives churn

| Cause | Impact | Mitigation |
|---|---|---|
| Customer never reaches first value | High | Onboarding flow tuning |
| Customer doesn't see ongoing value | High | Weekly digest emails |
| Customer's business changed | Medium | Pause vs. cancel option |
| Customer found alternative | Medium | Stay on top of competitive landscape |
| Pricing perception | Medium | Annual prepay reduces this |

### Calculation

Monthly churn = (customers lost / customers at start of month) × 100

**Example:** Start month with 100 customers, lose 5, end with 95.
Churn = 5/100 = 5% monthly churn.

---

## 2️⃣ Net Revenue Retention (NRR)

### Definition
NRR = (Starting MRR + Expansion - Churn - Contraction) / Starting MRR × 100

### Benchmarks

| Company size | Median NRR | Top quartile |
|---|---|---|
| <$1M ARR | ~95% | 100%+ |
| $1M-$10M ARR | 98% | 105% |
| $10M-$100M ARR | 105% | 115% |
| $100M+ ARR | 115% | 125%+ |

— Source: SaaS Hero 2026

### Where SellerCopilot lands

**Year 1:** NRR ~85-90% (typical for early-stage SMB SaaS)
**Year 2:** Target 95% (with upsells to Operator/Agency tiers)
**Year 3+:** Target 100%+ (mature)

### How to drive NRR up

1. **Upsell:** Get customers to upgrade Pilot → Operator → Agency
2. **Expansion:** Multi-account customers (agencies)
3. **Annual prepay:** Locks in revenue
4. **Reduce churn:** Direct improvement to NRR formula

---

## 3️⃣ Gross Revenue Retention (GRR)

### Definition
GRR = (Starting MRR - Churn - Contraction) / Starting MRR × 100

Pure retention, no expansion factored in.

### Benchmarks

| Company size | Median GRR |
|---|---|
| <$1M ARR | 85% |
| $1M-$10M ARR | 85% |
| $10M-$100M ARR | 89% |
| $100M+ ARR | 94% |

— Source: SaaS Hero 2026

### Where SellerCopilot lands

**Year 1:** GRR ~85-90% (in-line with industry)
**Year 2+:** Target 90%+

---

## 4️⃣ Customer Acquisition Cost (CAC)

### Benchmarks by segment

| Segment | CAC range |
|---|---|
| SMB (target: <$100/mo) | $100-$400 |
| Mid-market ($100-$500/mo) | $400-$800 |
| Enterprise ($500+/mo) | $800-$2,000+ |

— Source: Data-Mania CAC Benchmarks 2026

### Average B2B SaaS CAC 2026
$1,200 across all channels (up 14% from 2025) — Source: Multiple industry reports

### Where SellerCopilot lands

**Organic channels** (founder-led, forums, SEO):
- Year 1: CAC ~$50-$200 (low because organic-only)

**Paid channels** (when added):
- Google Ads: CAC ~$400-$800
- LinkedIn Ads: CAC ~$500-$1,000

**Blended Year 1 target:** $100-$300 CAC

### Calculation

CAC = Total acquisition spend / New customers acquired

**Example:** Spend $1,000 on Google Ads, get 5 customers.
CAC = $1,000 / 5 = $200

---

## 5️⃣ Lifetime Value (LTV)

### Definition
LTV = ARPU × Gross Margin / Churn Rate

### SellerCopilot LTV calculations

**Year 1 (high churn):**
- ARPU: $89
- Gross Margin: 88%
- Monthly Churn: 5%
- LTV = $89 × 0.88 / 0.05 = **$1,566**

**Year 2 (matured):**
- ARPU: $117.95 (blended across tiers)
- Gross Margin: 90%
- Monthly Churn: 4%
- LTV = $117.95 × 0.90 / 0.04 = **$2,654**

**Year 3 (best case):**
- ARPU: $130 (more upsells)
- Gross Margin: 91%
- Monthly Churn: 3%
- LTV = $130 × 0.91 / 0.03 = **$3,943**

### Benchmark
B2B SaaS LTV ranges from $1,500 (low end) to $50,000+ (enterprise). SellerCopilot at $1,500-$4,000 LTV is **healthy SMB B2B range.**

---

## 6️⃣ LTV:CAC Ratio (The Most Important Metric)

### What it measures
How much you make per customer vs. how much you spend to acquire them.

### Benchmarks

| Ratio | Assessment |
|---|---|
| <1:1 | Losing money — emergency |
| 1:1-3:1 | Sub-optimal, possibly survivable |
| **3:1** | **Industry minimum** ✅ |
| 4:1-6:1 | Top-quartile B2B SaaS |
| >6:1 | Exceptional |

— Source: SaaS Hero 2026

### Stage-specific targets

| Stage | LTV:CAC target | Payback |
|---|---|---|
| Early (<$2M ARR) | 2.5:1 | 120 days |
| Growth ($2M-$10M ARR) | 3-4:1 | 90 days |
| Scale (>$10M ARR) | 4-5:1+ | 80 days |

### SellerCopilot Year 1
- LTV: $1,566
- CAC: $150 (organic-heavy)
- **Ratio: 10.4:1** (excellent — because no paid spend yet)

### When paid is added
- LTV: $2,654 (Year 2)
- Blended CAC: $400 (mix of organic + paid)
- **Ratio: 6.6:1** (still excellent)

**Bottom line: SellerCopilot has room for paid acquisition. The unit economics work.**

---

## 7️⃣ Payback Period

### Definition
Months it takes to recoup CAC through gross profit per customer.

### Calculation
Payback = CAC / (ARPU × Gross Margin)

### Benchmarks

| Quality | Payback |
|---|---|
| Excellent | <6 months |
| Good | 6-12 months |
| Acceptable | 12-18 months |
| Bad | >18 months |

### SellerCopilot
- CAC: $150 (Year 1 organic)
- ARPU × Margin: $89 × 0.88 = $78/mo
- **Payback: 1.9 months** ⚡

This is **exceptional** because of low CAC. As paid is added (CAC → $400), payback rises to ~5 months. Still excellent.

---

## 8️⃣ Conversion Rate Benchmarks

### Visitor → Signup (landing page conversion)

| Quality | Rate |
|---|---|
| Below average | <1.5% |
| Average | 1.5-5% |
| Good | 5-10% |
| Top quartile | >12% |

— Source: SaaS Hero 2026

**SellerCopilot target:** 8% (clear positioning helps)

### Signup → Paid (free trial / freemium → paid)

| Trial type | Conversion |
|---|---|
| With credit card required | 30-50% |
| Without credit card required | 15-25% |
| Freemium (no trial) | 2-5% |

— Source: Industry benchmarks 2026

**SellerCopilot target (no card required):** 25-35%

### Demo → Close (founder-led sales)

| Quality | Close rate |
|---|---|
| Below average | <10% |
| Average | 15-25% |
| Good | 25-40% |
| Top quartile | >50% |

**SellerCopilot target (founder-led):** 30-50%

---

## 9️⃣ MRR Growth Rate

### Benchmarks by stage

| Stage | Monthly growth |
|---|---|
| 0-$10K MRR | 15-25% MoM (fast in % terms, small absolute) |
| $10K-$100K MRR | 8-15% MoM |
| $100K-$1M MRR | 5-10% MoM |
| $1M+ MRR | 3-7% MoM |

— Source: PM Toolkit 2026

### SellerCopilot trajectory

| Period | MRR | Target growth |
|---|---|---|
| Month 3 | $245 (5 customers @ $49) | n/a (validation) |
| Month 6 | $1,000 | ~20% MoM |
| Month 9 | $2,500 | ~15% MoM |
| Month 12 | $5,000 | ~12% MoM |
| Month 18 | $15,000 | ~10% MoM |
| Month 24 | $30,000 | ~8% MoM |

---

## 🔟 Cost Structure Benchmarks

### Typical B2B SaaS Cost Breakdown

| Category | % of revenue |
|---|---|
| COGS (hosting, API, infrastructure) | 10-25% |
| R&D | 20-30% |
| Sales & Marketing | 20-50% |
| G&A (admin, legal, etc.) | 10-15% |
| Total opex | 75-85% |
| Gross profit margin | 75-90% |
| Operating margin | 15-25% (mature) |

### SellerCopilot Year 1 reality (solo bootstrap)

| Category | Spend |
|---|---|
| COGS (Anthropic API) | $5-10/customer/mo (~10% of $89) |
| R&D | $0 (Meir's time, no cash cost) |
| S&M | <$5K Year 1 (organic-heavy) |
| G&A | ~$1K (legal, accounting) |
| **Total cash spend** | **~$10K Year 1** |
| **Revenue Year 1** | **~$30K-$92K** |
| **Cash profit Year 1** | **~$20K-$80K** |

**Translation:** Year 1 cash-positive. Meir doesn't need outside funding.

---

## 1️⃣1️⃣ Customer Segmentation Benchmarks

### Distribution across pricing tiers (typical 3-tier B2B SaaS)

| Tier | % of customers | % of revenue |
|---|---|---|
| Lowest | 40-50% | 20-30% |
| Middle (Goldilocks) | 40-50% | 50-60% |
| Highest | 5-15% | 20-30% |

### SellerCopilot expected mix (after Year 1)

| Tier | Price | % of customers (expected) | % of revenue (expected) |
|---|---|---|---|
| Pilot | $89 | 60% | 45% |
| Operator | $149 | 30% | 38% |
| Agency | $199 | 10% | 17% |

**Blended ARPU:** $117.95/mo

---

## 1️⃣2️⃣ Time to Key Milestones

### Bootstrap solo founder benchmarks

| Milestone | Median time | Fast track |
|---|---|---|
| First paying customer | 6-8 weeks | 3-4 weeks |
| $1K MRR | 12-18 months | 4-6 months |
| $5K MRR | 24-48 months | 12-15 months |
| $10K MRR | 30-60 months | 18-24 months |
| $50K MRR | 60-84 months | 36-48 months |

— Source: Micro-SaaS Revenue Reality, SaaS Ranger 2026

### SellerCopilot realistic plan

| Milestone | Target month | Probability |
|---|---|---|
| First customer | Month 3 | 70% |
| $1K MRR | Month 6 | 60% |
| $5K MRR | Month 12 | 50% |
| $10K MRR | Month 18-24 | 50% |
| $50K MRR | Month 36+ | 30% |

These probabilities assume:
- Validation passes
- Bootstrap solo (no team)
- Meir bandwidth ~3 hours/day average
- No paid acquisition Year 1

---

## 🎯 The 3 Metrics to Watch Weekly

If Meir tracks only 3 numbers:

### 1. MRR
Total recurring revenue this month. The North Star.

### 2. New customers / week
Reveals if acquisition is working before MRR moves.

### 3. Activation rate (% completing first conversation)
Predicts long-term retention.

Everything else is secondary in Year 1.

---

## 🚨 Warning Signs (when to pivot or fix)

### Red flag patterns

| Pattern | Diagnostic |
|---|---|
| 0 customers in 8 weeks | Wedge is wrong — reposition |
| <20% trial-to-paid | Value isn't clear at trial — fix onboarding |
| >10% monthly churn | Product doesn't deliver — fix the core |
| CAC > 6 months payback | Channels are wrong — switch |
| MRR flat for 3 months | Either acquisition or retention is broken |

### Healthy patterns

| Pattern | Signal |
|---|---|
| Customers asking "how soon can my team get on this?" | PMF emerging |
| Inbound DMs / leads | Reputation building |
| 30%+ trial-to-paid | Value clear at trial |
| <5% monthly churn | Product solving real pain |
| 20% MoM MRR growth | Healthy momentum |

---

## 📚 Sources

- [Pepper Effect - B2B SaaS Benchmarks 2026](https://peppereffect.com/blog/b2b-saas-benchmarks)
- [SaaS Hero - LTV:CAC Benchmarks](https://www.saashero.net/strategy/b2b-saas-ltv-cac-benchmarks/)
- [SaaS Hero - Conversion Benchmarks](https://www.saashero.net/competitor/b2b-saas-conversion-benchmarks-2026/)
- [Data-Mania - CAC Benchmarks 2026](https://www.data-mania.com/blog/cac-benchmarks-for-b2b-tech-startups-2025/)
- [PM Toolkit - SaaS Metrics 2026](https://pmtoolkit.ai/benchmarks/saas-metrics-2026)
- [ChartMogul - SaaS Retention Report](https://chartmogul.com/reports/saas-retention-report/)
- [SaaS Capital - 2023 Retention Benchmarks](https://www.saas-capital.com/wp-content/uploads/2023/05/RB28WS1-2023-B2B-SaaS-Retention-Benchmarks.pdf)

---

*Benchmarks are guides, not laws. Your specific market, product, and channel mix will create outliers. But know the averages so you can recognize good performance from bad.*

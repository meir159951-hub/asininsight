# 🗺️ Buyer Journey Map — Amazon Seller ICP

> **Purpose:** Map every stage of the seller's journey from problem-awareness to purchase to advocacy.
> **Date:** 2026-05-11
> **For:** SellerCopilot Pilot tier ICP ($25K-$250K/mo GMV seller)

---

## 🧭 The Full Journey at a Glance

```
                  Unaware
                     ↓
                  Pain ("PPC is bleeding")
                     ↓
                  Researching ("What tools exist?")
                     ↓
                  Comparing ("Adtomic vs Helium 10 vs SellerCopilot")
                     ↓
                  Trial ("Let me see what it does")
                     ↓
                  First action ("I approved a suggestion")
                     ↓
                  Habit ("I check it weekly")
                     ↓
                  Advocate ("Telling other sellers")
```

Each stage has:
- Specific seller psychology
- Specific actions they take
- Specific content/touchpoints from us
- Conversion rates from B2B SaaS benchmarks

---

## 🎬 Stage 0: Unaware

### Seller psychology
*"PPC is just part of doing business on Amazon. I'm doing fine."*

### Triggers that move them forward
- ACOS spikes unexpectedly
- A consultant says they should use a tool
- Hear about competitors using AI tools
- Q4 ad spend hits a record high
- Sees a peer post their PPC results on Twitter

### Content from us
- Brand awareness (SEO content for top-of-funnel keywords)
- Industry presence (Meir's Twitter/LinkedIn)
- Word of mouth from existing customers

### Conversion to Stage 1
- B2B SaaS: ~5-10% of unaware sellers become aware/curious each year
- For SellerCopilot in Year 1: Tiny — focus elsewhere

---

## 😣 Stage 1: Problem-Aware

### Seller psychology
*"Something's wrong. I'm spending too much on PPC. I don't know what to do."*

### Specific triggers (from voice_of_customer research)
- *"Sales dropped overnight"* — sudden visibility loss
- *"ACOS skyrocketed out of nowhere"* — keyword level issue
- *"All my revenue is going back into ads"* — margin compression
- *"Worst week in 15 years"* — veteran disorientation

### What they do
- Google: *"why is my Amazon ACOS so high"*
- Search forums: Seller Central, Reddit, FB groups
- Read articles like *"5 Amazon PPC mistakes"*

### What they don't yet do
- Specific tool research (Stage 2)
- Buy anything

### Content from us
- **Top SEO blog posts** (target this stage):
  - "Why Your Amazon PPC Tool Forgets Everything"
  - "Amazon ACOS Bleeding? Here's What Most Sellers Miss"
  - "Diagnostic: Is It Your Listing or Your Bids?"

- **Forum participation:** thoughtful answers to their questions

- **Free audit tool** (ASINInsight is exactly this — the existing CSV diagnostic)

### Conversion to Stage 2
- ~10-20% will move to research-mode if our content resonates
- Time in stage: weeks to months

---

## 🔍 Stage 2: Solution-Aware (Researching)

### Seller psychology
*"There must be a tool for this. Let me look at what's out there."*

### What they do
- Google: *"best Amazon PPC tool 2026"*
- Read comparison posts (Helium 10 vs Jungle Scout, etc.)
- Browse review sites (Capterra, G2, Trustpilot)
- Ask in forums: *"What PPC tool do you recommend?"*

### What they evaluate
- Pricing (anchored on Helium 10 $129)
- Features (especially bid automation)
- Reviews / ratings
- Integration with their current stack

### Content from us
- **Tier 2 SEO posts** target this stage:
  - "Adtomic Alternative: 7 Better PPC Tools in 2026"
  - "AI PPC Tools Compared: Astra vs AutoPilot vs SellerCopilot"
  - "What 'AI-Powered PPC' Actually Means (And Doesn't)"

- **Comparison page on site:** `/vs/adtomic`, `/vs/quartile`

- **Review presence:** Get on Capterra, G2 once you have customers

### Conversion to Stage 3
- B2B SaaS: 30-50% will visit candidate sites
- Critical: be in the consideration set

---

## ⚖️ Stage 3: Comparing

### Seller psychology
*"I'm looking at 3-5 tools. Which one is right for my business?"*

### What they do
- Visit SellerCopilot landing page
- Visit competitor sites
- Look at pricing
- Watch demo videos
- Read case studies
- May fill out trial form on 1-2

### What converts them
- **Clear positioning** ("the only tool that remembers")
- **Specific outcomes** (case studies with numbers)
- **Pricing clarity** ($89/mo, visible above-the-fold)
- **No friction trial** (no card, 14 days free)
- **Social proof** (testimonials from real sellers)

### Content from us
- **Landing page** (per `docs/landing_repositioning_draft.md`)
- **Pricing page** (clear, simple)
- **Comparison table** vs each major competitor
- **3-5 case studies** with real numbers
- **2-minute demo video** showing actual product

### Critical: the trust strip
🧠 *"Persistent memory — knows your business after one session"*
💬 *"Real conversations, not a dashboard"*
🎯 *"Honest reasoning, never blames Amazon"*
🔒 *"Compliant with Amazon BSA Agent Policy 2026"*

### Conversion to Stage 4
- B2B SaaS landing page → trial: 5-15%
- SellerCopilot target: 8-12% (clear value prop helps)

---

## 🧪 Stage 4: Trial

### Seller psychology
*"OK, I signed up. Let me see if this actually works for my account."*

### What they do
- Connect Amazon account (OAuth)
- Wait through data fetch (1-5 minutes)
- Have first conversation with agent
- See first suggestion
- Decide: approve, reject, or just observe

### Critical first 10 minutes
The "aha moment" must come quickly.

**Good first 10 minutes:**
- Agent opens with: *"I see your last 30 days. Here's what's notable: [3 specific observations about THEIR account]. Quick question: what's your target ACOS?"*
- Seller answers
- Agent: *"Got it. Based on that, the most obvious win is: [specific suggestion with reasoning]. Approve?"*
- Seller sees ROI clearly

**Bad first 10 minutes:**
- Generic "Welcome! Tell me about your business..."
- No specific data analysis
- Vague suggestions

### Content from us
- **Onboarding flow** (per `docs/onboarding_flow_design.md`)
- **First-conversation script** (engineered to surface value)
- **In-app help** (just-in-time, not upfront tutorial)

### Conversion to Stage 5
- B2B SaaS trial → paid: 20-40%
- For SellerCopilot with no credit card upfront: target 25-35%
- Critical metric: % of trials that approve at least 1 suggestion (target 50%+)

---

## ✅ Stage 5: First Action (Approving)

### Seller psychology
*"This is actually doing something useful. Let me approve this suggestion."*

### The micro-decision
The first approval is the hardest. After that, momentum builds.

**What helps approval:**
- Clear reasoning ("you said your margin floor is 22%, this campaign is at 58% ACOS")
- Memory note ("you told me this on May 4")
- Rollback safety ("30-day undo on everything")
- Estimated impact ("save ~$300/month")

**What blocks approval:**
- Vague reasoning ("our AI thinks you should...")
- Ignoring their constraints
- Too many suggestions at once (decision paralysis)
- Big changes (>20%) feel risky

### Conversion to Stage 6
- Trials that approve a suggestion → paid: 70-80%
- This is the highest-leverage metric to optimize

---

## 📈 Stage 6: Active Usage (Habit)

### Seller psychology
*"This is part of my Monday routine. I check what SellerCopilot suggests."*

### What this looks like
- Weekly login (Monday morning is common)
- 2-3 suggestions per week approved
- Memory grows with each session
- Agent references past context

### What sustains the habit
- **Memory paying off:** *"Last month you decided to pause SKU-X due to inventory. Now back in stock — want to relaunch?"*
- **Weekly summary emails:** Monday digest of past week's wins
- **Predictable value:** customer can predict savings each month

### What breaks the habit
- Agent gives obvious bad advice → trust collapses
- UI breaks during a Monday session → frustration
- A weekly check-in feels like effort, not value

### Conversion to Stage 7
- Active users at month 3 → still active at month 6: ~70-80% (B2B SaaS benchmark)

---

## 🎤 Stage 7: Advocacy

### Seller psychology
*"This tool actually changed how I run PPC. I tell other sellers."*

### What they do
- Mention SellerCopilot in forum posts (organically)
- Recommend to friends in private DMs
- Reply to "what PPC tool do you use?" threads
- Write reviews (Capterra, G2, Trustpilot)
- Agree to be a case study

### How to encourage advocacy
- **Ask explicitly:** *"Mind if I share your results as a case study?"*
- **Make it easy:** pre-written tweets to share
- **Reward:** referral discount (free month for each referral)
- **Recognize:** "Customer of the month" features

### Conversion impact
- 30% of B2B SaaS growth in early stages is referral-driven
- LTV of advocates is 2-3x higher than average customer

---

## 📊 Conversion Funnel Math

### Year 1 target funnel (conservative)

| Stage | Conversion | Count |
|---|---|---|
| Visitors to landing | - | 5,000 (organic + community) |
| Landing → Signup | 8% | 400 |
| Signup → Amazon connected | 70% | 280 |
| Connected → First conversation | 95% | 266 |
| First conversation → Approved suggestion | 50% | 133 |
| Trial → Paid ($89) | 35% of approvers | 47 |
| Total paying customers Year 1 | — | **~50** |

### Year 2 target (with momentum)

| Stage | Conversion | Count |
|---|---|---|
| Visitors | - | 25,000 (SEO compounds) |
| Landing → Signup | 10% | 2,500 |
| Through full funnel | ~17% | 425 new customers |
| Plus 80% retention of Year 1 | - | 40 returning |
| **Total paying end of Year 2** | - | **~280-380** |

### Math sanity check
- Year 1 ARR: 50 × $89 × ~6 months avg = ~$27K (conservative — see deeper analysis in `01_market_sizing.md`)
- Year 2 ARR: 280 × $117.95 × 12 = ~$396K

---

## 🎯 Where to Optimize First

When you have limited time, focus on the conversion that's most under your control:

### Highest leverage (do first)

1. **Landing page conversion (Stage 3 → Stage 4)**
   - This compounds every visitor
   - Test hero variants
   - Optimize trust strip
   - Add case studies as they emerge

2. **First-conversation experience (Stage 4 → Stage 5)**
   - The agent's opening message
   - Time to first specific observation
   - Quality of first suggestion
   - This is the AHA moment

3. **Trial-to-paid (Stage 5 → Stage 6)**
   - Day 7, 12, 13 emails
   - Make payment frictionless
   - Make cancellation visible (counterintuitively, this builds trust)

### Lower leverage (do later)

- Top-of-funnel (Stage 0 → 1): SEO compounds slowly, not Year 1 priority
- Advocacy programs (Stage 7): require 100+ customers first
- Comparison content (Stage 2): valuable but second-tier

---

## ❌ Friction Points to Eliminate

Map every drop-off and remove the cause:

### Common drop-offs in B2B SaaS (Amazon vertical)

| Drop-off | Cause | Fix |
|---|---|---|
| Landing → no signup | Unclear value prop | A/B test hero copy |
| Signup → no Amazon connect | Trust issue / OAuth fear | More trust copy on connect screen |
| Connect → no conversation | Loading screen feels too long | Engaging copy during fetch |
| Conversation → no approval | Generic suggestions | Tune agent prompt for specificity |
| Approval → no second session | Forgot to come back | Day 3 email reminder |
| Subscription → cancel | Value not clear | Weekly digest emails showing wins |

---

## 🎯 The Job-to-be-Done (JTBD)

The classic framing helps clarify the journey:

> *"When my Amazon PPC feels out of control and I don't know what to fix, I want a tool that learns my business and tells me specifically what to do — so I can spend less time guessing and more time on actually profitable work."*

This JTBD is what every stage must serve:
- Stage 1-3: We help you realize this is what you need
- Stage 4-5: We deliver this in the first conversation
- Stage 6: We sustain this through every conversation
- Stage 7: You tell others "this is what I wanted"

---

## 📈 KPIs Per Stage (track in admin dashboard)

| Stage | KPI | Target Year 1 |
|---|---|---|
| 1: Aware | Organic blog traffic | 5K visitors/mo by Q4 |
| 2: Researching | Comparison page visits | 1K visitors/mo |
| 3: Comparing | Landing → signup rate | 8% |
| 4: Trial | Signup → Amazon connected | 70% |
| 5: First action | Connected → first approval | 50% |
| 6: Active | Month-2 retention | 70%+ |
| 7: Advocate | Referral rate | 1 per 10 customers/mo |

---

*This journey map is the lens for every product, marketing, and sales decision.*

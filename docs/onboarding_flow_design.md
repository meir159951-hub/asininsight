# SellerCopilot — Customer Onboarding Flow Design

> **Purpose:** Define the journey from "first visit" to "first valuable conversation"
> **Date:** 2026-05-11
> **Status:** Draft for build phase reference

---

## The Critical 3 Moments

Customer onboarding has 3 make-or-break moments:

1. **Visit → Signup** (first 60 seconds on the landing page)
2. **Signup → First conversation** (first 10 minutes after creating account)
3. **First conversation → Approved suggestion** (first 30 minutes)

If any moment fails, customer churns within 7 days.

---

## Detailed Flow

### Stage 0: Discovery
**Where:** Landing page (`sellercopilot.com` or `/copilot`)
**Goal:** Get the visitor to click "Try it free"

Key elements:
- Hero copy (3 variants in `landing_repositioning_draft.md`)
- 60-second demo video (Loom-style, real conversation example)
- Pricing visible without scroll
- Social proof (when available)

**Success metric:** 8%+ click-through to signup

---

### Stage 1: Signup
**Where:** `/copilot/signup`
**Goal:** Capture email, set up account, redirect to OAuth

Form fields (minimal):
- Email
- Password (or "magic link" option)
- Optional: Brand name, monthly ad spend range (drives onboarding personalization)

NO fields for: phone, address, company size, role, etc. **Friction kills conversion.**

After submit:
- Welcome email with 1-click verification
- Redirect to: "Connect your Amazon account →"

**Success metric:** 70%+ of clicks complete signup

---

### Stage 2: Amazon Connection
**Where:** `/ppc/connect`
**Goal:** OAuth into Amazon Seller Central, verify access

Screen elements:
- One big button: "Connect Amazon Account"
- Below: "Read-only access. No credit card. No commitment. Disconnect anytime."
- Trust line: "We're an Amazon-approved Solution Provider. Compliant with the March 2026 Agent Policy."

Click → Amazon Consent screen → Approve → Callback

**Failure modes to handle:**
- Seller has multi-marketplace account → Pick one for now (UK/DE later)
- Seller's app permissions are limited → Show specific error + how to fix
- Network failure during OAuth → Retry button

**Success metric:** 80%+ of started connections complete

---

### Stage 3: Initial Data Pull
**Where:** `/ppc/setup` (loading screen)
**Goal:** Pull last 30 days of PPC data while showing engaging content

What happens:
- Background: `ppc_snapshot_fetcher.fetch_ppc_snapshot()` runs (1-5 minutes)
- Foreground: Animated progress bar + interesting facts about their account as data loads

Sample copy as data loads:
- *"Pulling your campaigns... 23 active campaigns found"*
- *"Analyzing keyword performance... 1,247 keywords across all campaigns"*
- *"Fetching your search-term report (last 30 days)..."*

**Make this feel like the agent is "studying" the seller's account before talking.** Sets the right mental model.

If data pull takes >5 minutes:
- Switch to "Continue in background" — let seller close tab
- Email them when ready: "Your copilot is ready. Start your first conversation →"

**Success metric:** 95%+ data pulls complete

---

### Stage 4: First Conversation
**Where:** `/ppc/dashboard` (chat interface)
**Goal:** Get to first valuable insight in <10 minutes

The agent **starts the conversation** (don't make seller think of what to ask):

**Opening message:**
> *"Hi! I just finished going through your last 30 days. Here's what I see:*
> 
> *📊 Quick stats:*
> *- Active campaigns: 23*
> *- Total ad spend (30d): $12,340*
> *- Average ACOS: 41%*
> *- Best campaign: SKU-A Auto ($890 sales / 22% ACOS)*
> *- Worst campaign: SKU-X Manual Broad ($340 spent / 0 sales)*
> 
> *Before I propose anything, I want to understand your business better. Three quick questions:*
> 
> *1. What's your target ACOS?*
> *2. What's your hard margin floor — the ACOS where you'd say "stop, this is unprofitable"?*
> *3. Are there any SKUs you're intentionally NOT scaling right now (out of stock, end of life, etc.)?*
> 
> *Just reply naturally. I'll remember everything you tell me."*

**Why this works:**
- Shows agent already did work
- Surfaces 1 obvious win (the worst campaign) immediately
- Asks 3 questions that map directly to memory structure
- Says "I'll remember" — signals the wedge

After seller answers → Agent writes `profile.md` and `strategy.md` to memory.

**Success metric:** 80%+ of conversations get to question 3

---

### Stage 5: First Suggestion
**Where:** Same chat interface
**Goal:** Propose ONE clearly-reasoned change for approval

After seller answers the 3 questions:

> *"Got it. Pet supplies, target ACOS 30%, margin floor 22%, hold off on SKU-X (out of stock). Saved.*
> 
> *Based on this, the most obvious win is SKU-X Manual Broad — it spent $340 in 30 days with zero sales. You said you're not scaling SKU-X due to inventory, so let's pause the ads to save that spend.*
> 
> *Proposed action: Pause Sponsored Products campaign 'SKU-X Manual Broad'*
> *Reasoning: 0 conversions in 30 days, you're inventory-constrained on this SKU*
> *Estimated savings: ~$300/month*
> 
> *Approve? [Yes] [No, explain] [Tell me more first]*"

If seller clicks "Yes":
- Agent calls `apply_suggestion()` → writes to Amazon Ads API
- Agent saves to `decisions/2026-05-11_paused_skux_manual_broad.md`
- Agent says: *"Done. I'll check in 7 days to confirm the spend is back to zero. What else?"*

**Success metric:** 50%+ of first conversations end with at least 1 approved suggestion

---

### Stage 6: Day 7 Check-In
**Where:** Email + dashboard
**Goal:** Show the agent followed up (proves memory)

Day 7 email:
> *Subject: Your SellerCopilot 7-day check-in*
> 
> *Hi [Name],*
> 
> *Last Tuesday, I paused 'SKU-X Manual Broad' to save you ~$300/month. Quick update:*
> 
> *✅ Campaign successfully paused 7 days ago*
> *✅ 7-day spend on this campaign: $0 (was on track for $80)*
> *✅ Estimated savings so far: $80*
> *✅ No negative impact on your other campaigns*
> 
> *I have 3 new opportunities to discuss. Want to talk?*
> 
> *[Open SellerCopilot →]*

**Why this works:**
- Reminds them what was done (memory in action)
- Shows actual outcome (proof of value)
- Soft CTA back to product

**Success metric:** 60%+ click-through to dashboard

---

### Stage 7: Day 14 Trial Decision
**Where:** Email + in-app modal
**Goal:** Convert free trial to paid

Modal triggered on day 14:
> *"Your free trial ends in 24 hours. Here's what you've got with SellerCopilot so far:*
> 
> *📊 12 conversations*
> *✅ 8 suggestions approved*
> *💰 Estimated monthly savings: $480*
> *🧠 Memory entries: 23*
> 
> *Continue for $89/mo? [Yes, charge me] [Maybe later]"*

**No retention call. No "are you sure" friction. One click each direction.**

**Success metric:** 30%+ trial-to-paid conversion (industry standard for B2B SaaS)

---

## Edge Cases

### Customer connects Amazon but has <30 days of data
- Show: *"Your account has [N] days of data. I'll work with what I have, but suggestions will be more valuable after 30 days. You'll see better insights starting [date]."*
- Don't block use, but set expectations

### Customer asks the agent something it can't answer
- Agent says: *"I don't know that yet. Here's what I CAN see in your data: [...]. Should I look further?"*
- **Honesty over confidence.** This IS the differentiator.

### Customer's first suggestion fails (ACOS gets worse)
- 7-day check-in email is BLUNT: *"My suggestion didn't work. ACOS went from 41% to 47%. Here's what I learned: [...]. I've saved this in memory. Want to try a different approach?"*
- This is the moment that builds trust. Most tools blame the seller. SellerCopilot owns it.

### Customer wants to disconnect Amazon
- 1-click in settings
- Agent says: *"OK, disconnecting. Your memory will be saved for 30 days in case you reconnect. After that, deleted."*
- Clean exit. No retention spam.

---

## What to NOT do in onboarding

❌ Don't ask 20 onboarding questions (3 max)
❌ Don't show a tutorial video before first use (let the agent be the tutorial)
❌ Don't require credit card upfront (kills conversion)
❌ Don't auto-pause campaigns without approval (Amazon policy + trust)
❌ Don't email more than 1x/week (spam)
❌ Don't send "are you sure?" cancel modals (anti-pattern)

---

## Metrics Dashboard for Founder (Meir)

Track these in `/admin` (use existing pattern from `server.py:3870`):

**Funnel metrics:**
- Landing → Signup (target: 8%)
- Signup → Amazon Connected (target: 70%)
- Connected → First Conversation (target: 95%)
- First Conversation → First Approved Suggestion (target: 50%)
- Trial → Paid (target: 30%)

**Quality metrics:**
- Average conversations per customer per week
- Memory hit rate (% of agent responses referencing past memory)
- Suggestion approval rate (% of suggestions approved)
- 7-day retention (% still active week 2)
- 30-day retention (% still active month 2)

**Business metrics:**
- MRR
- ARR
- Churn (monthly)
- LTV / CAC

---

*This onboarding flow is a hypothesis. Test with first 5 design partners. Iterate.*

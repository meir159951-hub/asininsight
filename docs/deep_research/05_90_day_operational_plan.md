# 📅 SellerCopilot — 90-Day Operational Plan (Week-by-Week)

> **Purpose:** Tactical day-by-day plan from validation to first paying customers.
> **Date:** 2026-05-11
> **For:** Solo bootstrapper (Meir) with limited time (2-4 hours/day)
> **Outcome target:** 15 paying customers by Day 90

---

## 🎯 The 90-Day Story Arc

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Day 1 ──── Day 14 ──── Day 30 ──── Day 60 ──── Day 90              │
│                                                                     │
│  VALIDATE    DECIDE     BUILD       LAUNCH      SCALE TO 15          │
│  (no code)   (gate)     (MVP)       (5 design   (15 paying)         │
│                                      partners)                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📆 WEEK 1 — Validation kickoff

### Goal
Get the first 5 substantive responses from real sellers.

### Daily commitments (2-3 hours/day)

**Day 1 (Monday):**
- ☐ Open Amazon Seller Central forum, post Survey #1 (from `docs/validation_surveys.md`)
- ☐ Apply to FBA High Rollers Facebook group
- ☐ Update LinkedIn profile (headline: *"Building SellerCopilot — AI PPC that remembers your Amazon business"*)
- ☐ Send Twitter DMs to 3 FBA voices (Steven Pope, Brock Johnson, Brian Johnson)
- ☐ Set up simple Google Sheet CRM (use template in `04_founder_sales_playbook.md`)

**Day 2 (Tuesday):**
- ☐ Reply to every comment on Seller Central post (within 2 hours)
- ☐ Comment on 5 other PPC pain threads (substantive answers, no pitch)
- ☐ Post 1 thoughtful tweet about AI PPC
- ☐ Check Twitter DMs → respond if anyone replied

**Day 3 (Wednesday):**
- ☐ Reply to Seller Central comments
- ☐ Comment on 5 more PPC threads
- ☐ LinkedIn outreach: 15 personalized connection requests
- ☐ Post 1 LinkedIn insight

**Day 4 (Thursday):**
- ☐ Forum engagement (same routine)
- ☐ Check if FBA High Rollers approved your application → if yes, lurk only today
- ☐ Twitter: 1 thread on a PPC topic

**Day 5 (Friday):**
- ☐ Review Week 1 responses
- ☐ Tag each as 🟢 strong / 🟡 medium / 🔴 weak
- ☐ DM 3 strong respondents: *"Open to 20-min Zoom next week?"*
- ☐ Weekly review (1 hour): what worked, what didn't

**Weekend:**
- Light engagement only
- Read voice-of-customer compendium (`docs/deep_research/02_voice_of_customer_deep.md`)
- Mental rest

### End of Week 1 measure
- ☐ 10+ thoughtful conversations
- ☐ 3+ strong "I'd pay for this" indications
- ☐ 0 customers (expected)

---

## 📆 WEEK 2 — Discovery calls + FB groups

### Goal
Conduct 5-10 discovery calls. Get into FBA High Rollers.

### Daily

**Day 8-9:**
- ☐ Take 2-3 discovery calls (use script in `04_founder_sales_playbook.md`)
- ☐ After each call: send thank-you email + summary within 1 hour
- ☐ Update CRM

**Day 10:**
- ☐ Post FBA High Rollers survey if approved (Survey #2 from `docs/validation_surveys.md`)
- ☐ Engage 5 posts (genuine comments, no pitch)
- ☐ 2-3 discovery calls

**Day 11-12:**
- ☐ Continue forum engagement
- ☐ More discovery calls (5-10 total this week)
- ☐ LinkedIn: 15 more outreach + 1 post

**Day 13 (Friday):**
- ☐ Review Week 2
- ☐ Identify 2-3 hottest prospects (ready to buy)
- ☐ Email them with design partner offer (templates in playbook)

### End of Week 2 measure
- ☐ 5-10 discovery calls completed
- ☐ 2-3 hot prospects identified
- ☐ FBA High Rollers post live
- ☐ 0-1 paying customer (early)

---

## 📆 WEEK 3 — Decision gate + first sales

### Goal
Decision: Build MVP or pivot? Plus: close first 1-3 customers.

### Day 15 (Decision Day — Monday morning)

This is the gate. Open `docs/validation_surveys.md` and review the criteria:

✅ **GO criteria:**
- 5+ strong "I'd pay $89/mo" responses
- 3+ specific examples of what sellers want memory for
- 1+ paying design partner (or strong commitment to pay)

🟡 **REFINE criteria:**
- 3-4 strong responses
- Mixed signals
- → Run another round with sharper questions

🔴 **PIVOT criteria:**
- <3 strong responses
- No paying customers after 2 weeks of asking
- → Consider returning to ASINInsight CSV product (already 80% built)

### If GO: Days 16-21

**Day 16:**
- ☐ Email all hot prospects: *"I'm starting builds with 5 design partners. You're top of my list. $49/mo locked for 12 months. Want in?"*
- ☐ Set up Paddle subscriptions for $49 design partner tier

**Day 17-18:**
- ☐ Take 2-3 closing calls
- ☐ Close 1-3 design partners
- ☐ Onboard: schedule first weekly check-in, send welcome email

**Day 19-21:**
- ☐ Continue acquisition (forums, DMs, calls)
- ☐ Begin MVP build planning
- ☐ Set up dev environment for Anthropic Agent SDK

### End of Week 3 measure
- ☐ 1-3 paying design partners ($49-$147 MRR)
- ☐ Decision gate passed (or pivot decision made)
- ☐ MVP build plan locked

---

## 📆 WEEK 4 — Build sprint begins

### Goal
Set up the SellerCopilot MVP infrastructure.

### Build tasks (4 hours/day for 1 week)

**Day 22-23: Anthropic Agent SDK integration**
- ☐ `pip install claude-agent-sdk` + dependencies
- ☐ Create `sellercopilot_agent.py` based on reference in `docs/sample_agent_code.md`
- ☐ Test: basic conversation, memory write, memory read
- ☐ Commit to repo on new branch

**Day 24-25: Memory layer**
- ☐ Implement memory directory structure (profile/decisions/learnings/strategy)
- ☐ Test memory persistence across sessions
- ☐ Build memory inspector UI (basic version)

**Day 26-27: Chat UI**
- ☐ Build `/ppc/chat` route in Flask
- ☐ Server-sent events for streaming responses
- ☐ Simple HTML+JS chat interface (no React, follow repo pattern)

**Day 28 (Friday):**
- ☐ Internal testing with your own Amazon account (if applicable)
- ☐ OR: Mock data testing
- ☐ Weekly review with design partners (call each one)

### Sales tasks (1-2 hours/day in parallel)

- ☐ Continue forum engagement (30 min/day)
- ☐ 1-2 discovery calls per day
- ☐ Aim to close 2-3 more design partners by Day 28

### End of Week 4 measure
- ☐ MVP basic flow working (chat → agent → memory)
- ☐ 3-5 design partners total
- ☐ 1 case study in progress (from design partners)

---

## 📆 WEEK 5 — Connect MVP to Amazon

### Goal
Hook the existing OAuth + Ads API code to the new agent.

### Build tasks

**Day 29-30:**
- ☐ Review existing code in `ppc_oauth.py`, `ppc_ads_client.py`, `ppc_snapshot_fetcher.py`
- ☐ Wire agent to use existing OAuth flow
- ☐ Test: agent can fetch PPC data via existing client

**Day 31-32:**
- ☐ Implement `propose_suggestion` tool (writes to `ppc_suggestions` table)
- ☐ Build approval UI (suggestion card in chat)
- ☐ Implement `apply_suggestion` with hard caps (50/week, 20%/24h)

**Day 33-34:**
- ☐ Implement audit log writes
- ☐ Implement 30-day rollback
- ☐ Compliance check: walk through `docs/amazon_compliance_checklist.md`

**Day 35 (Friday):**
- ☐ Test full flow: connect → conversation → suggestion → approval → applied to Amazon
- ☐ Weekly review with design partners

### Sales tasks

- ☐ Continue acquisition
- ☐ Target: 5 design partners closed

### End of Week 5 measure
- ☐ MVP runs end-to-end on a test account
- ☐ 5 design partners total
- ☐ Compliance checklist 80% complete

---

## 📆 WEEK 6 — Beta onboard design partners

### Goal
Get all 5 design partners actually USING the product.

### Build tasks

**Day 36-37:**
- ☐ Build onboarding flow (per `docs/onboarding_flow_design.md`)
- ☐ First-conversation script (agent asks 3 questions, writes profile.md)
- ☐ Test with internal account

**Day 38-39:**
- ☐ Set up monitoring (basic): log all agent calls, errors
- ☐ Set up Anthropic API cost tracking per customer
- ☐ Set up basic dashboard for Meir (admin view)

**Day 40-42:**
- ☐ Onboard design partners one at a time
- ☐ Each onboarding = 30-min Zoom call with Meir present
- ☐ Document every issue/bug/request

### Sales tasks
- ☐ Continue acquisition with focus on Pilot tier ($89) — design partner spots filled

### End of Week 6 measure
- ☐ 5 design partners using the product
- ☐ 30+ documented feedback items
- ☐ MRR: $245 (5 × $49)
- ☐ 0-2 Pilot tier customers ($89) starting to come in

---

## 📆 WEEK 7 — Iterate on partner feedback

### Goal
Fix the top 10 issues design partners raised.

### Build tasks

**Day 43-46:**
- ☐ Prioritize feedback list (impact × difficulty)
- ☐ Implement top 5 fixes
- ☐ Daily 15-min check-in with each partner

**Day 47-49:**
- ☐ Implement top 5-10 fixes
- ☐ Weekly call with each partner (longer, more strategic)

### Sales tasks

- ☐ Begin publishing SEO blog post #1 (use draft in `marketing/blog_seo_drafts.md`)
- ☐ Continue forum engagement
- ☐ 3-5 discovery calls per week

### End of Week 7 measure
- ☐ 10 product fixes shipped
- ☐ 7-10 customers total
- ☐ MRR: ~$500-$700
- ☐ Blog post #1 published

---

## 📆 WEEK 8 — Polish + launch publicly

### Goal
Prepare to take SellerCopilot from "beta" to "live for anyone."

### Build tasks

**Day 50-52:**
- ☐ Build out memory inspector UI (per `docs/ui_sketches.md`)
- ☐ Build decision log UI
- ☐ Polish chat interface

**Day 53-56:**
- ☐ Update landing page (use copy from `docs/landing_repositioning_draft.md`)
- ☐ Set up pricing page
- ☐ Set up signup flow with Paddle
- ☐ Privacy policy + ToS

### Marketing tasks

**Day 52-54:**
- ☐ Get 2 design partner case studies in writing
- ☐ Get permission to publish (with anonymization if needed)
- ☐ Schedule LinkedIn post: "We're now live"

### End of Week 8 measure
- ☐ Public site live
- ☐ Signup flow working end-to-end
- ☐ 2 published case studies
- ☐ 10-12 customers total

---

## 📆 WEEK 9 — Launch announcement

### Goal
Generate inbound interest from the announcement.

### Activities

**Day 57 (Monday):**
- ☐ LinkedIn announcement post (Meir personal account)
- ☐ Twitter announcement thread
- ☐ Email warm contacts: "We're live"

**Day 58-59:**
- ☐ Post to Hacker News (Show HN) — Tuesday morning is best
- ☐ Post to Indie Hackers
- ☐ Post to Product Hunt (be prepared for the day)

**Day 60-63:**
- ☐ Engage with comments/responses on all platforms
- ☐ Take inbound demo calls (expect 5-15)
- ☐ Close new customers at full $89/mo

### End of Week 9 measure
- ☐ 12-18 customers total
- ☐ MRR: ~$1,000-$1,500
- ☐ Substantial inbound interest

---

## 📆 WEEK 10 — Content marketing rhythm

### Goal
Start the SEO content engine that will compound.

### Activities

**Day 64-67:**
- ☐ Publish SEO blog post #2 (Agency vs Tool, from draft)
- ☐ Cross-post excerpts to LinkedIn + Twitter
- ☐ Submit to Marketplace Pulse newsletter

**Day 68-70:**
- ☐ Begin podcast outreach (top 5 from `docs/deep_research/03_gtm_channel_scorecard.md`)
- ☐ Pitch: "Built an AI agent with memory for Amazon PPC"
- ☐ Don't expect immediate booking — relationships take time

### End of Week 10 measure
- ☐ 15-20 customers total
- ☐ MRR: ~$1,300-$1,800
- ☐ 2 blog posts published
- ☐ 3-5 podcast pitches sent

---

## 📆 WEEK 11 — Optimization + retention

### Goal
Focus on keeping the customers you have.

### Activities

**Day 71-73:**
- ☐ Customer health check: any signals of churn risk?
- ☐ Reach out personally to anyone showing lower engagement
- ☐ Reinforce wins: send each customer their personal "savings so far" summary

**Day 74-77:**
- ☐ Implement next 5 product improvements based on feedback
- ☐ Run a "What would make this 10x better?" survey with all customers

### End of Week 11 measure
- ☐ 18-22 customers
- ☐ 95%+ retention (no churn yet)
- ☐ MRR: ~$1,600-$2,000

---

## 📆 WEEK 12 — Scale prep

### Goal
Set the foundation for Year 2 growth.

### Activities

**Day 78-81:**
- ☐ Document everything in the repo:
  - ☐ Update PROJECT.md with what you learned
  - ☐ Build a customer FAQ from real questions
  - ☐ Update CLAUDE.md with new context for future sessions

**Day 82-84:**
- ☐ Set up basic analytics dashboard
- ☐ Set up email drip campaigns for trial users
- ☐ Set up referral mechanism (simple discount code)

**Day 85-90:**
- ☐ Continue acquisition (steady drumbeat)
- ☐ Publish blog post #3
- ☐ Plan Q2 (months 4-6)

### End of Week 12 / Day 90 measure
- ☐ **15+ paying customers** (target)
- ☐ MRR: **$1,300-$1,800**
- ☐ 2-3 case studies published
- ☐ 2-3 blog posts published
- ☐ Foundation laid for Year 2 growth

---

## 🚦 Decision Gates (review every Friday)

### Friday Week 2 — Validation gate
- Pass: 5+ strong responses → Build
- Fail: <3 strong → Pivot or refine

### Friday Week 4 — Build gate
- Pass: MVP runs end-to-end → Onboard partners
- Fail: Major blockers → Pause acquisition, focus on build

### Friday Week 6 — Beta gate
- Pass: 5 partners actively using → Ready for public launch
- Fail: Partners not using → Discover why before scaling

### Friday Week 9 — Launch gate
- Pass: 10+ customers, no major bugs → Public push
- Fail: Major issues → Hold launch, fix first

### Friday Week 12 — Scale gate
- Pass: 15+ customers, retention >85% → Year 2 plan
- Fail: <10 customers or high churn → Investigate

---

## 📊 Daily/Weekly Rituals

### Daily (10 min, morning)
- Check: customer messages, support requests, urgent issues
- Top 3 priorities for the day

### Weekly (Friday afternoon, 1 hour)
- MRR update
- Customer count update
- Top 3 wins / Top 3 issues / Top 3 next week
- Update CRM

### Monthly (last Friday, 2 hours)
- Cohort analysis (who churned, who stayed)
- Channel ROI (which channels brought in customers)
- Product priorities (what to build next)
- Marketing priorities (what content to write)

---

## 💡 Critical Reminders

1. **You will be exhausted.** This is normal. Pace yourself. Take Sundays mostly off.

2. **You will doubt yourself.** This is normal. Read your customer testimonials.

3. **You will want to add features.** Don't, unless 3+ customers asked for the same thing.

4. **You will want to lower prices.** Don't, except for the design partner offer.

5. **You will want to skip sales for "just one more feature."** Don't.

6. **Talk to a customer every single day.** Even if it's just a quick check-in.

7. **Celebrate every win.** First paying customer. First testimonial. First referral. They matter.

---

## 📚 Reference Docs

- `docs/validation_surveys.md` — Templates for outreach
- `docs/facebook_groups_guide.md` — FB group entry strategy
- `docs/deep_research/04_founder_sales_playbook.md` — Sales script
- `docs/deep_research/03_gtm_channel_scorecard.md` — Channel ROI ranking
- `docs/technical_architecture_mvp.md` — Build phase architecture
- `docs/amazon_compliance_checklist.md` — Compliance gates

---

*This 90-day plan is ambitious but achievable. Don't try to optimize it — execute it. Real life will force changes. Adapt.*

# SellerCopilot — Risk Register

> **Purpose:** Identify, score, and plan mitigation for every risk that could kill the project.
> **Date:** 2026-05-11
> **Format:** Risk → Likelihood (1-5) × Impact (1-5) = Score → Mitigation

---

## 🔴 Critical Risks (Score 16-25)

### R1: Customer validation fails

**Risk:** Sellers don't actually want "memory" enough to switch from Helium 10/Adtomic.
**Likelihood:** 3/5 (memory is intuitively appealing but B2B inertia is real)
**Impact:** 5/5 (project dead)
**Score:** 15

**Early signals:**
- <5 substantive responses to validation surveys after 7 days
- Most responses are "interesting but I'd stay with my current tool"
- No specific examples of what they want remembered

**Mitigation:**
- 1-week validation gate before any code work (already built)
- Three different positioning tests (memory / honest AI / anti-agency)
- Backup plan: pivot to ASINInsight CSV product (already 80% built)

**Owner:** Meir (must run validation surveys)

---

### R2: Amazon API access revoked

**Risk:** Amazon decides our agent violates Agent Policy → API key revoked → product dies overnight.
**Likelihood:** 2/5 (low if compliant, but Amazon has discretion)
**Impact:** 5/5 (no API = no product)
**Score:** 10

**Triggers that increase likelihood:**
- Auto-applying changes without seller approval
- Exceeding rate caps (50/week, 20%/24h)
- Not self-identifying in User-Agent
- Receiving customer complaints to Amazon

**Mitigation:**
- Full compliance checklist completion (`amazon_compliance_checklist.md`)
- Conservative caps (we can do less than allowed)
- Legal review of terms of service
- Direct relationship with Amazon (apply for SPP listing once stable)
- Backup plan: pivot to CSV-import architecture (slower but no API dependency)

**Owner:** Meir + outside legal counsel pre-launch

---

### R3: Anthropic Managed Agents prices spike

**Risk:** Anthropic raises Managed Agents prices significantly during beta or post-GA. Currently $0.08/session-hour.
**Likelihood:** 3/5 (beta pricing usually goes up at GA)
**Impact:** 4/5 (margin compression but not dead)
**Score:** 12

**Early signals:**
- Anthropic announces price changes
- Per-customer cost crosses $20/mo (was $5-10)
- Margin drops below 70%

**Mitigation:**
- Monitor cost per customer monthly
- Build with abstraction layer — agent logic should swap LLM provider easily
- Backup plan: direct Claude API + custom file-backed memory (more work, similar feature)
- Long-term: optimize prompt caching (10% cost) and batch operations (50% off)

**Owner:** Meir (cost monitoring)

---

## 🟡 High Risks (Score 9-15)

### R4: Competitor adds memory feature first

**Risk:** Astra, AutoPilot, or new entrant launches "AI agent with memory" before SellerCopilot reaches PMF.
**Likelihood:** 4/5 (the concept is in the air — SellerLabs already wrote about it)
**Impact:** 3/5 (we lose first-mover but not the war)
**Score:** 12

**Triggers that increase likelihood:**
- SellerLabs launches a product after their blog post
- Helium 10 adds "AI advisor" mode to Adtomic
- A well-funded startup with VC money outpaces us

**Mitigation:**
- Speed: ship MVP in 10 weeks, not 26
- Sharp positioning: "honest AI" not just "memory"
- Lock in customers with annual prepay discounts
- Move to founder-led sales (Meir → 50 sellers personally)
- Don't compete on feature parity — compete on conversation quality

**Owner:** Meir (ship fast)

---

### R5: Amazon's own Ads Agent expands to Sponsored Products

**Risk:** Amazon Ads Agent (currently DSP/AMC enterprise only) opens to all Sponsored Products sellers.
**Likelihood:** 4/5 (Amazon has signaled this is the direction)
**Impact:** 3/5 (free competitor, but limited features and account-managed only)
**Score:** 12

**Why we'd survive:**
- Amazon Ads Agent is account-managed (need rep), not self-serve
- Amazon's tool serves THEIR interests (more spend), not seller's
- We still have the conversational + memory + honest reasoning angle

**Mitigation:**
- Position SellerCopilot explicitly: "Built for sellers, not for Amazon's ad revenue"
- Emphasize independence: "We work for you"
- Move fast on the conversation quality moat — Amazon won't compete on UX

**Owner:** Meir (positioning)

---

### R6: Founder bandwidth (solo + meetings)

**Risk:** Meir has limited hours, no co-founder, and other commitments. Project stalls due to slow iteration.
**Likelihood:** 4/5 (already happening — meetings during work day)
**Impact:** 3/5 (slows things, doesn't kill)
**Score:** 12

**Mitigation:**
- Use Claude Code aggressively for everything possible (research, code, docs)
- Customer development can be async (forum posts, FB posts vs synchronous calls)
- Set strict 2-hour daily focus block on the project
- Parallelize: validation surveys run in background while building MVP
- Outsource non-core work (legal, design) once revenue starts

**Owner:** Meir (time management)

---

### R7: Anthropic Managed Agents has technical limits we hit

**Risk:** Memory directory size limits, session quotas, or API constraints make the architecture unworkable at scale.
**Likelihood:** 2/5 (early product, edges unknown)
**Impact:** 4/5 (forces re-architecture)
**Score:** 8

**Unknown limits:**
- Max memory directory size per workspace
- Max concurrent agent sessions
- Long-running session timeout

**Mitigation:**
- Build abstraction layer for memory (can swap to S3 + vector DB if needed)
- Test with realistic load early (5 design partners with full data)
- Have backup plan: Mem0 + Postgres + custom orchestration

**Owner:** Meir (technical research during build)

---

## 🟢 Medium Risks (Score 5-8)

### R8: Sellers don't trust AI to make PPC decisions

**Risk:** Even if memory works, sellers fundamentally don't trust AI for high-stakes financial decisions.
**Likelihood:** 3/5 (varies by demographic — younger sellers more trusting)
**Impact:** 2/5 (limits TAM but doesn't kill)
**Score:** 6

**Mitigation:**
- Approval-required design (seller controls every change)
- Show reasoning for every suggestion
- Highlight 30-day rollback prominently
- Case studies from beta customers

---

### R9: Brand name "SellerCopilot" already taken

**Risk:** Domain or trademark unavailable. Need to rebrand pre-launch.
**Likelihood:** 3/5 (Copilot is genericized, but specific phrase might be taken)
**Impact:** 2/5 (frustrating, not fatal)
**Score:** 6

**Mitigation:**
- Check domains today: sellercopilot.com / .ai / .app / .io
- Backup names ready (PPCMemory, AmzCopilot — see `competitive_deep_dive_2026_05.md`)
- USPTO trademark search before any major brand investment

**Owner:** Meir (domain check this week)

---

### R10: Reddit / Facebook surveys yield low quality data

**Risk:** Anonymous surveys attract low-information responses, miss the actual ICP.
**Likelihood:** 3/5 (forums have noise)
**Impact:** 2/5 (slows validation but doesn't kill)
**Score:** 6

**Mitigation:**
- 5 channels, not just 1 (forum, FB, Twitter DMs, LinkedIn)
- Decision gate uses signal quality, not just quantity (5 strong > 50 weak)
- Backup: paid interviews via UserInterviews ($250-500)

---

### R11: Claude Sonnet 4.6 deprecated or replaced

**Risk:** Anthropic deprecates Sonnet 4.6, forcing migration mid-product.
**Likelihood:** 2/5 (low in first 12 months)
**Impact:** 2/5 (model swap is straightforward)
**Score:** 4

**Mitigation:**
- Code uses model name as config, not hardcoded
- Test against newer models periodically (Opus, Haiku)
- Stay current with Anthropic announcements

---

### R12: Customer support burden grows faster than revenue

**Risk:** Solo founder + 100 paying customers = 8 hours/day of support, no time to build.
**Likelihood:** 3/5 (real if growth is fast)
**Impact:** 2/5 (manageable with planning)
**Score:** 6

**Mitigation:**
- Self-serve onboarding (no hand-holding required for happy path)
- FAQ + help docs from day 1
- Async support (email only, no live chat for first 6 months)
- Hire VA at first $5K MRR
- Drop annoying customers (unprofitable to keep at 50% time consumption)

---

## 🟢 Low Risks (Score 1-4)

### R13: Railway (current hosting) outage

**Risk:** Railway down → product down.
**Likelihood:** 1/5 (rare)
**Impact:** 2/5 (recoverable)
**Score:** 2

**Mitigation:** Standard incident response. SLA notice to customers if outage >2 hours.

---

### R14: Postgres data loss

**Risk:** DB corruption or accidental deletion.
**Likelihood:** 1/5
**Impact:** 4/5 (memory + decision history lost)
**Score:** 4

**Mitigation:**
- Railway has automatic backups
- Daily snapshot to off-platform storage (S3)
- Point-in-time recovery enabled
- Test restore monthly

---

### R15: GDPR / privacy lawsuit

**Risk:** EU customer files complaint over data handling.
**Likelihood:** 1/5 (US-first launch limits exposure)
**Impact:** 4/5 (lawyers $$, reputation damage)
**Score:** 4

**Mitigation:**
- US-only launch for first 6 months
- Privacy policy from day 1
- Don't process EU data without explicit consent
- Memory data deletable on request

---

## 📊 Risk Summary

| # | Risk | Score | Status |
|---|------|-------|--------|
| R1 | Customer validation fails | 15 | 🟡 Active mitigation in progress |
| R2 | Amazon API access revoked | 10 | 🟡 Pre-launch mitigation needed |
| R3 | Anthropic price spike | 12 | 🟢 Monitor only |
| R4 | Competitor adds memory first | 12 | 🟡 Speed = mitigation |
| R5 | Amazon Ads Agent expands to SP | 12 | 🟢 Position around it |
| R6 | Founder bandwidth | 12 | 🟡 Active management needed |
| R7 | Anthropic Managed Agents limits | 8 | 🟢 Test during build |
| R8 | Sellers don't trust AI | 6 | 🟢 Approval design solves |
| R9 | Brand name taken | 6 | 🟡 Check domains this week |
| R10 | Survey data low quality | 6 | 🟢 Multi-channel mitigates |
| R11 | LLM deprecation | 4 | 🟢 Easy swap |
| R12 | Support burden | 6 | 🟢 Plan ready |
| R13 | Hosting outage | 2 | 🟢 Standard SRE |
| R14 | Data loss | 4 | 🟢 Backups exist |
| R15 | GDPR lawsuit | 4 | 🟢 US-first limits exposure |

**Top 3 to monitor weekly:**
1. R1 (validation) — gates everything
2. R6 (bandwidth) — could slow project to death
3. R4 (competitor speed) — race condition

---

*This doc is a living register. Update monthly or when significant new info surfaces.*

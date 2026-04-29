# ASINInsight — Gap Analysis Before Customer Acquisition
*Compiled April 2026 after audit of code + live site + marketing docs.*

Read this before pushing the site to potential customers.

---

## Tier 1 — Foundational Truth Issues (FIX FIRST)

### Gap 1.1 — Marketing positioning lies about privacy (CRITICAL)

**The lie:** `positioning_v2.md` and `BRIEF.md` claim *"Nothing leaves your browser"* and *"client-side processing"*.

**The truth:** `app.html` line 702 — `fetch('/api/diagnose', { method: 'POST', body: formData })`. The CSV uploads to the server. Server processes it. CSV is held in memory, not stored — but it absolutely does leave the browser.

**Live site copy is honest** (`app.html` line 412): *"Your file is analyzed on our server and deleted immediately. Never stored, never shared."*

**Severity:** 🔴 Critical. If a customer challenges the privacy claim and we point at our marketing doc, we're caught lying.

**Fix:** Rewrite marketing docs to match reality. The OTHER differentiators are still TRUE:
- ✅ No SP-API / no Amazon login
- ✅ No credit card to start
- ✅ Deleted in seconds, never stored, never shared, never used to train AI
- ❌ But NOT "nothing leaves your browser"

**Action:** I'll fix the docs now (positioning_v2.md, BRIEF.md, competitor_teardowns.md).

### Gap 1.2 — FAQ #4 contradicts product behavior

**Live FAQ (`landing.html` line 731):** *"By design, you see the single highest-priority issue."*

**Live product:** Returns a full numbered action plan with multiple steps (verified in my live test). The "single issue only" framing was true at some earlier version.

**Severity:** 🟡 Medium. Customers feel deceived (in the GOOD direction — getting more than promised — but still inconsistent).

**Fix:** Rewrite FAQ #4 to match current behavior.

### Gap 1.3 — Made-up stats on hero

**Live homepage shows:**
- "2,567 listings diagnosed"
- "$280 avg monthly impact found"
- "30s to your first diagnosis"

**Reality:** These look fabricated. The site isn't tracking real diagnostic counts that way. If a customer asks for proof, we have none.

**Severity:** 🟡 Medium. Risk: trust collapse if discovered.

**Fix:** Either (a) wire up real tracking and use real numbers, or (b) replace with honest framing ("Built to read the same Business Report you already export every month" — no number claim).

---

## Tier 2 — Customer-Ready Polish (FIX BEFORE ACQUISITION)

### Gap 2.1 — Anti-funnel not implemented

**The wedge** (per positioning research): "Audit before signup. Email gate at PDF/save. Card gate at >3/mo."

**Reality:** `/tool` route requires `session.get("plan")` to be set. To get there, user must POST to `/checkout/free` (which sets `plan="free"`). All "Diagnose my listing free" buttons hit this same /checkout/free POST. So technically the user signs up before audit — even though we call it "free."

**Severity:** 🟡 Medium. The friction is small (just a click), but the WEDGE depends on this being legitimate. The whole "no signup before value" pitch in marketing isn't really true today.

**Fix options:**
- (A) Allow `/tool` access without `plan` cookie. First audit free for any browser session. Email/card gates only at PDF export and >3/mo.
- (B) Keep current flow but rename — the "Start free" click IS effectively a no-friction signup. Truth in advertising.

**Recommendation:** Option A. Real anti-funnel = real differentiator.

### Gap 2.2 — No trust strip on hero

**Per positioning research:** Three pillars should be visible ON THE HERO:
- 🔒 No Amazon login. No SP-API. Deleted in seconds, never stored.
- 🎯 Prescription, not grading. Critical issues, ranked. Plain English.
- 💸 One-click cancel. No retention calls. No forced renewal.

**Reality:** Current hero shows headline + sub-hero + 3 stats + 2 CTAs. No trust strip.

**Severity:** 🟢 Quick win. Adds trust before scroll.

**Fix:** Insert trust strip below hero CTA, above stats.

### Gap 2.3 — Pricing comparison too similar (Free vs Pro)

**Reality (verified in live test):** The comparison table at `/pricing` shows:
- Free: ✓ Action plan, ✓ Revenue impact, ✓ Email delivery, 3 audits/mo
- Pro: same ✓s, plus unlimited audits

The ONLY material difference is volume. Customers will ask "why pay $49 if free has all the features?"

**Severity:** 🟡 Medium. Conversion friction.

**Fix options:**
- (A) Add Pro-only features: PDF export, audit history, multi-ASIN batch, "what changed since last audit," priority email support
- (B) Restrict Free to only show top 1 issue per audit (like FAQ #4 currently claims)
- (C) Honest reframing: "Free = try it. Pro = use it weekly without limits."

**Recommendation:** (A) + (C) combined.

### Gap 2.4 — "One-click cancel" not visible on pricing

**Per positioning research:** The single biggest differentiator vs Helium 10/JS/ZonGuru is the cancellation horror reviews on those tools. ASINInsight should make cancellation transparency a primary trust signal.

**Reality:** `/pricing` page shows price tiers and features. Nothing about cancellation.

**Severity:** 🟢 Quick win.

**Fix:** Add a visible line under each price: *"One-click cancel. No calls. No charges after canceling."*

### Gap 2.5 — FAQ missing common red-flag preempts

**Per voice_of_customer.md:** sellers warn each other about specific tool behaviors. The FAQ should preempt each:
- Generic AI advice → not on current FAQ
- Cancellation friction → not on current FAQ
- "Tools that just say 'spend more on ads'" → not on current FAQ
- Fake "free audit" lead-magnets → partially covered

**Severity:** 🟢 Easy add.

**Fix:** Add 3 FAQ items addressing each red flag.

---

## Tier 3 — Conversion Polish (NICE TO HAVE BEFORE ACQUISITION)

### Gap 3.1 — No demo video

**Per positioning research:** 90-second demo video on hero is "must have before any paid traffic."

**Reality:** No video exists. Current "demo" is a screenshot/GIF showing the app.

**Severity:** 🟢 Important but not blocker.

**Fix:** **You** record a 90-second Loom: paste a real anonymized CSV, show the tool generating ranked output. No music, no edits, no logo intro. I cannot do this — only you can.

### Gap 3.2 — No real case study

**Reality:** Site shows fabricated stats ("2,567 listings diagnosed") but no real case study with before/after numbers from a real seller.

**Severity:** 🟢 Important for ad creative + podcast pitches.

**Fix:** **You** find a beta seller, audit their CSV, ask permission to publish before/after. Or write a synthetic but clearly-labeled "what an audit looks like" walkthrough using a sample CSV.

### Gap 3.3 — Hero copy untested

**Per positioning research:** Multiple hero variants worth testing. Current hero: *"Your Business Report already has the answer. We just tell you which line."* Decent but not tested.

**Severity:** 🟢 Optimize after first 100 visitors.

**Fix:** I'll add 4 hero variants to the codebase as comments, ready for A/B test infrastructure later.

---

## Tier 4 — Things ONLY YOU Can Test

I cannot verify these from my browser sessions. They need a real human.

| Gap | Why I can't test | What you need to do |
|---|---|---|
| **Real email delivery to inbox** | I don't have a real inbox to receive emails | Submit your real email through the site, verify it arrives in <2 min and isn't in Spam |
| **Mobile responsiveness** | Browser kept freezing on resize attempts | Open `asininsight.com` on your phone, walk through full flow: home → start free → upload → audit → email modal |
| **Paddle full checkout** | I cannot use a real credit card | Use Paddle's test card or do a real $49 transaction (and refund yourself), verify Pro session activates after payment |
| **Cookie consent flow** | Some flow paths I haven't walked | Click "Reject all cookies" — does the site still work? Does GA NOT fire? |

---

## Priority Order — What I'm Doing Now

1. **Fix the marketing doc lies** (Tier 1.1) — 10 minutes, in progress
2. **Fix FAQ #4 to match reality** (Tier 1.2) — 5 minutes
3. **Replace fake stats with honest framing** (Tier 1.3) — 10 minutes
4. **Implement real anti-funnel** (Tier 2.1) — 30-60 minutes (code change)
5. **Add trust strip to hero** (Tier 2.2) — 15 minutes
6. **Differentiate Free vs Pro on pricing** (Tier 2.3) — 30 minutes (decide which features)
7. **Add "one-click cancel" trust line** (Tier 2.4) — 5 minutes
8. **Add 3 FAQ red-flag preempts** (Tier 2.5) — 15 minutes

**Total estimated time for Tier 1 + 2: ~2-3 hours of code/copy work.**

Tier 3 items I'll set up the structure for, but you complete (demo video, case study).

Tier 4 items only you can do.

---

## What This Gap Audit Found That Round 2 Marketing Research Missed

The deep market research I did yesterday was *strategic* but missed the *tactical truth check* — does the product actually deliver on the wedge? Two big misses:

1. **Privacy claim** — assumed client-side based on "client-side CSV analysis" mention in old project notes. Should have read the code first.
2. **Anti-funnel** — designed the wedge in `BRIEF.md` without verifying the live `/tool` route requires session.plan.

**Lesson:** verify product behavior against marketing claims BEFORE writing positioning. I'll do this every time going forward.

# SellerCopilot — UI Sketches (ASCII)

> **Purpose:** Visual reference for what each major screen looks like before building.
> **Status:** Conceptual — not pixel-perfect mockups.
> **Date:** 2026-05-11

---

## 📋 Screen Inventory

1. Landing page (sellercopilot.com)
2. Signup flow (3 steps)
3. Amazon connection
4. Loading screen (data fetch)
5. Main dashboard / chat
6. Suggestion approval card
7. Memory inspector
8. Decision log
9. Settings / billing
10. Email — Day 7 check-in

---

## 1. Landing page

```
╔══════════════════════════════════════════════════════════════════════════╗
║   SellerCopilot                                  [Pricing] [Demo] [Login]║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║   Finally, a PPC tool you can actually talk to.                          ║
║   And it remembers everything.                                           ║
║                                                                          ║
║   Tell SellerCopilot your goals once. It remembers every decision,       ║
║   every campaign you tried, every margin floor — forever.                ║
║                                                                          ║
║   ┌─────────────────────────────────┐  ┌────────────────────────────┐   ║
║   │  Connect your Amazon account →  │  │  Watch 60-second demo      │   ║
║   └─────────────────────────────────┘  └────────────────────────────┘   ║
║                                                                          ║
║   ✓ No credit card  ✓ 14-day free trial  ✓ Cancel in 1 click            ║
║                                                                          ║
║   ──────────────────────────────────────────────────────────────────     ║
║                                                                          ║
║   🧠 Persistent memory             💬 Real conversations                 ║
║   Knows your business after        Not a dashboard. Ask it               ║
║   the first session. Forever.      anything about your account.          ║
║                                                                          ║
║   🎯 Honest reasoning              🔒 Amazon-policy compliant            ║
║   Shows its work. Admits           Self-identifies as AI agent.          ║
║   uncertainty. Never blames.       Hard caps. Full audit log.            ║
║                                                                          ║
║   ──────────────────────────────────────────────────────────────────     ║
║                                                                          ║
║                       How it compares to other tools                     ║
║                                                                          ║
║   ┌────────────────────────┬──────────┬──────────┬──────────┬─────────┐ ║
║   │                        │ Adtomic  │ AutoPilot│ Agency   │ SC      │ ║
║   ├────────────────────────┼──────────┼──────────┼──────────┼─────────┤ ║
║   │ Conversational         │    ❌    │    ❌    │   📧    │   ✅    │ ║
║   │ Remembers decisions    │    ❌    │    ❌    │  🟡   │   ✅    │ ║
║   │ Strategic, not tactical│    ❌    │    ❌    │   ✅    │   ✅    │ ║
║   │ Price                  │  $129   │  $695   │ $2K+    │ $89/mo │ ║
║   └────────────────────────┴──────────┴──────────┴──────────┴─────────┘ ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 2. Signup (Step 1 of 3)

```
╔════════════════════════════════════════════════════════╗
║   Welcome to SellerCopilot                             ║
║                                                        ║
║   Step 1 of 3: Create your account                     ║
║                                                        ║
║   Email                                                ║
║   ┌────────────────────────────────────────────────┐  ║
║   │                                                │  ║
║   └────────────────────────────────────────────────┘  ║
║                                                        ║
║   Password                                             ║
║   ┌────────────────────────────────────────────────┐  ║
║   │                                                │  ║
║   └────────────────────────────────────────────────┘  ║
║                                                        ║
║   ☐ I prefer to sign in with a magic link             ║
║                                                        ║
║   ┌──────────────────────────────────────────────┐    ║
║   │  Continue →                                  │    ║
║   └──────────────────────────────────────────────┘    ║
║                                                        ║
║   Already have an account? Log in                      ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
```

---

## 3. Amazon connection

```
╔════════════════════════════════════════════════════════╗
║   Step 2 of 3: Connect your Amazon account             ║
║                                                        ║
║   ┌─────────────────────────────────────────────────┐ ║
║   │                                                 │ ║
║   │           [ Amazon Logo ]                       │ ║
║   │                                                 │ ║
║   │     Connect Amazon Seller Central               │ ║
║   │                                                 │ ║
║   └─────────────────────────────────────────────────┘ ║
║                                                        ║
║   What we access:                                      ║
║   ✓ Read your PPC campaign data                       ║
║   ✓ Read your search-term reports                     ║
║   ✓ Read your inventory status                        ║
║                                                        ║
║   What we will NOT do without your approval:           ║
║   ✗ Change bids                                       ║
║   ✗ Pause campaigns                                   ║
║   ✗ Add negative keywords                             ║
║                                                        ║
║   Every action requires your one-click approval.       ║
║                                                        ║
║   🔒 Amazon-policy compliant (BSA Agent Policy 2026)  ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
```

---

## 4. Loading screen (data fetch)

```
╔════════════════════════════════════════════════════════╗
║   Step 3 of 3: Setting up your copilot                 ║
║                                                        ║
║   Hi, I'm SellerCopilot. I'm reading your account so   ║
║   I can have a real conversation with you about it.    ║
║                                                        ║
║   This takes 1-5 minutes. You can close this tab — I'll║
║   email you when ready.                                ║
║                                                        ║
║   ┌────────────────────────────────────────────────┐  ║
║   │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░ 47%        │  ║
║   └────────────────────────────────────────────────┘  ║
║                                                        ║
║   ✓ Connected to Amazon                                ║
║   ✓ Found 23 active campaigns                          ║
║   ✓ Pulled 30 days of spend data                       ║
║   ⟳ Reading your search-term report...                ║
║   ⏳ Analyzing keyword performance                     ║
║   ⏳ Building your account profile                     ║
║                                                        ║
║   Need help while you wait?                            ║
║   [ Watch demo ] [ Read FAQ ] [ Contact support ]      ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
```

---

## 5. Main dashboard / chat (the heart of the product)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║ SellerCopilot                              [Memory] [Decisions] [Settings]   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  AcmePets Account                                          Updated: 2 min ago║
║  ┌──────────────┬──────────────┬──────────────┬──────────────┐              ║
║  │ 30d Spend    │ Avg ACOS     │ Active Camps │ Suggestions  │              ║
║  │ $12,340      │ 41% ↘       │ 23           │ 3 pending    │              ║
║  └──────────────┴──────────────┴──────────────┴──────────────┘              ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐ ║
║  │                                                                        │ ║
║  │  🤖 SellerCopilot — 2 minutes ago                                      │ ║
║  │  ─────────────────────────────────                                     │ ║
║  │                                                                        │ ║
║  │  Hi! Since last week:                                                  │ ║
║  │                                                                        │ ║
║  │  ✅ SKU-A ACOS dropped from 38% to 31% — you're almost at target       │ ║
║  │     (the 3 suggestions you approved on May 4 are working)              │ ║
║  │                                                                        │ ║
║  │  ⚠️ SKU-Y ACOS spiked to 58% — exceeded your margin floor of 22%      │ ║
║  │     I have 1 immediate suggestion for this.                            │ ║
║  │                                                                        │ ║
║  │  💡 SKU-Z is performing well, ACOS at 26%. Want to discuss scaling?    │ ║
║  │                                                                        │ ║
║  │  What should we focus on first?                                        │ ║
║  │                                                                        │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐ ║
║  │                                                                        │ ║
║  │  👤 You                                                                │ ║
║  │  ─────                                                                 │ ║
║  │                                                                        │ ║
║  │  Show me what's happening with SKU-Y                                   │ ║
║  │                                                                        │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐ ║
║  │                                                                        │ ║
║  │  Type a message...                                                  ➤ │ ║
║  │                                                                        │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 6. Suggestion approval card (inline in chat)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║  🤖 SellerCopilot                                                            ║
║                                                                              ║
║  Here's what I'm seeing on SKU-Y:                                            ║
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  SUGGESTION                                                         │    ║
║  │  ────────                                                           │    ║
║  │                                                                     │    ║
║  │  Pause: "SKU-Y Manual Broad — Catch-All"                            │    ║
║  │                                                                     │    ║
║  │  Reason:                                                            │    ║
║  │  ┌──────────────────────────────────────────────────────────────┐  │    ║
║  │  │  ACOS this campaign:  58%                                    │  │    ║
║  │  │  Your margin floor:   22%                                    │  │    ║
║  │  │  Gap:                 36% — bleeding $4.20 per sale         │  │    ║
║  │  │  30d spend on this:   $890                                   │  │    ║
║  │  │  30d sales:           $1,520                                 │  │    ║
║  │  │  Estimated monthly waste: ~$320                              │  │    ║
║  │  └──────────────────────────────────────────────────────────────┘  │    ║
║  │                                                                     │    ║
║  │  Memory note:                                                       │    ║
║  │  You told me on May 4 your margin floor is 22%. This campaign is    │    ║
║  │  36 points above that. I'm proposing pause, not scale-back, because │    ║
║  │  the gap is large enough that even a 50% bid cut wouldn't fix it.   │    ║
║  │                                                                     │    ║
║  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐    │    ║
║  │  │  ✓ Approve     │  │  ✗ Reject      │  │  ❓ Tell me more   │    │    ║
║  │  └────────────────┘  └────────────────┘  └────────────────────┘    │    ║
║  │                                                                     │    ║
║  │  30-day rollback enabled.                                           │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 7. Memory inspector (the moat made visible)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  Memory — What I know about AcmePets                            [Export ↓]   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  📋 Profile (profile.md)                                            Updated: ║
║     Brand:           AcmePets                                       May 4    ║
║     Category:        Pet supplies                                            ║
║     Target ACOS:     30%                                                     ║
║     Margin floor:    22%                                                     ║
║     Active SKUs:     12                                                      ║
║                                                                              ║
║  🎯 Strategy (strategy.md)                                          Updated: ║
║     • Don't scale SKUs below 25% margin                             May 6    ║
║     • SKU-X is out of stock — pause all ads (until July)                     ║
║     • Aggressive on SKU-A (new launch, hero product)                         ║
║     • Holiday Q4 plan: increase budget 40% Nov 1-Dec 24                      ║
║                                                                              ║
║  📚 Learnings (learnings/)                                          12 files ║
║     • seasonality.md — Q4 traffic +40%, Q1 -25%                              ║
║     • what_works.md — Long-tail keywords convert 3x better                   ║
║     • what_doesnt.md — Sponsored Brands wasted $500 in March                 ║
║     • category_quirks.md — Pet category higher returns rate                  ║
║                                                                              ║
║  ✅ Decisions (decisions/)                                          47 files ║
║     Most recent:                                                             ║
║     • 2026-05-11 — Paused SKU-X campaign (inventory constraint)              ║
║     • 2026-05-10 — Approved bid +12% on long-tail keywords for SKU-A         ║
║     • 2026-05-09 — Rejected suggestion to launch Sponsored Brands           ║
║       (you said: "let me focus on SP first, decide brands in Q3")            ║
║     [View all 47 →]                                                          ║
║                                                                              ║
║  ───────────────────────────────────────────────────────────────────────     ║
║                                                                              ║
║  🗑️  Want me to forget something? Tell me what.                              ║
║                                                                              ║
║  💾 Export all memory data: [JSON] [Markdown bundle]                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 8. Decision log

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  Decision Log — Every action ever taken on your account              [Filter]║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  May 11, 2026                                                                ║
║  ─────────────                                                               ║
║  ┌──────────────────────────────────────────────────────────────────────┐   ║
║  │ ⏸️  Paused campaign "SKU-X Manual Broad"                              │   ║
║  │    Approved by you at 10:42 AM. Applied to Amazon at 10:42 AM.       │   ║
║  │    Reason: inventory constraint                                       │   ║
║  │    Memory link: decisions/2026-05-11_paused_skux.md                   │   ║
║  │    [Undo (28 days remaining)] [View Amazon log] [Open memory note]    │   ║
║  └──────────────────────────────────────────────────────────────────────┘   ║
║                                                                              ║
║  May 10, 2026                                                                ║
║  ─────────────                                                               ║
║  ┌──────────────────────────────────────────────────────────────────────┐   ║
║  │ 📈 Increased bids +12% on 14 long-tail keywords (SKU-A)              │   ║
║  │    Approved by you at 3:15 PM. Applied to Amazon at 3:15 PM.         │   ║
║  │    Reason: high impression-to-click conversion in last 7 days        │   ║
║  │    7-day result: ACOS went from 38% to 31% ✓                         │   ║
║  │    [Undo (29 days remaining)] [View Amazon log] [Open memory note]    │   ║
║  └──────────────────────────────────────────────────────────────────────┘   ║
║                                                                              ║
║  May 9, 2026                                                                 ║
║  ─────────────                                                               ║
║  ┌──────────────────────────────────────────────────────────────────────┐   ║
║  │ ❌ REJECTED — Launch Sponsored Brands campaign                        │   ║
║  │    You rejected at 11:28 AM.                                          │   ║
║  │    Your reason: "Let me focus on SP first, decide brands in Q3"      │   ║
║  │    I've saved this to memory and won't suggest SB campaigns until    │   ║
║  │    we discuss Q3 plans.                                              │   ║
║  └──────────────────────────────────────────────────────────────────────┘   ║
║                                                                              ║
║  [Load more...]                                                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 9. Settings / billing

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  Settings                                                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Account                                                                     ║
║  ────────                                                                    ║
║  Email:            meir@example.com         [Change]                         ║
║  Password:         ••••••••••               [Change]                         ║
║                                                                              ║
║  Subscription                                                                ║
║  ────────────                                                                ║
║  Plan:             Pilot ($89/mo)           [Upgrade] [Cancel]               ║
║  Next billing:     June 11, 2026                                             ║
║  Payment method:   •••• 4242                [Update]                         ║
║                                                                              ║
║  Amazon Connection                                                           ║
║  ─────────────────                                                           ║
║  Account:          AcmePets (US)                                             ║
║  Status:           ✓ Connected                                               ║
║  Last sync:        2 minutes ago                                             ║
║                                          [Disconnect] [Reconnect]            ║
║                                                                              ║
║  Notifications                                                               ║
║  ─────────────                                                               ║
║  ☑ Weekly summary email (Mondays 9am ET)                                    ║
║  ☑ Important alerts (campaign failures, sudden ACOS spikes)                 ║
║  ☐ Daily digest                                                             ║
║                                                                              ║
║  Data & Memory                                                               ║
║  ─────────────                                                               ║
║  Export all data:  [Download JSON]  [Download Markdown]                      ║
║  Delete account:   [Permanently delete everything →]                         ║
║                                                                              ║
║  ──────────────────────────────────────────────────────────────────────      ║
║                                                                              ║
║  Cancel anytime. No retention calls. Your data exports as you cancel.       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 10. Day-7 check-in email

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  From: SellerCopilot AI <hi@sellercopilot.com>                               ║
║  To: meir@example.com                                                        ║
║  Subject: Your 7-day check-in                                                ║
║                                                                              ║
║  ─────────────────────────────────────────────────────────────────────       ║
║                                                                              ║
║  Hi Meir,                                                                    ║
║                                                                              ║
║  Last Tuesday, I paused "SKU-X Manual Broad" to save you ~$300/month.        ║
║  Quick update on how it's going:                                             ║
║                                                                              ║
║  ✅ Campaign successfully paused 7 days ago                                  ║
║  ✅ 7-day spend on this campaign: $0 (was on track for $80)                 ║
║  ✅ Estimated savings so far: $80                                            ║
║  ✅ No negative impact on your other campaigns                               ║
║                                                                              ║
║  I have 3 new opportunities to discuss whenever you're ready:                ║
║                                                                              ║
║    1. SKU-A long-tail keywords are converting 22% better than average        ║
║       — opportunity to scale                                                 ║
║                                                                              ║
║    2. SKU-Y has a search-term wasting $4.20/day with 0 conversions          ║
║       — opportunity to negative-match                                        ║
║                                                                              ║
║    3. Q2 seasonality starts shifting next week (per your category)          ║
║       — opportunity to adjust budget pace                                    ║
║                                                                              ║
║  ┌──────────────────────────────────────────┐                               ║
║  │  Open SellerCopilot →                    │                               ║
║  └──────────────────────────────────────────┘                               ║
║                                                                              ║
║  Don't want these check-ins? [Email preferences]                             ║
║                                                                              ║
║  ─────────────────────────────────────────────────────────────────────       ║
║  SellerCopilot AI Agent — sent on behalf of your Amazon account              ║
║  Compliant with Amazon BSA Agent Policy (March 2026)                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 🎨 Visual Design Principles

When the real UI gets built (HTML/CSS), preserve these principles:

### Color palette (suggested, extending existing repo theme)
- **Primary blue:** `#1f5fa8` (already in `landing.html`)
- **Accent green:** `#1d6a42` (good for "Approve" buttons)
- **Warning amber:** `#92400e` (for compliance/policy items)
- **Soft cream:** `#fffdfa` (paper background)
- **Subtle line:** `#ddd4c6` (dividers)

### Typography
- **Headlines:** Georgia (serif) — already used in repo
- **Body:** Segoe UI / Arial (sans-serif) — already used in repo
- **Code/data:** Monospace for numbers ($12,340 / 41%)

### Layout principles
1. **Conversation comes first.** The chat is the home screen, not a dashboard with chat tucked in a corner.
2. **Memory should be one click away.** "What does the agent know?" is the wedge — make it visible.
3. **Approval cards inline.** Don't move user to a separate page to approve a suggestion. Approve in flow.
4. **Decisions are first-class.** Every approved action should be a permanent, queryable record.
5. **No dashboards with 47 metrics.** Show 4 numbers max in the header. Everything else is in conversation.

---

## 🔧 Implementation Notes

Use the existing HTML pattern from `app.html` (no build step, static HTML+JS). Streaming agent responses via Server-Sent Events (SSE).

For the chat interface specifically:
- One textarea for input (auto-resize)
- One scrollable conversation area
- Agent messages styled with subtle background
- Suggestion cards as embedded components within agent messages
- "What I'm doing" indicator when agent is thinking (instead of spinner — try: *"Reading your last 7 days of data..."*)

---

*These ASCII sketches are conceptual. Build them in HTML/CSS during build phase week 8-9.*

# Amazon Agent Policy — Compliance Checklist (March 4, 2026)

> **Source:** Amazon Business Solutions Agreement update, effective March 4, 2026
> **Status:** ALREADY IN EFFECT (as of today, 2026-05-11)
> **Risk if violated:** API access revocation, account suspension

---

## ⚠️ Why this matters

Amazon's BSA Agent Policy went live March 4, 2026. **Every PPC tool connected to Seller Central must comply.** No grandfather clause. No opt-out.

> *"Continued use of your Seller Account after March 4, 2026 constitutes acceptance"* — Amazon

For SellerCopilot:
- Building a non-compliant agent → instant API revocation when Amazon checks
- Compliance is **not optional**, it's a launch blocker

The good news: most compliance items are already implemented in the existing repo code. This doc verifies and lists the ones still needed.

---

## ✅ Compliance Items — Status

### 1. Self-Identification

**Requirement:** Every API call must identify itself as an automated agent in the User-Agent header.

**Current status:** ✅ DONE
- See `ppc_ads_client.py:70` — `USER_AGENT = "SellerCopilot/1.0 (AI Agent)"`
- All Ads API calls use this header

**Verification command (when live):**
```bash
# Tail Amazon API logs to confirm User-Agent is correct
grep "User-Agent: SellerCopilot" /var/log/sellercopilot/*.log
```

---

### 2. Hard Rate Caps

**Requirement (per Agent Policy):**
- Max 50 suggestions/customer/week
- Max 20% bid change per 24h
- 30-day rollback window for any change

**Current status:** ✅ Defined as constants in `ppc_agent.py:79-81`:
```python
MAX_SUGGESTIONS_PER_CUSTOMER_PER_WEEK = 50
MAX_BID_CHANGE_PCT_PER_24H            = 20
ROLLBACK_WINDOW_DAYS                  = 30
```

**Still needed:** ❌ Enforcement code (these are constants, not yet enforced).

**Action item for build phase:**
Add enforcement in `apply_suggestion()` when implemented:
```python
def apply_suggestion(suggestion_id, customer_id):
    # Check 50/week cap
    weekly_count = _count_applied_this_week(customer_id)
    if weekly_count >= MAX_SUGGESTIONS_PER_CUSTOMER_PER_WEEK:
        raise ComplianceError("Weekly suggestion cap reached (50)")
    
    # Check 20%/24h bid change cap
    suggestion = _get_suggestion(suggestion_id)
    if suggestion.type == 'bid_change':
        pct_change = abs(suggestion.proposed_bid - suggestion.current_bid) / suggestion.current_bid * 100
        if pct_change > MAX_BID_CHANGE_PCT_PER_24H:
            raise ComplianceError(f"Bid change {pct_change}% exceeds 24h cap (20%)")
    
    # Snapshot before applying (for rollback)
    snapshot_id = _snapshot_state(suggestion_id)
    
    # Apply via Ads API
    result = ppc_ads_client.update_bid(...)
    
    # Log to audit trail
    _audit_log(suggestion_id, 'applied', before=snapshot_id, after=result, by=customer_id)
```

---

### 3. Audit Log (Append-Only)

**Requirement:** Every action taken on behalf of a seller must be logged with timestamp, before/after state, and who initiated.

**Current status:** ✅ Schema exists — `ppc_audit_log` table in `ppc_agent.py:147-158`:
```sql
CREATE TABLE ppc_audit_log (
    id              {serial},
    connection_id   INTEGER NOT NULL,
    suggestion_id   INTEGER,
    action          TEXT NOT NULL,
    before_value    {jsonb},
    after_value     {jsonb},
    api_response    {jsonb},
    performed_at    REAL NOT NULL,
    performed_by    TEXT NOT NULL
)
```

**Still needed:** ❌ Logging code that writes to it on every applied suggestion.

---

### 4. Cease-on-Request

**Requirement:** If Amazon asks the agent to stop accessing the account, it must immediately stop.

**Current status:** 🟡 Partial — connection can be marked `active=0` in `amazon_connections` table, but no automated detection of Amazon's request.

**Still needed:** ❌ 
- Webhook listener for Amazon revocation notifications (if Amazon publishes one)
- Daily check for 401/403 responses → if persistent, auto-deactivate connection
- Manual ops process: if Amazon emails the founder asking to stop, act within 24h

**Action item:**
Add to `ppc_ads_client.py`:
```python
# Track consecutive auth failures per connection
_auth_failures = defaultdict(int)
AUTH_FAILURE_THRESHOLD = 3  # 3 consecutive 401s = deactivate

def _handle_auth_failure(connection_id):
    _auth_failures[connection_id] += 1
    if _auth_failures[connection_id] >= AUTH_FAILURE_THRESHOLD:
        log.warning("Auto-deactivating connection %d after 3 auth failures", connection_id)
        _mark_connection_inactive(connection_id)
        _notify_founder_email(connection_id, "Auto-deactivated due to auth failures")
```

---

### 5. Read-Only Default; Write Requires Explicit Approval

**Requirement:** Agent must NOT auto-apply changes without seller approval. Every write requires explicit human consent.

**Current status:** ✅ Enforced by design
- Agent generates `ppc_suggestions` with `status='pending'`
- Only `apply_suggestion()` writes to Amazon
- That function should only be called from approved seller actions

**Still needed:** ❌ Enforcement that `apply_suggestion()` cannot be called from agent's tool list (only from Flask route after seller clicks "approve").

**Action item:**
- The agent's `propose_suggestion` tool **only logs to DB**, doesn't apply
- Only the Flask route `/ppc/approve/<suggestion_id>` calls `apply_suggestion()`
- This separation is structural, not just convention

---

### 6. No AI Training on Amazon Materials

**Requirement:** "New AI and machine learning restrictions now prohibit the use of Amazon materials or services for AI development without proper authorization."

**Current status:** ✅ Compliant (we don't train models on Amazon data)
- We use Claude Sonnet 4.6 (pre-trained by Anthropic)
- Per-customer memory is local, not used for model training
- Anthropic's terms also prohibit using customer data for training

**Still needed:** ✅ Privacy policy + terms of service that state clearly:
> *"SellerCopilot does not use your Amazon data to train AI models. Your data is used only to provide service to you."*

---

### 7. Data Retention + Deletion

**Requirement:** Amazon data retention should be limited to operational need.

**Current status:** 🟡 Partial
- ASINInsight has retention purge (`server.py:_process_retention_purge`)
- PPC snapshots have no documented retention policy

**Still needed:** ❌ Retention policy for PPC data:
- `ppc_snapshots`: retain 90 days, then archive or delete
- `ppc_audit_log`: retain 7 years (financial compliance)
- `ppc_rollback_snapshots`: 30 days (already implemented via `expires_at`)

**Action item:**
Add to background worker in `server.py`:
```python
def _process_ppc_retention():
    """Delete PPC snapshots older than 90 days."""
    cutoff = time.time() - (90 * 86400)
    with _db() as (cur, ph):
        cur.execute(f"DELETE FROM ppc_snapshots WHERE fetched_at < {ph}", (cutoff,))
```

---

### 8. Disclosure to Customer

**Requirement:** Sellers must understand they're using an AI agent.

**Current status:** ❌ Not yet documented in the product UI

**Action items:**
- Onboarding screen: "You're working with an AI agent. Here's what that means..."
- Every agent response: subtle "AI-generated" badge
- Privacy/Terms page: clear AI disclosure
- Email signature: "Sent by SellerCopilot AI Agent on behalf of [seller name]"

---

## 🚦 Compliance Gates (must pass before launch)

| Gate | Status | Owner |
|---|---|---|
| User-Agent self-ID in API calls | ✅ Done | Code (already implemented) |
| 50/week, 20%/24h, 30d rollback caps **enforced** | ❌ Not yet | Build phase |
| Audit log code (writes on every apply) | ❌ Not yet | Build phase |
| Auto-cease on 3 consecutive auth failures | ❌ Not yet | Build phase |
| Read-only default architecturally separated from write | 🟡 Partial | Build phase |
| Privacy policy with AI disclosure | ❌ Not yet | Pre-launch |
| Terms of service with AI agent terms | ❌ Not yet | Pre-launch |
| Data retention policy implemented | ❌ Not yet | Build phase |
| Onboarding AI disclosure | ❌ Not yet | Build phase |

**Cannot launch until all 9 are ✅.**

---

## 📝 What if Amazon contacts us?

If Amazon emails Meir at any point asking about SellerCopilot's compliance:

1. **Respond within 24 hours.** Amazon's policy gives 5 days but faster is better.
2. **Be transparent.** Provide:
   - Architecture overview (how the agent works)
   - Compliance evidence (audit log samples, rate cap enforcement code)
   - Customer count and average API calls per customer
3. **Offer a demo** if they want to see it work
4. **Don't argue.** If they ask for changes, make them. API access > principle.

**Worst case:** Amazon revokes API access. We have 30 days to wind down. Refund all paying customers.

**Best case:** Amazon approves and we get into the Solution Provider Portal listing.

---

## 📚 References

- [Amazon BSA Updates (March 4, 2026)](https://sellercentral.amazon.com/seller-forums/discussions/t/84e3f6b1-42f7-4cf3-a189-a5cc8d78d838)
- [Amazon Sellers Have 2 Weeks to Ensure Compliance](https://www.ecommercebytes.com/2026/02/18/amazon-sellers-have-2-weeks-to-ensure-compliance-of-tools-they-use/)
- [Amazon Sellers Attorney - BSA Update Guide](http://www.amazonsellers.attorney/blog/amazon-sellers-guide-to-the-march-4-2026-bsa-update-amazon-agent-policy-2026-bsa-section-20-update)
- [PPC.land - Amazon's New AI Agent Rules](https://ppc.land/amazons-new-ai-agent-rules-shake-up-sellers-before-march-4-deadline/)
- [SP-API Solution Provider Portal](https://developer.amazonservices.com/solution-provider-portal)

---

*Compliance is not glamorous. Skip it and you have no business. Get it right and you have a defensible moat.*

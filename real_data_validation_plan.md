# REAL DATA VALIDATION PLAN

For internal use only. Operational protocol for running ASINInsight
(the PPC Agent) against real seller PPC data before any beta outreach.
This document turns Section 6 of
[INTERNAL_MVP_DEMO_CHECKLIST.md](INTERNAL_MVP_DEMO_CHECKLIST.md) from
a one-line gate into a runnable validation pass.

Last updated: 2026-05-06
Required state at run time: Tasks 1 to 4 shipped, 285 tests passing,
no commits to main, no live Amazon writes wired.

A predecessor doc from the pre-pivot era lives at
[REAL_DATA_VALIDATION_PLAN_LEGACY_ASININSIGHT.md](REAL_DATA_VALIDATION_PLAN_LEGACY_ASININSIGHT.md).
That doc covers the older ASINInsight Business Reports tool and is
not authoritative for ASINInsight. Ignore it unless you are
researching the pivot history.

## Scope: what this plan tests, and what it does not

The CSV ingest path (`/ppc/csv`) exists to let a seller try the
PPC Agent without a live OAuth connection. By design, the CSV path is
**neutral on history**: no DB write, no decision history, no memory
pill, no approval baseline. That neutrality is part of the product
(verified by `test_csv_preview_does_not_render_memory_pill` and
`test_csv_preview_does_not_render_projection_block`).

Real-data validation therefore runs in two phases:

- **Phase A (this plan)**: real Sponsored Products Search Term
  Report CSV uploads through `/ppc/csv`. Tests the quality of
  Tasks 1 and 2 (Smart Recommendation Card + 3 to 5 ranked
  decisions) against real spend, real keywords, real search terms.
  This is the only phase we can run today.
- **Phase B (gated on SP-API Production approval)**: live OAuth-
  connected accounts with real ppc_snapshots. Tests Tasks 3 and 4
  (memory pill + approval baseline / projection block) end to end.
  Cannot run until SP-API Production approval lands (4 to 8 weeks
  per Amazon).

Run Phase A now. Run Phase B as soon as SP-API Production approval
lands. Do not wait for Phase B to start validating recommendation
quality.

---

## 1. CSV format the engine expects

The CSV must be a Sponsored Products Search Term Report exported
from Seller Central. Path inside Amazon: **Seller Central > Reports
> Advertising Reports > Sponsored Products > Search Term Report**.

### Required date range

Last 30 days of campaign data. Shorter ranges hide low-volume
keywords; longer ranges dilute the "current spend" signal the rules
key off.

### Recognised columns

The parser uses substring header matching (see `ppc_csv_ingest.py`
`_HEADER_SYNONYMS`), so the canonical column names below match a few
report variants. **At minimum, these canonical fields must be
present**:

| Canonical field | Acceptable header substrings |
|-----------------|------------------------------|
| campaign        | "Campaign Name", "Campaign" |
| ad_group        | "Ad Group Name", "Ad Group", "AdGroup" |
| keyword         | "Targeting", "Keyword Text", "Keyword" |
| match_type      | "Match Type", "MatchType" |
| search_term     | "Customer Search Term", "Search Term" |
| impressions     | "Impressions" |
| clicks          | "Clicks" |
| cost            | "Spend", "Cost" |
| sales           | "7/14/30 Day Total Sales", "Total Sales", "Sales" |
| orders          | "7/14/30 Day Total Orders", "Total Orders", "Orders" |

### File constraints

- UTF-8, comma-delimited.
- Maximum 8 MB (`CSV_MAX_UPLOAD_BYTES`). Reports above this are rare;
  if a seller hits it, ask them to narrow the date range.
- One row per (campaign, ad group, keyword, search term)
  combination. Daily-broken-out exports also work; the engine
  aggregates per keyword internally.
- No PDF, ZIP, XLSX, or image. The engine rejects those at upload
  via magic-byte detection.

### What the engine will silently ignore

- Rows with no `Customer Search Term`.
- Rows with all-zero metrics.
- Headers it doesn't recognise (kept in the file, not read).

### What the engine will reject loudly

- A CSV where no canonical headers match -> 400 with "Expected
  headers like 'Customer Search Term', 'Targeting' or 'Keyword',
  and 'Impressions'."
- Non-CSV file types -> 415 with the detected format name.
- Empty body -> 400.

### Privacy and storage handling

Treat each seller CSV as if it were their bank statement.

- Save under `validation/real_data/<seller_pseudonym>/<YYYY-MM-DD>.csv`
  on disk. **Never commit to git** (this path must live in
  `.gitignore` before any CSV is dropped in).
- Use a pseudonym for the seller (e.g. `seller_a`, `seller_b`),
  recorded once in your private notes, never inside a doc that gets
  shared.
- Redact brand names in any screenshot before it leaves your
  machine.
- If you ever publish results externally (you should not, but if
  you do), strip campaign names and search terms; keep only the
  rule type and dollar impact.

---

## 2. How to run the test

Per CSV. Repeat for 3 to 5 sellers. The whole loop should take 15
to 20 minutes per CSV.

### Step 0: pre-flight

```powershell
cd C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp
git status --short
pytest tests/ -q
```

Required: clean tree (no uncommitted edits to product code), 285
passed. If either fails, fix before validating; otherwise you are
chasing recommendation quality through a moving codebase.

### Step 1: drop the CSV

Save the file to:
`validation/real_data/<seller_pseudonym>/<YYYY-MM-DD>_search_term_report.csv`

Confirm `validation/real_data/` is gitignored before saving.

### Step 2: run the local server

```powershell
$env:FLASK_SECRET_KEY = "validation_local_only_xxxxxxxxxxxx"
$env:PPC_TOKEN_ENCRYPTION_KEY = "<a Fernet key, generate locally>"
python server.py
```

Visit `http://localhost:5000/ppc/csv`. The form should load with the
"Download sample" link visible.

### Step 3: upload and read

1. Click "Choose file", select the seller CSV.
2. Submit. The findings page should render in under 2 seconds for
   any report under 5 MB.
3. Confirm the disclaimer banner is present:
   "Past performance does not guarantee..." (cycle 12 / 13 work).

### Step 4: capture outputs

Per-CSV outputs to save (paths relative to repo root):

- `validation/real_data/<pseudonym>/findings_top.png` -> screenshot
  of the first-view list (the 3 to 5 cards above the fold).
- `validation/real_data/<pseudonym>/findings_card_open.png` ->
  screenshot of one card with the "Learn more" block expanded so
  the formula breakdown is visible.
- `validation/real_data/<pseudonym>/findings_full.html` -> right-
  click "View source" on the findings page and save. The HTML
  contains every card the engine surfaced, including the overflow
  bucket.
- `validation/real_data/<pseudonym>/engine_output.json` ->
  programmatic capture, see Step 5.

### Step 5: programmatic capture (recommended)

The CSV path is convenient for the screenshot pass, but the
canonical output for analysis is the engine's JSON. Run a one-shot
script locally (do not commit it):

```python
# validation/scratch_run.py  (gitignored, do not commit)
import json, sys
from ppc_csv_ingest import parse_search_term_report
from ppc_suggestions import analyze, build_card_views, rank_recommendations

with open(sys.argv[1], "rb") as fh:
    snapshot = parse_search_term_report(fh.read())

suggestions = analyze(snapshot)
cards = build_card_views(suggestions)
ranking = rank_recommendations(cards)

print(json.dumps({
    "raw_count": len(suggestions),
    "card_count": len(cards),
    "top_count": len(ranking["top"]),
    "hidden_count": len(ranking["hidden"]),
    "top": ranking["top"],
    "hidden": ranking["hidden"],
}, default=str, indent=2))
```

Pipe to `engine_output.json` per CSV.

### Step 6: 5-minute seller call (when possible)

If the seller is reachable, schedule a 5-minute call within 7 days
of the upload. Walk them through the top 3 cards. Their voice is
what turns "rule fired" into "non-obvious" judgment (Section 5).

### Step 7: write up the result

Use the template in Section 7. One file per CSV at
`validation/real_data/<pseudonym>/REAL_DATA_VALIDATION_RESULTS.md`.

---

## 3. Metrics to record (per CSV)

Capture all of these even if some are zero; zero is a finding.

### Volume

- `csv_row_count` -> total rows in the report.
- `keywords_recognised` -> distinct (keyword, ad group, match type)
  tuples the parser kept.
- `recognised_columns` -> list of canonical fields the parser
  matched. Anything missing here matters.

### Engine output

- `raw_suggestion_count` -> `analyze()` total.
- `card_count` -> `build_card_views()` total.
- `first_view_count` -> `len(ranking["top"])`. Must be in [0, 5].
- `overflow_count` -> `len(ranking["hidden"])`.
- `count_by_rule` -> per-rule histogram (`spend_no_sales`,
  `high_acos`, `bid_too_high`, `scale_profitable`,
  `promote_search_term`).

### Dollar impact

- `savings_total_usd` -> sum of `estimated_impact` across cost-
  reduction rules (`spend_no_sales`, `high_acos`, `bid_too_high`).
- `growth_total_usd` -> sum across growth rules
  (`scale_profitable`, `promote_search_term`).
- `top_5_impact_usd` -> sum of `estimated_impact` across the first
  view only.
- `max_card_impact_usd` -> single largest card.

### Quality (manual)

- `non_obvious_count` -> cards the seller flagged as non-obvious
  in the 5-minute call (Section 5).
- `zero_impact_card_count` -> cards that rendered with $0 impact
  (must be 0; non-zero is a bug).
- `crashes_or_renders_failed` -> 0 or 1.

### Resemblance to mock data

- `mock_overlap_score` -> qualitative 0 to 5, judged by you. 0
  means the recommendations look completely different from the
  mock-data output; 5 means they look like they could have come
  from the mock seed. **High overlap on real data is a flag**:
  it suggests the engine is over-fitted or that the rule
  thresholds are too generic.

---

## 4. Pass / fail criteria

Two layers: per-CSV gates, and an aggregate gate across the 3 to 5
CSVs.

### Per-CSV (every CSV must pass all of these)

- [ ] CSV uploaded without a 4xx / 5xx.
- [ ] No card rendered with $0 impact.
- [ ] At least one canonical field beyond the minimum was matched
      (sales OR orders present, not just impressions / clicks).
- [ ] Findings page rendered in under 2 seconds.

A CSV that fails any per-CSV gate is excluded from the aggregate
sample. Investigate the failure before running more CSVs.

### Aggregate (across the 3 to 5 CSVs that pass per-CSV)

Anchored to INTERNAL_MVP_DEMO_CHECKLIST.md Section 6. Pass only if
**all three** are true:

- [ ] At least 2 of the 5 (or 2 of 3 if you only sourced 3)
      reports surfaced recommendations the seller calls
      "non-obvious" (Section 5).
- [ ] At least 1 recommendation per report has $50/month or more
      dollar impact.
- [ ] Recommendations on real data are recognisably different
      from recommendations on mock data: average
      `mock_overlap_score` across the sample is <= 2.

If the aggregate gate fails, **do not begin beta outreach**. The
failure mode and fix are usually one of:

- Recommendations are all "lower bid on high ACOS" -> rules
  engine is too narrow; revisit `_rule_high_acos` thresholds.
- Recommendations are obvious -> either thresholds are too lax
  (the rule fires for everyone with a non-zero ACOS) or the
  dollar-impact formula is producing the same number for
  everyone.
- Mock overlap >= 3 on average -> the engine is producing the
  same shape of output regardless of input. Likely a bug in how
  the parser feeds the rules (e.g. dropping a field that the
  rules actually need).

---

## 5. How to judge "non-obvious"

This is the most subjective metric and the most important one. A
recommendation is **obvious** if the seller would have caught it
within their next 7-day Excel review without ASINInsight. A
recommendation is **non-obvious** if they would have missed it
entirely or for 30+ days.

### Litmus tests for non-obvious (any one is sufficient)

- The seller does not recognise the search term as one they were
  watching.
- The dollar number on the card is significantly larger than the
  seller's own estimate when asked to guess before seeing the
  card.
- The keyword is buried under 200+ rows in their report (they
  would have to scroll past most of their data to find it).
- The rule type surprises them ("I would have lowered the bid;
  I wouldn't have thought to negate the search term").
- They say "huh" or "wait, really?" out loud. Track this. It is
  the cleanest signal.

### Litmus tests for obvious (any one disqualifies)

- The seller already had this keyword on a watch list.
- The recommendation matches a rule they apply by hand every
  week (e.g. "I always pause keywords with 50+ clicks and 0
  sales").
- The dollar number matches their guess within 10%.
- The card surfaces a keyword from their top 10 by spend, which
  they review every Monday.

### How to score

For each card in the first view, after walking the seller
through it, ask: "On a scale of 1 to 5, how non-obvious was this?"

| Score | Meaning |
|-------|---------|
| 1 | Obvious. Already on their radar. |
| 2 | They'd have caught it within 7 days in Excel. |
| 3 | They'd have caught it within 30 days. |
| 4 | They'd have probably missed it for a quarter. |
| 5 | They never would have caught it on their own. |

A card is "non-obvious" for our purposes if it scores 3 or
higher. Aggregate `non_obvious_count` is the count of such cards
across the first view of all 3 to 5 sellers.

### When the seller is not reachable

If you cannot get the seller on a call, do the same scoring as
a proxy yourself, **and mark the result as proxy-judged**. Proxy
scores are evidence but should not pass the aggregate gate
alone; at least 1 of the 3 to 5 CSVs must be seller-judged for
the aggregate to pass.

---

## 6. Screenshots and outputs to save

Per CSV, in the seller's pseudonymised folder. None of these are
shared externally without explicit consent and brand-name
redaction.

| Artifact | Path | Why |
|----------|------|-----|
| Raw CSV (gitignored) | `validation/real_data/<p>/source.csv` | Reproduce findings later. |
| Findings page HTML | `validation/real_data/<p>/findings_full.html` | Full set of cards including overflow. |
| Findings screenshot | `validation/real_data/<p>/findings_top.png` | First-view 3 to 5 cards. |
| Card-open screenshot | `validation/real_data/<p>/findings_card_open.png` | Verifies Learn-more formula renders cleanly on real data. |
| Engine JSON | `validation/real_data/<p>/engine_output.json` | Canonical numerical record. |
| Results doc | `validation/real_data/<p>/REAL_DATA_VALIDATION_RESULTS.md` | Per-CSV verdict, see Section 7 template. |
| Seller-call notes | `validation/real_data/<p>/seller_call_notes.md` (optional) | Source of "non-obvious" judgments. |

What **not** to save:
- The seller's name. Use the pseudonym.
- Their Amazon login or refresh token. Never.
- The OAuth flow output. Phase A is CSV only; OAuth is Phase B.

---

## 7. Template for REAL_DATA_VALIDATION_RESULTS.md

Copy this verbatim into each per-CSV results file. Replace `<p>`
with the seller pseudonym and `<YYYY-MM-DD>` with the run date.

```markdown
# REAL DATA VALIDATION RESULTS — <p>

Run date: <YYYY-MM-DD>
Validator: <founder name or pseudonym>
Phase: A (CSV ingest, no live OAuth)

## Source

- Seller pseudonym: <p>
- Source: Sponsored Products Search Term Report
- Report date range: <YYYY-MM-DD> to <YYYY-MM-DD>
- File path (local, gitignored): validation/real_data/<p>/source.csv
- Seller-call held: yes / no / proxy-judged
- Seller-call date: <YYYY-MM-DD or n/a>

## Volume metrics

- csv_row_count: <int>
- keywords_recognised: <int>
- recognised_columns: <comma list>
- missing_canonical_columns: <comma list, or "none">

## Engine output metrics

- raw_suggestion_count: <int>
- card_count: <int>
- first_view_count: <int 0..5>
- overflow_count: <int>
- count_by_rule:
  - spend_no_sales: <int>
  - high_acos: <int>
  - bid_too_high: <int>
  - scale_profitable: <int>
  - promote_search_term: <int>

## Dollar impact metrics

- savings_total_usd: <$X.XX>
- growth_total_usd: <$X.XX>
- top_5_impact_usd: <$X.XX>
- max_card_impact_usd: <$X.XX>

## Quality metrics

- non_obvious_count (score >= 3): <int> of <first_view_count>
- zero_impact_card_count: <int, must be 0>
- crashes_or_renders_failed: <0 or 1>
- mock_overlap_score (0..5): <int>

## Per-card non-obvious scoring (first view only)

| # | Rule type | Keyword / search term | Impact ($/mo) | Seller score (1-5) | Note |
|---|-----------|------------------------|---------------|---------------------|------|
| 1 | <rule>    | <redacted if external> | <$X.XX>       | <int>               | <one line> |
| 2 | <rule>    | <redacted if external> | <$X.XX>       | <int>               | <one line> |
| 3 | <rule>    | <redacted if external> | <$X.XX>       | <int>               | <one line> |
| 4 | <rule>    | <redacted if external> | <$X.XX>       | <int>               | <one line> |
| 5 | <rule>    | <redacted if external> | <$X.XX>       | <int>               | <one line> |

## Per-CSV gate

- [ ] CSV uploaded without 4xx / 5xx
- [ ] No card with $0 impact
- [ ] sales or orders column matched (not just impressions / clicks)
- [ ] Findings page rendered in under 2 seconds

Per-CSV verdict: PASS / FAIL

## Artifacts saved

- validation/real_data/<p>/source.csv (gitignored)
- validation/real_data/<p>/findings_top.png
- validation/real_data/<p>/findings_card_open.png
- validation/real_data/<p>/findings_full.html
- validation/real_data/<p>/engine_output.json
- validation/real_data/<p>/seller_call_notes.md (optional)

## Notes / surprises

<free text. anything that surprised you about the rules engine,
the parser, or the seller's reaction. one to three short
paragraphs.>

## Follow-up actions for ASINInsight itself

<bullet list of code, copy, or rule changes this CSV revealed.
empty list is fine if nothing surfaced.>
```

---

## 8. Aggregate verdict (across 3 to 5 CSVs)

After all per-CSV results files are written, write one
`validation/real_data/AGGREGATE_VERDICT.md` summarising:

- Total CSVs run: <int>
- Total CSVs that passed per-CSV gate: <int>
- Aggregate non_obvious_count >= 2 of N: yes / no
- All passing CSVs had at least one card >= $50/mo: yes / no
- Average mock_overlap_score across sample: <float, must be <= 2>

**Aggregate verdict: PASS / FAIL**

If FAIL, do not begin beta outreach. Capture the failure mode in
a short note, take the corrective action (rule fix, threshold
tuning, parser fix), and rerun the validation pass on a fresh
CSV sample before reconsidering.

If PASS, the next step is INTERNAL_MVP_DEMO_CHECKLIST.md
Section 9 (beta outreach with the free or $49 path).

---

## Hard stops (this plan does not modify any of these)

- No product code changes
- No tests run beyond pre-flight
- No payments wiring
- No pricing page edits
- No deploys
- No live Amazon writes
- No outreach until aggregate verdict is PASS
- No commits of CSV / screenshot / engine_output artifacts to git

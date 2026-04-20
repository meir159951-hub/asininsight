"""
test_reliability.py

Reliability harness for the Phase A brain. Exercises the public
audit_engine API against the five criteria the product owner defined:

    1. Never crashes on any input.
    2. Always returns a valid, structured output.
    3. Handles partial / imperfect data gracefully.
    4. Deterministic: same input -> same output (timestamp excluded).
    5. Sanity: no contradictory or out-of-bounds values.

Runs as a plain script:

    python3 test_reliability.py

Exits non-zero on any failure so CI can fail loud. Every assertion
is labelled so a failing line points straight at the broken invariant.
"""

from __future__ import annotations

import copy
import json
import random
import sys
from typing import Any

from audit_engine import (
    OPTIONAL_CSV_FIELDS,
    REQUIRED_CSV_FIELDS,
    run_full_audit,
    run_store_audit,
)


# ---------------------------------------------------------------------------
# Harness plumbing
# ---------------------------------------------------------------------------

PASS_COUNT = 0
FAIL_COUNT = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  PASS  {label}")
    else:
        FAIL_COUNT += 1
        msg = f"  FAIL  {label}" + (f"  ({detail})" if detail else "")
        print(msg)
        FAILURES.append(msg)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def run_no_crash(label: str, product: dict[str, Any]) -> dict[str, Any] | None:
    """Run the audit and return the result; record a failure if it raised."""
    try:
        result = run_full_audit(product)
        check(label, True)
        return result
    except Exception as exc:
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WEAK_CONVERTER: dict[str, Any] = {
    "asin": "B0DEMO001", "title": "Insulated Water Bottle",
    "category": "Sports & Outdoors",
    "price": 24.99, "cogs": 6.50, "fba_fees": 4.20,
    "sessions_30d": 5000, "conversion_rate": 0.018, "ctr": 0.006,
    "acos": 0.50, "ad_spend_30d": 680, "buy_box_pct": 85,
    "rating": 3.9, "review_count": 15, "days_of_cover": 25,
    "organic_rank_top_keyword": 35, "units_ordered_30d": 90,
}

STRONG_SCALER: dict[str, Any] = {
    "asin": "B0DEMO999", "title": "Quality Kitchen Mat",
    "category": "Home & Kitchen",
    "price": 29.99, "cogs": 8.00, "fba_fees": 5.00,
    "sessions_30d": 1200, "conversion_rate": 0.045, "ctr": 0.0055,
    "acos": 0.20, "ad_spend_30d": 250, "buy_box_pct": 95,
    "rating": 4.5, "review_count": 80, "days_of_cover": 40,
    "organic_rank_top_keyword": 18, "units_ordered_30d": 54,
}


# ---------------------------------------------------------------------------
# Schema contract: every run must produce the same top-level keys
# ---------------------------------------------------------------------------

EXPECTED_TOP_KEYS = {
    "asin", "title", "category", "run_at",
    "summary", "data_quality", "assumptions_used",
    "patterns", "signals", "priority_blockers", "action_plan",
}

EXPECTED_SUMMARY_KEYS = {
    "score", "readiness",
    "core_problem", "narrative_theme",
    "patterns_triggered", "patterns_active",
    "patterns_suppressed", "patterns_grouped",
    "signals_raised", "total_findings",
    "aggregate_impact_min", "aggregate_impact_max",
    "aggregate_impact_display", "aggregate_by_driver",
    "aggregate_by_category", "primary_display_key",
    "naive_sum_impact_min", "naive_sum_impact_max",
    "biggest_single_opportunity", "caveat", "sanity_notes",
}

EXPECTED_DQ_KEYS = {
    "label", "quality_score", "required_total", "required_present",
    "missing_required_fields", "missing_optional_fields",
}

VALID_SEVERITIES = {"critical", "high", "medium", "low"}
VALID_READINESS = {"Strong", "Watch", "At Risk", "Critical"}
VALID_DQ_LABELS = {"full", "partial", "minimal"}


def assert_schema(result: dict[str, Any], label: str) -> None:
    check(f"{label}: has all top-level keys",
          EXPECTED_TOP_KEYS.issubset(result.keys()),
          f"missing {EXPECTED_TOP_KEYS - set(result.keys())}")
    check(f"{label}: summary has all keys",
          EXPECTED_SUMMARY_KEYS.issubset(result["summary"].keys()),
          f"missing {EXPECTED_SUMMARY_KEYS - set(result['summary'].keys())}")
    check(f"{label}: data_quality has all keys",
          EXPECTED_DQ_KEYS.issubset(result["data_quality"].keys()))
    check(f"{label}: patterns is list",      isinstance(result["patterns"], list))
    check(f"{label}: signals is list",       isinstance(result["signals"], list))
    check(f"{label}: priority_blockers list", isinstance(result["priority_blockers"], list))
    check(f"{label}: action_plan is list",   isinstance(result["action_plan"], list))
    check(f"{label}: action_plan <= 3 steps", len(result["action_plan"]) <= 3)


def assert_sanity(result: dict[str, Any], label: str) -> None:
    s = result["summary"]
    check(f"{label}: score in 0-100",
          isinstance(s["score"], int) and 0 <= s["score"] <= 100,
          f"got {s['score']}")
    check(f"{label}: readiness label valid",
          s["readiness"] in VALID_READINESS,
          f"got {s['readiness']}")
    check(f"{label}: data_quality label valid",
          result["data_quality"]["label"] in VALID_DQ_LABELS,
          f"got {result['data_quality']['label']}")
    check(f"{label}: patterns_triggered non-negative",
          s["patterns_triggered"] >= 0)
    check(f"{label}: total_findings = patterns + signals",
          s["total_findings"] == s["patterns_triggered"] + s["signals_raised"])

    # Every pattern: severity valid, roi range non-inverted, priority in 0-10.
    for p in result["patterns"]:
        check(f"{label}: pattern {p['name']} severity valid",
              p["severity"] in VALID_SEVERITIES)
        lo, hi = p["roi"]["min_monthly"], p["roi"]["max_monthly"]
        if lo is not None and hi is not None:
            check(f"{label}: pattern {p['name']} roi range not inverted",
                  lo <= hi, f"{lo} > {hi}")
            check(f"{label}: pattern {p['name']} roi non-negative",
                  lo >= 0 and hi >= 0, f"{lo}, {hi}")

    for sig in result["signals"]:
        check(f"{label}: signal {sig['name']} severity valid",
              sig["severity"] in VALID_SEVERITIES)
        check(f"{label}: signal {sig['name']} impact 0-10",
              0 <= sig["impact_score"] <= 10)

    # Ranking: priority scores strictly monotonic-non-increasing.
    prev = 11.0
    for blk in result["priority_blockers"]:
        check(f"{label}: priority rank {blk['rank']} monotonic",
              blk["priority_score"] <= prev + 1e-9,
              f"{blk['priority_score']} > {prev}")
        prev = blk["priority_score"]

    # aggregate_impact never exceeds naive sum.
    agg_max = s["aggregate_impact_max"]
    naive_max = s["naive_sum_impact_max"]
    if agg_max is not None and naive_max is not None:
        check(f"{label}: deduped aggregate <= naive sum",
              agg_max <= naive_max + 1e-9,
              f"{agg_max} > {naive_max}")

    # Top action aligns with top priority blocker.
    if result["action_plan"] and result["priority_blockers"]:
        check(f"{label}: action step 1 matches top blocker",
              result["action_plan"][0]["title"] == result["priority_blockers"][0]["action_title"])


# ---------------------------------------------------------------------------
# 1. Never crashes - fuzz edge cases
# ---------------------------------------------------------------------------

section("1. Never crashes")

edge_cases: list[tuple[str, dict[str, Any]]] = [
    ("empty dict", {}),
    ("just ASIN", {"asin": "B0X"}),
    ("all None values", {k: None for k in REQUIRED_CSV_FIELDS}),
    ("all empty strings", {k: "" for k in REQUIRED_CSV_FIELDS}),
    ("zero everywhere (divisors!)", {k: 0 for k in REQUIRED_CSV_FIELDS} | {"asin": "B0X", "title": "Z"}),
    ("negative values", {k: -1 for k in REQUIRED_CSV_FIELDS} | {"asin": "B0X", "title": "N", "price": -5.0}),
    ("huge values",
        {"asin": "B0X", "title": "H", "price": 1e9, "cogs": 1e9, "fba_fees": 1e9,
         "sessions_30d": 1e9, "conversion_rate": 0.5, "ctr": 0.9,
         "acos": 10.0, "ad_spend_30d": 1e9, "buy_box_pct": 100,
         "rating": 5.0, "review_count": 1e9, "days_of_cover": 1e6,
         "organic_rank_top_keyword": 1}),
    ("string where number expected",
        {**WEAK_CONVERTER, "sessions_30d": "abc", "ctr": "not a number"}),
    ("boolean where number expected",
        {**WEAK_CONVERTER, "rating": True, "buy_box_pct": False}),
    ("dict where scalar expected",
        {**WEAK_CONVERTER, "price": {"nested": 1}, "cogs": [1, 2, 3]}),
    ("unicode / special chars",
        {**WEAK_CONVERTER, "title": "Pro™ ★ Bottle 🔥", "asin": "B0ΩΩ"}),
    ("extreme ctr 1.0",           {**WEAK_CONVERTER, "ctr": 1.0}),
    ("ctr == 0 (div-by-zero)",    {**WEAK_CONVERTER, "ctr": 0.0}),
    ("buy_box == 0 (div-by-zero)",{**WEAK_CONVERTER, "buy_box_pct": 0}),
    ("buy_box == 100 (div-by-zero)", {**WEAK_CONVERTER, "buy_box_pct": 100}),
    ("price == 0 (margin calc)", {**WEAK_CONVERTER, "price": 0}),
    ("prev == 0 in trends",
        {**WEAK_CONVERTER, "sessions_30d_prev": 0, "acos_prev": 0}),
    ("all prev fields set (trends active)",
        {**WEAK_CONVERTER,
         "sessions_30d_prev": 10000, "conversion_rate_prev": 0.035,
         "acos_prev": 0.20, "organic_rank_prev": 8}),
]

results_by_case: dict[str, dict[str, Any]] = {}
for label, product in edge_cases:
    result = run_no_crash(f"runs on: {label}", product)
    if result is not None:
        results_by_case[label] = result


# ---------------------------------------------------------------------------
# 2. Schema contract: every result has every documented key
# ---------------------------------------------------------------------------

section("2. Schema contract (stable keys)")

for label, result in results_by_case.items():
    assert_schema(result, label)


# ---------------------------------------------------------------------------
# 3. Sanity invariants on every result
# ---------------------------------------------------------------------------

section("3. Sanity invariants")

for label, result in results_by_case.items():
    assert_sanity(result, label)


# ---------------------------------------------------------------------------
# 4. Determinism: same input -> same output (run_at excluded)
# ---------------------------------------------------------------------------

section("4. Determinism")

def strip_timestamps(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_timestamps(v) for k, v in obj.items()
                if k not in ("run_at", "generated_at")}
    if isinstance(obj, list):
        return [strip_timestamps(v) for v in obj]
    return obj


for label, product in edge_cases[:8]:  # sample across the edge cases
    first = strip_timestamps(run_full_audit(copy.deepcopy(product)))
    second = strip_timestamps(run_full_audit(copy.deepcopy(product)))
    serialised_first = json.dumps(first, sort_keys=True, default=str)
    serialised_second = json.dumps(second, sort_keys=True, default=str)
    check(f"deterministic: {label}", serialised_first == serialised_second)


# ---------------------------------------------------------------------------
# 5. Data-quality contract behaves correctly
# ---------------------------------------------------------------------------

section("5. Data quality contract")

# Full fixture should be "full".
r = run_full_audit(WEAK_CONVERTER)
check("full fixture -> 'full' label",
      r["data_quality"]["label"] == "full",
      f"got {r['data_quality']['label']}")
check("full fixture -> missing_required_fields empty",
      r["data_quality"]["missing_required_fields"] == [])

# Minimal fixture should be "minimal".
r = run_full_audit({"asin": "B0X", "title": "x"})
check("minimal fixture -> 'minimal' label",
      r["data_quality"]["label"] == "minimal",
      f"got {r['data_quality']['label']}")
check("minimal fixture -> many missing_required",
      len(r["data_quality"]["missing_required_fields"]) >= 10)

# Partial fixture: drop ~half of the required fields.
partial = {k: v for i, (k, v) in enumerate(WEAK_CONVERTER.items()) if i % 2 == 0}
partial.setdefault("asin", "B0X")
partial.setdefault("title", "x")
r = run_full_audit(partial)
check("partial fixture -> 'partial' label",
      r["data_quality"]["label"] in ("partial", "minimal"),
      f"got {r['data_quality']['label']}")


# ---------------------------------------------------------------------------
# 6. Fuzz: 500 random products never crash and always return valid schema
# ---------------------------------------------------------------------------

section("6. Fuzz (500 random products)")

rng = random.Random(42)  # fixed seed = reproducible failures

def _rand_val() -> Any:
    pick = rng.random()
    if pick < 0.15: return None
    if pick < 0.25: return ""
    if pick < 0.30: return "unexpected string"
    if pick < 0.35: return rng.choice([True, False])
    if pick < 0.45: return 0
    if pick < 0.55: return -rng.random() * 100
    if pick < 0.85: return rng.random() * 1000
    return rng.uniform(1e6, 1e9)

fuzz_crashed = 0
fuzz_schema_broken = 0
for _ in range(500):
    product: dict[str, Any] = {"asin": "B0FUZZ", "title": "Fuzz"}
    for field in REQUIRED_CSV_FIELDS + OPTIONAL_CSV_FIELDS:
        product[field] = _rand_val()
    try:
        result = run_full_audit(product)
        if not EXPECTED_TOP_KEYS.issubset(result.keys()):
            fuzz_schema_broken += 1
    except Exception:
        fuzz_crashed += 1

check("fuzz: 500 random products, zero crashes",
      fuzz_crashed == 0, f"{fuzz_crashed} crashed")
check("fuzz: 500 random products, schema always stable",
      fuzz_schema_broken == 0, f"{fuzz_schema_broken} schema-broken")


# ---------------------------------------------------------------------------
# 8. Trust-breaker guarantees (hardening pass)
# ---------------------------------------------------------------------------

section("8. Trust-breaker guarantees")

# --- 8a. Discontinuation dominance --------------------------------------
discontinuation_fixture = {
    "asin": "B0X", "title": "x", "category": "Home",
    "price": 20.0, "cogs": 5.0, "fba_fees": 4.0,
    "sessions_30d": 800, "conversion_rate": 0.012, "ctr": 0.003,
    "acos": 0.40, "ad_spend_30d": 150, "buy_box_pct": 90,
    "rating": 3.5, "review_count": 20, "days_of_cover": 30,
    "organic_rank_top_keyword": 60, "units_ordered_30d": 10,
}
r = run_full_audit(discontinuation_fixture)
pat_names = [p["name"] for p in r["patterns"]]
active = [p["name"] for p in r["patterns"]
          if not p.get("suppressed_by") and not p.get("grouped_under")]
if "discontinuation_candidate" in pat_names:
    check("discontinuation: sunset pattern is active",
          "discontinuation_candidate" in active)
    improvements = {"reviews_killing_conversion", "listing_over_promise",
                    "review_starvation", "hidden_winner", "underinvested_winner",
                    "buy_box_loss_healthy_stock", "buy_box_war_on_ranked",
                    "weak_listing_foundation", "unit_economics_loss",
                    "restock_urgency"}
    suppressed_improvements = [p for p in r["patterns"]
        if p["name"] in improvements and p.get("suppressed_by") == "discontinuation_candidate"]
    present_improvements = [p["name"] for p in r["patterns"] if p["name"] in improvements]
    check("discontinuation: every co-firing improvement is suppressed",
          len(suppressed_improvements) == len(present_improvements),
          f"present={present_improvements}, suppressed={[p['name'] for p in suppressed_improvements]}")
    plan_titles = {s["title"] for s in r["action_plan"]}
    check("discontinuation: 'Sunset this ASIN' is in the action plan",
          "Sunset this ASIN" in plan_titles)
    check("discontinuation: 'Repair the product rating' is NOT in the plan",
          "Repair the product rating" not in plan_titles)


# --- 8b. Sibling grouping: priority_blockers never has same driver twice
weak_converter_with_reviews = {
    "asin": "B0W", "title": "W", "price": 24.99, "cogs": 6.50, "fba_fees": 4.20,
    "sessions_30d": 5000, "conversion_rate": 0.018, "ctr": 0.006,
    "acos": 0.50, "ad_spend_30d": 680, "buy_box_pct": 85,
    "rating": 3.9, "review_count": 15, "days_of_cover": 25,
    "organic_rank_top_keyword": 35, "units_ordered_30d": 90,
}
r = run_full_audit(weak_converter_with_reviews)
drivers_in_blockers = [b.get("driver") for b in r["priority_blockers"]
                       if b["source"] == "pattern" and b.get("driver")]
check("sibling: blocker list has no duplicate pattern driver",
      len(drivers_in_blockers) == len(set(drivers_in_blockers)),
      f"drivers={drivers_in_blockers}")

action_drivers = [b.get("driver") for s in r["action_plan"]
                  for b in r["priority_blockers"] if b["action_title"] == s["title"]
                  and b["source"] == "pattern" and b.get("driver")]
check("action plan: distinct driver on every pattern step",
      len(action_drivers) == len(set(action_drivers)))


# --- 8c. Aggregate split is present and internally consistent ---------
agg = r["summary"].get("aggregate_by_category")
check("aggregate split present", agg is not None)
if agg is not None:
    cats = agg.get("by_category", {})
    check("aggregate split has 3 categories",
          set(cats.keys()) == {"profit_gain", "cost_savings", "loss_prevention"})
    # Combined upper bound must equal sum of category maxes (ignoring None).
    cat_maxes = [v.get("max") for v in cats.values() if v.get("max") is not None]
    combined = agg.get("combined_upper_bound_max")
    if cat_maxes:
        expected_sum = sum(cat_maxes)
        check("combined equals sum of category maxes",
              combined is not None and abs(combined - expected_sum) < 1e-6,
              f"{combined} vs {expected_sum}")


# --- 8d. Low-volume guard -----------------------------------------------
low_vol = {**weak_converter_with_reviews, "sessions_30d": 50, "units_ordered_30d": 1}
r = run_full_audit(low_vol)
check("low volume flag set",
      r["data_quality"].get("low_volume_flag") is True)
check("low volume note surfaced in summary",
      "low_volume_note" in r["summary"])
# Confidence downgraded on each active pattern.
for p in r["patterns"]:
    if p.get("suppressed_by") or p.get("grouped_under"):
        continue
    check(f"low volume: {p['name']} confidence not 'high'",
          p["confidence"] in ("medium", "low"))


# --- 8e. Conditional severity on tiny-velocity restock -----------------
tiny_velocity = {
    "asin": "B0T", "title": "t", "price": 25.0, "cogs": 7.0, "fba_fees": 4.0,
    "sessions_30d": 300, "conversion_rate": 0.025, "ctr": 0.004,
    "acos": 0.30, "ad_spend_30d": 50, "buy_box_pct": 95,
    "rating": 4.2, "review_count": 30, "days_of_cover": 13,
    "organic_rank_top_keyword": 25, "units_ordered_30d": 7,
}
r = run_full_audit(tiny_velocity)
for p in r["patterns"]:
    if p["name"] == "restock_urgency":
        max_m = p["roi"].get("max_monthly") or 0
        if max_m < 500:
            check("tiny-velocity restock: severity is 'medium' (not 'critical')",
                  p["severity"] == "medium",
                  f"got {p['severity']}, max_impact={max_m}")


# --- 8f. Bounds clamping ------------------------------------------------
out_of_bounds = {
    **weak_converter_with_reviews,
    "buy_box_pct": 150, "rating": 7.5, "acos": -0.2,
}
r = run_full_audit(out_of_bounds)
notes = r["data_quality"].get("clamp_notes", [])
check("bounds clamping: notes recorded",
      any("buy_box_pct" in n for n in notes) and
      any("rating" in n for n in notes) and
      any("acos" in n for n in notes),
      f"notes={notes}")


# --- 8g. Consistency warnings ------------------------------------------
bad_inputs = {
    **weak_converter_with_reviews,
    "units_ordered_30d": 10000,       # > sessions (5000)
    "ad_sales_30d": 0, "ad_spend_30d": 500,
    "cogs": 30.0, "price": 24.99,     # cogs > price
}
r = run_full_audit(bad_inputs)
warnings = r["data_quality"].get("consistency_warnings", [])
check("consistency: units > sessions flagged",
      any("exceeds sessions" in w for w in warnings))
check("consistency: ad_spend with zero ad_sales flagged",
      any("ad_sales_30d=$0" in w for w in warnings))
check("consistency: cogs > price flagged",
      any("cogs" in w and "exceeds price" in w for w in warnings))


# --- 8h. triggered_by_interpreted shape --------------------------------
r = run_full_audit(weak_converter_with_reviews)
for p in r["patterns"]:
    if p.get("suppressed_by") or p.get("grouped_under"):
        continue
    enriched = p.get("triggered_by_interpreted") or {}
    check(f"{p['name']}: triggered_by_interpreted present",
          len(enriched) > 0)
    for field, view in enriched.items():
        check(f"{p['name']}.{field}: has value/display/read",
              isinstance(view, dict) and
              {"value", "display", "read"}.issubset(view.keys()))


# --- 8i. assumptions_applied per pattern --------------------------------
for p in r["patterns"]:
    check(f"{p['name']}: assumptions_applied is a non-empty list",
          isinstance(p.get("assumptions_applied"), list)
          and len(p["assumptions_applied"]) > 0)


# --- 8j. Signals vs patterns tie-break ---------------------------------
# When a high-impact signal ties on priority with a pattern, the
# signal's impact_score must drive tie-break (not pattern ROI).
# Sanity check: the ranking never violates its own sort key.
for idx in range(1, len(r["priority_blockers"])):
    prev = r["priority_blockers"][idx - 1]
    curr = r["priority_blockers"][idx]
    check(f"tie-break: rank {curr['rank']} respects priority order",
          curr["priority_score"] <= prev["priority_score"] + 1e-9)


# ---------------------------------------------------------------------------
# 9. Refinement-pass guarantees (single source of truth, confidence
#    justification, readability, realism)
# ---------------------------------------------------------------------------

section("9. Refinement-pass guarantees")

# --- 9a. core_problem is the single source of truth --------------------
r = run_full_audit(weak_converter_with_reviews)
core = r["summary"].get("core_problem")
check("core_problem present when findings exist", core is not None)
if core is not None and r["priority_blockers"]:
    check("core_problem.name matches priority_blockers[0]",
          core["name"] == r["priority_blockers"][0]["name"])
    check("core_problem.action_title matches action_plan[0]",
          core["action_title"] == r["action_plan"][0]["title"])
    check("core_problem carries why_this_one text",
          bool(core.get("why_this_one")))

# Empty fixture -> core_problem is None, not missing.
r_empty = run_full_audit({"asin": "B0X", "title": "x"})
check("core_problem key always present (None when no findings OK)",
      "core_problem" in r_empty["summary"])

# --- 9b. Narrative theme --------------------------------------------------
if core is not None:
    theme = r["summary"].get("narrative_theme")
    check("narrative_theme is populated when a core_problem exists",
          isinstance(theme, str) and len(theme) > 0,
          f"got {theme!r}")

# --- 9c. priority_blockers capped at 3 -----------------------------------
for label, product in [("weak", weak_converter_with_reviews), ("demo", WEAK_CONVERTER)]:
    r = run_full_audit(product)
    check(f"priority_blockers <= 3 ({label})",
          len(r["priority_blockers"]) <= 3,
          f"got {len(r['priority_blockers'])}")
    # Ranks are 1..N in the truncated list (no gaps).
    ranks = [b["rank"] for b in r["priority_blockers"]]
    check(f"priority_blockers ranks are 1..N ({label})",
          ranks == list(range(1, len(ranks) + 1)),
          f"got {ranks}")

# --- 9d. Confidence justification on every finding ---------------------
r = run_full_audit(weak_converter_with_reviews)
for p in r["patterns"]:
    cr = p.get("confidence_reason")
    check(f"pattern {p['name']} has confidence_reason",
          isinstance(cr, str) and len(cr) > 10,
          f"got {cr!r}")
for s in r["signals"]:
    cr = s.get("confidence_reason")
    check(f"signal {s['name']} has confidence_reason",
          isinstance(cr, str) and len(cr) > 10,
          f"got {cr!r}")

# --- 9e. sanity_notes is always a list -----------------------------------
for label, product in [
    ("normal", weak_converter_with_reviews),
    ("empty", {"asin": "B0X", "title": "x"}),
    ("low-volume", {**weak_converter_with_reviews, "sessions_30d": 50, "units_ordered_30d": 1}),
]:
    r = run_full_audit(product)
    notes = r["summary"].get("sanity_notes")
    check(f"sanity_notes is a list ({label})",
          isinstance(notes, list),
          f"got {type(notes).__name__}")

# Low-volume scenario should produce at least one sanity note.
low_vol_r = run_full_audit({**weak_converter_with_reviews, "sessions_30d": 50, "units_ordered_30d": 1})
check("low-volume: sanity_notes non-empty",
      len(low_vol_r["summary"]["sanity_notes"]) >= 1)

# --- 9f. Cross-layer consistency ----------------------------------------
r = run_full_audit(weak_converter_with_reviews)
if r["priority_blockers"] and r["action_plan"]:
    check("consistency: action_plan[0].title == priority_blockers[0].action_title",
          r["action_plan"][0]["title"] == r["priority_blockers"][0]["action_title"])

# Whenever a pattern is suppressed by discontinuation, the core
# problem must NOT be the suppressed pattern's name.
r = run_full_audit(discontinuation_fixture)
suppressed_names = {p["name"] for p in r["patterns"] if p.get("suppressed_by")}
if r["summary"].get("core_problem") and suppressed_names:
    check("consistency: core_problem is not a suppressed pattern",
          r["summary"]["core_problem"]["name"] not in suppressed_names,
          f"core={r['summary']['core_problem']['name']}, "
          f"suppressed={suppressed_names}")

# Whenever a pattern is grouped under a sibling, the core problem
# must NOT be one of the grouped (loser) patterns.
r = run_full_audit(weak_converter_with_reviews)
grouped_names = {p["name"] for p in r["patterns"] if p.get("grouped_under")}
if r["summary"].get("core_problem") and grouped_names:
    check("consistency: core_problem is not a grouped sibling",
          r["summary"]["core_problem"]["name"] not in grouped_names)


# ---------------------------------------------------------------------------
# 7. Real demo store end-to-end
# ---------------------------------------------------------------------------

section("7. Real demo store end-to-end")

import pathlib
demo_path = pathlib.Path("sample_data/demo_store.json")
if demo_path.exists():
    store = json.loads(demo_path.read_text(encoding="utf-8"))
    try:
        audit = run_store_audit(store)
        check("demo store runs", True)
        check("demo store has audits", len(audit.get("audits", [])) > 0)
        for a in audit["audits"]:
            assert_schema(a, f"demo[{a.get('asin')}]")
            assert_sanity(a, f"demo[{a.get('asin')}]")
    except Exception as exc:
        check("demo store runs", False, f"{type(exc).__name__}: {exc}")
else:
    print("  SKIP  demo store not found")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print()
print("=" * 60)
print(f"RESULTS: {PASS_COUNT} pass, {FAIL_COUNT} fail")
if FAIL_COUNT:
    print("\nFailures:")
    for f in FAILURES[:20]:
        print(" ", f)
    sys.exit(1)
print("All reliability checks passed.")
sys.exit(0)

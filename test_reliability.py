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
    "patterns_triggered", "signals_raised", "total_findings",
    "aggregate_impact_min", "aggregate_impact_max",
    "aggregate_impact_display", "aggregate_by_driver",
    "naive_sum_impact_min", "naive_sum_impact_max",
    "biggest_single_opportunity", "caveat",
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

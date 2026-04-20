# ASIN CSV Template - Field Reference

This file documents the exact columns, types, and formats that
`audit_engine.run_full_audit` expects. Uploading a CSV that follows
this spec produces the most complete audit; any missing column causes
the affected patterns or signals to downgrade rather than raise, and
`data_quality.label` in the output drops accordingly.

## Format rules (read these first)

- **Rates** (`conversion_rate`, `ctr`, `acos`) are **decimal fractions
  between 0 and 1**, NOT percentages.
  - 2.19% conversion rate -> write `0.0219`
  - 35% ACoS -> write `0.35`
  - 0.31% CTR -> write `0.0031`
- **`buy_box_pct`** is the one exception: write it as a whole number
  between 0 and 100.
  - 85% Buy Box share -> write `85`
- **Money fields** (`price`, `cogs`, `fba_fees`, `ad_spend_30d`,
  `ad_sales_30d`) are plain dollars, no currency symbol, no thousands
  separator. `24.99` is fine; `$24.99` or `1,200.50` is not.
- **Booleans** (`has_a_plus`) are `true` / `false` (lowercase).
- **Delimiter**: comma `,` by default; semicolon `;` is also accepted.
- **ASIN** column accepts either `asin` or `ASIN` as the header.

## Required fields (15)

These must be present for a full audit. A row missing any of them is
still evaluated, but `data_quality.missing_required_fields` will list
them in the output.

| Column | Type | Format | Example | Meaning |
|---|---|---|---|---|
| `asin` | text | 10-char ASIN | `B07XYZ1234` | Primary key. |
| `title` | text | up to 200 chars | `Insulated Water Bottle` | Listing title. |
| `sessions_30d` | integer | whole number | `5200` | Unique sessions in last 30 days. |
| `conversion_rate` | decimal | 0.0 - 1.0 fraction | `0.0219` | Order conversion rate (not percent). |
| `ctr` | decimal | 0.0 - 1.0 fraction | `0.0031` | Click-through rate (not percent). |
| `price` | decimal | USD | `24.99` | Current selling price per unit. |
| `cogs` | decimal | USD | `6.50` | Cost of goods sold per unit. |
| `fba_fees` | decimal | USD | `4.20` | FBA fulfilment fee per unit. |
| `buy_box_pct` | integer | 0 - 100 | `85` | Buy Box share, as a whole-number percent. |
| `acos` | decimal | 0.0 - 1.0 fraction | `0.35` | ACoS (not percent). |
| `ad_spend_30d` | decimal | USD | `680.00` | Total PPC spend in last 30 days. |
| `rating` | decimal | 0.0 - 5.0 | `4.1` | Average star rating. |
| `review_count` | integer | whole number | `47` | Total review count on the listing. |
| `days_of_cover` | integer | whole number | `11` | Days of inventory remaining at current velocity. |
| `organic_rank_top_keyword` | integer | whole number >= 1 | `39` | Organic rank on the listing's main keyword (1 = best). |

## Optional fields

These are not required but unlock additional findings (especially
trend signals). Their absence never fails an audit.

| Column | Type | Format | Example | Adds |
|---|---|---|---|---|
| `category` | text | Amazon main category | `Home & Kitchen` | Label only today; reserved for future category benchmarking. |
| `units_ordered_30d` | integer | whole number | `114` | Used directly; if missing, units are estimated from `sessions_30d * conversion_rate`. |
| `ad_sales_30d` | decimal | USD | `1210.00` | Currently informational; reserved for PPC efficiency signals. |
| `images_count` | integer | whole number | `7` | Reserved for listing-quality signals. |
| `bullet_count` | integer | 0 - 5 | `5` | Reserved for listing-quality signals. |
| `has_a_plus` | boolean | `true`/`false` | `true` | Reserved for listing-quality signals. |
| `sessions_30d_prev` | integer | whole number | `6800` | Enables the `trend_sessions` signal. |
| `conversion_rate_prev` | decimal | fraction | `0.028` | Enables `trend_conversion`. |
| `acos_prev` | decimal | fraction | `0.32` | Enables `trend_acos`. |
| `organic_rank_prev` | integer | whole number | `22` | Enables `trend_rank`. |

## What happens when optional fields are missing

| Missing optional field | Effect |
|---|---|
| `units_ordered_30d` | Units estimated from `sessions_30d * conversion_rate`. |
| `sessions_30d_prev` | `trend_sessions` signal never fires. |
| `conversion_rate_prev` | `trend_conversion` signal never fires. |
| `acos_prev` | `trend_acos` signal never fires. |
| `organic_rank_prev` | `trend_rank` signal never fires. |
| `category` | No current effect. |

## What happens when required fields are missing

| Missing required field | Patterns / signals affected |
|---|---|
| `buy_box_pct` | `analyze_buy_box` signal suppressed; patterns `buy_box_loss_healthy_stock` and `buy_box_war_on_ranked` cannot match. |
| `cogs`, `fba_fees` | Every ROI that depends on unit margin degrades to an `insufficient` explanation; `calculate_true_profit_margin` signal suppressed. |
| `ctr` | `listing_over_promise` and `hidden_winner` patterns cannot match. |
| `acos` | `ppc_waste_on_organic`, `unit_economics_loss`, `overbid_weak_listing` patterns cannot match; ACoS-based ROI savings degrade. |
| `sessions_30d`, `conversion_rate` | Suppression-risk signal loses one of its three flags; underinvested_winner and several ROI formulas degrade. |
| `rating` | `reviews_killing_conversion` cannot fire. |
| `review_count` | `review_starvation`, `weak_listing_foundation`, `discontinuation_candidate` cannot fire. |
| `days_of_cover` | Inventory patterns (`inventory_trap`, `restock_urgency`) cannot fire. |
| `organic_rank_top_keyword` | Several rank-aware patterns (`ppc_waste_on_organic`, `ppc_addiction`, `buy_box_war_on_ranked`, `weak_listing_foundation`) cannot fire. |

## Column order in the template files

The files `asin_template.csv` and `sample_asin_data.csv` use the
column order below. You do not have to match it; intake maps columns
by header name, not position. But keeping the same order makes review
easier.

```
asin, title, category, sessions_30d, units_ordered_30d, conversion_rate,
ctr, review_count, rating, days_of_cover, ad_spend_30d, ad_sales_30d,
acos, images_count, bullet_count, has_a_plus, organic_rank_top_keyword,
price, cogs, fba_fees, buy_box_pct,
sessions_30d_prev, conversion_rate_prev, acos_prev, organic_rank_prev
```

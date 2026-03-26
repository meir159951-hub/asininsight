# Sample Scenario Notes

This file explains the intended meaning of each sample ASIN in
[sample_asin_data.csv](C:\Users\meir1\ai_trading_system\amazon_seller_audit_mvp\sample_data\sample_asin_data.csv).

The goal is to compare:

- what the dataset is trying to simulate
- what the diagnosis engine actually reports

If those diverge too much, the rules need adjustment.

## Scenario guide

| ASIN | Intended story | Expected main category |
|---|---|---|
| `B0DEMO001` | Moderate traffic, weak listing quality, rising inventory risk, ads not efficient enough | `Offer` or `Ops` |
| `B0DEMO002` | Healthy baseline product with good conversion and trust | `Stable` |
| `B0DEMO003` | Broad failure case: weak CTR, weak conversion, weak trust, stock risk, poor ads | `Offer` |
| `B0DEMO004` | Product gets clicks but fails after the click; likely offer/conversion issue | `Offer` |
| `B0DEMO005` | Conversion is solid, but click-through is weak relative to portfolio | `Traffic` |
| `B0DEMO006` | Trust weakness: low reviews, weak rating, some content gaps | `Trust` |
| `B0DEMO007` | Strong product used as a healthy comparison anchor | `Stable` |
| `B0DEMO008` | Paid spend and stock risk are both hurting growth; also has weak merchandising | `Ops` or `Offer` |

## How to use this file

1. Load the sample dataset into the MVP
2. Click through each ASIN
3. Compare the reported diagnosis with the intended story here
4. Adjust the logic when the gap is too large

## What counts as a good result

- The engine identifies the same broad category as the intended story
- The top blockers make sense for the scenario
- The recommended actions feel aligned with the intended problem

## What counts as a logic miss

- Healthy ASINs are marked as severely weak
- CTR-heavy cases are diagnosed mainly as trust problems
- Conversion-heavy cases are diagnosed mainly as traffic problems
- Ops-driven cases ignore inventory pressure

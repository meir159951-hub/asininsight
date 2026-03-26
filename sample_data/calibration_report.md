# Calibration Report

This is the first manual calibration pass against
[sample_scenarios.md](C:\Users\meir1\ai_trading_system\amazon_seller_audit_mvp\sample_data\sample_scenarios.md).

The goal is to estimate whether the current rules are directionally aligned with the intended sample stories.

## Calibration table

| ASIN | Intended category | Likely current engine category | Calibration read |
|---|---|---|---|
| `B0DEMO001` | `Offer` or `Ops` | `Offer` | Acceptable. The engine likely over-weights offer-side blockers relative to inventory. |
| `B0DEMO002` | `Stable` | `Stable` | Good. This looks like a healthy anchor case. |
| `B0DEMO003` | `Offer` | `Offer` | Good. Broad failure case should be clearly weak. |
| `B0DEMO004` | `Offer` | `Offer` | Good. This should read mainly as a post-click problem. |
| `B0DEMO005` | `Traffic` | `Traffic` | Good. Weak CTR should dominate here. |
| `B0DEMO006` | `Trust` | `Offer` before improvement #2 | Improvement target: trust should be weighted more clearly after the combined trust rule. |
| `B0DEMO007` | `Stable` | `Stable` | Good. Healthy comparison product. |
| `B0DEMO008` | `Ops` or `Offer` | `Offer` | Borderline. Inventory pressure may be under-weighted versus offer-side blockers. |

## Main finding

The current engine appears directionally correct for most scenarios.

The biggest likely weakness is:

- `Ops` cases can be overshadowed by multiple offer-side blockers

This is most visible in scenarios like:

- `B0DEMO001`
- `B0DEMO008`

## Why this happens

Inventory currently contributes:

- one direct blocker

Offer-side problems can contribute several blockers:

- conversion
- listing
- ads
- growth combination
- below-portfolio conversion

That can make the diagnosis category drift toward `Offer` even when stock risk is strategically important.

## Recommended adjustment

Add one combined inventory-pressure signal when:

- days of cover is critically low
- and demand or spend is still active

This would let the engine surface:

`Growth constrained by inventory`

That should strengthen `Ops` categorization in the right cases without changing the entire framework.

## Calibration improvement #2

Another likely gap was trust-heavy cases such as:

- `B0DEMO006`

In those scenarios, weak conversion plus weak trust signals could still be read too much as an offer problem.

To improve this, the engine now adds a combined trust blocker when:

- rating is weak
- review count is low
- conversion is also weak

This new combined signal is:

`Trust is suppressing conversion`

Expected effect:

- stronger `Trust` categorization in mixed trust/conversion scenarios
- better alignment for products where the page may be acceptable, but credibility is not

This especially targets:

- `B0DEMO006`

## Calibration improvement #3

Healthy anchor products should not accumulate too much relative-noise from portfolio comparison rules.

This matters especially for:

- `B0DEMO002`
- `B0DEMO007`

To improve this, the engine now treats very strong ASINs as healthy anchors when they combine:

- strong conversion
- strong CTR
- strong reviews
- efficient ads
- safe inventory

Expected effect:

- healthy products stay closer to `Stable`
- relative comparison blockers do not over-fire on obviously strong ASINs
- stronger products can act as comparison anchors for weaker ones

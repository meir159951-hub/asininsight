# Real-Data Validation Report

## Phase status

`In progress, but structurally ready`

## Dataset used

- [realistic_messy_portfolio.csv](C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\sample_data\realistic_messy_portfolio.csv)

## Dataset profile

Current messy dataset characteristics:

- 11 raw rows
- 9 expected valid rows
- 2 intentionally rejected rows
- mixed categories, not a single-category portfolio
- multiple formatting patterns across rate and money fields

Expected rejected rows:

- one row missing `ASIN`
- one row missing `title`

## What has already been hardened for this phase

- alternate header support
- semicolon-delimited intake
- percent and decimal rate parsing
- decimal-comma parsing
- currency-style numeric parsing
- invalid-row rejection with visible reasons
- benchmark-scope visibility
- same-category-first benchmarking
- data-quality guidance
- sanity checks
- export alignment with benchmark context
- readiness now degrades to `Conditional` when the evidence is thin, incomplete, or benchmark confidence is weak

## Current read

The MVP now looks strong enough to start internal real-data validation.

It still relies on heuristic rules, but it no longer depends on unrealistically clean input or a single static demo path.

## What looks strongest right now

- intake resilience
- portfolio triage structure
- readability of the diagnosis output
- export coverage for internal review
- benchmark-scope transparency

## Concrete validation read so far

The current build appears strong on these points:

1. The messy dataset is suitable for testing input robustness, not just diagnosis logic.
2. The product already has the right visibility for this phase:
   - raw / valid / rejected counts
   - header mapping
   - benchmark scope
   - data quality
   - sanity checks
3. The current portfolio view is less likely to overstate certainty than earlier versions because:
   - category-first benchmarking now exists
   - mixed-portfolio interpretation is surfaced more explicitly
   - exports now carry more of the same context shown in the UI

4. The validation layer now grades benchmark reliability more explicitly:
   - `high`
   - `medium`
   - `low`

That is better than the earlier coarse read, because the product can now express when a file is category-concentrated enough for stronger portfolio comparisons.

5. The validation layer now also produces a `Validation score`, so internal testing is not only descriptive but also partially measurable.

## Current pass / watch / fail view

### Pass

- intake can now tolerate realistic formatting noise
- the product visibly distinguishes weak input from strong input
- the output is structured enough to support internal review

### Watch

- mixed-category portfolios can still reduce diagnosis clarity
- readiness labels still need scrutiny on thinner data
- portfolio-wide recurring blockers may still be noisier than single-ASIN reads
- category concentration can still make the same file useful for ASIN diagnosis but weaker for portfolio proof
- readiness thresholds may still need another pass once more real seller exports are available

## Current structured test result

The product now exposes this structure directly in the UI and exported validation context, not only in this document.

### Intake

Status: `Pass`

Why:

- the dataset is intentionally messy and the current product is already built to surface:
  - raw rows
  - valid rows
  - rejected rows
  - header mapping
- the current test dataset includes exactly the kinds of issues we wanted:
  - alternate headers
  - semicolon delimiters
  - percentage formats
  - decimal commas
  - two invalid rows

### ASIN-level diagnosis

Status: `Pass with caution`

Why:

- the current product now favors ASIN-level reads over portfolio-wide reads when the file is category-mixed
- benchmark scope is explicit
- benchmark confidence is now explicit
- peer-count context is now explicit

Main caution:

- ASIN-level diagnosis is more trustworthy than broad portfolio comparisons on mixed files

### Portfolio-level diagnosis

Status: `Watch`

Why:

- the product now communicates when the portfolio is too mixed for stronger portfolio proof
- the portfolio decision layer now lowers confidence on heavily mixed files
- the portfolio overview now uses the same report-bound validation context as the rest of the product
- but recurring blockers and portfolio-level conclusions can still be noisier than single-ASIN diagnosis

Main caution:

- the portfolio layer is useful for prioritization, but should not yet be treated as strong evidence on mixed-category files

### Export integrity

Status: `Pass`

Why:

- validation context now flows through:
  - single-ASIN JSON
  - portfolio JSON
  - portfolio CSV
  - portfolio summary
  - validation summary

That means exported output no longer loses the same context shown in the UI.

### Not yet proven

- whether the current diagnosis is credible enough for a seller who knows their own business well
- whether the ASIN-level promise is stronger than the portfolio-level promise
- whether the product is differentiated enough once exposed to real seller workflows

## What still needs the most scrutiny

- whether weak-category peer groups still produce believable comparisons
- whether readiness labels are too aggressive on mixed or thin data
- whether portfolio-level conclusions stay useful when the file is category-mixed
- whether the diagnosis is still too generous with directional certainty

## Current recommendation

Do not move to Amazon integration yet.

Finish this phase first:

1. run repeated checks against the messy dataset
2. tighten any remaining false confidence
3. confirm that the new readiness guard is conservative enough on thin-data ASINs
4. confirm that the portfolio decision layer remains believable

## Exit condition for this phase

This phase is complete when the current MVP feels reliable enough that showing it to an external seller would no longer feel premature.

## Immediate next move

Use the current validation pack to do focused internal review in this order:

1. load the messy dataset
2. confirm the expected rejected rows and header mapping
3. inspect the weakest ASINs first
4. inspect the portfolio decision layer second
5. log any false confidence before moving toward external validation

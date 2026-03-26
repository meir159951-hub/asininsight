# Real-Data Validation Checklist

Use this checklist when testing the current MVP against messy or realistic CSV input.

Main product file:

- [app.html](C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\app.html)

Primary test dataset:

- [realistic_messy_portfolio.csv](C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\sample_data\realistic_messy_portfolio.csv)

## Intake checks

- [ ] The file loads without breaking the page
- [ ] Raw / valid / rejected row counts are visible
- [ ] Rejected rows show clear reasons
- [ ] Header mapping is visible
- [ ] Alternate headers map correctly
- [ ] Percent fields parse correctly
- [ ] Decimal-comma values parse correctly
- [ ] Currency-style fields parse correctly

## Diagnosis checks

- [ ] The weakest ASIN opens first
- [ ] Top blockers feel believable
- [ ] Root cause feels directionally correct
- [ ] Scaling readiness feels believable
- [ ] Data-quality warnings reduce overconfidence where needed
- [ ] Benchmark scope is clearly visible
- [ ] Same-category benchmarking is used when enough peers exist

## Portfolio checks

- [ ] Portfolio snapshot feels coherent
- [ ] Portfolio read feels believable
- [ ] Validation status matches the actual shape of the uploaded file
- [ ] Benchmark reliability feels fair for the category mix in the file
- [ ] Immediate triage list is sensible
- [ ] Growth candidates list is sensible
- [ ] Focus split feels useful
- [ ] Recurring blockers are not obviously noisy
- [ ] Overview table supports quick scanning

## Export checks

- [ ] Current ASIN summary reflects what the UI shows
- [ ] Current ASIN JSON includes benchmark and validation context
- [ ] Portfolio JSON includes decision, focus split, and validation context
- [ ] Portfolio CSV includes blocker count, readiness context, and benchmark reliability
- [ ] Export preview matches downloadable output

## Decision

- [ ] Good enough to test with more realistic inputs
- [ ] Needs another calibration pass before broader testing

## Current internal read

- [x] Intake resilience looks ready for this phase
- [x] ASIN-level diagnosis looks usable with caution
- [ ] Portfolio-level diagnosis is strong enough on mixed files
- [x] Export integrity now carries the same context shown in the UI

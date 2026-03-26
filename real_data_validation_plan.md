# Real-Data Validation Plan

## Goal

Move from "the local MVP looks strong" to "the diagnosis still feels believable on messier, more realistic input."

This phase is still internal product validation.

It does **not** prove:

- market demand
- willingness to pay
- live Amazon integration viability

It is meant to prove:

- the intake layer can tolerate imperfect CSVs
- the diagnosis does not collapse when the input is less clean
- the output remains useful enough to support the next phase

## Scope for this phase

We are validating three things:

1. Intake resilience
2. Diagnosis quality
3. Decision usefulness

## Validation datasets

Primary dataset for this phase:

- [realistic_messy_portfolio.csv](C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\sample_data\realistic_messy_portfolio.csv)

Supporting notes:

- [realistic_messy_notes.md](C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\sample_data\realistic_messy_notes.md)
- [sample_scenarios.md](C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\sample_data\sample_scenarios.md)
- [calibration_report.md](C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\sample_data\calibration_report.md)

## What we test

### 1. Intake resilience

We want to confirm that the product:

- loads semicolon-delimited files
- handles alternate column names
- parses percent-style and decimal-style rates
- parses currency-style values
- rejects invalid rows visibly
- explains what got mapped and what got rejected

### 2. Diagnosis quality

We want to confirm that the diagnosis:

- does not become overconfident on weak input
- chooses the right benchmark scope when possible
- produces believable blockers
- produces believable root causes
- does not overreact to noisy portfolio-relative signals

### 3. Decision usefulness

We want to confirm that the product still answers practical questions:

- what needs fixing first
- which ASINs are not ready to scale
- which ASINs can support growth
- whether the portfolio is mostly a fix problem or a scale problem

## Pass criteria

This phase counts as successful if all of the following are true:

1. The dataset loads without breaking the product flow.
2. Invalid rows are surfaced clearly.
3. The diagnosis for the weakest ASINs feels directionally correct.
4. The portfolio-level decision board feels coherent.
5. The output is understandable without extra explanation from us.

## Soft failure signals

This phase is not good enough yet if we still see:

- blockers that obviously contradict the input story
- overconfident output on low-quality input
- misleading portfolio comparisons across mixed categories
- exports that omit important context used in the UI
- triage and growth candidate lists that feel arbitrary

## What happens after this phase

If the product passes this phase:

1. run controlled tests on more realistic CSVs
2. prepare a lightweight external demo flow
3. only then consider market-facing validation

If it fails this phase:

1. tighten the diagnosis rules again
2. reduce over-interpretation
3. narrow the product promise before external validation

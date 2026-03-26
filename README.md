# Amazon Seller Audit MVP

This is a zero-dependency local prototype for an Amazon ASIN diagnosis product.

It does not connect to Amazon yet. Instead, it reads demo ASIN data,
analyzes common growth issues, and generates a diagnosis inside a local browser UI.

## What this prototype proves

- The product concept can be explained clearly
- A seller can upload ASIN data and receive a structured diagnosis
- The diagnosis can prioritize issues instead of dumping raw data
- The MVP can simulate a narrow Amazon growth workflow without external services

## What it does not prove yet

- Real seller demand
- Real Amazon API integration
- Real billing or user onboarding
- Real production benchmarking across categories and accounts

## Files

- `audit_engine.py`: Reads store data and generates the audit report
- `app.html`: Local browser MVP for CSV upload and ASIN diagnosis
- `sample_data/demo_store.json`: Demo input data
- `sample_data/sample_asin_data.csv`: Demo CSV for the browser MVP
- `sample_data/realistic_messy_portfolio.csv`: Messier intake test CSV with alternate headers and mixed formatting
- `real_data_validation_plan.md`: Internal plan for the real-data validation phase
- `real_data_validation_checklist.md`: Internal checklist for validation runs
- `real_data_validation_report.md`: Running summary of what the current validation phase proves
- `sample_data/asin_template.csv`: Blank CSV template for your own data
- `sample_data/sample_scenarios.md`: Intended scenario meanings for the sample dataset
- `sample_data/realistic_messy_notes.md`: Notes for the messy intake test dataset
- `output/`: Generated reports
- `asin_mvp_blueprint.md`: Product blueprint for the ASIN diagnosis MVP
- `asin_pilot_plan.md`: Pilot framing for the narrower product direction
- `product_strategy.md`: Differentiation and product strategy notes
- `final_mvp_handoff.md`: End-of-phase summary and next-step handoff

## Run

From the repository root:

```powershell
& "C:\Users\meir1\ai_trading_system\.venv\Scripts\python.exe" `
  "C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\audit_engine.py"
```

Optional custom input:

```powershell
& "C:\Users\meir1\ai_trading_system\.venv\Scripts\python.exe" `
  "C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\audit_engine.py" `
  --input "C:\path\to\store.json"
```

The script writes an HTML report into `output/`.

## Browser MVP

You can also open the local MVP directly in a browser:

```text
C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\app.html
```

Use the sample CSV in:

```text
C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\sample_data\sample_asin_data.csv
```

## Suggested local flow

1. Open `app.html`
2. Drag in your own CSV or click `Load Sample Data`
3. Review the weakest ASIN diagnosis
4. Switch between ASINs using the selector or the portfolio overview
5. Copy or download the diagnosis summary if needed
6. Compare the output with `sample_scenarios.md` to calibrate the rules

You can also use `Load Realistic Sample` to test the intake layer against alternate headers, semicolon delimiters, mixed percentage formats, and invalid rows.

## Current MVP features

- CSV upload
- Drag-and-drop CSV loading
- One-click sample data load
- One-click realistic intake test load
- Browser-side session restore after refresh
- Reset flow for repeated testing
- Visible dataset source state
- Visible raw/valid/rejected row counts during intake
- Flexible column mapping for several common alternate header names
- Visible header-mapping feedback inside the diagnosis
- Support for comma- and semicolon-delimited files
- Numeric parsing that tolerates percent signs, commas, and currency-style formatting
- Rate parsing that accepts either decimals (`0.12`) or percentage-style values (`12%` / `12`)
- Better handling for decimal commas and accounting-style negatives like `(123.45)`
- ASIN selector
- Quick filters for ASIN focus buckets
- Clickable portfolio overview
- Portfolio overview now includes readiness, data quality, and blocker count at a glance
- Portfolio overview now includes benchmark confidence and peer-count context
- Portfolio overview now surfaces portfolio confidence and validation score
- Portfolio rank for each ASIN
- Growth score
- Ranked blockers
- Root cause summary
- Recommended order of work
- In-product reading legend for category, priority, confidence, and data quality
- Portfolio-relative benchmarking
- Same-category-first benchmarking when enough category peers exist
- Gap-vs-portfolio view for the selected ASIN
- Benchmark scope now flows through summaries and exports
- Benchmark confidence and peer-count context now flow through the UI and exports
- Validation score now appears in the UI and exported validation context
- Validation checks now appear as structured `Pass / Pass with caution / Watch` reads
- Current ASIN JSON now carries the full validation checks context
- Validation reads now rely on report-bound load stats, not only transient UI state
- Portfolio overview now uses the same report-bound validation flow as the rest of the product
- The UI now distinguishes between portfolio-wide averages and the benchmark scope used for the current ASIN
- Portfolio snapshot now shows how many ASINs used category vs portfolio benchmarks
- Recurring blocker summary across the uploaded portfolio
- Confidence labels
- Scaling readiness label for the selected ASIN
- Scaling readiness now stays `Conditional` when the evidence is thin or benchmark context is weak, even if no major blocker fires
- Scaling readiness summary across the uploaded portfolio
- Immediate triage list for the weakest or not-ready ASINs
- Portfolio focus split for fix-first vs scale-ready work
- "Before acting" validation hints for weaker reads
- Copyable diagnosis summary
- Downloadable diagnosis summary
- Downloadable current-ASIN diagnosis JSON
- Downloadable validation summary
- Downloadable portfolio summary
- Downloadable portfolio diagnosis CSV
- Downloadable portfolio diagnosis JSON
- Input profile summary for the uploaded file
- Validation status read for the uploaded file
- Validation score for the uploaded file
- Validation context now flows through summary and JSON exports
- Portfolio exports now include recurring blocker context and blocker counts
- Portfolio CSV now includes rank and metric gaps vs portfolio averages
- Scaling readiness now appears in both single-ASIN and portfolio exports
- Portfolio exports now include focus buckets tied to readiness
- Growth candidate view for the strongest scale-ready ASINs
- Portfolio decision board for fix-vs-scale direction
- Portfolio decision board now lowers confidence on heavily mixed files
- Scenario notes link inside the UI
- Data quality guidance inside the diagnosis
- Sanity checks for obviously invalid or suspicious values
- Built-in scenario calibration panel for the sample ASINs
- Scenario calibration overview across the full sample dataset

## Current MVP limits

- No live Amazon connection
- No authentication
- No billing
- No category-aware benchmarks
- No historical trend analysis

## Current next phase

The build phase for the first local MVP is effectively complete.

The current next phase is:

`real-data validation`

Use these documents for that phase:

- [real_data_validation_plan.md](C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\real_data_validation_plan.md)
- [real_data_validation_checklist.md](C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\real_data_validation_checklist.md)
- [real_data_validation_report.md](C:\Users\meir1\ai_trading_system\product_lab\amazon_seller_audit_mvp\real_data_validation_report.md)

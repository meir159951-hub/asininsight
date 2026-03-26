# ASIN MVP Blueprint

## Product name

Why Sales Stalled

## Product type

Single-purpose diagnosis tool for one Amazon ASIN.

## User goal

The seller wants a clear answer to one question:

`Why is this product not growing?`

## MVP format

A simple local or web-based tool with:

- one upload screen
- one results screen

No accounts.
No Amazon login.
No billing.

## Screen 1: Input

### Purpose

Collect the ASIN data needed for a first diagnosis.

### User action

Upload a CSV file containing one or more ASIN rows.

### Required fields

| Field | Purpose |
|---|---|
| ASIN | identify product |
| title | display in result |
| sessions_30d | traffic signal |
| units_ordered_30d | sales signal |
| conversion_rate | conversion diagnosis |
| ctr | click-through diagnosis |
| review_count | trust diagnosis |
| rating | trust diagnosis |
| days_of_cover | inventory diagnosis |
| ad_spend_30d | ad efficiency diagnosis |
| ad_sales_30d | ad efficiency diagnosis |
| acos | ad efficiency diagnosis |
| images_count | listing quality diagnosis |
| bullet_count | listing quality diagnosis |
| has_a_plus | listing quality diagnosis |

### Optional fields

| Field | Purpose |
|---|---|
| organic_rank_top_keyword | SEO weakness signal |
| price | context only |
| category | display only |

### Input UX

| Element | Description |
|---|---|
| File upload box | drag and drop or select CSV |
| Sample CSV link | lets user see expected schema |
| Analyze button | starts diagnosis |
| Validation message | tells user if required columns are missing |

## Screen 2: Results

### Purpose

Show the seller the top reasons this ASIN is underperforming.

### Output blocks

| Block | What it shows |
|---|---|
| ASIN summary | title, ASIN, category |
| growth score | simple 0-100 score |
| top blockers | 3 to 5 ranked issues |
| issue detail | why each blocker matters |
| next actions | what to fix first |
| metric snapshot | key supporting metrics |

### Tone of output

- plain language
- direct
- low jargon
- action-oriented

## Blocker rules

### 1. CTR blocker

Trigger if:

- `ctr < 0.0035`

Meaning:

- the product is not winning enough clicks from search or ads

Action:

- improve hero image
- tighten title positioning

### 2. Conversion blocker

Trigger if:

- `conversion_rate < 0.025`

Meaning:

- traffic exists, but buyers are not converting at a healthy rate

Action:

- review price, creative, reviews, and listing clarity

### 3. Review trust blocker

Trigger if:

- `rating < 4.0`
- or `review_count < 25`

Meaning:

- trust is weak compared with stronger competing listings

Action:

- inspect review complaints
- improve review generation process

### 4. Ad waste blocker

Trigger if:

- `acos > 0.45`

Meaning:

- ad spend is likely inefficient

Action:

- cut weak spend
- improve listing conversion before scaling ads

### 5. Inventory risk blocker

Trigger if:

- `days_of_cover < 14`

Meaning:

- stock risk may damage sales and ranking

Action:

- replenish inventory
- avoid over-driving demand until supply is safe

### 6. Listing quality blocker

Trigger if any:

- `images_count < 6`
- `bullet_count < 5`
- `has_a_plus = false`

Meaning:

- listing quality may be limiting clicks and conversion

Action:

- improve content completeness and merchandising quality

## Ranking logic

Each blocker gets:

- severity
- explanation
- recommended action

### Severity order

1. critical
2. high
3. medium
4. low

### Example severity logic

| Blocker | Critical | High | Medium |
|---|---|---|---|
| conversion | <1.8% | <2.5% | <3.0% |
| CTR | <0.25% | <0.35% | <0.45% |
| ACOS | >80% | >45% | >35% |
| days of cover | <8 days | <14 days | <21 days |
| rating | <3.9 | <4.1 | <4.3 |

## Growth score

Start from 100 and subtract points per blocker.

### Example deductions

| Severity | Score impact |
|---|---|
| critical | -8 |
| high | -5 |
| medium | -3 |
| low | -1 |

## MVP success condition

The MVP is good enough if:

- a seller can upload data in under 1 minute
- the report feels understandable without extra explanation
- the top blockers feel believable
- the next actions feel specific enough to be useful

## What is out of scope

- live Amazon API connection
- account creation
- payment system
- multi-user dashboards
- store-wide workflow automation
- ad campaign editing

## Next technical build

Build a single-page experience with:

- CSV upload
- diagnosis engine
- results view

The current report engine can be adapted into this flow.

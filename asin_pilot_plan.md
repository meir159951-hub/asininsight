# ASIN Pilot Plan

## Pilot concept

Instead of diagnosing an entire Amazon store, the first pilot focuses on one question:

`Why is this ASIN not growing?`

This is narrower, easier to explain, and easier to test.

## Why this is better than the broader idea

- the seller understands it faster
- the output is more actionable
- the scope is smaller
- the product is easier to build
- differentiation is clearer

## Example user

John sells a product on Amazon.

The listing is live.
He has some traffic.
He may even be spending on ads.

But the product is not growing the way he expected.

John wants one answer:

`What is probably blocking this ASIN?`

## What Amazon already gives John

- raw performance reports
- ad reporting
- listing tools
- inventory and account data
- some AI guidance inside Seller Central

## What Amazon does not clearly give as a standalone product

A short diagnosis that combines multiple weak signals and answers:

- what is most likely wrong
- how serious it is
- what to fix first

## Pilot promise

Upload one ASIN data file and get a ranked diagnosis of why growth is weak.

## Pilot input

The first version should use CSV, not Amazon API.

### Example fields

- ASIN
- title
- sessions
- units ordered
- conversion rate
- CTR
- review count
- rating
- days of cover
- ad spend
- ad sales
- ACOS
- images count
- bullet count
- A+ status

## Pilot output

The report should answer:

1. What are the top 3 to 5 bottlenecks?
2. Which bottleneck is most urgent?
3. What should the seller do next?

### Example output blocks

- ASIN growth score
- main growth blockers
- severity by blocker
- likely business impact
- recommended next actions

## Diagnosis areas

### Traffic signal

- weak CTR
- poor search attractiveness

### Conversion signal

- enough sessions but not enough orders

### Trust signal

- weak rating
- low review count

### Ad efficiency signal

- high ACOS
- ad spend not converting well

### Inventory signal

- low stock cover
- risk of rank loss

### Listing quality signal

- weak image count
- missing bullets
- missing A+ content

## Why this may still be differentiated

The value is not:

- more data
- more dashboards
- more seller tools

The value is:

- diagnosis
- prioritization
- clarity

## What the seller should feel after reading the report

`Now I know where the real problem is.`

Not:

`Now I have more metrics to look at.`

## Business model for the pilot

### Option A

One-time ASIN diagnosis

### Option B

Monthly monitoring for a small number of ASINs

## Best starting model

Start with a one-time diagnosis concept.

Why:

- simpler to explain
- easier to test willingness to pay
- lower commitment for the user
- cleaner first product

## Pilot success criteria

The pilot is promising if:

- the offer is easy to understand
- users care about the output
- users say the diagnosis feels clearer than raw Amazon reports
- at least some users want to run it on their own ASIN

## Next build recommendation

Build a simple ASIN diagnosis screen:

- upload CSV
- press analyze
- view ranked blockers

No Amazon login.
No billing.
No full dashboard.

# Product Strategy

## Core question

Can we build something in the Amazon seller space that is different enough from existing tools to deserve testing?

## Short answer

Yes, but not as a broad seller platform.

The likely opening is a narrow diagnosis product:

`Why did this ASIN stop growing?`

## What already exists

### Broad seller suites

- Helium 10
- Jungle Scout
- SellerApp

These products already cover large parts of:

- listing analysis
- keyword research
- PPC analytics
- inventory management
- seller workflow

### Amazon itself

Amazon is adding more built-in AI and seller guidance inside Seller Central.

That makes a general "AI helper for Amazon sellers" weak as a standalone concept.

## What we should not build

- a full Amazon seller suite
- a generic AI assistant for sellers
- a feature-heavy dashboard
- a listing optimization tool only

## Where differentiation may exist

### 1. Diagnosis instead of tooling

Most seller tools provide data, scores, and many workflows.

We can focus on one specific output:

`a prioritized diagnosis of why growth stopped`

That is a different promise from:

- keyword research
- listing builders
- analytics dashboards
- operations suites

### 2. Simplicity for smaller sellers

Large tools are powerful, but they can feel heavy, expensive, and broad.

We can aim for:

- one clear question
- one report
- one ranked action list

### 3. Explainability

The report should not just flag weak metrics.

It should connect the weak signals:

- low CTR
- low conversion
- poor reviews
- high ACOS
- low stock cover

And translate them into:

- what is probably wrong
- why it matters
- what to fix first

## Proposed differentiated product

### Working title

Why Sales Stalled

### Product promise

Find the top reasons a product or store stopped growing, and get a ranked action plan.

### Target customer

- small and mid-sized Amazon sellers
- brands with a few active ASINs
- sellers with some sales or ad spend already
- users who do not want a full enterprise suite

### Main value

The product saves time, reduces confusion, and tells the seller where to look first.

It is not a replacement for Helium 10 or Jungle Scout.
It is a focused diagnosis layer.

## Differentiation matrix

| Area | Broad tools | Our product |
|---|---|---|
| Product scope | Many seller workflows | One diagnosis workflow |
| Primary output | Dashboard, tools, metrics | Ranked reasons and next actions |
| Learning curve | Medium to high | Low |
| Ideal buyer | Power user or scaling seller | Smaller seller with a clear pain |
| Positioning | Seller operating system | Growth bottleneck diagnosis |

## Real risk

The biggest risk is not technical.

It is that sellers may say:

`I already get enough insight from my current tools.`

If that happens, our diagnosis must feel:

- faster
- clearer
- easier to act on

Otherwise there is no reason to adopt it.

## MVP recommendation

Do not start with a full store platform.

Start with:

`ASIN Growth Diagnosis`

### Input

- CSV upload
- one or more ASIN performance rows

### Output

- growth score
- top 3 to 5 bottlenecks
- severity
- recommended next actions

### First diagnosis areas

- click-through weakness
- conversion weakness
- reviews and trust issues
- ad inefficiency
- inventory risk
- listing quality gaps

## Business model

### Stage 1

One-time diagnosis report

### Stage 2

Monthly monitoring for multiple ASINs

### Stage 3

Expanded product with alerts and store-level views

## What success would look like before launch

- the product feels different enough in one sentence
- the output is clearer than broad tools
- the first version can be demoed without Amazon API integration
- we can explain why a seller should use this even if they already have another tool

## Current recommendation

Proceed, but only with a narrow MVP.

The right next step is not more outreach.

It is refining the actual product spec so the differentiation is visible in the build itself.

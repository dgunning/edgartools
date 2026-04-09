---
description: Understand why XBRL equity statement values differ across layers in SEC filings. Python guide to accessing face totals, component breakdowns, and disclosure note detail with edgartools.
---

# Understanding Equity Statement Data Layers in XBRL

SEC equity statements report the same activity at three distinct levels of detail, and each level carries different numbers by design. Users working with edgartools sometimes compare a face statement total against a disclosure note value, find they don't match, and conclude the library has a bug. This guide explains the three layers, why their values differ, and how to access each one.

## The Three Layers

### Layer 1: Face Statement Totals

The face equity statement shows the total impact of each activity on stockholders' equity across all programs and sources. This is what `statement_of_equity()` renders by default.

```python
from edgar import Company

company = Company("MSFT")
filing = company.get_filings(form="10-K").head(1)[0]
financials = filing.obj().financials

eq = financials.statement_of_equity()
print(eq)
```

For Microsoft FY2025, the stock repurchase line reads approximately $18.4B. That figure is `us-gaap:StockRepurchasedAndRetiredDuringPeriodValue` — the total equity reduction from all share retirements across all programs during the year.

### Layer 2: Dimensional Breakdown by Equity Component

The same face-statement concepts are often also reported split by `us-gaap:StatementEquityComponentsAxis`, showing how much of the activity touched each equity component (common stock and paid-in capital vs. retained earnings). These dimensional rows sum back to the face total.

```python
df = eq.to_dataframe()

# Non-dimensional rows: face totals
face_rows = df[~df['dimension'].fillna(False)]

# Dimensional rows: breakdown by equity component
component_rows = df[df['dimension'].fillna(False)]
component_rows = component_rows[
    component_rows['dimension_axis'].str.contains('StatementEquityComponentsAxis', na=False)
]
# Period columns are date strings; use the last column for the most recent value
period_col = df.columns[-1]
print(component_rows[['label', 'dimension_member_label', period_col]])
```

For the MSFT repurchase example, the component breakdown shows roughly $5.9B against common stock/APIC and $12.6B against retained earnings — together summing to the $18.4B face total.

To include dimensional rows in the display, pass `view="detailed"`:

```python
eq_detailed = financials.statement_of_equity(view="detailed")
print(eq_detailed)
```

### Layer 3: Disclosure Note Detail

Disclosure notes in XBRL use a different concept and a different dimensional axis to report activity per repurchase program. For stock repurchases specifically, the concept is `us-gaap:StockRepurchasedDuringPeriodValue` (note: *Repurchased*, not *RepurchasedAndRetired*), grouped under `srt:ShareRepurchaseProgramAxis` or `us-gaap:ShareRepurchaseProgramAxis`.

```python
xbrl = filing.xbrl()

repurchase_program_facts = (
    xbrl.facts.query()
    .by_concept("StockRepurchasedDuringPeriodValue", exact=True)
    .with_dimensions()
    .to_dataframe()
)
print(repurchase_program_facts[['concept', 'value', 'dimension_axis', 'dimension_member_label']])
```

The note-level value for a single repurchase program might be $13.0B — substantially less than the $18.4B face total. Both numbers are correct. They measure different things.

## Why the Numbers Differ

The face total ($18.4B in the MSFT example) captures all equity retirements:
- Shares repurchased under the Board-authorized buyback program
- Shares withheld to cover employee tax obligations on equity awards
- Any other retirement activity in the period

The disclosure note ($13.0B) reports only the activity under a specific named repurchase program. Tax withholding retirements and other activity are excluded.

These are not the same economic measure. The gap is real, intended, and consistent with GAAP disclosure requirements.

## The Same Pattern Applies Broadly

Stock repurchases are the most common source of confusion, but the three-layer structure appears throughout the equity statement:

| Activity | Face Concept | Note/Detail Concept | Detail Axis |
|----------|-------------|---------------------|-------------|
| Share repurchases | `StockRepurchasedAndRetiredDuringPeriodValue` | `StockRepurchasedDuringPeriodValue` | `ShareRepurchaseProgramAxis` |
| Dividends | `DividendsCommonStock` | `DividendsCommonStockCash` | `StatementClassOfStockAxis` |
| Stock-based compensation | `ShareBasedCompensation` | `ShareBasedCompensationArrangementByShareBasedPaymentAwardEquityInstrumentsOtherThanOptionsGrantsInPeriodWeightedAverageGrantDateFairValue` | `AwardTypeAxis` |

The rule: face statement concepts roll up all activity; disclosure note concepts break it down by program, award type, or class.

## Taxonomy Migration Note

Older filings (roughly pre-2021) use `us-gaap:ShareRepurchaseProgramAxis` for per-program repurchase detail. More recent filings use `srt:ShareRepurchaseProgramAxis` following an SRT taxonomy migration. When searching across filing years, query for both:

```python
from edgar import Company
from edgar.xbrl import XBRLS

company = Company("MSFT")
filings = company.get_filings(form="10-K").head(5)
xbrls = XBRLS.from_filings(filings)

# Facts across five years
all_repurchase_facts = (
    xbrls.facts.query()
    .by_concept("StockRepurchasedDuringPeriodValue", exact=True)
    .with_dimensions()
    .to_dataframe()
)

# Filter to program-axis rows only, accepting both axis names
program_axis_mask = all_repurchase_facts['dimension_axis'].str.contains(
    'ShareRepurchaseProgramAxis', na=False
)
print(all_repurchase_facts[program_axis_mask][['concept', 'value', 'dimension_axis', 'dimension_member_label']])
```

## EdgarTools Standardization and Dual Concepts

EdgarTools maps both `StockRepurchasedAndRetiredDuringPeriodValue` and `StockRepurchasedDuringPeriodValue` to the same internal standard concept `StockRepurchasesEquity`. This is correct: they both relate to share repurchase activity.

The consequence is that a 10-K XBRL instance may contain both concepts, and both will appear when querying `StockRepurchasesEquity` through the standardized view. The 10-Q filing typically includes only the face concept. If you are building cross-filing or cross-period comparisons and need to disambiguate, filter by the exact XBRL concept name rather than the standard concept:

```python
# Face statement concept only
face_facts = (
    xbrl.facts.query()
    .by_concept("StockRepurchasedAndRetiredDuringPeriodValue", exact=True)
    .to_dataframe()
)

# Note-level concept only
note_facts = (
    xbrl.facts.query()
    .by_concept("StockRepurchasedDuringPeriodValue", exact=True)
    .with_dimensions()
    .to_dataframe()
)
```

## Quick Reference

### Get the face statement

```python
from edgar import Company

company = Company("MSFT")
financials = company.get_financials()
eq = financials.statement_of_equity()

# Default display: face totals, no dimensional rows
print(eq)
```

### Get the face statement with equity component breakdown

```python
# view="detailed" includes dimensional rows (Layer 2)
eq_detailed = financials.statement_of_equity(view="detailed")
df = eq_detailed.to_dataframe()

# Identify which rows are dimensional
component_rows = df[df['dimension'].fillna(False)]
```

### Get disclosure note per-program detail

```python
filing = company.get_filings(form="10-K").head(1)[0]
xbrl = filing.xbrl()

program_facts = (
    xbrl.facts.query()
    .by_concept("StockRepurchasedDuringPeriodValue", exact=True)
    .with_dimensions()
    .to_dataframe()
)
```

### DataFrame columns for dimensional inspection

| Column | Type | Description |
|--------|------|-------------|
| `dimension` | `bool` | True if this row is a dimensional breakdown |
| `dimension_axis` | `str` | The XBRL dimension axis (e.g., `us-gaap:StatementEquityComponentsAxis`) |
| `dimension_member` | `str` | The member concept within the axis |
| `dimension_member_label` | `str` | Human-readable member label (e.g., `"Common Stock and APIC"`) |

## Related Pages

- [Extract Financial Statements](extract-statements.md) — Getting income statements, balance sheets, and cash flow
- [XBRL Dimension Handling](../xbrl/concepts/dimension-handling.md) — How dimensional data works across all statement types
- [Multi-Year Financial Data](multi-year-financial-data-api.md) — Comparing equity data across multiple filings

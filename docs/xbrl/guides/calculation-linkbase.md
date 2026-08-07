# Calculation Linkbase & Extension Facts

Most XBRL APIs in EdgarTools hide the linkbase machinery and surface clean line items. But sometimes you need the calculation graph itself — to map a filer's own extension concepts (`jpm:AssetManagementFees`, `tsla:RestructuringAndOtherExpenses`) back to their us-gaap parents, to preserve signed weights for rollups, or to recover concepts that the presentation tree silently drops.

This guide covers two APIs that expose that raw calculation graph.

## Why the calculation linkbase matters

When a company files XBRL with the SEC, it ships several linkbase files:

| Linkbase | What it carries |
|---|---|
| Presentation (`_pre.xml`) | The ordered list of line items as the filer wants them rendered |
| Calculation (`_cal.xml`) | The parent → child math: which concepts roll up to which, and with what sign |
| Definition (`_def.xml`) | Dimensional structure (segments, geographies, etc.) |
| Label (`_lab.xml`) | Display labels per concept |

The presentation tree drives `render()`. The calculation tree is what lets a bank declare:

```text
us-gaap:Revenues
├── us-gaap:InterestAndDividendIncomeOperating
└── us-gaap:NoninterestIncome
    ├── jpm:AssetManagementFees                    (filer extension)
    ├── us-gaap:InvestmentBankingFees
    └── us-gaap:PrincipalTransactionsRevenue
```

That tree exists in every 10-K. Banks, insurers, REITs, and utilities all use it to disaggregate the standard us-gaap line items in industry-specific ways. The calculation linkbase API exposes it.

## Layer 1: `calculation_linkbase()` — the full graph as a DataFrame

```python
from edgar import Company

filing = Company("JPM").latest("10-K")
calc = filing.xbrl().calculation_linkbase()

calc.columns
# Index(['concept', 'concept_taxonomy', 'parent_concept', 'parent_taxonomy',
#        'weight', 'role_uri', 'role_short', 'menucat', 'is_abstract', 'label'])
```

Each row is one parent → child relationship.

### Example: building a per-filer concept hierarchy

For a stock-screening pipeline that needs to know which concepts roll up to revenue *for this specific filer*:

```python
# Find every extension concept and what us-gaap parent it rolls into
extensions = calc[
    (calc.concept_taxonomy == 'jpm') &
    (calc.parent_taxonomy == 'us-gaap')
]

# Or: build a per-parent index across all concepts (us-gaap + extensions)
noninterest_components = calc[calc.parent_concept == 'NoninterestIncome']
print(noninterest_components[['concept', 'concept_taxonomy', 'weight']])
#                       concept   concept_taxonomy  weight
# 6      AssetManagementFees                  jpm     1.0
# 7  InvestmentBankingFees             us-gaap     1.0
# 8  PrincipalTransactionsRevenue       us-gaap     1.0
# ...
```

Same shape works for any filer. The bank chart-of-accounts for JPM, the insurance chart for MetLife, the REIT chart for Realty Income — they're all in the calculation linkbase, encoded by each filer themselves. No hand-curated registry required.

### Signed weights — don't flatten them

The `weight` column preserves the XBRL `weight` attribute exactly. Real filings use `-1.0` for contra-account rollups:

```python
# MetLife's amortization entries subtract from operating expenses
met_calc = Company("MET").latest("10-K").xbrl().calculation_linkbase()
met_calc[met_calc.concept.str.contains('Amortization')][
    ['concept', 'parent_concept', 'weight']
]
# Some rows show weight=-1.0 — flattening to +1.0 would corrupt the rollup
```

If you're computing `parent = sum(child * weight for child in children)`, this matters. JPM's FY2023 cash flow statement has 64 negative-weight arcs across both standard and extension concepts.

### Filtering by SEC report tier

The `menucat` column carries the SEC's FilingSummary `MenuCategory` classification when
available. The values are the full category names, not single-letter codes:

| Value | Meaning |
|---|---|
| `Statements` | Face financial statements |
| `Details` | Disclosure detail schedules |
| `Notes` | Notes to the financial statements |
| `Tables` | Note tables |
| `Policies` | Accounting policies |
| `Cover` | Cover page |

```python
# Just the face financial statements, not all the detail schedules
face_statements = calc[calc.menucat == 'Statements']
```

`menucat` is `None` for older filings without a FilingSummary.

## Layer 2: `Statement.extension_arcs()` — extensions absent from a statement

The calculation linkbase often includes filer extensions that don't appear in the presentation tree for the same role. Those concepts have real values in the instance document, real parents in us-gaap, and real weights — but `render()` skips them.

```python
cash_flow = filing.xbrl().statements.cash_flow_statement()

# These appear nowhere in print(cash_flow):
for arc in cash_flow.extension_arcs():
    print(f"{arc.concept_taxonomy}:{arc.concept}")
    print(f"    -> {arc.parent_taxonomy}:{arc.parent_concept}  w={arc.weight:+.1f}")

# jpm:NetChangeInAdvancesToandInvestmentsInSubsidiaries
#     -> us-gaap:NetCashProvidedByUsedInInvestingActivities  w=+1.0
# jpm:NetBorrowingsFromSubsidiaries
#     -> us-gaap:NetCashProvidedByUsedInFinancingActivities  w=+1.0
```

These two extension concepts have real FY2023 values (`-$25B` and `-$2.249B` respectively) but don't show up in the rendered cash flow statement because the filer didn't add them to the presentation tree for that role.

### Getting the values too

```python
for arc in cash_flow.extension_arcs(include_values=True):
    print(f"{arc.concept}  {arc.period_key}  {arc.value:>20,.0f}")

# NetChangeInAdvancesToandInvestmentsInSubsidiaries  duration_2023-01-01_2023-12-31     -25,000,000,000
# NetChangeInAdvancesToandInvestmentsInSubsidiaries  duration_2022-01-01_2022-12-31               0
# NetBorrowingsFromSubsidiaries                      duration_2023-01-01_2023-12-31      -2,249,000,000
# ...
```

One `ExtensionArc` per (concept, context) when `include_values=True`.

### What `extension_arcs()` does not do

- **It does not change `render()` output.** The rendered statement is unchanged whether or not you call `extension_arcs()`. The new method is purely additive.
- **It does not include us-gaap or other standard concepts.** Only filer-authored extensions surface. Standard concepts that drop out of a statement's presentation tree are a different problem (usually a presentation-tree omission, not a missing-from-render bug).
- **It does not synthesize values.** `value` is whatever the instance document records. If a concept appears in the calc linkbase but has no facts (rare), `value` is `None`.

## When to use which API

| Question | API |
|---|---|
| What does this filer's chart of accounts look like? | `xbrl.calculation_linkbase()` |
| Which extensions roll up to `us-gaap:NoninterestIncome`? | `xbrl.calculation_linkbase()` filtered by `parent_concept` |
| What extension facts is `render()` silently dropping from this statement? | `statement.extension_arcs()` |
| What's the value of those dropped extensions? | `statement.extension_arcs(include_values=True)` |
| What signed weight does this concept carry in the rollup? | Either API — `weight` is on both |

## Performance notes

- `calculation_linkbase()` walks every node in every calc tree. JPM's FY2023 10-K has 438 arcs across 61 roles — runs in well under 100ms cold.
- `extension_arcs()` is a single-role walk — bounded by the size of the statement's calc tree. Typically dozens to hundreds of nodes.
- Both methods are lazy (computed on call). For repeated access, cache the result yourself.

## Related

- **[XBRL API reference](../../api/xbrl.md#calculation_linkbase)** — full method signatures
- **[Issue #766](https://github.com/dgunning/edgartools/issues/766)** — feature discussion and validation work

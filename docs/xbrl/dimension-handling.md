# Understanding Dimensions in Financial Statements

This guide explains how EdgarTools handles XBRL dimensions and how to get complete, accurate financial statements.

## Quick Summary

When you retrieve a financial statement, EdgarTools automatically:
- **Shows** values that belong on the face of the statement (including dimensional face values)
- **Hides** breakdown details that belong in notes disclosures (geographic, segment, etc.)

```python
from edgar import Company

company = Company("WDAY")
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Default: Shows face presentation (what you'd see in SEC Viewer)
income = xbrl.statements.income_statement()
print(income)

# Full data: Shows everything for custom analysis
df = income.to_dataframe(include_dimensions=True)
```

## Why Dimensions Matter

Many companies report financial values **only through dimensional XBRL**. Without proper handling, these statements appear incomplete or out-of-balance.

### The Scale of the Problem

Based on community research ([GH-577](https://github.com/dgunning/edgartools/issues/577)), dimensional-only reporting is widespread:

**Income Statement - Cost of Goods Sold:**
- BA (Boeing) 2023+, CARR (Carrier) 2020+, GD (General Dynamics) 2020+
- HII (Huntington Ingalls) 2020+, INTU (Intuit) 2018+, NOC (Northrop Grumman) 2019+
- RTX 2019+, SLB (Schlumberger) 2018+, WDAY (Workday) 2019+
- CHH 2022+, CHRW 2018+, CTAS 2020+, GEHC 2024+, MAR 2022+
- OTIS 2020+, PFE 2022, TT 2021+, UPS 2018, VZ 2020+

**Balance Sheet - Various Line Items:**
- Goodwill: BSX 2019, IBM 2023+, JKHY 2016+, MCD 2023
- PPE: BSX 2019, CSX 2015+, HLT 2022+, PFE 2022
- Receivables: COP 2023+, FIS 2024+, GEHC 2023+, LYB 2023+
- Payables: COP 2023+, HLT 2019+, LYB 2023+, WDC 2023+
- Debt: ADP 2023+, CAT 2020+, HLT 2019+
- Contract Liabilities: BBY 2021+, HLT 2019+, MAR 2018+, REGN 2020

### Example: Workday Income Statement

Workday reports Cost of Goods Sold exclusively via `ProductOrServiceAxis`:

```
                                               2025         2024         2023
Revenue:
  Subscription services                      $7,718M      $6,603M      $5,567M
  Professional services                        $728M        $656M        $649M
  Total Revenue                              $8,446M      $7,259M      $6,216M

Cost of Goods Sold:
  Subscription services                      $1,266M      $1,031M      $1,007M
  Professional services                        $803M        $740M        $703M
  Total COGS                                 $2,069M      $1,771M      $1,710M
```

**Without dimensional handling**: COGS would show as NaN/missing, making it impossible to calculate gross margin.

**With EdgarTools**: Both subscription and professional services COGS values are preserved, and the statement balances correctly.

### Example: Caterpillar Balance Sheet

Caterpillar reports debt through dimensional XBRL across multiple years:

| Year | Concept | Axis Used |
|------|---------|-----------|
| 2020-2025 | ShortTermBorrowings | ConsolidationItemsAxis |
| 2020-2025 | LongTermDebtCurrent | ConsolidationItemsAxis |
| 2020-2025 | LongTermDebt | ConsolidationItemsAxis |

EdgarTools preserves these values so debt totals appear correctly on the balance sheet.

## How It Works

### Face Values vs Breakdowns

Not all dimensional data is the same:

| Type | Description | Example | Shown by Default? |
|------|-------------|---------|-------------------|
| **Face Value** | Values that appear on the statement face | Product vs Service revenue | ✅ Yes |
| **Breakdown** | Drill-down details for notes disclosures | Revenue by country | ❌ No |

### Classification Logic

EdgarTools uses a tiered approach to classify dimensions:

**Tier 1: Definition Linkbase (Authoritative)**
- The XBRL filing itself declares which dimensions are valid for each statement
- If declared in the definition linkbase, it's a face value
- Highest confidence classification

**Tier 2: Curated Axis Lists**
- Known face-level axes: `ProductOrServiceAxis`, `DebtInstrumentAxis`, `PropertyPlantAndEquipmentByTypeAxis`
- Known breakdown axes: `StatementGeographicalAxis`, `StatementBusinessSegmentsAxis`, `BusinessAcquisitionAxis`
- Based on empirical analysis of S&P 500 filings

**Tier 3: Pattern Matching**
- Axes matching patterns like `FairValue*Axis` or `*HierarchyLevelAxis` are classified as breakdowns
- Fallback when other methods don't apply

## Usage Guide

### Standard View (Default)

Get the statement as it would appear in the SEC Viewer:

```python
from edgar import Company

company = Company("SLB")
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Face presentation - includes dimensional face values
income = xbrl.statements.income_statement()
print(income)
```

Output shows COGS by Product and Services (the dimensional face values):
```
Cost of Goods and Services Sold:
  Product                                    $10,982M
  Services                                   $17,847M
```

### Full Data View

Get all data including breakdowns for custom analysis:

```python
# All dimensional data included
df = income.to_dataframe(include_dimensions=True)

# Filter as needed for your analysis
geographic_breakdown = df[df['dimension_label'].str.contains('Geographic', na=False)]
```

### Working with Dimensional Data

The dataframe includes helpful columns for understanding dimensions:

```python
df = income.to_dataframe(include_dimensions=True)

# Key columns:
# - 'dimension': True/False - is this a dimensional row?
# - 'is_breakdown': True/False - is this a breakdown (vs face value)?
# - 'dimension_label': Human-readable dimension info

# Find all face-level dimensional values
face_dimensional = df[(df['dimension'] == True) & (df['is_breakdown'] == False)]

# Find all breakdown values
breakdowns = df[df['is_breakdown'] == True]
```

### Calculating Totals

When a concept has dimensional values but no non-dimensional total, you may need to sum:

```python
df = income.to_dataframe(include_dimensions=False)

# COGS may have individual values but NaN for total
cogs_rows = df[df['concept'] == 'us-gaap_CostOfGoodsAndServicesSold']

# Sum the non-NaN values for the total
period_col = '2025-01-31'  # or whichever period you need
total_cogs = cogs_rows[period_col].sum()
```

## Dimension Classification Reference

### Face-Level Axes (Always Shown)

These dimensions represent valid face presentation and are preserved by default:

| Axis | Usage |
|------|-------|
| `ProductOrServiceAxis` | Product vs Service breakdown (revenue, COGS) |
| `PropertyPlantAndEquipmentByTypeAxis` | PPE categories |
| `DebtInstrumentAxis` | Debt instrument types |
| `LongtermDebtTypeAxis` | Long-term debt categories |
| `ShortTermDebtTypeAxis` | Short-term debt categories |
| `StatementClassOfStockAxis` | Stock class distinctions |
| `ContracttypeAxis` | Contract types (defense contractors) |
| `MajorProgramsAxis` | Major program breakdown (defense) |

### Breakdown Axes (Filtered by Default)

These dimensions represent notes disclosures and are hidden by default:

| Axis | Usage |
|------|-------|
| `StatementGeographicalAxis` | Geographic segment breakdown |
| `StatementBusinessSegmentsAxis` | Business segment breakdown |
| `BusinessAcquisitionAxis` | Acquisition-specific details |
| `ConsolidationItemsAxis` | Consolidation eliminations |
| `MajorCustomersAxis` | Customer concentration |
| `RestatementAxis` | Prior period adjustments |
| `FairValueByFairValueHierarchyLevelAxis` | Fair value hierarchy |
| `RetirementPlanTypeAxis` | Pension plan details |

### Context-Dependent Axes

Some axes behave differently based on statement type:

```python
# StatementEquityComponentsAxis:
# - On Statement of Equity: STRUCTURAL (defines columns) - shown
# - On Balance Sheet: BREAKDOWN (notes detail) - hidden
```

## Troubleshooting

### Statement Shows NaN for Expected Values

**Possible causes:**
1. **Dimensional-only value with old EdgarTools version**: Upgrade to v5.7.4+
2. **No total row exists**: The XBRL only has dimensional breakdown, no aggregated total
3. **Unknown axis**: The dimension axis isn't in our classification lists

**Solution:**
```python
# Check what's in the full data
df = statement.to_dataframe(include_dimensions=True)
concept_rows = df[df['concept'].str.contains('YourConcept')]
print(concept_rows[['label', 'dimension', 'dimension_label', value_column]])
```

### Statement Doesn't Balance

**Check the dimensional data:**
```python
df = income.to_dataframe(include_dimensions=True)

# Look for missing values that might be dimensional
missing = df[df[value_column].isna() & (df['abstract'] == False)]
print(missing[['concept', 'label', 'dimension']])
```

### Need a Specific Breakdown

```python
# Get all data first
df = statement.to_dataframe(include_dimensions=True)

# Filter to specific dimension
geographic = df[df['dimension_label'].str.contains('Geographic', na=False)]
```

## API Reference

### Statement Methods

```python
# Get statement with default handling (face values preserved)
statement = xbrl.statements.income_statement()

# Convert to dataframe
df = statement.to_dataframe(
    include_dimensions=False,  # Default: filter breakdowns
    include_concept=True,      # Include concept column
)

df = statement.to_dataframe(
    include_dimensions=True,   # Include all dimensional data
)
```

### Dimension Classification API

```python
from edgar.xbrl.dimensions import (
    classify_dimension_with_confidence,
    DimensionConfidence,
    is_breakdown_dimension,
)

# Check if an item is a breakdown
is_breakdown = is_breakdown_dimension(item, xbrl=xbrl, role_uri=role_uri)

# Get detailed classification
classification, confidence, reason = classify_dimension_with_confidence(
    item,
    xbrl=xbrl,
    role_uri=role_uri
)
# Returns: ('face', DimensionConfidence.HIGH, 'Declared in definition linkbase')
```

### XBRL Dimension Methods

```python
# Check if definition linkbase exists for a role
has_def = xbrl.has_definition_linkbase_for_role(role_uri)

# Check if a specific dimension is valid for a role
is_valid = xbrl.is_dimension_valid_for_role('srt:ProductOrServiceAxis', role_uri)

# Get all valid dimensions for a role
valid_dims = xbrl.get_valid_dimensions_for_role(role_uri)
```

## Version History

| Version | Change |
|---------|--------|
| v5.7.4 | Definition linkbase-based dimension filtering (GH-577 fix) |
| v5.7.2 | Initial dimension handling with hardcoded lists (GH-569) |
| v5.7.0 | Changed default to `include_dimensions=False` |

## Related Resources

- [XBRL Roadmap](xbrl-roadmap.md) - Planned XBRL enhancements
- [GitHub Issue #577](https://github.com/dgunning/edgartools/issues/577) - Original problem documentation
- [SEC Financial Statement Data Sets](https://www.sec.gov/data-research/sec-markets-data/financial-statement-notes-data-sets) - SEC's processed XBRL data

## Acknowledgments

Special thanks to [@mpreiss9](https://github.com/mpreiss9) for extensive research documenting dimensional-only reporting patterns across hundreds of filings, which directly informed this implementation.

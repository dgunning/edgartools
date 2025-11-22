
# XBRL Mapping Files Analysis - mpreiss9 Contribution

**Date**: 2025-11-21
**Source**: GitHub Issue #494
**Contributor**: @mpreiss9
**Files**: custom_taxonomy_mapping.csv, gaap_taxonomy_mapping.csv
**Architecture**: `docs-internal/planning/architecture/xbrl-standardization-pipeline.md`

## Executive Summary

mpreiss9 shared production XBRL mapping files containing **6,177 mappings** refined over work with **390+ companies**. These files represent a goldmine of real-world standardization knowledge.

### Key Statistics

| Metric | Value |
|--------|-------|
| **Total mappings** | 6,177 |
| **GAAP mappings** | 2,343 |
| **Custom (company-specific)** | 3,834 |
| **Unique companies** | 390 CIKs |
| **Ambiguous tags** | 215 (9.2%) |
| **Current/NonCurrent ambiguities** | 202 (94% of ambiguous) |
| **Tags marked "DropThisItem"** | 276 |
| **Unique standard tags** | 129 |

## File Structure

### 1. GAAP Taxonomy Mapping (gaap_taxonomy_mapping.csv)

**Purpose**: Standard XBRL → Standardized tag mappings

**Format**:
```csv
xbrl_tag,std_tag,comments,deprecated
AccountsPayableCurrentAndNoncurrent,TradePayables:OtherOperatingNonCurrentLiabilities,Curr/NonCurr ambiguity,
```

**Key Features**:
- **2,343 mappings** covering standard GAAP taxonomy
- **Ambiguous tags** use `:` separator (e.g., `TagA:TagB`)
- **Comments** column explains ambiguity patterns
- **Deprecated** column flags outdated tags

### 2. Custom Taxonomy Mapping (custom_taxonomy_mapping.csv)

**Purpose**: Company-specific XBRL → Standardized tag mappings

**Format**:
```csv
cik,xbrl_tag,std_tag,comments
1800,AccruedAllOtherLiabilities,OtherNonOperatingCurrentLiabilities,
```

**Key Features**:
- **3,834 mappings** across 390 companies
- **CIK-based** (not ticker, for stability)
- Top company: CIK 40545 with 82 custom mappings
- Avg 9.8 mappings per company

## Ambiguity Analysis

### Pattern Breakdown

| Ambiguity Type | Count | % of Total |
|----------------|-------|-----------|
| **Curr/NonCurr** | 202 | 93.9% |
| **Assets/Liabilities** | 11 | 5.1% |
| **Both** | 1 | 0.5% |
| **Other** | 1 | 0.5% |

### Current/NonCurrent: The Core Challenge

**Problem**: Same XBRL tag can represent current OR non-current items depending on context.

**Examples**:
```
AccountsPayableCurrentAndNoncurrent
  → TradePayables (if current section)
  → OtherOperatingNonCurrentLiabilities (if non-current section)

AccountsReceivableNet
  → TradeReceivables (if current)
  → OtherOperatingNonCurrentAssets (if non-current)
```

**Resolution Strategy** (from mpreiss9's methodology):
1. Parse balance sheet to identify **section boundaries** (Assets, Liabilities, Equity)
2. Use **subtotals** as section markers
3. Apply **context-aware mapping** based on position
4. Validate with **Assets = Liabilities + Equity**

### Assets/Liabilities Ambiguity

**Examples**:
```
InterestAndDividendsPayableCurrentAndNoncurrent
  → CashAndMarketableSecurities (if asset)
  → OtherNonOperatingCurrentLiabilities (if liability)
```

## Standard Tag Distribution

### Top 15 Most-Used Standard Tags

| Standard Tag | Mappings | Category |
|-------------|----------|----------|
| DropThisItem | 276 | Special |
| NonoperatingIncomeExpense | 199 | Income Statement |
| CostOfGoodsAndServicesSold | 142 | Income Statement |
| OtherNonOperatingNonCurrentAssets | 140 | Balance Sheet |
| Revenue | 139 | Income Statement |
| OtherNonOperatingCurrentAssets | 131 | Balance Sheet |
| OtherNonOperatingCurrentLiabilities | 82 | Balance Sheet |
| OtherNonOperatingNonCurrentLiabilities | 81 | Balance Sheet |
| IncomeTaxes | 78 | Income Statement |
| LongTermDebt | 71 | Balance Sheet |

### "DropThisItem" Tags (276 total)

Tags deliberately excluded from standardization:
- EPS-related details (per-share amounts, pro-forma)
- Accelerated share repurchase specifics
- Antidilutive securities details
- Auction market preferred stock details

**Rationale** (from mpreiss9):
> "Some xbrl tags are deliberately mapped to DropThisItem, meaning I not only don't use the item, it would confuse my code if it got mapped."

## Company Coverage

### Top 10 Companies by Custom Mapping Count

| Rank | CIK | Mappings | Notes |
|------|-----|----------|-------|
| 1 | 40545 | 82 | Highest complexity |
| 2 | 1164727 | 67 | |
| 3 | 1398659 | 45 | |
| 4 | 1166691 | 43 | |
| 5 | 78003 | 40 | |
| 6 | 831259 | 37 | |
| 7 | 14272 | 34 | |
| 8 | 895126 | 33 | |
| 9 | 37785 | 32 | |
| 10 | 1099800 | 32 | |

**Distribution**: 390 companies, avg 9.8 custom mappings each

## Key Innovations in mpreiss9's Approach

### 1. Reverse Mapping Structure
- **XBRL tag as primary key** (unique, unchanging)
- **Multiple standard tags** per XBRL tag (context-dependent)
- **O(1) lookup** vs iteration

### 2. Colon Separator for Ambiguity
```csv
AccountsPayableCurrentAndNoncurrent,TradePayables:OtherOperatingNonCurrentLiabilities
```
- Easy to parse programmatically
- No multi-column complexity
- Self-documenting

**From mpreiss9's follow-up comment**:
> "I forgot to mention that in the mapping files, ambiguous standard tags are separated by a colon ':'. This is easy to identify and process programatically vs multiple columns in the csv."

### 3. Comprehensive Comments
- **7 distinct ambiguity patterns** documented
- Clear explanation of resolution strategy
- Aids debugging and validation

### 4. CIK-Based Company Mapping
- **Stable identifier** (ticker can change)
- Company-level customization
- Scales to 390+ companies

### 5. Footnote Integration
From mpreiss9:
> "Once my code has verified that I have an in balance primary statement, I look for footnotes or tree children of line items that add up to the primary item, and when found I swap in the footnote values."

Example:
- Primary: "Non-operating Income and Interest" (single line)
- Footnote breakdown: Interest Income + Interest Expense + Other
- **Swaps if sums match** for greater granularity

### 6. Flexible Mapping Philosophy: Two Reasons for Mapping

**Critical Insight** from mpreiss9's follow-up comment:

> "There are really two reasons to map an xbrl tag to a standard tag. The first reason is to take what is exactly the same kind of fact coded different ways into a common tag (for example the seemingly countless revenue tag flavors). The second reason is often overlooked but very important - a user may want to consolidate multiple kinds of facts into a single concept because the distinction is immaterial to them."

#### Reason 1: Standardization (Same Facts, Different Tags)
**Goal**: Normalize identical concepts with different XBRL names

**Example**: Revenue variations
```
us-gaap:Revenue                → "Revenue"
us-gaap:Revenues               → "Revenue"
us-gaap:SalesRevenueNet        → "Revenue"
us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax → "Revenue"
```

All represent the same concept, just coded differently across companies.

#### Reason 2: Consolidation (Different Facts, User's Choice)
**Goal**: Combine distinct concepts when granularity doesn't matter to the user

**Example**: Non-Operating Liabilities (mpreiss9's granular mapping)
```
us-gaap:TaxLiabilities          → "Tax Liabilities"
us-gaap:RetirementLiabilities   → "Retirement Liabilities"
us-gaap:OtherNonOperatingLiab   → "Other Non-Operating Liabilities"
```

**Alternative**: Another user's consolidated mapping
```
us-gaap:TaxLiabilities          → "Non-Operating Liabilities"
us-gaap:RetirementLiabilities   → "Non-Operating Liabilities"
us-gaap:OtherNonOperatingLiab   → "Non-Operating Liabilities"
```

Both are valid! The choice depends on the user's analytical needs.

#### Implications for EdgarTools

**Current Approach**: One "standard" mapping for all users
- Fixed granularity level
- EdgarTools decides the level of detail
- Users can't easily adjust

**Flexible Approach** (mpreiss9's insight):
- Users choose granularity based on their needs
- Some users want detailed breakdowns
- Others want high-level summaries
- Same data, different views

**Quote from mpreiss9**:
> "For example, I gave you a pretty granular mapping, distinguishing between tax liabilities, retirement liabilities and other non-operating liabilities. Another user might just collapse all those xbrl tags into a single non-operating liability tag. This is why a flexible mapping scheme is so important."

#### Design Considerations

**User Profiles** (suggested):
- **Detailed**: Maximum granularity (like mpreiss9's mappings)
- **Standard**: Balanced level of detail (EdgarTools default)
- **Summarized**: High-level consolidation (for overview analysis)

**Configurable Granularity**:
- Users should be able to define their own rollup rules
- CSV format supports easy customization
- Multiple mapping files for different use cases

**Hierarchical Mappings**:
- Define parent-child relationships
- Allow drill-down: "Non-Operating Liabilities" → Tax, Retirement, Other
- Allow roll-up: Multiple detailed tags → Single summary tag

## Value for EdgarTools

### Immediate Applications

**1. Balance Sheet Validation (edgartools-y3k)**
- Use as test data for Assets = Liabilities + Equity validation
- Verify section boundary detection
- Test rollup calculations

**2. Ambiguous Tag Catalog (edgartools-3yx)**
- 215 real-world ambiguous cases documented
- Resolution patterns identified
- Test coverage for edge cases

**3. Context-Aware Resolution**
- Proof that reverse mapping + context works in production
- 390 companies validated
- Current/NonCurrent pattern handles 94% of ambiguities

**4. Flexible Granularity Model** (Pipeline Stage 4)
- mpreiss9's mappings provide "detailed" profile example
- Shows how to support different analytical needs
- Template for user-configurable mapping levels
- Integrates with architecture as Stage 4: Granularity Transformation

### Future Enhancements

**1. Section Membership Dictionaries**
- Build from these mappings
- Assets vs Liabilities classification
- Current vs NonCurrent heuristics

**2. CSV Workflow Tools**
- Import/export utilities
- Excel-friendly editing
- Merge with EdgarTools standard mappings

**3. Enhanced Context Threading**
- Parent concept tracking
- Section position awareness
- Sign and value validation

**4. User-Configurable Granularity** (NEW from mpreiss9's insight - Pipeline Stage 4)
- **Mapping profiles**: Detailed, Standard, Summarized
- **Custom granularity settings**: Let users define rollup rules
- **Hierarchical mappings**: Support drill-down and roll-up
- **Use case templates**: Financial analyst, researcher, casual user
- **API design**: `xbrl.statements.balance_sheet(granularity='detailed')`
- **Architecture integration**: See Stage 4 in `xbrl-standardization-pipeline.md`
- **Three user levels**:
  - Level 1: Choose profile (`granularity='detailed'`)
  - Level 2: Custom profile file (`Profile.from_csv()`)
  - Level 3: Programmatic transformation (user owns logic)

## Technical Notes

### Mapping Logic

**Standard approach (current EdgarTools)**:
```python
standard_tag = mapping[xbrl_tag]  # 1:1 mapping
```

**mpreiss9 approach**:
```python
possible_tags = mapping[xbrl_tag].split(':')  # 1:N mapping
standard_tag = resolve_with_context(possible_tags, context)
```

### Context Structure

Based on mpreiss9's methodology:
```python
context = {
    'section': 'current_assets',  # or 'current_liabilities', etc.
    'parent': 'TotalCurrentAssets',
    'position': 5,  # Line number in statement
    'sign': 'debit',
    'value': 12500.00
}
```

### Balance Sheet Sections

```
ASSETS
  Current Assets
    Cash, Receivables, Inventory, etc.
    [Subtotal: CurrentAssets]
  Non-Current Assets
    PPE, Intangibles, LongTermInvestments, etc.
    [Subtotal: NoncurrentAssets]
  [Total: Assets]

LIABILITIES
  Current Liabilities
    Payables, ShortTermDebt, etc.
    [Subtotal: CurrentLiabilities]
  Non-Current Liabilities
    LongTermDebt, Pensions, etc.
    [Subtotal: NoncurrentLiabilities]
  [Total: Liabilities]

EQUITY
  [Total: StockholdersEquity]

VALIDATION: Assets = Liabilities + Equity
```

## Recommendations

### Phase 1: Integration (Immediate)
1. **Add to test fixtures**
   - Copy files to `tests/fixtures/xbrl-mappings/`
   - Use for validation test cases

2. **Document in advanced guide**
   - Reference as example of production usage
   - Show reverse mapping pattern

3. **Create comparison analysis**
   - EdgarTools mappings vs mpreiss9 mappings
   - Identify gaps and improvements

### Phase 2: Implementation (v4.31.0)
1. **Balance sheet validation**
   - Assets = Liabilities + Equity
   - Section total validation
   - Use these mappings for test data

2. **Section membership dictionaries**
   - Build from ambiguity comments
   - Current/NonCurrent classification
   - Assets/Liabilities classification

### Phase 3: Enhancement (v5.0.0)
1. **Context-aware disambiguation**
   - Implement colon-separated mapping support
   - Add context resolution logic
   - Validate with 215 ambiguous cases

2. **CSV import/export**
   - User-friendly mapping management
   - Merge capability
   - Company override support

## Questions for Community

1. **Privacy**: Can we include anonymized subset in test fixtures?
2. **Collaboration**: Interest in contributing to context-aware resolution?
3. **Priorities**: Which enhancement is most valuable?
   - Balance sheet validation
   - Ambiguous tag handling
   - CSV workflow tools

## Files

**Location**: `/data/xbrl-mappings/`
- `custom_taxonomy_mapping.csv` (294KB, 3,834 rows)
- `gaap_taxonomy_mapping.csv` (173KB, 2,343 rows)

**Git Status**: Not committed (data files, user contribution)

**Usage**: Test data, research, validation

## References

- **GitHub Issue**: #494 - Create documentation on how to customize standardization tagging
- **Architecture**: `docs-internal/planning/architecture/xbrl-standardization-pipeline.md`
- **Enhancement Roadmap**: `docs-internal/planning/future-enhancements/context-aware-standardization.md`
- **Epic**: edgartools-ocf - Context-Aware XBRL Standardization Enhancements
- **Related Issues**: edgartools-y3k, edgartools-3yx, edgartools-qcd
- **Documentation**: `docs/advanced/customizing-standardization.md`

### How This Fits in the Pipeline

mpreiss9's contributions integrate into the 7-stage XBRL processing pipeline:

- **Stage 3 (Base Standardization)**: CSV mappings show production-scale standardization
- **Stage 4 (Granularity)**: "Detailed" profile example - maximum granularity for advanced users
- **Stage 5 (Context Resolution)**: 215 ambiguous tags document what needs context-aware handling

See the complete pipeline architecture for how these pieces fit together.

---

**Analysis Date**: 2025-11-21
**Analyst**: Claude (EdgarTools AI Assistant)
**Status**: Complete - Ready for integration planning

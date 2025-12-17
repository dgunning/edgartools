# Financial Statement Concept Learning Guide

This guide documents the learning process for extracting financial statement presentation metadata from SEC filings.

## Overview

The learning pipeline analyzes SEC filings to discover:
1. Which concepts belong to which financial statements (Balance Sheet, Income Statement, etc.)
2. Parent-child relationships between concepts (hierarchical structure)
3. Concept occurrence rates across companies
4. Display labels and ordering

## Data Selection

The learning pipeline supports **flexible company and form selection**. The selection determines which filings are analyzed to learn concept patterns.

### Current Production Defaults

The most recent production run used:
- **Exchange**: NYSE only
- **Company count**: ~340 companies
- **Form**: 10-K (annual filings)
- **Time**: Latest available 10-K per company

### Configuring Company Selection

Use the `CompanySubset` API to customize which companies are included in learning:

```python
from edgar.reference.company_subsets import CompanySubset, PopularityTier

# Option 1: Exchange-based (current default)
companies = CompanySubset().from_exchange('NYSE').sample(500).get()

# Option 2: Multiple exchanges for broader coverage
companies = (CompanySubset()
    .from_exchange(['NYSE', 'Nasdaq'])
    .sample(600, random_state=42)
    .get())

# Option 3: Industry-specific learning
companies = (CompanySubset()
    .from_exchange('NYSE')
    .filter_by(lambda df: df['sic'].between(3500, 3700))  # Computer equipment
    .get())

# Option 4: Popular companies only (well-known, consistent filers)
companies = CompanySubset().from_popular(PopularityTier.MAINSTREAM).get()

# Option 5: Exclude financial sector (different statement structures)
companies = (CompanySubset()
    .from_exchange('NYSE')
    .exclude_tickers(['JPM', 'GS', 'C', 'BAC', 'WFC'])
    .filter_by(lambda df: ~df['name'].str.contains('bank|financial', case=False))
    .sample(400)
    .get())
```

### Company Selection Guidelines

| Goal | Recommended Selection | Expected Count | Notes |
|------|----------------------|----------------|-------|
| Initial learning | NYSE only | 300-400 | Good baseline coverage |
| Broad coverage | NYSE + NASDAQ | 500-700 | More diverse concepts |
| Industry-specific | SIC code filter | Variable | Specialized patterns |
| Financial sector | Bank/financial filter | 100-200 | Unique statement structures |
| Small sample test | Popular companies | 50-100 | Quick validation runs |

### Form Type Selection

| Form | Primary Use | Characteristics |
|------|-------------|-----------------|
| **10-K** (default) | Main learning set | Complete annual statements; canonical presentation |
| **10-Q** (optional) | Comparative analysis | Condensed quarterly; reveals annual-only concepts |

**Recommendation**: Use 10-K as the primary learning source. The 10-Q filings can be analyzed separately to identify:
- Concepts that only appear in annual reports
- Structural differences between quarterly and annual presentations
- Occurrence rate variations by form type

### Time Range

The default behavior uses the **latest available filing** per company. To specify a time range:

```python
# In learning script, filter filings by date
from datetime import date

filings = company.get_filings(form='10-K')
recent_filings = [f for f in filings if f.filing_date >= date(2023, 1, 1)]
```

## Running the Learning Pipeline

### Quick Start

```bash
# Run with default settings (100 NYSE companies)
python -m edgar.entity.training.run_learning

# Run with specific parameters
python -m edgar.entity.training.run_learning --companies 200 --exchange NYSE --output training/output

# Quick test run with 10 companies
python -m edgar.entity.training.run_learning --companies 10
```

### Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--companies` | 100 | Number of companies to process |
| `--exchange` | NYSE | Exchange to sample from (NYSE, Nasdaq, OTC) |
| `--output` | training/output | Output directory for generated files |
| `--min-occurrence` | 0.3 | Minimum occurrence rate threshold |
| `--random-state` | 42 | Random seed for reproducibility |

### Example Runs

```bash
# Production run: 500 NYSE companies
python -m edgar.entity.training.run_learning --companies 500 --exchange NYSE

# Broad coverage: Multiple exchanges
python -m edgar.entity.training.run_learning --companies 600 --exchange NYSE
# Note: Run separately for NASDAQ and combine results

# Quick validation
python -m edgar.entity.training.run_learning --companies 20 --min-occurrence 0.5
```

## Pipeline Steps

### Step 1: Concept Census

Extract all concepts from filings and count their frequency by statement type:
- Statement assignment (Balance Sheet, Income Statement, Cash Flow, etc.)
- Occurrence rate across companies
- Data type (monetary, shares, percentage)
- Natural balance (debit/credit)

### Step 2: Presentation Extraction

Parse XBRL presentation linkbases to extract:
- Parent-child hierarchies
- Display ordering
- Preferred labels
- Abstract vs. concrete concepts

### Step 3: Pattern Learning

Cluster similar presentation structures:
- Identify canonical patterns
- Build concept co-occurrence matrices
- Determine industry-specific variations

### Step 4: Output Generation

Generate production-ready files:
- `learned_mappings.json` - Concept-to-statement assignments
- `virtual_trees.json` - Hierarchical statement structures
- `canonical_structures.json` - Statistical analysis data

## Output Files

### learned_mappings.json

Maps concepts to their primary statement:

```json
{
  "Assets": "BalanceSheet",
  "Revenue": "IncomeStatement",
  "NetCashProvidedByOperatingActivities": "CashFlowStatement"
}
```

### virtual_trees.json

Defines hierarchical structure for each statement:

```json
{
  "BalanceSheet": {
    "statement_type": "BalanceSheet",
    "nodes": {
      "Assets": {
        "concept": "Assets",
        "label": "Total Assets",
        "parent": "AssetsAbstract",
        "depth": 1,
        "children": ["CurrentAssets", "NoncurrentAssets"]
      }
    },
    "roots": ["StatementOfFinancialPositionAbstract"],
    "sections": {...}
  }
}
```

### learning_summary.json

Metadata about the learning run:

```json
{
  "timestamp": "2025-08-13T15:38:56",
  "companies_processed": 337,
  "successful_companies": 337,
  "total_observations": 56193,
  "canonical_concepts": {
    "BalanceSheet": 40,
    "IncomeStatement": 21,
    "CashFlowStatement": 35
  },
  "multi_statement_concepts": 19,
  "linkage_concepts": 6,
  "errors": 0
}
```

### concept_linkages.json

Tracks concepts that appear in multiple financial statements (e.g., NetIncomeLoss appears in Income Statement, Cash Flow, Statement of Equity, and Comprehensive Income):

```json
{
  "metadata": {
    "total_unique_concepts": 486,
    "single_statement_concepts": 467,
    "multi_statement_concepts": 19,
    "linkage_concepts": 6
  },
  "summary": {
    "by_statement_count": {"2": 13, "3": 2, "4": 4},
    "key_linkages": ["NetIncomeLoss", "ProfitLoss", "StatementTable", ...]
  },
  "categories": {
    "income_to_cashflow": ["NetIncomeLoss", "DepreciationAndAmortization"],
    "balance_to_equity": ["StockholdersEquity", "CommonStockSharesOutstanding"],
    "balance_to_cashflow": ["CashAndCashEquivalentsAtCarryingValue"],
    "comprehensive_income": ["OtherComprehensiveIncomeLossNetOfTax"]
  },
  "multi_statement_concepts": [
    {
      "concept": "NetIncomeLoss",
      "statement_count": 4,
      "primary_statement": "IncomeStatement",
      "statements": ["IncomeStatement", "CashFlowStatement", "StatementOfEquity", "ComprehensiveIncome"],
      "statement_details": {
        "IncomeStatement": {"occurrence_rate": 0.88, "label": "Net Income", "parent": "..."},
        "CashFlowStatement": {"occurrence_rate": 0.85, "label": "Net Income", "parent": "..."}
      }
    }
  ]
}
```

**Linkage Categories:**
- `income_to_cashflow`: Net income flows from IS to CF (e.g., NetIncomeLoss, Depreciation)
- `balance_to_equity`: Equity items linking BS and Statement of Equity
- `balance_to_cashflow`: Cash reconciliation between BS and CF
- `comprehensive_income`: OCI items linking IS and Comprehensive Income
- `xbrl_structural`: XBRL scaffolding elements (StatementTable, StatementLineItems)

### learning_statistics.json

Comprehensive statistics about the learning run including coverage analysis and outlier detection:

```json
{
  "data_summary": {
    "companies_processed": 500,
    "companies_successful": 485,
    "success_rate": 0.97,
    "total_observations": 125000,
    "avg_processing_time_ms": 850.5
  },
  "concept_counts": {
    "total_unique_concepts": 1250,
    "standard_concepts": 980,
    "custom_concepts": 270,
    "custom_rate": 0.216,
    "canonical_concepts": 450,
    "canonical_rate": 0.36,
    "filtered_out": 800
  },
  "per_company_stats": {
    "concepts": {"min": 85, "max": 350, "mean": 180, "median": 165, "stdev": 45},
    "coverage": {"min": 0.55, "max": 0.95, "mean": 0.72, "median": 0.70}
  },
  "outliers": {
    "high_concept_count": [{"ticker": "JPM", "total_concepts": 350, "deviation": 3.8}],
    "high_custom_rate": [{"ticker": "GS", "custom_rate": 0.35, "custom_concepts": 85}],
    "low_coverage": [{"ticker": "XYZ", "coverage_rate": 0.45, "total_concepts": 220}]
  },
  "custom_concepts_by_company": {
    "jpm": {"count": 45, "examples": ["jpm_TradingAssets", "jpm_Loans", ...]},
    "gs": {"count": 38, "examples": ["gs_InvestmentBanking", ...]}
  },
  "company_details": [
    {"ticker": "AAPL", "total_concepts": 133, "canonical_covered": 95, "coverage_rate": 0.71, "custom_rate": 0.15}
  ]
}
```

**Key Statistics:**
- `concept_counts.canonical_rate`: What percentage of all concepts made it to canonical output
- `per_company_stats.coverage`: How well canonical covers each company's concepts
- `outliers`: Companies that deviate significantly from the norm
- `custom_concepts_by_company`: Which companies use the most custom concepts

## Deployment

After a successful learning run, deploy outputs to the library:

```bash
# Using the deploy script (recommended)
python -m edgar.entity.training.deploy --canonical

# Or manually copy files
cp training/output/learned_mappings.json edgar/entity/data/
cp training/output/virtual_trees.json edgar/entity/data/
```

## Quality Thresholds

### Occurrence Rate Filtering

Concepts are included based on occurrence rate (how many companies use them):

| Threshold | Use Case |
|-----------|----------|
| 30% (default) | Balance between coverage and noise filtering |
| 50% | Stricter; only very common concepts |
| 20% | More inclusive; may include some noise |

### Validation Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Hierarchy accuracy | >90% | Learned structure matches XBRL presentation |
| Concept coverage | >95% | Concepts in output vs. concepts in filings |
| Label accuracy | >95% | Learned labels match XBRL labels |

## Troubleshooting

### Missing Concepts

If expected concepts don't appear in outputs:
1. Check occurrence rate threshold (lower if needed)
2. Verify concept exists in source filings
3. Check for concept name variations (synonyms)

### Statement Misassignment

If concepts appear in wrong statements:
1. Review source filing presentation linkbases
2. Check for ambiguous concepts used in multiple statements
3. Consider industry-specific patterns

### Empty Output

If learning produces no results:
1. Verify company selection returns companies
2. Check network connectivity for filing downloads
3. Review error logs for XBRL parsing failures

## Canonical vs Per-Company Data

This learning pipeline builds **canonical** (common) concept mappings. There's a tradeoff:

| Approach | Coverage | Storage | Build Time |
|----------|----------|---------|------------|
| **Canonical** (this guide) | ~40% of concepts | ~few MB | ~1 hour |
| **Per-Company** | ~100% of concepts | 100-200 MB | 10-20 hours |

### The Coverage Gap

From analysis of 10 companies:
- Total unique concepts observed: **486**
- Canonical concepts (≥30% occurrence): **198** (40.7%)
- Per-company loss (e.g., AAPL): **~33%** of concepts not in canonical set

### When to Use Each

**Canonical (this pipeline)**:
- Rendering statements for most companies with reasonable coverage
- EdgarTools library default behavior
- Quick to build and deploy

**Per-Company**:
- Rendering statements with full company-specific structure
- No concept loss for any company
- Requires larger infrastructure

For per-company presentation metadata, see [PER_COMPANY_DATABASE_GUIDE.md](./PER_COMPANY_DATABASE_GUIDE.md).

## Related Documentation

- [Per-Company Database Guide](./PER_COMPANY_DATABASE_GUIDE.md) - Building company-specific presentation metadata
- [Company Subsets](../../docs/company-subsets.md) - Full CompanySubset API documentation
- [XBRL Processing](../../docs/xbrl-guide.md) - How EdgarTools parses XBRL data

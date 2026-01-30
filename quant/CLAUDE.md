# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Quant Package

**Advanced quantitative extensions for EdgarTools** - Trailing Twelve Months (TTM) calculations, stock split adjustments, XBRL standardization, and markdown extraction.

## Architecture

The quant package follows the **Soft Fork Protocol**: it extends `edgar/` functionality WITHOUT modifying core library files. All enhancements are implemented through:

- **Inheritance**: `QuantCompany` extends `Company`
- **Composition**: Wrapper classes around `EntityFacts`
- **Pure extension**: New capabilities layered on top of existing APIs

Read `xbrl_standardize/SOFT_FORK_COMPLIANCE_SUMMARY.md` for full protocol details.

## Package Structure

```
quant/
├── core.py                    # QuantCompany - main entry point
├── utils.py                   # TTM calculations, split detection
├── entity_facts_wrapper.py    # QuantEntityFacts wrapper
│
├── markdown/                  # Filing document markdown extraction
│   ├── extraction.py          # Core extraction logic
│   ├── adapters.py           # Integration with edgar.documents
│   ├── boundaries.py         # Section boundary detection
│   ├── helpers.py            # Utility functions
│   ├── metadata.py           # Section metadata
│   └── types.py              # Type definitions
│
├── xbrl_standardize/         # XBRL concept mapping system
│   ├── schemas/              # Financial statement schemas (3 files)
│   │   ├── income-statement.json
│   │   ├── balance-sheet.json
│   │   └── cash-flow.json
│   ├── extractors/           # Schema-based extractors (is.py, bs.py, cf.py)
│   ├── tools/                # Mapping tools (build, analyze, apply)
│   ├── ml_data/              # ML-learned concept mappings (36 files)
│   ├── ml_training/          # ML training pipeline
│   ├── overlays/             # Sector-specific overrides (banking, insurance, utilities)
│   └── tests/                # Validation tests
│
└── tests/                    # Unit tests for quant package
    ├── test_utils.py         # TTM calculator tests
    └── test_markdown.py      # Markdown extraction tests
```

## Usage Examples

### QuantCompany - Enhanced Company Object

```python
from quant import QuantCompany

# Create enhanced company object (drop-in replacement for edgar.Company)
company = QuantCompany("AAPL")

# Get TTM (Trailing Twelve Months) financials
ttm_income = company.income_statement(period='ttm')
ttm_revenue = company.get_ttm_revenue()
ttm_net_income = company.get_ttm_net_income()

# Get quarterly data with automatic Q4 derivation
quarterly_income = company.income_statement(period='quarterly', periods=8)

# Stock splits are automatically detected and adjusted
# Quarterly data is automatically derived when Q4 is missing
```

### TTM Calculations

```python
from quant.utils import TTMCalculator, TTMMetric
from edgar import Company

# Get facts from edgar Company
company = Company("MSFT")
facts = company.facts._facts

# Calculate TTM for any concept
revenue_facts = [f for f in facts if f.concept == 'us-gaap:Revenues']
calc = TTMCalculator(revenue_facts)
ttm = calc.calculate_ttm()

print(f"TTM Revenue: ${ttm.value / 1e9:.1f}B as of {ttm.as_of_date}")
print(f"Periods: {ttm.periods}")
print(f"Has gaps: {ttm.has_gaps}")
print(f"Q4 calculated: {ttm.has_calculated_q4}")
```

### XBRL Standardization

```python
from quant.xbrl_standardize.tools.apply_mappings import (
    extract_income_statement,
    extract_with_auto_sector,
    validate_extraction
)

# Extract standardized fields from XBRL facts
facts = {
    'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax': 100000000,
    'us-gaap:NetIncomeLoss': 20000000,
    'us-gaap:EarningsPerShareBasic': 2.50
}

result = extract_income_statement(facts)
print(result['data']['revenue'])  # 100000000

# Auto-detect sector and apply sector-specific mappings
result = extract_with_auto_sector(facts, sic=6021)  # Commercial bank
print(result['sector'])  # 'banking'

# Validate extraction quality
validation = validate_extraction(result, required_fields=['revenue', 'netIncome'])
print(f"Extraction rate: {validation['extraction_rate']:.1%}")
```

### Markdown Extraction

```python
from quant.markdown import extract_markdown, extract_sections, get_available_sections

from edgar import Company, Filing

# Get filing
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest(1)

# Extract all sections as markdown
markdown_content = extract_markdown(filing)

# Extract specific sections
sections = extract_sections(filing, ["1", "1A", "7"])
for section in sections:
    print(f"{section.section_id}: {section.title}")
    print(section.content)

# List available sections
available = get_available_sections(filing)
print(available)  # ['1', '1A', '1B', '2', '7', '7A', ...]
```

## Testing

### Running Quant Tests

```bash
# Run quant package tests
cd quant
pytest tests/

# Run specific test file
pytest tests/test_utils.py -v

# Run with coverage
pytest tests/ --cov=quant --cov-report=term-missing
```

### Running XBRL Standardization Tests

```bash
# Integration tests
cd quant/xbrl_standardize
python tests/extract_financials.py --symbol AAPL --form 10-K

# Real company validation (requires network)
python tests/fetch_fresh_nasdaq.py

# Unit tests for mapping system
python -m pytest tests/ -v
```

### Test Markers

Tests use pytest markers for categorization:
- `fast` - No network calls, runs in <1s
- `network` - Requires SEC Edgar access
- `slow` - Long-running tests (>10s)

## Development Workflow

### Adding New Features to QuantCompany

1. **Read edgar/ implementation first** - Understand existing patterns
2. **Extend, don't modify** - Use inheritance or composition
3. **Add to core.py** - Implement new methods in `QuantCompany`
4. **Update utils.py** - Add supporting calculations if needed
5. **Write tests** - Add to `tests/test_utils.py`
6. **Update __init__.py** - Export new public APIs

### Working with XBRL Standardization

1. **Understanding the System**:
   - `schemas/` - JSON schemas define standardized field mappings
   - `extractors/` - Python scripts extract fields using schemas
   - `ml_data/` - ML-learned concept mappings (trained on 500+ companies)
   - `tools/` - Build, analyze, and apply mapping tools

2. **Common Tasks**:
   ```bash
   # Extract financials for a company
   cd xbrl_standardize/extractors
   python is.py --symbol AAPL --form 10-K

   # Analyze mapping quality
   cd ../tools
   python analyze_mappings.py

   # Rebuild schemas after ML updates
   python build_map_schema.py --trees ../ml_data/virtual_trees_merged.json
   ```

3. **Adding New Financial Fields**:
   - Edit schema in `schemas/income-statement.json` (or bs/cf)
   - Add concept mappings with fallbacks
   - Run `tools/validate_config.py` to check schema
   - Test extraction with `extractors/is.py`

4. **Sector-Specific Mappings**:
   - Industry-specific overrides in `overlays/banking.json`, `insurance.json`, `utilities.json`
   - Auto-detection based on SIC codes
   - Higher confidence for sector-specific concepts

### ML Training Pipeline

```bash
# Location: xbrl_standardize/ml_training/
cd xbrl_standardize/ml_training

# Basic training (uses original edgar script)
PYTHONPATH=/path/to/edgartools python run_learning.py --global --companies 300

# Enhanced training (apply patch first)
git apply run_learning_enhancements.patch
PYTHONPATH=/path/to/edgartools python run_learning.py --sector banking --tag banking
git restore ../../edgar/entity/training/run_learning.py  # Clean up

# Output goes to ../ml_data/
```

See `ml_training/README.md` for detailed training instructions.

## Important Files

| File | Purpose | Size |
|------|---------|------|
| `core.py` | QuantCompany implementation | 12KB |
| `utils.py` | TTM calculations, split detection | 62KB |
| `entity_facts_wrapper.py` | QuantEntityFacts wrapper | 3KB |
| `xbrl_standardize/README.md` | Full XBRL system documentation | 16KB |
| `xbrl_standardize/SOFT_FORK_COMPLIANCE_SUMMARY.md` | Architecture compliance | 12KB |

## Key Concepts

### TTM (Trailing Twelve Months)

Aggregates 4 consecutive quarters to smooth seasonal variations:
- **Q4 Derivation**: Calculates Q4 = FY - (Q1 + Q2 + Q3) when Q4 missing
- **Gap Detection**: Warns when quarters aren't consecutive
- **Split Adjustment**: Automatically adjusts for stock splits
- **Multiple Metrics**: Revenue, net income, EPS, cash flow, etc.

### Stock Split Detection

Automatically detects and adjusts for stock splits:
- Analyzes share count discontinuities
- Adjusts per-share metrics (EPS, book value)
- Preserves original data in metadata
- Applied to all QuantCompany methods

### XBRL Concept Mapping

Maps 1000+ XBRL concepts to ~20 standardized fields:
- **Primary + Fallbacks**: Each field has multiple concept options
- **ML-Learned**: Mappings trained on 500+ companies
- **Sector-Aware**: Banking/insurance/utilities get custom mappings
- **High Coverage**: 90%+ field extraction rate

### Markdown Extraction

Converts SEC HTML filings to clean markdown:
- **Section Detection**: Automatically identifies filing sections
- **Table Preservation**: Maintains table structure
- **Clean Output**: Removes SEC headers, navigation
- **Flexible API**: Extract all sections or select specific ones

## Dependencies

Quant extends but does not modify:
- `edgar/` - Core EdgarTools library (read-only dependency)
- `edgar.entity.models.FinancialFact` - Fact data model
- `edgar.entity.enhanced_statement.EnhancedStatementBuilder` - Statement builder
- `edgar.Company` - Base company class (extended by QuantCompany)

Install edgartools:
```bash
pip install edgartools
# or for development:
pip install -e /path/to/edgartools
```

## Troubleshooting

### TTM Calculation Issues

**Problem**: TTM value seems incorrect

**Solutions**:
1. Check `ttm.has_gaps` - gaps in quarters may cause inaccuracies
2. Check `ttm.has_calculated_q4` - derived Q4 may be wrong if FY includes adjustments
3. Verify fiscal year alignment - some companies have non-standard fiscal years
4. Examine `ttm.period_facts` - inspect the actual facts used

### XBRL Extraction Low Rate

**Problem**: `extraction_rate` < 30%

**Solutions**:
1. Check concept name format: `us-gaap:` vs `us-gaap_` prefix
2. Try sector-specific extraction if company is bank/insurance/utility
3. Review `result['metadata']` to see attempted concepts
4. Add custom fallback concepts to schema

### Soft Fork Violations

If you modify `edgar/` core files:
1. **STOP** - Core library is read-only
2. Move changes to `quant/` package
3. Use inheritance or composition patterns
4. See `SOFT_FORK_COMPLIANCE_SUMMARY.md` for examples

## Philosophy

- **Extend, don't modify**: Never change edgar/ core files
- **ML-powered**: Learn from real company data, not manual rules
- **Sector-aware**: Banking ≠ Technology ≠ Insurance
- **Fallback chains**: Multiple ways to extract each field
- **Data quality**: Warn users about gaps, derivations, adjustments

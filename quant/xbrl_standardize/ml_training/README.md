# ML Training for XBRL Standardization

**Purpose**: Train machine learning models to discover canonical XBRL concepts from real company filings.

**Source**: Copied from `edgar/entity/training/run_learning.py` (reference only, not modified)

**Enhancements**: Available as `run_learning_enhancements.patch` (422 lines) - apply temporarily for advanced features, then revert for soft fork compliance

---

## Overview

This script analyzes 300+ companies across different sectors to learn:
- Most common XBRL concepts for each financial statement line item
- Industry-specific concept patterns (banking, insurance, utilities)
- Concept occurrence rates and hierarchies
- Canonical structures for balance sheet, income statement, cash flow

---

## Usage

### Option 1: Basic Training (Original Script)

Uses the original edgar repo script (read-only, no modifications):

```bash
cd /c/edgartools_git/quant/xbrl_standardize/ml_training
PYTHONPATH=/c/edgartools_git python run_learning.py --companies 300
```

**Limitations**:
- No multi-exchange support
- No sector-specific filtering
- No output file tagging
- Basic company selection only

**Output**: `../ml_data/learned_mappings.json`, `canonical_structures.json`, etc.

---

### Option 2: Enhanced Training (With Patch)

Uses temporary patch with advanced features (soft fork compliant):

#### Step 1: Apply Enhancements Patch

```bash
cd /c/edgartools_git
git apply quant/xbrl_standardize/ml_training/run_learning_enhancements.patch
```

**Enhancements Added**:
- ✅ Multi-exchange selection (NYSE, Nasdaq, etc.)
- ✅ Sector-specific filtering using CIK_CODES.csv
- ✅ Output file tagging for organization
- ✅ Enhanced company discovery methods

#### Step 2: Run Training with Enhanced Features

```bash
cd /c/edgartools_git/quant/xbrl_standardize/ml_training

# Global multi-exchange training
PYTHONPATH=/c/edgartools_git python run_learning.py --exchanges NYSE,Nasdaq --companies 500 --tag global

# Sector-specific training
PYTHONPATH=/c/edgartools_git python run_learning.py --sector financials_banking --companies 150 --tag banking
PYTHONPATH=/c/edgartools_git python run_learning.py --sector financials_insurance --companies 150 --tag insurance
PYTHONPATH=/c/edgartools_git python run_learning.py --sector utilities --companies 100 --tag utilities
```

**Outputs**: `../ml_data/canonical_structures_banking.json`, `learned_mappings_global.json`, etc.

#### Step 3: Revert Patch

```bash
cd /c/edgartools_git
git restore edgar/entity/training/run_learning.py
```

**Why Revert**: Maintains soft fork compliance (no edgar repo modifications)

---

### Comparison: Basic vs Enhanced

| Feature | Basic (Option 1) | Enhanced (Option 2) |
|---------|------------------|---------------------|
| Company selection | Manual ticker list | Multi-exchange, sector filters |
| Output organization | Single set of files | Tagged files (global, banking, etc.) |
| Sector discovery | Manual | Automatic via CIK_CODES.csv |
| Speed | Slow (scan all filings) | Fast (CSV index lookup) |
| Edgar repo compliance | ✅ Clean | ✅ Clean (patch applied temporarily) |

**Recommendation**: Use Option 2 (patch) for production ML training, then revert to maintain clean edgar repo.

---

## Output Files

All outputs are saved to `../ml_data/`:

| File Pattern | Description |
|--------------|-------------|
| `canonical_structures_{sector}.json` | Statement hierarchies with is_total flags, occurrence rates |
| `learned_mappings_{sector}.json` | Concept metadata and confidence scores |
| `learning_statistics_{sector}.json` | Usage statistics and co-occurrence |
| `concept_linkages_{sector}.json` | Cross-statement concept relationships |
| `statement_mappings_v1_{sector}.json` | ML-generated field mappings |
| `learning_summary_{sector}.json` | Training run metadata |

---

## Configuration

### Modify Company Selection

Edit `run_learning.py` to change company filters:

```python
# Example: Filter by market cap
companies = get_companies_by_market_cap(min_market_cap=1000000000)

# Example: Filter by SIC codes
companies = get_companies_by_sic(sic_range=(6000, 6999))  # Banking

# Example: Specific ticker list
companies = ['AAPL', 'MSFT', 'GOOGL', 'JPM', 'BAC']
```

### Adjust Thresholds

```python
# Minimum occurrence rate to include concept
MIN_OCCURRENCE_RATE = 0.10  # 10% of companies

# Confidence levels
HIGH_CONFIDENCE = 0.30   # 30%+ occurrence
MEDIUM_CONFIDENCE = 0.20  # 20-30%
LOW_CONFIDENCE = 0.10     # 10-20%
```

---

## Dependencies

**External Package**: `edgar`
- Script uses `from edgar import Company, set_identity`
- Edgar package must be installed/available in PYTHONPATH
- No modification to edgar repo required (read-only usage)

**Python Packages**:
```
pandas
numpy
json
pathlib
```

---

## Workflow Integration

After training, rebuild schemas:

```bash
cd ../tools

# Merge global + sector trees
python merge_virtual_trees.py --input-dir ../ml_data

# Build schemas from merged trees
python build_map_schema.py --trees ../ml_data/virtual_trees_merged.json

# Analyze quality
python analyze_mappings.py --core ../schemas/income-statement.json

# Run audit
python audit_mapping_with_ml.py --mapping ../schemas/balance-sheet.json --ml-data ../ml_data --sector banking
```

---

## Output Example

**canonical_structures_banking.json**:
```json
{
  "BalanceSheet": [
    {
      "concept": "CashAndDueFromBanks",
      "label": "Cash and due from banks",
      "occurrence_rate": 0.732,
      "company_count": 93,
      "is_total": false,
      "avg_depth": 3.3,
      "parent": "AssetsAbstract"
    },
    {
      "concept": "CashAndCashEquivalentsAtCarryingValue",
      "label": "Cash and Cash Equivalents",
      "occurrence_rate": 0.425,
      "company_count": 54,
      "is_total": true,
      "avg_depth": 3.1,
      "parent": "AssetsAbstract"
    }
  ]
}
```

**Key Fields**:
- `is_total`: Identifies aggregate/total concepts vs components
- `occurrence_rate`: Percentage of companies using this concept
- `avg_depth`: Presentation hierarchy depth (lower = parent/aggregate)

---

## Troubleshooting

### ImportError: No module named 'edgar'

**Solution**: Set PYTHONPATH to edgar repo root:
```bash
export PYTHONPATH=/c/edgartools_git:$PYTHONPATH
python run_learning.py --global
```

### Rate Limiting (SEC)

**Problem**: Script fails with HTTP 429 errors

**Solution**: Reduce parallelism or add delays:
```python
# In run_learning.py
MAX_WORKERS = 2  # Reduce from 10
DELAY_BETWEEN_REQUESTS = 1.0  # Add 1s delay
```

### Missing Filings

**Problem**: Some companies return no data

**Solution**: Check filing availability:
```python
from edgar import Company
company = Company('TICKER')
filings = company.get_filings(form='10-K')
print(f"Found {len(filings)} 10-K filings")
```

---

## Best Practices

1. **Start Small**: Test with 10-20 companies before full run
2. **Backup Data**: Save ml_data/ before retraining
3. **Version Control**: Tag ml_data/ with training date
4. **Incremental Updates**: Add new companies, don't retrain from scratch
5. **Validate Output**: Check occurrence rates make sense

---

## Maintenance

### Retraining Schedule

- **Quarterly**: Add new companies from recent IPOs
- **Annually**: Full retrain with updated company universe
- **Ad-hoc**: When new XBRL taxonomy released

### Quality Checks

After training, verify:
- Occurrence rates > 10% for high-confidence concepts
- is_total flags correct (check aggregate vs component)
- No duplicate concepts in same statement
- Sector-specific patterns different from global

---

## Patch File Details

**File**: `run_learning_enhancements.patch` (422 lines)

**Enhancements Included**:
1. `generate_outputs()` - Added `tag` parameter for output file naming
2. `get_companies_multi_exchange()` - Select companies across multiple exchanges (NYSE, Nasdaq)
3. `get_companies_by_sector()` - Fast sector filtering using `../CIK_CODES.csv` index (~3 hours → <1 second)
4. CLI arguments: `--exchanges`, `--sector`, `--tag`

**Compliance Strategy**: Apply patch temporarily for training, revert immediately after to keep edgar repo clean.

---

**Last Updated**: 2026-01-02
**Script Source**: `edgar/entity/training/run_learning.py` (read-only reference)
**Patch File**: `run_learning_enhancements.patch` (optional, temporary application)
**Output Location**: `../ml_data/` (inside quant folder, soft fork compliant)
**Edgar Repo Status**: ✅ Clean (no modifications)

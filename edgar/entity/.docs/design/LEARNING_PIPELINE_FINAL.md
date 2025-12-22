# Learning Pipeline - Final Documentation

## ✅ Current Status
The learning pipeline is **fully integrated and working**. No manual post-processing needed.

## Complete Workflow

### 1. Run Learning Pipeline
```bash
cd /path/to/edgartools
python gists/analysis/structural_learning_with_subsets.py
```

Configuration in the script:
- `scenario_name = 'production'` - Uses 500 NYSE+NASDAQ companies
- `min_occurrence_rate = 0.3` - 30% threshold (works well)
- `min_companies = 5` - Minimum companies for concept inclusion

### 2. Generated Files
The pipeline creates these production-ready files in `output/structural_learning/`:

| File | Purpose | Format |
|------|---------|--------|
| `learned_mappings.json` | Concept-to-statement mappings | Direct mappings dictionary |
| `statement_mappings_v1.json` | Same mappings with metadata | Wrapped with version info |
| `virtual_trees_production.json` | Hierarchical statement structures | Full tree with nodes, roots, sections |
| `canonical_structures.json` | Raw learning output | Statistical analysis data |
| `DEPLOYMENT_INSTRUCTIONS.md` | Copy commands | Ready-to-use bash commands |

### 3. Deploy to Production
```bash
# From project root
cp output/structural_learning/learned_mappings.json edgar/entity/data/
cp output/structural_learning/statement_mappings_v1.json edgar/entity/data/
cp output/structural_learning/virtual_trees_production.json edgar/entity/data/virtual_trees.json
```

**IMPORTANT**: The virtual trees file is renamed from `virtual_trees_production.json` to `virtual_trees.json`

### 4. Verify Deployment
```python
from edgar import Company

# Test with AAPL
company = Company("AAPL")
facts = company.get_facts()

# Check statements
income = facts.income_statement()
balance = facts.balance_sheet()
cash_flow = facts.cash_flow()

print(f"Income: {income.shape if income else 'None'}")
print(f"Balance: {balance.shape if balance else 'None'}")
print(f"Cash Flow: {cash_flow.shape if cash_flow else 'None'}")
```

## Key Changes Made

### 1. Integrated `generate_production_files()`
The method now generates all production files directly, eliminating the need for `process_mappings.py`.

### 2. Fixed Virtual Trees Format
Changed from:
```python
virtual_trees[stmt_type] = tree['nodes']  # Wrong - only nodes
```
To:
```python
virtual_trees[stmt_type] = tree  # Correct - full tree structure
```

The full tree structure includes:
- `statement_type`: Name of the statement
- `nodes`: Dictionary of all concepts
- `roots`: List of root concept names
- `sections`: Dictionary grouping concepts by section

### 3. No Manual Processing
The old `edgar/entity/data/process_mappings.py` is **no longer needed**. Everything is handled in the main learning pipeline.

## Working Parameters

### Current Production Settings (133 companies)
- Generated **120 concepts** with good AAPL coverage
- Training set: NYSE companies
- Threshold: 30% occurrence rate

### Test Results
- **FAANG test** (5 companies): Generated 132 concepts, AAPL works
- **Production** (133 companies): Generated 120 concepts, AAPL works

## Important Notes

1. **Don't change the 30% threshold** - It filters noise while keeping useful concepts
2. **Virtual trees must have full structure** - Not just nodes
3. **AAPL uses standard GAAP concepts** - Not custom ones like "ProductSales"
4. **Small training sets work** - Even 5 companies generate useful mappings

## Troubleshooting

### If AAPL concepts disappear:
1. Check virtual_trees.json has the full structure (statement_type, nodes, roots, sections)
2. Verify learned_mappings.json has 100+ concepts
3. Ensure statement_mappings_v1.json matches learned_mappings.json content

### To rollback:
```bash
# Keep backups before deploying
cp edgar/entity/data/*.json backup/
# Deploy new files
# If issues, restore:
cp backup/*.json edgar/entity/data/
```

## Summary
The learning pipeline is **production-ready**. It generates all necessary files in the correct format. Just run, copy, and verify. No manual processing needed.
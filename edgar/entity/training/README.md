# Financial Statement Concept Learning

This folder contains the learning pipeline for extracting presentation metadata from SEC filings. The learning process discovers which financial concepts belong to which statements and how they're structured.

## What It Does

The learning pipeline analyzes 10-K/10-Q filings to learn:
- **Concept-to-statement mappings** - Which concepts appear in which financial statements
- **Hierarchical structures** - Parent-child relationships between concepts
- **Occurrence rates** - How commonly each concept is used across companies

## Quick Start

```bash
# Run with default settings (100 NYSE companies)
python -m edgar.entity.training.run_learning

# Quick test with 10 companies
python -m edgar.entity.training.run_learning --companies 10

# Production run
python -m edgar.entity.training.run_learning --companies 500 --exchange NYSE
```

See [GUIDE.md](GUIDE.md) for detailed documentation on:
- Configuring company and form selection
- Running the learning pipeline
- Understanding and using outputs

## Package Structure

```
edgar/entity/training/
├── __init__.py               # Package configuration
├── README.md                 # This file
├── GUIDE.md                  # Detailed learning guide
├── PER_COMPANY_DATABASE_GUIDE.md  # Per-company database spec
├── run_learning.py           # Canonical learning script
├── run_industry_learning.py  # Industry-specific learning
├── deploy.py                 # Deploy learnings to entity data
└── view.py                   # View learning results

training/output/              # Generated outputs (gitignored)
```

## Output Files

The learning pipeline generates these files in `output/`:

| File | Purpose |
|------|---------|
| `learned_mappings.json` | Concept-to-statement mappings |
| `virtual_trees.json` | Hierarchical statement structures |
| `canonical_structures.json` | Statistical analysis data |
| `concept_linkages.json` | Multi-statement concept tracking |
| `learning_summary.json` | Run metadata and statistics |
| `learning_statistics.json` | Comprehensive stats, coverage, outliers |

**Key insight:** `concept_linkages.json` tracks concepts that appear in multiple statements (e.g., `NetIncomeLoss` appears in Income Statement, Cash Flow, Statement of Equity, and Comprehensive Income). This reveals how financial statements are interconnected.

These outputs are deployed to `edgar/entity/data/` for use by the library.

## Related Documentation

- [Company Subsets](../../docs/company-subsets.md) - CompanySubset API for flexible company selection

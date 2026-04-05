---
name: sp500-multiperiod-test
description: "Run S&P25/S&P50 multi-period E2E validation to verify XBRL concept mappings against yfinance. Use after modifying metrics.yaml, industry_logic, or reference_validator."
---

# S&P500 Multi-Period E2E Test

## When to Use This Skill

- After modifying `metrics.yaml` (new concepts, changed mappings)
- After updating `reference_validator.py` (composite logic, industry extractors)
- After adding company-specific overrides in `company_mappings/`
- To verify overall system health before releases

## How to Run

From the project root:

```bash
// turbo
python sandbox/notes/007_sp500_multiperiod_test/run_e2e.py --help
```

**Common commands:**

```bash
# Quick test (S&P25, default 8 workers)
// turbo
python sandbox/notes/007_sp500_multiperiod_test/run_e2e.py --group sp25

# Full test (S&P50, default 8 workers)
// turbo
python sandbox/notes/007_sp500_multiperiod_test/run_e2e.py --group sp50
```

## Understanding Outputs

Reports are written to `sandbox/notes/007_sp500_multiperiod_test/reports/`:

1. **`e2e_YYYY-MM-DD.json`**: Detailed failure log with:
   - Ticker, form, filing date, accession number
   - XBRL value vs reference value, variance %
   - Mapping source, concept used, industry
   - Suggested actions for fixing

2. **`e2e_YYYY-MM-DD.md`**: Summary with:
   - Pass rates table (S&P25 vs S&P50)
   - Top 10 failing metrics
   - Top 10 failing companies

## Suggested Actions Reference

When reviewing failures, use these patterns to fix issues:

| Failure Pattern | Suggested Action |
|-----------------|------------------|
| High variance (>50%) + composite | Edit `COMPOSITE_METRICS` in `reference_validator.py` |
| Banking/Financial metric | Check dual-track logic in `industry_logic/__init__.py` |
| Alternative concept available | Add to `known_concepts` in `metrics.yaml` |
| Dimension mismatch | Review segment filtering in `tree_parser.py` |
| No mapping found | Add concept to `metrics.yaml` known_concepts |

## After Running

1. Review the markdown summary for high-level trends
2. Check the JSON file for specific failures to fix
3. Update `progress_tracker.md` with new pass rates

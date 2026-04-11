# S&P500 Multi-Period E2E Test

Parallel validation of XBRL concept mappings against yfinance for S&P25/S&P50 companies.

## Features

- **Parallel processing** via multiprocessing (configurable workers)
- **Multi-period coverage**: 5 years 10-K + 6 quarters 10-Q
- **Detailed failure logs**: JSON with full debugging context
- **Summary reports**: Markdown with top failures and pass rates

## Usage

```bash
# Quick test (S&P25)
python run_e2e.py --group sp25 --workers 4

# Full test (S&P50)
python run_e2e.py --group sp50 --workers 8

# Custom periods
python run_e2e.py --group sp25 --years 3 --quarters 4
```

## Output

Reports go to `reports/`:
- `e2e_YYYY-MM-DD.json` - Detailed failures
- `e2e_YYYY-MM-DD.md` - Summary

## See Also

- Agent skill: `.agent/skills/sp500-multiperiod-test/SKILL.md`
- Progress tracker: `../005_calculation_tree_study/progress_tracker.md`

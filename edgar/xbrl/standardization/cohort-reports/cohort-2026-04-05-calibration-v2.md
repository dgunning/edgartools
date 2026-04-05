# Cohort Report: calibration-v2-2026-04-05

**Status:** inner_loop_complete

## Companies

| Ticker | EF-CQS | Status | Gaps | Notes |
|--------|--------|--------|------|-------|
| AAPL | 0.89 | graduated | 0 |  |
| JPM | 0.83 | graduated | 1 |  |
| HD | 0.86 | graduated | 3 |  |
| D | 0.76 | needs_investigation | 3 |  |
| NEE | 0.81 | graduated | 0 |  |
| CAT | 0.81 | graduated | 2 |  |
| V | 0.81 | graduated | 0 |  |
| XOM | 0.78 | needs_investigation | 1 |  |
| UNH | 0.88 | graduated | 3 |  |
| NFLX | 0.94 | graduated | 1 |  |

## Fixes Applied

_No fixes applied._

## Unresolved Gaps

| Ticker | Metric | Gap Type | Variance | Root Cause | Graveyard |
|--------|--------|----------|----------|------------|-----------|
| D | OperatingIncome | validation_failure | 88.0 | wrong_concept | 0 |
| UNH | OperatingIncome | validation_failure | 38.2 | wrong_concept | 0 |
| JPM | IntangibleAssets | high_variance | 14.1 | wrong_concept | 0 |
| NFLX | SGA | high_variance | 13.2 | sector_specific | 0 |
| D | IncomeTaxExpense | high_variance | 25.1 | wrong_concept | 0 |
| D | RetainedEarnings | high_variance | 24.0 | wrong_concept | 0 |
| HD | AccountsReceivable | high_variance | 13.5 | wrong_concept | 0 |
| HD | DepreciationAmortization | high_variance | 11.3 | wrong_concept | 0 |
| UNH | COGS | high_variance | 85.0 | wrong_concept | 0 |
| HD | PropertyPlantEquipment | explained_variance | 24.3 | explained_variance | 0 |
| CAT | Capex | explained_variance | 38.2 | explained_variance | 0 |
| CAT | AccountsReceivable | explained_variance | 50.8 | explained_variance | 0 |
| UNH | AccountsPayable | explained_variance | 49.9 | explained_variance | 0 |
| XOM | LongTermDebt | explained_variance | 12.0 | explained_variance | 2 |

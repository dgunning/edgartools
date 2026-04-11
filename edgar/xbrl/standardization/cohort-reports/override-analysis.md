# Override Exclusion Analysis

**Date**: 2026-04-05

## Data Sources

- **company_overrides/*.json**: 81 files, 60 with exclude_metrics, 73 total exclusions
- **companies.yaml**: 123 companies, 63 with exclude_metrics, 144 total exclusions
- **Combined unique**: 87 companies with exclusions, 216 total exclusion entries
- **Industry resolved**: 64 (43 from companies.yaml, 21 from SIC lookup)
- **No industry**: 23

## Classification Summary

| Category | Count | Action |
|----------|-------|--------|
| Redundant (already in industry forbidden_metrics) | 51 | Remove from per-company config |
| Promotable (3+ companies, same industry+metric) | 16 groups | Add to industry_metrics.yaml |
| Borderline (2 companies) | 7 groups | Review manually |
| Company-specific (1 company) | 42 | Keep in per-company override |
| No industry assigned | 44 | Assign industry first |

## Redundant Exclusions (safe to remove)

These are already covered by `industry_metrics.yaml` forbidden_metrics.
Removing them will reduce config noise without changing behavior.

| Ticker | Metric | Industry | Source |
|--------|--------|----------|--------|
| AIG | COGS | insurance | yaml |
| AMT | COGS | reits | yaml |
| AMT | Inventory | reits | yaml |
| AON | COGS | insurance | yaml |
| AON | Inventory | insurance | yaml |
| AXP | COGS | financial_services | yaml |
| AXP | SGA | financial_services | yaml |
| BAC | COGS | banking | yaml |
| BAC | Inventory | banking | yaml |
| BK | COGS | banking | yaml |
| BLK | COGS | asset_management | yaml |
| BLK | Capex | asset_management | yaml |
| BRK-B | COGS | insurance | yaml |
| C | COGS | banking | yaml |
| C | Inventory | banking | yaml |
| CB | COGS | insurance | yaml |
| CMCSA | Inventory | telecom | yaml |
| CME | COGS | securities | yaml |
| CME | Capex | securities | yaml |
| CME | OperatingIncome | securities | yaml |
| CME | SGA | securities | yaml |
| EQIX | COGS | reits | yaml |
| FDX | COGS | transportation | yaml |
| GS | COGS | banking | yaml |
| GS | Inventory | banking | yaml |
| ICE | COGS | securities | yaml |
| ICE | Capex | securities | yaml |
| ICE | OperatingIncome | securities | yaml |
| ICE | SGA | securities | yaml |
| JPM | COGS | banking | yaml |
| JPM | GrossProfit | banking | yaml |
| JPM | ResearchAndDevelopment | banking | yaml |
| MET | COGS | insurance | yaml |
| MMC | COGS | insurance | yaml |
| MMC | Inventory | insurance | yaml |
| MS | COGS | banking | yaml |
| MS | Inventory | banking | yaml |
| PLD | COGS | reits | yaml |
| PLD | Inventory | reits | yaml |
| PNC | COGS | banking | yaml |
| SCHW | COGS | securities | yaml |
| SCHW | Capex | securities | yaml |
| SCHW | Inventory | securities | yaml |
| SCHW | OperatingIncome | securities | yaml |
| SCHW | SGA | securities | yaml |
| SPG | COGS | reits | yaml |
| SPG | Inventory | reits | yaml |
| STT | COGS | banking | yaml |
| UPS | COGS | transportation | yaml |
| USB | COGS | banking | yaml |
| WFC | COGS | banking | yaml |

## Promotable Exclusions (add to industry_metrics.yaml)

These metrics are excluded by 3+ companies in the same industry,
suggesting they are industry-level patterns, not company-specific.

| Metric | Industry | Count | Tickers |
|--------|----------|-------|---------|
| SGA | banking | 10 | BAC, BK, C, GS, JPM, MS, PNC, STT, USB, WFC |
| AccountsPayable | banking | 5 | BAC, C, GS, JPM, MS |
| ResearchAndDevelopment | retail | 5 | HD, LOW, ORLY, ROST, TGT |
| COGS | healthcare | 4 | ABBV, AMGN, GILD, MRK |
| COGS | tech | 4 | INTU, NOW, ORCL, SNOW |
| ResearchAndDevelopment | reits | 4 | AMT, EQIX, PLD, SPG |
| ResearchAndDevelopment | telecom | 4 | CMCSA, T, TMUS, VZ |
| ResearchAndDevelopment | transportation | 4 | CSX, FDX, NSC, UPS |
| ResearchAndDevelopment | utilities | 4 | D, DUK, NEE, SO |
| AccountsReceivable | banking | 3 | C, JPM, MS |
| COGS | business_services | 3 | ACN, MA, V |
| Capex | insurance | 3 | AIG, BRK-B, MET |
| DividendPerShare | tech | 3 | NOW, PANW, SNOW |
| ResearchAndDevelopment | financial_services | 3 | AXP, DE, SPGI |
| ResearchAndDevelopment | insurance | 3 | AON, BRK-B, MMC |
| ResearchAndDevelopment | securities | 3 | CME, ICE, SCHW |

## Borderline (2 companies - review manually)

| Metric | Industry | Tickers |
|--------|----------|---------|
| DividendsPaid | tech | PANW, SNOW |
| GrossProfit | business_services | MA, V |
| Inventory | business_services | MA, V |
| Inventory | financial_services | AXP, MCO |
| Inventory | tech | NOW, SNOW |
| OperatingIncome | financial_services | AXP, DE |
| ResearchAndDevelopment | business_services | MA, V |

## Company-Specific (keep in per-company override)

| Metric | Industry | Ticker |
|--------|----------|--------|
| AccountsPayable | insurance | BRK-B |
| AccountsPayable | reits | SPG |
| AccountsPayable | securities | SCHW |
| COGS | energy | COP |
| COGS | health_insurance | CI |
| COGS | utilities | NEE |
| Capex | business_services | MA |
| Capex | financial_services | AXP |
| Capex | reits | EQIX |
| DividendPerShare | healthcare | VRTX |
| DividendPerShare | insurance | BRK-B |
| DividendPerShare | retail | ORLY |
| DividendPerShare | semiconductors | AMD |
| DividendsPaid | healthcare | VRTX |
| Goodwill | transportation | NSC |
| GrossProfit | reits | SPG |
| GrossProfit | transportation | UPS |
| IntangibleAssets | transportation | NSC |
| IntangibleAssets | utilities | NEE |
| Inventory | asset_management | BLK |
| LongTermDebt | insurance | BRK-B |
| LongTermDebt | tech | SNOW |
| OperatingIncome | asset_management | BLK |
| OperatingIncome | healthcare | MRK |
| OperatingIncome | insurance | MMC |
| PretaxIncome | financial_services | DE |
| PretaxIncome | semiconductors | AVGO |
| ResearchAndDevelopment | asset_management | BLK |
| ResearchAndDevelopment | consumergoods | STZ |
| ResearchAndDevelopment | franchise | MCD |
| RetainedEarnings | asset_management | BLK |
| SGA | asset_management | BLK |
| ShortTermDebt | asset_management | BLK |
| ShortTermDebt | financial_services | DE |
| ShortTermDebt | healthcare | ABBV |
| ShortTermDebt | reits | SPG |
| ShortTermDebt | retail | HD |
| ShortTermDebt | securities | ICE |
| ShortTermDebt | tech | SNOW |
| ShortTermDebt | utilities | NEE |
| StockBasedCompensation | insurance | BRK-B |
| WeightedAverageSharesDiluted | insurance | BRK-B |

## No Industry Assigned (need industry before categorizing)

These companies have exclusions but no industry classification.
Assign industry in companies.yaml to enable proper categorization.

| Ticker | Metric |
|--------|--------|
| AAPL | Goodwill |
| AAPL | IntangibleAssets |
| ADBE | COGS |
| ADBE | DividendPerShare |
| ADBE | DividendsPaid |
| ADBE | Inventory |
| AMZN | DividendPerShare |
| AMZN | DividendsPaid |
| CAT | ResearchAndDevelopment |
| CAT | ShortTermDebt |
| COST | ResearchAndDevelopment |
| CRM | COGS |
| CRM | Inventory |
| DHR | DividendPerShare |
| DIS | ResearchAndDevelopment |
| GE | AccountsPayable |
| GE | ResearchAndDevelopment |
| GOOG | GrossProfit |
| HON | ResearchAndDevelopment |
| HSY | ResearchAndDevelopment |
| JNJ | OperatingIncome |
| KO | ResearchAndDevelopment |
| KO | ShortTermDebt |
| LLY | OperatingIncome |
| META | COGS |
| META | GrossProfit |
| META | Inventory |
| NFLX | DividendPerShare |
| NFLX | DividendsPaid |
| NFLX | Goodwill |
| NFLX | Inventory |
| NFLX | PretaxIncome |
| NKE | OperatingIncome |
| NKE | ResearchAndDevelopment |
| PEP | ResearchAndDevelopment |
| PG | ResearchAndDevelopment |
| RTX | ResearchAndDevelopment |
| RTX | ShortTermDebt |
| TSLA | DividendPerShare |
| TSLA | DividendsPaid |
| TSLA | IntangibleAssets |
| TSLA | ShareRepurchases |
| WMT | GrossProfit |
| WMT | ResearchAndDevelopment |

## Most Frequently Excluded Metrics (all companies)

| Metric | Companies Excluding | % of Companies with Exclusions |
|--------|--------------------|---------------------------------|
| ResearchAndDevelopment | 48 | 55% |
| COGS | 44 | 51% |
| Inventory | 22 | 25% |
| SGA | 15 | 17% |
| DividendPerShare | 12 | 14% |
| OperatingIncome | 11 | 13% |
| ShortTermDebt | 11 | 13% |
| Capex | 10 | 11% |
| AccountsPayable | 9 | 10% |
| GrossProfit | 8 | 9% |
| DividendsPaid | 7 | 8% |
| IntangibleAssets | 4 | 5% |
| PretaxIncome | 3 | 3% |
| Goodwill | 3 | 3% |
| AccountsReceivable | 3 | 3% |
| LongTermDebt | 2 | 2% |
| RetainedEarnings | 1 | 1% |
| ShareRepurchases | 1 | 1% |
| StockBasedCompensation | 1 | 1% |
| WeightedAverageSharesDiluted | 1 | 1% |

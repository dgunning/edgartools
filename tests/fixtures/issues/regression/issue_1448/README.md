# GH #1448 fixture: Conagra company facts, cash-change elements only

`conagra_cash_change_companyfacts.json` is SEC's company facts for Conagra Brands
(CIK 23217), fetched 2026-11-12 from
`https://data.sec.gov/api/xbrl/companyfacts/CIK0000023217.json` (4.9 MB) and trimmed to
183 KB with `trim_companyfacts.py`. The trim keeps all `dei` facts and seven `us-gaap`
concepts, each with every fact SEC served, copied verbatim:

- `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect`
- `...PeriodIncreaseDecreaseIncludingExchangeRateEffectContinuingOperations`
- `...PeriodIncreaseDecreaseIncludingExchangeRateEffectDisposalGroupIncludingDiscontinuedOperations`
- `EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsIncludingDisposalGroupAndDiscontinuedOperations`
- `NetCashProvidedByUsedIn{Operating,Investing,Financing}Activities` (EntityFacts builds no
  cash flow statement without the three activity totals)

The values the test asserts come from Conagra's FY2026 10-K, accession
0001104659-26-083905 (cash flow statement, R8): for the year ended 2025-05-25, net change
in cash including held-for-sale balances $-11.0M, held-for-sale change $-1.3M, and the
continuing-operations-tagged change $-9.7M.

To rebuild:

```bash
curl -A "Your Name you@example.com" -o CIK0000023217.json \
  https://data.sec.gov/api/xbrl/companyfacts/CIK0000023217.json
python trim_companyfacts.py CIK0000023217.json conagra_cash_change_companyfacts.json
```

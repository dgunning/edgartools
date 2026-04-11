---
description: Document a known XBRL/reference data discrepancy
---

# Document Discrepancy Workflow

Use this workflow when you discover a mismatch between XBRL extracted values and reference data (yfinance) that cannot be fixed by mapping improvements.

## When to Use

1. XBRL value is correct but differs from yfinance due to **definition differences**
2. Reference data is unavailable (yfinance returns NaN) but mapping is correct
3. Period alignment issues that are inherent to the data source

## Steps

1. **Identify the discrepancy**
   - Ticker: Company symbol
   - Metric: Standard metric name (e.g., IntangibleAssets)
   - XBRL value and concepts used
   - Reference value and source

2. **Classify the discrepancy**
   - `definition_mismatch`: Different definitions between XBRL and reference
   - `reference_unavailable`: Reference returns NaN/null
   - `period_mismatch`: Different reporting periods

3. **Add to discrepancies.json**

```bash
// turbo
python -m edgar.xbrl.standardization.tools.discrepancy_manager add \
  TICKER METRIC \
  --period "2024-FY" \
  --xbrl-value 390000000 \
  --xbrl-concepts "us-gaap:Goodwill" "us-gaap:IntangibleAssetsNetExcludingGoodwill" \
  --ref-value 1470000000 \
  --ref-field "Goodwill And Other Intangible Assets" \
  --classification definition_mismatch \
  --reason "yfinance includes items XBRL categorizes differently"
```

4. **If multi-period verified, update validation_history.json**
   - Verify mapping works across 3+ fiscal periods
   - Promote to tier 1 (trusted)

5. **Commit changes**
```bash
git add edgar/xbrl/standardization/company_mappings/
git commit -m "doc: Add discrepancy for {TICKER} {METRIC}"
```

## Discrepancy Classifications

| Classification | Description | Action |
|----------------|-------------|--------|
| `definition_mismatch` | XBRL and reference define metric differently | Use XBRL value |
| `reference_unavailable` | Reference returns NaN (metric doesn't exist) | Use XBRL value |
| `period_mismatch` | Different reporting periods | Investigate further |

## Example: TSLA IntangibleAssets

```json
{
  "id": "TSLA-IntangibleAssets-2024FY",
  "ticker": "TSLA",
  "metric": "IntangibleAssets",
  "xbrl": {"value": 390000000},
  "reference": {"value": 1470000000},
  "variance_pct": 73.5,
  "classification": "definition_mismatch",
  "action": "use_xbrl_value"
}
```

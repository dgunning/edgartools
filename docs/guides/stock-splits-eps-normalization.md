---
description: Detect stock splits from SEC filings and normalize per-share metrics with Python. Automatically adjust EPS and share counts using edgartools split detection.
---

# Stock Splits: Detect Split Events and Normalize Per-Share Metrics with Python

Stock splits change share counts and per-share values, making historical comparisons difficult. A company reporting $10 EPS before a 2-for-1 split should show $5 adjusted EPS for that period -- but SEC filings contain both adjusted and unadjusted values depending on when they were filed. EdgarTools detects splits from XBRL data and automatically normalizes per-share metrics so you can build consistent time series.

```python
from edgar import Company
from edgar.ttm import detect_splits

company = Company("NVDA")
facts = company.get_facts()
splits = detect_splits(facts.get_all_facts())

for split in splits:
    print(f"{split['date']}: {split['ratio']:.0f}-for-1 split")
```

A few lines to find every stock split in a company's SEC filing history.

---

## Detect Stock Splits from XBRL Data

EdgarTools finds splits by looking for `StockSplitConversionRatio` facts in XBRL filings. These facts appear in 10-Q, 10-K, and 8-K reports whenever a company reports a split event.

```python
from edgar import Company
from edgar.ttm import detect_splits

nvidia = Company("NVDA")
entity_facts = nvidia.get_facts()
facts = entity_facts.get_all_facts()

splits = detect_splits(facts)

for split in splits:
    print(f"Date: {split['date']}, Ratio: {split['ratio']}")
```

Output:
```
Date: 2021-07-20, Ratio: 4.0
Date: 2024-06-10, Ratio: 10.0
```

### How Split Detection Works

The `detect_splits()` function:

1. **Finds split facts** - Searches for `StockSplitConversionRatio` in XBRL concepts
2. **Filters stale data** - Rejects facts filed >280 days after the split date (historical echoes)
3. **Validates duration** - Accepts instant facts or short-duration facts (≤31 days), rejects quarterly/annual aggregations
4. **Deduplicates** - One split per year/ratio combination (same split reported in multiple filings)

The ratio represents the multiplier applied to share counts. A 10-for-1 split has `ratio=10.0`.

---

## Find Stock Split Announcements in 8-K Filings

Companies typically announce splits via 8-K current reports, usually under Item 8.01 ("Other Events") or occasionally Item 5.03 ("Amendments to Articles of Incorporation").

```python
from edgar import Company

apple = Company("AAPL")
filings_8k = apple.get_filings(form="8-K")

# Filter to filings that might contain split announcements
for filing in filings_8k[:50]:  # Check recent 50 filings
    eight_k = filing.obj()

    # Look for Item 8.01 (where most splits are announced)
    if 'Item 8.01' in eight_k.items or 'Item 5.03' in eight_k.items:
        content = eight_k.get('8.01') or eight_k.get('5.03') or ''
        if 'split' in content.lower():
            print(f"{filing.filing_date}: {filing.accession_no}")
            print(f"Items: {', '.join(eight_k.items)}")
```

Press releases attached as EX-99 exhibits often contain the split announcement details:

```python
if eight_k.has_press_release:
    for release in eight_k.press_releases:
        text = release.text()
        if 'stock split' in text.lower():
            print(f"Split announced: {filing.filing_date}")
            print(text[:500])  # First 500 chars
```

---

## Normalize Per-Share Metrics

Once you've detected splits, use `apply_split_adjustments()` to retroactively adjust historical data. This makes pre-split and post-split values directly comparable.

```python
from edgar import Company
from edgar.ttm import detect_splits, apply_split_adjustments

tesla = Company("TSLA")
facts = tesla.get_facts().get_all_facts()

# Detect splits
splits = detect_splits(facts)

# Apply adjustments
adjusted_facts = apply_split_adjustments(facts, splits)

# Compare original vs adjusted EPS
eps_facts = [f for f in facts if 'EarningsPerShare' in f.concept]
eps_adjusted = [f for f in adjusted_facts if 'EarningsPerShare' in f.concept]

for orig, adj in zip(eps_facts[:3], eps_adjusted[:3]):
    print(f"{orig.period_end}: ${orig.numeric_value:.2f} → ${adj.numeric_value:.2f}")
```

Output shows EPS before and after split adjustment:
```
2021-12-31: $4.90 → $1.63
2022-03-31: $3.22 → $1.07
2022-06-30: $2.27 → $0.76
```

### What Gets Adjusted

The adjustment logic depends on the fact's unit and concept:

| Type | Unit Pattern | Adjustment | Examples |
|------|-------------|------------|----------|
| **Per-share metrics** | `/share` in unit or `EarningsPerShare` in concept | Divide by ratio | EPS, Dividends per share, Book value per share |
| **Share counts** | `shares` in unit (but not per-share) | Multiply by ratio | Shares outstanding, Weighted average shares |
| **Other metrics** | All others | No adjustment | Revenue, Net Income, Assets |

```python
# Per-share: Divide by split ratio
# If 10-for-1 split, $10 EPS becomes $1 EPS
adjusted_eps = original_eps / 10.0

# Share counts: Multiply by split ratio
# If 10-for-1 split, 100M shares becomes 1B shares
adjusted_shares = original_shares * 10.0
```

### Retroactive Adjustment Rules

Splits only adjust facts from periods **before** the split date. The function applies cumulative ratios for multiple splits:

```python
# Example: Company had two splits
# 2021-07-20: 4-for-1 split
# 2024-06-10: 10-for-1 split

# For a fact from 2020:
# - Both splits occurred after 2020
# - Cumulative ratio = 4.0 * 10.0 = 40.0
# - Adjust by dividing by 40

# For a fact from 2022:
# - Only 2024 split occurred after 2022
# - Cumulative ratio = 10.0
# - Adjust by dividing by 10

# For a fact from 2024-07:
# - No splits after this date
# - No adjustment needed (already post-split values)
```

The function also checks filing dates. If a fact was filed **after** the split, it's already adjusted by the company and doesn't need further modification.

---

## Automatic Split Handling in TTM Calculations

TTM (Trailing Twelve Months) methods automatically detect and apply split adjustments. You don't need to call `detect_splits()` or `apply_split_adjustments()` manually when using these methods.

```python
from edgar import Company

nvidia = Company("NVDA")

# TTM calculations handle splits automatically
ttm_revenue = nvidia.get_ttm_revenue()
ttm_net_income = nvidia.get_ttm_net_income()

print(f"TTM Revenue: ${ttm_revenue.value / 1e9:.1f}B")
print(f"TTM Net Income: ${ttm_net_income.value / 1e9:.1f}B")
print(f"As of: {ttm_revenue.as_of_date}")
print(f"Periods: {ttm_revenue.periods}")
```

For any XBRL concept:

```python
# Per-share metrics are automatically split-adjusted
ttm_eps = nvidia.get_ttm("EarningsPerShareBasic")
print(f"TTM EPS: ${ttm_eps.value:.2f}")

# Share counts are automatically adjusted too
ttm_shares = nvidia.get_ttm("WeightedAverageNumberOfSharesOutstandingBasic")
print(f"Weighted Avg Shares: {ttm_shares.value / 1e9:.2f}B")
```

Behind the scenes, `get_ttm()` calls the internal method `_get_split_adjusted_facts()` which:
1. Gets all facts for the company
2. Detects splits using `detect_splits()`
3. Applies adjustments using `apply_split_adjustments()`
4. Returns normalized facts for TTM calculation

---

## Complete Workflow: NVIDIA 10-for-1 Split Example

NVIDIA executed a 10-for-1 stock split on June 10, 2024. Let's build a complete workflow that detects this split, normalizes historical EPS, and validates the adjustments.

```python
from edgar import Company
from edgar.ttm import detect_splits, apply_split_adjustments

# Step 1: Get NVIDIA data
nvidia = Company("NVDA")
facts = nvidia.get_facts().get_all_facts()

# Step 2: Detect splits
splits = detect_splits(facts)
print(f"Found {len(splits)} splits:")
for split in splits:
    print(f"  {split['date']}: {split['ratio']:.0f}-for-1")

# Step 3: Filter to EPS facts
eps_facts = [f for f in facts
             if 'EarningsPerShareBasic' in f.concept
             and f.period_end
             and f.numeric_value is not None]

# Sort by period
eps_facts.sort(key=lambda f: f.period_end)

# Step 4: Apply split adjustments
adjusted_facts = apply_split_adjustments(eps_facts, splits)

# Step 5: Compare pre-split periods
print("\nEPS Comparison (split-adjusted):")
print(f"{'Period':<12} {'Original':>12} {'Adjusted':>12} {'Cumulative Ratio':>18}")
print("-" * 58)

for orig, adj in zip(eps_facts[-8:], adjusted_facts[-8:]):
    # Calculate cumulative ratio from the adjustment context
    context = adj.calculation_context or ""
    if "split_adj_ratio" in context:
        ratio = float(context.split("_")[-1])
    else:
        ratio = 1.0

    print(f"{orig.period_end!s:<12} ${orig.numeric_value:>11.2f} "
          f"${adj.numeric_value:>11.2f} {ratio:>17.1f}x")
```

Expected output:
```
Found 2 splits:
  2021-07-20: 4-for-1
  2024-06-10: 10-for-1

EPS Comparison (split-adjusted):
Period       Original     Adjusted   Cumulative Ratio
----------------------------------------------------------
2022-01-30   $    4.44   $    0.11             40.0x
2022-05-01   $    1.36   $    0.03             40.0x
2022-07-31   $    0.51   $    0.01             40.0x
2022-10-30   $    0.58   $    0.01             40.0x
2023-01-29   $    0.88   $    0.02             40.0x
2023-04-30   $    1.09   $    0.03             40.0x
2023-07-30   $    2.70   $    0.07             40.0x
2024-01-28   $    5.16   $    0.13             40.0x
```

Periods before both splits get cumulative adjustment of 40x (4 × 10). Periods between the splits would get 10x adjustment. Periods after June 2024 need no adjustment.

---

## Common Analysis Patterns

### Track Split History Across Multiple Companies

```python
from edgar import Company
from edgar.ttm import detect_splits

tech_stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA"]

for ticker in tech_stocks:
    try:
        company = Company(ticker)
        facts = company.get_facts()
        splits = detect_splits(facts.get_all_facts())

        if splits:
            print(f"\n{ticker} ({company.name}):")
            for split in splits:
                print(f"  {split['date']}: {split['ratio']:.1f}-for-1")
        else:
            print(f"\n{ticker}: No splits detected")

    except Exception as e:
        print(f"\n{ticker}: Error - {e}")
```

### Build Split-Adjusted Time Series

Compare EPS over multiple years with consistent per-share values:

```python
from edgar import Company
from edgar.ttm import detect_splits, apply_split_adjustments
import pandas as pd

company = Company("AAPL")
facts = company.get_facts().get_all_facts()

# Get splits and adjust facts
splits = detect_splits(facts)
adjusted_facts = apply_split_adjustments(facts, splits)

# Extract EPS time series
eps_data = []
for f in adjusted_facts:
    if 'EarningsPerShareBasic' in f.concept and f.fiscal_period == 'FY':
        eps_data.append({
            'fiscal_year': f.fiscal_year,
            'period_end': f.period_end,
            'eps': f.numeric_value
        })

# Create DataFrame
df = pd.DataFrame(eps_data).sort_values('fiscal_year')
print(df)

# Calculate growth rates on split-adjusted data
df['yoy_growth'] = df['eps'].pct_change() * 100
print(f"\nAverage EPS growth: {df['yoy_growth'].mean():.1f}%")
```

### Validate Split Adjustments Against Company Reports

Companies publish adjusted historical data after splits. You can validate the adjustment logic:

```python
from edgar import Company
from edgar.ttm import detect_splits, apply_split_adjustments

company = Company("NVDA")
facts = company.get_facts().get_all_facts()

splits = detect_splits(facts)
adjusted = apply_split_adjustments(facts, splits)

# Find the same period reported before and after split
# Pre-split: Filed in 2023 10-K, reports 2023 EPS (pre-split basis)
# Post-split: Filed in 2024 10-K, reports 2023 EPS (post-split basis)

eps_2023_filings = [f for f in adjusted
                     if 'EarningsPerShareBasic' in f.concept
                     and f.fiscal_year == 2023]

# Group by filing date
from collections import defaultdict
by_filing = defaultdict(list)
for f in eps_2023_filings:
    by_filing[f.filing_date].append(f)

# Compare values across filings
for filing_date in sorted(by_filing.keys())[:3]:
    facts_list = by_filing[filing_date]
    if facts_list:
        f = facts_list[0]
        print(f"Filed {filing_date}: 2023 EPS = ${f.numeric_value:.2f}")
```

### Calculate Split-Adjusted Market Cap History

Combine share counts and stock prices to build historical market cap:

```python
from edgar import Company
from edgar.ttm import detect_splits, apply_split_adjustments

company = Company("AAPL")
facts = company.get_facts().get_all_facts()

splits = detect_splits(facts)
adjusted = apply_split_adjustments(facts, splits)

# Get split-adjusted shares outstanding
shares_facts = [f for f in adjusted
                if 'CommonStockSharesOutstanding' in f.concept
                and f.fiscal_period == 'FY']

for f in sorted(shares_facts, key=lambda x: x.period_end)[-5:]:
    shares_b = f.numeric_value / 1e9
    print(f"{f.period_end}: {shares_b:.2f}B shares (split-adjusted)")
```

---

## API Quick Reference

### Detection and Adjustment Functions

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `detect_splits(facts)` | `facts`: List of FinancialFact | List of dicts with `date` and `ratio` | Find all stock splits in facts |
| `apply_split_adjustments(facts, splits)` | `facts`: List of FinancialFact<br>`splits`: List of split dicts | List of adjusted FinancialFact | Apply retroactive adjustments |

### Company Methods with Automatic Split Handling

| Method | Returns | Description |
|--------|---------|-------------|
| `company.get_ttm(concept, as_of=None)` | `TTMMetric` | TTM for any concept (split-adjusted) |
| `company.get_ttm_revenue(as_of=None)` | `TTMMetric` | TTM revenue (split-adjusted) |
| `company.get_ttm_net_income(as_of=None)` | `TTMMetric` | TTM net income (split-adjusted) |

### Split Detection Parameters

The detection logic uses these constants from `edgar.ttm.calculator`:

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_SPLIT_LAG_DAYS` | 280 | Maximum days between split date and filing date |
| `MAX_SPLIT_DURATION_DAYS` | 31 | Maximum period duration for split facts |

---

## Things to Know

**Splits apply retroactively to historical data only.** Facts from periods after the split date don't need adjustment -- they're already reported on a post-split basis.

**Filing date matters for restated facts.** If a fact was filed after a split date, the company has already adjusted it. The adjustment logic checks `filing_date` to avoid double-adjusting.

**Multiple splits compound.** A company with a 4-for-1 split in 2021 and a 10-for-1 split in 2024 requires a cumulative adjustment of 40x for pre-2021 data.

**Reverse splits work automatically.** A 1-for-10 reverse split has `ratio=0.1`. Per-share metrics get divided by 0.1 (multiplied by 10), which correctly increases the adjusted historical EPS.

**Balance sheet items don't need adjustment.** Assets, liabilities, and equity are not per-share values. Total stockholders' equity stays the same regardless of share count.

**Not all facts have filing dates.** The adjustment logic handles `None` filing dates by assuming the fact needs adjustment if it's from before the split.

**Instant facts are preferred.** Split events are moment-in-time occurrences. The detector accepts instant facts (no `period_start`) or short-duration facts (≤31 days) but rejects quarterly/annual durations.

**8-K filing timing varies.** While Item 8.01 is common for split announcements, check Items 5.03 and exhibit press releases. Not all companies follow the same disclosure pattern.

**Weighted average share counts need special handling.** These represent time-weighted averages over a period. For Q4 EPS derivation with splits, use the formula: Q4 shares = 4 × annual_shares - 3 × YTD_9M_shares.

---

## Related

- [Financial Data](financial-data.md) - Extract financial statements and metrics
- [8-K Current Reports](../eightk-filings.md) - Parse material event filings
- [Company Facts API](company-facts.md) - Access XBRL facts programmatically

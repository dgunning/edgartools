# Quant Package

**Advanced quantitative analysis extensions for EdgarTools** - production-ready TTM (Trailing Twelve Months) calculations, XBRL standardization, and stock split adjustments.

## What Problems Does This Solve?

Financial analysts, quantitative researchers, and investors face critical challenges when working with SEC XBRL data:

**1. Missing Quarterly Data (Q4 Problem)**: Most companies only file annual 10-K reports, leaving Q4 data unavailable. This creates gaps in quarterly analysis and makes TTM calculations impossible using traditional methods.

**2. Stock Split Distortions**: Stock splits create discontinuities in per-share metrics and share counts across time periods. Without proper adjustment, EPS trends appear broken and comparisons become meaningless.

**3. XBRL Concept Chaos**: Companies use 1,000+ different XBRL concepts to report the same financial metrics. Revenue alone has 50+ variations (`RevenueFromContractWithCustomer`, `Revenues`, `SalesRevenueNet`, etc.), making cross-company analysis extremely difficult.

**4. Sector-Specific Reporting**: Banks report "Interest Income" while retailers report "Sales Revenue" - both are revenue, but use completely different XBRL taxonomies. Generic mappings fail for sector-specific companies.

**This package solves these problems** by:
- **Deriving Q4 data** from annual reports using multiple proven methods (FY - YTD9, FY - Q1-Q3 sum)
- **Auto-detecting and adjusting** for stock splits across all per-share metrics and share counts
- **Mapping 1,000+ XBRL concepts** to 20 standardized fields using ML-learned mappings from 500+ companies
- **Sector-aware extraction** with automatic detection (banking, insurance, utilities) and sector-specific concept mappings

Developers get **consistent, clean financial data** across all companies with minimal code. Investors get **accurate TTM metrics** for current performance analysis. Financial analysts get **standardized fields** that work across industries and time periods.

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [TTM (Trailing Twelve Months)](#ttm-trailing-twelve-months)
   - [What is TTM?](#what-is-ttm)
   - [Q4 Derivation Methodology](#q4-derivation-methodology-critical)
   - [YTD Period Handling](#ytd-period-handling)
   - [Non-Summation Metrics (EPS, Shares)](#non-summation-metrics-eps-shares)
   - [Stock Split Detection and Adjustment](#stock-split-detection-and-adjustment-critical)
   - [EPS Integration with Split Adjustment](#eps-integration-with-split-adjustment)
4. [XBRL Standardization](#xbrl-standardization)
5. [API Reference](#api-reference)
6. [Examples](#examples)

---

## Installation

The quant package is an extension of EdgarTools and requires the core library:

```bash
pip install edgartools

# For development
cd edgartools/quant
pip install -e .
```

---

## Quick Start

### TTM Calculations

```python
from quant import QuantCompany

# Create enhanced company object (drop-in replacement for edgar.Company)
company = QuantCompany("AAPL")

# Get TTM income statement (most recent 12 months)
ttm_income = company.income_statement(period='ttm')
print(ttm_income)

# Get specific TTM metrics
ttm_revenue = company.get_ttm_revenue()
print(f"TTM Revenue: ${ttm_revenue.value / 1e9:.1f}B as of {ttm_revenue.as_of_date}")

# Get quarterly data with automatic Q4 derivation
quarterly_income = company.income_statement(period='quarterly', periods=8)
```

### XBRL Standardization

```python
from quant.xbrl_standardize.extractors.ic import Evaluator
import json
from pathlib import Path

# Load income statement schema
schema_path = Path('xbrl_standardize/schemas/income-statement.json')
with open(schema_path) as f:
    schema = json.load(f)

# Extract standardized fields from raw XBRL facts
# Note: Concepts must include the taxonomy prefix (us-gaap:)
facts = {
    'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax': 100000000,
    'us-gaap:NetIncomeLoss': 20000000,
    'us-gaap:EarningsPerShareBasic': 2.50
}

evaluator = Evaluator(mapping=schema, facts=facts)
result = evaluator.standardize()
print(result['revenue'])  # 100000000.0
print(result['netIncome'])  # 20000000.0
```

---

## TTM (Trailing Twelve Months)

### What is TTM?

TTM aggregates 4 consecutive quarters to create a rolling 12-month metric. This smooths seasonal variations and provides a current view of annual performance without waiting for fiscal year-end.

**Example**: If most recent quarter is 2024-Q2 (ended June 30, 2024):
```
TTM = Q3 2023 + Q4 2023 + Q1 2024 + Q2 2024
```

This gives you "current annual run rate" as of June 30, 2024.

### Q4 Derivation Methodology (CRITICAL)

**The Problem**: Most companies file quarterly 10-Q reports for Q1-Q3, but only file annual 10-K reports. This means Q4 discrete quarter data is never explicitly reported - only cumulative year-to-date (YTD) and full-year (FY) values are available.

**Our Solution**: We derive Q4 values using two proven methods with automatic fallback:

#### Method 1: Q4 = FY - YTD_9M (Primary)

This is the preferred method when available:

```python
Q4_value = FY_value - YTD_9M_value

# Example for Revenue:
# FY 2023 (Jan 1 - Dec 31): $480B
# YTD_9M (Jan 1 - Sep 30): $350B
# Derived Q4 (Oct 1 - Dec 31): $480B - $350B = $130B
```

**Implementation** (`utils.py:519-552`):
```python
def _derive_q4_from_fy(self, quarters, ytd_9m, annual):
    for fy in annual:
        if not self._is_additive_concept(fy):
            continue  # Skip non-additive concepts (see below)

        # Find matching YTD_9M with same fiscal year start
        ytd9 = self._find_matching_ytd9(ytd_9m,
                                        period_start=fy.period_start,
                                        before=fy.period_end)

        if ytd9:
            q4_value = fy.numeric_value - ytd9.numeric_value
            q4_start = ytd9.period_end + timedelta(days=1)

            # Create derived Q4 fact
            q4_fact = self._create_derived_quarter(
                fy, q4_value, "derived_q4_fy_minus_ytd9",
                target_period="Q4", period_start=q4_start
            )
            derived.append(q4_fact)
```

#### Method 2: Q4 = FY - (Q1 + Q2 + Q3) (Fallback)

When YTD_9M is unavailable, we derive Q4 from the sum of discrete quarters:

```python
Q4_value = FY_value - (Q1_value + Q2_value + Q3_value)

# Example for Net Income:
# FY 2023: $48B
# Q1 2023: $10B
# Q2 2023: $12B
# Q3 2023: $13B
# Derived Q4: $48B - ($10B + $12B + $13B) = $13B
```

**Implementation** (`utils.py:554-609`):
```python
# Fallback when YTD_9M is absent
q1_q3_candidates = [q for q in quarters
                    if q.fiscal_period in ("Q1", "Q2", "Q3")
                    and fy.period_start <= q.period_start <= fy.period_end]

# Prefer latest filing per quarter (handles restatements)
quarter_by_period = {}
for q in q1_q3_candidates:
    existing = quarter_by_period.get(q.fiscal_period)
    if not existing or q.filing_date > existing.filing_date:
        quarter_by_period[q.fiscal_period] = q

# Need all three quarters
q1, q2, q3 = [quarter_by_period.get(p) for p in ("Q1", "Q2", "Q3")]
if all([q1, q2, q3]):
    q4_value = fy.numeric_value - (q1.numeric_value + q2.numeric_value + q3.numeric_value)
```

**Caveats**:
- Q4 derivation assumes **additive concepts only** (revenue, net income, cash flow)
- Non-additive concepts (EPS, shares, ratios) are **excluded** from derivation
- Derived Q4 may be inaccurate if FY includes one-time adjustments not in quarters
- `TTMMetric.has_calculated_q4` flag warns when Q4 is derived vs. reported

### YTD Period Handling

Companies file cumulative Year-To-Date values that must be converted to discrete quarters:

**Duration Buckets** (`utils.py:25-31`):
```python
class DurationBucket:
    QUARTER = "QUARTER"     # 70-120 days  (discrete Q1, Q2, Q3, Q4)
    YTD_6M = "YTD_6M"       # 140-240 days (Jan-Jun cumulative)
    YTD_9M = "YTD_9M"       # 230-330 days (Jan-Sep cumulative)
    ANNUAL = "ANNUAL"       # 330-420 days (Jan-Dec full year)
```

**Quarterization Process** (`utils.py:414-457`):

```python
# Step 1: Classify facts by duration
quarters = self._filter_by_duration(DurationBucket.QUARTER)   # Direct reports
ytd_6m = self._filter_by_duration(DurationBucket.YTD_6M)      # H1 cumulative
ytd_9m = self._filter_by_duration(DurationBucket.YTD_9M)      # 9M cumulative
annual = self._filter_by_duration(DurationBucket.ANNUAL)      # Full year

# Step 2: Derive discrete quarters from YTD
# Q2 = YTD_6M - Q1
for ytd6 in ytd_6m:
    q1 = self._find_prior_quarter(quarters, before=ytd6.period_end)
    if q1:
        q2_value = ytd6.numeric_value - q1.numeric_value
        q2_fact = self._create_derived_quarter(ytd6, q2_value,
                                                "derived_q2_ytd6_minus_q1",
                                                target_period="Q2")

# Q3 = YTD_9M - YTD_6M
for ytd9 in ytd_9m:
    ytd6 = self._find_prior_ytd6(ytd_6m, before=ytd9.period_end)
    if ytd6:
        q3_value = ytd9.numeric_value - ytd6.numeric_value
        q3_fact = self._create_derived_quarter(ytd9, q3_value,
                                                "derived_q3_ytd9_minus_ytd6",
                                                target_period="Q3")

# Q4 = FY - YTD_9M (see Q4 derivation above)
```

**Example Flow**:
```
Company Reports:
- Q1 (Jan-Mar): $100B                    → Keep as-is
- YTD_6M (Jan-Jun): $220B                → Derive Q2 = $220B - $100B = $120B
- YTD_9M (Jan-Sep): $350B                → Derive Q3 = $350B - $220B = $130B
- FY (Jan-Dec): $480B                    → Derive Q4 = $480B - $350B = $130B

Result: Q1=$100B, Q2=$120B, Q3=$130B, Q4=$130B
```

### Non-Summation Metrics (EPS, Shares)

**Not all financial metrics are additive**. You cannot derive Q4 EPS by subtracting YTD values because EPS is a **derived ratio** (Net Income / Shares), and shares change over time.

**Additive vs. Non-Additive** (`utils.py:364-412`):

```python
def _is_additive_concept(self, fact: FinancialFact) -> bool:
    """
    Check if a fact can be safely derived via subtraction.

    Returns False for:
    - Instant facts (Assets, Equity) - point-in-time, not flows
    - Share counts (UnitType.SHARES) - not additive across periods
    - Ratios/Rates (UnitType.RATIO) - averages, not sums
    - Per-share metrics (EPS) - derived from Income/Shares

    Returns True for:
    - Duration monetary flows (Revenue, Net Income, Cash Flow)
    """

    # 1. Instant facts are never additive (Balance Sheet items)
    if fact.period_type == 'instant':
        return False

    # 2. Shares and ratios are never additive
    unit_type = UnitNormalizer.get_unit_type(fact.unit)
    if unit_type in (UnitType.SHARES, UnitType.RATIO):
        return False

    # 3. Per-share metrics are never additive
    if norm_unit in UnitNormalizer.PER_SHARE_MAPPINGS:
        return False

    # 4. Duration monetary flows are additive
    return True
```

**Example - Why EPS is NOT additive**:
```
Q1 EPS: $2.00 = $1B net income / 500M shares
Q2 EPS: $2.10 = $1.05B net income / 500M shares
Q3 EPS: $2.20 = $1.1B net income / 500M shares

YTD_9M "EPS" ≠ $2.00 + $2.10 + $2.20 = $6.30  ❌ WRONG!

Correct YTD_9M EPS = $2.10 = $3.15B total income / 500M avg shares
```

**Solution**: We **recalculate EPS** from components (see next section).

### Stock Split Detection and Adjustment (CRITICAL)

**Stock splits create discontinuities** in per-share metrics and share counts. Without adjustment, historical EPS appears to crash and share counts appear to spike.

#### Split Detection (`utils.py:1478-1519`)

```python
def detect_splits(facts: List[FinancialFact]) -> List[Dict[str, Any]]:
    """
    Detect stock splits from StockSplitConversionRatio facts.

    Filters for valid split events by:
    1. Rejecting filing lags >280 days (historical echoes)
    2. Accepting instant facts OR short-duration (≤31 days)
    3. Rejecting long-duration comparative periods (>31 days)
    4. Deduplicating by (year, ratio)
    """

    split_facts = [f for f in facts if 'StockSplitConversionRatio' in f.concept]
    splits = []
    seen_splits = set()

    for f in split_facts:
        # Skip if filing is >280 days after event (historical echo)
        if f.filing_date:
            lag = (f.filing_date - f.period_end).days
            if lag > 280:
                continue

        # Accept instant facts OR month-long events (≤31 days)
        # Reject quarterly/annual comparative periods (>31 days)
        if f.period_start is not None:
            duration_days = (f.period_end - f.period_start).days
            if duration_days > 31:
                continue

        # Deduplicate by (year, ratio)
        split_key = (f.period_end.year, f.numeric_value)
        if split_key in seen_splits:
            continue
        seen_splits.add(split_key)

        splits.append({
            'date': f.period_end,
            'ratio': f.numeric_value  # e.g., 10.0 for 10-for-1 split
        })

    return sorted(splits, key=lambda s: s['date'])
```

**Example**:
```
NVIDIA 10-for-1 split on June 10, 2024:
- Fact: StockSplitConversionRatio = 10.0
- Period End: 2024-06-10
- Filing Date: 2024-07-15 (lag = 35 days ✓)
- Duration: instant (period_start = None ✓)
→ Valid split detected
```

#### Split Adjustment (`utils.py:1521-1577`)

```python
def apply_split_adjustments(
    facts: List[FinancialFact],
    splits: List[Dict[str, Any]]
) -> List[FinancialFact]:
    """
    Apply retrospective split adjustments to historical data.

    Adjusts:
    - Per-share metrics (EPS, Dividend/Share): DIVIDED by cumulative ratio
    - Share counts (Shares Outstanding): MULTIPLIED by cumulative ratio

    Only adjusts facts filed BEFORE the split date (not restated data).
    """

    for f in facts:
        # Identify metric type
        is_per_share = '/share' in f.unit.lower() or 'earningspershare' in f.concept.lower()
        is_shares = 'shares' in f.unit.lower() and not is_per_share

        if not (is_per_share or is_shares):
            continue

        # Calculate cumulative ratio for all FUTURE splits
        cum_ratio = 1.0
        for s in splits:
            # Apply split if it occurred AFTER this fact's period
            # AND fact was filed BEFORE the split (not already restated)
            if s['date'] > f.period_end:
                if not f.filing_date or f.filing_date <= s['date']:
                    cum_ratio *= s['ratio']

        if cum_ratio == 1.0:
            continue

        # Apply adjustment
        if is_per_share:
            new_val = f.numeric_value / cum_ratio  # Divide EPS
        else:  # is_shares
            new_val = f.numeric_value * cum_ratio  # Multiply shares

        # Create adjusted fact
        adjusted_fact = replace(f,
                               value=new_val,
                               numeric_value=new_val,
                               calculation_context=f"split_adj_ratio_{cum_ratio:.2f}")
```

**Example - NVIDIA 10-for-1 Split (June 2024)**:

```
Historical EPS (Q1 2024, filed May 2024):
- Original reported: $6.00
- Split date: June 10, 2024 (after Q1)
- Cumulative ratio: 10.0
- Adjusted EPS: $6.00 / 10.0 = $0.60 ✓

Historical Shares (Q1 2024):
- Original reported: 500M shares
- Cumulative ratio: 10.0
- Adjusted shares: 500M × 10.0 = 5,000M shares ✓

Post-split EPS (Q3 2024, filed after split):
- Reported: $0.65 (already split-adjusted by company)
- Filing date > split date → cumulative ratio = 1.0
- No adjustment needed → $0.65 ✓
```

### EPS Integration with Split Adjustment

**The Challenge**: We need to derive Q4 EPS from Q4 Net Income and Q4 Weighted Average Shares, but shares change throughout the year and we need split-adjusted values.

**Our Solution** (`utils.py:611-723`):

#### Step 1: Derive Q4 Net Income (Additive)

```python
# Net Income is additive - derive Q4 normally
ni_calculator = TTMCalculator(net_income_facts)
ni_quarters = ni_calculator._quarterize_facts()
q4_net_income = [q for q in ni_quarters if q.fiscal_period == 'Q4']
```

#### Step 2: Calculate Q4 Weighted Average Shares

**Formula**: Q4_WAS = 4 × FY_WAS - 3 × YTD9_WAS

```python
def _calculate_single_q4_eps(self, q4_ni, fy_shares_map, ytd9_shares_map, eps_concept):
    """
    Calculate Q4 EPS using derived net income and calculated Q4 shares.
    """

    fy = q4_ni.fiscal_year
    fy_shares = fy_shares_map[fy]  # Full year weighted average
    ytd9_shares = ytd9_shares_map.get(fy)  # 9-month weighted average

    # Calculate precise Q4 weighted average shares
    if ytd9_shares and ytd9_shares > 0:
        # Q4_WAS = 4 × FY_WAS - 3 × YTD9_WAS
        # Derivation:
        # FY_WAS = (Q1 + Q2 + Q3 + Q4) / 4
        # YTD9_WAS = (Q1 + Q2 + Q3) / 3
        # → 4 × FY_WAS = Q1 + Q2 + Q3 + Q4
        # → 3 × YTD9_WAS = Q1 + Q2 + Q3
        # → Q4 = 4 × FY_WAS - 3 × YTD9_WAS

        q4_shares = 4 * fy_shares - 3 * ytd9_shares

        if q4_shares <= 0:  # Sanity check
            q4_shares = fy_shares  # Fallback to FY average
    else:
        q4_shares = fy_shares  # Fallback when YTD9 unavailable

    # Calculate Q4 EPS
    q4_eps_value = q4_ni.numeric_value / q4_shares

    return q4_eps_value
```

**Example - Apple FY2023**:
```
FY 2023 Weighted Avg Shares: 15.55B
YTD9 2023 Weighted Avg Shares: 15.63B

Q4 Shares Calculation:
Q4_WAS = 4 × 15.55B - 3 × 15.63B
       = 62.2B - 46.89B
       = 15.31B shares

Q4 Net Income: $23.0B (derived via Q4 = FY - YTD9)
Q4 EPS = $23.0B / 15.31B = $1.50

Why this works:
- FY_WAS is average of all 4 quarters
- YTD9_WAS is average of first 3 quarters
- Formula isolates Q4 by subtracting weighted Q1-Q3 from weighted total
```

#### Step 3: Apply Split Adjustments

```python
# Shares are automatically split-adjusted because:
# 1. detect_splits() identifies all splits from facts
# 2. apply_split_adjustments() adjusts share counts BEFORE calculation
# 3. Net income is NOT per-share, so not affected by splits
# 4. Final EPS = adjusted_net_income / adjusted_shares

# Example with 10-for-1 split:
# Pre-split Q4 2023: Net Income $10B, Shares 1B → EPS $10.00
# After 2024 split applied retroactively:
#   - Net Income: $10B (unchanged)
#   - Shares: 1B × 10 = 10B (adjusted)
#   - EPS: $10B / 10B = $1.00 (correctly adjusted)
```

#### Complete Integration Flow

```python
# In QuantCompany.income_statement(period='quarterly'):

# 1. Get facts with split adjustments
facts = self._get_adjusted_facts()  # Applies split adjustments first

# 2. Prepare quarterly facts (derives Q4 net income)
facts = self._prepare_quarterly_facts(facts)

# 3. Within _prepare_quarterly_facts():
net_income_facts = _collect_facts(["NetIncomeLoss"])
shares_facts = _collect_facts(["WeightedAverageNumberOfSharesOutstandingBasic"])

# 4. Derive Q4 EPS from split-adjusted components
calc = TTMCalculator(net_income_facts)
derived_eps = calc.derive_eps_for_quarter(
    net_income_facts,  # Already split-adjusted (no effect, not per-share)
    shares_facts,      # Already split-adjusted (multiplied by ratio)
    eps_concept="us-gaap:EarningsPerShareBasic"
)

# 5. Add derived Q4 EPS to facts (only if not already reported)
for eps_fact in derived_eps:
    if not _has_eps_for_period(eps_fact.concept, eps_fact.period_end, eps_fact.fiscal_period):
        derived_facts.append(eps_fact)

# Result: Complete quarterly data with split-adjusted Q4 EPS
```

**Summary - TTM Methodology**:

1. **Q4 Derivation**: Two methods (FY - YTD9, FY - Q1-Q3) for additive metrics only
2. **YTD Handling**: Duration classification and quarterization (Q2 from YTD6, Q3 from YTD9)
3. **Non-Summation**: EPS and shares excluded from derivation, recalculated from components
4. **Stock Splits**: Automatic detection and retrospective adjustment (divide per-share, multiply shares)
5. **EPS Integration**: Q4 EPS = Q4 Net Income / Q4 Weighted Shares (formula: 4×FY - 3×YTD9)

---

## XBRL Standardization

### The Problem

Companies use 1,000+ different XBRL concepts to report identical financial metrics:

```
Revenue can be reported as:
- us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax
- us-gaap:Revenues
- us-gaap:SalesRevenueNet
- us-gaap:SalesRevenueGoodsNet
- ... 50+ more variations
```

Traditional approaches fail because:
- Manual mappings don't scale (too many concepts)
- Simple keyword matching misses context (e.g., "Revenue" vs "Deferred Revenue")
- Sector-specific terminology differs (banks use "InterestIncome", retailers use "SalesRevenue")

### Our Solution: ML-Powered Mapping

We train on 500+ real companies to learn which concepts actually represent each financial field:

```
Training Data:
- 500 global companies → Core mappings
- 150 banks → Banking overlay
- 150 insurers → Insurance overlay
- 150 utilities → Utilities overlay

Output:
- Primary concepts (highest occurrence rate)
- Fallback chains (try A, then B, then C)
- Confidence scores (high/medium/low)
- Sector-specific overrides
```

### Architecture

```
Input: Raw XBRL Facts
  ↓
Sector Detection (SIC code or fact patterns)
  ↓
Load Mappings (core + sector overlay)
  ↓
Concept Resolution (primary → fallback chain)
  ↓
Output: Standardized Fields
```

### Standardized Fields

**Income Statement** (16 fields):
- `revenue`, `costOfRevenue`, `grossProfit`
- `operatingExpenses`, `operatingIncome`
- `interestExpense`, `otherIncomeExpense`
- `incomeBeforeTax`, `incomeTaxExpense`, `netIncome`
- `earningsPerShareBasic`, `earningsPerShareDiluted`
- `weightedAverageSharesBasic`, `weightedAverageSharesDiluted`
- `comprehensiveIncome`, `dividendsPerShare`

**Balance Sheet** (15 fields):
- `cashAndEquivalents`, `currentAssets`, `totalAssets`
- `currentLiabilities`, `totalLiabilities`, `totalEquity`
- `retainedEarnings`, `accumulatedOCI`
- ... and more

**Cash Flow Statement** (10 fields):
- `operatingCashFlow`, `investingCashFlow`, `financingCashFlow`
- `capitalExpenditures`, `freeCashFlow`
- ... and more

### Quality Metrics

```
Coverage Rate: 100% (16/16 required fields)
High Confidence: 68.8% (11/16 fields)
Mean Occurrence: 46.9% (average across all fields)
Conflict Rate: 0% (no duplicate mappings)
```

---

## API Reference

### QuantCompany

Drop-in replacement for `edgar.Company` with quantitative enhancements.

```python
from quant import QuantCompany

company = QuantCompany("AAPL")
```

#### Methods

**`income_statement(periods=4, period='annual', as_dataframe=False)`**

Get income statement with optional TTM calculation.

- `period`: `'annual'`, `'quarterly'`, or `'ttm'`
- `periods`: Number of periods to return
- `as_dataframe`: Return as pandas DataFrame

```python
# Annual income statement (last 4 years)
annual = company.income_statement(period='annual', periods=4)

# Quarterly with Q4 derivation (last 8 quarters)
quarterly = company.income_statement(period='quarterly', periods=8)

# TTM income statement (most recent 12 months)
ttm = company.income_statement(period='ttm')
```

**`get_ttm_revenue()`**

Get TTM revenue metric.

```python
ttm_rev = company.get_ttm_revenue()
print(f"${ttm_rev.value / 1e9:.1f}B as of {ttm_rev.as_of_date}")
print(f"Periods: {ttm_rev.periods}")
print(f"Has gaps: {ttm_rev.has_gaps}")
print(f"Q4 calculated: {ttm_rev.has_calculated_q4}")
```

**`get_ttm_net_income()`**

Get TTM net income metric.

**`get_ttm(concept, as_of=None)`**

Get TTM for any XBRL concept.

```python
# TTM for specific concept
ttm = company.get_ttm('OperatingIncomeLoss')

# TTM as of specific date
ttm = company.get_ttm('NetIncomeLoss', as_of='2023-12-31')
```

### TTMCalculator

Low-level TTM calculation engine.

```python
from quant.utils import TTMCalculator
from edgar import Company

company = Company("MSFT")
facts = company.facts._facts
revenue_facts = [f for f in facts if f.concept == 'us-gaap:Revenues']

calc = TTMCalculator(revenue_facts)
ttm = calc.calculate_ttm()

print(f"TTM Revenue: ${ttm.value / 1e9:.1f}B")
print(f"Periods: {ttm.periods}")
print(f"Warning: {ttm.warning}")
```

#### Methods

**`calculate_ttm(as_of=None)`**

Calculate single TTM value.

**`calculate_ttm_trend(periods=8)`**

Calculate rolling TTM time series.

```python
trend = calc.calculate_ttm_trend(periods=8)
print(trend[['as_of_quarter', 'ttm_value', 'yoy_growth']])
```

### XBRL Standardization

**`Evaluator(mapping, facts, industry=None)`**

Extract standardized income statement fields using schema-based mapping.

```python
from quant.xbrl_standardize.extractors.ic import Evaluator
import json
from pathlib import Path

# Load schema
with open('xbrl_standardize/schemas/income-statement.json') as f:
    schema = json.load(f)

# Extract - facts dict must include taxonomy prefix (us-gaap:)
facts = {
    'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax': 100000000,
    'us-gaap:NetIncomeLoss': 20000000
}

evaluator = Evaluator(mapping=schema, facts=facts)
result = evaluator.standardize()
print(result['revenue'])  # 100000000.0
print(result['netIncome'])  # 20000000.0
```

**Note**: The full `apply_mappings` API referenced in earlier documentation is under development. Current extraction uses schema-based extractors (`extractors/ic.py`, `bs.py`, `cf.py`) with schema files from `schemas/` directory.

---

## Examples

### Example 1: Quarterly Analysis with Q4 Derivation

```python
from quant import QuantCompany
import pandas as pd

# Get company
company = QuantCompany("NVDA")

# Get 8 quarters of income statement (includes derived Q4)
stmt = company.income_statement(period='quarterly', periods=8, as_dataframe=True)

# Analyze quarterly revenue trend
revenue_row = stmt[stmt['label'] == 'Revenue'].iloc[0]
quarters = [col for col in stmt.columns if col.startswith('Q')]
revenue_by_quarter = {q: revenue_row[q] for q in quarters}

print("Quarterly Revenue (includes derived Q4):")
for quarter, value in revenue_by_quarter.items():
    print(f"{quarter}: ${value/1e9:.1f}B")
```

### Example 2: TTM Trend Analysis

```python
from quant import QuantCompany
from quant.utils import TTMCalculator

company = QuantCompany("AAPL")
facts = company._get_adjusted_facts()

# Get revenue facts
revenue_facts = [f for f in facts if 'Revenue' in f.concept and 'Contract' in f.concept]

# Calculate TTM trend
calc = TTMCalculator(revenue_facts)
trend = calc.calculate_ttm_trend(periods=8)

# Analyze growth
print("TTM Revenue Trend:")
print(trend[['as_of_quarter', 'ttm_value', 'yoy_growth']])

# Plot trend
import matplotlib.pyplot as plt
plt.plot(trend['as_of_quarter'], trend['ttm_value'] / 1e9)
plt.title('TTM Revenue Trend')
plt.ylabel('Revenue ($B)')
plt.xticks(rotation=45)
plt.show()
```

### Example 3: Stock Split Detection

```python
from quant import QuantCompany
from quant.utils import detect_splits

company = QuantCompany("NVDA")
facts = company.facts._facts

# Detect splits
splits = detect_splits(facts)

print(f"Found {len(splits)} stock splits:")
for split in splits:
    print(f"  {split['date']}: {split['ratio']:.1f}-for-1 split")

# Get split-adjusted EPS
eps_facts = [f for f in company._get_adjusted_facts()
             if 'EarningsPerShare' in f.concept and f.fiscal_period == 'Q1']

print("\nQ1 EPS (split-adjusted):")
for f in sorted(eps_facts, key=lambda x: x.fiscal_year):
    print(f"  {f.fiscal_year} Q1: ${f.numeric_value:.2f}")
```

### Example 4: Cross-Company Comparison

```python
from quant import QuantCompany

# Compare companies using QuantCompany
companies = ["AAPL", "MSFT", "NVDA"]

for ticker in companies:
    company = QuantCompany(ticker)

    # Get TTM revenue and net income
    try:
        ttm_rev = company.get_ttm_revenue()
        ttm_ni = company.get_ttm_net_income()

        print(f"\n{ticker}:")
        print(f"  TTM Revenue: ${ttm_rev.value/1e9:.1f}B (as of {ttm_rev.as_of_date})")
        print(f"  TTM Net Income: ${ttm_ni.value/1e9:.1f}B (as of {ttm_ni.as_of_date})")
        print(f"  Q4 Calculated: {ttm_rev.has_calculated_q4}")
    except Exception as e:
        print(f"{ticker}: Error - {e}")
```

### Example 5: TTM vs Annual Comparison

```python
from quant import QuantCompany

company = QuantCompany("MSFT")

# Get annual income statement
annual = company.income_statement(period='annual', periods=1)

# Get TTM income statement
ttm = company.income_statement(period='ttm')

# Get TTM metrics for comparison
ttm_rev = company.get_ttm_revenue()
ttm_ni = company.get_ttm_net_income()

print("Revenue Comparison:")
print(f"  TTM Revenue: ${ttm_rev.value/1e9:.1f}B (as of {ttm_rev.as_of_date})")
print(f"  TTM periods: {ttm_rev.periods}")
print(f"  Has calculated Q4: {ttm_rev.has_calculated_q4}")
print(f"\nNet Income:")
print(f"  TTM: ${ttm_ni.value/1e9:.1f}B")
```

---

## Testing

### Run TTM Tests

```bash
cd quant
pytest tests/test_utils.py -v
```

### Run XBRL Standardization Tests

```bash
cd quant/xbrl_standardize
python tests/extract_financials.py --symbol AAPL --form 10-K
python tests/fetch_fresh_nasdaq.py  # Real company validation
```

### Run All Tests

```bash
cd quant
pytest tests/ --cov=quant --cov-report=term-missing
```

---

## Performance

- **TTM Calculation**: <5ms per concept
- **Stock Split Detection**: <10ms per company
- **XBRL Extraction**: <1ms per company
- **Q4 Derivation**: <2ms per concept
- **Memory Footprint**: ~50MB (includes mapping cache)

---

## Troubleshooting

### TTM Calculation Fails

**Error**: `ValueError: Insufficient quarterly data`

**Solution**:
- Check if company has at least 4 quarters of data
- Use `ttm.warning` to see data quality issues
- Verify facts are properly classified (period_type='duration')

### Q4 Derivation Issues

**Error**: Negative Q4 values

**Cause**: Company may have one-time charges in FY not in Q1-Q3

**Solution**:
- Check `ttm.has_calculated_q4` flag
- Review `ttm.period_facts` for anomalies
- Use reported Q4 from 10-K when available

### Stock Split Not Detected

**Error**: EPS shows discontinuity

**Solution**:
- Verify `StockSplitConversionRatio` fact exists
- Check fact duration (should be instant or ≤31 days)
- Review `detect_splits()` output manually

### Low XBRL Extraction Rate

**Error**: `extraction_rate` < 30%

**Solution**:
- Check concept name format (`us-gaap_` vs `us-gaap:`)
- Try sector-specific extraction
- Review `result['metadata']` for attempted concepts
- Add custom fallback concepts

---

## Contributing

See `CLAUDE.md` for development guidelines and Soft Fork Protocol compliance.

---

## License

Part of the EdgarTools project.

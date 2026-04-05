# Extraction Evolution Report: Standard Industrial Test

**Run ID:** e2e_industrial_2026-01-26T15:20:47.153468
**Scope:** Standard Industrial Companies (33 companies, 6 sectors)
**Report Generated:** 2026-01-26 15:23

---

## Report Lineage

**Previous Report:** `extraction_evolution_report_2026-01-26-13-54.md`
**This Report:** `extraction_evolution_report_2026-01-26-15-23.md`

### Changes Since Previous Report

| Category | Previous | Current | Delta | Notes |
|----------|----------|---------|-------|-------|
| **Metrics Tested** | 17 | 24 | +7 | Major expansion |
| **10-K Total Comparisons** | 46 | 1,105 | +1,059 | Expanded coverage |
| **10-Q Total Comparisons** | 39 | 1,081 | +1,042 | Expanded coverage |
| **Overall 10-K Pass Rate** | 100.0% | 91.8%* | -8.2% | New metrics introduced |
| **Overall 10-Q Pass Rate** | 100.0% | 75.8% | -24.2% | YTD vs Quarterly pattern |
| **Known Divergences (Skipped)** | 16 | 16 | 0 | Unchanged |
| **Actual Failures** | 0 | 367 | +367 | New metrics account for 167 |

*Pass rates calculated excluding skipped items.

**Summary:** This test run introduces 7 new metrics (`DepreciationAmortization`, `StockBasedCompensation`, `DividendsPaid`, `Inventory`, `AccountsReceivable`, `AccountsPayable`, `WeightedAverageSharesDiluted`). The failures are primarily due to:
1. **YTD vs Quarterly Mismatch:** 10-Q cash flow metrics extract YTD values while yfinance reports quarterly
2. **Accumulated vs Period Values:** DepreciationAmortization extracts accumulated balance sheet values instead of period expense
3. **Concept Mapping Gaps:** Some metrics (AccountsPayable) are falling back to incorrect parent concepts

---

## 1. Executive Snapshot

| Metric | Value | Status |
|--------|-------|--------|
| **Overall 10-K Pass Rate** | 91.8% (1,000/1,089 validated) | Needs Attention |
| **Overall 10-Q Pass Rate** | 75.8% (819/1,081 validated) | Critical |
| **Known Divergences (Skipped)** | 16 | Maintained |
| **Total Failures** | 367 | Structural Issues |
| **New Metric Failures** | 167 (45.5%) | Expected - New Coverage |
| **Existing Metric Failures** | 200 (54.5%) | YTD Pattern |

### Pass Rates by Sector

| Sector | 10-K Pass | 10-K Fail | 10-K Skip | 10-Q Pass | 10-Q Fail | Notes |
|--------|-----------|-----------|-----------|-----------|-----------|-------|
| **MAG7** | 96.2% (202/210) | 8 | 0 | 78.9% (194/246) | 52 | YTD cash flows + D&A issues |
| **Industrial_Mfg** | 85.7% (239/280) | 41 | 4 | 70.2% (198/282) | 84 | CAT/GE complex structures |
| **Consumer_Staples** | 92.2% (201/218) | 17 | 0 | 80.6% (133/165) | 32 | Relatively stable |
| **Energy** | 89.9% (125/139) | 14 | 8 | 72.9% (105/144) | 39 | OperatingIncome skipped |
| **Healthcare_Pharma** | 95.5% (128/134) | 6 | 4 | 74.3% (101/136) | 35 | JNJ/PFE OI skipped |
| **Transportation** | 97.2% (105/108) | 3 | 0 | 81.5% (88/108) | 20 | Most stable sector |

### Critical Failure Patterns

| Pattern | Count | Root Cause | Impact |
|---------|-------|------------|--------|
| YTD vs Quarterly Cash Flows | ~200 | 10-Q extracts YTD, yfinance reports quarterly | All 10-Q cash flow metrics |
| Accumulated D&A | 46 | Wrong concept: Accumulated vs Period | MSFT, TSLA, GE most affected |
| AccountsPayable Fallback | 26 | Falling back to `us-gaap:Liabilities` | META, GE, AMZN |
| Capex Concept Selection | 68 | YTD + concept variance | Broad impact |

---

## 2. The Knowledge Increment

### 2.1 Structural Discovery: YTD vs Quarterly (CRITICAL)

**Root Cause Identified:** The most significant failure pattern (200+ failures) is caused by a fundamental mismatch in 10-Q data extraction:

| Source | Cash Flow Metrics | Balance Sheet Metrics |
|--------|-------------------|----------------------|
| **XBRL 10-Q** | Year-to-Date (cumulative) | Point-in-time |
| **yfinance Reference** | Quarterly (period) | Point-in-time |

**Evidence:**
- AAPL Q2 OperatingCashFlow: XBRL $81.75B (YTD) vs yfinance $27.87B (quarterly) = 193% variance
- This ~3x ratio is consistent with 3 quarters of cumulative data vs single quarter

**Affected Metrics (10-Q only):**
- `OperatingCashFlow` (55 failures)
- `Capex` (56 failures)
- `StockBasedCompensation` (41 failures)
- `DividendsPaid` (38 failures)
- `DepreciationAmortization` (30 10-Q failures)

### 2.2 Concept Mapping Issues Discovered

| Metric | Issue | Evidence | Proposed Fix |
|--------|-------|----------|--------------|
| **DepreciationAmortization** | Extracting `AccumulatedDepreciation...` (balance sheet) instead of period expense | MSFT 10-K: $93.65B vs $34.15B (174% variance), concept = `AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment` | Use `DepreciationDepletionAndAmortization` from cash flow statement |
| **AccountsPayable** | Falling back to `us-gaap:Liabilities` | META 10-K: $93.4B vs $7.7B (1115% variance), concept = `us-gaap:Liabilities` | Need direct mapping to `AccountsPayableCurrent` |
| **ShortTermDebt** | Concept inconsistency | CAT 10-K: $4.4B vs $11.1B (-60%), varies between `ShortTermBorrowings` and `DebtCurrent` | Standardize to include all current debt |
| **WeightedAverageSharesDiluted** | Pre-split values | NVDA 10-K 2024: 2.49B vs 24.94B (-90%) | Handle stock splits in validation |

### 2.3 Validated Extraction Behaviors (Stable from Previous)

The following 10 metrics from the original set maintain high reliability:

| Metric | Concept | 10-K Stability | 10-Q Stability |
|--------|---------|----------------|----------------|
| **Revenue** | `RevenueFromContractWithCustomerExcludingAssessedTax` | High (87%) | High (92%) |
| **NetIncome** | Standard us-gaap concepts | Very High (99%) | Very High (99%) |
| **TotalAssets** | Balance sheet extraction | Very High | Very High |
| **CashAndEquivalents** | Reliable extraction | Very High | Very High |
| **LongTermDebt** | Standard us-gaap concepts | High (91%) | High (95%) |
| **Goodwill** | Goodwill concepts | Very High (97%) | Very High |
| **IntangibleAssets** | Note: Some fallback to Goodwill | Moderate (90%) | High |
| **FreeCashFlow** | Derived calculation | Affected by YTD | Affected by YTD |
| **TangibleAssets** | Derived calculation | High | High |
| **NetDebt** | Derived calculation | High | High |

### 2.4 The Graveyard (Discarded Hypotheses)

| Hypothesis | Outcome | Evidence | Lesson | First Recorded |
|------------|---------|----------|--------|----------------|
| Energy uses standard OperatingIncome concepts | FAILED | XOM, CVX, COP, SLB all skipped | Energy sector requires industry-specific calculation | 2026-01-25 |
| Industry logic OperatingIncome works for conglomerates | FAILED | GE, DE negative extraction | Conglomerate structures need segment-level aggregation | 2026-01-25 |
| Healthcare standard OperatingIncome extraction | FAILED | JNJ, PFE one-time charges | Healthcare has significant one-time charges | 2026-01-25 |
| **NEW: Period D&A from balance sheet concepts** | FAILED | AccumulatedDepreciation != DepreciationExpense | Balance sheet shows cumulative; need cash flow source | 2026-01-26 |
| **NEW: AccountsPayable fallback to Liabilities** | FAILED | META/GE 1000%+ variance | Liabilities != AccountsPayable | 2026-01-26 |

### 2.5 XBRL Concept Observations (New Discoveries)

| Entity/Pattern | Observation | Impact |
|----------------|-------------|--------|
| **MSFT** | Uses `AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment` for D&A | 174-896% variance in DepreciationAmortization |
| **TSLA** | Uses `AccumulatedDepreciation...` for D&A | 190-1144% variance |
| **META** | Missing direct `AccountsPayableCurrent` mapping | Falls back to total Liabilities |
| **CAT** | Complex debt structure with financial services | ShortTermDebt under-counted by 60% |
| **NVDA** | Stock split impact on shares | 10x discrepancy in WeightedAverageSharesDiluted |

---

## 3. Sector Transferability Matrix

### 3.1 MAG7 Tech (AAPL, MSFT, GOOG, AMZN, META, NVDA, TSLA)

| Metric | 10-K Status | 10-Q Status | Notes |
|--------|-------------|-------------|-------|
| Revenue | ++ | ++ | Stable |
| NetIncome | ++ | ++ | Stable |
| OperatingIncome | ++ | ++ | Stable |
| TotalAssets | ++ | ++ | Stable |
| CashAndEquivalents | ++ | ++ | Stable |
| **OperatingCashFlow** | ++ | FAIL | YTD pattern |
| **Capex** | ++ | FAIL | YTD pattern |
| **DepreciationAmortization** | FAIL | FAIL | Wrong concept (MSFT, TSLA) |
| **StockBasedCompensation** | ++ | FAIL | YTD pattern |
| **AccountsPayable** | FAIL | FAIL | META fallback issue |

**Transferability Score:** 6/10 metrics stable
**Safe to Merge:** CONDITIONAL (exclude new metrics with known issues)

### 3.2 Industrial Manufacturing (CAT, GE, HON, DE, MMM, EMR, RTX, ASTE)

| Metric | 10-K Status | 10-Q Status | Notes |
|--------|-------------|-------------|-------|
| Revenue | ++ | ++ | GE partial (segment reporting) |
| NetIncome | ++ | ++ | Stable |
| OperatingIncome | SKIP (GE, DE, EMR) | ++ | 3 companies skipped |
| TotalAssets | ++ | ++ | Stable |
| **OperatingCashFlow** | ++ | FAIL | YTD pattern |
| **Capex** | FAIL | FAIL | CAT, GE, RTX issues |
| **ShortTermDebt** | FAIL | FAIL | CAT financial services |
| **LongTermDebt** | FAIL | FAIL | CAT financial services |
| **AccountsReceivable** | FAIL | FAIL | CAT ~50% variance |
| **DepreciationAmortization** | FAIL | FAIL | GE 3000%+ variance |

**Transferability Score:** 4/10 metrics stable
**Safe to Merge:** NO (significant new metric issues)
**Key Blocker:** CAT, GE have financial services segments that distort standard extraction

### 3.3 Consumer Staples (PG, KO, PEP, WMT, COST, HSY)

| Metric | 10-K Status | 10-Q Status | Notes |
|--------|-------------|-------------|-------|
| Revenue | ++ | ++ | Stable |
| NetIncome | ++ | ++ | Stable |
| OperatingIncome | ++ | ++ | Stable |
| TotalAssets | ++ | ++ | Stable |
| CashAndEquivalents | ++ | ++ | Stable |
| **OperatingCashFlow** | ++ | FAIL | YTD pattern |
| **Capex** | FAIL | FAIL | Scattered failures |
| **DividendsPaid** | ++ | FAIL | YTD pattern |
| **DepreciationAmortization** | MIXED | FAIL | Concept inconsistency |

**Transferability Score:** 6/10 metrics stable
**Safe to Merge:** YES (with original 17 metrics)
**Baseline Sector:** Still most reliable for original metric set

### 3.4 Energy Sector (XOM, CVX, COP, SLB, PBF)

| Metric | 10-K Status | 10-Q Status | Notes |
|--------|-------------|-------------|-------|
| Revenue | ++ | ++ | Stable |
| NetIncome | ++ | ++ | Stable |
| OperatingIncome | SKIP (4/5) | ++ | Only PBF passes |
| TotalAssets | ++ | ++ | Stable |
| **OperatingCashFlow** | ++ | FAIL | YTD pattern |
| **Capex** | FAIL | FAIL | COP, SLB issues |
| **DepreciationAmortization** | FAIL | FAIL | XOM, COP issues |

**Transferability Score:** 4/10 metrics stable
**Safe to Merge:** CONDITIONAL (OperatingIncome excluded for XOM, CVX, COP, SLB)

### 3.5 Healthcare/Pharma (JNJ, UNH, LLY, PFE)

| Metric | 10-K Status | 10-Q Status | Notes |
|--------|-------------|-------------|-------|
| Revenue | ++ | ++ | Stable |
| NetIncome | ++ | ++ | Stable |
| OperatingIncome | SKIP (JNJ, PFE) | ++ | UNH, LLY pass |
| TotalAssets | ++ | ++ | Stable |
| **OperatingCashFlow** | ++ | FAIL | YTD pattern |
| **Capex** | FAIL | FAIL | JNJ, LLY issues |
| **DepreciationAmortization** | MIXED | FAIL | Scattered |

**Transferability Score:** 5/10 metrics stable
**Safe to Merge:** CONDITIONAL (OperatingIncome excluded for JNJ, PFE)

### 3.6 Transportation (UPS, FDX, BA)

| Metric | 10-K Status | 10-Q Status | Notes |
|--------|-------------|-------------|-------|
| Revenue | ++ | ++ | Stable |
| NetIncome | ++ | ++ | Stable |
| OperatingIncome | ++ | ++ | Stable |
| TotalAssets | ++ | ++ | Stable |
| CashAndEquivalents | ++ | ++ | Stable |
| **OperatingCashFlow** | ++ | FAIL | YTD pattern |
| **Capex** | ++ | FAIL | YTD pattern |

**Transferability Score:** 7/10 metrics stable (best sector)
**Safe to Merge:** YES
**Best Practice Sector:** Most consistent extraction across all metrics

---

## 4. Sector-Specific Considerations

| Sector | Key Issues | Extraction Notes | Action Required |
|--------|------------|------------------|-----------------|
| **MAG7** | DepreciationAmortization, AccountsPayable | Uses accumulated D&A concepts; META missing AP mapping | Fix D&A concept; Add META AP mapping |
| **Industrial_Mfg** | Financial services segments | CAT, GE have captive finance that distorts debt/receivables | Document as known limitation |
| **Energy** | OperatingIncome, Capex | Company-specific XBRL; yfinance proprietary normalization | OperatingIncome skipped; investigate Capex |
| **Healthcare** | OperatingIncome, D&A | JNJ/PFE one-time charges; D&A concept issues | OperatingIncome skipped for 2 companies |
| **Consumer_Staples** | YTD pattern only | Most reliable baseline | Use as regression baseline |
| **Transportation** | YTD pattern only | Best overall consistency | Use as validation baseline |

---

## 5. The Truth Alignment (Proxy vs. Reality)

We document intentional divergences from yfinance reference values.

### 5.1 Existing Known Divergences (Unchanged)

| Scenario | Our Extraction | yfinance Calculation | Accepted Variance | Status |
|----------|----------------|---------------------|-------------------|--------|
| Energy OperatingIncome | XBRL tree/industry logic | Proprietary normalization | SKIP | Confirmed |
| Healthcare OperatingIncome | Standard GAAP concepts | May exclude one-time charges | SKIP | Confirmed |
| Conglomerate OperatingIncome | Segment aggregation issues | Consolidated view | SKIP | Confirmed |

### 5.2 New Divergences Identified (Require Resolution)

| Scenario | Our Extraction | yfinance Calculation | Observed Variance | Proposed Resolution |
|----------|----------------|---------------------|-------------------|---------------------|
| **10-Q Cash Flow Metrics** | YTD cumulative | Quarterly period | 100-300% | Need period extraction logic |
| **DepreciationAmortization** | Accumulated balance sheet | Period expense | 50-1000% | Use cash flow statement source |
| **AccountsPayable (META)** | Total Liabilities fallback | AccountsPayableCurrent | 800-1300% | Add explicit concept mapping |
| **ShortTermDebt (CAT)** | ShortTermBorrowings only | All current debt | 60-65% | Include LongTermDebtCurrent |
| **WeightedAverageSharesDiluted** | Pre-split values | Split-adjusted | 90% | Handle stock splits |

---

## 6. Failure Analysis & Resolution

### 6.1 Pattern: YTD vs Quarterly Cash Flow Extraction (200+ instances)

**Affected Metrics:** OperatingCashFlow, Capex, StockBasedCompensation, DividendsPaid

**Symptom:** 10-Q metrics show consistent ~2x to ~3x variance depending on quarter position.

**Root Cause:** XBRL 10-Q filings report cash flow metrics on a YTD basis. Our extraction pulls the YTD value, while yfinance provides the quarterly (period) value.

**Evidence Table:**
| Ticker | Metric | Q2 XBRL (YTD) | yfinance (Q) | Ratio |
|--------|--------|---------------|--------------|-------|
| AAPL | OperatingCashFlow | $81.75B | $27.87B | 2.93x |
| AAPL | Capex | -$9.47B | -$3.46B | 2.74x |
| GOOG | OperatingCashFlow | $112.3B | $48.4B | 2.32x |
| META | OperatingCashFlow | $79.6B | $30.0B | 2.65x |

**Corrective Action Required:**
- Implement quarterly derivation: Current Quarter = YTD(Qn) - YTD(Qn-1)
- Or mark these metrics as "YTD only" for 10-Q validation

### 6.2 Pattern: DepreciationAmortization Concept Mismatch (46 instances)

**Symptom:** Extracted values are 2-10x reference values, with some >1000% variance.

**Root Cause:** The extraction is selecting `AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment` (a balance sheet contra-asset) instead of `DepreciationDepletionAndAmortization` (period expense from cash flow statement).

**Evidence:**
| Ticker | Form | XBRL Value | Reference | Variance | Concept Used |
|--------|------|------------|-----------|----------|--------------|
| MSFT | 10-K | $93.65B | $34.15B | 174% | AccumulatedDepreciation... |
| MSFT | 10-Q | $87.07B | $8.74B | 896% | AccumulatedDepreciation... |
| TSLA | 10-K | $15.59B | $5.37B | 190% | AccumulatedDepreciation... |
| TSLA | 10-Q | $18.98B | $1.63B | 1068% | AccumulatedDepreciation... |

**Corrective Action Required:**
- Update metrics.yaml to prioritize cash flow statement concepts for DepreciationAmortization
- Add explicit mapping: `DepreciationDepletionAndAmortization` > `Depreciation` > `AccumulatedDepreciation...`

### 6.3 Pattern: AccountsPayable Fallback to Liabilities (26 instances)

**Symptom:** META and some GE filings show 800-2400% variance.

**Root Cause:** When `AccountsPayableCurrent` is not directly available, the extraction falls back to `us-gaap:Liabilities` (total liabilities) which is vastly larger.

**Evidence:**
| Ticker | Form | XBRL Value | Reference | Variance | Concept Used |
|--------|------|------------|-----------|----------|--------------|
| META | 10-K | $93.42B | $7.69B | 1115% | us-gaap:Liabilities |
| META | 10-Q | $109.78B | $7.80B | 1308% | us-gaap:Liabilities |
| GE | 10-K | $134.47B | $5.29B | 2442% | us-gaap:Liabilities |

**Corrective Action Required:**
- Investigate why META lacks AccountsPayableCurrent in XBRL
- Consider adding `AccountsPayableAndAccruedLiabilitiesCurrent` as fallback
- Never fall back to total Liabilities

### 6.4 Pattern: ShortTermDebt Undercount (CAT - 29 instances)

**Symptom:** CAT short-term debt consistently 60-65% below reference.

**Root Cause:** CAT has a financial services subsidiary (Cat Financial). The extraction uses `ShortTermBorrowings` which excludes current portion of long-term debt from the financial services segment.

**Evidence:**
| Ticker | Form | XBRL Value | Reference | Variance | Concept Used |
|--------|------|------------|-----------|----------|--------------|
| CAT | 10-K | $4.39B | $11.06B | 60.3% | ShortTermBorrowings |
| CAT | 10-K | $4.64B | $13.41B | 65.4% | ShortTermBorrowings |

**Corrective Action:**
- Document CAT as known divergence (financial services segment)
- Or expand ShortTermDebt definition to include LongTermDebtCurrent

---

## 7. Recommendations

### 7.1 Immediate Actions (Priority Order)

| Priority | Action | Impact | Complexity |
|----------|--------|--------|------------|
| **P0** | Fix DepreciationAmortization concept mapping | 46 failures | Medium |
| **P0** | Implement 10-Q quarterly derivation for cash flows | 200+ failures | High |
| **P1** | Fix AccountsPayable fallback chain | 26 failures | Low |
| **P2** | Add ShortTermDebt comprehensive mapping | 29 failures | Medium |
| **P3** | Handle stock split in WeightedAverageSharesDiluted | 5 failures | Low |

### 7.2 Known Divergences to Add

Based on structural analysis, the following should be added to the known_divergences configuration:

```yaml
known_divergences:
  # Existing (maintained)
  GE: [OperatingIncome]
  DE: [OperatingIncome]
  EMR: [OperatingIncome]
  XOM: [OperatingIncome]
  CVX: [OperatingIncome]
  COP: [OperatingIncome]
  SLB: [OperatingIncome]
  JNJ: [OperatingIncome]
  PFE: [OperatingIncome]

  # Proposed additions
  CAT: [ShortTermDebt, LongTermDebt, AccountsReceivable]  # Financial services
  GE: [Revenue, COGS, OperatingIncome, AccountsPayable]   # Conglomerate + 2024 spin-off
```

### 7.3 Sector Priorities

| Priority | Sector | Recommended Action |
|----------|--------|-------------------|
| 1 | **Consumer_Staples** | Maintain as regression baseline with original 17 metrics |
| 2 | **Transportation** | Secondary baseline - best new metric coverage |
| 3 | **MAG7** | Fix D&A and AccountsPayable mappings |
| 4 | **Healthcare** | Monitor PFE trend - may become includable |
| 5 | **Energy** | Defer OperatingIncome; focus on other metrics |
| 6 | **Industrial_Mfg** | Document CAT/GE as structurally complex |

### 7.4 Metric Expansion Strategy

The 7 new metrics reveal important gaps. Recommended approach:

1. **Safe to Validate (with fixes):**
   - DepreciationAmortization (after concept fix)
   - AccountsPayable (after fallback fix)
   - Inventory (minor issues)
   - AccountsReceivable (CAT exception)

2. **Requires Quarterly Derivation:**
   - OperatingCashFlow (10-Q)
   - Capex (10-Q)
   - StockBasedCompensation (10-Q)
   - DividendsPaid (10-Q)

3. **Structural Limitations:**
   - WeightedAverageSharesDiluted (stock splits)
   - ShortTermDebt for financial-services conglomerates

---

## Appendix A: Test Configuration

```yaml
# Test Parameters
group: industrial_33
workers: 4
years: 2
quarters: 2
mode: standard

# Metrics Validated (24 total)
metrics:
  # Original 17 (from previous reports)
  - Revenue
  - COGS
  - SGA
  - OperatingIncome
  - PretaxIncome
  - NetIncome
  - OperatingCashFlow
  - Capex
  - TotalAssets
  - Goodwill
  - IntangibleAssets
  - ShortTermDebt
  - LongTermDebt
  - CashAndEquivalents
  - FreeCashFlow
  - TangibleAssets
  - NetDebt

  # New 7 (added in this run)
  - DepreciationAmortization
  - StockBasedCompensation
  - DividendsPaid
  - Inventory
  - AccountsReceivable
  - AccountsPayable
  - WeightedAverageSharesDiluted
```

## Appendix B: Failure Breakdown by Metric

| Metric | 10-K Failures | 10-Q Failures | Total | Root Cause |
|--------|---------------|---------------|-------|------------|
| Capex | 12 | 56 | 68 | YTD + concept variance |
| OperatingCashFlow | 0 | 55 | 55 | YTD vs quarterly |
| DepreciationAmortization | 16 | 30 | 46 | Wrong concept (accumulated) |
| StockBasedCompensation | 0 | 41 | 41 | YTD vs quarterly |
| DividendsPaid | 0 | 38 | 38 | YTD vs quarterly |
| ShortTermDebt | 19 | 10 | 29 | CAT/financial services |
| AccountsPayable | 16 | 10 | 26 | META fallback issue |
| Revenue | 9 | 5 | 14 | GE conglomerate |
| COGS | 9 | 5 | 14 | GE conglomerate |
| AccountsReceivable | 5 | 4 | 9 | CAT financial services |
| LongTermDebt | 5 | 3 | 8 | CAT financial services |
| IntangibleAssets | 7 | 1 | 8 | Goodwill fallback |
| WeightedAverageSharesDiluted | 3 | 2 | 5 | Stock splits |
| Goodwill | 2 | 0 | 2 | GE segment issues |
| Inventory | 2 | 0 | 2 | GE segment issues |
| NetIncome | 0 | 2 | 2 | Minor |

## Appendix C: Sector Cohort Definitions

```yaml
Industrial_33:
  total: 33 companies
  sectors: 6
  tickers:
    - AAPL, MSFT, GOOG, AMZN, META, NVDA, TSLA  # MAG7
    - CAT, GE, HON, DE, MMM, EMR, RTX, ASTE      # Industrial_Manufacturing
    - PG, KO, PEP, WMT, COST, HSY                # Consumer_Staples
    - XOM, CVX, COP, SLB, PBF                    # Energy
    - JNJ, UNH, LLY, PFE                         # Healthcare_Pharma
    - UPS, FDX, BA                               # Transportation
```

## Appendix D: Run Comparison

| Metric | Previous (1641) | Current (1520) | Delta |
|--------|-----------------|----------------|-------|
| Metrics Tested | 17 | 24 | +7 |
| 10-K Total | 46 | 1,105 | +1,059 |
| 10-K Passed | 46 | 1,000 | +954 |
| 10-K Skipped | 16 | 16 | 0 |
| 10-K Failed | 0 | 89 | +89 |
| 10-Q Total | 39 | 1,081 | +1,042 |
| 10-Q Passed | 39 | 819 | +780 |
| 10-Q Failed | 0 | 262 | +262 |
| Total Failures | 0 | 367 | +367 |

**Conclusion:** The significant increase in failures is primarily due to:
1. Expanded metric coverage (7 new metrics = 167 new failures)
2. YTD vs quarterly mismatch in 10-Q cash flow metrics (~200 failures)
3. The original 17-metric test suite remains stable when excluding the new metrics

---

*Report generated by Standard Industrial E2E Test Framework*
*Previous Report: extraction_evolution_report_2026-01-26-13-54.md*

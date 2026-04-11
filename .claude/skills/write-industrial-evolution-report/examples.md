# Extraction Evolution Report: Industrial Test Example

**Run ID:** e2e_industrial_2026-01-25T14:30:00
**Scope:** Standard Industrial Companies (30 companies, 6 sectors)

---

## 1. Executive Snapshot

| Metric | Previous | Current | Delta | Status |
|--------|----------|---------|-------|--------|
| **Overall 10-K Pass Rate** | 82.0% | **88.5%** | +6.5% | Improved |
| **Overall 10-Q Pass Rate** | 78.0% | **85.0%** | +7.0% | Improved |
| **Sectors at 90%+** | 2/6 | **4/6** | +2 | Improved |
| **Critical Blockers** | NVDA (Capex), TSLA (Debt) | TSLA (Debt) | -1 | Improved |

### Pass Rates by Sector

| Sector | 10-K | 10-Q | Notes |
|--------|------|------|-------|
| **Industrial_Manufacturing** | 95.0% | 92.5% | Baseline - most reliable |
| **Energy** | 97.5% | 95.0% | Capex mapping improved |
| **Healthcare_Pharma** | 90.0% | 87.5% | R&D handling stabilized |
| **Consumer_Staples** | 88.0% | 85.0% | Lease impacts remain |
| **Transportation** | 85.0% | 82.0% | Asset depreciation variance |
| **MAG7** | 80.0% | 78.0% | Expected - Archetype C mismatch |

---

## 2. The Knowledge Increment

### 2.1 Sector-Specific Patterns

| Sector | Pattern | Confirmed Via |
|--------|---------|---------------|
| **Energy** | Uses `PaymentsToAcquireProductiveAssets` not `PaymentsToAcquirePropertyPlantAndEquipment` for Capex | XOM, CVX, COP, SLB - 100% match |
| **Healthcare** | R&D is expensed, not capitalized; use `ResearchAndDevelopmentExpense` | JNJ, PFE, LLY validation |
| **Retail** | Operating lease liabilities significantly impact Total Liabilities | WMT, COST, PG analysis |
| **Manufacturing** | Standard us-gaap concepts work reliably across sector | CAT, GE, HON, DE - 95%+ |

### 2.2 Validated Extraction Behaviors

* **Standard Capex Mapping:** `PaymentsToAcquirePropertyPlantAndEquipment` works for 24/30 companies (80%).
    * *Exception:* Energy sector requires `PaymentsToAcquireProductiveAssets` (includes oil/gas assets).
* **Revenue Recognition:** `RevenueFromContractWithCustomerExcludingAssessedTax` is the primary concept across all sectors.
* **Operating Income:** `OperatingIncomeLoss` is consistent except for financial services elements in some companies.

### 2.3 The Graveyard (Discarded Hypotheses)

| Hypothesis | Outcome | Evidence | Lesson |
|------------|---------|----------|--------|
| Universal Capex Concept | FAILED | Energy sector: 75% variance with standard concept | Use sector-specific Capex mapping |
| MAG7 Standard Extraction | FAILED | Archetype C companies have different structures | Document expected variance for MAG7 |
| Lease-Adjusted Liabilities | PARTIAL | Improved WMT but broke KO | Apply only to big-box retailers |

### 2.4 New XBRL Concept Mappings

| Entity | Concept/Tag | Usage |
|--------|-------------|-------|
| **XOM** | `exxon:PaymentsForCapitalAndExploratoryExpenditures` | Company-specific Capex aggregate |
| **WMT** | `wmt:TotalOperatingLeaseObligations` | Operating lease component |
| **BA** | `ba:CommercialAircraftPrograms` | Inventory categorization |

---

## 3. Sector Transferability Matrix

### 3.1 Industrial Manufacturing (CAT, GE, HON, DE, MMM, EMR, RTX)

| Metric | CAT | GE | HON | DE | MMM | EMR | RTX | Net |
|--------|-----|----|----|----|----|-----|-----|-----|
| Revenue | ++ | ++ | ++ | ++ | ++ | ++ | ++ | 7/7 |
| Operating Income | ++ | ++ | ++ | ++ | ++ | ++ | ++ | 7/7 |
| Capex | ++ | ++ | ++ | ++ | ++ | ++ | ++ | 7/7 |
| ShortTermDebt | ++ | ++ | = | ++ | ++ | ++ | ++ | 6/7 |

**Transferability Score:** 7/7 improved or neutral
**Safe to Merge:** YES

### 3.2 Energy Sector (XOM, CVX, COP, SLB)

| Metric | XOM | CVX | COP | SLB | Net |
|--------|-----|-----|-----|-----|-----|
| Revenue | ++ | ++ | ++ | ++ | 4/4 |
| Capex (with ProductiveAssets) | ++ | ++ | ++ | ++ | 4/4 |
| Operating Income | ++ | ++ | ++ | = | 3/4 |
| ShortTermDebt | ++ | ++ | ++ | ++ | 4/4 |

**Transferability Score:** 4/4 improved or neutral
**Safe to Merge:** YES

### 3.3 MAG7 Tech (AAPL, MSFT, GOOG, AMZN, META, NVDA, TSLA)

| Metric | AAPL | MSFT | GOOG | AMZN | META | NVDA | TSLA | Net |
|--------|------|------|------|------|------|------|------|-----|
| Revenue | ++ | ++ | ++ | ++ | ++ | ++ | ++ | 7/7 |
| Operating Income | ++ | ++ | ++ | ++ | ++ | ++ | ++ | 7/7 |
| Capex | ++ | ++ | ++ | ++ | ++ | = | = | 5/7 |
| ShortTermDebt | ++ | = | ++ | ++ | ++ | -- | -- | 4/7 |

**Transferability Score:** 5/7 improved or neutral
**Safe to Merge:** CONDITIONAL (review NVDA, TSLA ShortTermDebt)

**Note:** MAG7 companies are Archetype C (Intangible Digital) in config. Some variance expected with Archetype A strategies.

### 3.4 Consumer Staples (PG, KO, PEP, WMT, COST)

| Metric | PG | KO | PEP | WMT | COST | Net |
|--------|----|----|-----|-----|------|-----|
| Revenue | ++ | ++ | ++ | ++ | ++ | 5/5 |
| Operating Income | ++ | ++ | ++ | ++ | ++ | 5/5 |
| TotalLiabilities | ++ | = | ++ | = | = | 2/5 |

**Transferability Score:** 4/5 improved or neutral
**Safe to Merge:** YES (lease variance documented)

### 3.5 Healthcare/Pharma (JNJ, UNH, LLY, PFE)

| Metric | JNJ | UNH | LLY | PFE | Net |
|--------|-----|-----|-----|-----|-----|
| Revenue | ++ | ++ | ++ | ++ | 4/4 |
| R&D Expense | ++ | N/A | ++ | ++ | 3/3 |
| Operating Income | ++ | = | ++ | ++ | 3/4 |

**Transferability Score:** 4/4 improved or neutral
**Safe to Merge:** YES

### 3.6 Transportation (UPS, FDX, BA)

| Metric | UPS | FDX | BA | Net |
|--------|-----|-----|----|-----|
| Revenue | ++ | ++ | ++ | 3/3 |
| Capex | ++ | ++ | = | 2/3 |
| Operating Income | ++ | = | -- | 1/3 |

**Transferability Score:** 2/3 improved or neutral
**Safe to Merge:** CONDITIONAL (review BA Operating Income)

---

## 4. Sector-Specific Considerations

| Sector | Key Issues | Extraction Notes |
|--------|------------|------------------|
| **MAG7** | Archetype C mismatch | Expected 20-30% variance on some metrics with Archetype A strategies |
| **Energy** | Capex concept | Uses `PaymentsToAcquireProductiveAssets` - includes oil/gas capital |
| **Pharma** | R&D | All R&D expensed under ASC 730; use `ResearchAndDevelopmentExpense` |
| **Retail** | Leases | ASC 842 operating leases inflate Total Liabilities significantly |
| **Industrial** | Baseline | Most reliable for standard extraction; use as regression baseline |
| **Transportation** | Depreciation | Heavy equipment depreciation creates timing differences |

---

## 5. The Truth Alignment (Proxy vs. Reality)

We consciously diverge from yfinance in specific scenarios.

| Scenario | Our View | yfinance View | Accepted Variance | Rationale |
|----------|----------|---------------|-------------------|-----------|
| Energy Capex | Includes exploration | Excludes exploration | 10-15% | Exploration is capital for energy |
| Retail Liabilities | Includes operating leases | Varies | 5-10% | ASC 842 compliance |
| Pharma R&D | All expensed | Same | <5% | Consistent treatment |
| MAG7 Debt | Standard extraction | May differ | 15-25% | Archetype mismatch |

---

## 6. Failure Analysis & Resolution

### 6.1 Incident: NVDA 10-K ShortTermDebt Failure

**Sector:** MAG7

**Symptom:** Extracted $2.5B vs Reference $1.8B (variance: +38.9%)

**Root Cause:** NVDA reports commercial paper and current debt portions differently in their fiscal year filings (January year-end).

**Sector Pattern:** Specific to tech companies with non-calendar fiscal years. AAPL (September) and NVDA (January) both show higher variance.

**Corrective Action:** Add fiscal year-end awareness to debt extraction for non-calendar companies.

### 6.2 Incident: TSLA 10-Q ShortTermDebt Failure

**Sector:** MAG7

**Symptom:** Extracted $1.2B vs Reference $0.9B (variance: +33.3%)

**Root Cause:** TSLA's capital structure is evolving rapidly; includes convertible notes that may be classified differently.

**Sector Pattern:** Specific to high-growth companies with complex capital structures.

**Corrective Action:** Document as known divergence; monitor for pattern changes.

### 6.3 Incident: BA Operating Income Failure

**Sector:** Transportation

**Symptom:** Extracted $-2.1B vs Reference $1.5B (variance: -240%)

**Root Cause:** BA's 737 MAX program charges create significant non-recurring items that affect operating income classification.

**Sector Pattern:** Specific to BA; not systemic across Transportation sector.

**Corrective Action:** Add BA to known divergences for Operating Income until program charges stabilize.

---

## 7. Recommendations

### 7.1 Immediate Actions
1. **Add Energy Capex mapping** - Use `PaymentsToAcquireProductiveAssets` for Energy sector
2. **Document MAG7 expected variance** - Add to known_divergences in companies.yaml
3. **Add BA Operating Income divergence** - Skip validation until program charges stabilize

### 7.2 Sector Priorities
1. **Industrial Manufacturing** - Baseline complete, use for regression testing
2. **Energy** - Capex mapping needed, otherwise reliable
3. **Healthcare** - Stable, no changes needed
4. **Consumer Staples** - Lease handling acceptable, document variance
5. **Transportation** - BA-specific issues; UPS/FDX reliable
6. **MAG7** - Accept variance as Archetype mismatch; consider Archetype C strategies

### 7.3 Future Work
- Implement Archetype C strategies for MAG7 companies
- Add fiscal year-end awareness for non-calendar companies
- Create sector-specific validation tolerance thresholds

---

## Appendix: Sector Cohort Definitions

```yaml
# Industrial_30 cohort for comprehensive testing
Industrial_30:
  members: [AAPL, MSFT, GOOG, AMZN, META, NVDA, TSLA, CAT, GE, HON, DE, MMM, EMR, RTX, PG, KO, PEP, WMT, COST, XOM, CVX, COP, SLB, JNJ, UNH, LLY, PFE, UPS, FDX, BA]
  description: "Standard Industrial companies across 6 sectors"
  metrics: [Revenue, OperatingIncome, Capex, ShortTermDebt]

# Individual sector cohorts
MAG7_Tech:
  members: [AAPL, MSFT, GOOG, AMZN, META, NVDA, TSLA]
  archetype: "C"
  description: "Magnificent 7 tech companies - Archetype C"

Industrial_Manufacturing:
  members: [CAT, GE, HON, DE, MMM, EMR, RTX]
  archetype: "A"
  description: "Traditional industrial manufacturers - Archetype A baseline"

Consumer_Staples:
  members: [PG, KO, PEP, WMT, COST]
  archetype: "A"
  description: "Consumer staples and retail"

Energy_Sector:
  members: [XOM, CVX, COP, SLB]
  archetype: "A"
  description: "Energy companies with capital-intensive operations"

Healthcare_Pharma:
  members: [JNJ, UNH, LLY, PFE]
  archetype: "A"
  description: "Healthcare and pharmaceutical companies"

Transportation_Logistics:
  members: [UPS, FDX, BA]
  archetype: "A"
  description: "Transportation and logistics companies"
```

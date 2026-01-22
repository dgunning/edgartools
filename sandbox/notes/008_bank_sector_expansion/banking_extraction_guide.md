# Banking Data Extraction: A Developer's Guide

**Target Audience:** Senior Engineers / Data Architects
**Scope:** Extraction, processing, and validation of financial data for Global Systemically Important Banks (GSIBs).

---

## 1. Executive Summary

Standardizing financial data for banks is fundamentally different from non-financial corporates. The standard XBRL "GAAP" tags often misrepresent the economic reality of a bank's balance sheet.

For example:
- **Cash** is not just "Cash and Cash Equivalents" but includes Fed deposits, interbank placements, and segregated regulatory cash.
- **Short-Term Debt** is not just "Short-Term Borrowings" but a specific "Street View" that excludes operational funding (like customer deposits) and includes economic leverage (like Net Repos for dealers).

This system implements a **Dual-Track Extraction Architecture** that serves two distinct purposes:
1. **GAAP Track** - For validation against external sources (yfinance)
2. **Street View Track** - For our investment-grade database with economic leverage

---

## 2. Architecture: The Dual-Track Extraction System

### 2.1 Philosophy: Why Two Tracks?

**Key Insight:** We do NOT need our metrics to be identical to yfinance. Our database serves investment analysts who need "economic leverage" views, not strict GAAP compliance.

However, we use yfinance validation to **prove we understand the EDGAR API**. If we can reproduce yfinance values in GAAP mode, we have confidence our Street View is intentionally different, not accidentally wrong.

```
                    ┌─────────────────────────────────────────┐
                    │        BankingExtractor                  │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
         ┌─────────────────────┐           ┌─────────────────────┐
         │   GAAP Track        │           │   Street View Track │
         │   mode='gaap'       │           │   mode='street'     │
         └─────────────────────┘           └─────────────────────┘
                    │                                   │
                    ▼                                   ▼
         ┌─────────────────────┐           ┌─────────────────────┐
         │ For VALIDATION      │           │ For DATABASE        │
         │ - Matches yfinance  │           │ - Economic leverage │
         │ - Proves API        │           │ - Includes Net Repos│
         │   understanding     │           │ - Analyst convention│
         └─────────────────────┘           └─────────────────────┘
```

### 2.2 Mode Selection API

```python
from edgar.xbrl.standardization.industry_logic import BankingExtractor

extractor = BankingExtractor()

# For yfinance validation (proves we understand the API)
gaap_result = extractor.extract_short_term_debt(xbrl, facts_df, mode='gaap')

# For database storage (Street View, default)
street_result = extractor.extract_short_term_debt(xbrl, facts_df, mode='street')

# Same pattern for Cash
gaap_cash = extractor.extract_cash_and_equivalents(xbrl, facts_df, mode='gaap')
street_cash = extractor.extract_cash_and_equivalents(xbrl, facts_df, mode='street')
```

### 2.3 Reference Validator Integration

The `reference_validator.py` uses **GAAP mode for validation** to prove API understanding:

```python
# In _try_industry_extraction() - line 192
if industry == 'banking' and metric == 'ShortTermDebt':
    extractor = BankingExtractor()
    # CRITICAL: Use mode='gaap' for yfinance validation
    result = extractor.extract_short_term_debt(xbrl, facts_df, mode='gaap')
```

---

## 3. The Two Tracks Explained

### 3.1 GAAP Track (`mode='gaap'`)

**Purpose:** Reproduce yfinance "Current Debt" / "Cash And Cash Equivalents" values.

**ShortTermDebt GAAP Extraction:**
1. Try `DebtCurrent` tag (cleanest match to yfinance)
2. Try `ShortTermBorrowings` aggregate
3. Fall back to component sum: `CP + CPLTD + OtherSTB`

**CashAndEquivalents GAAP Extraction:**
1. Try `CashAndCashEquivalentsAtCarryingValue`
2. Try `CashAndCashEquivalents`
3. Fall back to `Cash`

**Expected Outcome:** < 15% variance vs yfinance (validation passes)

### 3.2 Street View Track (`mode='street'`, default)

**Purpose:** Investment-grade database with economic leverage views.

**ShortTermDebt Street View:**
- **Commercial Banks:** `STB(Aggregate) - CPLTD - OperatingLiabilities`
- **Dealer Banks:** `Unsecured + BrokerPayables + OtherSecured + NetRepos`

**CashAndEquivalents Street View:**
- **Commercial Banks:** Physical cash anchor + IB deposits + Fed deposits
- **Dealer Banks:** All liquidity pools including Segregated/Restricted

**Expected Outcome:** May differ significantly from yfinance - this is intentional and documented.

---

## 4. Street View Guardrails

### 4.1 TradingLiabilities Exclusion

Operating liabilities are excluded from Street View debt:
- `TradingLiabilities` / `TradingAccountLiabilities`
- `PayablesToCustomers`
- `FinancialInstrumentsSoldNotYetPurchasedAtFairValue` / `SecuritiesSoldShort`

```python
operating_liabilities = trading_liabilities + payables_customers + securities_sold_short
clean_debt = max(0, stb_aggregate - operating_liabilities)
```

### 4.2 Sanity Governor

Prevents contaminated aggregates from passing:

```python
# If aggregate > 2x components, the aggregate is contaminated
if stb_aggregate > (components_sum * 2.0):
    # Use components only, not the contaminated aggregate
    total = cp + other_stb + fhlb
    notes = "SANITY GOVERNOR triggered - using components"
```

---

## 5. Bank Archetypes

We classify banks into three archetypes to tailor extraction logic:

| Archetype | Characteristics | Examples | Street View Differences |
|-----------|-----------------|----------|-------------------------|
| **Commercial** | Loan/Deposit centric | USB, WFC, JPM, C, PNC, BAC | Clean debt (excludes TradingLiab) |
| **Dealer** | Trading/Market Making | GS, MS | Includes Net Repos, Broker Payables |
| **Custodial** | Asset Servicing | BK, STT | High Fed Deposits in Cash |

Archetype detection happens dynamically in `BankingExtractor._detect_bank_archetype()`:
- **Custodial:** `PayablesToCustomers / Liabilities > 20%`
- **Dealer:** `TradingAssets / Assets > 15%` AND `Loans / Assets < 30%`
- **Commercial:** Default

---

## 6. Documented Street View Variances

For dealer banks, the Street View is **intentionally different** from yfinance. This is documented in `companies.yaml`:

```yaml
GS:
  industry: "banking"
  bank_archetype: "dealer"
  street_view_notes:
    ShortTermDebt: "Includes Net Repos (~$90B) for economic leverage view"
    CashAndEquivalents: "Includes Segregated Cash for regulatory liquidity view"

MS:
  industry: "banking"
  bank_archetype: "dealer"
  street_view_notes:
    ShortTermDebt: "Includes Net Repos for economic leverage view"
    CashAndEquivalents: "Includes Restricted Cash (~$30B) per Street analyst convention"
```

---

## 7. Configuration & Control

### 7.1 `industry_metrics.yaml`

Controls the behavior of the extraction system:

```yaml
metrics:
  ShortTermDebt:
    industries:
      banking:
        enabled: true
        fallback_to_tree: false  # Fail fast if industry logic misses
```

### 7.2 `companies.yaml`

Company-specific configuration with Street View documentation:

```yaml
companies:
  WFC:
    industry: "banking"
    bank_archetype: "commercial"
    validation_tolerance_pct: 20.0
    street_view_notes:
      ShortTermDebt: "Street View excludes TradingLiabilities"
```

---

## 8. Validation Patterns

### 8.1 Running the Bank Sector Test

```bash
# Full test (all metrics)
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py

# Specific metrics only
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --metrics ShortTermDebt,CashAndEquivalents
```

### 8.2 Interpreting Results

| Status | Meaning | Action |
|--------|---------|--------|
| `match` | GAAP extraction matches yfinance | Success |
| `mismatch` | Variance > tolerance | Check GAAP extraction logic |
| `mapping_needed` | Industry logic returned None | Add missing concept handling |
| `excluded` | Metric N/A for sector | Expected (e.g., COGS for banks) |

### 8.3 Expected Pass Rates

- **GAAP mode validation:** Should achieve > 80% pass rate
- **Street View:** Documented variances are acceptable

---

## 9. Troubleshooting

### 9.1 High Variance in ShortTermDebt

**Symptoms:** XBRL value >> yfinance (e.g., 500%+ variance)

**Likely Causes:**
1. `ShortTermBorrowings` aggregate includes Repos/Fed Funds
2. GAAP extraction not finding clean `DebtCurrent` tag
3. Commercial bank being treated with dealer logic

**Debug Steps:**
```python
# Check what tags are available
facts_df[facts_df['concept'].str.contains('ShortTerm', case=False)]['concept'].unique()
facts_df[facts_df['concept'].str.contains('Debt', case=False)]['concept'].unique()
```

### 9.2 Missing Cash for Custodial Banks (BK, STT)

**Symptoms:** XBRL value << yfinance (e.g., 95%+ variance)

**Likely Causes:**
1. Fed deposits use company-extension tags (e.g., `bk:InterestBearingDepositsInFederalReserve`)
2. GAAP extraction not capturing bank-specific composite

**Debug Steps:**
```python
# Check for Fed deposit variants
facts_df[facts_df['concept'].str.contains('FederalReserve|CentralBank', case=False)]['concept'].unique()
```

---

## 10. Future Roadmap

1. **GAAP Track Refinement:** Improve yfinance matching for remaining edge cases
2. **Regional Bank Expansion:** Test on super-regionals (TFC, HBAN, KEY)
3. **Regulatory Captions:** Auto-discover new segregated cash tags
4. **Dual-Value API:** Expose both GAAP and Street values in API response

---

## Appendix A: Method Reference

| Method | Mode | Purpose |
|--------|------|---------|
| `extract_short_term_debt(mode='gaap')` | GAAP | yfinance validation |
| `extract_short_term_debt(mode='street')` | Street | Database storage |
| `extract_short_term_debt_gaap()` | GAAP | Direct GAAP extraction |
| `extract_street_debt()` | Street | Direct Street extraction |
| `extract_cash_and_equivalents(mode='gaap')` | GAAP | yfinance validation |
| `extract_cash_and_equivalents(mode='street')` | Street | Database storage |
| `extract_cash_gaap()` | GAAP | Direct GAAP extraction |
| `extract_street_cash()` | Street | Direct Street extraction |

---

*Updated: Jan 2026 - Dual-Track Extraction System*
*Created by the Advanced Agentic Coding Team*

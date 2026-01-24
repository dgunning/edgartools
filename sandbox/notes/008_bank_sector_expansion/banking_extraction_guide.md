# Banking Data Extraction: A Developer's Guide

**Target Audience:** Senior Engineers / Data Architects / New Developers
**Scope:** Extraction, processing, and validation of financial data for Global Systemically Important Banks (GSIBs).

---

## Quick Start (5 Minutes)

### Run Tests Immediately

```bash
# Run bank sector E2E tests (validates against yfinance)
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py

# Test a single bank
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --tickers WFC

# Test specific metrics
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --metrics ShortTermDebt,CashAndEquivalents
```

### Key Files to Read First

1. **This guide** - Architecture overview and troubleshooting
2. `edgar/xbrl/standardization/industry_logic/__init__.py:45-86` - `ARCHETYPE_EXTRACTION_RULES` dictionary
3. `edgar/xbrl/standardization/industry_logic/__init__.py:995-1073` - `extract_short_term_debt_gaap()` main logic
4. `extraction_evolution_report_2026-01-24-16-19.md` - Latest phase changes (Phase 4)

### Validate Your Changes Work

```bash
# After any change to industry_logic:
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --tickers WFC,JPM,GS

# Check for regressions across all banks:
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py
```

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

## 2. Codebase Navigation

### Critical Files

| File | Purpose | Key Lines/Methods |
|------|---------|-------------------|
| `edgar/xbrl/standardization/industry_logic/__init__.py` | **BankingExtractor** - Core extraction logic | `ARCHETYPE_EXTRACTION_RULES:45`, `extract_short_term_debt:995`, `_detect_bank_archetype:1962` |
| `edgar/xbrl/standardization/reference_validator.py` | Validation orchestration | `validate_company:604`, `_try_industry_extraction:143` |
| `.claude/skills/bank-sector-test/scripts/run_bank_e2e.py` | E2E test runner | `process_company` |
| `config/companies.yaml` | Company-specific overrides | Bank configs with archetype overrides |
| `config/industry_metrics.yaml` | Industry metric mappings | Banking metric definitions |

### Configuration Hierarchy

```
Company Override (companies.yaml)
        │
        ▼ (takes precedence)
Archetype Rules (ARCHETYPE_EXTRACTION_RULES)
        │
        ▼ (fallback)
Default Extraction Logic
```

**Example:** WFC config override with `prefer_net_in_bs: true` overrides the commercial archetype's default repos treatment.

---

## 3. Architecture: The Dual-Track Extraction System

### 3.1 Philosophy: Why Two Tracks?

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

### 3.2 Data Flow

```
Filing → filing.xbrl() → XBRL object
                              │
                              ▼
                    xbrl.facts.to_dataframe() → facts_df
                              │
                              ▼
                    BankingExtractor.extract_short_term_debt(xbrl, facts_df, mode='gaap', ticker)
                              │
                    ┌─────────┴─────────┐
                    │ _detect_bank_archetype() │  (or config override)
                    └─────────┬─────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    _extract_custodial_stb  _extract_dealer_stb  _extract_commercial_stb
          │                   │                   │
          ▼                   ▼                   ▼
                      ExtractedMetric
```

### 3.3 ARCHETYPE_EXTRACTION_RULES Dictionary

This is the central configuration for archetype-specific behavior (line 45-86):

```python
ARCHETYPE_EXTRACTION_RULES = {
    'commercial': {
        # WFC, USB, PNC - traditional banks
        'repos_treatment': 'exclude_from_stb',      # Repos are NOT operating debt
        'trading_treatment': 'exclude_from_stb',    # Trading liabilities are NOT debt
        'extraction_strategy': 'hybrid',            # Try bottom-up, fall back to top-down
        'formula': 'STB - Repos - TradingLiab + CPLTD',
        'safe_fallback': True,                      # Allow top-down fallback
    },
    'dealer': {
        # GS, MS - investment banks
        'repos_treatment': 'separate_line_item',    # Repos already separate
        'trading_treatment': 'separate_line_item',
        'extraction_strategy': 'direct',            # Use UnsecuredSTB directly
        'formula': 'UnsecuredSTB + CPLTD',
        'safe_fallback': True,
    },
    'custodial': {
        # BK, STT - custody banks
        'repos_treatment': 'include_as_debt',       # Repos ARE financing for custody ops
        'trading_treatment': 'exclude',
        'extraction_strategy': 'component_sum',     # Sum specific components only
        'formula': 'OtherSTB + FedFundsPurchased + CPLTD',
        'safe_fallback': False,                     # NEVER fall back to fuzzy match!
    },
    'hybrid': {
        # JPM, BAC, C - universal banks
        'repos_treatment': 'check_nesting_first',   # Check if already separated
        'trading_treatment': 'separate_line_item',
        'extraction_strategy': 'direct',            # No subtraction unless confirmed nested
        'formula': 'STB + CPLTD (no subtraction)',
        'safe_fallback': True,
    },
    'regional': {
        # Smaller banks (SIC 6022) - fallback to commercial rules
        'repos_treatment': 'exclude_from_stb',
        'trading_treatment': 'exclude_from_stb',
        'extraction_strategy': 'hybrid',
        'formula': 'Commercial rules (default)',
        'safe_fallback': True,
    },
}
```

### 3.4 Mode Selection API

```python
from edgar.xbrl.standardization.industry_logic import BankingExtractor

extractor = BankingExtractor()

# For yfinance validation (proves we understand the API)
gaap_result = extractor.extract_short_term_debt(xbrl, facts_df, mode='gaap', ticker='WFC')

# For database storage (Street View, default)
street_result = extractor.extract_short_term_debt(xbrl, facts_df, mode='street', ticker='WFC')

# Same pattern for Cash
gaap_cash = extractor.extract_cash_and_equivalents(xbrl, facts_df, mode='gaap')
street_cash = extractor.extract_cash_and_equivalents(xbrl, facts_df, mode='street')
```

### 3.5 Reference Validator Integration

The `reference_validator.py` uses **GAAP mode for validation** to prove API understanding:

```python
# In _try_industry_extraction() - line 207-214
if industry == 'banking' and metric == 'ShortTermDebt':
    extractor = BankingExtractor()
    # CRITICAL: Use mode='gaap' for yfinance validation
    # PHASE 3 FIX: Pass ticker for config-based archetype lookup
    result = extractor.extract_short_term_debt(xbrl, facts_df, mode='gaap', ticker=ticker)
    if result.value is not None:
        return result.value
```

---

## 4. Helper Methods Reference

### 4.1 Standard Fact Lookup

**`_get_fact_value(df, concept, target_period_days=None)`** (line 170)

Standard lookup for a GAAP concept. Returns the most recent non-dimensional value.

```python
cpltd = self._get_fact_value(facts_df, 'LongTermDebtCurrent')
# Returns: 5000000000.0 (5B) or None
```

### 4.2 Non-Dimensional Lookup (Phase 4)

**`_get_fact_value_non_dimensional(df, concept)`** (line 300)

**CRITICAL:** Returns ONLY consolidated totals. Returns None if only dimensional values exist.

```python
# WFC has TradingLiabilities with TradingActivityByTypeAxis dimension ONLY
# This returns None (correct) instead of the dimensional breakdown value
trading = self._get_fact_value_non_dimensional(facts_df, 'TradingLiabilities')
```

**Use Case:** Prevents mixing dimensional breakdowns (analytical data) with operational line items.

### 4.3 Fuzzy/Suffix Matching

**`_get_fact_value_fuzzy(df, concept_pattern)`** (line 424)

Matches by concept suffix, handling company-extension namespaces (`wfc:`, `jpm:`, `bac:`).

```python
# Matches: us-gaap:SecuritiesSold..., wfc:SecuritiesSold..., etc.
repos = self._get_fact_value_fuzzy(facts_df, 'SecuritiesSoldUnderAgreementsToRepurchase')
```

### 4.4 Repos Decomposition (Phase 4)

**`_get_repos_value(facts_df, prefer_net_in_bs=False)`** (line 777)

Gets repos value with optional WFC-style decomposition.

```python
# For most banks:
repos = self._get_repos_value(facts_df)

# For WFC (combined repos+sec loaned):
# Pure Repos = Combined NET - SecuritiesLoaned
repos = self._get_repos_value(facts_df, prefer_net_in_bs=True)
# Returns: $194.3B (not $202.3B combined)
```

### 4.5 Linkbase Nesting Detection

**`_is_concept_nested_in_stb(xbrl, concept)`** (line 684)

Checks calculation and presentation linkbases to determine if a concept is nested inside ShortTermBorrowings.

```python
# Returns True if repos is a CHILD of STB (should subtract)
# Returns False if repos is a SIBLING (should NOT subtract)
is_nested = self._is_concept_nested_in_stb(xbrl, 'SecuritiesSoldUnderAgreementsToRepurchase')
```

**Check Order:**
1. Calculation Linkbase - definitive parent/child with weight
2. Presentation Linkbase - visual indentation implies summation
3. Default: Assume SIBLING (Do Not Subtract)

### 4.6 Dimensional Aggregation

**`_get_dimensional_sum(facts_df, concept, axis=None)`** (line 865)

Sums dimensional facts when consolidated value is missing (e.g., STT's ShortTermBorrowings with ShortTermDebtTypeAxis).

```python
# STT reports STB only with dimensional breakdown
stb_sum = self._get_dimensional_sum(facts_df, 'ShortTermBorrowings', axis='ShortTermDebtTypeAxis')
```

### 4.7 Constructed Net Metrics

**`_construct_net_metric(facts_df, structure)`** (line 385)

Constructs a metric by summing/subtracting components.

```python
# Example: WFC ShortTermBorrowings - Repos
net_debt = self._construct_net_metric(facts_df, {
    'add': ['ShortTermBorrowings'],
    'deduct': ['SecuritiesSoldUnderAgreementsToRepurchase']
})
```

---

## 5. Bank Archetypes

### 5.1 Classification Table

| Archetype | Characteristics | Examples | Detection Signal | GAAP Extraction |
|-----------|-----------------|----------|------------------|-----------------|
| **Commercial** | Loan/Deposit centric | USB, WFC, PNC | Default (loans > 50% assets) | STB - Repos - TradingLiab + CPLTD |
| **Dealer** | Trading/Market Making | GS, MS | TradingAssets > 15% AND Loans < 30% | UnsecuredSTB + CPLTD |
| **Custodial** | Asset Servicing | BK, STT | PayablesToCustomers > 20% Liabilities | OtherSTB + FedFunds + CPLTD |
| **Hybrid** | Universal banks | JPM, BAC, C | Config override | STB + CPLTD (no subtraction) |

### 5.2 Dynamic Detection Logic

From `_detect_bank_archetype()` (line 1962):

```python
def _detect_bank_archetype(self, facts_df) -> str:
    assets = self._get_fact_value(facts_df, 'Assets') or 0
    liabilities = self._get_fact_value(facts_df, 'Liabilities') or 0

    # Custodial signal: High payables to customers (asset management)
    payables_customers = self._get_fact_value(facts_df, 'PayablesToCustomers') or 0
    if liabilities > 0 and payables_customers / liabilities > 0.20:
        return 'custodial'

    # Dealer signal: High trading assets and low loans
    trading_assets = self._get_fact_value(facts_df, 'TradingAssets') or 0
    loans = self._get_fact_value(facts_df, 'LoansAndLeasesReceivableGrossCarryingAmount') or 0

    if assets > 0:
        trading_ratio = trading_assets / assets
        loan_ratio = loans / assets
        if trading_ratio > 0.15 and loan_ratio < 0.30:
            return 'dealer'

    # Default: Commercial bank
    return 'commercial'
```

### 5.3 Config Override

Company-specific archetype can be forced via `companies.yaml`:

```yaml
JPM:
  industry: "banking"
  bank_archetype: "hybrid"  # Override dynamic detection
  extraction_rules:
    repos_treatment: "check_nesting_first"
```

---

## 6. The Two Tracks Explained

### 6.1 GAAP Track (`mode='gaap'`)

**Purpose:** Reproduce yfinance "Current Debt" / "Cash And Cash Equivalents" values.

**ShortTermDebt GAAP Extraction:**
1. Try `DebtCurrent` tag (cleanest match to yfinance)
2. Try `ShortTermBorrowings` aggregate with archetype-aware cleaning:
   - **Commercial banks:** Subtract Repos + TradingLiabilities (if nested and non-dimensional)
   - **Dealer banks:** Use STB directly (repos are separate line items, not nested)
3. Add `LongTermDebtCurrent` (CPLTD)
   - **NO maturity schedule fallback** - `LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths` is a footnote disclosure (ASC 470-10-50-1), not a balance sheet classification
4. Fall back to component sum: `CP + CPLTD + OtherSTB`

**CashAndEquivalents GAAP Extraction:**
1. Try `CashAndCashEquivalentsAtCarryingValue`
2. Try `CashAndDueFromBanks` (common for commercial banks like USB)
3. Try `CashAndCashEquivalents`
4. Add `InterestBearingDepositsInBanks` + `FedDeposits` (if separate line items)
5. Subtract `RestrictedCash` (yfinance excludes)
6. Fall back to `Cash`

**Expected Outcome:** < 15% variance vs yfinance (validation passes)

### 6.2 Street View Track (`mode='street'`, default)

**Purpose:** Investment-grade database with economic leverage views.

**ShortTermDebt Street View:**
- **Commercial Banks:** `STB(Aggregate) - CPLTD - OperatingLiabilities`
- **Dealer Banks:** `Unsecured + BrokerPayables + OtherSecured + NetRepos`

**CashAndEquivalents Street View:**
- **Commercial Banks:** Physical cash anchor + IB deposits + Fed deposits
- **Dealer Banks:** All liquidity pools including Segregated/Restricted

**Expected Outcome:** May differ significantly from yfinance - this is intentional and documented.

---

## 7. Street View Guardrails

### 7.1 TradingLiabilities Exclusion

Operating liabilities are excluded from Street View debt:
- `TradingLiabilities` / `TradingAccountLiabilities`
- `PayablesToCustomers`
- `FinancialInstrumentsSoldNotYetPurchasedAtFairValue` / `SecuritiesSoldShort`

```python
operating_liabilities = trading_liabilities + payables_customers + securities_sold_short
clean_debt = max(0, stb_aggregate - operating_liabilities)
```

### 7.2 Sanity Governor

Prevents contaminated aggregates from passing:

```python
# If aggregate > 2x components, the aggregate is contaminated
if stb_aggregate > (components_sum * 2.0):
    # Use components only, not the contaminated aggregate
    total = cp + other_stb + fhlb
    notes = "SANITY GOVERNOR triggered - using components"
```

---

## 8. Architectural Decision Records (ADR)

### ADR-001: Dual-Track Architecture
**Context:** Investment analysts need economic leverage views, but we must prove API understanding.
**Decision:** Implement separate GAAP (validation) and Street View (database) extraction modes.
**Impact:** All extraction methods accept `mode` parameter.

### ADR-002: Archetype-Based Extraction
**Context:** Banks have fundamentally different balance sheet structures.
**Decision:** Classify banks into archetypes (commercial, dealer, custodial, hybrid) with tailored extraction rules.
**Impact:** `ARCHETYPE_EXTRACTION_RULES` dictionary drives extraction behavior.

### ADR-003: Maturity Schedule Ban
**Context:** `LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths` is a footnote disclosure (ASC 470-10-50-1), not balance sheet.
**Decision:** Never use maturity schedule concepts as CPLTD fallback.
**Impact:** Removed from all CPLTD fallback chains.

### ADR-004: Dealer Repos Sibling Rule
**Context:** GS/MS report repos as separate line items (~$274B), not nested in STB (~$70B).
**Decision:** For dealers, do NOT subtract repos from STB.
**Impact:** Dealer extraction uses `UnsecuredSTB + CPLTD` directly.

### ADR-005: Linkbase Nesting Check
**Context:** Need to determine if repos/trading are nested in STB before subtracting.
**Decision:** Check calculation and presentation linkbases for parent-child relationship.
**Impact:** `_is_concept_nested_in_stb()` method with suffix matching for namespace resilience.

### ADR-006: Balance Guard Override
**Context:** Some extractions return negative values due to over-subtraction.
**Decision:** Apply `max(0, result)` guard to prevent negative debt values.
**Impact:** All archetype extraction methods clamp to zero minimum.

### ADR-007: Config-Driven Subtraction
**Context:** Different banks need different subtraction behavior for the same concept.
**Decision:** Allow `companies.yaml` to override archetype rules.
**Impact:** Company rules merged with archetype rules, company takes precedence.

### ADR-008: Custodial repos_as_debt Default
**Context:** Custody banks (BK, STT) use repos as operational financing.
**Decision:** Custodial archetype includes repos as debt by default.
**Impact:** `repos_treatment: 'include_as_debt'` in custodial rules.

### ADR-009: Strict Non-Dimensional Fact Extraction
**Context:** WFC's TradingLiabilities appears only with dimensional attributes (analytical breakdowns, not operational totals).
**Decision:** Add `_get_fact_value_non_dimensional()` method that returns None if only dimensional values exist.
**Impact:** Prevents mixing analytical breakdowns with operational line items. Applied to TradingLiabilities in commercial extraction.

### ADR-010: Bank-Specific Repos Decomposition
**Context:** WFC reports repos+securities loaned combined in a single line item.
**Decision:** Add `prefer_net_in_bs` parameter to `_get_repos_value()`. When enabled, calculates pure repos = Combined NET - SecuritiesLoaned.
**Impact:** Enables WFC-specific repos handling while maintaining backwards compatibility.

---

## 9. Troubleshooting

### 9.1 High Variance in ShortTermDebt (Over-extraction)

**Symptoms:** XBRL value >> yfinance (e.g., 82-996% over-extraction)

**Likely Causes:**
1. Using maturity schedule (`LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths`) as CPLTD fallback - this is a footnote disclosure, not balance sheet
2. `ShortTermBorrowings` aggregate includes Repos/Fed Funds for commercial banks
3. Contamination subtraction not working properly

**Known Cases (Fixed):**
- **WFC:** Was 82% over ($24.8B vs $13.6B yfinance) due to maturity schedule CPLTD
- **BK:** Was 996% over ($3.3B vs $0.3B yfinance) due to maturity schedule CPLTD

**Debug Steps:**
```python
# Check for maturity schedule vs balance sheet CPLTD
facts_df[facts_df['concept'].str.contains('Maturities|LongTermDebtCurrent', case=False)]['concept'].unique()
```

### 9.2 Low Variance in ShortTermDebt (Under-extraction for Dealers)

**Symptoms:** XBRL value << yfinance for dealer banks (e.g., 95% under-extraction)

**Likely Causes:**
1. Subtracting repos from STB for dealers when repos are *separate* line items
2. Dealer banks (GS, MS) report massive repos (~$274B) as standalone liabilities, not nested in STB (~$70B)

**Known Cases (Fixed):**
- **GS:** Was 95% under ($4.6B vs $90.6B yfinance) due to subtracting $274B repos from $70B STB

**Debug Steps:**
```python
# Check archetype detection
extractor = BankingExtractor()
archetype = extractor._detect_bank_archetype(facts_df)
print(f"Archetype: {archetype}")  # Should be 'dealer' for GS/MS

# Check repos vs STB magnitude
stb = extractor._get_fact_value(facts_df, 'ShortTermBorrowings')
repos = extractor._get_fact_value_fuzzy(facts_df, 'SecuritiesSoldUnderAgreementsToRepurchase')
print(f"STB: {stb/1e9:.1f}B, Repos: {repos/1e9:.1f}B")
# If repos >> STB, they're separate line items (don't subtract)
```

### 9.3 Dimensional-Only Concepts (Phase 4)

**Symptoms:** Over-extraction due to subtracting dimensional breakdown values

**Example - WFC 10-Q:**
- WFC reports `TradingLiabilities` ONLY with `TradingActivityByTypeAxis` dimension
- These are analytical breakdowns by trading type, NOT operational totals bundled in STB
- Subtracting dimensional trading ($51.9B) caused $43B over-extraction error

**Solution:** Use `_get_fact_value_non_dimensional()` which returns None for dimensional-only concepts.

```python
# WRONG - may return dimensional breakdown value
trading = self._get_fact_value(facts_df, 'TradingLiabilities')

# CORRECT - returns None if only dimensional values exist
trading = self._get_fact_value_non_dimensional(facts_df, 'TradingLiabilities')
```

### 9.4 Combined Repos+Securities Pattern (Phase 4)

**Symptoms:** Incorrect repos subtraction for banks with combined reporting

**Example - WFC:**
- WFC reports repos+securities loaned combined: `wfc:SecuritiesSoldUnderAgreementsToRepurchaseAndSecuritiesLoanedNetAmountInConsolidatedBalanceSheet` = $202.3B
- Securities Loaned separately: $8.0B
- Pure Repos needed: $202.3B - $8.0B = $194.3B

**Solution:** Use `prefer_net_in_bs=True` in `_get_repos_value()`:

```python
# For WFC: calculate pure repos = Combined - SecLoaned
repos = self._get_repos_value(facts_df, prefer_net_in_bs=True)
```

### 9.5 Missing Cash for Commercial Banks

**Symptoms:** XBRL value << yfinance for commercial banks (e.g., 83% under-extraction)

**Likely Causes:**
1. Bank uses `CashAndDueFromBanks` instead of `CashAndCashEquivalentsAtCarryingValue`
2. GAAP extraction not finding the correct tag in hierarchy

**Known Cases (Fixed):**
- **USB:** Was 83% under ($9.4B vs $56.5B yfinance) due to missing `CashAndDueFromBanks` in hierarchy

**Debug Steps:**
```python
# Check which cash tags are available
facts_df[facts_df['concept'].str.contains('Cash', case=False)]['concept'].unique()
```

### 9.6 Missing Cash for Custodial Banks (BK, STT)

**Symptoms:** XBRL value << yfinance (e.g., 95%+ variance)

**Likely Causes:**
1. Fed deposits use company-extension tags (e.g., `bk:InterestBearingDepositsInFederalReserve`)
2. GAAP extraction not capturing bank-specific composite

**Debug Steps:**
```python
# Check for Fed deposit variants
facts_df[facts_df['concept'].str.contains('FederalReserve|CentralBank', case=False)]['concept'].unique()
```

### 9.7 Empty Facts DataFrame

**Symptoms:** Test returns "mapping_needed" or extraction returns None

**Likely Causes:**
1. Filing not yet available in EDGAR
2. XBRL parsing failed
3. Corrupt or unsupported filing format

**Debug Steps:**
```python
# Check facts count
from edgar import Company
c = Company('BK')
filing = c.get_filings(form='10-Q').latest()
xbrl = filing.xbrl()
facts_df = xbrl.facts.to_dataframe()
print(f"Facts count: {len(facts_df)}")  # Should be > 100
```

---

## 10. Development Workflow

### 10.1 How to Debug a Failure

1. **Run the specific test:**
   ```bash
   python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --tickers WFC
   ```

2. **Get the extracted value:**
   ```python
   from edgar import Company
   from edgar.xbrl.standardization.industry_logic import BankingExtractor

   c = Company('WFC')
   filing = c.get_filings(form='10-Q').latest()
   xbrl = filing.xbrl()
   facts_df = xbrl.facts.to_dataframe()

   extractor = BankingExtractor()
   result = extractor.extract_short_term_debt(xbrl, facts_df, mode='gaap', ticker='WFC')
   print(f"Extracted: ${result.value/1e9:.1f}B")
   print(f"Method: {result.extraction_method}")
   print(f"Notes: {result.notes}")
   ```

3. **Check archetype detection:**
   ```python
   archetype = extractor._detect_bank_archetype(facts_df)
   print(f"Archetype: {archetype}")
   ```

4. **Trace component values:**
   ```python
   stb = extractor._get_fact_value(facts_df, 'ShortTermBorrowings')
   repos = extractor._get_repos_value(facts_df, prefer_net_in_bs=True)
   trading = extractor._get_fact_value_non_dimensional(facts_df, 'TradingLiabilities')
   cpltd = extractor._get_fact_value(facts_df, 'LongTermDebtCurrent')
   print(f"STB: {stb}, Repos: {repos}, Trading: {trading}, CPLTD: {cpltd}")
   ```

### 10.2 How to Add a New Bank

1. **Run initial test:**
   ```bash
   python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --tickers NEW_BANK
   ```

2. **Check archetype detection is correct:**
   - If incorrect, add override to `companies.yaml`:
   ```yaml
   NEW_BANK:
     industry: "banking"
     bank_archetype: "commercial"  # or dealer, custodial, hybrid
   ```

3. **If extraction still fails, add company-specific rules:**
   ```yaml
   NEW_BANK:
     industry: "banking"
     bank_archetype: "commercial"
     extraction_rules:
       prefer_net_in_bs: true  # For combined repos+sec loaned
   ```

4. **Run regression test:**
   ```bash
   python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py
   ```

### 10.3 How to Add a New Metric

1. **Add extraction method to `BankingExtractor`:**
   ```python
   def extract_new_metric(self, xbrl, facts_df, mode: str = 'street') -> ExtractedMetric:
       # Implementation
   ```

2. **Register in `reference_validator.py`:**
   ```python
   if industry == 'banking' and metric == 'NewMetric':
       extractor = BankingExtractor()
       result = extractor.extract_new_metric(xbrl, facts_df, mode='gaap')
   ```

3. **Add to E2E test metrics list:**
   ```python
   # In run_bank_e2e.py
   METRICS = ['ShortTermDebt', 'CashAndEquivalents', 'NewMetric']
   ```

### 10.4 How to Run Tests for Specific Banks/Metrics

```bash
# Single bank
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --tickers WFC

# Multiple banks
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --tickers WFC,JPM,GS

# Specific metrics
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --metrics ShortTermDebt

# Combined
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --tickers WFC --metrics ShortTermDebt
```

---

## 11. Documented Street View Variances

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

## 12. Configuration & Control

### 12.1 `industry_metrics.yaml`

Controls the behavior of the extraction system:

```yaml
metrics:
  ShortTermDebt:
    industries:
      banking:
        enabled: true
        fallback_to_tree: false  # Fail fast if industry logic misses
```

### 12.2 `companies.yaml`

Company-specific configuration with Street View documentation:

```yaml
companies:
  WFC:
    industry: "banking"
    bank_archetype: "commercial"
    validation_tolerance_pct: 20.0
    extraction_rules:
      prefer_net_in_bs: true  # Phase 4: Combined repos+sec loaned decomposition
    street_view_notes:
      ShortTermDebt: "Street View excludes TradingLiabilities"
```

---

## 13. Validation Patterns

### 13.1 Running the Bank Sector Test

```bash
# Full test (all metrics)
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py

# Specific metrics only
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --metrics ShortTermDebt,CashAndEquivalents
```

### 13.2 Interpreting Results

| Status | Meaning | Action |
|--------|---------|--------|
| `match` | GAAP extraction matches yfinance | Success |
| `mismatch` | Variance > tolerance | Check GAAP extraction logic |
| `mapping_needed` | Industry logic returned None | Add missing concept handling |
| `excluded` | Metric N/A for sector | Expected (e.g., COGS for banks) |

### 13.3 Current Test Results (Phase 4)

**Run ID:** e2e_banks_2026-01-24T11:45

| Form | Pass Rate | Details |
|------|-----------|---------|
| **10-K** | 44.4% (4/9) | Remaining issues: WFC (53%), USB (104%), STT |
| **10-Q** | 77.8% (7/9) | Improved from 61.5% after Phase 4 fixes |

**Top Failing Metrics:**
- ShortTermDebt: 8 failures

**Top Failing Companies:**
- WFC: 4 failures (10-K has different annual reporting structure)
- STT: 2 failures
- USB: 2 failures (data source mismatch)

---

## 14. Future Roadmap

1. **GAAP Track Refinement:** Improve yfinance matching for remaining edge cases
2. **Regional Bank Expansion:** Test on super-regionals (TFC, HBAN, KEY)
3. **Regulatory Captions:** Auto-discover new segregated cash tags
4. **Dual-Value API:** Expose both GAAP and Street values in API response

---

## Appendix A: Method Reference

| Method | Mode | Purpose | Line |
|--------|------|---------|------|
| `extract_short_term_debt(mode='gaap')` | GAAP | yfinance validation | 995 |
| `extract_short_term_debt(mode='street')` | Street | Database storage | 995 |
| `extract_short_term_debt_gaap()` | GAAP | Direct GAAP extraction | 1017 |
| `extract_street_debt()` | Street | Direct Street extraction | 1607 |
| `extract_cash_and_equivalents(mode='gaap')` | GAAP | yfinance validation | - |
| `extract_cash_and_equivalents(mode='street')` | Street | Database storage | - |
| `_get_fact_value()` | - | Standard fact lookup | 170 |
| `_get_fact_value_non_dimensional()` | - | Strict non-dimensional lookup | 300 |
| `_get_fact_value_fuzzy()` | - | Suffix/namespace-resilient lookup | 424 |
| `_get_repos_value()` | - | Repos with optional decomposition | 777 |
| `_is_concept_nested_in_stb()` | - | Linkbase nesting check | 684 |
| `_get_dimensional_sum()` | - | Dimensional aggregation | 865 |
| `_detect_bank_archetype()` | - | Dynamic archetype detection | 1962 |

---

## Appendix B: Changelog

### Jan 24, 2026 - Phase 4: Dimensional Data & Repos Decomposition

**Fixes Applied:**

| Issue | Company | Root Cause | Fix |
|-------|---------|------------|-----|
| Dimensional Trading Subtraction | WFC 10-Q | Subtracting dimensional TradingLiabilities ($51.9B) that are analytical breakdowns, not operational totals | Added `_get_fact_value_non_dimensional()` - returns None for dimensional-only concepts |
| Combined Repos+SecLoaned | WFC 10-Q | Using combined NET ($202.3B) instead of pure repos ($194.3B) | Added `prefer_net_in_bs` parameter to `_get_repos_value()` for decomposition |

**Results:**
- 10-K Pass Rate: 44.4% (unchanged - expected, as 10-K has different structure)
- 10-Q Pass Rate: 61.5% → 77.8% (+16.3%)
- WFC 10-Q: **FIXED** - $79.7B → $36.4B (matches yfinance)

**New ADRs:**
- ADR-009: Strict Non-Dimensional Fact Extraction
- ADR-010: Bank-Specific Repos Decomposition

### Jan 22, 2026 - GAAP Extraction Remediation

**Fixes Applied:**

| Issue | Company | Root Cause | Fix |
|-------|---------|------------|-----|
| Dealer Debt Subtraction | GS | Subtracting repos ($274B) that are separate line items | Added archetype check - skip subtraction for dealers |
| Maturity Schedule Ban | WFC, BK | Using footnote disclosure as balance sheet | Removed `LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths` fallback |
| Cash Hierarchy | USB | Missing `CashAndDueFromBanks` tag | Added to GAAP cash hierarchy as priority #2 |

**Results:**
- 10-K Pass Rate: 58.3% → 81.8%
- 10-Q Pass Rate: 76.0% → 90.0%
- CashAndEquivalents failures: 3 → 0
- ShortTermDebt failures: 13 → 7

---

*Updated: Jan 24, 2026 - Phase 4: Dimensional Data & Repos Decomposition*
*Created by the Advanced Agentic Coding Team*

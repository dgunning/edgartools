# Banking Data Extraction: A Developer's Guide

**Target Audience:** Senior Engineers / Data Architects
**Scope:** Extraction, processing, and validation of financial data for Global Systemically Important Banks (GSIBs).

---

## 1. Executive Summary

Standardizing financial data for banks is fundamentally different from non-financial corporates. The standard XBRL "GAAP" tags often misrepresent the economic reality of a bank's balance sheet.

For example:
- **Cash** is not just "Cash and Cash Equivalents" but includes Fed deposits, interbank placements, and segregated regulatory cash.
- **Short-Term Debt** is not just "Short-Term Borrowings" but a specific "Street View" that excludes operational funding (like customer deposits) and includes economic leverage (like Net Repos for dealers).

This system implements a **Dual-Track Extraction Architecture** that prioritizes specialized `industry_logic` over standard tree-walking for specific sectors.

---

## 2. Architecture: The Dual-Track System

We do not rely on a single mapping strategy. Instead, we use a fallback mechanism controlled by logic and configuration.

### The Flow
1.  **Reference Validator (`reference_validator.py`)**: The orchestrator.
2.  **Industry Detection**: Checks `industry_metrics.yaml` to see if the metric has specialized logic.
3.  **Path A: Industry Logic (Priority)**
    *   Calls `industry_logic.get_industry_metric()`.
    *   If successful, returns the value with `MappingSource.INDUSTRY`.
    *   **Crucial:** For Banking metrics (`ShortTermDebt`), we often set `fallback_to_tree: false`. If industry logic fails, we want a hard failure (or `MISSING`) rather than a potentially misleading value from the standard tree.
4.  **Path B: Tree Mapping (Fallback)**
    *   If industry logic returns `None` (and fallback is allowed), it proceeds to standard taxonomy tree walking (`tree_parser.py`).

---

## 3. The "Street View" Philosophy

Our goal is to match the "Street" (Analyst/yfinance) view, which often differs from the strict GAAP face of the filing.

### Key Concept: Bank Archetypes
We classify banks into three archetypes to tailor extraction logic. This categorization happens dynamically in `BankingExtractor._detect_bank_archetype()`:

| Archetype | Characteristics | Examples | Key Extraction Differences |
|-----------|-----------------|----------|----------------------------|
| **Commercial** | Audit/Deposit centric | USB, WFC, JPM, C | `ShortTermDebt` = Aggregates - CPLTD |
| **Dealer** | Trading/Market Making | GS, MS | `ShortTermDebt` includes Net Repos & Broker Payables |
| **Custodial** | Asset Servicing | BK, STT | High Fed Deposits, often lower traditional debt |

---

## 4. Implementation Deep Dive

The core logic resides in `edgar/xbrl/standardization/industry_logic/__init__.py`.

### 4.1. Short-Term Debt (The Hardest Problem)

**Why it's hard:** Banks commingle "Operational Liabilities" (customer deposits, trading liabilities) with "Financial Debt" (borrowings).

**Our Approach:**
1.  **Strict Component Summation**: We prefer building the number up from components rather than trusting a top-level aggregate that might include "dirty" items.
2.  **Economic Leverage (Dealers)**: For Goldman (GS) and Morgan Stanley (MS), we explicitly **include** "Net Repos" (Securities Sold under Agreements to Repurchase - Securities Purchased under Agreements to Resell) and "Payables to Broker-Dealers". This reflects the funding used to leverage their trading book.
    *   *Note:* This causes variance against some data providers who use a strictly "Structural Debt" view, but it is the correct "Economic" view for our users.
3.  **CPLTD Deduction (Commercial)**: For US Bancorp (USB) and others, we take the `ShortTermBorrowings` aggregate and strictly **deduct** `CurrentPortionOfLongTermDebt` (CPLTD) if it's included, to isolate the true short-term funding needs.

**Code Reference:** `BankingExtractor.extract_street_debt`

### 4.2. Cash & Equivalents

**Why it's hard:** A bank's "Cash" is often tied up in regulatory requirements or central banks.

**Our Approach:**
We iterate through a priority list of composite definitions:
1.  **Liquid Assets Composite**: `CashAndCashEquivalents` + `InterestBearingDepositsInBanks` + `Fed/CentralBankDeposits`.
2.  **Regulatory Cash**: For dealers/custodians, we explicitly add `CashAndSecuritiesSegregatedUnderFederalAndOtherRegulations` and `RestrictedCash`.
3.  **Fuzzy Match Fallback**: Checks for generic "Cash and Due from Banks" if specific tags fail.

**Code Reference:** `BankingExtractor.extract_street_cash`

---

## 5. Configuration & Control

### `industry_metrics.yaml`
This file controls the behavior of the system.

```yaml
metrics:
  ShortTermDebt:
    industries:
      banking:
        enabled: true
        fallback_to_tree: false  # <--- CRITICAL: Fail fast if logic misses
```

### `metrics.yaml`
Standard taxonomy definitions. Banking concepts are added here to be "known" to the system, ensuring the XBRL loader parses them even if they aren't in the standard calculation linkbase.

---

## 6. Validation Patterns

We use a suite of End-to-End (E2E) tests found in `.agent/skills/bank-sector-test/`.

### 6.1. The Standard Test
Run the banking skill to test the 9 GSIBs against yfinance data:
```bash
python .agent/skills/bank-sector-test/scripts/run_bank_e2e.py
```

### 6.2. Analyzing Failures
*   **Missing Reference**: The data provider (yfinance) has no data. Check `debug_banking_facts.py` to see the raw values.
*   **Mismatch (>10%)**:
    *   If **Commercial Bank**: Check if we are double-counting a debt component or missing a CPLTD deduction.
    *   If **Dealer**: Check if "Net Repos" has swung wildly or if a new "Other Secured Borrowings" tag has appeared.
*   **Execution Path Error**: The industry logic returned `None`, and `fallback_to_tree` is false. This means our logic missed every single heuristic. **Action**: Add the missing XBRL tag to the relevant extractor method.

---

## 7. Future Roadmap

1.  **Regional Bank Expansion**: Testing logic on super-regionals (PNC, TFC, USB) to ensure the "Commercial" archetype holds up.
2.  **Repo Nettings**: Refine the "Net Repos" calculation to handle cases where "Resell Agreements" (Assets) exceed "Repurchase Agreements" (Liabilities).
3.  **Regulatory Captions**: Automate the discovery of new "Segregated Cash" tags, as these change frequently in regulatory filings.

---
*Created by the Advanced Agentic Coding Team - Jan 2026*

# Calculation Tree Study - MAG7 Companies

**Date:** 2026-01-06  
**Purpose:** Understand XBRL calculation trees across MAG7 to inform concept mapping

---

## Research Questions

1. **Cross-company variation**: How different are calculation trees reported by different companies?
2. **Temporal evolution**: How do trees change over time (within company and across companies)?

---

## Background

XBRL filings include a **calculation linkbase** that defines parent-child relationships between financial concepts. For example:

```
NetIncome (ROOT)
├── IncomeLossBeforeTax (weight +1.0)
│   ├── OperatingIncome (weight +1.0)
│   │   ├── Revenue (weight +1.0)
│   │   └── CostsAndExpenses (weight -1.0)
│   └── NonoperatingIncome (weight +1.0)
└── IncomeTaxExpense (weight -1.0)
```

**Key insight**: We can extract these trees programmatically using EdgarTools - NO AI needed!

---

## Scripts

| Script | Purpose |
|--------|---------|
| `01_extract_meta_trees.py` | Demo: Extract all calculation trees from META's 10-K |
| `02_compare_mag7_trees.py` | Compare tree structures across MAG7 companies |
| `03_temporal_evolution.py` | Track how trees change over time for each company |

---

## Key Findings

### Finding 1: Tree Counts by Company

| Company | Total Trees | Income | Balance | CashFlow | Filing Date |
|---------|-------------|--------|---------|----------|-------------|
| GOOG | 30 | 11 | 2 | 1 | 2025-02-05 |
| AMZN | 25 | 8 | 1 | 2 | 2025-02-07 |
| AAPL | 23 | 6 | 1 | 2 | 2025-10-31 |
| MSFT | 28 | 10 | 1 | 1 | 2025-07-30 |
| NVDA | 25 | 6 | 6 | 1 | 2025-02-26 |
| META | 26 | 9 | 1 | 1 | 2025-01-30 |

**Observations:**
- All companies have 23-30 calculation trees
- All have at least 1 each of Income, Balance, and CashFlow trees
- GOOG has the most (30), AAPL has the fewest (23)

### Finding 2: Universal Concepts (Present in ALL 7 Companies)

Found **27 concepts** universal across MAG7:

**Income Statement:**
- `RevenueFromContractWithCustomerExcludingAssessedTax` ← **Revenue**
- `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest` ← **PretaxIncome**
- `OperatingIncomeLoss`, `NetIncomeLoss`, `IncomeTaxExpenseBenefit`, `NonoperatingIncomeExpense`

**Balance Sheet:**
- `CashAndCashEquivalentsAtCarryingValue`, `MarketableSecuritiesCurrent`
- `PropertyPlantAndEquipmentNet`, `OtherAssetsNoncurrent`
- `AccruedLiabilitiesCurrent`, `LongTermDebt`, `LongTermDebtNoncurrent`

**Cash Flow:**
- `ShareBasedCompensation`, `DeferredIncomeTaxExpenseBenefit`

### Finding 3: Temporal Stability (5-Year Analysis)

| Company | 2021 | 2022 | 2023 | 2024 | 2025 | Trend |
|---------|------|------|------|------|------|-------|
| GOOG | 31 | 31 | 30 | 27 | 30 | Stable |
| AMZN | 23 | 24 | 24 | 25 | 25 | +2 |
| AAPL | 21 | 21 | 25 | 23 | 23 | +2 |
| MSFT | 30 | 29 | 29 | 29 | 28 | -2 |
| NVDA | 22 | 24 | 25 | 24 | 25 | +3 |
| META | 21 | 21 | 25 | 25 | 26 | +5 |

**Observations:**
- Trees are **highly stable** over 5 years (variance ±3-5)
- No company had major restructuring of calculation trees
- META grew the most (+5 trees), MSFT decreased slightly (-2)

### Finding 4: 10-K vs 10-Q Comparison (All MAG7)

| Company | 10-Q Trees | Naming Pattern | Example Income Tree |
|---------|------------|----------------|---------------------|
| GOOG | 25 | `CONSOLIDATED` | `CONSOLIDATEDSTATEMENTSOFINCOME` |
| AMZN | 17 | `Consolidated` | `ConsolidatedStatementsofOperations` |
| AAPL | 10 | `CONDENSED` ✅ | `CONDENSEDCONSOLIDATEDSTATEMENTSOFOPERATIONSUnaudited` |
| MSFT | 22 | `Role_` | `Role_StatementINCOMESTATEMENTS` |
| NVDA | 20 | `Condensed` ✅ | `CondensedConsolidatedStatementsofIncome` |
| TSLA | 15 | `Consolidated` | `ConsolidatedStatementsofOperations` |
| META | 14 | `CONDENSED` ✅ | `CONDENSEDCONSOLIDATEDSTATEMENTSOFINCOME` |

**Key Findings:**
- **NOT universal**: Only AAPL, NVDA, META use "CONDENSED" prefix
- GOOG, AMZN, TSLA use **same names** as 10-K (`CONSOLIDATED`)
- MSFT uses unique `Role_Statement` prefix pattern
- 10-Q has **fewer trees** than 10-K (10-25 vs 23-30)

**Implications:**
- Cannot rely on "CONDENSED" prefix to identify 10-Q vs 10-K
- Use broader pattern matching: `INCOME`, `BALANCE`, `CASHFLOW` keywords
- Universal concepts still apply regardless of tree naming

---

## Implementation Results

This research led to the **Multi-Layer Concept Mapping System** achieving **99% coverage**.

### Final Coverage

| Company | Mapped | Total | Coverage |
|---------|--------|-------|----------|
| GOOG | 14 | 14 | **100%** |
| AMZN | 14 | 14 | **100%** |
| AAPL | 14 | 14 | **100%** |
| MSFT | 14 | 14 | **100%** |
| NVDA | 14 | 14 | **100%** |
| TSLA | 14 | 14 | **100%** |
| META | 12 | 13 | 92% |
| **Total** | **96** | **97** | **99.0%** |

### Architecture Built

```
Layer 1: Tree Parser     → 94% (calc tree matching)
Layer 2: AI Semantic     → +2% (custom concepts)
Layer 4: Facts Search    → +3% (concepts not in calc trees)
Reference Validator      → yfinance validation
```

---

## Key Insights Applied

1. **27 universal concepts** → Direct high-confidence mapping
2. **Calculation trees first** → No AI needed for most mappings
3. **Facts search fallback** → Some concepts exist but not in calc trees
4. **Reference validation** → Confirm mappings are correct (not copy values)
5. **Company exclusions** → META has no COGS (services company)

---

## Files

| File | Description |
|------|-------------|
| `universal_concepts.md` | All 27 universal concepts documented |
| `workflow_limitations.md` | **Limitations found + future tools to build** |
| `mag7_trees_comparison.json` | Cross-company tree comparison |
| `mag7_temporal_evolution.json` | 5-year temporal analysis |

### Implementation Files

Located in `edgar/xbrl/standardization/`:

| File | Purpose |
|------|---------|
| `config/metrics.yaml` | 14 target metrics + known concepts |
| `config/companies.yaml` | MAG7 company configs |
| `layers/tree_parser.py` | Layer 1: Calc tree matching |
| `layers/ai_semantic.py` | Layer 2: LLM semantic mapping |
| `layers/facts_search.py` | Layer 4: Direct facts search |
| `orchestrator.py` | Runs all layers with fallback |

---

## Usage

```bash
# Run mapping on MAG7
python -m edgar.xbrl.standardization.orchestrator --companies MAG7

# Save results
python -m edgar.xbrl.standardization.orchestrator --output results.json
```

---

## Related Notes

- [004_ai_agent_concept_mapping](../004_ai_agent_concept_mapping/) - AI agent design
- [001_initial_mag7_mapping_observation](../001_initial_mag7_mapping_observation/) - Initial MAG7 data

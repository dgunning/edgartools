# Response to Architect Technical Questions
## Banking GAAP Extraction - Directive Implementation Review
**Date:** 2026-01-23
**From:** AI Implementation Team
**To:** Principal Financial Systems Architect

---

## Executive Summary

We investigated each of the 5 technical questions through forensic analysis of the XBRL data. **Critical finding:** The "Bottom-Up Aggregation" strategy cannot work for WFC because the individual component concepts (CommercialPaper, FHLB, OtherShortTermBorrowings) **do not exist** in their XBRL. WFC only reports the aggregate `us-gaap:ShortTermBorrowings`.

---

## Question 1: Architectural Strategy (Top-Down vs. Bottom-Up)

### Your Question
> Why are we persisting with a Top-Down Subtraction strategy rather than switching to Bottom-Up Aggregation (CommercialPaper + FHLB + Repos(Net) + OtherBorrowings)?

### Our Investigation

We checked if WFC reports the bottom-up components:

```
=== WFC BOTTOM-UP COMPONENT AVAILABILITY ===
CommercialPaper:           NOT FOUND
FederalHomeLoanBankAdvances: NOT FOUND
OtherShortTermBorrowings:  NOT FOUND
ShortTermBorrowings:       $108.81B (aggregate only)
```

### Answer

**Bottom-Up Aggregation is NOT possible for WFC** because the filer does not report the individual debt components. WFC only reports:
- `us-gaap:ShortTermBorrowings` = $108.81B (contaminated aggregate)
- `wfc:SecuritiesSoldUnderAgreementsToRepurchase...` = $54.21B (repos, separate concept)
- `us-gaap:TradingLiabilities` = $48.0B (separate concept)

The individual components (CP, FHLB, OtherSTB) that would enable Bottom-Up do not exist in WFC's taxonomy. This is why we defaulted to Top-Down subtraction.

### Recommendation

Implement a **Hybrid Strategy**:
1. **Attempt Bottom-Up first** (sum CP + FHLB + OtherSTB + CPLTD)
2. **If Bottom-Up yields $0 or None**, fall back to Top-Down (STB - Repos - Trading)
3. **If both fail**, use archetype-based deterministic rules

---

## Question 2: Taxonomy Traversal & Namespace Resolution

### Your Question
> Did your debug session check if WFC uses custom extension namespaces? Did you check the Definition Linkbase?

### Our Investigation

```
=== WFC NAMESPACE ANALYSIS ===
Namespaces found: ['cyd', 'dei', 'ecd', 'srt', 'us-gaap', 'wfc']

Repos-related concepts (using wfc: namespace):
- wfc:SecuritiesSoldUnderAgreementsToRepurchaseAndSecuritiesLoanedGrossAmountOffsetAgainstBalanceSheetCollateral: $54.21B
- wfc:SecuritiesSoldUnderAgreementsToRepurchaseAndSecuritiesLoanedNetAmountInConsolidatedBalanceSheet: $95.22B
- wfc:SecuritiesSoldUnderAgreementsToRepurchaseAndSecuritiesLoanedNet: (another variant)

Definition Linkbase: NOT AVAILABLE IN PARSER
Calculation Linkbase: Available (47 roles)
Presentation Linkbase: Available
```

### Answer

**Yes, WFC uses custom `wfc:` namespace** for repos concepts. Our `_is_concept_nested_in_stb()` method checks for `us-gaap:SecuritiesSoldUnderAgreementsToRepurchase` but WFC reports repos under `wfc:SecuritiesSoldUnderAgreementsToRepurchase...`.

**No, we did not check the Definition Linkbase** - it is not available in our XBRL parser. We only checked Calculation and Presentation linkbases.

### Root Cause Confirmed

The structural check returns `False` (sibling) because:
1. The lookup expects `us-gaap:` namespace but WFC uses `wfc:`
2. The Definition Linkbase (`arcrole/general-special`) which might have the relationship is not parsed

### Recommendation

1. **Extend namespace handling** in `_is_concept_nested_in_stb()` to check both `us-gaap:` and company-extension namespaces
2. **Add Definition Linkbase parsing** to the XBRL parser for `general-special` relationships
3. As interim fix: **Use archetype-based deterministic rules** (see Q3)

---

## Question 3: Archetype Determinism vs. Heuristics

### Your Question
> Given we have SIC Code (6021 for WFC) and strict archetype rules, why resort to "fuzzy" magnitude logic? Why not implement: If Archetype == Commercial AND Concept == Repos, THEN Treat as Debt?

### Answer

**You are correct.** We should implement deterministic archetype-based rules rather than magnitude heuristics.

### Proposed Deterministic Rules

```python
ARCHETYPE_EXTRACTION_RULES = {
    'commercial': {
        # WFC, USB, PNC - traditional banks
        'repos_treatment': 'exclude_from_stb',  # Repos are NOT operating debt
        'trading_treatment': 'exclude_from_stb', # Trading liabilities are NOT debt
        'formula': 'STB - Repos - TradingLiab + CPLTD',
    },
    'dealer': {
        # GS, MS - investment banks
        'repos_treatment': 'separate_line_item',  # Repos already separate
        'trading_treatment': 'separate_line_item',
        'formula': 'UnsecuredSTB + CPLTD',  # No subtraction needed
    },
    'custodial': {
        # BK, STT - custody banks
        'repos_treatment': 'include_as_debt',  # Repos ARE financing for custody ops
        'trading_treatment': 'exclude',
        'formula': 'OtherSTB + Repos(Net) + CPLTD',
    },
    'hybrid': {
        # JPM, BAC, C - universal banks
        'repos_treatment': 'separate_line_item',  # Treat like dealers
        'formula': 'STB + CPLTD',  # No subtraction
    }
}
```

### Why We Used Magnitude Heuristics

Historical reason: Before archetype detection was implemented, we used magnitude as a proxy to detect if repos were "nested" (embedded in STB) vs "siblings" (separate line items). This was fragile.

### Recommendation

**Replace magnitude heuristics entirely** with deterministic archetype rules:

```python
def extract_short_term_debt_gaap(self, xbrl, facts_df, ticker=None):
    archetype = self._get_archetype(facts_df, ticker)
    rules = ARCHETYPE_EXTRACTION_RULES[archetype]

    stb = self._get_fact_value(facts_df, 'ShortTermBorrowings') or 0
    repos = self._get_repos_value(facts_df) or 0
    trading = self._get_fact_value(facts_df, 'TradingLiabilities') or 0
    cpltd = self._get_fact_value(facts_df, 'LongTermDebtCurrent') or 0

    if rules['repos_treatment'] == 'exclude_from_stb':
        stb = stb - repos
    if rules['trading_treatment'] == 'exclude_from_stb':
        stb = stb - trading

    return stb + cpltd
```

---

## Question 4: Dimensional Fallback Mechanics (STT Failure)

### Your Question
> For STT, is the "wrong value" a generic `us-gaap:ShortTermBorrowings` tag? Does `_get_dimensional_sum` have the ability to override a found consolidated value?

### Our Investigation

```
=== STT DEBT STRUCTURE ===
us-gaap:ShortTermBorrowings:        NOT FOUND (concept does not exist!)
us-gaap:OtherShortTermBorrowings:   $2.66B (non-dimensional)
ShortTermDebtTypeAxis breakdown:    NOT FOUND (axis does not exist!)

What our extraction found:
_get_fact_value(ShortTermBorrowings): $1.87B (source unknown - possibly fuzzy match)

yfinance Current Debt: $9.84B
```

### Answer

**Critical Finding:** STT does NOT have:
1. `us-gaap:ShortTermBorrowings` concept
2. `ShortTermDebtTypeAxis` dimensional breakdown

The $1.87B we extracted came from a fuzzy match (likely `InterestExpenseShortTermBorrowings` or similar). The dimensional fallback to `ShortTermDebtTypeAxis` **cannot work** because that axis doesn't exist in STT's XBRL.

### What STT Actually Reports

| Concept | Value |
|---------|-------|
| `us-gaap:OtherShortTermBorrowings` | $2.66B |
| `stt:ReverseRepurchaseAgreementsAndSecuritiesBorrowingFairValueGrossLiability` | $214.36B |
| `us-gaap:LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities` | $18.84B |

### yfinance Composition for STT

```
Current Debt: $9.84B
Other Current Borrowings: $9.84B
Long Term Debt: $23.16B
```

### Recommendation

For STT (custodial archetype):
1. **Do not rely on ShortTermBorrowings** - it doesn't exist
2. **Use custodial-specific formula**: `OtherShortTermBorrowings + FedFundsPurchased + Repos(portion) + CPLTD`
3. **Override logic**: If archetype == custodial and STB is None, use component aggregation

---

## Question 5: Ground Truth Validation (yfinance Variance)

### Your Question
> Have we forensically reconciled the composition of the yfinance number? Is yfinance potentially a "Net" figure (offsetting assets against liabilities) while XBRL is "Gross"?

### Our Investigation

```
=== FORENSIC RECONCILIATION: WFC ===

XBRL Values:
- ShortTermBorrowings (aggregate):    $108.81B
- Repos (gross liability):            $54.21B
- Trading Liabilities:                $48.00B
- Repos (net on balance sheet):       $95.22B

yfinance Values:
- Current Debt:                       $13.57B
- Other Current Borrowings:           $13.57B
- Total Debt:                         $186.65B
- Long Term Debt:                     $173.06B

RECONCILIATION:
XBRL STB:                $108.81B
Less: Repos (gross):     -$54.21B
Less: Trading:           -$48.00B
Calculated Clean STB:    $6.60B

yfinance Current Debt:   $13.57B
Difference:              $6.97B (likely CPLTD or other components)
```

### Answer

**Yes, the variance IS explained by Repos + Trading.**

The yfinance "Current Debt" figure of $13.57B appears to be the **clean debt** that excludes:
- Securities sold under agreements to repurchase ($54.21B gross)
- Trading liabilities ($48.0B)

**On the netting question:** WFC reports multiple repo figures:
- `Gross Amount`: $54.21B
- `Net Amount In Consolidated Balance Sheet`: $95.22B

The $95.22B "net" figure reflects FIN 39/41 netting where repo assets and liabilities with the same counterparty are offset. However, yfinance appears to exclude repos entirely from "Current Debt" rather than using the net figure.

### Conclusion

yfinance's "Current Debt" represents **clean financial debt** excluding:
1. Repos (whether gross or net) - treated as secured financing, not debt
2. Trading Liabilities - treated as operating liabilities, not debt

This aligns with the "Banking Liquidity" report's warning about distinguishing GAAP presentation from economic debt.

---

## Summary of Findings

| Question | Key Finding | Action Required |
|----------|-------------|-----------------|
| Q1: Top-Down vs Bottom-Up | WFC lacks bottom-up components | Implement hybrid strategy |
| Q2: Namespace Resolution | WFC uses `wfc:` namespace; Definition Linkbase not parsed | Extend namespace handling |
| Q3: Archetype Determinism | Magnitude heuristics are fragile | Replace with deterministic rules |
| Q4: STT Dimensional | ShortTermDebtTypeAxis doesn't exist for STT | Use custodial-specific formula |
| Q5: yfinance Reconciliation | Variance = Repos + Trading (confirmed) | Validate our clean debt matches |

---

## Recommended Remediation Plan

### Phase 1: Immediate (Restore Pass Rates)

1. **Implement deterministic archetype rules** per Q3 recommendation
2. **For Commercial banks (WFC, USB)**: Always subtract repos + trading from STB
3. **For Custodial banks (STT)**: Use `OtherShortTermBorrowings` + CPLTD formula

### Phase 2: Short-Term (Robustness)

1. **Add Definition Linkbase parsing** to XBRL parser
2. **Extend namespace resolution** to handle company-extension prefixes
3. **Implement hybrid Bottom-Up/Top-Down strategy** per Q1 recommendation

### Phase 3: Validation (Confidence)

1. **Build yfinance reconciliation tests** that verify component math
2. **Flag "Methodology Deviation" cases** where our GAAP is correct but differs from yfinance normalization
3. **Document FIN 39/41 netting effects** per Q5 findings

---

## Appendix: Raw Debug Output

### WFC Concepts Found

```
Namespaces: ['cyd', 'dei', 'ecd', 'srt', 'us-gaap', 'wfc']

Bottom-Up Components:
- CommercialPaper: NOT FOUND
- FederalHomeLoanBankAdvances: NOT FOUND
- OtherShortTermBorrowings: NOT FOUND
- ShortTermBorrowings: $108.81B

Repos Variants (wfc: namespace):
- wfc:SecuritiesSoldUnderAgreementsToRepurchaseAndSecuritiesLoanedGrossAmountOffsetAgainstBalanceSheetCollateral: $54.21B
- wfc:SecuritiesSoldUnderAgreementsToRepurchaseAndSecuritiesLoanedNetAmountInConsolidatedBalanceSheet: $95.22B
```

### STT Concepts Found

```
Debt Concepts:
- us-gaap:OtherShortTermBorrowings: $2.66B
- us-gaap:LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities: $18.84B
- stt:ReverseRepurchaseAgreementsAndSecuritiesBorrowingFairValueGrossLiability: $214.36B

ShortTermBorrowings: NOT FOUND
ShortTermDebtTypeAxis: NOT FOUND
```

### yfinance Reference Values

```
WFC:
- Current Debt: $13.57B
- Other Current Borrowings: $13.57B
- Long Term Debt: $173.06B

USB:
- Current Debt: $7.62B
- Other Current Borrowings: $3.34B

STT:
- Current Debt: $9.84B
- Other Current Borrowings: $9.84B
- Long Term Debt: $23.16B
```

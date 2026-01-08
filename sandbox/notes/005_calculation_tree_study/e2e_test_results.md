# E2E Test Results: Concept Mapping Workflow

## Overview

Executed the E2E test plan defined in `e2e_test_ai_tools.md` on 3 MAG7 companies: AAPL, GOOG, AMZN.

## Summary of Findings

1.  **Orchestrator & Validation Logic**: ✅ **Pass**
    *   Correctly identified gaps and invalid mappings.
    *   Validation feedback loop works: flagged `TotalAssets`, `IntangibleAssets`, and `LongTermDebt` as `INVALID` due to value mismatches.

2.  **Tool Execution**: ✅ **Pass**
    *   `discover_concepts`: Successfully found semantic candidates (e.g., `us-gaap:FiniteLivedIntangibleAssetsNet` for AMZN IntangibleAssets).
    *   `check_fallback_quality`: Correctly validated semantic quality.
    *   `learn_mappings`: Successfully discovered patterns across companies.

3.  **Gap Resolution**: ❌ **Fail**
    *   `resolve_all_gaps` failed to resolve any of the 9 identified invalid mappings.
    *   **Root Cause**: Value mismatch between XBRL extracted data and yfinance reference data.

## Detailed Issues

### 1. Consolidation / Entity Context Issue (TotalAssets)
Large discrepancies suggest extraction of "Parent Company Only" values instead of "Consolidated" values.

*   **AAPL**: 14.59B (XBRL) vs 359.24B (Ref)
*   **GOOG**: 184.62B (XBRL) vs 450.26B (Ref)
*   **AMZN**: 3.48B (XBRL) vs 624.89B (Ref)

**Hypothesis**: The extraction logic might be picking up the non-consolidated legal entity values which often appear in 10-Ks alongside consolidated statements.

### 2. Component Mismatch (IntangibleAssets)
The discovered concept was `FiniteLived...` which likely excludes Indefinite Lived assets or Goodwill, whereas the reference metric includes them.

*   **AMZN**: 7.44B (XBRL) vs 31.68B (Ref)
*   Top candidate: `us-gaap:FiniteLivedIntangibleAssetsNet` (7.44B)

### 3. Definition Differences (LongTermDebt)
*   **AAPL**: 49.30B vs 78.33B
*   **GOOG**: 9.00B vs 10.88B
*   **AMZN**: 5.00B vs 52.62B

## Recommendations

1.  **Enhance Value Extraction**: Update `_extract_xbrl_value` to prefer consolidated contexts or check dimensions.
2.  **Composite Logic**: Allow `resolve_gaps` to try summing components (e.g. `Finite` + `Indefinite`) if a single concept doesn't match.
3.  **Validation Tolerance**: Investigate if yfinance definitions match standard GAAP tags or if logic needs adjustment (e.g., adding `CurrentLongTermDebt` to `LongTermDebt`).

## Next Steps

Investigate `edgar/xbrl/standardization/reference_validator.py` extraction logic to handle entity consolidation.

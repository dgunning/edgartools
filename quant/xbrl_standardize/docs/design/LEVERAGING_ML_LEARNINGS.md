# Leveraging ML Learnings for Balance Sheet Mapping

**Date**: 2026-01-02
**Purpose**: Use ML-learned data from `training/output/` to systematically enhance `balance-sheet.json`
**Status**: STRATEGY DOCUMENT

---

## Available ML Data

The `C:\edgartools_git\training\output\` directory contains rich ML-learned data from **300+ companies**:

| File | Purpose | Key Fields |
|------|---------|------------|
| `canonical_structures_{sector}.json` | Statement hierarchies | `is_total`, `avg_depth`, `parent`, `occurrence_rate` |
| `learned_mappings_{sector}.json` | Concept metadata | `statement_type`, `confidence`, `label` |
| `learning_statistics_{sector}.json` | Usage statistics | Concept frequency, co-occurrence |
| `statement_mappings_v1_{sector}.json` | ML-generated mappings | Field→concept mappings with confidence |

**Sectors Available**: `global`, `banking`, `insurance`, `utilities`

---

## Issue #5 Validation Using ML Data

### What ML Data Shows

**Banking Cash Concepts** (from `canonical_structures_banking.json`):

| Concept | is_total | Occurrence | Depth | Classification |
|---------|----------|------------|-------|----------------|
| `CashAndDueFromBanks` | ❌ false | 73.2% | 3.3 | **COMPONENT** |
| `CashAndCashEquivalentsAtCarryingValue` | ✅ true | 42.5% | 3.1 | **TOTAL** |
| `CashCashEquivalentsAndFederalFundsSold` | ✅ true | 22.0% | 2.8 | **TOTAL** |
| `CashCashEquivalentsRestrictedCash...` | ✅ true | 6.3% | 3.0 | **TOTAL** |

**Key Insight**: ML system correctly identified:
- `CashAndDueFromBanks` (73% occurrence) is a COMPONENT, not a total
- Despite being most common, it should NOT be prioritized
- Total concepts have lower depth (closer to root) and `is_total: true` flag

---

## Enhancement Strategy

### Phase 1: Validate Current Mappings

Use ML data to audit existing `balance-sheet.json` selectAny arrays:

**Algorithm**:
1. For each field in balance-sheet.json
2. Extract all concepts in `selectAny` arrays
3. Look up each concept in `canonical_structures_{sector}.json`
4. Check `is_total` flag and `avg_depth`
5. **Flag** if component concept appears before total concept

**Example - Cash Field Audit**:
```python
# balance-sheet.json (BEFORE FIX):
selectAny = [
    "us-gaap:CashAndDueFromBanks",  # ← is_total: false, depth: 3.3
    "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",  # ← is_total: true, depth: 3.0
]

# ML audit result:
WARNING: Component concept (CashAndDueFromBanks) listed before total concept!
SUGGESTION: Reorder to: [
    "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",  # Total first
    "us-gaap:CashAndDueFromBanks"  # Component as fallback
]
```

---

### Phase 2: Auto-Generate selectAny Ordering

Use ML occurrence rates and is_total flags to automatically generate optimal selectAny orders:

**Prioritization Algorithm**:
```python
def sort_concepts_by_priority(concepts, sector='global'):
    """Sort concepts: totals before components, high occurrence before low."""
    canonical = load_canonical_structures(sector)

    def concept_priority(concept):
        info = canonical.get(concept, {})
        is_total = info.get('is_total', False)
        occurrence = info.get('occurrence_rate', 0)
        depth = info.get('avg_depth', 99)

        # Priority tuple: (is_total desc, occurrence desc, depth asc)
        return (
            0 if is_total else 1,  # Totals first
            -occurrence,            # Higher occurrence first
            depth                   # Lower depth (parent) first
        )

    return sorted(concepts, key=concept_priority)
```

**Example Output**:
```json
{
    "name": "Banks: Cash (ML-optimized order)",
    "selectAny": [
        "us-gaap:CashAndCashEquivalentsAtCarryingValue",  // is_total:true, 42.5%, depth:3.1
        "us-gaap:CashCashEquivalentsAndFederalFundsSold", // is_total:true, 22.0%, depth:2.8
        "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",  // is_total:true, 6.3%, depth:3.0
        "us-gaap:CashAndDueFromBanks"  // is_total:false, 73.2%, depth:3.3 (fallback only)
    ]
}
```

---

### Phase 3: Add Missing Concepts

ML data reveals concepts we may have missed:

**Example - Cash Concepts Not in balance-sheet.json**:
```
From canonical_structures_banking.json:
✓ CashCashEquivalentsAndFederalFundsSold - 22.0% occurrence (TOTAL)
✗ Missing from our mapping!
```

**Action**: Add high-occurrence concepts to selectAny arrays:
```json
{
    "selectAny": [
        "us-gaap:CashCashEquivalentsAndFederalFundsSold",  // ← ADD THIS (22% occurrence in banks)
        "us-gaap:CashAndCashEquivalentsAtCarryingValue",
        // ...
    ]
}
```

---

### Phase 4: Industry-Specific Optimization

Use sector-specific canonical structures to optimize industry rules:

**Banking Balance Sheet**:
```python
# Load banking-specific learnings
banking = load_canonical_structures('banking')

# Top 10 banking-specific concepts:
# - CashAndDueFromBanks: 73.2% (component)
# - LoansAndLeasesReceivableNetOfDeferredIncome: 65.4%
# - Deposits: 64.6%
# - AvailableForSaleSecuritiesDebtSecurities: 61.4%

# Add these to banking industry rules at Priority 150
```

**Insurance Balance Sheet**:
```python
# Load insurance-specific learnings
insurance = load_canonical_structures('insurance')

# Top insurance-specific concepts:
# - DeferredPolicyAcquisitionCosts: 71.2%
# - PolicyLiabilitiesAndAccruals: 68.4%
# - PremiumsReceivableAtCarryingValue: 54.2%
```

---

### Phase 5: Add Confidence Metadata

Enhance balance-sheet.json with ML confidence scores:

**Current Structure**:
```json
{
    "cash": {
        "rules": [{
            "selectAny": ["us-gaap:CashAndCashEquivalentsAtCarryingValue"]
        }]
    }
}
```

**Enhanced with ML Metadata**:
```json
{
    "cash": {
        "rules": [{
            "selectAny": ["us-gaap:CashAndCashEquivalentsAtCarryingValue"],
            "ml_confidence": 0.677,
            "ml_occurrence_global": 0.677,
            "ml_occurrence_banking": 0.425,
            "ml_is_total": true,
            "ml_avg_depth": 4.0,
            "ml_companies": 222
        }]
    }
}
```

**Benefits**:
- Validation: Low confidence = needs review
- Debugging: Understand why extraction failed
- Monitoring: Track extraction success vs ML predictions
- Evolution: Retrain mappings as taxonomy changes

---

## Concrete Enhancement Examples

### 1. Cash Field (DONE - Manual Fix)

**Before** (manual mapping):
```json
{
    "selectAny": [
        "us-gaap:CashAndDueFromBanks",  // ← Component first (WRONG)
        "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    ]
}
```

**After ML-Informed Fix**:
```json
{
    "selectAny": [
        "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",  // ← Total first (ML: is_total=true)
        "us-gaap:CashAndCashEquivalentsAtCarryingValue",  // ML: is_total=true, 67.7% global
        "us-gaap:CashCashEquivalentsAndFederalFundsSold",  // ML: is_total=true, 22% banking
        "us-gaap:CashAndDueFromBanks"  // ML: is_total=false (fallback only)
    ]
}
```

---

### 2. Short-Term Investments (TODO)

**Current Mapping**:
```json
{
    "name": "Banks: Trading securities",
    "selectAny": [
        "us-gaap:TradingSecurities",
        "us-gaap:AvailableForSaleSecuritiesDebtSecuritiesCurrent"
    ]
}
```

**ML Data Shows**:
```
From canonical_structures_banking.json:
- TradingSecurities: 31.5% occurrence
- AvailableForSaleSecuritiesDebtSecurities: 61.4% occurrence ← Higher!
- MarketableSecurities: 11.8% occurrence (is_total: true)
```

**ML-Optimized**:
```json
{
    "name": "Banks: Short-term securities (ML-optimized)",
    "selectAny": [
        "us-gaap:MarketableSecurities",  // ← Total (if current portion tagged separately)
        "us-gaap:AvailableForSaleSecuritiesDebtSecuritiesCurrent",  // ← 61.4% occurrence
        "us-gaap:TradingSecurities",  // 31.5% occurrence
        "us-gaap:ShortTermInvestments"  // Generic fallback
    ]
}
```

---

### 3. Deposits (Already Good!)

**Current Mapping**:
```json
{
    "selectAny": ["us-gaap:Deposits"]
}
```

**ML Validation**:
```
From canonical_structures_banking.json:
- Deposits: 64.6% occurrence, is_total: true ✓
```

**Status**: ✅ Already optimal!

---

## Implementation Tools

### Tool 1: ML Mapping Auditor

```bash
python tools/audit_mapping_with_ml.py \
    --mapping balance-sheet.json \
    --ml-data training/output/canonical_structures_banking.json \
    --sector banking \
    --output audit_report.md
```

**Output**:
```markdown
## Audit Report

### Issues Found: 3

1. **cash** - Component before total
   - CashAndDueFromBanks (is_total: false, 73.2%) listed before totals
   - Suggest: Reorder selectAny array

2. **shortTermInvestments** - Missing high-occurrence concept
   - AvailableForSaleSecuritiesDebtSecurities (61.4%) not in selectAny
   - Suggest: Add to selectAny array

3. **accountsReceivable** - OK ✓
```

---

### Tool 2: ML Concept Ranker

```bash
python tools/rank_concepts.py \
    --field cash \
    --sector banking \
    --ml-data training/output/
```

**Output**:
```
Recommended selectAny order for 'cash' (banking):
1. us-gaap:CashCashEquivalentsAndFederalFundsSold (is_total: true, 22.0%, depth: 2.8)
2. us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents (is_total: true, 6.3%, depth: 3.0)
3. us-gaap:CashAndCashEquivalentsAtCarryingValue (is_total: true, 42.5%, depth: 3.1)
4. us-gaap:CashAndDueFromBanks (is_total: false, 73.2%, depth: 3.3)  ← Component (fallback)
```

---

### Tool 3: ML Mapping Generator

```bash
python tools/generate_mapping_from_ml.py \
    --statement balance-sheet \
    --sector banking \
    --ml-data training/output/ \
    --output balance-sheet-ml.json
```

**Generates**: Fully ML-driven balance-sheet.json with:
- Concepts sorted by: is_total (desc), occurrence (desc), depth (asc)
- Industry-specific rules at Priority 150
- Computation fallbacks based on concept linkages
- Confidence metadata for each concept

---

## Validation Strategy

### 1. Systematic Testing

**Test Matrix**:
| Sector | Companies | Expected Improvement |
|--------|-----------|----------------------|
| Banking | BAC, JPM, WFC, C | +10-15% extraction rate |
| Corporate | AAPL, MSFT, GOOGL | No regression |
| Insurance | PGR, MET | +5-10% extraction rate |
| Utilities | NEE, SO | +5-10% extraction rate |

---

### 2. Metrics to Track

```python
{
    "field": "cash",
    "before_ml": {
        "BAC": 26000000000,  # Component value
        "extraction_rate": "48.4%"
    },
    "after_ml": {
        "BAC": 290114000000,  # Total value ✓
        "extraction_rate": "48.4%",  # Same field count, better accuracy
        "accuracy_improvement": "+91%"  # Cash value accuracy
    }
}
```

---

### 3. Regression Testing

**Ensure ML enhancements don't break existing extractions**:
```bash
# Baseline
python bs.py --symbol AAPL > baseline_aapl.json

# After ML enhancements
python bs.py --symbol AAPL > ml_aapl.json

# Compare
diff baseline_aapl.json ml_aapl.json
# Expected: No changes or improvements only
```

---

## Next Steps

### Immediate (This Session)
1. ✅ Document ML data availability and structure
2. ⬜ Create audit tool to identify component-before-total issues
3. ⬜ Run audit on all 31 balance sheet fields
4. ⬜ Apply ML-recommended fixes systematically

### Short-Term (This Week)
1. ⬜ Build concept ranker tool
2. ⬜ Add missing high-occurrence concepts to mappings
3. ⬜ Test ML-enhanced mapping across 10+ companies
4. ⬜ Add confidence metadata to balance-sheet.json

### Medium-Term (This Month)
1. ⬜ Build full ML mapping generator
2. ⬜ Create hybrid approach: Manual rules + ML validation
3. ⬜ Extend to income statement and cash flow mappings
4. ⬜ Set up automated retraining pipeline

---

## Conclusion

**Key Realization**: The ML system (`run_learning.py` → `training/output/`) has ALREADY solved the problems I identified as "long-term":

| "Long-Term" Goal | ML Solution | Status |
|------------------|-------------|--------|
| Concept taxonomy | `canonical_structures*.json` | ✅ DONE |
| Aggregate vs component | `is_total` flags | ✅ DONE |
| Presentation hierarchies | `parent`, `avg_depth` | ✅ DONE |
| Occurrence statistics | `occurrence_rate` | ✅ DONE |
| Industry patterns | `*_banking.json`, `*_insurance.json` | ✅ DONE |
| Optimal ordering | Rankable by is_total + occurrence + depth | ✅ READY |

**Recommendation**:
- ✅ Use ML data to VALIDATE and ENHANCE current manual mappings
- ✅ Build tools to systematically apply ML insights
- ✅ Create hybrid approach: Manual curation + ML validation
- ✅ Set up feedback loop: Extraction results → retrain ML → update mappings

**Status**: ✅ STRATEGY READY FOR IMPLEMENTATION

---

**Document Date**: 2026-01-02
**ML Data Source**: `C:\edgartools_git\training\output\`
**Companies Analyzed**: 300+ (global), 127 (banking), 104 (insurance), 89 (utilities)
**Ready to Use**: ✅ YES

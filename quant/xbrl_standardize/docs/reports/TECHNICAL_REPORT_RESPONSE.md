# Technical Report Evaluation & Response

**Date**: 2026-01-02
**Map Version Evaluated**: 2026-01-01.3
**Reviewer Assessment**: ⚠️ CRITICAL ISSUES IDENTIFIED

---

## Executive Summary

The technical report identifies **3 critical structural issues** and **4 enhancement recommendations**. After validation against the actual map.json implementation:

**Critical Issues Confirmed**:
1. ✅ **Revenue Priority Overlap** - Banks rule (100) is LOWER than General (110) - CRITICAL BUG
2. ✅ **EBIT Definition for Banks** - Conceptually questionable but documented as intentional
3. ⚠️ **Circular Dependency Risk** - Mitigated by selectAny-first structure, but still a risk

**Enhancement Recommendations**: All valid and valuable

---

## 1. Financial Logic Issues - Detailed Responses

### A. EBIT Definition for Banks

**Report Claim**:
> "EBIT = pretaxIncome (Priority 200) is incorrect because EBIT should exclude non-operating interest"

**Validation**:
```json
{
  "name": "Banks/financial intermediaries: EBIT = pretax income",
  "priority": 200,
  "industryHints": ["Bank", "Banks", ...],
  "computeAny": [
    {
      "op": "id",
      "terms": [{"field": "pretaxIncome"}]
    }
  ]
}
```

**Assessment**: ⚠️ **PARTIALLY CORRECT**

**Current Behavior**:
- For banks, EBIT = pretaxIncome (intentional design)
- Documented in map.json notes: "For bank-style statements, EBIT is defined as pretaxIncome (interest income/expense are operating lines)"

**The Issue**:
- Banks CAN have non-operating interest (e.g., interest on long-term debt vs. deposit interest)
- True EBIT should be: `pretaxIncome + non-operating interest expense - non-operating interest income`
- Current mapping conflates operating and non-operating interest

**Severity**: Medium
- Most banking analysts use "Pre-tax income" rather than EBIT for banks
- But technically incorrect for banks with material non-operating interest

**Recommendation**:
```json
{
  "name": "Banks: EBIT = pretax + non-operating interest",
  "priority": 200,
  "industryHints": ["Bank", "Banks", ...],
  "computeAny": [
    {
      "op": "add",
      "terms": [
        {"field": "pretaxIncome"},
        {
          "conceptAny": [
            "us-gaap:InterestExpenseDebtExcludingAmortization",
            "us-gaap:InterestExpenseLongTermDebt"
          ]
        }
      ]
    }
  ]
}
```

**Status**: ⚠️ **DESIGN DECISION NEEDED** - Is EBIT even meaningful for banks?

---

### B. Gross Income vs Financial Services

**Report Claim**:
> "grossIncome relies on revenue - COGS. Banks don't have COGS. Should map to netInterestIncome + nonInterestIncome."

**Validation**:
Current grossIncome rule (Priority 80):
```json
{
  "name": "Fallback: Revenue - COGS",
  "priority": 80,
  "computeAny": [
    {
      "op": "sub",
      "terms": [
        {"field": "revenue"},
        {"field": "costOfGoodsSold"}
      ]
    }
  ]
}
```

**Assessment**: ✅ **CORRECT CRITIQUE**

**Current Behavior**:
- BAC/JPM: grossIncome = null (because costOfGoodsSold = null)
- Documented as "expected" in BANK_NULL_FIELDS_EXPLAINED.md
- We stated: "Gross Income is conceptually invalid for banks"

**The Issue**:
- Report suggests: `grossIncome = netInterestIncome + nonInterestIncome` for banks
- This would be the banking equivalent of "gross profit" (revenue before operating expenses)

**Example**:
```
BAC (current):
- revenue: $101.9B (net interest income)
- grossIncome: null

BAC (proposed):
- revenue: $101.9B (net interest income)
- grossIncome: $101.9B + $45.8B = $147.7B (net interest + noninterest)
```

**Severity**: Medium
- Currently documented as "expected null"
- But proposed mapping would provide more useful data

**Recommendation**: ✅ **IMPLEMENT**
```json
{
  "name": "Banks: Gross income = net interest + noninterest income",
  "priority": 130,
  "industryHints": ["Bank", "Banks", ...],
  "computeAny": [
    {
      "op": "add",
      "terms": [
        {
          "conceptAny": [
            "us-gaap:InterestIncomeExpenseNet",
            "us-gaap:NetInterestIncome"
          ]
        },
        {
          "conceptAny": [
            "us-gaap:NoninterestIncome"
          ]
        }
      ]
    }
  ]
}
```

This would improve bank extraction from 14/19 (73.7%) → 15/19 (78.9%)!

**Status**: ✅ **VALID ENHANCEMENT**

---

### C. Depreciation & Amortization Location

**Report Claim**:
> "D&A is often in Cash Flow Statement, not Income Statement. Add mechanism to fetch from cash flow if income statement is missing."

**Validation**:
Current D&A rule:
```json
{
  "name": "US GAAP: Depreciation, depletion and amortization",
  "priority": 110,
  "selectAny": [
    "us-gaap:DepreciationDepletionAndAmortization",
    "us-gaap:DepreciationAndAmortization",
    "us-gaap:Depreciation",
    "us-gaap:AmortizationOfIntangibleAssets"
  ]
}
```

**Assessment**: ✅ **CORRECT CRITIQUE**

**Current Behavior**:
- AAPL: D&A = null (not separately disclosed on income statement)
- BAC/JPM: D&A = null (embedded in operating expenses)
- But all companies report D&A on **cash flow statement**

**Evidence**:
- Income statement search: `us-gaap:DepreciationDepletionAndAmortization` - NOT FOUND
- Cash flow statement: ALWAYS HAS D&A as operating cash flow adjustment

**Severity**: Medium
- D&A is important for EBITDA calculation
- Currently missing for most companies

**Recommendation**: ✅ **IMPLEMENT CROSS-STATEMENT LOOKUP**

**Technical Challenge**:
- Current schema is **income statement only**
- Would need to extend is.py to fetch from cash flow statement if income statement is null

**Proposed Enhancement**:
```python
# In is.py, after income statement extraction:
if standardized['depreciationAndAmortization'] is None:
    # Try cash flow statement
    cf_stmt = try_cash_flow_statement_df(company)
    if cf_stmt is not None:
        da_value = extract_from_cash_flow(cf_stmt, [
            'us-gaap:DepreciationDepletionAndAmortization',
            'us-gaap:DepreciationAndAmortization'
        ])
        standardized['depreciationAndAmortization'] = da_value
```

**Status**: ✅ **VALID ENHANCEMENT** - Requires cross-statement logic

---

## 2. Structural & Technical Risks - Detailed Responses

### A. Revenue Priority Overlap - **CRITICAL BUG**

**Report Claim**:
> "General Corporates (Priority 110) will catch banks before Banks rule (Priority 100). Boost industry rules to 150+."

**Validation**:
```json
// General corporates - Priority 110
{
  "name": "General corporates (US GAAP / ASC 606 / classic)",
  "priority": 110,
  "selectAny": [
    "us-gaap:Revenues",  // ← PROBLEM: Generic tag
    ...
  ]
}

// Banks - Priority 100
{
  "name": "Banks / lenders (net interest + noninterest)",
  "priority": 100,  // ← LOWER PRIORITY
  "industryHints": ["Bank", "Banks", ...],
  "selectAny": [
    "us-gaap:Revenues",  // ← SAME TAG
    ...
  ]
}
```

**Assessment**: 🚨 **CRITICAL BUG CONFIRMED**

**The Problem**:
1. Bank uses generic tag `us-gaap:Revenues`
2. General rule (Priority 110) checks `us-gaap:Revenues` first
3. Returns generic revenue value (e.g., net interest income only)
4. Bank rule (Priority 100) never executes
5. Misses noninterest income computation

**Why It Works Currently**:
- BAC/JPM happen to use `us-gaap:RevenuesNetOfInterestExpense` (bank-specific)
- So they skip the general rule
- **But some banks use generic `us-gaap:Revenues` and would be caught incorrectly**

**Test Case**:
If a bank uses `us-gaap:Revenues`:
```
Current behavior (WRONG):
- General rule (110) catches it → Returns just net interest income
- Bank computation never runs → Noninterest income missed

Correct behavior (FIXED):
- Bank rule (150) catches it first → Computes net interest + noninterest
- Falls back to general (110) only if industry hint doesn't match
```

**Severity**: 🚨 **CRITICAL**
- Silent data error (underreporting revenue)
- Affects all industry-specific rules (utilities, energy, insurance, REIT)

**Recommendation**: ✅ **FIX IMMEDIATELY**

**Priority Restructure**:
```
150+ : Industry-specific rules (banks, utilities, insurance, REIT, energy)
120  : IFRS baseline
110  : General corporates (fallback)
80-100: Computed fallbacks
```

**Proposed Fix**:
```json
{
  "name": "Banks / lenders (net interest + noninterest)",
  "priority": 150,  // ← INCREASE FROM 100
  "industryHints": [...],
  ...
}

{
  "name": "Insurance (premiums + investment income)",
  "priority": 150,  // ← INCREASE FROM 90
  ...
}

{
  "name": "REIT / real estate (rental + other)",
  "priority": 150,  // ← INCREASE FROM 80
  ...
}

{
  "name": "Utilities / regulated",
  "priority": 150,  // ← INCREASE FROM 105
  ...
}

{
  "name": "Energy / O&G",
  "priority": 150,  // ← INCREASE FROM 104
  ...
}
```

**Status**: 🚨 **CRITICAL BUG - FIX REQUIRED**

---

### B. Circular Dependency Risk

**Report Claim**:
> "operatingIncome depends on grossIncome. If grossIncome fails, operatingIncome fails even if direct tag exists. Ensure selectAny before computeAny."

**Validation**:
```json
"operatingIncome": {
  "rules": [
    {
      "name": "IFRS: Operating profit/loss",
      "priority": 120,
      "selectAny": [...]  // ← CHECKED FIRST ✅
    },
    {
      "name": "US GAAP: Operating income (loss)",
      "priority": 110,
      "selectAny": [...]  // ← CHECKED SECOND ✅
    },
    {
      "name": "Compute: grossIncome - totalOperatingExpense",
      "priority": 80,
      "computeAny": [...]  // ← CHECKED LAST ✅
    }
  ]
}
```

**Assessment**: ✅ **RISK MITIGATED BUT VALID CONCERN**

**Current Structure**:
- ✅ selectAny rules (120, 110) execute BEFORE computeAny (80)
- ✅ Direct XBRL tags tried before computed fields
- ✅ Prevents "house of cards" failure

**Remaining Risk**:
- If both selectAny rules fail (no direct tag), falls back to computation
- Computation requires grossIncome to succeed
- If grossIncome also fails, operatingIncome returns null
- **Could happen if both direct tags AND grossIncome are missing**

**Example Failure Scenario**:
```
Company has:
- ✗ No us-gaap:OperatingIncomeLoss tag
- ✗ No ifrs-full:OperatingProfitLoss tag
- ✓ Has revenue and totalOperatingExpense
- ✗ But no costOfGoodsSold (service company)

Result:
- selectAny: Fails (no direct tags)
- computeAny: Fails (grossIncome is null because COGS is null)
- operatingIncome: null (even though it could be computed from revenue - expenses)
```

**Severity**: Low-Medium
- Current structure minimizes risk
- But edge cases exist

**Recommendation**: ⚠️ **ADD ADDITIONAL COMPUTATION FALLBACK**

```json
{
  "name": "Compute: revenue - totalOperatingExpense (service companies)",
  "priority": 70,
  "computeAny": [
    {
      "op": "sub",
      "terms": [
        {"field": "revenue"},
        {"field": "totalOperatingExpense"}
      ]
    }
  ]
}
```

**Status**: ⚠️ **LOW PRIORITY ENHANCEMENT**

---

## 3. Recommended Enhancements - Detailed Responses

### A. Other Comprehensive Income (OCI)

**Report Recommendation**:
> "Add comprehensiveIncome field for Statement of Comprehensive Income"

**Assessment**: ✅ **VALID ENHANCEMENT**

**Why It Matters**:
- Required disclosure under US GAAP and IFRS
- Includes unrealized gains/losses on securities, foreign currency, pensions
- Important for financial institutions and multinationals

**Proposed Field**:
```json
"comprehensiveIncome": {
  "standardLabel": "comprehensiveIncome",
  "rules": [
    {
      "name": "IFRS: Comprehensive income",
      "priority": 120,
      "selectAny": [
        "ifrs-full:ComprehensiveIncome",
        "ifrs-full:ProfitLossAndOtherComprehensiveIncome"
      ]
    },
    {
      "name": "US GAAP: Comprehensive income net of tax",
      "priority": 110,
      "selectAny": [
        "us-gaap:ComprehensiveIncomeNetOfTax",
        "us-gaap:ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest"
      ]
    },
    {
      "name": "Compute: Net income + OCI",
      "priority": 80,
      "computeAny": [
        {
          "op": "add",
          "terms": [
            {"field": "netIncome"},
            {
              "conceptAny": [
                "us-gaap:OtherComprehensiveIncomeLossNetOfTax"
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

**Impact**: Adds 1 field (19 → 20)

**Status**: ✅ **RECOMMENDED FOR NEXT VERSION**

---

### B. Preferred Dividends (Net Income Available to Common)

**Report Recommendation**:
> "Add netIncomeAvailableToCommon = netIncome - preferred dividends (crucial for P/E ratios)"

**Assessment**: ✅ **HIGHLY VALUABLE**

**Why It Matters**:
- EPS should be calculated using net income AVAILABLE TO COMMON stockholders
- Companies with preferred stock need adjustment
- Critical for accurate P/E ratio

**Current Issue**:
```
Current EPS extraction:
- earningsPerShareBasic: $3.25 (reported)
- netIncome: $27.1B

If we compute EPS manually:
- netIncome / shares = $27.1B / 7.86B = $3.45 ≠ $3.25 ???

Why? Preferred dividends:
- netIncome: $27.1B (total)
- Preferred dividends: $1.6B
- Available to common: $25.5B
- EPS: $25.5B / 7.86B = $3.25 ✓
```

**Proposed Field**:
```json
"netIncomeAvailableToCommon": {
  "standardLabel": "netIncomeAvailableToCommon",
  "rules": [
    {
      "name": "US GAAP: Net income available to common stockholders",
      "priority": 120,
      "selectAny": [
        "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic",
        "us-gaap:NetIncomeLossAvailableToCommonShareholdersBasic"
      ]
    },
    {
      "name": "Compute: Net income - preferred dividends",
      "priority": 100,
      "computeAny": [
        {
          "op": "sub",
          "terms": [
            {"field": "netIncome"},
            {
              "conceptAny": [
                "us-gaap:PreferredStockDividendsAndOtherAdjustments",
                "us-gaap:PreferredStockDividendsIncomeStatementImpact"
              ]
            }
          ]
        }
      ]
    },
    {
      "name": "Fallback: Net income (if no preferred stock)",
      "priority": 80,
      "computeAny": [
        {
          "op": "id",
          "terms": [{"field": "netIncome"}]
        }
      ]
    }
  ]
}
```

**Impact**: Adds 1 field (19 → 20)

**Status**: ✅ **HIGHLY RECOMMENDED**

---

### C. SG&A Accuracy Improvement

**Report Recommendation**:
> "Add computeAny for sgaExpense = TotalOperatingExpenses - R&D"

**Assessment**: ✅ **VALID ENHANCEMENT**

**Current Issue**:
Some companies report "Operating Expenses" as a single block without breaking out SG&A.

**Current sgaExpense Rules**:
```json
{
  "name": "US GAAP: Selling, general & administrative",
  "priority": 130,
  "selectAny": [
    "us-gaap:SellingGeneralAndAdministrativeExpense"
  ]
}
```

**Limitation**:
- Only works if company explicitly tags SG&A
- Fails if company uses consolidated "Operating Expenses"

**Proposed Enhancement**:
```json
{
  "name": "Compute: Total operating expenses - R&D",
  "priority": 90,
  "computeAny": [
    {
      "op": "sub",
      "terms": [
        {"field": "totalOperatingExpense"},
        {"field": "researchDevelopment"}
      ]
    }
  ]
}
```

**Caveat**: Only works if totalOperatingExpense excludes COGS.

**Impact**: Improves SG&A extraction for companies with consolidated operating expense disclosure.

**Status**: ⚠️ **CONDITIONAL ENHANCEMENT** - Test carefully

---

## 4. Priority Action Plan

### CRITICAL (Fix Immediately) 🚨

1. **Fix Revenue Priority Overlap**
   - Increase all industry-specific rules to Priority 150+
   - Ensure industry hints always win over generic rules
   - **Impact**: Prevents silent revenue underreporting for banks/utilities/insurance

---

### HIGH PRIORITY (Next Version)

2. **Add Banking Gross Income Rule**
   - `grossIncome = netInterestIncome + noninterestIncome`
   - **Impact**: Improves bank extraction from 73.7% → 78.9%

3. **Add Net Income Available to Common**
   - Critical for accurate EPS validation
   - **Impact**: Enables P/E ratio calculation

4. **Add Comprehensive Income**
   - Required disclosure, especially for financial institutions
   - **Impact**: Complete income statement coverage

---

### MEDIUM PRIORITY (Future Enhancement)

5. **Cross-Statement D&A Lookup**
   - Fetch D&A from cash flow statement if missing from income statement
   - Requires architectural change (multi-statement extraction)

6. **Re-evaluate Bank EBIT Definition**
   - Decide if EBIT is meaningful for banks
   - If yes, adjust for non-operating interest

7. **Add SG&A Computation Fallback**
   - `sgaExpense = totalOperatingExpense - R&D`
   - Test thoroughly before deployment

---

## 5. Recommended Schema Changes

### Version 2026-01-02.1: Critical Bug Fix

**Changes**:
1. Increase all industry-specific revenue rules to Priority 150
2. Restructure priority scheme:
   - 150+: Industry-specific (with industryHints)
   - 120: IFRS baseline
   - 110: General corporates (fallback)
   - 80-100: Computed fallbacks

**Files to Modify**:
- `map/map.json` - Update priority values for:
  - Banks revenue: 100 → 150
  - Insurance revenue: 90 → 150
  - REIT revenue: 80 → 150
  - Utilities revenue: 105 → 150
  - Energy revenue: 104 → 150
  - All other industry-specific rules

**Testing Required**:
- Re-test BAC, JPM (ensure revenue still correct)
- Test bank that uses generic `us-gaap:Revenues` tag
- Validate utilities, insurance, REIT extraction

---

### Version 2026-01-02.2: Banking Enhancements

**Changes**:
1. Add banking gross income rule (Priority 130)
2. Verify no conflicts with new priority structure

**Expected Impact**:
- BAC: 14/19 → 15/19 (78.9%)
- JPM: 14/19 → 15/19 (78.9%)

---

### Version 2026-01-02.3: Enhanced Fields

**Changes**:
1. Add `comprehensiveIncome` field
2. Add `netIncomeAvailableToCommon` field
3. Update field count: 19 → 21

**Expected Impact**:
- Complete income statement + comprehensive income coverage
- Accurate EPS validation

---

## 6. Technical Report Scorecard

| Issue | Severity | Validated | Recommendation |
|-------|----------|-----------|----------------|
| **Revenue Priority Overlap** | 🚨 Critical | ✅ Confirmed | Fix immediately |
| **Bank EBIT Definition** | ⚠️ Medium | ✅ Confirmed | Design decision needed |
| **Bank Gross Income** | ⚠️ Medium | ✅ Confirmed | Implement enhancement |
| **D&A Location** | ⚠️ Medium | ✅ Confirmed | Future: cross-statement |
| **Circular Dependency** | ⚠️ Low | ⚠️ Mitigated | Add fallback |
| **Add OCI Field** | ℹ️ Enhancement | ✅ Valid | Next version |
| **Add Net Income to Common** | ℹ️ Enhancement | ✅ Valid | Next version |
| **SG&A Computation** | ℹ️ Enhancement | ✅ Valid | Test carefully |

---

## 7. Conclusion

**Technical Report Assessment**: ✅ **HIGHLY VALUABLE**

The report identified:
- 1 critical bug (revenue priority overlap)
- 3 medium-severity issues (bank EBIT, gross income, D&A)
- 4 valuable enhancements (OCI, net income to common, SG&A, circular dependency)

**Immediate Action Required**:
1. Fix revenue priority overlap (Critical)
2. Test all industry-specific extractions
3. Plan version 2026-01-02.1 deployment

**Long-Term Roadmap**:
1. Version 2026-01-02.1: Priority bug fix (CRITICAL)
2. Version 2026-01-02.2: Banking enhancements
3. Version 2026-01-02.3: New fields (OCI, net income to common)
4. Version 2026-01-03.0: Cross-statement extraction (D&A from cash flow)

---

**Report Evaluation**: ✅ **EXCELLENT TECHNICAL ANALYSIS**
**Status**: ⚠️ **CRITICAL BUG REQUIRES IMMEDIATE FIX**
**Recommendation**: Deploy priority fix before production use

---

**Response Date**: 2026-01-02
**Current Map Version**: 2026-01-01.3
**Next Version**: 2026-01-02.1 (Critical bug fix)

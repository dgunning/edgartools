# ML Mapping Audit Report
**Mapping File**: `map\balance-sheet.json`
**ML Data**: `C:\edgartools_git\training\output`
**Sector**: banking
**Fields Audited**: 31
**Total Issues**: 8

---
## Issues by Severity
- 🟠 **HIGH**: 3
- 🟡 **MEDIUM**: 5

## Issues by Type
- **Missing High Occurrence**: 5
- **Component Before Total**: 3

---
## Detailed Issues

### 1. 🟡 cash - Missing High Occurrence
**Rule**: Banks: Cash and cash equivalents (total first, components as fallback)
**Severity**: medium
**Description**: High-occurrence total concept CashCashEquivalentsAndFederalFundsSold (22.0%) not in selectAny
**Recommendation**: Consider adding us-gaap:CashCashEquivalentsAndFederalFundsSold to selectAny array

### 2. 🟡 cash - Missing High Occurrence
**Rule**: IFRS: Cash and cash equivalents
**Severity**: medium
**Description**: High-occurrence total concept CashAndCashEquivalentsAtCarryingValue (42.5%) not in selectAny
**Recommendation**: Consider adding us-gaap:CashAndCashEquivalentsAtCarryingValue to selectAny array

### 3. 🟡 cash - Missing High Occurrence
**Rule**: IFRS: Cash and cash equivalents
**Severity**: medium
**Description**: High-occurrence total concept CashCashEquivalentsAndFederalFundsSold (22.0%) not in selectAny
**Recommendation**: Consider adding us-gaap:CashCashEquivalentsAndFederalFundsSold to selectAny array

### 4. 🟡 cash - Missing High Occurrence
**Rule**: US GAAP: Cash and cash equivalents
**Severity**: medium
**Description**: High-occurrence total concept CashCashEquivalentsAndFederalFundsSold (22.0%) not in selectAny
**Recommendation**: Consider adding us-gaap:CashCashEquivalentsAndFederalFundsSold to selectAny array

### 5. 🟡 intangibleAssets - Missing High Occurrence
**Rule**: IFRS: Intangible assets other than goodwill
**Severity**: medium
**Description**: High-occurrence total concept FiniteLivedIntangibleAssetsNet (18.1%) not in selectAny
**Recommendation**: Consider adding us-gaap:FiniteLivedIntangibleAssetsNet to selectAny array

### 6. 🟠 intangibleAssets - Component Before Total
**Rule**: US GAAP: Intangible assets net (excluding goodwill)
**Severity**: high
**Description**: Component concept IntangibleAssetsNetExcludingGoodwill (24.4%) appears before total concept FiniteLivedIntangibleAssetsNet (18.1%)
**Recommendation**: Move us-gaap:FiniteLivedIntangibleAssetsNet before us-gaap:IntangibleAssetsNetExcludingGoodwill in selectAny array

### 7. 🟠 longTermDebt - Component Before Total
**Rule**: US GAAP: Long-term debt non-current
**Severity**: high
**Description**: Component concept LongTermDebtNoncurrent (2.4%) appears before total concept LongTermDebt (15.0%)
**Recommendation**: Move us-gaap:LongTermDebt before us-gaap:LongTermDebtNoncurrent in selectAny array

### 8. 🟠 longTermDebt - Component Before Total
**Rule**: US GAAP: Long-term debt non-current
**Severity**: high
**Description**: Component concept LongTermDebtNoncurrent (2.4%) appears before total concept LongTermDebtAndCapitalLeaseObligations (3.1%)
**Recommendation**: Move us-gaap:LongTermDebtAndCapitalLeaseObligations before us-gaap:LongTermDebtNoncurrent in selectAny array

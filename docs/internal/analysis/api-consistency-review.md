# API Consistency Review: EntityFacts vs Financials

**Date:** 2026-01-22
**Issue:** Inconsistent APIs for accessing financial data
**Impact:** User confusion, duplicate functionality with different interfaces

---

## Executive Summary

EdgarTools has **two parallel APIs** for accessing financial data:
1. **EntityFacts** - Uses SEC Company Facts JSON API
2. **Financials** - Parses XBRL directly from filings

These APIs have **overlapping functionality** but **inconsistent interfaces**, creating confusion for users.

---

## API Comparison Matrix

| Feature | EntityFacts | Financials | Consistent? |
|---------|-------------|------------|-------------|
| **Access Method** | `company.get_facts()` | `company.get_financials()` | ✅ Clear distinction |
| **Revenue Method** | `get_revenue(period, unit, annual)` | `get_revenue(period_offset)` | ❌ Different signatures |
| **Net Income Method** | `get_net_income(period, unit, annual)` | `get_net_income(period_offset)` | ❌ Different signatures |
| **Assets Method** | `get_total_assets(period, unit, annual)` | `get_total_assets(period_offset)` | ❌ Different signatures |
| **Income Statement** | `income_statement()` → `MultiPeriodStatement` | `income_statement()` → `Statement` | ❌ Different types |
| **Balance Sheet** | `balance_sheet()` → `MultiPeriodStatement` | `balance_sheet()` → `Statement` | ❌ Different types |
| **Cash Flow** | `cash_flow()` → `MultiPeriodStatement` | `cashflow_statement()` → `Statement` | ❌ **Different names!** |
| **Period Selection** | String format: `"2024-Q4"`, `"2024-FY"` | Integer offset: `0`, `1`, `2` | ❌ Incompatible |
| **Data Source** | Company Facts JSON (all filings) | XBRL (single filing) | ⚠️ Different scope |

---

## Detailed Inconsistencies

### 1. **Method Signature Mismatch** ⚠️ HIGH PRIORITY

```python
# EntityFacts - Semantic, clear parameters
facts.get_revenue(
    period="2024-Q4",  # ✅ Clear: specific quarter
    unit="USD",        # ✅ Clear: currency
    annual=True        # ✅ Clear: prefer annual
)

# Financials - Positional, unclear parameters
financials.get_revenue(
    period_offset=0    # ❌ Unclear: 0 means what? Current? Latest?
)
```

**User Confusion:**
- "What does `period_offset=1` mean? 1 quarter ago? 1 year ago?"
- "Can I get Q4 2023 data from Financials?"
- "Why do these methods have the same name but different parameters?"

---

### 2. **Method Naming Inconsistency** ⚠️ MEDIUM PRIORITY

```python
# EntityFacts
facts.cash_flow()  # ✅ Shorter, cleaner

# Financials
financials.cashflow_statement()  # ❌ Different name, inconsistent
```

**Impact:**
- Users must remember different method names for same concept
- Code doesn't port between APIs
- Documentation confusion

**Recommendation:** Pick ONE naming convention:
- Option A: `cash_flow()` everywhere (shorter)
- Option B: `cashflow_statement()` everywhere (more explicit)
- Option C: Alias both → `cash_flow = cashflow_statement`

---

### 3. **Different Return Types** ⚠️ HIGH PRIORITY

```python
# EntityFacts returns MultiPeriodStatement
facts_stmt = facts.income_statement()
for item in facts_stmt.items:  # Works
    print(item.label, item.values)

# Financials returns Statement (XBRL)
fin_stmt = financials.income_statement()
for item in fin_stmt.items:  # ❌ AttributeError! Must render first
    ...

# Financials requires rendering step
rendered = fin_stmt.render()
df = rendered.to_dataframe()  # Now works
```

**User Confusion:**
- "Why does `.income_statement()` return different types?"
- "Why do I need `.render()` for one but not the other?"
- "Can't I just iterate through the statement?"

---

### 4. **Period Selection Philosophy** ⚠️ HIGH PRIORITY

| Aspect | EntityFacts | Financials |
|--------|-------------|------------|
| **Approach** | Explicit semantic periods | Relative offset from filing |
| **Example** | `period="2024-Q3"` | `period_offset=1` |
| **Intuitive?** | ✅ Yes - "Give me Q3 2024" | ❌ No - "Give me... previous period?" |
| **Flexible?** | ✅ Can request any period | ❌ Limited to filing's periods |
| **Type-safe?** | ⚠️ String (no validation) | ✅ Integer |

**Real User Scenarios:**

```python
# Scenario: Get Q3 2024 revenue

# EntityFacts - Clear and explicit
revenue_q3 = facts.get_revenue(period="2024-Q3")  # ✅ Obvious

# Financials - Requires knowledge of filing structure
# User must know:
# 1. What filing they're looking at
# 2. What periods are in that filing
# 3. What order they're in
# 4. Count backwards from 0
revenue_q3 = financials.get_revenue(period_offset=2)  # ❌ Magic number
```

---

## Data Source Differences

### EntityFacts (Company Facts JSON)
- **Source:** Aggregated data from ALL filings
- **Coverage:** Complete historical data
- **Updates:** Every filing updates the dataset
- **Periods:** Can access any filed period
- **Pros:**
  - Complete history in one place
  - Easy to query specific periods
  - Consistent format across companies
- **Cons:**
  - May lag behind latest filing
  - Less detailed than raw XBRL

### Financials (XBRL from specific filing)
- **Source:** Single filing's XBRL data
- **Coverage:** Only periods in that filing
- **Updates:** Per-filing basis
- **Periods:** Limited to filing's comparative periods
- **Pros:**
  - Exact data from filing
  - Full XBRL detail available
  - Includes dimensions/breakdowns
- **Cons:**
  - Limited historical access
  - Must fetch multiple filings for history
  - Period offset is confusing

---

## User Confusion Patterns

### Pattern 1: "Which API should I use?"

```python
company = Company("AAPL")

# User sees both options:
facts = company.get_facts()
financials = company.get_financials()

# Both have get_revenue()! Which to use?
revenue1 = facts.get_revenue()       # ?
revenue2 = financials.get_revenue()  # ?
```

**Current Documentation Issues:**
- No clear guidance on when to use which
- Both methods appear in autocomplete
- No indication they return same data differently

### Pattern 2: "Why doesn't this work?"

```python
# User learns EntityFacts API
revenue = facts.get_revenue(period="2024-Q3")  # Works!

# Tries to use same pattern with Financials
revenue = financials.get_revenue(period="2024-Q3")  # ❌ TypeError!
# TypeError: get_revenue() got an unexpected keyword argument 'period'
```

### Pattern 3: "What period am I getting?"

```python
# EntityFacts - Explicit
revenue = facts.get_revenue(annual=True)  # ✅ "Annual revenue"

# Financials - Implicit
revenue = financials.get_revenue()  # ❌ "Revenue from... which period?"
```

---

## Recommendations

### 🔴 Critical (Breaking Changes Needed)

**1. Align get_* Method Signatures**

Adopt EntityFacts' semantic approach everywhere:

```python
# BEFORE (Financials)
financials.get_revenue(period_offset=0)

# AFTER (Proposed)
financials.get_revenue(period=None, annual=True)
# Where period is index into statement's periods: 0, 1, 2
# Or keep period_offset but add period as alias
```

**Rationale:** Semantic parameters are clearer than positional offsets.

**2. Standardize Cash Flow Method Name**

```python
# Choose ONE:
# Option A: Short form everywhere
facts.cash_flow()
financials.cash_flow()  # Rename from cashflow_statement

# Option B: Explicit form everywhere
facts.cashflow_statement()  # Rename from cash_flow
financials.cashflow_statement()

# Option C: Support both via alias
class Financials:
    def cashflow_statement(self): ...
    cash_flow = cashflow_statement  # Alias
```

**Recommendation:** Option C (aliasing) for backward compatibility.

### 🟡 High Priority (API Improvements)

**3. Add Period Selection Helper**

```python
# Make period selection intuitive for Financials
financials.get_revenue(period=0)  # Most recent
financials.get_revenue(period=-1)  # Previous (negative indexing)

# Or even better - support both:
financials.get_revenue(period=0)  # By index
financials.get_revenue(period="2024-12-31")  # By date string
```

**4. Unified Documentation Pattern**

Create a comparison table in docs:

```markdown
| Task | EntityFacts | Financials | Notes |
|------|-------------|------------|-------|
| Annual revenue | `facts.get_revenue()` | `financials.get_revenue()` | Both default to annual |
| Q3 revenue | `facts.get_revenue(period="2024-Q3")` | `financials.get_revenue(period=2)` | Different approaches |
| Full statement | `facts.income_statement()` | `financials.income_statement().render()` | Financials needs render |
```

**5. Add Explicit Guidance**

In `Company` class docstring:

```python
class Company:
    """
    Financial Data APIs:

    1. get_facts() - Use for:
       - Historical analysis (access all periods)
       - Comparing across time
       - Specific period queries (e.g., "2024-Q3")

    2. get_financials() - Use for:
       - Latest filing details
       - Full XBRL data with dimensions
       - Exact filing reproduction
    """
```

### 🟢 Nice to Have (Non-Breaking Improvements)

**6. Type Hints for Period Parameters**

```python
from typing import Literal, Union

PeriodSpec = Union[
    str,  # "2024-Q3", "2024-FY"
    int,  # 0, 1, 2 (offset)
]

def get_revenue(
    self,
    period: Optional[PeriodSpec] = None,
    annual: bool = True
) -> Optional[float]:
    ...
```

**7. Add Validation**

```python
# Validate period strings
if isinstance(period, str):
    if not re.match(r'\\d{4}-(Q[1-4]|FY)', period):
        raise ValueError(f"Invalid period format: {period}. Use '2024-Q3' or '2024-FY'")
```

---

## Migration Path

### Phase 1: Documentation (No Code Changes)
1. Add "API Comparison" page to docs
2. Add guidance to `Company` docstring
3. Add warnings about inconsistencies

### Phase 2: Deprecation Warnings (v5.12)
```python
def cashflow_statement(self):
    warnings.warn(
        "cashflow_statement() will be renamed to cash_flow() in v6.0 "
        "for consistency with EntityFacts API",
        DeprecationWarning
    )
```

### Phase 3: Harmonization (v6.0 - Breaking)
1. Align all method signatures
2. Rename `cashflow_statement` → `cash_flow`
3. Keep aliases with deprecation warnings

---

## Testing Requirements

If we proceed with changes:

1. **Signature compatibility tests** - Ensure both APIs accept same parameters
2. **Return value tests** - Verify both return same data (when applicable)
3. **Documentation examples** - Test all code examples in docs
4. **Migration guide** - Provide runnable scripts to update user code

---

## Open Questions

1. **Should Financials support semantic period strings?**
   - Pro: Consistent with EntityFacts
   - Con: Financials has limited periods per filing

2. **Should we merge the APIs eventually?**
   - Single unified API that handles both sources
   - More complex implementation
   - Cleaner user experience

3. **How do we handle the different return types?**
   - Can we make `Statement` and `MultiPeriodStatement` more similar?
   - Duck typing protocol?
   - Common base class?

---

## Conclusion

The current dual API structure creates **significant user confusion** through:
- ❌ Inconsistent method signatures
- ❌ Different naming conventions
- ❌ Different return types
- ❌ Different period selection approaches

**Recommendation:** Prioritize signature alignment and naming consistency. Even without breaking changes, we can improve significantly through:
- Better documentation
- Clearer guidance on which API to use
- Aliases for backward compatibility

**Impact if not addressed:**
- Continued user confusion
- Support burden
- Negative user experience
- Harder to maintain two parallel APIs

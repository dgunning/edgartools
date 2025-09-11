# PeriodType Quick Reference

**FEAT-003: PeriodType Enum for EdgarTools**  
Enhanced developer experience through IDE autocomplete and parameter validation for financial reporting periods.

## 📋 Available Period Types

| Enum Value | String Value | Description | Use Case |
|------------|-------------|-------------|----------|
| `PeriodType.ANNUAL` | `"annual"` | Annual reporting periods | Full fiscal year financial data |
| `PeriodType.QUARTERLY` | `"quarterly"` | Quarterly reporting periods | 3-month period financial data |
| `PeriodType.MONTHLY` | `"monthly"` | Monthly reporting periods | Monthly financial data (rare) |
| `PeriodType.TTM` | `"ttm"` | Trailing Twelve Months | Rolling 12-month performance |
| `PeriodType.YTD` | `"ytd"` | Year to Date | Current year performance |

### Convenience Aliases
| Alias | Same As | Notes |
|-------|---------|--------|
| `PeriodType.YEARLY` | `PeriodType.ANNUAL` | Alternative naming |
| `PeriodType.QUARTER` | `PeriodType.QUARTERLY` | Shorter form |

## 🚀 Basic Usage

### Import
```python
from edgar.enums import PeriodType, PeriodInput
```

### Function Parameters (New Style)
```python
from edgar import Company
from edgar.enums import PeriodType

# Enhanced with autocomplete
company = Company("AAPL")
facts = company.get_facts(period=PeriodType.ANNUAL)       # IDE autocomplete!
quarterly_data = company.get_facts(period=PeriodType.QUARTERLY)
ttm_data = company.get_facts(period=PeriodType.TTM)
```

### Backwards Compatibility (Existing Style)
```python
# Still works - no breaking changes
facts = company.get_facts(period="annual")
quarterly_data = company.get_facts(period="quarterly")
```

## 🛡️ Enhanced Validation

### Smart Error Messages
```python
from edgar.enums import validate_period_type

# Typo detection
try:
    validate_period_type("anual")  # misspelled
except ValueError as e:
    # Error: "Invalid period type 'anual'. Did you mean: annual?"
    
# Invalid input
try:
    validate_period_type("invalid")
except ValueError as e:
    # Error: "Invalid period type 'invalid'. Use PeriodType enum for autocomplete..."
```

## 🔧 Function Integration

### Type Hints
```python
from edgar.enums import PeriodInput

def analyze_financials(ticker: str, period: PeriodInput = PeriodType.ANNUAL) -> str:
    """Function with PeriodType parameter."""
    validated_period = validate_period_type(period)
    return f"Analyzing {ticker} {validated_period} financials"

# Usage
result = analyze_financials("AAPL", PeriodType.QUARTERLY)  # IDE autocomplete
result = analyze_financials("MSFT", "ttm")                 # String still works
```

### Migration from Boolean Annual
```python
# Old pattern
def old_style(annual: bool = True) -> str:
    period = "annual" if annual else "quarterly"
    return f"Getting {period} data"

# New pattern - more expressive
def new_style(period: PeriodInput = PeriodType.ANNUAL) -> str:
    period_str = validate_period_type(period)
    return f"Getting {period_str} data"

# Benefits:
# ✅ Support for TTM, YTD, monthly (not just annual/quarterly)
# ✅ IDE autocomplete 
# ✅ Validation prevents typos
# ✅ Self-documenting code
```

## 📚 Convenience Collections

```python
from edgar.enums import STANDARD_PERIODS, SPECIAL_PERIODS, ALL_PERIODS

# Most common periods
for period in STANDARD_PERIODS:
    print(f"Standard: {period}")  # ANNUAL, QUARTERLY

# Special analysis periods  
for period in SPECIAL_PERIODS:
    print(f"Special: {period}")   # TTM, YTD

# All available periods
for period in ALL_PERIODS:
    print(f"Available: {period}") # All 5 period types
```

## 🌍 Real-World Examples

### Financial Analysis
```python
def compare_performance(ticker: str, periods: list[PeriodInput]) -> dict:
    """Compare company performance across different periods."""
    results = {}
    for period in periods:
        period_str = validate_period_type(period)
        # Mock analysis
        results[period_str] = f"{ticker} performance for {period_str}"
    return results

# Usage with mixed types
analysis = compare_performance("AAPL", [
    PeriodType.ANNUAL,    # Enum
    "quarterly",          # String
    PeriodType.TTM        # Enum
])
```

### Batch Processing
```python
def process_companies(tickers: list[str], 
                     period: PeriodInput = PeriodType.QUARTERLY) -> str:
    """Process multiple companies for specified period."""
    period_str = validate_period_type(period)
    return f"Processing {len(tickers)} companies for {period_str} data"

# Usage
tech_stocks = ["AAPL", "MSFT", "GOOGL"]
result = process_companies(tech_stocks, PeriodType.TTM)
```

### Period Iteration
```python
def comprehensive_analysis(ticker: str) -> dict:
    """Analyze company across all standard periods."""
    results = {}
    
    for period in STANDARD_PERIODS:
        # Each period provides IDE autocomplete when used
        results[period.value] = f"Analysis for {period.value}"
        
    return results
```

## 💡 IDE Benefits

With PeriodType, your IDE will provide:

### Autocomplete
When you type `PeriodType.`, your IDE shows:
```
PeriodType.ANNUAL     # 'annual' - Full fiscal year
PeriodType.QUARTERLY  # 'quarterly' - 3-month periods  
PeriodType.MONTHLY    # 'monthly' - Monthly periods
PeriodType.TTM        # 'ttm' - Trailing twelve months
PeriodType.YTD        # 'ytd' - Year to date
```

### Documentation
Hover over enum values to see descriptions:
- **ANNUAL**: Annual reporting periods (full fiscal year)
- **QUARTERLY**: Quarterly reporting periods (3-month periods)
- **TTM**: Trailing Twelve Months for rolling performance analysis

### Type Safety
Your IDE will warn about:
- Invalid period types
- Wrong parameter types
- Potential typos before runtime

## 🔄 Migration Guide

### From Boolean Annual Parameter

**Before:**
```python
# Limited to annual/quarterly only
company.get_facts(annual=True)    # Annual data
company.get_facts(annual=False)   # Quarterly data
```

**After:**
```python
# Rich period support with autocomplete
company.get_facts(period=PeriodType.ANNUAL)     # Annual
company.get_facts(period=PeriodType.QUARTERLY)  # Quarterly
company.get_facts(period=PeriodType.TTM)        # Trailing twelve months
company.get_facts(period=PeriodType.YTD)        # Year to date

# String compatibility maintained
company.get_facts(period="annual")     # Still works
company.get_facts(period="quarterly")  # Still works
```

### From String Parameters

**Before:**
```python
# Typo-prone, no autocomplete
analyze_data("annual")     # Could typo as "anual"
analyze_data("quarterly")  # Could typo as "quartly"
```

**After:**
```python
# Autocomplete prevents typos
analyze_data(PeriodType.ANNUAL)     # IDE autocomplete
analyze_data(PeriodType.QUARTERLY)  # IDE autocomplete

# Strings still work with validation
analyze_data("annual")     # Validated, helpful errors if typo
```

## ⚖️ Consistency with FormType

PeriodType follows the same design pattern as FormType:

| Feature | FormType | PeriodType |
|---------|----------|------------|
| **Enum Type** | `StrEnum` | `StrEnum` |
| **Validation** | `validate_form_type()` | `validate_period_type()` |
| **Type Hints** | `FormInput` | `PeriodInput` |
| **Collections** | `PERIODIC_FORMS`, etc. | `STANDARD_PERIODS`, etc. |
| **Error Handling** | Smart suggestions | Smart suggestions |
| **Backwards Compat** | ✅ Union types | ✅ Union types |

## 🎯 Best Practices

### 1. Use Enums for New Code
```python
# Recommended: Enhanced developer experience
def analyze_trends(period: PeriodInput = PeriodType.ANNUAL):
    ...
```

### 2. Maintain String Compatibility  
```python
# Support both for flexibility
def flexible_function(period: PeriodInput):
    validated = validate_period_type(period)  # Handles both
    ...
```

### 3. Leverage Collections
```python
# Use predefined collections
for period in STANDARD_PERIODS:
    process_period(period)
```

### 4. Provide Good Defaults
```python
# Use meaningful defaults
def get_financials(period: PeriodInput = PeriodType.ANNUAL):
    """Default to annual for most financial analysis."""
    ...
```

## 🚦 Error Handling

### Common Errors and Solutions

```python
from edgar.enums import validate_period_type, PeriodType

# Typo in string
try:
    validate_period_type("anual")
except ValueError as e:
    print(e)  # "Did you mean: annual?"

# Wrong type
try:
    validate_period_type(123)
except TypeError as e:
    print(e)  # "Period must be PeriodType or str"

# Completely invalid
try:
    validate_period_type("invalid")
except ValueError as e:
    print(e)  # "Use PeriodType enum for autocomplete..."
```

---

## 📈 Impact Summary

**FEAT-003 delivers on EdgarTools principles:**

- ✅ **Simple yet powerful**: Easy enum usage with rich functionality
- ✅ **Beginner-friendly**: IDE autocomplete helps discovery
- ✅ **Joyful UX**: Prevents typos, provides helpful errors
- ✅ **Accurate financials**: Validation ensures correct period specification

**Key improvements:**
- 🎯 IDE autocomplete for period types
- 🛡️ Enhanced validation with smart error messages  
- 🔧 Seamless integration with existing API
- 🔄 Clear migration path from boolean parameters
- ⚖️ Consistent design with FormType enum
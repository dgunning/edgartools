# Issue #440: Currency Display Fix for Non-US Companies

## Problem Summary

Deutsche Bank (DB) and other non-US companies were displaying amounts in USD ($) instead of their actual reporting currency (EUR €) in financial statements from XBRL filings. This was causing confusion as users expected to see the correct currency symbols.

**Example Issue:**
- **Expected**: 29,493 million € (EURO)
- **Actual**: 29,493 million $ (Dollar)

## Root Cause Analysis

The issue was in the XBRL currency handling pipeline:

1. **Currency Information Available**: XBRL filings contain proper unit definitions with ISO currency codes:
   ```
   'u-3': {'type': 'simple', 'measure': 'iso4217:EUR'}
   'u-4': {'type': 'simple', 'measure': 'iso4217:USD'}
   ```

2. **Currency Not Captured**: The `_generate_line_items()` method in `/edgar/xbrl/xbrl.py` was capturing fact values and decimals but NOT capturing currency information from fact `unit_ref` attributes.

3. **Hardcoded USD Symbol**: The `format_value()` function in `/edgar/xbrl/core.py` was hardcoded to use `$` for all monetary values regardless of actual currency.

## Solution Implementation

### 1. Added Currency Symbol Mapping Function

Added `get_currency_symbol()` function in `/edgar/xbrl/core.py`:

```python
def get_currency_symbol(unit_measure: Optional[str]) -> str:
    """Get the appropriate currency symbol from a unit measure string."""
    currency_symbols = {
        'iso4217:USD': '$',
        'iso4217:EUR': '€',
        'iso4217:GBP': '£',
        'iso4217:JPY': '¥',
        'iso4217:CAD': 'C$',
        # ... (30+ currency mappings)
    }
    return currency_symbols.get(unit_measure, '$')  # Default to USD
```

### 2. Enhanced format_value Function

Updated `format_value()` function to accept and use currency symbols:

```python
def format_value(value: Union[int, float, str], is_monetary: bool, scale: int,
                 decimals: Optional[int] = None, currency_symbol: Optional[str] = None) -> str:
    # ... formatting logic ...
    if is_monetary:
        symbol = currency_symbol if currency_symbol is not None else '$'
        if value < 0:
            return f"{symbol}({abs(scaled_value):{decimal_format}})"
        else:
            return f"{symbol}{scaled_value:{decimal_format}}"
```

### 3. Currency Capture in Statement Generation

Modified `_generate_line_items()` in `/edgar/xbrl/xbrl.py` to capture currency information:

```python
# Added currency tracking alongside values and decimals
currencies = {}  # Store currency info for each period

# When processing facts, capture currency info
if hasattr(fact, 'unit_ref') and fact.unit_ref and fact.unit_ref in self.units:
    unit_info = self.units[fact.unit_ref]
    if 'measure' in unit_info:
        currencies[period_key] = unit_info['measure']

# Include currencies in line item data
line_item = {
    'concept': element_id,
    'name': node.element_name,
    'values': values,
    'decimals': decimals,
    'currencies': currencies,  # NEW: Currency info
    # ... other fields ...
}
```

### 4. Currency Usage in Rendering

Updated `_format_value_for_display_as_string()` in `/edgar/xbrl/rendering.py` to use currency info:

```python
# Get currency symbol for this period
currency_symbol = None
if is_monetary and period_key:
    currencies_dict = item.get('currencies', {})
    if currencies_dict and period_key in currencies_dict:
        from edgar.xbrl.core import get_currency_symbol
        currency_measure = currencies_dict[period_key]
        currency_symbol = get_currency_symbol(currency_measure)

return format_value(value, is_monetary, dominant_scale, fact_decimals, currency_symbol)
```

## Testing and Verification

### Deutsche Bank Test Results

**Before Fix:**
```
Financial liabilities designated at fair value through profit or loss  $5,425  $29,493  $(6,046)
```

**After Fix:**
```
Financial liabilities designated at fair value through profit or loss  €5,425  €29,493  €(6,046)
```

### Regression Testing

- ✅ Deutsche Bank (EUR): Shows € symbols correctly
- ✅ Apple (USD): Still shows $ symbols correctly
- ✅ Core functionality: No breaking changes
- ✅ Unit tests: All currency mapping tests pass

## Files Modified

1. `/edgar/xbrl/core.py` - Added currency symbol mapping and enhanced format_value
2. `/edgar/xbrl/xbrl.py` - Added currency capture in statement generation
3. `/edgar/xbrl/rendering.py` - Added currency usage in value formatting

## Regression Test

Created comprehensive regression test at:
`/tests/issues/regression/test_issue_440_currency_display.py`

This test ensures:
- Non-US companies show correct currency symbols
- US companies still show USD symbols
- Currency mapping functions work correctly
- Format_value function handles all currency types

## Benefits

1. **Accurate Financial Display**: Non-US companies now show correct currency symbols
2. **Backward Compatibility**: US companies continue to work as before
3. **Comprehensive Support**: 30+ currencies supported with proper symbols
4. **Maintainable Solution**: Clean separation of concerns with dedicated currency mapping function

## Edge Cases Handled

- Missing currency information defaults to USD ($)
- Unknown currencies default to USD ($)
- Empty or null unit references default to USD ($)
- Mixed currency filings handle each period independently

This fix ensures EdgarTools accurately represents the financial data as intended by the filing companies, improving data integrity and user experience for international filings.
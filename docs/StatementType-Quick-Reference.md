# StatementType Quick Reference

**FEAT-005: Statement Type Classifications for EdgarTools**  
Enhanced developer experience through IDE autocomplete and parameter validation for financial statement types.

## 📋 Available Statement Types

### Primary Financial Statements (The Big Four)
| Enum Value | String Value | Description | Use Case |
|------------|-------------|-------------|----------|
| `StatementType.INCOME_STATEMENT` | `"income_statement"` | Profit & Loss Statement | Revenue, expenses, net income analysis |
| `StatementType.BALANCE_SHEET` | `"balance_sheet"` | Statement of Financial Position | Assets, liabilities, equity analysis |
| `StatementType.CASH_FLOW` | `"cash_flow_statement"` | Statement of Cash Flows | Cash inflows, outflows, liquidity analysis |
| `StatementType.CHANGES_IN_EQUITY` | `"changes_in_equity"` | Statement of Changes in Equity | Equity movements, dividends, retained earnings |

### Comprehensive Statements
| Enum Value | String Value | Description | Use Case |
|------------|-------------|-------------|----------|
| `StatementType.COMPREHENSIVE_INCOME` | `"comprehensive_income"` | Statement of Comprehensive Income | Total comprehensive income including OCI |

### Analytical Statements  
| Enum Value | String Value | Description | Use Case |
|------------|-------------|-------------|----------|
| `StatementType.SEGMENTS` | `"segment_reporting"` | Segment Information | Business segment performance |
| `StatementType.SUBSIDIARIES` | `"subsidiaries"` | Subsidiary Information | Subsidiary company details |
| `StatementType.FOOTNOTES` | `"footnotes"` | Notes to Financial Statements | Detailed disclosures and notes |
| `StatementType.ACCOUNTING_POLICIES` | `"accounting_policies"` | Significant Accounting Policies | Accounting methods and principles |

### Specialized Statements
| Enum Value | String Value | Description | Use Case |
|------------|-------------|-------------|----------|
| `StatementType.REGULATORY_CAPITAL` | `"regulatory_capital"` | Regulatory Capital | Bank capital adequacy ratios |
| `StatementType.INSURANCE_RESERVES` | `"insurance_reserves"` | Insurance Reserves | Insurance loss reserves |

### Convenience Aliases
| Alias | Same As | Notes |
|-------|---------|--------|
| `StatementType.PROFIT_LOSS` | `StatementType.INCOME_STATEMENT` | Common P&L terminology |
| `StatementType.PL_STATEMENT` | `StatementType.INCOME_STATEMENT` | Abbreviated P&L |
| `StatementType.FINANCIAL_POSITION` | `StatementType.BALANCE_SHEET` | IFRS terminology |
| `StatementType.STATEMENT_OF_POSITION` | `StatementType.BALANCE_SHEET` | Alternative naming |
| `StatementType.CASH_FLOWS` | `StatementType.CASH_FLOW` | Plural form |
| `StatementType.EQUITY_CHANGES` | `StatementType.CHANGES_IN_EQUITY` | Shorter form |

## 🚀 Basic Usage

### Import
```python
from edgar.enums import StatementType, StatementInput, validate_statement_type
```

### Unified Statement Access (New Style)
```python
from edgar import Company
from edgar.enums import StatementType

# Enhanced with autocomplete
company = Company("AAPL")
income = company.get_statement(StatementType.INCOME_STATEMENT)      # IDE autocomplete!
balance = company.get_statement(StatementType.BALANCE_SHEET)
cash_flow = company.get_statement(StatementType.CASH_FLOW)
```

### Backwards Compatibility (Existing Style)
```python
# Still works - no breaking changes
income = company.get_statement("income_statement")
balance = company.get_statement("balance_sheet")

# Legacy methods also still work
income = company.get_income_statement()
balance = company.get_balance_sheet()
```

## 🛡️ Enhanced Validation

### Smart Error Messages
```python
from edgar.enums import validate_statement_type

# Typo detection
try:
    validate_statement_type("income")  # partial match
except ValidationError as e:
    # Error: "Invalid statement type 'income'. Did you mean: income_statement?"
    
try:
    validate_statement_type("balanc")  # misspelling
except ValidationError as e:
    # Error: "Invalid statement type 'balanc'. Did you mean: balance_sheet?"
    
# Context-aware help
try:
    validate_statement_type("unknown")
except ValidationError as e:
    # Error: "Invalid statement type 'unknown'. Primary statements: 
    # 'income_statement' (P&L), 'balance_sheet' (financial position), ..."
```

## 🔧 Function Integration

### Type Hints
```python
from edgar.enums import StatementInput

def analyze_statement(company: str, statement: StatementInput) -> dict:
    """Function with StatementType parameter."""
    validated_statement = validate_statement_type(statement)
    return {"company": company, "statement": validated_statement, "analysis": "..."}

# Usage
result = analyze_statement("AAPL", StatementType.INCOME_STATEMENT)  # IDE autocomplete
result = analyze_statement("MSFT", "balance_sheet")                 # String still works
```

### Unified Statement API
```python
def get_statement(statement_type: StatementInput, periods: int = 4) -> Statement:
    """Unified statement access with enhanced validation."""
    validated_type = validate_statement_type(statement_type)
    # Implementation...
    return statement

# Benefits:
# ✅ Single method instead of get_income_statement(), get_balance_sheet(), etc.
# ✅ IDE autocomplete for all statement types
# ✅ Consistent parameter validation
# ✅ Extensible to new statement types
```

## 📚 Convenience Collections

```python
from edgar.enums import (
    PRIMARY_STATEMENTS, 
    COMPREHENSIVE_STATEMENTS,
    ANALYTICAL_STATEMENTS, 
    SPECIALIZED_STATEMENTS,
    ALL_STATEMENTS
)

# Analyze primary financial statements
for statement in PRIMARY_STATEMENTS:
    result = company.get_statement(statement)
    print(f"Analyzed {statement.name}")

# Check comprehensive statement availability
available_statements = []
for statement in COMPREHENSIVE_STATEMENTS:
    try:
        result = company.get_statement(statement)
        available_statements.append(statement)
    except StatementNotAvailable:
        pass

# Full financial analysis
all_results = {}
for statement in ALL_STATEMENTS:
    try:
        all_results[statement.value] = company.get_statement(statement)
    except Exception as e:
        all_results[statement.value] = f"Not available: {e}"
```

## 🌍 Real-World Examples

### Financial Analysis Workflow
```python
def comprehensive_financial_analysis(ticker: str) -> dict:
    """Analyze company across all primary statements."""
    company = Company(ticker)
    results = {}
    
    for statement_type in PRIMARY_STATEMENTS:
        try:
            statement = company.get_statement(statement_type)
            results[statement_type.value] = analyze_statement_data(statement)
        except Exception as e:
            results[statement_type.value] = f"Analysis failed: {e}"
    
    return results

# Usage with enhanced error handling
try:
    analysis = comprehensive_financial_analysis("AAPL")
    print(f"Successfully analyzed {len(analysis)} statement types")
except ValidationError as e:
    print(f"Invalid input: {e}")
```

### Statement Categorization
```python
def categorize_available_statements(company: Company) -> dict:
    """Categorize available statements by type."""
    categories = {
        "primary": [],
        "analytical": [],
        "specialized": []
    }
    
    # Check primary statements
    for statement in PRIMARY_STATEMENTS:
        if is_statement_available(company, statement):
            categories["primary"].append(statement.value)
    
    # Check analytical statements
    for statement in ANALYTICAL_STATEMENTS:
        if is_statement_available(company, statement):
            categories["analytical"].append(statement.value)
    
    return categories
```

### Educational Usage
```python
def explain_statement_types() -> None:
    """Educational function explaining financial statements."""
    explanations = {
        StatementType.INCOME_STATEMENT: "Shows company profitability - revenues minus expenses",
        StatementType.BALANCE_SHEET: "Shows financial position - assets, liabilities, equity",
        StatementType.CASH_FLOW: "Shows cash movements - operating, investing, financing",
        StatementType.CHANGES_IN_EQUITY: "Shows equity changes - dividends, retained earnings"
    }
    
    print("Financial Statement Types:")
    for statement, explanation in explanations.items():
        print(f"  {statement.name}: {explanation}")
```

## 💡 IDE Benefits

With StatementType, your IDE will provide:

### Autocomplete
When you type `StatementType.`, your IDE shows:
```
StatementType.INCOME_STATEMENT     # 'income_statement' - P&L Statement
StatementType.BALANCE_SHEET        # 'balance_sheet' - Financial Position  
StatementType.CASH_FLOW            # 'cash_flow_statement' - Cash Flows
StatementType.CHANGES_IN_EQUITY    # 'changes_in_equity' - Equity Changes
StatementType.COMPREHENSIVE_INCOME # 'comprehensive_income' - Total Income
...
```

### Documentation
Hover over enum values to see descriptions:
- **INCOME_STATEMENT**: Profit & Loss Statement showing revenues and expenses
- **BALANCE_SHEET**: Statement of Financial Position showing assets and liabilities
- **CASH_FLOW**: Statement of Cash Flows showing cash movements

### Type Safety
Your IDE will warn about:
- Invalid statement types
- Wrong parameter types  
- Potential typos before runtime

## 🔄 Migration Guide

### From Multiple Methods to Unified API

**Before:**
```python
# Multiple methods, hard to discover
income = company.get_income_statement()
balance = company.get_balance_sheet()
cash_flow = company.get_cash_flow_statement()
# equity = company.get_changes_in_equity()  # Does this method exist?
```

**After:**
```python
# Unified API with autocomplete
income = company.get_statement(StatementType.INCOME_STATEMENT)
balance = company.get_statement(StatementType.BALANCE_SHEET)
cash_flow = company.get_statement(StatementType.CASH_FLOW)
equity = company.get_statement(StatementType.CHANGES_IN_EQUITY)  # Discoverable!

# String compatibility maintained
income = company.get_statement("income_statement")  # Still works
```

### From String Parameters

**Before:**
```python
# Typo-prone, no autocomplete
get_statement_data("income")        # Could typo as "inccome" 
get_statement_data("balance")       # Could typo as "balanc"
```

**After:**
```python
# Autocomplete prevents typos
get_statement_data(StatementType.INCOME_STATEMENT)    # IDE autocomplete
get_statement_data(StatementType.BALANCE_SHEET)       # IDE autocomplete

# Strings still work with validation
get_statement_data("income_statement")    # Validated, helpful errors if typo
```

## ⚖️ Consistency with Other Types

StatementType follows the same design pattern as FormType and PeriodType:

| Feature | FormType | PeriodType | StatementType |
|---------|----------|------------|---------------|
| **Enum Type** | `StrEnum` | `StrEnum` | `StrEnum` |
| **Validation** | `validate_form_type()` | `validate_period_type()` | `validate_statement_type()` |
| **Type Hints** | `FormInput` | `PeriodInput` | `StatementInput` |
| **Collections** | `PRIMARY_FORMS`, etc. | `STANDARD_PERIODS`, etc. | `PRIMARY_STATEMENTS`, etc. |
| **Error Handling** | Smart suggestions | Smart suggestions | Smart suggestions |
| **Backwards Compat** | ✅ Union types | ✅ Union types | ✅ Union types |

## 🎯 Best Practices

### 1. Use Enums for New Code
```python
# Recommended: Enhanced developer experience
def analyze_financials(statement: StatementInput = StatementType.INCOME_STATEMENT):
    ...
```

### 2. Maintain String Compatibility  
```python
# Support both for flexibility
def flexible_statement_function(statement: StatementInput):
    validated = validate_statement_type(statement)  # Handles both
    ...
```

### 3. Leverage Collections
```python
# Use predefined collections
for statement in PRIMARY_STATEMENTS:
    process_statement(statement)
```

### 4. Provide Educational Context
```python
# Help beginners understand financial statements
def get_statement_with_help(statement_type: StatementInput) -> Tuple[Statement, str]:
    """Get statement with educational context."""
    validated = validate_statement_type(statement_type)
    
    context = {
        "income_statement": "This shows the company's profitability over time",
        "balance_sheet": "This shows what the company owns and owes at a point in time"
    }.get(validated, "Financial statement data")
    
    return get_statement(statement_type), context
```

## 🚦 Error Handling

### Common Errors and Solutions

```python
from edgar.enums import validate_statement_type, StatementType

# Typo in string
try:
    validate_statement_type("income")
except ValidationError as e:
    print(e)  # "Did you mean: income_statement?"

# Wrong type
try:
    validate_statement_type(123)
except TypeError as e:
    print(e)  # "Statement must be StatementType or str"

# Completely invalid
try:
    validate_statement_type("invalid_statement")
except ValidationError as e:
    print(e)  # "Use StatementType enum for autocomplete..."
```

---

## 📈 Impact Summary

**FEAT-005 delivers on EdgarTools principles:**

- ✅ **Beginner-friendly**: Makes financial statement exploration discoverable
- ✅ **Simple yet powerful**: Unified API with comprehensive statement coverage
- ✅ **Joyful UX**: Reduces confusion about available statement types

**Key improvements:**
- 📊 IDE autocomplete for financial statement types
- 🛡️ Enhanced validation with financial context
- 🔧 Unified statement access API
- 📚 Educational categorization of statement types  
- 🔄 Full backwards compatibility maintained
- ⚖️ Consistent design with FormType and PeriodType

**Phase 3 (Expansion) of Discussion 423 type hinting roadmap complete!**
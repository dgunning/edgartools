# StatementType Quick Reference

**FEAT-005: Statement Type Classifications for EdgarTools**
Enhanced developer experience through IDE autocomplete and parameter validation for financial statement types.

## Available Statement Types

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

## Basic Usage

### Import
```python
from edgar.enums import StatementType, StatementInput, validate_statement_type
```

## Two Ways to Access Financial Statements

EdgarTools provides **two different APIs** for accessing financial statements, each with different use cases:

### 1. Company Facts API (Multi-Period Historical Data)

Use the **Company** class for historical financial data across multiple periods. This uses the SEC's Company Facts API.

```python
from edgar import Company

company = Company("AAPL")

# Direct convenience methods (recommended for beginners)
income = company.income_statement(periods=4, annual=True)
balance = company.balance_sheet(periods=4, annual=True)
cash = company.cashflow_statement(periods=4, annual=True)

# These return MultiPeriodStatement objects with rich display
print(income)  # Beautiful table output
```

**Best for:**
- Multi-period trend analysis
- Quick access to historical financials
- Beginners who want simple API

**Limitations:**
- Only supports primary statements (income, balance sheet, cash flow)
- Does not support segment or analytical statements

### 2. XBRL API (Full Statement Access)

Use the **XBRL** class for complete access to all statement types from a specific filing.

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Recommended: Use the statements property for common statements
income = xbrl.statements.income_statement()
balance = xbrl.statements.balance_sheet()
cash_flow = xbrl.statements.cashflow_statement()

# For analytical statements, use get_statement() with PascalCase string names
segments = xbrl.get_statement("SegmentDisclosure")
comprehensive = xbrl.get_statement("ComprehensiveIncome")
```

> **Note:** `get_statement()` accepts PascalCase type names (e.g., `"IncomeStatement"`, `"BalanceSheet"`,
> `"CashFlowStatement"`), role URIs, or statement short names — **not** `StatementType` enum values.

**Best for:**
- Accessing specific filing periods
- Analytical statements (segments, footnotes, etc.)
- Full XBRL dimensional data
- Advanced analysis

## Accessing Segment Statements

Segment data is only available through the XBRL API:

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Get segment statement data using PascalCase string name
segment_data = xbrl.get_statement("SegmentDisclosure")

# Segment dimensional data also appears in income statements
income = xbrl.statements.income_statement()
# Shows segment breakdowns by product, geography, etc.
print(income)
```

## Enhanced Validation

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

## Function Integration

### Type Hints
```python
from edgar.enums import StatementInput

def analyze_statement(filing, statement: StatementInput) -> dict:
    """Function with StatementType parameter."""
    xbrl = filing.xbrl()
    validated_statement = validate_statement_type(statement)
    # Note: get_statement() expects PascalCase names like "IncomeStatement"
    statement_data = xbrl.get_statement(validated_statement)
    return {"statement": validated_statement, "data": statement_data}

# Usage with get_statement() - pass PascalCase strings
result = analyze_statement(filing, "IncomeStatement")
result = analyze_statement(filing, "BalanceSheet")
```

## Convenience Collections

```python
from edgar.enums import (
    PRIMARY_STATEMENTS,
    COMPREHENSIVE_STATEMENTS,
    ANALYTICAL_STATEMENTS,
    SPECIALIZED_STATEMENTS,
    ALL_STATEMENTS
)

# Use the statements property for primary financial statements
income = xbrl.statements.income_statement()
balance = xbrl.statements.balance_sheet()
cash_flow = xbrl.statements.cashflow_statement()

# For analytical statements, use get_statement() with PascalCase names
segments = xbrl.get_statement("SegmentDisclosure")
comprehensive = xbrl.get_statement("ComprehensiveIncome")
```

## Real-World Examples

### Financial Analysis Workflow
```python
from edgar import Company

def comprehensive_financial_analysis(ticker: str) -> dict:
    """Analyze company across all primary statements from latest 10-K."""
    company = Company(ticker)
    filing = company.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()

    return {
        "income": xbrl.statements.income_statement(),
        "balance": xbrl.statements.balance_sheet(),
        "cash_flow": xbrl.statements.cashflow_statement(),
        "equity": xbrl.statements.statement_of_equity(),
    }

# Usage
analysis = comprehensive_financial_analysis("AAPL")
```

### Multi-Period Historical Analysis
```python
from edgar import Company

def trend_analysis(ticker: str, periods: int = 5) -> dict:
    """Analyze company trends using Company Facts API."""
    company = Company(ticker)

    return {
        "income": company.income_statement(periods=periods, annual=True),
        "balance": company.balance_sheet(periods=periods, annual=True),
        "cash_flow": company.cashflow_statement(periods=periods, annual=True)
    }

# Usage - returns MultiPeriodStatement objects
trends = trend_analysis("AAPL", periods=5)
print(trends["income"])  # Shows 5 years of income statement data
```

### Statement Categorization
```python
def categorize_available_statements(xbrl) -> dict:
    """Categorize available statements by type."""
    categories = xbrl.statements.get_statements_by_category()
    return categories
```

## IDE Benefits

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

## API Comparison

| Feature | Company API | XBRL API |
|---------|-------------|----------|
| **Methods** | `income_statement()`, `balance_sheet()`, `cash_flow()` | `xbrl.statements.income_statement()` or `xbrl.get_statement("IncomeStatement")` |
| **Source** | Company Facts API | Filing XBRL data |
| **Multi-Period** | Yes (built-in) | No (single filing) |
| **Segments** | No | Yes |
| **Footnotes** | No | Yes |
| **StatementType Enum** | Not used | Not used (use PascalCase strings or `statements` property) |
| **Best For** | Historical trends | Full statement access |

## Migration Guide

### Choosing the Right API

**Use Company API when:**
```python
# You need multi-period historical data
company = Company("AAPL")
income = company.income_statement(periods=5, annual=True)  # 5 years of data
```

**Use XBRL API when:**
```python
# You need specific filing data or analytical statements
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()
segments = xbrl.get_statement("SegmentDisclosure")  # Only available here
```

## Consistency with Other Types

StatementType follows the same design pattern as FormType and PeriodType:

| Feature | FormType | PeriodType | StatementType |
|---------|----------|------------|---------------|
| **Enum Type** | `StrEnum` | `StrEnum` | `StrEnum` |
| **Validation** | `validate_form_type()` | `validate_period_type()` | `validate_statement_type()` |
| **Type Hints** | `FormInput` | `PeriodInput` | `StatementInput` |
| **Collections** | `PRIMARY_FORMS`, etc. | `STANDARD_PERIODS`, etc. | `PRIMARY_STATEMENTS`, etc. |
| **Error Handling** | Smart suggestions | Smart suggestions | Smart suggestions |
| **Backwards Compat** | Union types | Union types | Union types |

## Best Practices

### 1. Use Appropriate API for Your Use Case
```python
# Historical analysis - use Company API
company = Company("AAPL")
income = company.income_statement(periods=4)

# Specific filing analysis - use XBRL statements property (recommended)
xbrl = company.get_filings(form="10-K").latest().xbrl()
income = xbrl.statements.income_statement()
balance = xbrl.statements.balance_sheet()
cash_flow = xbrl.statements.cashflow_statement()
```

### 2. Access Analytical Statements
```python
# For statements beyond the Big Three, use get_statement() with PascalCase names
xbrl = filing.xbrl()
segments = xbrl.get_statement("SegmentDisclosure")
comprehensive = xbrl.get_statement("ComprehensiveIncome")
equity = xbrl.get_statement("StatementOfEquity")
```

### 3. Enumerate Available Statements
```python
# See what statements are available in a filing, organized by category
xbrl = filing.xbrl()
categories = xbrl.statements.get_statements_by_category()
for category, stmts in categories.items():
    for stmt in stmts:
        print(f"{category}: {stmt['type']} - {stmt.get('title', '')}")
```

## Error Handling

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

## Impact Summary

**FEAT-005 delivers on EdgarTools principles:**

- **Beginner-friendly**: Makes financial statement exploration discoverable
- **Simple yet powerful**: Two APIs for different use cases
- **Joyful UX**: IDE autocomplete and helpful error messages

**Key improvements:**
- IDE autocomplete for financial statement types
- Enhanced validation with financial context
- Clear separation between Company and XBRL APIs
- Educational categorization of statement types
- Full backwards compatibility maintained
- Consistent design with FormType and PeriodType

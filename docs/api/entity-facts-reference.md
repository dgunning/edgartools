# EntityFacts API Reference

Complete API documentation for the enhanced EntityFacts system, including all classes, methods, and data models.

## Overview

The EntityFacts API provides structured access to SEC company financial data with AI-ready features, powerful querying capabilities, and professional formatting. The system consists of several key components:

- **EntityFacts** - Main class for accessing company facts
- **FactQuery** - Fluent query builder for advanced filtering
- **FinancialStatement** - Formatted display wrapper for financial data
- **FinancialFact** - Individual fact data model with rich metadata

## EntityFacts Class

The main entry point for accessing company financial facts.

### Constructor

```python
EntityFacts(cik: int, name: str, facts: List[FinancialFact])
```

**Parameters:**
- `cik` (int): Company CIK number
- `name` (str): Company name  
- `facts` (List[FinancialFact]): List of financial facts

### Properties

#### Core Properties

#### `cik: int`
The company's CIK (Central Index Key) number.

```python
facts = company.facts
print(facts.cik)  # 320193
```

#### `name: str`
The company's official name.

```python
facts = company.facts
print(facts.name)  # "Apple Inc."
```

#### DEI Properties

#### `shares_outstanding: Optional[float]`
Number of common shares outstanding.

```python
shares = facts.shares_outstanding
if shares:
    print(f"Shares Outstanding: {shares:,.0f}")
```

#### `public_float: Optional[float]`
Public float value in dollars.

```python
float_val = facts.public_float
if float_val:
    print(f"Public Float: ${float_val:,.0f}")
```

#### `shares_outstanding_fact: Optional[FinancialFact]`
Full fact object for shares outstanding with metadata.

```python
fact = facts.shares_outstanding_fact
if fact:
    print(f"Shares: {fact.get_formatted_value()} as of {fact.period_end}")
```

#### `public_float_fact: Optional[FinancialFact]`
Full fact object for public float with metadata.

```python
fact = facts.public_float_fact
if fact:
    print(f"Float: {fact.get_formatted_value()} as of {fact.period_end}")
```

### Core Methods

#### Query Interface

#### `query() -> FactQuery`
Start building a facts query using the fluent interface.

```python
query = facts.query()
results = query.by_concept('Revenue').latest(4)
```

**Returns:** FactQuery builder instance

#### `get_fact(concept: str, period: Optional[str] = None) -> Optional[FinancialFact]`
Get a single fact by concept name.

```python
revenue_fact = facts.get_fact('Revenue')
q1_revenue = facts.get_fact('Revenue', '2024-Q1')
```

**Parameters:**
- `concept` (str): Concept name or label (case-insensitive)
- `period` (str, optional): Period in format "YYYY-QN" or "YYYY-FY"

**Returns:** Most recent matching fact or None


```python
time_series(concept: str, periods: int = 20) -> pd.DataFrame
```

Get time series data for a concept.

```python
revenue_ts = facts.time_series('Revenue', periods=8)
```

**Parameters:**
- `concept` (str): Concept name or label
- `periods` (int): Number of periods to retrieve (default: 20)

**Returns:** DataFrame with time series data

### Financial Statement Methods

```python
income_statement(periods: int = 4, 
                 period_length: Optional[int] = None, 
                 as_dataframe: bool = False, 
                 annual: bool = True)
```

Get income statement facts formatted as a financial statement.

```python
# Default: 4 annual periods, formatted display
stmt = facts.income_statement()

# 8 quarterly periods as DataFrame
df = facts.income_statement(periods=8, annual=False, as_dataframe=True)
```

**Parameters:**
- `periods` (int): Number of periods to retrieve (default: 4)
- `period_length` (int, optional): Filter by period length in months (3=quarterly, 12=annual)
- `as_dataframe` (bool): If True, return DataFrame; if False, return FinancialStatement (default: False)
- `annual` (bool): If True, prefer annual periods; if False, prefer quarterly (default: True)

**Returns:** FinancialStatement or DataFrame

#### `balance_sheet(periods: int = 4, as_of: Optional[date] = None, as_dataframe: bool = False, annual: bool = True)`

Get balance sheet facts for periods or point-in-time.

```python
# Multi-period balance sheet
stmt = facts.balance_sheet(periods=4)

# Point-in-time snapshot
snapshot = facts.balance_sheet(as_of=date(2024, 12, 31))
```

**Parameters:**
- `periods` (int): Number of periods to retrieve (default: 4)
- `as_of` (date, optional): Get snapshot as of specific date
- `as_dataframe` (bool): If True, return DataFrame; if False, return FinancialStatement (default: False)
- `annual` (bool): If True, prefer annual periods (default: True)

**Returns:** FinancialStatement or DataFrame

#### `cash_flow(periods: int = 4, period_length: Optional[int] = None, as_dataframe: bool = False, annual: bool = True)`

Get cash flow statement facts.

```python
# Annual cash flow trends
stmt = facts.cash_flow(periods=5, annual=True)
```

**Parameters:**
- `periods` (int): Number of periods to retrieve (default: 4)
- `period_length` (int, optional): Filter by period length in months
- `as_dataframe` (bool): If True, return DataFrame; if False, return FinancialStatement (default: False)
- `annual` (bool): If True, prefer annual periods (default: True)

**Returns:** FinancialStatement or DataFrame

### DEI Methods

#### `dei_facts(as_of: Optional[date] = None) -> pd.DataFrame`

Get Document and Entity Information facts.

```python
# Latest DEI facts
dei = facts.dei_facts()

# DEI facts as of specific date
dei = facts.dei_facts(as_of=date(2024, 12, 31))
```

**Parameters:**
- `as_of` (date, optional): Get facts as of specific date

**Returns:** DataFrame with DEI facts

#### `entity_info() -> Dict[str, Any]`

Get key entity information as a clean dictionary.

```python
info = facts.entity_info()
print(info['entity_name'])
print(info['shares_outstanding'])
```

**Returns:** Dictionary with entity information

### AI/LLM Methods

#### `to_llm_context(focus_areas: Optional[List[str]] = None, time_period: str = "recent") -> Dict[str, Any]`

Generate comprehensive context for LLM analysis.

```python
context = facts.to_llm_context(
    focus_areas=['profitability', 'growth'],
    time_period='5Y'
)
```

**Parameters:**
- `focus_areas` (List[str], optional): Areas to emphasize (['profitability', 'growth', 'liquidity'])
- `time_period` (str): Time period to analyze ('recent', '5Y', '10Y', 'all') (default: 'recent')

**Returns:** Dictionary with structured LLM context

#### `to_agent_tools() -> List[Dict[str, Any]]`

Export facts as MCP-compatible tools for AI agents.

```python
tools = facts.to_agent_tools()
```

**Returns:** List of tool definitions

### Magic Methods

#### `__len__() -> int`
Get total number of facts.

```python
total_facts = len(facts)
```

#### `__iter__() -> Iterator[FinancialFact]`
Iterate over all facts.

```python
for fact in facts:
    print(f"{fact.concept}: {fact.numeric_value}")
```

## FactQuery Class

Fluent query builder for advanced fact filtering and analysis.

### Constructor

Created via `EntityFacts.query()` method. Do not instantiate directly.

### Filtering Methods

#### Concept Filtering

#### `by_concept(concept: str, exact: bool = False) -> FactQuery`

Filter by concept name or pattern.

```python
# Fuzzy matching (default)
revenue_facts = query.by_concept('Revenue')

# Exact matching  
exact_revenue = query.by_concept('us-gaap:Revenue', exact=True)
```

**Parameters:**
- `concept` (str): Concept name or label to match
- `exact` (bool): If True, require exact match (default: False)

#### `by_label(label: str, fuzzy: bool = True) -> FactQuery`

Filter by human-readable label.

```python
# Fuzzy label matching
facts = query.by_label('Total Revenue', fuzzy=True)

# Exact label matching
facts = query.by_label('Revenue', fuzzy=False)
```

**Parameters:**
- `label` (str): Label to match
- `fuzzy` (bool): Use fuzzy matching (default: True)

#### Time-Based Filtering

#### `by_fiscal_year(year: int) -> FactQuery`

Filter by fiscal year.

```python
fy2024_facts = query.by_fiscal_year(2024)
```

**Parameters:**
- `year` (int): Fiscal year to filter by

#### `by_fiscal_period(period: str) -> FactQuery`

Filter by fiscal period.

```python
q1_facts = query.by_fiscal_period('Q1')
fy_facts = query.by_fiscal_period('FY')
```

**Parameters:**
- `period` (str): Fiscal period ('FY', 'Q1', 'Q2', 'Q3', 'Q4')

#### `by_period_length(months: int) -> FactQuery`

Filter by period length in months.

```python
# Quarterly periods (3 months)
quarterly = query.by_period_length(3)

# Annual periods (12 months)
annual = query.by_period_length(12)
```

**Parameters:**
- `months` (int): Period length (3=quarterly, 12=annual, 9=YTD)

#### `date_range(start: date, end: date) -> FactQuery`

Filter by date range.

```python
recent_facts = query.date_range(
    start=date(2023, 1, 1),
    end=date(2024, 12, 31)
)
```

**Parameters:**
- `start` (date): Start date (inclusive)
- `end` (date): End date (inclusive)

#### `as_of(as_of_date: date) -> FactQuery`

Get facts as of specific date (point-in-time).

```python
snapshot = query.as_of(date(2024, 6, 30))
```

**Parameters:**
- `as_of_date` (date): Date for point-in-time view

#### Statement and Form Filtering

#### `by_statement_type(statement_type: str) -> FactQuery`

Filter by financial statement type.

```python
income_facts = query.by_statement_type('IncomeStatement')
balance_facts = query.by_statement_type('BalanceSheet')
cash_facts = query.by_statement_type('CashFlow')
```

**Parameters:**
- `statement_type` (str): Statement type ('IncomeStatement', 'BalanceSheet', 'CashFlow')

#### `by_form_type(form_type: Union[str, List[str]]) -> FactQuery`

Filter by SEC form type.

```python
# Single form type
annual_facts = query.by_form_type('10-K')

# Multiple form types
periodic_facts = query.by_form_type(['10-K', '10-Q'])
```

**Parameters:**
- `form_type` (str or List[str]): Form type(s) to filter by

#### Quality Filtering

#### `high_quality_only() -> FactQuery`

Filter to only high-quality, audited facts.

```python
quality_facts = query.high_quality_only()
```

#### `min_confidence(threshold: float) -> FactQuery`

Filter by minimum confidence score.

```python
confident_facts = query.min_confidence(0.9)
```

**Parameters:**
- `threshold` (float): Minimum confidence score (0.0 to 1.0)

#### Special Queries

#### `latest_instant() -> FactQuery`

Filter to most recent instant facts (for balance sheet items).

```python
latest_balance = query.by_statement_type('BalanceSheet').latest_instant()
```

#### `latest_periods(n: int = 4, prefer_annual: bool = True) -> FactQuery`

Get facts from the n most recent periods.

```python
# Latest 4 periods, preferring annual
recent = query.latest_periods(4, prefer_annual=True)

# Latest 8 periods, any type
recent = query.latest_periods(8, prefer_annual=False)
```

**Parameters:**
- `n` (int): Number of recent periods (default: 4)
- `prefer_annual` (bool): Prefer annual over interim periods (default: True)

### Sorting and Limiting

#### `sort_by(field: str, ascending: bool = True) -> FactQuery`

Sort results by field.

```python
# Sort by filing date (newest first)
sorted_facts = query.sort_by('filing_date', ascending=False)

# Sort by fiscal year
sorted_facts = query.sort_by('fiscal_year')
```

**Parameters:**
- `field` (str): Field name to sort by
- `ascending` (bool): Sort order (default: True)

#### `latest(n: int = 1) -> List[FinancialFact]`

Get the n most recent facts.

```python
latest_revenue = query.by_concept('Revenue').latest(5)
```

**Parameters:**
- `n` (int): Number of facts to return (default: 1)

**Returns:** List of facts (executes query immediately)

### Execution Methods

#### `execute() -> List[FinancialFact]`

Execute query and return matching facts.

```python
facts = query.by_concept('Revenue').by_fiscal_year(2024).execute()
```

**Returns:** List of FinancialFact objects

#### `count() -> int`

Get count of facts matching current filters.

```python
revenue_count = query.by_concept('Revenue').count()
```

**Returns:** Number of matching facts

### Output Methods

#### `to_dataframe(*columns) -> pd.DataFrame`

Convert results to pandas DataFrame.

```python
# All columns
df = query.by_concept('Revenue').to_dataframe()

# Selected columns
df = query.by_concept('Revenue').to_dataframe(
    'label', 'numeric_value', 'fiscal_period'
)
```

**Parameters:**
- `*columns` (str): Optional column names to include

**Returns:** DataFrame with query results

#### `pivot_by_period(return_statement: bool = True) -> Union[FinancialStatement, pd.DataFrame]`

Pivot facts to show concepts as rows and periods as columns.

```python
# Formatted financial statement
stmt = query.by_statement_type('IncomeStatement').pivot_by_period()

# Raw DataFrame
df = query.by_statement_type('IncomeStatement').pivot_by_period(return_statement=False)
```

**Parameters:**
- `return_statement` (bool): If True, return FinancialStatement; if False, return DataFrame (default: True)

**Returns:** FinancialStatement or DataFrame

#### `to_llm_context() -> List[Dict[str, Any]]`

Convert results to LLM-friendly context.

```python
llm_data = query.by_concept('Revenue').to_llm_context()
```

**Returns:** List of fact contexts for LLM consumption

## FinancialStatement Class

Wrapper around pandas DataFrame for financial statements with intelligent formatting.

### Constructor

```python
FinancialStatement(
    data: pd.DataFrame,
    statement_type: str,
    entity_name: str = "",
    period_lengths: Optional[List[str]] = None,
    mixed_periods: bool = False
)
```

**Parameters:**
- `data` (pd.DataFrame): Financial data
- `statement_type` (str): Statement type
- `entity_name` (str): Company name
- `period_lengths` (List[str], optional): Period lengths in data
- `mixed_periods` (bool): Whether data contains mixed period lengths

### Properties

#### `shape: tuple`
Shape of the underlying DataFrame.

```python
stmt = company.income_statement()
print(stmt.shape)  # (10, 4)
```

#### `columns: pd.Index`
Column names of the statement.

```python
periods = stmt.columns
print(list(periods))  # ['FY 2024', 'FY 2023', 'FY 2022', 'FY 2021']
```

#### `index: pd.Index`
Row labels (concept names).

```python
concepts = stmt.index
print(list(concepts))  # ['Revenue', 'Cost of Revenue', 'Gross Profit', ...]
```

#### `empty: bool`
Whether the statement is empty.

```python
if not stmt.empty:
    print("Statement has data")
```

### Methods

#### `to_numeric() -> pd.DataFrame`

Get underlying numeric DataFrame for calculations.

```python
stmt = company.income_statement()
numeric_data = stmt.to_numeric()
growth_rates = numeric_data.pct_change(axis=1)
```

**Returns:** DataFrame with original numeric values

#### `get_concept(concept_name: str) -> Optional[pd.Series]`

Get data for specific concept across all periods.

```python
revenue_series = stmt.get_concept('Revenue')
if revenue_series is not None:
    print(revenue_series)
```

**Parameters:**
- `concept_name` (str): Name of concept to retrieve

**Returns:** Series with values across periods, or None

#### `calculate_growth(concept_name: str, periods: int = 2) -> Optional[pd.Series]`

Calculate period-over-period growth for a concept.

```python
revenue_growth = stmt.calculate_growth('Revenue', periods=1)
```

**Parameters:**
- `concept_name` (str): Name of concept
- `periods` (int): Number of periods for growth calculation (default: 2)

**Returns:** Series with growth rates, or None

#### `format_value(value: float, concept_label: str) -> str`

Format a single value based on its concept.

```python
formatted = stmt.format_value(1234567, 'Revenue')
print(formatted)  # "$1,234,567"
```

**Parameters:**
- `value` (float): Numeric value to format
- `concept_label` (str): Label of financial concept

**Returns:** Formatted string

#### `to_llm_context() -> Dict[str, Any]`

Generate LLM-friendly context from the statement.

```python
context = stmt.to_llm_context()
```

**Returns:** Dictionary with structured financial data

### Display Methods

The FinancialStatement class provides rich display capabilities:

- **Jupyter Notebooks**: Automatic HTML rendering with professional styling
- **Console**: Formatted text output with proper alignment
- **Rich Integration**: Compatible with Rich library for enhanced terminal display

## FinancialFact Class

Individual financial fact with rich metadata and AI-ready features.

### Constructor

```python
FinancialFact(
    concept: str,
    taxonomy: str,
    label: str,
    value: Union[float, int, str],
    numeric_value: Optional[float],
    unit: str,
    scale: Optional[int] = None,
    # ... additional parameters
)
```

### Core Attributes

#### `concept: str`
Standardized concept identifier (e.g., 'us-gaap:Revenue').

#### `taxonomy: str`
Taxonomy namespace (us-gaap, ifrs, etc.).

#### `label: str`
Human-readable label.

#### `value: Union[float, int, str]`
The actual fact value.

#### `numeric_value: Optional[float]`
Numeric representation for calculations.

#### `unit: str`
Unit of measure (USD, shares, etc.).

#### `scale: Optional[int]`
Scale factor (1000, 1000000, etc.).

### Temporal Attributes

#### `period_start: Optional[date]`
Period start date (for duration facts).

#### `period_end: date`
Period end date.

#### `period_type: Literal['instant', 'duration']`
Type of period.

#### `fiscal_year: int`
Fiscal year.

#### `fiscal_period: str`
Fiscal period (FY, Q1, Q2, Q3, Q4).

### Filing Context

#### `filing_date: date`
Date the fact was filed with SEC.

#### `form_type: str`
SEC form type (10-K, 10-Q, etc.).

#### `accession: str`
SEC accession number.

### Quality Indicators

#### `data_quality: DataQuality`
Data quality enum (HIGH, MEDIUM, LOW).

#### `is_audited: bool`
Whether the fact is from audited filing.

#### `confidence_score: float`
Confidence score (0.0 to 1.0).

### AI-Ready Attributes

#### `semantic_tags: List[str]`
Semantic tags for AI processing.

#### `business_context: str`
Business context description.

### Methods

#### `to_llm_context() -> Dict[str, Any]`

Generate rich context for LLM consumption.

```python
fact = facts.get_fact('Revenue')
context = fact.to_llm_context()
print(context['concept'])
print(context['value'])
print(context['period'])
```

**Returns:** Dictionary with formatted context

#### `get_formatted_value() -> str`

Format the numeric value for display.

```python
fact = facts.get_fact('Revenue')
formatted = fact.get_formatted_value()
print(formatted)  # "365,817,000,000"
```

**Returns:** Formatted string representation

#### `get_display_period_key() -> str`

Generate display-friendly period key.

```python
fact = facts.get_fact('Revenue')
period = fact.get_display_period_key()
print(period)  # "Q1 2024"
```

**Returns:** Period key like "Q1 2024", "FY 2023"

## EntityFactsParser Class

Parser for converting SEC JSON data to enhanced EntityFacts format.

### Static Methods

#### `parse_company_facts(facts_json: Dict[str, Any]) -> EntityFacts`

Parse SEC company facts JSON to EntityFacts object.

```python
from edgar.entity.parser import EntityFactsParser

# Download SEC JSON
facts_json = download_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")

# Parse to enhanced format
entity_facts = EntityFactsParser.parse_company_facts(facts_json)
```

**Parameters:**
- `facts_json` (Dict): SEC company facts JSON data

**Returns:** EntityFacts object

## Data Models

### DataQuality Enum

Quality indicators for financial facts.

```python
from edgar.entity.models import DataQuality

DataQuality.HIGH    # Direct from XBRL, validated
DataQuality.MEDIUM  # Derived or calculated  
DataQuality.LOW     # Estimated or inferred
```

### ConceptMetadata Class

Metadata about financial concepts.

```python
@dataclass
class ConceptMetadata:
    concept: str
    label: str
    definition: str
    parent_concepts: List[str]
    child_concepts: List[str]
    # ... additional fields
```

## Error Handling

### NoCompanyFactsFound Exception

Raised when company facts cannot be found.

```python
from edgar.entity.core import NoCompanyFactsFound

try:
    facts = get_company_facts(invalid_cik)
except NoCompanyFactsFound as e:
    print(f"No facts found: {e.message}")
```

## Type Hints

The API uses comprehensive type hints for better IDE support:

```python
from typing import Optional, List, Dict, Any, Union
from datetime import date
from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact
from edgar.entity.query import FactQuery
from edgar.entity.statement import FinancialStatement
```

## Usage Patterns

### Method Chaining

All query methods return the query object for chaining:

```python
results = facts.query()\
    .by_concept('Revenue')\
    .by_fiscal_year(2024)\
    .by_form_type('10-K')\
    .sort_by('filing_date')\
    .execute()
```

### Error Handling

The API uses graceful error handling:

```python
# Methods return None instead of raising exceptions
stmt = company.income_statement()  # Returns None if no data
if stmt:
    # Process statement
    pass
```

### Performance Considerations

- Use specific filters for better performance
- Leverage caching by reusing EntityFacts objects
- Use `count()` for existence checks before loading data
- Prefer `latest()` over `execute()` when you need recent data only

---

*This API reference documents EdgarTools EntityFacts system. For usage examples and tutorials, see the [Company Facts Guide](../guides/company-facts.md).*
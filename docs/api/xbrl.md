# XBRL API Reference

The XBRL module provides comprehensive parsing and processing of XBRL (eXtensible Business Reporting Language) data from SEC filings. It includes support for statement standardization, multi-period analysis, and advanced querying capabilities.

## Module Overview

The XBRL module is organized into several key components:

- **Core Classes**: `XBRL`, `XBRLS` for parsing and managing XBRL documents
- **Statement Processing**: `Statements`, `Statement` for working with financial statements
- **Facts Querying**: `FactsView`, `FactQuery` for querying XBRL facts
- **Multi-Period Analysis**: `StitchedStatements`, `StitchedStatement` for comparative analysis
- **Standardization**: `StandardConcept` for normalizing company-specific concepts
- **Rendering**: `RenderedStatement` for formatted output

## Core Classes

### XBRL

The main class for parsing and working with XBRL documents from SEC filings.

```python
from edgar.xbrl import XBRL

class XBRL:
    """Main XBRL parser integrating all components of the XBRL parsing system."""
```

#### Factory Methods

#### from_filing()
```python
@classmethod
def from_filing(cls, filing: Filing) -> XBRL
```
Create an XBRL instance from a Filing object.

**Parameters:**
- `filing`: SEC filing object containing XBRL data

**Returns:** `XBRL` instance

**Example:**
```python
from edgar import Company
from edgar.xbrl import XBRL

company = Company("AAPL")
filing = company.latest("10-K")
xbrl = XBRL.from_filing(filing)
```

#### from_directory()
```python
@classmethod
def from_directory(cls, directory: str) -> XBRL
```
Create an XBRL instance from a directory containing XBRL files.

**Parameters:**
- `directory`: Path to directory containing XBRL files

**Returns:** `XBRL` instance

#### from_files()
```python
@classmethod
def from_files(cls, files: List[str]) -> XBRL
```
Create an XBRL instance from a list of XBRL files.

**Parameters:**
- `files`: List of file paths to XBRL documents

**Returns:** `XBRL` instance

#### Core Properties

#### statements
```python
@property
def statements(self) -> Statements
```
Access to all financial statements in the XBRL document.

**Returns:** `Statements` object for accessing individual statements

**Example:**
```python
# Access different statement types
balance_sheet = xbrl.statements.balance_sheet()
income_statement = xbrl.statements.income_statement()
cash_flow = xbrl.statements.cash_flow_statement()
```

#### facts
```python
@property
def facts(self) -> FactsView
```
Access to all XBRL facts with querying capabilities.

**Returns:** `FactsView` object for querying facts

**Example:**
```python
# Query facts by concept
revenue_facts = xbrl.facts.by_concept("Revenue")

# Convert to DataFrame for analysis
facts_df = xbrl.facts.to_dataframe()
```

#### Statement Methods

#### get_statement()
```python
def get_statement(self, statement_type: str) -> Optional[Statement]
```
Get a specific financial statement by type.

**Parameters:**
- `statement_type`: Statement type ("BalanceSheet", "IncomeStatement", "CashFlowStatement", etc.)

**Returns:** `Statement` object or None if not found

#### render_statement()
```python
def render_statement(self, statement_type: str, **kwargs) -> RenderedStatement
```
Render a financial statement with rich formatting.

**Parameters:**
- `statement_type`: Statement type to render
- `**kwargs`: Additional rendering options

**Returns:** `RenderedStatement` object

**Example:**
```python
# Render balance sheet
rendered = xbrl.render_statement("BalanceSheet")
print(rendered)

# Render with custom options
rendered = xbrl.render_statement("IncomeStatement", 
                                show_percentages=True,
                                max_rows=50)
```

#### Data Conversion

#### to_pandas()
```python
def to_pandas(self) -> pd.DataFrame
```
Convert XBRL facts to a pandas DataFrame.

**Returns:** DataFrame with all facts and their attributes

**Example:**
```python
# Convert to DataFrame for analysis
df = xbrl.to_pandas()
print(df.columns)  # ['concept', 'value', 'period', 'label', ...]

# Filter for specific concepts
revenue_df = df[df['concept'].str.contains('Revenue', case=False)]
```

### XBRLS

Container class for managing multiple XBRL documents for multi-period analysis.

```python
from edgar.xbrl import XBRLS

class XBRLS:
    """Container for multiple XBRL objects enabling multi-period analysis."""
```

#### Factory Methods

#### from_filings()
```python
@classmethod
def from_filings(cls, filings: List[Filing]) -> XBRLS
```
Create an XBRLS instance from multiple filings.

**Parameters:**
- `filings`: List of Filing objects

**Returns:** `XBRLS` instance

**Example:**
```python
from edgar import Company
from edgar.xbrl import XBRLS

company = Company("AAPL")
filings = company.get_filings(form="10-K").head(3)  # Get 3 years
xbrls = XBRLS.from_filings(filings)
```

#### Properties

#### statements
```python
@property
def statements(self) -> StitchedStatements
```
Access to stitched statements showing multi-period data.

**Returns:** `StitchedStatements` object

**Example:**
```python
# Get multi-period statements
income_stmt = xbrls.statements.income_statement()
balance_sheet = xbrls.statements.balance_sheet()

# Render multi-period view
print(income_stmt.render())
```

## Statement Classes

### Statements

High-level interface for accessing financial statements from a single XBRL document.

```python
class Statements:
    """High-level interface to all statements in an XBRL document."""
```

#### Statement Access Methods

#### balance_sheet()
```python
def balance_sheet(self) -> Optional[Statement]
```
Get the balance sheet statement.

**Returns:** `Statement` object or None

#### income_statement()
```python
def income_statement(self) -> Optional[Statement]
```
Get the income statement.

**Returns:** `Statement` object or None

#### cash_flow_statement()
```python
def cash_flow_statement(self) -> Optional[Statement]
```
Get the cash flow statement.

**Returns:** `Statement` object or None

#### statement_of_equity()
```python
def statement_of_equity(self) -> Optional[Statement]
```
Get the statement of equity.

**Returns:** `Statement` object or None

#### comprehensive_income()
```python
def comprehensive_income(self) -> Optional[Statement]
```
Get the comprehensive income statement.

**Returns:** `Statement` object or None

**Example:**
```python
statements = xbrl.statements

# Access different statement types
if statements.balance_sheet():
    bs = statements.balance_sheet()
    print(f"Total Assets: {bs.get_concept_value('Assets')}")

if statements.income_statement():
    is_stmt = statements.income_statement()
    print(f"Revenue: {is_stmt.get_concept_value('Revenue')}")
```

### Statement

Individual financial statement with analysis and rendering capabilities.

```python
class Statement:
    """A single financial statement extracted from XBRL data."""
```

#### Core Methods

#### render()
```python
def render(self, **kwargs) -> RenderedStatement
```
Render the statement with rich formatting.

**Parameters:**
- `**kwargs`: Rendering options (show_percentages, max_rows, etc.)

**Returns:** `RenderedStatement` object

#### to_dataframe()
```python
def to_dataframe(
    self,
    include_dimensions: bool = True,
    include_unit: bool = False,
    include_point_in_time: bool = False,
    presentation: bool = False
) -> pd.DataFrame
```
Convert statement to pandas DataFrame with optional transformations.

**Parameters:**
- `include_dimensions`: Include dimensional breakdowns (default: True)
- `include_unit`: Include unit column (USD, shares, etc.) (default: False)
- `include_point_in_time`: Include point-in-time column for instant facts (default: False)
- `presentation`: Apply HTML-matching transformations using preferred_sign (default: False)
  - False (default): Raw instance values from XML
  - True: Transform values to match SEC filing HTML display

**Returns:** DataFrame with the following columns:
- **Core columns**: `concept`, `label`, period columns (dates)
- **Metadata columns** (always included): `balance`, `weight`, `preferred_sign`
- **Optional columns**: `dimension`, `unit`, `point_in_time`

**Value Modes:**
- **Raw mode** (default): Preserves values exactly as reported in instance document
- **Presentation mode** (`presentation=True`): Applies transformations to match SEC HTML rendering
  - Cash Flow: outflows with preferred_sign=-1 shown as negative
  - Income Statement: applies preferred_sign transformations

**Example:**
```python
statement = xbrl.statements.income_statement()

# Raw values (default)
df_raw = statement.to_dataframe()
# Returns actual XML values + metadata columns

# Presentation mode (matches SEC HTML)
df_presentation = statement.to_dataframe(presentation=True)
# Returns transformed values matching 10-K HTML display

# Check metadata
print(df_raw[['concept', 'balance', 'weight', 'preferred_sign']].head())
```

**See Also:** Issue #463 - XBRL value transformations and metadata columns

**Returns:** DataFrame with statement data

#### get_concept_value()
```python
def get_concept_value(self, concept: str) -> Optional[Any]
```
Get the value for a specific concept.

**Parameters:**
- `concept`: Concept name to look up

**Returns:** Concept value or None

**Example:**
```python
statement = xbrl.statements.income_statement()

# Render the statement
rendered = statement.render()
print(rendered)

# Convert to DataFrame
df = statement.to_dataframe()

# Get specific values
revenue = statement.get_concept_value("Revenue")
net_income = statement.get_concept_value("NetIncomeLoss")
```

## Facts Querying

### FactsView

Provides a view over all XBRL facts with analysis and querying methods.

```python
class FactsView:
    """View over all facts with analysis methods."""
```

#### Query Methods

#### by_concept()
```python
def by_concept(self, pattern: str, exact: bool = False) -> FactQuery
```
Filter facts by concept name.

**Parameters:**
- `pattern`: Pattern to match against concept names
- `exact`: If True, require exact match; otherwise, use regex

**Returns:** `FactQuery` object for further filtering

#### by_label()
```python
def by_label(self, pattern: str, exact: bool = False) -> FactQuery
```
Filter facts by element label.

**Parameters:**
- `pattern`: Pattern to match against labels
- `exact`: If True, require exact match; otherwise, use regex

**Returns:** `FactQuery` object for further filtering

#### by_value()
```python
def by_value(self, min_value: float = None, max_value: float = None) -> FactQuery
```
Filter facts by value range.

**Parameters:**
- `min_value`: Minimum value threshold
- `max_value`: Maximum value threshold

**Returns:** `FactQuery` object for further filtering

#### by_period()
```python
def by_period(self, start_date: str = None, end_date: str = None) -> FactQuery
```
Filter facts by period range.

**Parameters:**
- `start_date`: Start date (YYYY-MM-DD format)
- `end_date`: End date (YYYY-MM-DD format)

**Returns:** `FactQuery` object for further filtering

#### Analysis Methods

#### pivot_by_period()
```python
def pivot_by_period(self, concepts: List[str] = None) -> pd.DataFrame
```
Create a pivot table showing concepts by period.

**Parameters:**
- `concepts`: List of concepts to include (default: all)

**Returns:** DataFrame with concepts as rows and periods as columns

#### time_series()
```python
def time_series(self, concept: str) -> pd.Series
```
Get time series data for a specific concept.

**Parameters:**
- `concept`: Concept name

**Returns:** pandas Series with time series data

#### Data Conversion

#### to_dataframe()
```python
def to_dataframe(self) -> pd.DataFrame
```
Convert facts to pandas DataFrame.

**Returns:** DataFrame with all facts and metadata

**Example:**
```python
facts = xbrl.facts

# Query by concept
revenue_query = facts.by_concept("Revenue")
revenue_facts = revenue_query.execute()

# Query by label and value
large_expenses = facts.by_label("expense").by_value(min_value=1000000)
expense_facts = large_expenses.to_dataframe()

# Time series analysis
revenue_ts = facts.time_series("Revenue")
print(revenue_ts.head())

# Pivot analysis
pivot_df = facts.pivot_by_period(["Revenue", "NetIncomeLoss"])
```

### FactQuery

Fluent query builder for filtering and manipulating XBRL facts.

```python
class FactQuery:
    """A query builder for XBRL facts with fluent interface."""
```

#### Filtering Methods

All filtering methods return `self` for method chaining.

#### by_concept()
```python
def by_concept(self, pattern: str, exact: bool = False) -> FactQuery
```

#### by_label()
```python
def by_label(self, pattern: str, exact: bool = False) -> FactQuery
```

#### by_value()
```python
def by_value(self, min_value: float = None, max_value: float = None) -> FactQuery
```

#### by_period()
```python
def by_period(self, start_date: str = None, end_date: str = None) -> FactQuery
```

#### by_statement()
```python
def by_statement(self, statement_type: str) -> FactQuery
```
Filter facts by statement type.

**Parameters:**
- `statement_type`: Statement type to filter by

**Returns:** `FactQuery` object for method chaining

#### Execution Methods

#### execute()
```python
def execute(self) -> List[Dict]
```
Execute the query and return matching facts.

**Returns:** List of fact dictionaries

#### to_dataframe()
```python
def to_dataframe(self) -> pd.DataFrame
```
Execute the query and return results as DataFrame.

**Returns:** DataFrame with query results

#### first()
```python
def first(self) -> Optional[Dict]
```
Get the first matching fact.

**Returns:** First fact dictionary or None

#### count()
```python
def count(self) -> int
```
Count matching facts without retrieving them.

**Returns:** Number of matching facts

**Example:**
```python
# Chain multiple filters
query = (xbrl.facts
         .by_concept("Revenue")
         .by_period(start_date="2023-01-01")
         .by_value(min_value=1000000))

# Execute in different ways
facts_list = query.execute()
facts_df = query.to_dataframe()
first_fact = query.first()
count = query.count()
```

## Multi-Period Analysis

### StitchedStatements

Interface for accessing multi-period statements that combine data across multiple XBRL documents.

```python
class StitchedStatements:
    """Interface for multi-period statements."""
```

#### Statement Access Methods

Similar to `Statements` but returns `StitchedStatement` objects. All methods accept these common parameters:

- `max_periods` (int): Maximum number of periods to include (default: 8)
- `standard` (bool): Whether to use standardized concept labels (default: True)
- `use_optimal_periods` (bool): Whether to use entity info for optimal period selection (default: True)
- `show_date_range` (bool): Whether to show full date ranges for duration periods (default: False)
- `include_dimensions` (bool): Whether to include dimensional segment data (default: False, True for equity/comprehensive income)
- `view` (str): Controls dimensional filtering — `"standard"`, `"detailed"`, or `"summary"`. Overrides `include_dimensions` when provided.

#### balance_sheet()
```python
def balance_sheet(self, view=None, **kwargs) -> Optional[StitchedStatement]
```

#### income_statement()
```python
def income_statement(self, view=None, **kwargs) -> Optional[StitchedStatement]
```

#### cashflow_statement()
```python
def cashflow_statement(self, view=None, **kwargs) -> Optional[StitchedStatement]
```

#### statement_of_equity()
```python
def statement_of_equity(self, view=None, **kwargs) -> Optional[StitchedStatement]
```

#### comprehensive_income()
```python
def comprehensive_income(self, view=None, **kwargs) -> Optional[StitchedStatement]
```

**Example:**
```python
# Multi-period analysis
stitched_statements = xbrls.statements
income_stmt = stitched_statements.income_statement()

# Shows multiple years of data
print(income_stmt.render())

# Include dimensional breakdowns (e.g., cost by segment)
income_detailed = stitched_statements.income_statement(view="detailed")
df = income_detailed.to_dataframe()
```

### StitchedStatement

Individual statement showing multi-period data with comparative analysis.

```python
class StitchedStatement:
    """Individual stitched statement showing multi-period data."""
```

**Constructor Parameters:**
- `xbrls`: XBRLS object containing stitched data
- `statement_type` (str): Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
- `max_periods` (int): Maximum number of periods (default: 8)
- `standard` (bool): Use standardized labels (default: True)
- `include_dimensions` (bool): Include dimensional data (default: False)
- `view` (str): `"standard"`, `"detailed"`, or `"summary"`. Overrides `include_dimensions`.

#### Analysis Methods

#### render()
```python
def render(self, show_date_range: bool = False) -> Table
```
Render multi-period statement with rich formatting.

#### to_dataframe()
```python
def to_dataframe(self) -> pd.DataFrame
```
Convert to DataFrame with periods as columns.

## Standardization

### StandardConcept

Represents a standardized concept that normalizes company-specific terminology.

```python
class StandardConcept:
    """Standardized concept representation."""
```

#### Properties

#### name
```python
@property
def name(self) -> str
```
Standardized concept name.

#### label
```python
@property
def label(self) -> str
```
Standardized human-readable label.

**Example:**
```python
# Standardization is applied automatically in statements
statement = xbrl.statements.income_statement()
df = statement.to_dataframe()

# Check for standardized vs original labels
print(df[['label', 'original_label']].head())
```

## Rendering

### RenderedStatement

Formatted statement output with rich console display capabilities.

```python
class RenderedStatement:
    """Rich formatted statement output."""
```

#### Display Methods

#### __str__()
```python
def __str__(self) -> str
```
Plain text representation of the statement.

#### __rich__()
```python
def __rich__(self) -> RichRenderable
```
Rich console representation with formatting.

**Example:**
```python
# Rich rendering in console
rendered = xbrl.render_statement("BalanceSheet")
print(rendered)  # Displays with rich formatting

# Plain text for export
text_output = str(rendered)
```

## Utility Functions

### stitch_statements()
```python
def stitch_statements(statements: List[Statement]) -> StitchedStatement
```
Combine multiple statements into a stitched statement.

**Parameters:**
- `statements`: List of Statement objects to combine

**Returns:** `StitchedStatement` object

### render_stitched_statement()
```python
def render_stitched_statement(stitched_statement: StitchedStatement, **kwargs) -> RenderedStatement
```
Render a stitched statement with formatting.

**Parameters:**
- `stitched_statement`: StitchedStatement to render
- `**kwargs`: Rendering options

**Returns:** `RenderedStatement` object

### to_pandas()
```python
def to_pandas(obj: Union[XBRL, Statement, FactsView]) -> pd.DataFrame
```
Convert various XBRL objects to pandas DataFrame.

**Parameters:**
- `obj`: Object to convert (XBRL, Statement, or FactsView)

**Returns:** DataFrame representation

## Advanced Usage Examples

### Multi-Period Financial Analysis

```python
from edgar import Company
from edgar.xbrl import XBRLS

# Get multiple years of data
company = Company("AAPL")
filings = company.get_filings(form="10-K").head(3)
xbrls = XBRLS.from_filings(filings)

# Analyze income statement trends
income_stmt = xbrls.statements.income_statement()
revenue_trend = income_stmt.get_trend("Revenue")
revenue_growth = income_stmt.calculate_growth("Revenue")

print(f"Revenue Growth: {revenue_growth.iloc[-1]:.2%}")
```

### Complex Fact Querying

```python
from edgar import Company
from edgar.xbrl import XBRL

company = Company("MSFT")
filing = company.latest("10-K")
xbrl = XBRL.from_filing(filing)

# Complex query with multiple filters
high_value_revenue = (xbrl.facts
                     .by_concept("Revenue")
                     .by_value(min_value=50000000000)  # $50B+
                     .by_period(start_date="2023-01-01")
                     .to_dataframe())

# Pivot analysis
pivot_df = xbrl.facts.pivot_by_period([
    "Revenue", 
    "NetIncomeLoss", 
    "OperatingIncomeLoss"
])
```

### Statement Comparison

```python
# Compare statements across different companies
companies = ["AAPL", "MSFT", "GOOGL"]
statements = []

for ticker in companies:
    company = Company(ticker)
    filing = company.latest("10-K")
    xbrl = XBRL.from_filing(filing)
    if xbrl.statements.income_statement():
        statements.append(xbrl.statements.income_statement())

# Create comparison DataFrame
comparison_data = []
for stmt in statements:
    df = stmt.to_dataframe()
    comparison_data.append(df)

# Analyze key metrics across companies
key_metrics = ["Revenue", "NetIncomeLoss", "OperatingIncomeLoss"]
for metric in key_metrics:
    print(f"\n{metric} Comparison:")
    for i, stmt in enumerate(statements):
        value = stmt.get_concept_value(metric)
        if value:
            print(f"  {companies[i]}: ${value/1e9:.1f}B")
```

## Import Reference

```python
# Core classes
from edgar.xbrl import XBRL, XBRLS

# Statement classes
from edgar.xbrl import Statements, Statement
from edgar.xbrl import StitchedStatements, StitchedStatement

# Facts querying
from edgar.xbrl import FactsView, FactQuery
from edgar.xbrl import StitchedFactsView, StitchedFactQuery

# Standardization and rendering
from edgar.xbrl import StandardConcept, RenderedStatement

# Utility functions
from edgar.xbrl import stitch_statements, render_stitched_statement, to_pandas
```

## Error Handling

```python
from edgar.xbrl import XBRL, XBRLFilingWithNoXbrlData

try:
    xbrl = XBRL.from_filing(filing)
except XBRLFilingWithNoXbrlData:
    print("Filing does not contain XBRL data")
except Exception as e:
    print(f"Error parsing XBRL: {e}")

# Check for statement availability
if xbrl.statements.income_statement():
    income_stmt = xbrl.statements.income_statement()
    df = income_stmt.to_dataframe()
else:
    print("Income statement not found")
```

## XBRL Value Transformations (Issue #463)

EdgarTools provides a two-layer system for XBRL value handling:

### Value Layers

1. **Raw Values** (default): Values exactly as reported in the XBRL instance document
   - Matches SEC CompanyFacts API
   - Preserves original data for analysis
   - No transformations applied

2. **Presentation Values** (`presentation=True`): Values transformed to match SEC filing HTML display
   - Applies `preferred_sign` transformations from presentation linkbase
   - Cash Flow outflows shown as negative when appropriate
   - Matches how values appear in the official 10-K/10-Q HTML

### Metadata Columns

All statement DataFrames include XBRL metadata columns:

- **`balance`**: Debit or credit classification from schema (accounting semantics)
- **`weight`**: Calculation weight from calculation linkbase (+1.0 or -1.0)
- **`preferred_sign`**: Presentation hint from presentation linkbase (+1 or -1)

These columns provide transparency about XBRL semantics and enable custom transformations.

### Usage Examples

```python
# Get raw values (default)
xbrl = filing.xbrl()
statement = xbrl.statements.cash_flow_statement()
df_raw = statement.to_dataframe()

# PaymentsOfDividends appears as positive (raw XML value)
dividends = df_raw[df_raw['concept'].str.contains('PaymentsOfDividends')]
print(dividends[['concept', 'balance', 'preferred_sign', '2024-09-30']])
# Output: concept=PaymentsOfDividends, balance=credit, preferred_sign=-1, value=12345000000 (positive)

# Get presentation values (matches SEC HTML)
df_presentation = statement.to_dataframe(presentation=True)
dividends_pres = df_presentation[df_presentation['concept'].str.contains('PaymentsOfDividends')]
print(dividends_pres[['concept', '2024-09-30']])
# Output: value=-12345000000 (negative, matches HTML display with parentheses)
```

### When to Use Each Mode

**Use Raw Values** (default):
- Cross-company financial analysis
- Data science and machine learning
- Comparison with SEC CompanyFacts API
- When you need unmodified reported values

**Use Presentation Values** (`presentation=True`):
- Matching SEC filing HTML display
- Creating investor-facing reports
- Replicating official financial statement appearance
- When users expect "traditional" financial statement signs

### Technical Notes

- **Raw values are consistent across companies**: Testing confirmed SEC instance data uses consistent signs
- **Metadata always included**: All transformations can be recreated using metadata columns
- **No data loss**: Raw values always preserved, transformations are reversible

## Performance Tips

1. **Use specific queries** - Filter facts early to reduce processing time
2. **Cache XBRL objects** - Parsing is expensive, reuse when possible
3. **Limit statement rendering** - Use `max_rows` parameter for large statements
4. **Batch processing** - Use `XBRLS` for efficient multi-period analysis

## See Also

- **[Company API Reference](company.md)** - Working with company data
- **[Filing API Reference](filing.md)** - Working with individual filings
- **[Extract Financial Statements Guide](../guides/extract-statements.md)** - Practical examples
- **[Working with Filing Guide](../guides/working-with-filing.md)** - Filing workflows
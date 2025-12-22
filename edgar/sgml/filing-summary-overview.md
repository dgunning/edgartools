# FilingSummary Overview

## Purpose

FilingSummary is a key component in SEC filings (particularly 10-K and 10-Q) that provides a structured index of all documents and reports within a filing. It acts as a table of contents, listing financial statements, notes, and exhibits in an organized hierarchy.

## Current Architecture

### Core Components

1. **FilingSummary** - Main class that parses the XML document listing all attachments
   - Contains metadata about the filing (entity count, context count, etc.)
   - Holds collections of reports organized by category
   - Provides access to input files and supplemental files

2. **Reports** - Collection class managing all reports in the filing
   - Implements pagination and filtering
   - Organized by categories: Statements, Notes, Tables, Policies, Details
   - Provides methods to find reports by name, category, or filename

3. **Report** - Individual report/document within the filing
   - Links to HTML files containing financial data
   - Contains metadata: position, category, long/short names
   - Currently extracts and displays content as rich text tables

4. **Statements** - Specialized wrapper for financial statements
   - Uses pattern matching to identify standard statements
   - Properties for easy access: balance_sheet, income_statement, etc.
   - Handles variations in naming conventions across companies

## Data Flow

```
Filing (SGML) → FilingSummary.xml → Reports Collection → Individual Report HTML
                                          ↓
                                    Statements Wrapper
                                    (Smart statement detection)
```

## Current Capabilities

- Parse FilingSummary.xml to extract report metadata
- Navigate reports by category, name, or position
- Display report content as formatted text tables
- Identify standard financial statements using regex patterns
- Access raw HTML content of individual reports

## Proposed Enhancement: DataFrame Extraction

### Goal
Add capability to extract financial tables from HTML reports as pandas DataFrames, providing an alternative to XBRL parsing that preserves company-specific formatting.

### Benefits
1. **Simpler extraction** - HTML tables are pre-formatted by companies
2. **Preserves presentation** - Maintains company's intended layout
3. **Complements XBRL** - Provides fallback when XBRL is complex/missing
4. **Direct access** - No need to understand XBRL taxonomy

### Challenges
1. **HTML complexity** - Nested tables, spans, styling variations
2. **Data identification** - Distinguishing data tables from layout tables
3. **Header detection** - Multi-level headers, merged cells
4. **Data typing** - Converting string values to appropriate types
5. **Period handling** - Extracting time periods from headers

## Implementation Strategy

### Phase 1: Table Extraction Infrastructure
- Enhance Report class with `to_dataframe()` method
- Identify and extract primary data tables from HTML
- Handle basic table structures with simple headers

### Phase 2: Smart Header Processing
- Detect multi-level column headers (periods, metrics)
- Handle row headers and hierarchical line items
- Extract metadata (currency, units, scaling factors)

### Phase 3: Data Normalization
- Convert string values to numeric types
- Handle parentheses for negative values
- Apply scaling factors (thousands, millions)
- Standardize date/period formats

### Phase 4: Statement-Specific Extractors
- Create specialized extractors for each statement type
- Handle statement-specific patterns and layouts
- Validate extracted data against known structures

### Example API

```python
# Get filing and reports
filing = Company("AAPL").get_filings(form="10-K").latest(1)
statements = filing.statements

# Extract balance sheet as DataFrame
balance_sheet_df = statements.balance_sheet.to_dataframe()
# Returns DataFrame with:
# - Index: Line items (Assets, Liabilities, etc.)
# - Columns: Period dates
# - Values: Numeric financial data

# Extract with options
income_df = statements.income_statement.to_dataframe(
    include_metadata=True,  # Include units, currency
    normalize_periods=True,  # Standardize period names
    numeric_only=False      # Keep text annotations
)

# Access specific tables within a report
tables = statements.balance_sheet.get_tables()
assets_df = tables[0].to_dataframe()  # First table might be assets
liabilities_df = tables[1].to_dataframe()  # Second might be liabilities
```

### Data Structure Considerations

The extracted DataFrames should:
- Use line item descriptions as index
- Use period end dates as column names
- Include metadata as DataFrame attributes
- Handle missing data appropriately
- Preserve hierarchical relationships where possible

### Integration Points

1. **With existing HTML parser** - Leverage Document class for table extraction
2. **With XBRL module** - Provide consistent DataFrame output format
3. **With Rich display** - Maintain current viewing capabilities
4. **With caching** - Cache extracted DataFrames for performance

This enhancement would make EdgarTools more accessible to users who want financial data without dealing with XBRL complexity, while maintaining the robustness of XBRL as the primary data source.
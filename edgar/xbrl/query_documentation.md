# XBRL Query Functionality

The XBRL class provides powerful query capabilities for exploring and analyzing financial facts within a single XBRL filing. This documentation covers how to use the query system to find specific facts, filter data, and perform analysis.

## Overview

XBRL query functionality is built around two main classes:
- `FactsView` - Provides access to raw XBRL facts from a single filing
- `FactQuery` - Enables complex filtering and analysis of those facts

## Basic Usage

### Accessing Facts

```python
from edgar import Company
from edgar.xbrl import XBRL

# Get an XBRL filing
company = Company("AAPL")
filing = company.latest("10-K")
xbrl = XBRL.from_filing(filing)

# Access the facts view
facts = xbrl.facts
print(f"Total facts: {len(facts)}")

# Get all facts as a list
all_facts = facts.get_facts()
```

### Simple Queries

```python
# Start a query
query = xbrl.query()

# Execute to get all facts
results = query.execute()

# Convert to DataFrame for analysis
df = query.to_dataframe()
print(df.head())
```

## Filtering Facts

### By Concept

```python
# Find revenue-related facts
revenue_query = xbrl.query().by_concept("us-gaap:Revenues")
revenue_facts = revenue_query.execute()

# Multiple concepts
concepts = ["us-gaap:Revenues", "us-gaap:NetIncomeLoss"]
multi_query = xbrl.query().by_concept(concepts)
```

### By Label

```python
# Search by label text
revenue_query = xbrl.query().by_label("Revenue")
results = revenue_query.execute()

# Case-insensitive partial matching
sales_query = xbrl.query().by_label("sales", exact=False)
```

### By Value

```python
# Facts with values above $1 billion
large_values = xbrl.query().by_value(lambda x: x > 1_000_000_000)

# Facts within a range
range_query = xbrl.query().by_value(lambda x: 100_000 <= x <= 1_000_000)
```

### By Period

```python
# Facts for a specific period
period_query = xbrl.query().by_period("2023-12-31")

# Duration periods
duration_query = xbrl.query().by_period("2023-01-01", "2023-12-31")
```

### By Statement Type

```python
# Facts from specific statements
income_facts = xbrl.query().by_statement("IncomeStatement")
balance_facts = xbrl.query().by_statement("BalanceSheet")
```

## Method Chaining

Combine multiple filters using method chaining:

```python
# Complex query with multiple filters
complex_query = (xbrl.query()
                 .by_statement("IncomeStatement")
                 .by_label("Revenue")
                 .by_value(lambda x: x > 1_000_000)
                 .sort_by('value', ascending=False)
                 .limit(10))

results = complex_query.execute()
```

## Data Transformations

### Sorting

```python
# Sort by value (descending)
sorted_query = xbrl.query().sort_by('value', ascending=False)

# Sort by concept name
concept_sorted = xbrl.query().sort_by('concept')
```

### Limiting Results

```python
# Get top 10 results
top_10 = xbrl.query().limit(10)

# Pagination
page_1 = xbrl.query().limit(20)
page_2 = xbrl.query().offset(20).limit(20)
```

### Transforming Values

```python
# Convert to millions
millions_query = xbrl.query().transform(lambda x: x / 1_000_000)

# Apply custom transformation
def to_thousands(value):
    return round(value / 1000, 2) if value else None

thousands_query = xbrl.query().transform(to_thousands)
```

## Working with Results

### DataFrame Output

```python
# Get specific columns
df = query.to_dataframe('concept', 'label', 'value', 'period_end')

# All available columns
full_df = query.to_dataframe()

# Column information
print("Available columns:", df.columns.tolist())
```

### Fact Structure

Each fact contains the following key information:

```python
fact = results[0]
print(f"Concept: {fact['concept']}")
print(f"Label: {fact['label']}")
print(f"Value: {fact['value']}")
print(f"Period: {fact['period_end']}")
print(f"Units: {fact['units']}")
print(f"Decimals: {fact['decimals']}")
```

## Advanced Filtering

### Dimensions

```python
# Facts with specific dimensions
dimensional_query = xbrl.query().by_dimension("ProductOrServiceAxis", "ProductMember")

# Facts with any value for a dimension
any_product_dim = xbrl.query().by_dimension("ProductOrServiceAxis")

# Facts with NO dimensions (undimensioned facts)
undimensioned_facts = xbrl.query().by_dimension(None)

# Multiple dimensions
multi_dim = xbrl.query().by_dimensions({
    "ProductOrServiceAxis": "ProductMember",
    "GeographyAxis": "USMember"
})
```

### Context Information

```python
# Filter by entity
entity_query = xbrl.query().by_entity("0000320193")  # Apple's CIK

# Instant vs duration facts
instant_facts = xbrl.query().by_period_type("instant")
duration_facts = xbrl.query().by_period_type("duration")
```

### Numeric vs Text Facts

```python
# Only numeric facts
numeric_query = xbrl.query().numeric_only()

# Only text facts  
text_query = xbrl.query().text_only()

# Facts with specific data types
string_facts = xbrl.query().by_data_type("string")
```

## Aggregation and Analysis

### Grouping

```python
# Group by concept
grouped = xbrl.query().group_by('concept').sum('value')

# Group by multiple fields
multi_grouped = xbrl.query().group_by(['concept', 'period_end']).mean('value')
```

### Statistical Functions

```python
# Summary statistics
stats = xbrl.query().by_statement("IncomeStatement").stats()
print(f"Mean value: {stats['value']['mean']}")
print(f"Total count: {stats['value']['count']}")

# Custom aggregations
total_revenue = (xbrl.query()
                 .by_label("Revenue")
                 .aggregate('value', 'sum'))
```

## Error Handling and Validation

```python
try:
    results = xbrl.query().by_concept("invalid-concept").execute()
except ValueError as e:
    print(f"Query error: {e}")

# Check if query has results
query = xbrl.query().by_label("NonexistentLabel")
if query.count() == 0:
    print("No results found")
else:
    results = query.execute()
```

## Performance Tips

1. **Use specific filters**: Filter early to reduce data processing
2. **Limit results**: Use `.limit()` for large datasets
3. **Cache queries**: Store frequently used queries
4. **Select columns**: Use `to_dataframe()` with specific columns

```python
# Efficient query pattern
efficient_query = (xbrl.query()
                   .by_statement("IncomeStatement")  # Filter first
                   .by_value(lambda x: x > 0)        # Remove zeros
                   .limit(100)                       # Limit results
                   .to_dataframe('concept', 'value')) # Select columns
```

## Examples

### Finding Revenue Information

```python
# All revenue-related facts
revenue_facts = (xbrl.query()
                 .by_label("revenue", exact=False)
                 .sort_by('value', ascending=False)
                 .execute())

for fact in revenue_facts:
    print(f"{fact['label']}: ${fact['value']:,}")
```

### Comparing Quarterly Data

```python
# Get quarterly revenue data
quarterly_revenue = (xbrl.query()
                     .by_concept("us-gaap:Revenues")
                     .by_period_type("duration")
                     .sort_by('period_end')
                     .to_dataframe('period_end', 'value'))

print(quarterly_revenue)
```

### Balance Sheet Analysis

```python
# Major balance sheet items
balance_items = (xbrl.query()
                 .by_statement("BalanceSheet")
                 .by_value(lambda x: x > 1_000_000_000)  # > $1B
                 .sort_by('value', ascending=False)
                 .to_dataframe('label', 'value'))

print("Major Balance Sheet Items (> $1B):")
print(balance_items)
```

This query system provides a flexible and powerful way to explore XBRL data, enabling detailed financial analysis and data extraction from individual filings.
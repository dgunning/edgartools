# XBRLS Query Functionality

The XBRLS class provides advanced query capabilities for exploring and analyzing stitched financial data across multiple XBRL filings. This enables powerful multi-period analysis with standardized, comparable data.

## Overview

XBRLS query functionality is built around two main classes:
- `StitchedFactsView` - Provides access to standardized facts extracted from stitched statements
- `StitchedFactQuery` - Enables complex filtering and multi-period analysis of stitched data

The key difference from single XBRL queries is that XBRLS operates on **post-processed, standardized data** that has been stitched together across multiple periods, ensuring consistent concept mapping and comparability.

## Basic Usage

### Accessing Stitched Facts

```python
from edgar import Company
from edgar.xbrl.stitching import XBRLS

# Get multiple filings for multi-period analysis
company = Company("AAPL")
filings = company.latest("10-K", 3)  # Last 3 annual filings
xbrls = XBRLS.from_filings(filings)

# Access the stitched facts view
facts = xbrls.facts
print(f"Total stitched facts: {len(facts)}")

# Get all facts from stitched statements
all_facts = facts.get_facts()
```

### Simple Queries

```python
# Start a query with default parameters
query = xbrls.query()

# Execute to get all stitched facts
results = query.execute()

# Convert to DataFrame for analysis
df = query.to_dataframe()
print(f"Shape: {df.shape}")
print(df.head())
```

### Query Parameters

```python
# Customize query parameters
query = xbrls.query(
    max_periods=5,                           # Include up to 5 periods
    standardize=True,                        # Use standardized labels
    statement_types=['IncomeStatement']      # Only income statement facts
)
```

## Multi-Period Filtering

### By Standardized Concept

The `by_standardized_concept()` method searches both standardized labels and original concepts:

```python
# Find revenue across all periods
revenue_query = xbrls.query().by_standardized_concept("Revenue")
revenue_facts = revenue_query.execute()

# Display revenue trend
for fact in revenue_facts:
    print(f"{fact['period_end']}: ${fact['numeric_value']:,}")
```

### By Original Labels

Search using the original company-specific labels before standardization:

```python
# Find facts using original company terminology
original_query = xbrls.query().by_original_label("Net sales")
results = original_query.execute()

# Pattern matching with regex
pattern_query = xbrls.query().by_original_label(r".*revenue.*", exact=False)
```

### Cross-Period Analysis

Filter to concepts that appear across multiple periods:

```python
# Concepts that appear in at least 3 periods
consistent_data = xbrls.query().across_periods(min_periods=3)
results = consistent_data.execute()

# Find concepts with complete data across all periods
complete_data = xbrls.query().complete_periods_only()
```

## Advanced Multi-Period Features

### Trend Analysis

Set up queries specifically for trend analysis:

```python
# Prepare revenue data for trend analysis
trend_query = xbrls.query().trend_analysis("Revenue")
trend_results = trend_query.execute()

# Get trend-optimized DataFrame
trend_df = trend_query.to_trend_dataframe()
print(trend_df)
```

The trend DataFrame pivots data with concepts as rows and periods as columns:

```
                           2023-09-30  2022-09-24  2021-09-25
label        concept                                         
Revenue      us-gaap:Rev    383285000   394328000   365817000
```

### Statement Type Filtering

Focus on specific types of financial statements:

```python
# Only income statement facts
income_query = xbrls.query(statement_types=['IncomeStatement'])

# Multiple statement types
multi_statements = xbrls.query(statement_types=[
    'IncomeStatement', 
    'BalanceSheet'
])

# All available statement types (default)
all_statements = xbrls.query(statement_types=[
    'IncomeStatement',
    'BalanceSheet', 
    'CashFlowStatement',
    'StatementOfEquity',
    'ComprehensiveIncome'
])
```

## Method Chaining for Complex Queries

Combine multiple filters for sophisticated analysis:

```python
# Complex multi-period revenue analysis
complex_query = (xbrls.query()
                 .by_standardized_concept("Revenue")
                 .across_periods(min_periods=2)
                 .sort_by('period_end')
                 .limit(10))

results = complex_query.execute()
```

### Comprehensive Analysis Example

```python
# Find major line items that are consistent across periods
major_items = (xbrls.query()
               .by_value(lambda x: x > 1_000_000_000)  # > $1B
               .across_periods(min_periods=3)          # In at least 3 periods
               .sort_by('period_end')                   # Sort by time
               .to_dataframe('label', 'value', 'period_end'))

print("Major consistent line items:")
print(major_items)
```

## Working with Stitched Data

### Understanding Stitched Facts

Each stitched fact contains enhanced information compared to raw XBRL facts:

```python
fact = results[0]
print(f"Standardized Label: {fact['label']}")
print(f"Original Label: {fact['original_label']}")
print(f"Concept: {fact['concept']}")
print(f"Value: {fact['value']}")
print(f"Numeric Value: {fact['numeric_value']}")
print(f"Period: {fact['period_end']}")
print(f"Statement Type: {fact['statement_type']}")
print(f"Standardized: {fact['standardized']}")
print(f"Filing Count: {fact['filing_count']}")
```

### Standardized vs Original Labels

```python
# Compare standardized and original labels
comparison_df = query.to_dataframe('label', 'original_label', 'value')
print(comparison_df[comparison_df['label'] != comparison_df['original_label']])
```

## Data Analysis Examples

### Revenue Trend Analysis

```python
# Comprehensive revenue analysis
revenue_analysis = (xbrls.query()
                    .trend_analysis("Revenue")
                    .to_trend_dataframe())

print("Revenue Trend Analysis:")
print(revenue_analysis)

# Calculate growth rates
if len(revenue_analysis.columns) > 1:
    latest_col = revenue_analysis.columns[0]
    previous_col = revenue_analysis.columns[1]
    growth_rate = ((revenue_analysis[latest_col] / revenue_analysis[previous_col]) - 1) * 100
    print(f"Revenue growth rate: {growth_rate.iloc[0]:.1f}%")
```

### Cross-Statement Analysis

```python
# Compare assets and revenue across periods
assets_revenue = (xbrls.query()
                  .by_standardized_concept("Assets")
                  .across_periods(min_periods=2)
                  .to_dataframe('label', 'numeric_value', 'period_end'))

print("Assets across periods:")
print(assets_revenue)
```

### Consistency Check

```python
# Find concepts that appear in all periods
consistent_concepts = (xbrls.query()
                       .complete_periods_only()
                       .to_dataframe('label', 'concept'))

unique_concepts = consistent_concepts['label'].nunique()
print(f"Concepts appearing in all periods: {unique_concepts}")
```

## Fiscal Period Analysis

```python
# Filter by fiscal period if available
fy_data = xbrls.query().by_fiscal_period("FY")
q4_data = xbrls.query().by_fiscal_period("Q4")

# Note: Fiscal period data depends on entity_info availability
```

## Performance and Caching

The XBRLS query system includes intelligent caching:

```python
# First call processes and caches data
facts1 = xbrls.facts.get_facts(max_periods=3)

# Second call with same parameters uses cache
facts2 = xbrls.facts.get_facts(max_periods=3)
assert facts1 is facts2  # Same object reference

# Different parameters bypass cache
facts3 = xbrls.facts.get_facts(max_periods=5)
```

## Error Handling

```python
try:
    # Query with invalid statement type
    results = xbrls.query(statement_types=['InvalidStatement']).execute()
except Exception as e:
    print(f"Query failed: {e}")

# Check for empty results
query = xbrls.query().by_standardized_concept("NonexistentConcept")
results = query.execute()
if not results:
    print("No matching facts found")
```

## Integration with Statement Rendering

Combine queries with statement rendering for comprehensive analysis:

```python
# Render stitched income statement
income_statement = xbrls.render_statement("IncomeStatement")
print(income_statement)

# Query specific facts from the same data
revenue_facts = (xbrls.query(statement_types=['IncomeStatement'])
                 .by_standardized_concept("Revenue")
                 .execute())

print(f"Revenue facts found: {len(revenue_facts)}")
```

## Comparison with Single XBRL Queries

| Feature | XBRL Query | XBRLS Query |
|---------|------------|-------------|
| Data Source | Raw XBRL facts | Stitched, standardized facts |
| Periods | Single filing | Multiple periods |
| Concept Labels | Original only | Standardized + original |
| Consistency | Variable | Standardized across periods |
| Trend Analysis | Limited | Built-in support |
| Cross-Period Filtering | Not available | Available |

## Best Practices

1. **Use appropriate max_periods**: Balance between completeness and performance
2. **Filter by statement type**: Reduce data volume for focused analysis
3. **Leverage standardization**: Use `by_standardized_concept()` for consistent results
4. **Check for cross-period consistency**: Use `across_periods()` for reliable trends
5. **Combine with rendering**: Use both queries and statement rendering for comprehensive analysis

```python
# Recommended pattern for trend analysis
def analyze_concept_trend(xbrls, concept_name, min_periods=2):
    """Analyze trend for a specific concept across periods."""
    query = (xbrls.query()
             .trend_analysis(concept_name)
             .across_periods(min_periods=min_periods))
    
    # Get both detailed facts and trend DataFrame
    facts = query.execute()
    trend_df = query.to_trend_dataframe()
    
    return {
        'facts': facts,
        'trend_dataframe': trend_df,
        'period_count': len(set(f['period_end'] for f in facts))
    }

# Usage
revenue_trend = analyze_concept_trend(xbrls, "Revenue", min_periods=3)
print(f"Revenue data spans {revenue_trend['period_count']} periods")
print(revenue_trend['trend_dataframe'])
```

This enhanced query system enables sophisticated multi-period financial analysis with consistent, standardized data across multiple XBRL filings.
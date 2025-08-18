# Company Subsets

The `edgar.reference.company_subsets` module provides powerful and flexible tools for creating subsets of companies from SEC reference data. This is especially useful for research, analysis, educational purposes, and machine learning tasks where you need specific groups of companies.

## Key Features

- **Exchange-based selection**: Filter by NYSE, NASDAQ, OTC, CBOE
- **Popularity-based selection**: Get popular stocks, mega-cap companies, etc.
- **Sampling capabilities**: Random sampling, stratified sampling, top N selection
- **Filtering and combination utilities**: Include/exclude specific companies, combine sets
- **Fluent interface**: Chain operations for readable, flexible subset creation
- **Consistent output**: All functions return standardized DataFrames with `['cik', 'ticker', 'name', 'exchange']` columns

## Quick Start

```python
from edgar.reference.company_subsets import (
    CompanySubset, 
    get_companies_by_exchanges,
    get_popular_companies,
    get_random_sample
)

# Simple exchange-based selection
nyse_companies = get_companies_by_exchanges('NYSE')
print(f"Found {len(nyse_companies)} NYSE companies")

# Get popular companies
popular = get_popular_companies()
print(f"Found {len(popular)} popular companies")

# Random sampling
random_100 = get_random_sample(n=100, random_state=42)
print(f"Sampled {len(random_100)} random companies")
```

## Fluent Interface with CompanySubset

The `CompanySubset` class provides a powerful fluent interface for building complex company selections:

```python
from edgar.reference.company_subsets import CompanySubset, PopularityTier

# Complex selection with method chaining
companies = (CompanySubset()
             .from_exchange(['NYSE', 'Nasdaq'])        # Major exchanges only
             .exclude_tickers(['JPM', 'GS', 'C'])      # Exclude some financials
             .sample(50, random_state=42)              # Take random sample
             .get())                                   # Get the DataFrame

print(f"Selected {len(companies)} companies")
print(companies.head())

# Popular tech companies
tech_subset = (CompanySubset()
               .from_popular(PopularityTier.POPULAR)   # Popular companies
               .filter_by(lambda df: df['name'].str.contains('tech|software|computer', case=False))
               .top(20, by='ticker')                   # Top 20 alphabetically
               .get())
```

## Core Functions

### Exchange-Based Selection

Filter companies by stock exchange:

```python
from edgar.reference.company_subsets import get_companies_by_exchanges

# Single exchange
nyse_companies = get_companies_by_exchanges('NYSE')
nasdaq_companies = get_companies_by_exchanges('Nasdaq')

# Multiple exchanges
major_exchanges = get_companies_by_exchanges(['NYSE', 'Nasdaq'])
all_exchanges = get_companies_by_exchanges(['NYSE', 'Nasdaq', 'OTC', 'CBOE'])

print(f"NYSE: {len(nyse_companies)} companies")
print(f"NASDAQ: {len(nasdaq_companies)} companies") 
print(f"Major exchanges: {len(major_exchanges)} companies")
```

### Popular Companies

Access curated lists of popular and well-known companies:

```python
from edgar.reference.company_subsets import get_popular_companies, PopularityTier

# All popular companies
all_popular = get_popular_companies()

# By popularity tier
mega_cap = get_popular_companies(PopularityTier.MEGA_CAP)      # Top 10
popular = get_popular_companies(PopularityTier.POPULAR)        # Top 50
mainstream = get_popular_companies(PopularityTier.MAINSTREAM)  # Top 100
emerging = get_popular_companies(PopularityTier.EMERGING)      # All available

print(f"Mega cap: {len(mega_cap)} companies")
print(f"Popular: {len(popular)} companies")
print(f"All popular: {len(all_popular)} companies")
```

### Sampling Methods

Create representative samples from larger datasets:

```python
from edgar.reference.company_subsets import (
    get_random_sample, 
    get_stratified_sample,
    get_top_companies_by_metric
)

# Random sampling
random_sample = get_random_sample(n=200, random_state=42)

# Stratified sampling (maintains exchange proportions)
stratified_sample = get_stratified_sample(
    n=100, 
    stratify_by='exchange', 
    random_state=42
)

# Top companies by name (alphabetical)
top_alphabetical = get_top_companies_by_metric(
    n=50, 
    metric='name', 
    ascending=True
)

# Sample from a specific subset
nyse_random = get_random_sample(
    get_companies_by_exchanges('NYSE'), 
    n=100, 
    random_state=42
)
```

## Filtering and Combining

### Include/Exclude Specific Companies

```python
from edgar.reference.company_subsets import filter_companies, exclude_companies

all_companies = get_all_companies()

# Include specific tickers (FAANG companies)
faang = filter_companies(
    all_companies,
    ticker_list=['META', 'AAPL', 'AMZN', 'NFLX', 'GOOGL']
)

# Include companies with names containing specific text
tech_companies = filter_companies(
    all_companies,
    name_contains='Technology'
)

# Include specific CIKs
specific_companies = filter_companies(
    all_companies,
    cik_list=[320193, 1018724, 1652044]  # AAPL, AMZN, GOOGL
)

# Exclude financial companies (simplified example)
non_financial = exclude_companies(
    all_companies,
    ticker_list=['JPM', 'GS', 'C', 'BAC', 'WFC']
)

# Exclude companies with 'Corp' in name  
non_corp = exclude_companies(
    all_companies,
    name_contains='Corp'
)
```

### Custom Filtering

Apply custom filtering logic:

```python
from edgar.reference.company_subsets import filter_companies

# Custom filter function
def large_company_filter(df):
    """Filter to companies with longer names (proxy for larger companies)."""
    return df[df['name'].str.len() > 20]

# Apply custom filter
large_companies = filter_companies(
    get_companies_by_exchanges('NYSE'),
    custom_filter=large_company_filter
)

# Using lambda for simple filters
short_tickers = filter_companies(
    get_popular_companies(),
    custom_filter=lambda df: df[df['ticker'].str.len() <= 4]
)
```

### Combining and Intersecting Sets

```python
from edgar.reference.company_subsets import combine_company_sets, intersect_company_sets

# Get different company sets
nyse_companies = get_companies_by_exchanges('NYSE')
popular_companies = get_popular_companies()
tech_companies = filter_companies(get_all_companies(), name_contains='Tech')

# Union: Combine multiple sets (removes duplicates)
combined = combine_company_sets([nyse_companies, popular_companies, tech_companies])

# Intersection: Find companies present in all sets
nyse_popular = intersect_company_sets([nyse_companies, popular_companies])
popular_tech = intersect_company_sets([popular_companies, tech_companies])

print(f"Combined: {len(combined)} companies")
print(f"NYSE + Popular intersection: {len(nyse_popular)} companies")
print(f"Popular + Tech intersection: {len(popular_tech)} companies")
```

## Convenience Functions

Pre-defined functions for common company groupings:

```python
from edgar.reference.company_subsets import (
    get_faang_companies,
    get_tech_giants, 
    get_dow_jones_sample
)

# FAANG companies (Meta, Apple, Amazon, Netflix, Google)
faang = get_faang_companies()

# Major tech companies
tech_giants = get_tech_giants()

# Dow Jones Industrial Average sample
dow_sample = get_dow_jones_sample()

print(f"FAANG: {len(faang)} companies")
print(f"Tech Giants: {len(tech_giants)} companies") 
print(f"Dow Sample: {len(dow_sample)} companies")

# Display the companies
print("\nFAANG Companies:")
for _, company in faang.iterrows():
    print(f"  {company['ticker']}: {company['name']}")
```

## Advanced Examples

### Research Dataset Creation

Create a balanced research dataset:

```python
from edgar.reference.company_subsets import CompanySubset, PopularityTier

# Create a research dataset with companies from different tiers
research_dataset = []

# Get 20 mega-cap companies
mega_cap = (CompanySubset()
           .from_popular(PopularityTier.MEGA_CAP)
           .sample(20, random_state=42)
           .get())

# Get 30 popular mid-tier companies  
mid_tier = (CompanySubset()
           .from_popular(PopularityTier.POPULAR)
           .exclude_tickers(mega_cap['ticker'].tolist())  # Don't overlap
           .sample(30, random_state=42)
           .get())

# Get 50 random companies from major exchanges
random_companies = (CompanySubset()
                    .from_exchange(['NYSE', 'Nasdaq'])
                    .exclude_tickers(mega_cap['ticker'].tolist() + mid_tier['ticker'].tolist())
                    .sample(50, random_state=42)
                    .get())

# Combine all for final research set
research_companies = combine_company_sets([mega_cap, mid_tier, random_companies])
print(f"Research dataset: {len(research_companies)} companies")

# Analyze composition
exchange_dist = research_companies['exchange'].value_counts()
print("\nExchange distribution:")
print(exchange_dist)
```

### Sector-Based Analysis

Create industry-focused subsets:

```python
# Create sector-based subsets (simplified approach using name patterns)
sectors = {
    'technology': ['tech', 'software', 'computer', 'digital'],
    'financial': ['bank', 'financial', 'insurance', 'capital'],
    'healthcare': ['health', 'medical', 'pharma', 'bio'],
    'energy': ['energy', 'oil', 'gas', 'power'],
    'retail': ['retail', 'store', 'market', 'shop']
}

sector_companies = {}
all_companies = get_companies_by_exchanges(['NYSE', 'Nasdaq'])

for sector, keywords in sectors.items():
    # Create pattern for all keywords
    pattern = '|'.join(keywords)
    
    sector_subset = filter_companies(
        all_companies,
        custom_filter=lambda df, p=pattern: df[df['name'].str.contains(p, case=False)]
    )
    
    sector_companies[sector] = sector_subset
    print(f"{sector.title()}: {len(sector_subset)} companies")

# Get top 10 from each sector for analysis
analysis_set = []
for sector, companies in sector_companies.items():
    top_10 = get_top_companies_by_metric(companies, n=10, metric='ticker')
    analysis_set.append(top_10)

final_analysis_set = combine_company_sets(analysis_set)
print(f"\nFinal analysis set: {len(final_analysis_set)} companies across sectors")
```

### Machine Learning Dataset Preparation

Prepare balanced datasets for ML training:

```python
from edgar.reference.company_subsets import get_stratified_sample

# Create training/test split with stratification
all_popular = get_popular_companies()

# Training set (70% of data, stratified by exchange)
training_companies = get_stratified_sample(
    all_popular,
    n=int(len(all_popular) * 0.7),
    stratify_by='exchange',
    random_state=42
)

# Test set (remaining companies)  
test_companies = all_popular[~all_popular['cik'].isin(training_companies['cik'])]

print(f"Training set: {len(training_companies)} companies")
print(f"Test set: {len(test_companies)} companies")

# Verify stratification worked
print("\nTraining exchange distribution:")
print(training_companies['exchange'].value_counts(normalize=True))

print("\nTest exchange distribution:")  
print(test_companies['exchange'].value_counts(normalize=True))
```

## Data Structure

All functions return a standardized pandas DataFrame with these columns:

- **`cik`** (int): SEC Central Index Key - unique company identifier
- **`ticker`** (str): Stock ticker symbol (e.g., 'AAPL', 'MSFT')  
- **`name`** (str): Official company name
- **`exchange`** (str): Stock exchange ('NYSE', 'Nasdaq', 'OTC', 'CBOE', etc.)

```python
# Example output structure
companies = get_random_sample(5)
print(companies)

#        cik ticker                     name exchange
# 0   320193   AAPL             Apple Inc.   Nasdaq
# 1  1018724   AMZN        Amazon.com, Inc.   Nasdaq  
# 2  1652044  GOOGL          Alphabet Inc.   Nasdaq
# 3   789019   MSFT  Microsoft Corporation   Nasdaq
# 4  1326801   META     Meta Platforms, Inc   Nasdaq
```

## Error Handling

The module includes robust error handling and logging:

```python
# Functions gracefully handle errors and return empty DataFrames
empty_result = get_companies_by_exchanges('INVALID_EXCHANGE')
print(f"Invalid exchange result: {len(empty_result)} companies")

# Check for empty results
companies = get_random_sample(n=10)
if companies.empty:
    print("No companies found")
else:
    print(f"Found {len(companies)} companies")

# All functions include logging for debugging
import logging
logging.basicConfig(level=logging.DEBUG)

# Now function calls will show debug information
companies = get_popular_companies()
```

## Performance Considerations

- **Caching**: `get_all_companies()` uses LRU cache for performance
- **Lazy evaluation**: CompanySubset operations are efficient and don't duplicate data unnecessarily
- **Memory efficient**: Functions work with DataFrame views when possible
- **Batch operations**: Use combine/intersect functions instead of loops for better performance

```python
# Efficient: Use batch operations
company_sets = [
    get_companies_by_exchanges('NYSE'),
    get_companies_by_exchanges('Nasdaq'),
    get_popular_companies()
]
combined = combine_company_sets(company_sets)

# Less efficient: Multiple individual operations in loops
# combined = pd.DataFrame()
# for exchange in ['NYSE', 'Nasdaq']:
#     exchange_companies = get_companies_by_exchanges(exchange)
#     combined = pd.concat([combined, exchange_companies])  # Avoid this pattern
```

## Integration with Edgar Tools

Company subsets integrate seamlessly with other Edgar tools:

```python
from edgar import Company
from edgar.reference.company_subsets import get_tech_giants

# Get tech companies and analyze their latest filings
tech_companies = get_tech_giants()

for _, company_info in tech_companies.head(5).iterrows():
    try:
        company = Company(company_info['ticker'])
        latest_filing = company.get_filings(form='10-K').latest()
        print(f"{company_info['ticker']}: Latest 10-K filed {latest_filing.filing_date}")
    except:
        print(f"{company_info['ticker']}: No recent 10-K found")
```

## Best Practices

1. **Use appropriate sample sizes**: Don't sample more companies than you need for analysis
2. **Set random seeds**: Use `random_state` parameter for reproducible results  
3. **Handle empty results**: Always check if returned DataFrames are empty
4. **Combine operations efficiently**: Use method chaining with CompanySubset for readable code
5. **Cache results**: Store company subsets if you'll reuse them multiple times
6. **Validate data**: Check that your filters return expected results

```python
# Good: Reproducible and efficient
companies = (CompanySubset()
            .from_exchange('NYSE') 
            .sample(100, random_state=42)
            .get())

# Store for reuse
cached_companies = companies.copy()

# Good: Check for empty results
if not companies.empty:
    print(f"Analysis ready with {len(companies)} companies")
else:
    print("No companies found matching criteria")
```

This module provides a comprehensive toolkit for creating company subsets tailored to your specific research, analysis, or educational needs. The combination of simple functions and the powerful fluent interface makes it easy to create both simple selections and complex, multi-criteria company datasets.
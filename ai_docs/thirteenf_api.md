# ThirteenF API

## Overview
The ThirteenF API provides access to institutional investment manager holdings reported in Form 13F filings.

## Key Classes
- `ThirteenF` - Represents a 13F-HR filing with portfolio holdings

## Core Functionality
- Access fund holdings from 13F filings
- Analyze portfolio composition
- Track position changes over time
- Calculate portfolio statistics

## Common Patterns

### Accessing 13F Data
```python
# From a filing
filing = get_filings(form="13F-HR").latest()
thirteenf = filing.obj()

# From a fund company
fund_company = find_fund("0000102909")  # Vanguard
filings = fund_company.get_filings(form="13F-HR")
latest_filing = filings.latest()
thirteenf = latest_filing.obj()
```

### Working with Holdings
```python
# Get holdings as DataFrame
holdings_df = thirteenf.infotable  # 'infotable' is a pandas DataFrame

# Sort by value
top_holdings = holdings_df.sort_values(by="Value", ascending=False)

# Basic statistics
total_value = holdings_df["Value"].sum()
distinct_securities = len(holdings_df)
```

### Analyzing Portfolio
```python
# Top 10 holdings
top_10 = holdings_df.head(10)

# You can use all standard pandas DataFrame operations on 'infotable', such as filtering, grouping, and aggregation.
# For example, to calculate portfolio concentration or sector breakdowns, use pandas methods as needed.
top_10_concentration = top_10["value"].sum() / holdings_df["value"].sum()

# Group by security type
by_type = holdings_df.groupby("security_type").sum()
```

### Comparing Holdings Over Time
```python
# Get two consecutive quarters
recent_filings = fund_company.get_filings(form="13F-HR").latest(2)
current = recent_filings[0].obj().get_holdings()
previous = recent_filings[1].obj().get_holdings()

# Set index for comparison
current.set_index("cusip", inplace=True)
previous.set_index("cusip", inplace=True)

# Find new positions
new_positions = current.index.difference(previous.index)

# Find exited positions
exited_positions = previous.index.difference(current.index)

# Find changed positions
changed = {}
for cusip in current.index.intersection(previous.index):
    current_shares = current.loc[cusip, "shares"]
    previous_shares = previous.loc[cusip, "shares"]
    if current_shares != previous_shares:
        changed[cusip] = (current_shares - previous_shares) / previous_shares  # % change
```

## Relevant User Journeys
- Fund Holdings Analysis Journey
- Investment Fund Research Journey
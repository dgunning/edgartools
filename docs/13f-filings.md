# 13F Holdings Reports

13F filings are quarterly reports filed by institutional investment managers that disclose their equity holdings. These reports provide valuable insights into how large institutions allocate their capital and are essential for investment research, portfolio tracking, and market analysis.

## What are 13F Filings?

**13F-HR (Holdings Report)** filings are required for institutional investment managers with over $100 million in qualifying assets under management. These reports must be filed within 45 days of the end of each quarter and disclose all equity holdings as of the quarter's end.

### Types of 13F Filings

EdgarTools supports all 13F filing types:

| Form | Description | Has Holdings Data |
|------|-------------|-------------------|
| **13F-HR** | Holdings Report | ✅ Yes |
| **13F-HR/A** | Amended Holdings Report | ✅ Yes |
| **13F-NT** | Notice Report (no holdings to report) | ❌ No |
| **13F-NT/A** | Amended Notice Report | ❌ No |

## Getting 13F Filings

### Search All 13F Filings

Find 13F filings across all institutional managers:

```python
from edgar import get_filings

# Get recent 13F holdings reports
holdings_reports = get_filings(form="13F-HR")
print(holdings_reports)
```

### Get 13F Filings for Specific Fund

Search for a specific institutional manager by company name:

```python
from edgar import Company

# Berkshire Hathaway's 13F filings
berkshire = Company("BRK.A")
filings = berkshire.get_filings(form="13F-HR")
print(filings)
```

### Filter by Date Range

Focus on specific time periods:

```python
# Get Q3 2024 13F filings
q3_filings = get_filings(
    form="13F-HR",
    filing_date="2024-11-01:2024-11-15"  # Typical Q3 filing window
)
```

## Working with ThirteenF Objects

Convert a 13F filing to a structured data object for analysis:

```python
# Get the latest 13F filing
filing = holdings_reports.latest()
thirteenf = filing.obj()  # Convert to ThirteenF object

print(thirteenf)
```

### Basic Information

Access key details about the 13F filing:

```python
# Fund/Manager information
fund_name = thirteenf.investment_manager.name
fund_address = thirteenf.investment_manager.address

# Filing details
report_period = thirteenf.report_period      # "2024-09-30"
filing_date = thirteenf.filing_date          # "2024-11-14"
form_type = thirteenf.form                   # "13F-HR"

# Portfolio summary
total_value = thirteenf.total_value          # Total portfolio value
holdings_count = thirteenf.total_holdings    # Number of holdings
signer = thirteenf.signer                    # Person who signed the filing

print(f"{fund_name} reported ${total_value:,.0f} across {holdings_count} holdings")
```

### Checking for Holdings Data

Not all 13F filings contain holdings data (NT forms are notice reports):

```python
if thirteenf.has_infotable():
    print(f"Filing contains {len(thirteenf.infotable)} holdings")
    holdings = thirteenf.infotable
else:
    print("This is a notice filing with no holdings data")
```

## Accessing Holdings Data

The core value of 13F filings is the detailed holdings information:

### Get All Holdings

```python
# Holdings as pandas DataFrame
holdings = thirteenf.infotable
print(f"Found {len(holdings)} holdings")

# Display top holdings by value
top_10 = holdings.sort_values('Value', ascending=False).head(10)
print(top_10[['Issuer', 'Ticker', 'Value', 'Shares']])
```

### Holdings Data Structure

Each holding contains detailed information:

```python
for _, holding in holdings.head(5).iterrows():
    print(f"Company: {holding['Issuer']}")
    print(f"Ticker: {holding['Ticker']}")
    print(f"CUSIP: {holding['Cusip']}")
    print(f"Value: ${holding['Value']:,.0f}")
    print(f"Shares: {holding['Shares']:,.0f}")
    print(f"Security Type: {holding['Type']}")
    print(f"Put/Call: {holding['PutCall']}")
    print("---")
```

### Holdings DataFrame Columns

The holdings DataFrame includes these columns:

| Column | Description | Example |
|--------|-------------|---------|
| `Issuer` | Company name | "APPLE INC" |
| `Class` | Security class | "COM" |
| `Cusip` | CUSIP identifier | "037833100" |
| `Ticker` | Stock ticker symbol | "AAPL" |
| `Value` | Market value (thousands) | 1500000 |
| `Shares` | Number of shares | 1234567 |
| `Type` | Security type | "Shares" or "Principal" |
| `PutCall` | Options type | "Put", "Call", or "" |
| `SoleVoting` | Sole voting authority | 1234567 |
| `SharedVoting` | Shared voting authority | 0 |
| `NonVoting` | No voting authority | 0 |

## Common Use Cases

### 1. Portfolio Analysis

Analyze a fund's portfolio composition:

```python
# Portfolio concentration
total_portfolio = holdings['Value'].sum()
holdings['Weight'] = holdings['Value'] / total_portfolio * 100

# Top 10 holdings by weight
top_holdings = holdings.nlargest(10, 'Weight')
print("Top 10 Holdings:")
for _, holding in top_holdings.iterrows():
    print(f"{holding['Ticker']:>6}: {holding['Weight']:>5.1f}% (${holding['Value']:>10,.0f}K)")

# Sector analysis (if you have sector mapping)
print(f"\nPortfolio concentration: Top 10 = {top_holdings['Weight'].sum():.1f}%")
```

### 2. Position Tracking

Track specific positions across time:

```python
# Find Apple positions across multiple quarters
apple_positions = []

for filing in berkshire.get_filings(form="13F-HR").head(4):
    thirteenf = filing.obj()
    if thirteenf.has_infotable():
        apple_holding = thirteenf.infotable.query("Ticker == 'AAPL'")
        if not apple_holding.empty:
            position = {
                'date': thirteenf.report_period,
                'shares': apple_holding.iloc[0]['Shares'],
                'value': apple_holding.iloc[0]['Value']
            }
            apple_positions.append(position)

# Convert to DataFrame for analysis
import pandas as pd
apple_df = pd.DataFrame(apple_positions)
print("Apple position over time:")
print(apple_df)
```

### 3. New Positions & Changes

Identify new positions by comparing quarters:

```python
# Get current and previous quarter
current_13f = berkshire.get_filings(form="13F-HR").latest().obj()
previous_13f = current_13f.previous_holding_report()

if previous_13f:
    current_tickers = set(current_13f.infotable['Ticker'].dropna())
    previous_tickers = set(previous_13f.infotable['Ticker'].dropna())
    
    new_positions = current_tickers - previous_tickers
    closed_positions = previous_tickers - current_tickers
    
    print(f"New positions: {len(new_positions)}")
    for ticker in new_positions:
        if ticker:  # Skip NaN tickers
            print(f"  {ticker}")
    
    print(f"Closed positions: {len(closed_positions)}")
    for ticker in closed_positions:
        if ticker:
            print(f"  {ticker}")
```

### 4. Options Analysis

Analyze put and call option holdings:

```python
# Filter for options positions
options = holdings.query("PutCall in ['Put', 'Call']")

if not options.empty:
    puts = options.query("PutCall == 'Put'")
    calls = options.query("PutCall == 'Call'")
    
    print(f"Options positions: {len(options)}")
    print(f"  Puts: {len(puts)} (${puts['Value'].sum():,.0f}K)")
    print(f"  Calls: {len(calls)} (${calls['Value'].sum():,.0f}K)")
    
    # Top options positions
    print("\nTop Options Positions:")
    for _, option in options.nlargest(5, 'Value').iterrows():
        print(f"  {option['Ticker']} {option['PutCall']}: ${option['Value']:,.0f}K")
```

## Data Structure Overview

### ThirteenF Object Properties

| Property | Type | Description |
|----------|------|-------------|
| `form` | str | Filing form type ("13F-HR", "13F-NT", etc.) |
| `investment_manager` | FilingManager | Fund/manager information and address |
| `report_period` | str | Quarter end date ("2024-09-30") |
| `filing_date` | str | Date filed with SEC |
| `total_value` | Decimal | Total portfolio value (in thousands) |
| `total_holdings` | int | Number of holdings reported |
| `signer` | str | Name of person who signed the filing |
| `infotable` | DataFrame | Holdings data (if available) |

### FilingManager Object

```python
manager = thirteenf.investment_manager
print(f"Name: {manager.name}")
print(f"Address: {manager.address.street1}")
print(f"City: {manager.address.city}, {manager.address.state_or_country}")
```

### Previous Period Reports

Access historical filings from the same manager:

```python
# Get the previous quarter's filing
previous = thirteenf.previous_holding_report()

if previous:
    print(f"Previous report: {previous.report_period}")
    print(f"Previous holdings: {previous.total_holdings}")
else:
    print("No previous report available")
```

## Advanced Features

### Raw XML Access

Access the underlying XML data for custom parsing:

```python
# Primary document XML (cover page, summary, signature)
primary_xml = thirteenf.filing.xml()

# Holdings information table XML
if thirteenf.has_infotable():
    infotable_xml = thirteenf.infotable_xml
    infotable_html = thirteenf.infotable_html  # HTML version if available
```

### Related Filings

13F filings often have related filings (amendments, combined reports):

```python
# Get all related filings on the same filing date
related = thirteenf._related_filings
print(f"Related filings: {len(related)}")

for filing in related:
    print(f"  {filing.accession_no}: {filing.form}")
```

## Rich Display Output

EdgarTools provides beautiful formatted output for 13F data:

```python
# Display the complete 13F report
print(thirteenf)  # Rich formatted table with holdings

# Display just the holdings table
if thirteenf.has_infotable():
    print(thirteenf.infotable)  # Pandas DataFrame with rich formatting
```

The output includes:
- 📊 Summary table with key metrics
- 📈 Top holdings by value
- 🎯 Options positions (puts/calls)
- 💼 Portfolio statistics

## Limitations & Notes

### Current Limitations

- **Discovery**: Finding 13F filers by name requires knowing the exact company name or CIK. There's no built-in search for "all hedge funds" or "top asset managers"
- **Sector Classification**: Holdings don't include automatic sector/industry classification
- **Historical Comparisons**: Comparing positions across multiple periods requires manual analysis

### Performance Tips

- **Caching**: Large 13F files are cached automatically to improve performance
- **Filtering**: Use `.query()` on DataFrames for efficient filtering
- **Batch Processing**: Process multiple filings using list comprehensions

### Data Quality Notes

- **Ticker Symbols**: Not all holdings have ticker symbols (private companies, bonds)
- **CUSIP Mapping**: Ticker mapping is based on CUSIP identifiers which may not be current
- **Amendments**: Always check for amended filings (13F-HR/A) for the most accurate data

## Error Handling

Handle common issues gracefully:

```python
try:
    thirteenf = filing.obj()
    
    if thirteenf.has_infotable():
        holdings = thirteenf.infotable
        print(f"Successfully loaded {len(holdings)} holdings")
    else:
        print("Filing contains no holdings data (notice report)")
        
except Exception as e:
    print(f"Error parsing 13F filing: {e}")
    # Fall back to raw filing content
    content = filing.text
```

## Getting Help

- **📖 [API Reference](data-objects.md#investment-fund-holdings-13f)**: Complete method documentation
- **💬 [GitHub Discussions](https://github.com/dgunning/edgartools/discussions)**: Ask questions about 13F analysis
- **🐛 [Issues](https://github.com/dgunning/edgartools/issues)**: Report bugs or request 13F enhancements

---

**🎯 Pro Tip**: 13F filings are powerful for tracking institutional investment trends, but remember they're filed quarterly with a 45-day delay. For real-time analysis, combine with other data sources.
# Business Development Companies

Access and analyze Business Development Companies (BDCs) - specialized investment companies that invest in small and mid-sized private companies.

## What Are BDCs?

Business Development Companies are closed-end investment funds that:

- Invest in small and mid-sized private U.S. companies
- Provide financing (loans) and equity investments
- Must distribute 90%+ of taxable income as dividends
- File with the SEC under file numbers starting with "814-"

BDCs provide a unique window into private credit markets through their quarterly Schedule of Investments disclosures.

## Finding BDCs

### List All BDCs

Get the complete list of ~196 BDCs from the SEC BDC Report:

```python
from edgar.bdc import get_bdc_list

bdcs = get_bdc_list()
print(f"Found {len(bdcs)} BDCs")
```

**Output:**
```plaintext
Found 196 BDCs
```

### Get a Specific BDC

Find a BDC by ticker or CIK:

```python
from edgar.bdc import get_bdc_list

bdcs = get_bdc_list()

# By ticker
arcc = bdcs.get_by_ticker("ARCC")
print(arcc.name)  # ARES CAPITAL CORP

# By CIK
main = bdcs.get_by_cik(1396440)
print(main.name)  # MAIN STREET CAPITAL CORP
```

### Search for BDCs

Use fuzzy search to find BDCs by name or ticker:

```python
from edgar.bdc import find_bdc

# Search by name
results = find_bdc("Ares")
print(results[0].name)  # ARES CAPITAL CORP

# Search by ticker
results = find_bdc("MAIN")
print(results[0].name)  # MAIN STREET CAPITAL CORP
```

**Key points:**
- Search is case-insensitive
- Supports partial name matching
- Returns ranked results by relevance

### Filter BDCs

Filter by state or activity status:

```python
bdcs = get_bdc_list()

# Active BDCs only (filed within last 18 months)
active_bdcs = bdcs.filter(active=True)
print(f"Active BDCs: {len(active_bdcs)}")

# BDCs in New York
ny_bdcs = bdcs.filter(state='NY')
print(f"NY-based BDCs: {len(ny_bdcs)}")

# Combine filters
ny_active = bdcs.filter(state='NY', active=True)
```

### Check if a Company is a BDC

Verify whether a CIK belongs to a BDC:

```python
from edgar.bdc import is_bdc_cik

is_bdc_cik(1287750)  # True - ARCC is a BDC
is_bdc_cik(320193)   # False - Apple is not a BDC
```

## BDC Properties

Each BDC entity provides useful information:

```python
arcc = bdcs.get_by_ticker("ARCC")

# Basic info
print(f"Name: {arcc.name}")
print(f"CIK: {arcc.cik}")
print(f"File Number: {arcc.file_number}")  # 814-00663
print(f"State: {arcc.state}")
print(f"Active: {arcc.is_active}")

# Filing info
print(f"Last Filing: {arcc.last_filing_date}")
print(f"Last Form: {arcc.last_filing_type}")
```

**Output:**
```plaintext
Name: ARES CAPITAL CORP
CIK: 1287750
File Number: 814-00663
State: MD
Active: True
Last Filing: 2024-11-05
Last Form: 10-Q
```

## Portfolio Investments

BDCs disclose their portfolio holdings in the Schedule of Investments within their 10-K and 10-Q filings.

### Get Individual Investments

Extract detailed investment positions from a BDC's latest filing:

```python
arcc = bdcs.get_by_ticker("ARCC")
investments = arcc.portfolio_investments()

print(f"Total positions: {len(investments)}")
print(f"Total fair value: ${investments.total_fair_value:,.0f}")
print(f"Total cost: ${investments.total_cost:,.0f}")
```

**Output:**
```plaintext
Total positions: 1256
Total fair value: $26,800,000,000
Total cost: $25,100,000,000
```

### Explore Investment Details

Each investment includes detailed information:

```python
# Get the largest investment
inv = investments[0]

print(f"Company: {inv.company_name}")
print(f"Type: {inv.investment_type}")
print(f"Fair Value: ${inv.fair_value:,.0f}")
print(f"Cost: ${inv.cost:,.0f}")

# For debt investments
if inv.interest_rate:
    print(f"Interest Rate: {inv.interest_rate:.2%}")
if inv.spread:
    print(f"Spread: {inv.spread:.2%}")
```

**Output:**
```plaintext
Company: Ivy Hill Asset Management, L.P.
Type: First lien senior secured loan
Fair Value: $1,915,300,000
Cost: $1,890,000,000
Interest Rate: 11.75%
Spread: 5.75%
```

### Filter Investments

Find specific types of investments:

```python
# First lien loans only
first_lien = investments.filter(investment_type="First lien")
print(f"First lien positions: {len(first_lien)}")

# Search by company name
software = investments.filter(company_name="software")
print(f"Software companies: {len(software)}")

# Large positions only
from decimal import Decimal
large = investments.filter(min_fair_value=Decimal('100000000'))
print(f"Positions over $100M: {len(large)}")
```

### Convert to DataFrame

For analysis in pandas:

```python
df = investments.to_dataframe()

# Analyze by investment type
print(df.groupby('investment_type')['fair_value'].sum().sort_values(ascending=False).head())

# Find largest positions
print(df.nlargest(10, 'fair_value')[['company_name', 'investment_type', 'fair_value']])
```

### Data Quality

Check data completeness:

```python
quality = investments.data_quality

print(f"Fair value coverage: {quality.fair_value_coverage:.0%}")
print(f"Cost coverage: {quality.cost_coverage:.0%}")
print(f"Interest rate coverage: {quality.interest_rate_coverage:.0%}")
print(f"Debt investments: {quality.debt_count}")
print(f"Equity investments: {quality.equity_count}")
```

**Note:** Not all BDCs provide detailed XBRL data for individual investments. Use `has_detailed_investments()` to check:

```python
if arcc.has_detailed_investments():
    investments = arcc.portfolio_investments()
else:
    print("This BDC only provides aggregate data")
```

## Cross-BDC Analysis

Use SEC DERA bulk datasets for analysis across all BDCs.

### Fetch Quarterly Data

```python
from edgar.bdc import fetch_bdc_dataset

dataset = fetch_bdc_dataset(2024, 3)

print(f"Period: {dataset.period}")
print(f"BDCs: {dataset.num_companies}")
print(f"SOI entries: {dataset.num_soi_entries:,}")
```

**Output:**
```plaintext
Period: 2024Q3
BDCs: 148
SOI entries: 106,715
```

### Search for Portfolio Companies

Find which BDCs hold a specific private company:

```python
soi = dataset.schedule_of_investments

results = soi.search("Ivy Hill")
print(results)
```

**Output:**
```plaintext
                           company           bdc_name   bdc_cik    fair_value
0  Ivy Hill Asset Management, L.P.  ARES CAPITAL CORP  1287750  1915300000.0
```

### Find Most Common Holdings

Identify the most widely-held private companies:

```python
top = soi.top_companies(10)
print(top)
```

**Output:**
```plaintext
                    company  num_bdcs  total_fair_value                    bdc_names
0          OA Buyer, Inc.         6       322406000.0  BARINGS BDC, BARINGS CAPITAL...
1      MRI Software LLC          5       287500000.0  ARES CAPITAL, GOLUB CAPITAL...
```

### Subset by BDC

Get data for a specific BDC from the bulk dataset:

```python
# By CIK
arcc_soi = soi[1287750]
print(f"ARCC entries: {len(arcc_soi)}")

# By BDCEntity
arcc = bdcs.get_by_ticker("ARCC")
arcc_soi = soi[arcc]
```

### Industry Analysis

Analyze industry concentration:

```python
summary = dataset.summary_by_industry()
print(summary.head(10))
```

## Integration with Company Objects

BDC entities connect to standard Company functionality:

```python
arcc = bdcs.get_by_ticker("ARCC")

# Get the Company object
company = arcc.get_company()
print(company)

# Access filings
filings = arcc.get_filings(form="10-K")
latest_10k = filings[0]
print(f"Latest 10-K: {latest_10k.filing_date}")

# Get the Schedule of Investments statement
soi_statement = arcc.schedule_of_investments()
print(soi_statement)
```

## Common Use Cases

### Private Company Research

Find all BDC exposure to a private company:

```python
from edgar.bdc import fetch_bdc_dataset

dataset = fetch_bdc_dataset(2024, 3)
soi = dataset.schedule_of_investments

# Search for the company
results = soi.search("MRI Software")

print(f"Found in {len(results)} BDC positions")
print(f"Total exposure: ${results['fair_value'].sum():,.0f}")
print(f"BDCs holding: {results['bdc_name'].unique().tolist()}")
```

### BDC Portfolio Comparison

Compare portfolio composition across BDCs:

```python
from edgar.bdc import get_bdc_list

bdcs = get_bdc_list()
tickers = ["ARCC", "MAIN", "GBDC"]

for ticker in tickers:
    bdc = bdcs.get_by_ticker(ticker)
    if bdc and bdc.has_detailed_investments():
        inv = bdc.portfolio_investments()
        quality = inv.data_quality
        print(f"{ticker}: {len(inv)} positions, "
              f"{quality.debt_count} debt, {quality.equity_count} equity")
```

### Yield Analysis

Analyze interest rates across a BDC's debt portfolio:

```python
arcc = bdcs.get_by_ticker("ARCC")
investments = arcc.portfolio_investments()

# Filter to debt with interest rates
df = investments.to_dataframe()
debt = df[df['interest_rate'].notna()]

print(f"Average interest rate: {debt['interest_rate'].mean():.2%}")
print(f"Rate range: {debt['interest_rate'].min():.2%} - {debt['interest_rate'].max():.2%}")
```

## Data Sources

The BDC module uses two SEC data sources:

| Source | Content | Best For |
|--------|---------|----------|
| **SEC BDC Report** | List of all BDCs with file numbers | Finding and identifying BDCs |
| **DERA Quarterly Datasets** | Pre-extracted Schedule of Investments | Cross-BDC analysis |
| **Individual 10-K/10-Q** | Detailed XBRL investment data | Deep dive into single BDC |

## Performance Tips

1. **Cache the BDC list**: `get_bdc_list()` is cached after first call
2. **Use bulk datasets for cross-BDC analysis**: Much faster than parsing individual filings
3. **Check data availability**: Use `has_detailed_investments()` before parsing
4. **Filter early**: Use the `filter()` method to reduce data before analysis

## Next Steps

Now that you can access BDC data, learn how to:

- **[Extract Financial Statements](extract-statements.md)** - Get balance sheets and income statements
- **[Query XBRL Facts](../xbrl-querying.md)** - Deep dive into XBRL data
- **[Company Facts API](company-facts.md)** - Historical financial metrics

## Related Documentation

- **[Company Subsets](../company-subsets.md)** - Create groups of companies for analysis
- **[Finding Companies](finding-companies.md)** - General company lookup

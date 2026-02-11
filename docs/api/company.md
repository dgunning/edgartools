# Company API Reference

The `Company` class is the primary interface for working with public companies in EdgarTools. It provides access to company information, SEC filings, and financial data.

## Class Overview

```python
from edgar import Company

class Company(Entity):
    """Represents a public company with SEC filings."""
```

**Inheritance:** `SecFiler` → `Entity` → `Company`

## Constructor

### Company(cik_or_ticker)

Create a Company instance using either a CIK number or ticker symbol.

```python
Company(cik_or_ticker: Union[str, int])
```

**Parameters:**
- `cik_or_ticker` (Union[str, int]): Company identifier
  - **CIK**: Central Index Key as integer or string (with or without padding)
  - **Ticker**: Stock ticker symbol (case-insensitive)

**Examples:**
```python
# By ticker symbol (case-insensitive)
company = Company("AAPL")
company = Company("aapl")

# By CIK number
company = Company(320193)
company = Company("320193")
company = Company("0000320193")  # Zero-padded
```

**Raises:**
- `CompanyNotFoundError`: When company cannot be found
- `ValueError`: When identifier format is invalid

## Core Properties

### Basic Information

#### name
```python
@property
def name(self) -> str
```
Official company name as registered with the SEC.

```python
company = Company("AAPL")
print(company.name)  # "Apple Inc."
```

#### cik
```python
@property
def cik(self) -> int
```
Central Index Key - unique identifier assigned by the SEC.

```python
print(company.cik)  # 320193
```

#### display_name
```python
@property
def display_name(self) -> str
```
Formatted display name combining ticker and company name.

```python
print(company.display_name)  # "AAPL - Apple Inc."
```

#### tickers
```python
@property
def tickers(self) -> List[str]
```
List of all ticker symbols associated with the company.

```python
berkshire = Company("BRK-A")
print(berkshire.tickers)  # ["BRK-A", "BRK-B"]
```

### Industry & Classification

#### industry
```python
@property
def industry(self) -> str
```
Industry description based on SIC code.

```python
print(company.industry)  # "ELECTRONIC COMPUTERS"
```

#### sic
```python
@property
def sic(self) -> str
```
Standard Industrial Classification code.

```python
print(company.sic)  # "3571"
```

#### fiscal_year_end
```python
@property
def fiscal_year_end(self) -> str
```
Fiscal year end date in MMDD format.

```python
print(company.fiscal_year_end)  # "0930" (September 30)
```

### Company Status

#### is_company
```python
@property
def is_company(self) -> bool
```
Always `True` for Company instances. Used to distinguish from other entities.

```python
print(company.is_company)  # True
```

#### not_found
```python
@property
def not_found(self) -> bool
```
Whether the company data was found in SEC database.

```python
print(company.not_found)  # False if found, True if not
```

### Key Metrics

#### shares_outstanding
```python
@property
def shares_outstanding(self) -> Optional[float]
```
Number of common shares outstanding, sourced from SEC company facts.

```python
company = Company("AAPL")
print(company.shares_outstanding)
# 15115785000.0
```

#### public_float
```python
@property
def public_float(self) -> Optional[float]
```
Public float value in dollars, sourced from SEC company facts.

```python
company = Company("AAPL")
print(company.public_float)
# 2899948348000.0
```

## Filing Access

### get_filings()

Get company filings with extensive filtering options.

```python
def get_filings(
    self,
    *,
    year: Union[int, List[int], range] = None,
    quarter: Union[int, List[int]] = None,
    form: Union[str, List[str]] = None,
    accession_number: Union[str, List[str]] = None,
    file_number: Union[str, List[str]] = None,
    filing_date: str = None,
    date: str = None,
    amendments: bool = True,
    is_xbrl: bool = None,
    is_inline_xbrl: bool = None,
    sort_by: str = "filing_date",
    trigger_full_load: bool = False
) -> EntityFilings
```

**Parameters:**
- `year`: Filter by year(s) - int, list of ints, or range
- `quarter`: Filter by quarter(s) - 1, 2, 3, or 4
- `form`: SEC form type(s) - e.g., "10-K", ["10-K", "10-Q"]
- `accession_number`: Specific accession number(s)
- `file_number`: SEC file number(s)
- `filing_date`: Date or date range (YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD)
- `date`: Alias for filing_date
- `amendments`: Include amended filings (default: True)
- `is_xbrl`: Filter for XBRL filings
- `is_inline_xbrl`: Filter for inline XBRL filings
- `sort_by`: Sort field (default: "filing_date")
- `trigger_full_load`: Load all filing details upfront

**Returns:** `EntityFilings` - Collection of company filings

**Examples:**
```python
# Get all filings
all_filings = company.get_filings()

# Get specific form types
annual_reports = company.get_filings(form="10-K")
quarterly_reports = company.get_filings(form=["10-K", "10-Q"])

# Filter by date
recent = company.get_filings(filing_date="2023-01-01:")
date_range = company.get_filings(filing_date="2023-01-01:2023-12-31")

# Filter by year and quarter
q4_2023 = company.get_filings(year=2023, quarter=4)
multi_year = company.get_filings(year=[2022, 2023])

# XBRL filings only
xbrl_filings = company.get_filings(is_xbrl=True)

# Exclude amendments
original_only = company.get_filings(amendments=False)
```

### latest()

Get the latest filing(s) of a specific form type.

```python
def latest(self, form: str, n: int = 1) -> Union[Filing, List[Filing]]
```

**Parameters:**
- `form`: SEC form type (e.g., "10-K", "10-Q", "8-K")
- `n`: Number of latest filings to return (default: 1)

**Returns:**
- Single `Filing` if n=1
- `List[Filing]` if n>1

**Examples:**
```python
# Get latest 10-K
latest_10k = company.latest("10-K")

# Get latest 3 quarterly reports
latest_10qs = company.latest("10-Q", 3)
```

### Convenience Properties

#### latest_tenk
```python
@property
def latest_tenk(self) -> Optional[TenK]
```
Latest 10-K filing as a TenK object with enhanced functionality.

```python
tenk = company.latest_tenk
if tenk:
    print(tenk.filing_date)
    financials = tenk.financials
```

#### latest_tenq
```python
@property  
def latest_tenq(self) -> Optional[TenQ]
```
Latest 10-Q filing as a TenQ object with enhanced functionality.

```python
tenq = company.latest_tenq
if tenq:
    print(tenq.filing_date)
    financials = tenq.financials
```

## Financial Data

### get_financials()

Get financial statements from the latest 10-K filing.

```python
def get_financials(self) -> Optional[Financials]
```

**Returns:** `Financials` object with balance sheet, income statement, and cash flow data

**Example:**
```python
financials = company.get_financials()
if financials:
    balance_sheet = financials.balance_sheet
    income_statement = financials.income
    cash_flow = financials.cash_flow
    
    # Access specific metrics
    revenue = income_statement.loc['Revenue'].iloc[0]
    total_assets = balance_sheet.loc['Total Assets'].iloc[0]
```

### get_quarterly_financials()

Get financial statements from the latest 10-Q filing.

```python
def get_quarterly_financials(self) -> Optional[Financials]
```

**Returns:** `Financials` object from latest quarterly report

**Example:**
```python
quarterly = company.get_quarterly_financials()
if quarterly:
    q_income = quarterly.income
    quarterly_revenue = q_income.loc['Revenue'].iloc[0]
```

### get_facts()

Get structured XBRL facts for the company.

```python
def get_facts(self) -> Optional[EntityFacts]
```

**Returns:** `EntityFacts` object containing all XBRL facts

**Example:**
```python
facts = company.get_facts()
if facts:
    # Convert to pandas DataFrame
    facts_df = facts.to_pandas()
    
    # Get number of facts
    num_facts = facts.num_facts()
    print(f"Company has {num_facts} XBRL facts")
```

## Address Information

### business_address()

Get the company's business address.

```python
def business_address(self) -> Optional[Address]
```

**Returns:** `Address` object or None

**Example:**
```python
address = company.business_address()
if address:
    print(f"{address.street1}")
    print(f"{address.city}, {address.state_or_country} {address.zipcode}")
```

### mailing_address()

Get the company's mailing address.

```python
def mailing_address(self) -> Optional[Address]
```

**Returns:** `Address` object or None

## Utility Methods

### get_ticker()

Get the primary ticker symbol for the company.

```python
def get_ticker(self) -> Optional[str]
```

**Returns:** Primary ticker symbol or None

**Example:**
```python
ticker = company.get_ticker()
print(ticker)  # "AAPL"
```

### get_exchanges()

Get all exchanges where the company's stock is traded.

```python
def get_exchanges(self) -> List[str]
```

**Returns:** List of exchange names

**Example:**
```python
exchanges = company.get_exchanges()
print(exchanges)  # ["NASDAQ"]
```

### get_icon()

Get company icon (if available).

```python
def get_icon(self)
```

**Returns:** Icon data or placeholder

## Data Access

### data

Access the underlying company data object.

```python
@property
def data(self) -> EntityData
```

**Returns:** `EntityData` object with complete company information

**Example:**
```python
# Access detailed company data
company_data = company.data
print(company_data.former_names)  # Previous company names
print(company_data.entity_type)   # Entity type
print(company_data.flags)         # SEC flags
```

## Related Classes

### EntityFilings

Collection of SEC filings returned by `get_filings()`.

```python
filings = company.get_filings(form="10-K")

# Collection methods
latest = filings.latest()           # Get latest filing
first_five = filings.head(5)        # Get first 5 filings
random_sample = filings.sample(3)   # Get 3 random filings

# Filtering
recent = filings.filter(filing_date="2023-01-01:")
xbrl_only = filings.filter(is_xbrl=True)

# Indexing
first_filing = filings[0]           # Get first filing
second_filing = filings[1]          # Get second filing

# Iteration
for filing in filings:
    print(f"{filing.form}: {filing.filing_date}")

# Conversion
filings_df = filings.to_pandas()    # Convert to DataFrame
```

### Address

Physical address representation.

```python
class Address:
    street1: str
    street2: Optional[str]
    city: str
    state_or_country: str
    zipcode: str
    state_or_country_desc: str
```

**Example:**
```python
address = company.business_address()
full_address = f"{address.street1}, {address.city}, {address.state_or_country}"
```

### EntityFacts

XBRL facts data container.

```python
facts = company.get_facts()

# Convert to DataFrame
df = facts.to_pandas()

# Get fact count
count = facts.num_facts()
```

## Factory Functions

Alternative ways to create Company instances:

```python
from edgar import get_company, get_entity

# Factory function
company = get_company("AAPL")

# More general entity function (returns Company for companies)
entity = get_entity("AAPL")
```

## Import Options

```python
# Primary import
from edgar import Company

# Alternative imports
from edgar.entity import Company
from edgar.entity.core import Company
```

## Error Handling

```python
try:
    company = Company("INVALID")
except CompanyNotFoundError:
    print("Company not found")
except ValueError as e:
    print(f"Invalid identifier: {e}")

# Check if company was found
company = Company("MAYBE_INVALID")
if company.not_found:
    print("Company data not available")
else:
    filings = company.get_filings()
```

## Performance Tips

1. **Use CIK when possible** - faster than ticker lookup
2. **Cache Company objects** - avoid repeated API calls
3. **Filter filings efficiently** - use specific parameters in `get_filings()`
4. **Limit result sets** - use reasonable date ranges and form filters

```python
# Efficient: specific filtering
recent_10k = company.get_filings(form="10-K", filing_date="2023-01-01:")

# Less efficient: get all then filter
all_filings = company.get_filings()
filtered = all_filings.filter(form="10-K").filter(filing_date="2023-01-01:")
```

## Complete Example

```python
from edgar import Company

# Create company instance
company = Company("AAPL")

# Basic information
print(f"Company: {company.name}")
print(f"CIK: {company.cik}")
print(f"Industry: {company.industry}")
print(f"Fiscal Year End: {company.fiscal_year_end}")

# Key metrics — simple property access
print(f"Shares Outstanding: {company.shares_outstanding:,.0f}")
print(f"Public Float: ${company.public_float:,.0f}")

# Get recent filings
recent_filings = company.get_filings(
    form=["10-K", "10-Q"],
    filing_date="2023-01-01:",
    limit=5
)

print(f"\nRecent Filings ({len(recent_filings)}):")
for filing in recent_filings:
    print(f"  {filing.form}: {filing.filing_date}")

# Get financial data
financials = company.get_financials()
if financials:
    revenue = financials.income.loc['Revenue'].iloc[0]
    print(f"\nLatest Revenue: ${revenue/1e9:.1f}B")

# Get company facts
facts = company.get_facts()
if facts:
    print(f"Total XBRL Facts: {facts.num_facts()}")

# Address information
address = company.business_address()
if address:
    print(f"Location: {address.city}, {address.state_or_country}")
```

## See Also

- **[Finding Companies Guide](../guides/finding-companies.md)** - How to locate companies
- **[Filing API Reference](filing.md)** - Working with individual filings
- **[Filings API Reference](filings.md)** - Working with filing collections
- **[Extract Financial Statements](../guides/extract-statements.md)** - Getting financial data
# Company

Access company information, filings, and financial data from the SEC.

## Quick Start

```python
from edgar import Company

# Get a company
company = Company("AAPL")

# Check if found
if company.not_found:
    print("Company not found")
    exit()

# Access basic information
print(company.name)              # Apple Inc.
print(company.get_ticker())      # AAPL
print(company.industry)          # Electronic Computers

# Get filings
filings = company.get_filings(form="10-K")
latest = filings.latest()

# Get financial statements
income = company.income_statement()
balance = company.balance_sheet()
cashflow = company.cashflow_statement()
```

## Creating a Company

### By Ticker

```python
company = Company("AAPL")    # Case insensitive
company = Company("aapl")    # Also works
```

### By CIK

```python
company = Company(320193)           # Integer
company = Company("320193")         # String
company = Company("0000320193")     # Zero-padded
```

### Checking if Found

```python
company = Company("INVALID")

if company.not_found:
    print("Company not found")
```

Note: `Company()` does not raise an error for invalid input. It creates a placeholder entity. Always check `not_found` when user input is involved.

## Properties

### Identity

| Property | Type | Description |
|----------|------|-------------|
| `name` | str | Company name |
| `cik` | int | Central Index Key |
| `tickers` | List[str] | Trading symbols |
| `fiscal_year_end` | str | Fiscal year end (e.g., "12-31") |
| `not_found` | bool | True if company doesn't exist |

### Classification

| Property | Type | Description |
|----------|------|-------------|
| `sic` | int | SIC code |
| `industry` | str | Industry description |
| `business_category` | str | Business category (e.g., "Operating Company", "REIT", "Bank") |
| `is_foreign` | bool | True if incorporated outside US |
| `filer_type` | str | "Domestic", "Foreign", or "Canadian" |

### Filer Status

| Property | Type | Description |
|----------|------|-------------|
| `filer_category` | FilerCategory | Parsed filer category |
| `is_large_accelerated_filer` | bool | Public float >= $700M |
| `is_accelerated_filer` | bool | Public float >= $75M and < $700M |
| `is_non_accelerated_filer` | bool | Public float < $75M |
| `is_smaller_reporting_company` | bool | Qualifies as SRC |
| `is_emerging_growth_company` | bool | Qualifies as EGC |

### Financial Data

| Property | Type | Description |
|----------|------|-------------|
| `facts` | EntityFacts | Company facts (cached) |
| `latest_tenk` | TenK | Latest 10-K filing |
| `latest_tenq` | TenQ | Latest 10-Q filing |
| `public_float` | float | Public float value |
| `shares_outstanding` | float | Shares outstanding |

## Methods

### get_filings()

Get company filings with optional filtering.

```python
def get_filings(
    *,
    year: int | List[int] = None,
    quarter: int | List[int] = None,
    form: str | List[str] = None,
    accession_number: str | List[str] = None,
    file_number: str | List[str] = None,
    filing_date: str | Tuple[str, str] = None,
    amendments: bool = True,
    is_xbrl: bool = None,
    is_inline_xbrl: bool = None
) -> EntityFilings
```

**Examples:**

```python
# All filings
filings = company.get_filings()

# Filter by form
filings_10k = company.get_filings(form="10-K")
periodic = company.get_filings(form=["10-K", "10-Q"])

# Filter by date
recent = company.get_filings(filing_date="2024-01-01:")
date_range = company.get_filings(filing_date=("2023-01-01", "2023-12-31"))

# Filter by year and quarter
q4_2023 = company.get_filings(year=2023, quarter=4)

# Exclude amendments
originals = company.get_filings(form="10-K", amendments=False)

# Get latest
latest = company.get_filings(form="10-K").latest()
```

### get_facts()

Get structured financial data from SEC Company Facts API.

```python
def get_facts(
    period_type: str | PeriodType = None
) -> Optional[EntityFacts]
```

**Examples:**

```python
# Get all facts
facts = company.get_facts()

# Or use cached property
facts = company.facts

# Filter by period type
annual_facts = company.get_facts(period_type='annual')
quarterly_facts = company.get_facts(period_type='quarterly')
```

### Financial Statement Methods

Get financial statements directly.

```python
def income_statement(
    periods: int = 4,
    period: str = 'annual',
    as_dataframe: bool = False,
    concise_format: bool = False
) -> Optional[MultiPeriodStatement | TTMStatement | DataFrame]
```

**Parameters:**

- `periods` - Number of periods to retrieve (default: 4)
- `period` - 'annual', 'quarterly', or 'ttm' (trailing twelve months)
- `as_dataframe` - Return as DataFrame instead of Statement
- `concise_format` - Display as $1.0B instead of $1,000,000,000

**Examples:**

```python
# Annual income statement (last 4 years)
income = company.income_statement()

# Quarterly statements
income = company.income_statement(period='quarterly', periods=8)

# Trailing twelve months
ttm = company.income_statement(period='ttm')

# As DataFrame
df = company.income_statement(as_dataframe=True)

# Balance sheet and cash flow work the same way
balance = company.balance_sheet(period='annual')
cashflow = company.cashflow_statement(period='quarterly')
```

Note: TTM is not applicable for balance sheet (point-in-time data).

### get_ttm()

Calculate Trailing Twelve Months value for any concept.

```python
def get_ttm(
    concept: str,
    as_of: date | str = None
) -> TTMMetric
```

**Parameters:**

- `concept` - XBRL concept name (e.g., 'Revenues', 'us-gaap:NetIncomeLoss')
- `as_of` - Date, ISO string 'YYYY-MM-DD', or quarter string 'YYYY-QN'

**Examples:**

```python
# Latest TTM revenue
ttm_revenue = company.get_ttm("Revenues")
print(f"TTM Revenue: ${ttm_revenue.value / 1e9:.1f}B")

# TTM as of specific date
ttm = company.get_ttm("NetIncomeLoss", as_of="2024-06-30")
ttm = company.get_ttm("NetIncomeLoss", as_of="2024-Q2")

# Access TTM details
print(f"Value: {ttm.value}")
print(f"Periods: {ttm.periods}")  # Shows which quarters summed
print(f"Calculation: {ttm.calculation_context}")
```

**Common TTM Methods:**

```python
# Convenience methods for common metrics
ttm_revenue = company.get_ttm_revenue()
ttm_income = company.get_ttm_net_income()
```

### list_concepts()

Discover available XBRL concepts for this company.

```python
def list_concepts(
    search: str = None,
    statement: str = None,
    limit: int = 20
) -> ConceptList
```

**Examples:**

```python
# Search for revenue-related concepts
concepts = company.list_concepts(search="revenue")

# Filter by statement
concepts = company.list_concepts(
    search="assets",
    statement="BalanceSheet"
)

# Iterate over results
for concept in concepts:
    print(f"{concept['concept']}: {concept['label']}")

# Convert to DataFrame
df = concepts.to_dataframe()

# Get as list
concept_list = concepts.to_list()
```

### get_ticker() / get_exchanges()

Get ticker and exchange information.

```python
# Primary ticker
ticker = company.get_ticker()

# All tickers
tickers = company.tickers

# All exchanges
exchanges = company.get_exchanges()
```

### get_financials() / get_quarterly_financials()

Get financial statements from latest 10-K or 10-Q.

```python
# From latest 10-K
financials = company.get_financials()
if financials:
    print(financials.income_statement)

# From latest 10-Q
quarterly = company.get_quarterly_financials()
```

### to_context()

Get AI-optimized text representation.

```python
def to_context(
    detail: str = 'standard',
    max_tokens: int = None
) -> str
```

**Detail levels:**

- `'minimal'` - Basic info (~100-150 tokens)
- `'standard'` - Adds industry, category, actions (~250-350 tokens)
- `'full'` - Adds addresses, phone, filing stats (~500+ tokens)

**Example:**

```python
# For LLM consumption
context = company.to_context('standard')
print(context)
```

## Common Workflows

### Get Latest Annual Report

```python
company = Company("AAPL")

# Get latest 10-K
filings = company.get_filings(form="10-K")
latest = filings.latest()

# Access XBRL data
if latest.is_xbrl:
    xbrl = latest.xbrl()
    income = xbrl.statements.income_statement()
```

### Compare Quarterly Performance

```python
# Get last 4 quarters
filings = company.get_filings(form="10-Q")
last_4 = filings.latest(4)

for filing in last_4:
    print(f"Period: {filing.report_date}")
    print(f"Filed: {filing.filing_date}")
```

### Track Insider Trading

```python
# Get Form 4 filings (insider transactions)
filings = company.get_filings(form="4")

for filing in filings.head(10):
    form4 = filing.obj()
    summary = form4.get_ownership_summary()
    print(f"{form4.insider_name}: {summary.net_change:,} shares")
```

## Business Categorization

EdgarTools classifies companies into business categories:

```python
category = company.business_category
# Returns one of: 'Operating Company', 'ETF', 'Mutual Fund',
# 'Closed-End Fund', 'BDC', 'REIT', 'Investment Manager',
# 'Bank', 'Insurance Company', 'SPAC', 'Holding Company'

# Helper methods
if company.is_fund():
    print("Investment fund")

if company.is_financial_institution():
    print("Financial institution")

if company.is_operating_company():
    print("Operating company")
```

## Error Handling

### Company Not Found

```python
company = Company("INVALID")

if company.not_found:
    print("Company does not exist")
    exit()
```

### No Filings Available

```python
filings = company.get_filings(form="RARE-FORM")

if filings.empty:
    print("No filings of this type")
else:
    latest = filings.latest()
```

### Facts Not Available

```python
facts = company.get_facts()

if facts is None:
    print("Facts not available for this company")
```

## Performance Tips

### Cache the Company Object

```python
# Good - reuse company
company = Company("AAPL")
filings = company.get_filings(form="10-K")
facts = company.facts
income = company.income_statement()

# Less efficient - creates company each time
Company("AAPL").get_filings(form="10-K")
Company("AAPL").facts
Company("AAPL").income_statement()
```

### Use CIK for Production

```python
# Faster - direct CIK lookup (one API call)
company = Company(320193)

# Slower - ticker requires lookup (two API calls)
company = Company("AAPL")
```

### Use Latest Properties

```python
# Good - cached property
tenk = company.latest_tenk

# More verbose
tenk = company.get_filings(form="10-K").latest().obj()
```

## See Also

- `company.docs` - Display this documentation in terminal
- [EntityFilings](EntityFilings.md) - Working with filing collections
- [EntityFiling](EntityFiling.md) - Working with individual filings

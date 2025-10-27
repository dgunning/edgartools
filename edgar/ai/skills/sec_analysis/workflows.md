---
name: SEC Analysis Workflows
description: End-to-end workflows for common SEC filing analysis tasks using EdgarTools with step-by-step examples.
---

# SEC Analysis Workflows

End-to-end examples for common SEC filing analysis patterns.

## Workflow 1: Compare Revenue Across Competitors

**Goal**: Compare revenue trends for multiple companies over time

**Use Case**: Market analysis, competitive intelligence, sector research

### Steps

1. **Define competitors**:
   ```python
   tickers = ["AAPL", "MSFT", "GOOGL"]
   ```

2. **Get revenue data** (using helper):
   ```python
   from edgar.ai.helpers import compare_companies_revenue

   results = compare_companies_revenue(tickers, periods=3)
   ```

3. **Access individual results**:
   ```python
   aapl_income = results["AAPL"]
   msft_income = results["MSFT"]
   googl_income = results["GOOGL"]

   print("Apple Revenue:")
   print(aapl_income)
   print("\nMicrosoft Revenue:")
   print(msft_income)
   print("\nGoogle Revenue:")
   print(googl_income)
   ```

### Alternative (Raw API)

```python
from edgar import Company

companies = [Company(t) for t in ["AAPL", "MSFT", "GOOGL"]]
statements = [c.income_statement(periods=3) for c in companies]

for ticker, stmt in zip(tickers, statements):
    print(f"\n{ticker} Revenue Trend:")
    print(stmt)
```

### Expected Output

Multi-period income statements showing 3-year revenue trends for each company, allowing easy comparison of growth rates and revenue scale.

---

## Workflow 2: Track Recent Filings for a Sector

**Goal**: Monitor recent 10-K and 10-Q filings for a specific sector (e.g., technology)

**Use Case**: Real-time monitoring, sector analysis, investment research

### Steps

1. **Get recent filings**:
   ```python
   from edgar import get_current_filings

   recent = get_current_filings()  # Last ~24 hours
   ```

2. **Filter by form types**:
   ```python
   # Filter for 10-K and 10-Q only
   reports = recent.filter(form=["10-K", "10-Q"])
   ```

3. **Filter by sector companies** (if you know the tickers):
   ```python
   # Example: Technology sector
   tech_tickers = ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "TSLA"]
   tech_reports = reports.filter(ticker=tech_tickers)
   ```

4. **Display results**:
   ```python
   print(f"Found {len(tech_reports)} tech filings in last 24 hours")
   print(tech_reports.head(10))  # Show first 10
   ```

5. **Access specific filing for details**:
   ```python
   if len(tech_reports) > 0:
       filing = tech_reports[0]
       print(f"\nLatest filing:")
       print(filing)

       # Get financial statements if it's 10-K or 10-Q
       if filing.form in ["10-K", "10-Q"]:
           xbrl = filing.xbrl()
           income = xbrl.statements.income_statement()
           print(income)
   ```

### Use Cases

- Daily monitoring of sector activity
- Tracking quarterly earnings releases
- Identifying companies filing late
- Sector-wide trend analysis

---

## Workflow 3: Quarterly Trend Analysis

**Goal**: Analyze quarterly financial trends for a single company

**Use Case**: Quarterly earnings analysis, seasonal pattern identification, growth tracking

### Steps

1. **Get quarterly data** (using helper):
   ```python
   from edgar.ai.helpers import get_revenue_trend

   quarterly_income = get_revenue_trend("TSLA", periods=4, quarterly=True)
   ```

2. **Display quarterly trend**:
   ```python
   print("Tesla Quarterly Revenue Trend:")
   print(quarterly_income)  # Shows last 4 quarters
   ```

3. **Get more detail from specific quarter**:
   ```python
   from edgar import Company

   company = Company("TSLA")
   latest_10q = company.get_filings(form="10-Q")[0]

   # Parse XBRL for detailed line items
   xbrl = latest_10q.xbrl()
   detailed_income = xbrl.statements.income_statement()

   print("\nDetailed Income Statement (Latest Quarter):")
   print(detailed_income)
   ```

4. **Access balance sheet and cash flow for comprehensive analysis**:
   ```python
   balance = xbrl.statements.balance_sheet()
   cash_flow = xbrl.statements.cash_flow_statement()

   print("\nBalance Sheet:")
   print(balance)
   print("\nCash Flow Statement:")
   print(cash_flow)
   ```

### Alternative: Manual Quarter Selection

```python
from edgar import Company

company = Company("TSLA")

# Get all 10-Q filings
quarterly_filings = company.get_filings(form="10-Q")

# Process first 4 quarters
for i, filing in enumerate(quarterly_filings[:4]):
    print(f"\nQuarter {i+1}: Filed {filing.filing_date}")
    xbrl = filing.xbrl()
    income = xbrl.statements.income_statement()
    # Extract revenue (implementation specific)
```

---

## Workflow 4: Deep Dive into Specific Filing

**Goal**: Extract comprehensive information from a specific 10-K filing

**Use Case**: Detailed company research, due diligence, financial modeling

### Steps

1. **Get the filing** (using helper):
   ```python
   from edgar.ai.helpers import get_filing_statement

   # Get all three major statements
   income = get_filing_statement("AAPL", 2023, "10-K", "income")
   balance = get_filing_statement("AAPL", 2023, "10-K", "balance")
   cash_flow = get_filing_statement("AAPL", 2023, "10-K", "cash_flow")

   print("Income Statement:")
   print(income)
   print("\nBalance Sheet:")
   print(balance)
   print("\nCash Flow Statement:")
   print(cash_flow)
   ```

2. **Or use raw API for more control**:
   ```python
   from edgar import Company

   company = Company("AAPL")
   filing = company.get_filings(year=2023, form="10-K")[0]
   ```

3. **Access different components**:
   ```python
   # Financial statements from XBRL
   xbrl = filing.xbrl()
   income = xbrl.statements.income_statement()
   balance = xbrl.statements.balance_sheet()
   cash_flow = xbrl.statements.cash_flow_statement()

   # Parsed document structure
   doc = filing.document()

   # Raw HTML (if needed)
   html = filing.html()
   ```

4. **Extract specific sections from document**:
   ```python
   # Business description
   if hasattr(doc, 'get_section'):
       item1 = doc.get_section("Item 1")
       print("Business Description:")
       print(item1)

       # Risk factors
       item1a = doc.get_section("Item 1A")
       print("\nRisk Factors:")
       print(item1a)

       # MD&A (Management Discussion & Analysis)
       item7 = doc.get_section("Item 7")
       print("\nMD&A:")
       print(item7)
   ```

5. **Access filing metadata**:
   ```python
   print(f"Company: {filing.company}")
   print(f"Form: {filing.form}")
   print(f"Filed: {filing.filing_date}")
   print(f"Period: {filing.period_of_report}")
   print(f"Accession: {filing.accession_number}")
   ```

---

## Workflow 5: Historical Filings Search

**Goal**: Find all S-1 filings (IPOs) from a specific time period

**Use Case**: IPO research, market timing analysis, historical trends

### Steps

1. **Define time period and form**:
   ```python
   from edgar import get_filings

   filings = get_filings(
       2023, 1,  # Q1 2023
       form="S-1",
       filing_date="2023-02-01:2023-02-28"  # February only
   )
   ```

2. **Review results**:
   ```python
   print(f"Found {len(filings)} S-1 filings in February 2023")
   print(filings.head(5))
   ```

3. **Access specific filing**:
   ```python
   if len(filings) > 0:
       filing = filings[0]
       print("\nFirst S-1 Filing:")
       print(filing)

       # Get company information
       company = filing.company
       print(f"\nCompany: {company}")
   ```

4. **Iterate through all results**:
   ```python
   for filing in filings[:10]:  # First 10
       print(f"\n{filing.company} - Filed {filing.filing_date}")
       # Access filing document for more details
       doc = filing.document()
   ```

### Advanced: Filter by Industry

```python
from edgar import get_filings, Company

# Get all S-1 filings
s1_filings = get_filings(2023, 1, form="S-1")

# Filter for technology companies (example using SIC codes)
tech_s1 = []
for filing in s1_filings:
    try:
        company = Company(filing.ticker)
        # Technology SIC codes typically start with 35 or 73
        if company.sic and str(company.sic).startswith(('35', '73')):
            tech_s1.append(filing)
    except:
        continue

print(f"Found {len(tech_s1)} technology S-1 filings")
```

---

## Workflow 6: Multi-Year Financial Analysis

**Goal**: Analyze 5-year financial trends for comprehensive company assessment

**Use Case**: Long-term trend analysis, historical performance review, valuation

### Steps

1. **Get 5-year financial statements**:
   ```python
   from edgar import Company

   company = Company("AAPL")

   income = company.income_statement(periods=5)
   balance = company.balance_sheet(periods=5)
   cash_flow = company.cash_flow_statement(periods=5)
   ```

2. **Display trends**:
   ```python
   print("5-Year Income Statement:")
   print(income)

   print("\n5-Year Balance Sheet:")
   print(balance)

   print("\n5-Year Cash Flow:")
   print(cash_flow)
   ```

3. **Calculate growth rates** (programmatic access):
   ```python
   # Access specific metrics from statements
   # (Implementation depends on object structure)

   print("\nRevenue Growth Analysis:")
   # Revenue trend analysis
   ```

---

## Error Handling Patterns

### Handle Missing Data

```python
from edgar import Company

try:
    company = Company("INVALID_TICKER")
    income = company.income_statement(periods=3)
except Exception as e:
    print(f"Error: {e}")
    # Fallback to alternative approach or notify user
```

### Handle Empty Results

```python
from edgar import get_filings

filings = get_filings(2023, 1, form="RARE-FORM")
if len(filings) == 0:
    print("No filings found matching criteria")
    print("Try broader search parameters")
else:
    print(f"Found {len(filings)} filings")
    print(filings.head(5))
```

### Verify Data Availability

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]

# Check if XBRL is available
if hasattr(filing, 'xbrl'):
    try:
        xbrl = filing.xbrl()
        # Process XBRL data
        income = xbrl.statements.income_statement()
        print(income)
    except Exception as e:
        print(f"Error parsing XBRL: {e}")
else:
    print("XBRL data not available for this filing")
```

### Graceful Degradation

```python
from edgar import Company

def get_company_revenue(ticker, periods=3):
    """Get company revenue with fallback options."""
    try:
        # Try Entity Facts API (fastest)
        company = Company(ticker)
        return company.income_statement(periods=periods)
    except Exception as e1:
        print(f"Entity Facts failed: {e1}")
        try:
            # Fallback to filing XBRL
            company = Company(ticker)
            filing = company.get_filings(form="10-K")[0]
            xbrl = filing.xbrl()
            return xbrl.statements.income_statement()
        except Exception as e2:
            print(f"Filing XBRL failed: {e2}")
            return None

# Usage
revenue = get_company_revenue("AAPL", periods=3)
if revenue:
    print(revenue)
else:
    print("Unable to retrieve revenue data")
```

---

## Performance Tips

### Batch Processing Efficiently

```python
from edgar import Company
import time

tickers = ["AAPL", "MSFT", "GOOGL", "META", "AMZN"]
results = {}

for ticker in tickers:
    try:
        company = Company(ticker)
        results[ticker] = company.income_statement(periods=3)
        # Respect rate limits
        time.sleep(0.1)  # EdgarTools handles this automatically
    except Exception as e:
        print(f"Error with {ticker}: {e}")
        results[ticker] = None

# Process results
for ticker, statement in results.items():
    if statement:
        print(f"\n{ticker}:")
        print(statement)
```

### Cache-Friendly Patterns

```python
from edgar import Company

# Create company object once, reuse multiple times
company = Company("AAPL")

# All these calls may use cached data
filings = company.get_filings(form="10-K")
income = company.income_statement(periods=3)
balance = company.balance_sheet(periods=3)
```

### Minimize Token Usage

```python
from edgar import get_filings

# Instead of printing everything
filings = get_filings(2023, 1, form="10-K")
print(filings)  # Could be thousands of filings

# Use head() to limit output
print(filings.head(5))  # Only 5 filings

# Or filter first
tech_filings = filings.filter(ticker=["AAPL", "MSFT", "GOOGL"])
print(tech_filings)  # Much smaller result set
```

---

## See Also

- [skill.md](skill.md) - Main API documentation
- [objects.md](objects.md) - Object representations and token estimates
- [README.md](README.md) - Installation and setup guide

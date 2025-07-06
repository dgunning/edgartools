---
title: "Understanding SEC Filings"
description: "A comprehensive guide to SEC filings, their types, purposes, and how to work with them using edgartools"
category: "concepts"
difficulty: "beginner"
time_required: "15 minutes"
prerequisites: ["installation"]
related: ["xbrl-fundamentals", "statement-structure"]
keywords: ["SEC", "EDGAR", "filings", "10-K", "10-Q", "8-K", "13F", "Form 4", "regulatory", "disclosure"]
---

# Understanding SEC Filings

## Introduction

The U.S. Securities and Exchange Commission (SEC) requires public companies, investment funds, and certain individuals to submit various regulatory filings. These documents provide transparency into financial performance, significant events, insider activities, and investment decisions. The SEC's Electronic Data Gathering, Analysis, and Retrieval system (EDGAR) makes these filings publicly available.

This guide explains the key SEC filing types, their purposes, and how to access and analyze them using the `edgartools` library.

## Why SEC Filings Matter

SEC filings are the most authoritative source of company information available to the public. Unlike press releases, investor presentations, or news articles, SEC filings:

- Are legally required to be accurate and complete
- Follow standardized formats for consistency
- Contain detailed financial data and disclosures
- Are subject to strict liability for false or misleading information
- Provide a historical record of a company's development

## Common SEC Filing Types

### Company Reporting Forms

| Form | Description | Frequency | Key Information |
|------|-------------|-----------|-----------------|
| **10-K** | Annual report | Annual | Comprehensive financial statements, business description, risk factors, management discussion |
| **10-Q** | Quarterly report | Quarterly | Interim financial statements, updates since last 10-K |
| **8-K** | Current report | As needed | Material events (acquisitions, executive changes, bankruptcy) |
| **S-1** | Registration statement | Before IPO | Business model, financials, risk factors, use of proceeds |
| **DEF 14A** | Proxy statement | Annual | Executive compensation, board members, shareholder proposals |

### Ownership and Investment Forms

| Form | Description | Filed By | Key Information |
|------|-------------|----------|-----------------|
| **Form 3** | Initial ownership | Insiders | Initial positions when becoming an insider |
| **Form 4** | Changes in ownership | Insiders | Purchases, sales, and other transactions |
| **Form 5** | Annual ownership | Insiders | Summary of transactions for the year |
| **13F** | Holdings report | Investment funds | Portfolio holdings of investment managers |
| **13D/G** | Beneficial ownership | 5%+ shareholders | Significant ownership positions and intentions |

## Anatomy of Key Filings

### 10-K Annual Report

The 10-K is the most comprehensive filing and typically contains:

1. **Business Overview** (Part I, Item 1)
   - Company operations, products/services, markets
   - Revenue breakdown by segment
   - Competitive landscape

2. **Risk Factors** (Part I, Item 1A)
   - Detailed disclosure of business risks
   - Industry, operational, and financial risks

3. **Management's Discussion & Analysis** (Part II, Item 7)
   - Analysis of financial condition and results
   - Liquidity and capital resources
   - Critical accounting policies

4. **Financial Statements** (Part II, Item 8)
   - Balance sheet
   - Income statement
   - Cash flow statement
   - Statement of shareholders' equity
   - Notes to financial statements

5. **Controls and Procedures** (Part II, Item 9)
   - Disclosure controls
   - Internal control over financial reporting

### 10-Q Quarterly Report

The 10-Q is a condensed version of the 10-K filed quarterly, containing:

- Unaudited financial statements
- Management's discussion of results
- Updates on risk factors
- Disclosure of material events

### 8-K Current Report

The 8-K reports significant events that occur between 10-K and 10-Q filings:

- Item 1.01: Entry into a Material Agreement
- Item 2.01: Completion of Acquisition or Disposition
- Item 5.02: Departure/Election of Directors or Officers
- Item 7.01: Regulation FD Disclosure
- Item 8.01: Other Events

### Form 4 (Insider Transactions)

Form 4 discloses transactions by company insiders (directors, officers, 10%+ shareholders):

- Transaction date and type (purchase, sale, grant, exercise)
- Number of securities involved
- Price per share
- Resulting ownership after transaction

### 13F (Investment Fund Holdings)

13F reports show investment portfolios of funds managing over $100 million:

- Securities held at quarter-end
- Number of shares
- Market value
- Investment discretion

## Working with SEC Filings in edgartools

### Accessing Filings

```python
from edgar import Company, Filings

# Get all filings for a specific company
apple = Company("AAPL")
filings = apple.get_filings()

# Filter by form type
annual_reports = filings.filter(form="10-K")
quarterly_reports = filings.filter(form="10-Q")
current_reports = filings.filter(form="8-K")

# Get the most recent annual report
latest_10k = annual_reports.latest()

# Search across multiple companies
tech_filings = Filings.search(
    companies=["AAPL", "MSFT", "GOOGL"],
    form="8-K",
    start_date="2023-01-01",
    end_date="2023-12-31"
)
```

### Extracting Financial Data

```python
# Get financial statements from a 10-K
filing = annual_reports.latest()
financials = filing.get_financials()

# Access specific statements
balance_sheet = financials.get_balance_sheet()
income_stmt = financials.get_income_statement()
cash_flow = financials.get_cash_flow_statement()

# Query specific financial items
revenue = income_stmt.get_value("Revenues")
net_income = income_stmt.get_value("NetIncomeLoss")
total_assets = balance_sheet.get_value("Assets")
```

### Analyzing Insider Trading

```python
from edgar import Company

# Get insider transactions
tesla = Company("TSLA")
insider_filings = tesla.get_insider_transactions(start_date="2023-01-01")

# Analyze transactions by insider
for filing in insider_filings:
    print(f"Insider: {filing.reporting_owner}")
    print(f"Transaction: {filing.transaction_type}")
    print(f"Shares: {filing.shares}")
    print(f"Value: ${filing.value:,.2f}")
    print(f"Date: {filing.transaction_date}")
```

### Researching Investment Funds

```python
from edgar import Fund

# Get fund holdings
blackrock = Fund("BlackRock")
holdings = blackrock.get_holdings()

# Analyze portfolio
for holding in holdings.top(10):
    print(f"Company: {holding.company_name}")
    print(f"Ticker: {holding.ticker}")
    print(f"Shares: {holding.shares:,}")
    print(f"Value: ${holding.value:,.2f}")
    print(f"% of Portfolio: {holding.portfolio_percent:.2f}%")
```

## Best Practices for Working with SEC Filings

### 1. Understand Filing Timelines

- **10-K**: Due 60-90 days after fiscal year-end (depending on company size)
- **10-Q**: Due 40-45 days after quarter-end
- **8-K**: Due within 4 business days of the event
- **Form 4**: Due within 2 business days of the transaction
- **13F**: Due within 45 days of quarter-end

### 2. Be Aware of Filing Amendments

Amendments are indicated with a suffix:
- 10-K/A, 10-Q/A, 8-K/A, etc.

```python
# Get original and amended filings
filings = company.get_filings(form="10-K")
amendments = filings.filter(form="10-K/A")
```

### 3. Handle Historical Data Carefully

- Financial restatements can change historical data
- Company structures change over time (mergers, spin-offs)
- Accounting standards evolve

### 4. Respect SEC Access Guidelines

The SEC has rate limits for EDGAR access:
- Identify yourself properly with `edgar.set_identity()`
- Implement appropriate delays between requests
- Consider using local caching for repeated access

```python
from edgar import set_identity, enable_cache

# Set your identity for SEC access
set_identity("your.email@example.com")

```


## Conclusion

SEC filings provide a wealth of structured and unstructured data for financial analysis, investment research, and regulatory compliance. With `edgartools`, you can efficiently access, parse, and analyze these filings to extract valuable insights.

Understanding the different filing types, their purposes, and how to work with them programmatically allows you to build sophisticated financial analysis workflows and make more informed investment decisions.

## Additional Resources

- [SEC EDGAR Website](https://www.sec.gov/edgar/search-and-access)
- [SEC Filing Deadlines](https://www.sec.gov/edgar/filer-information/calendar)
- [EDGAR Filing Codes](https://www.sec.gov/info/edgar/forms/edgform.pdf)

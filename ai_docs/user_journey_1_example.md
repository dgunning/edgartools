# User Journey Example: Company Financial Analysis

**User Goal:** Understand a company's financial health

This example demonstrates how to use edgartools to complete the "Company Financial Analysis Journey" as outlined in the user journeys documentation.

## Steps Satisfying the Journey

> Note: Filings returned by `get_filings()` are always sorted by most recent date (descending) by default. Use `.sort()` for custom orderings.

### 1. Find a specific company by ticker
```python
from edgar import *
set_identity("user@domain.com")

company = Company(ticker="AAPL")
print(company.name, company.cik)
```

### 2. Retrieve latest 10-K/10-Q filings
```python
# Get the latest 10-K and 10-Q filings directly
latest_10k = company.get_filings(form="10-K").latest()
latest_10q = company.get_filings(form="10-Q").latest()
print(latest_10k.filing_date, latest_10q.filing_date)
```

# Optionally, get several recent filings using head()
recent_10ks = company.get_filings(form="10-K").head(3)
for filing in recent_10ks:
    print(filing.filing_date)


### 3. Extract financial statements
```python
# Convert the filing to a data object and access XBRL statements
xbrl = latest_10k.obj()  # Returns an XBRL object for 10-K
balance_sheet = xbrl.balance_sheet
income_statement = xbrl.income_statement
cash_flow = xbrl.cash_flow_statement

print(balance_sheet.head())
print(income_statement.head())
print(cash_flow.head())
```

### 4. Calculate key financial ratios
```python
from edgar.xbrl.analysis.ratios import FinancialRatios

ratios = FinancialRatios(xbrl)
liquidity = ratios.calculate_liquidity_ratios()
print(liquidity)  # Pretty table of liquidity ratios

# Access a specific ratio (e.g., current ratio)
current_ratio = liquidity.ratios['current'].results
print("Current Ratio:", current_ratio)

# Calculate all ratios
all_ratios = ratios.calculate_all()
print(all_ratios['profitability'])  # Pretty table of profitability ratios
```

# See [ratios_api.md](ratios_api.md) for full details and more examples.

### 5. Compare with previous periods
```python
# Get previous 10-K filings (excluding the latest)
previous_10ks = company.get_filings(form="10-K").head(3)[1:]
for prev in previous_10ks:
    prev_xbrl = prev.obj()
    prev_bs = prev_xbrl.balance_sheet
    prev_is = prev_xbrl.income_statement
    prev_ratio = prev_bs.loc["CurrentAssets", "value"] / prev_bs.loc["CurrentLiabilities", "value"]
    print(f"{prev.filing_date}: Current Ratio = {prev_ratio}")
```

---

## Critique: Can This User Journey Be Satisfied with the API?

**Strengths:**
- The edgartools API provides a direct path for each step: company lookup, filings retrieval, filtering by form, and conversion to XBRL objects.
- Convenient methods like `latest()` and `head()` make it easy to access the most recent filings without manual sorting.
- Financial statements are accessible as pandas DataFrames, making further analysis and ratio calculation straightforward.
- The API supports sorting and filtering, so comparing across periods is natural.

**Limitations:**
- Some XBRL tag names may differ between companies or years; robust code should handle missing or variant tag names.
- Not all filings will have XBRL data (especially older ones), so error handling is needed in production.
- Advanced ratio calculations (e.g., multi-year trends, custom metrics) may require additional logic or helper functions.

**Conclusion:**
> The "Company Financial Analysis Journey" is well-supported by edgartools. All steps can be accomplished with the documented API, though users should be aware of financial data variability and handle edge cases in real-world usage.

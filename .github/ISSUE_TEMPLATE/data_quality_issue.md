---
name: Data Quality Issue
about: Report incorrect financial data, missing values, or calculation errors
title: '[DATA] '
labels: 'data-quality, bug'
assignees: ''
---

## Data Quality Issue Details

**Issue Type:**
- [ ] Incorrect financial values (wrong numbers)
- [ ] Missing financial data (expected data not present)
- [ ] Calculation errors (formulas producing wrong results)
- [ ] Data inconsistency (different values for same metric)
- [ ] Historical data problems (changes over time)

## Environment
**EdgarTools Version:** (e.g., 4.9.0)
**Python Version:** (e.g., 3.10.5)  
**Operating System:** (e.g., macOS 14.0, Windows 11, Ubuntu 22.04)

## Financial Data Details
**Company/Ticker:** (e.g., AAPL)
**Form Type:** (e.g., 10-K, 10-Q, 8-K)
**Filing Date/Period:** (e.g., 2023-09-30, Q4 2023)
**Statement Type:** (e.g., Income Statement, Balance Sheet, Cash Flow)

**Specific Metric/Concept:**
- Financial line item: (e.g., "Total Revenue", "Net Income", "Total Assets")
- XBRL concept name: (if known, e.g., "us-gaap:Revenues")

## Data Issue
**Expected Value:** 
- Amount: (e.g., $394.3 billion)
- Source: (where you found the correct value - SEC filing, company website, etc.)
- Page/section reference: (e.g., "Page 45 of 10-K filing")

**Actual Value from EdgarTools:**
- Amount: (e.g., $39.43 billion - off by factor of 10)
- How obtained: (code snippet showing how you retrieved this value)

**Code to reproduce:**
```python
from edgar import Company

company = Company("AAPL")
filings = company.get_filings(form="10-K", year=2023)
filing = filings.latest()

# Show how you retrieved the incorrect value
statements = filing.xbrl.statements
income_stmt = statements.get_statement("INCOME")
revenue = income_stmt.get_concept("Revenue")  # or however you accessed it

print(f"Revenue: {revenue}")  # Shows incorrect value
```

## Cross-Verification
**Have you verified this issue with:**
- [ ] Multiple time periods for same company
- [ ] Multiple companies with same issue
- [ ] Direct SEC filing comparison
- [ ] Other financial data sources

**Affects multiple periods/companies?**
- Companies tested: (e.g., AAPL, MSFT, GOOGL)
- Time periods tested: (e.g., 2021-2023)
- Pattern observed: (e.g., all Q4 periods affected, only certain companies)

## Expected Behavior
**What should happen:**
A clear description of the correct financial data that should be returned.

**Data validation rules:**
- Should the value be positive/negative?
- Expected magnitude/range?
- Should it match specific calculations?

## Additional Context
- Links to official SEC filings showing correct values
- Screenshots comparing EdgarTools output vs official data
- Any patterns or hypotheses about why the data might be wrong
- Related issues or similar problems you've noticed

**Impact Assessment:**
- [ ] Minor (affects specific edge case)
- [ ] Moderate (affects common use cases)  
- [ ] Major (affects core financial calculations)
- [ ] Critical (produces completely wrong results)

---
*Data quality issues are high priority and will be verified against official SEC filings. Accuracy is fundamental to EdgarTools.*
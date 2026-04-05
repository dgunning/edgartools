# Choosing the Right API

EdgarTools offers three different ways to access financial data. This guide helps you choose the right one for your needs.

## Quick Decision Tree

```
What do you want to do?

├─ "Get historical financial trends for one company"
│  └─> Use Company Facts API (company.income_statement())
│
├─ "Compare metrics across multiple companies"
│  └─> Use Financials API (company.get_financials())
│
├─ "Need segment data, dimensions, or detailed breakdowns"
│  └─> Use XBRL API (filing.xbrl().statements)
│
└─ "Need footnotes or custom concepts"
   └─> Use XBRL API (filing.xbrl())
```

## The Three APIs at a Glance

### 1. Company Facts API - Simplest
```python
company = Company("AAPL")
income = company.income_statement()  # Multi-year data instantly
```

### 2. Financials API - Best for Comparison
```python
company = Company("AAPL")
financials = company.get_financials()
revenue = financials.get_revenue()
```

### 3. XBRL API - Most Complete
```python
filing = Company("AAPL").get_filings(form="10-K").latest()
xbrl = filing.xbrl()
statements = xbrl.statements
```

## Detailed Comparison

| Feature | Company Facts | Financials | XBRL |
|---------|--------------|------------|------|
| **Speed** | Fastest (cached) | Fast | Slower (parses filing) |
| **Lines of code** | 1-2 | 2-3 | 3-5 |
| **Multi-period data** | Built-in | Built-in | Manual filtering |
| **Historical range** | All available periods | Recent filings | Single filing only |
| **Statements** | Primary 3 only | Primary 3 only | All statements |
| **Segment/dimension data** | No | No | Yes |
| **Footnotes** | No | No | Yes |
| **Custom concepts** | No | Limited | All concepts |
| **Standardization** | Partial | Yes | Raw (you control) |
| **Cross-company comparison** | Manual | Built-in | Manual |

## Use Case Examples

### Scenario 1: "I want Apple's revenue for the last 5 years"
**Recommended: Company Facts API**

```python
from edgar import Company

company = Company("AAPL")
income = company.income_statement()

# Get all revenue values
revenues = income.get_all_values("Revenues")
for value in revenues[:5]:
    print(f"{value.period}: ${value.value:,.0f}")
```

**Why this API?**
- Single company, historical trend
- Standard metric (revenue)
- Fastest way to get multi-period data

---

### Scenario 2: "Compare revenue growth: Apple vs Microsoft"
**Recommended: Financials API**

```python
from edgar import Company

aapl = Company("AAPL").get_financials()
msft = Company("MSFT").get_financials()

print(f"Apple revenue: ${aapl.get_revenue():,.0f}")
print(f"Microsoft revenue: ${msft.get_revenue():,.0f}")
```

**Why this API?**
- Multiple companies
- Standardized metrics ensure apples-to-apples comparison
- Simple API for common metrics

---

### Scenario 3: "Get Apple's revenue by product segment"
**Recommended: XBRL API**

```python
from edgar import Company

filing = Company("AAPL").get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Find revenue statement with segments
revenue_stmt = xbrl.statements.get("Revenues")
print(revenue_stmt)  # Shows dimensional breakdown
```

**Why this API?**
- Need dimensional/segment data
- Company Facts and Financials don't include segments
- Full access to structured XBRL data

---

### Scenario 4: "Get footnote details about debt terms"
**Recommended: XBRL API**

```python
from edgar import Company

filing = Company("AAPL").get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Access footnotes
for fact in xbrl.facts:
    if "Debt" in fact.concept and fact.footnote:
        print(f"{fact.concept}: {fact.footnote}")
```

**Why this API?**
- Only XBRL API provides footnote access
- Need detailed qualitative information
- Going beyond just numbers

---

## The Same Task, Three Ways

Here's how to get current year revenue using each API:

### Method 1: Company Facts
```python
company = Company("AAPL")
income = company.income_statement()
revenue = income.get_value("Revenues", period="latest")
print(f"Revenue: ${revenue:,.0f}")
```
**Pros**: Simplest, one company object
**Cons**: Less standardized concept names

### Method 2: Financials
```python
company = Company("AAPL")
financials = company.get_financials()
revenue = financials.get_revenue()
print(f"Revenue: ${revenue:,.0f}")
```
**Pros**: Standardized, guaranteed to work across companies
**Cons**: Two API calls

### Method 3: XBRL
```python
filing = Company("AAPL").get_filings(form="10-K").latest()
statements = filing.xbrl().statements
income = statements.income_statement
revenue = income.get_fact_value("Revenues", period_filter="current")
print(f"Revenue: ${revenue:,.0f}")
```
**Pros**: Most control, access to everything
**Cons**: Most verbose, must filter period

---

## When to Upgrade Your Approach

Start simple and upgrade only when you need more power:

### Start: Company Facts API
Begin here for exploratory analysis and single-company work.

```python
company = Company("AAPL")
income = company.income_statement()
```

### Upgrade to: Financials API
When you need:
- Cross-company comparison
- Standardized metric names
- Guaranteed concept availability

```python
companies = [Company(ticker).get_financials()
             for ticker in ["AAPL", "MSFT", "GOOGL"]]
```

### Upgrade to: XBRL API
When you need:
- Segment/dimension data
- Footnotes and context
- Custom or rare concepts
- Maximum control over data

```python
xbrl = filing.xbrl()
statements = xbrl.statements
```

---

## Common Mistakes

### Mistake 1: Using XBRL for simple tasks
```python
# DON'T: Too complex for this task
filing = Company("AAPL").get_filings(form="10-K").latest()
xbrl = filing.xbrl()
statements = xbrl.statements
income = statements.income_statement
revenue = income.get_fact_value("Revenues")

# DO: Use Company Facts
company = Company("AAPL")
income = company.income_statement()
revenue = income.get_value("Revenues")
```

### Mistake 2: Using Company Facts for cross-company work
```python
# DON'T: Manual standardization
aapl_income = Company("AAPL").income_statement()
msft_income = Company("MSFT").income_statement()
# Now you have to handle different concept names...

# DO: Use Financials API
aapl_fin = Company("AAPL").get_financials()
msft_fin = Company("MSFT").get_financials()
# Standardized getters work across companies
```

### Mistake 3: Expecting segments in Company Facts
```python
# DON'T: Company Facts doesn't have segments
income = company.income_statement()
segments = income.get_segments()  # Won't work

# DO: Use XBRL API for segments
xbrl = filing.xbrl()
# Access dimensional data through XBRL
```

---

## Summary

**Use Company Facts API when:**
- Getting historical data for one company
- Working with standard statements (income, balance, cash flow)
- Speed matters
- You want the simplest code

**Use Financials API when:**
- Comparing multiple companies
- Need standardized metrics
- Building cross-company datasets
- Want guaranteed concept availability

**Use XBRL API when:**
- Need segment/dimension data
- Accessing footnotes
- Working with custom concepts
- Building specialized tools
- Maximum control is required

**General Rule**: Start with the simplest API that meets your needs. You can always upgrade later.

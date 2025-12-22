# Quick Start by Task Type

**Fast routing guide for AI agents** - Find the right approach in < 30 seconds based on your task type.

## Prerequisites

**REQUIRED FIRST STEP:** Set your identity before any API calls:

```python
from edgar import set_identity
set_identity("Your Name your@email.com")  # SEC requirement
```

**Tip:** Use `.to_context()` for token-efficient output (see [SKILL.md](SKILL.md#token-efficient-api-usage)).

## How to Use This Guide

1. **Identify your task type** from the categories below
2. **Follow the pattern** shown for that task
3. **Reference detailed docs** if needed (links provided)

---

## Task Type Decision Tree

```
START → What do you want to do?

├─ COUNT or CHECK existence
│  └─ Use: Core API (len, filter)
│     Time: < 1 minute
│     → Go to: Section 1
│
├─ DISCOVER or SCREEN filings
│  └─ Use: get_filings() + filter()
│     Time: 1-2 minutes
│     → Go to: Section 2
│
├─ ANALYZE CONTENT
│  └─ Use: .text() or .markdown() + AI
│     Time: 2-5 minutes
│     → Go to: Section 3
│
├─ EXTRACT FINANCIAL METRICS
│  └─ Use: Entity Facts API or XBRL
│     Time: 1-2 minutes
│     → Go to: Section 4
│
└─ MONITOR EVENTS
   └─ Use: get_current_filings() + filter
      Time: 1-2 minutes
      → Go to: Section 5
```

---

## Section 1: Counting & Existence Checks

### When to Use
- "How many filings?"
- "Did company X file a Y?"
- "Are there any Z filings?"
- "Count filings by type"

### ❌ Don't Use
- `.text()` methods (wastes tokens)
- AI features (unnecessary)
- Complex parsing (not needed)

### ✅ Pattern

```python
from edgar import get_filings

# Basic count
filings = get_filings(2024, 1, form="10-K")
count = len(filings)  # Simple!

# Existence check
has_filing = len(filings) > 0

# Count by company
company_filings = filings.filter(ticker="AAPL")
count = len(company_filings)
```

### Examples

**"How many crowdfunding filings in the past week?"**
```python
from edgar import get_filings
from datetime import datetime, timedelta

# Calculate date range
start_date = (datetime.now() - timedelta(days=7)).date()

# Get filings (Form C = crowdfunding) and filter by date
filings = get_filings(form="C")
recent = filings.filter(filing_date=f"{start_date}:")  # Efficient!

# Count
count = len(recent)
print(f"{count} crowdfunding filings in past week")
```

**"Did Tesla file a 10-Q this quarter?"**
```python
from edgar import Company

company = Company("TSLA")
filings = company.get_filings(form="10-Q", year=2024)
has_10q = len(filings) > 0
```

### Form Type Lookup
Don't know the form code? See [form-types-reference.md](form-types-reference.md)

**Common mappings:**
- Crowdfunding → C
- IPO → S-1
- Insider trading → 4
- Annual report → 10-K

---

## Section 2: Discovery & Screening

### When to Use
- "Show me all [form type] from [period]"
- "Find companies that filed [X]"
- "List filings where [criteria]"
- "Screen for [conditions]"

### Pattern

```python
from edgar import get_filings

# Get filings for period
filings = get_filings(2024, 1)  # Q1 2024

# Filter by criteria
filtered = filings.filter(
    form="10-K",
    exchange="NASDAQ",
    date="2024-01-01:2024-01-31"
)

# Display results
print(f"Found {len(filtered)} filings")
print(filtered.head(10))  # Show first 10
```

### Examples

**"Show all S-1 filings from February 2024"**
```python
from edgar import get_filings

filings = get_filings(
    2024, 1,  # Q1 2024
    form="S-1",
    filing_date="2024-02-01:2024-02-28"
)
print(f"Found {len(filings)} IPO filings")
```

**"Find tech companies that filed 10-Ks in Q1"**
```python
from edgar import get_filings

filings = get_filings(2024, 1, form="10-K")
tech = filings.filter(
    exchange="NASDAQ",
    ticker=["AAPL", "MSFT", "GOOGL", "META"]
)
```

### Date Filtering

**Specific date range:**
```python
filings.filter(filing_date="2024-01-01:2024-01-31")
```

**Open-ended (from date onwards):**
```python
filings.filter(filing_date="2024-01-01:")
```

**Relative dates (past N days):**
```python
from datetime import datetime, timedelta

start = (datetime.now() - timedelta(days=30)).date()
recent = filings.filter(filing_date=f"{start}:")  # Use .filter()!
```

### Searching Filing Content

**When you need to find specific text INSIDE filings** (not just filter by metadata):

```python
from edgar import get_filings
from datetime import datetime, timedelta

# Get recent proxy statements
start_date = datetime.now() - timedelta(days=30)
filings = get_filings(form="DEF 14A")
recent = filings.filter(filing_date=f"{start_date.strftime('%Y-%m-%d')}:")

# Search each filing's content
results = []
for filing in recent:
    # Search actual filing text (NOT filing.docs.search!)
    matches = filing.search("executive compensation")

    if matches:
        results.append({
            'company': filing.company,
            'filing_date': filing.filing_date,
            'score': matches[0].score,
            'excerpt': str(matches[0])[:200]
        })

print(f"Found {len(results)} companies mentioning 'executive compensation'")
```

**⚠️ Common Mistake**:
```python
# WRONG - This searches API documentation, not filing content!
matches = filing.docs.search("executive compensation")  # ❌

# CORRECT - This searches the actual filing document
matches = filing.search("executive compensation")  # ✅
```

**Performance**: ~1-2 seconds per filing (BM25 search with caching)

---

## Section 3: Content Analysis

### When to Use
- "What does the filing say about [topic]?"
- "Extract [section] from filing"
- "Summarize [content]"
- "Find mentions of [keyword]"

### ✅ Use AI Features
This is when .text() and AI analysis are appropriate!

### Pattern

```python
from edgar import Company

# Get filing
company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]

# Extract content
text = filing.text()          # Plain text (for search)
markdown = filing.markdown()   # Markdown format (better structure)

# Now use AI to analyze the content
# (Pass text/markdown to your LLM)
```

### Examples

**"What are Apple's biggest risks?"**
```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]

# Get Item 1A (Risk Factors)
text = filing.text()
# Search for "Item 1A" or "Risk Factors" section
# Use AI to extract and rank risks
```

**"Extract revenue recognition policy"**
```python
filing = company.get_filings(form="10-K")[0]
markdown = filing.markdown()
# AI prompt: "Extract the revenue recognition accounting policy from this 10-K"
```

### Token Estimates
- Full 10-K text: ~50,000-100,000 tokens
- Specific section: ~5,000-15,000 tokens
- Use markdown for better structure preservation

### Search Within Filing
```python
# Simple text search
results = filing.search("revenue recognition")

# See matches
for result in results[:5]:
    print(result)
```

---

## Section 4: Financial Metrics

### When to Use
- "What was [company]'s revenue?"
- "Show me [metric] trends"
- "Compare financials across companies"
- "Get balance sheet data"

### ❌ Don't Use
- Content parsing (structured data available!)
- AI for extraction (data is already structured)

### ✅ Pattern: Entity Facts API (Fastest)

```python
from edgar import Company

company = Company("AAPL")

# Multi-period trends (single API call!)
income = company.income_statement(periods=3)  # 3 fiscal years
balance = company.balance_sheet(periods=3)
cash_flow = company.cash_flow_statement(periods=3)

# Quarterly data
quarterly = company.income_statement(periods=4, annual=False)
```

### Alternative: XBRL from Specific Filing

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]

# Parse XBRL
xbrl = filing.xbrl()
statements = xbrl.statements

# Get specific statements
income = statements.income_statement()
balance = statements.balance_sheet()
cash_flow = statements.cash_flow_statement()
```

### Helper Functions

```python
from edgar.ai.helpers import (
    get_revenue_trend,
    compare_companies_revenue,
    get_filing_statement
)

# Quick revenue trend
income = get_revenue_trend("AAPL", periods=3)

# Compare multiple companies
results = compare_companies_revenue(["AAPL", "MSFT", "GOOGL"], periods=3)

# Specific statement from filing
balance = get_filing_statement("AAPL", 2024, "10-K", "balance")
```

### Examples

**"What was Microsoft's R&D spending over 3 years?"**
```python
from edgar import Company

company = Company("MSFT")
income = company.income_statement(periods=3)

# Find R&D row in the statement
# (Row names vary: "ResearchAndDevelopment", "R&D", etc.)
print(income)  # Display to see available rows
```

**"Compare Tesla and Ford's revenue"**
```python
from edgar.ai.helpers import compare_companies_revenue

results = compare_companies_revenue(["TSLA", "F"], periods=3)
print("Tesla:")
print(results["TSLA"])
print("\nFord:")
print(results["F"])
```

---

## Section 5: Event Monitoring

### When to Use
- "Which companies filed about [event]?"
- "Recent [form type] filings"
- "CEO changes this month"
- "Latest insider transactions"

### Pattern: Current Filings + Filtering

```python
from edgar import get_current_filings

# Get recent filings (last ~24 hours)
current = get_current_filings()

# Filter by form type
reports = current.filter(form=["10-K", "10-Q"])
insider = current.filter(form="4")
events = current.filter(form="8-K")

# Filter by company
tech = current.filter(ticker=["AAPL", "MSFT", "GOOGL"])
```

### Examples

**"Which companies filed 8-Ks about CEO changes today?"**
```python
from edgar import get_current_filings

# Get recent 8-Ks
current = get_current_filings()
eightks = current.filter(form="8-K")

# Need to check content for Item 5.02 (CEO changes)
for filing in eightks:
    text = filing.text()
    if "Item 5.02" in text or "Chief Executive Officer" in text:
        print(f"{filing.company} - {filing.filing_date}")
```

**"Show insider selling at Nvidia this month"**
```python
from edgar import Company
from datetime import datetime, timedelta

company = Company("NVDA")
start_date = (datetime.now() - timedelta(days=30)).date()

# Get Form 4 filings (insider transactions) and filter by date
form4s = company.get_filings(form="4")
recent = form4s.filter(filing_date=f"{start_date}:")  # Efficient!

# Analyze transactions using Form4 data object
for filing in recent[:10]:  # First 10 filings
    form4 = filing.obj()

    # Check for large sales (> $1M)
    if form4.common_stock_sales is not None and not form4.common_stock_sales.empty:
        for idx, sale in form4.common_stock_sales.iterrows():
            value = sale['Shares'] * sale['Price']
            if value > 1_000_000:
                print(f"{form4.insider_name}: Sold ${value:,.2f} on {sale['Date']}")
```

---

## When to Use get_filings() vs Company()

### Use `get_filings()` when:
- ✅ You DON'T know which companies
- ✅ Screening across many companies
- ✅ Pattern discovery
- ✅ Specific time period

```python
filings = get_filings(2024, 1, form="S-1")  # All IPOs in Q1
```

### Use `Company()` when:
- ✅ You KNOW the company ticker/name
- ✅ Company-specific analysis
- ✅ Historical filings for one entity
- ✅ Financial data trends

```python
company = Company("AAPL")
filings = company.get_filings(form="10-K")
```

---

## Common Anti-Patterns

### ❌ DON'T: Use .text() for counting
```python
# WRONG - wastes tokens and time
for filing in filings:
    text = filing.text()  # Don't need content to count!
count = len(filings)
```

### ✅ DO: Count directly
```python
count = len(filings)  # Just count!
```

---

### ❌ DON'T: Parse financials from text
```python
# WRONG - hard to parse, error-prone
text = filing.text()
# Try to regex out revenue numbers... NO!
```

### ✅ DO: Use structured data
```python
# RIGHT - data is already structured
xbrl = filing.xbrl()
income = xbrl.statements.income_statement()
# Revenue is a structured row
```

---

### ❌ DON'T: Make multiple API calls for trends
```python
# WRONG - slow, many API calls
filing1 = company.get_filings(form="10-K")[0]
filing2 = company.get_filings(form="10-K")[1]
filing3 = company.get_filings(form="10-K")[2]
# Parse each one separately...
```

### ✅ DO: Use Entity Facts API
```python
# RIGHT - single API call, pre-aggregated
income = company.income_statement(periods=3)
# All 3 years in one call!
```

---

## Quick Reference Card

| Question Type | API | Example | Tokens |
|--------------|-----|---------|--------|
| "How many?" | `len(get_filings(...))` | Count filings | 0 |
| "Show all" | `get_filings().filter()` | Screen filings | 0 |
| "What does it say?" | `filing.text()` | Content analysis | 50K+ |
| "What was revenue?" | `company.income_statement()` | Financial data | 500-1K |
| "Recent filings?" | `get_current_filings()` | Monitor events | 0 |

---

## Next Steps

After finding your pattern here:

1. **Need form codes?** → See [form-types-reference.md](form-types-reference.md)
2. **Need detailed API docs?** → See [skill.md](skill.md)
3. **Need complete examples?** → See [workflows.md](workflows.md)
4. **Need token estimates?** → See [objects.md](objects.md)

---

## Troubleshooting

### "I don't know the form type"
→ Check [form-types-reference.md](form-types-reference.md) - Natural language index

### "Date filtering isn't working"
→ Use format `"YYYY-MM-DD:YYYY-MM-DD"` or `"YYYY-MM-DD:"` for open-ended ranges

### "Results are too large"
→ Use `.head(N)` to limit output: `filings.head(10)`

### "Need specific date range crossing quarters"
→ Use `.filter(filing_date="start_date:")` - works across quarters!

### "Not sure if I need AI features"
→ Ask: "Do I need to READ content?" If no → don't use .text()

---

**Time to Answer:** < 2 minutes for any task type
**Next:** See detailed examples in [skill.md](skill.md)

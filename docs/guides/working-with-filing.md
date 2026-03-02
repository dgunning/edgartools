# Working with SEC Filings — Access Content, Attachments, and Structured Data

This guide shows you how to get, view, and extract data from individual SEC filings using the `Filing` class.

## Getting a Filing

### From a Company

Get filings for a specific company by ticker or CIK:

```python
from edgar import Company

company = Company("AAPL")
filings = company.get_filings(form="10-K")
filing = filings.latest()

print(filing.company)      # "Apple Inc."
print(filing.form)         # "10-K"
print(filing.filing_date)  # "2023-11-03"
```

### From a Filing Search

Search across all filings and pick one:

```python
from edgar import get_filings

# Get all Q1 2024 10-K filings
filings = get_filings(2024, 1, form="10-K")

# Get the first one
filing = filings[0]

# Or get the latest
filing = filings.latest()
```

### By Accession Number

If you know the accession number:

```python
from edgar import get_by_accession_number

filing = get_by_accession_number("0000320193-23-000106")
print(filing.company)  # "Apple Inc."
```

### Direct Construction

Create a Filing object directly (rarely needed):

```python
from edgar import Filing

filing = Filing(
    form='10-Q',
    filing_date='2024-06-30',
    company='Tesla Inc.',
    cik=1318605,
    accession_no='0001628280-24-028839'
)
```

## Filing Properties

### Basic Information

```python
print(f"Company: {filing.company}")
print(f"CIK: {filing.cik}")
print(f"Form: {filing.form}")
print(f"Filing Date: {filing.filing_date}")
print(f"Period: {filing.period_of_report}")
print(f"Accession: {filing.accession_no}")
```

**Output:**
```
Company: Apple Inc.
CIK: 320193
Form: 10-K
Filing Date: 2023-11-03
Period: 2023-09-30
Accession: 0000320193-23-000106
```

### Enhanced Properties (EntityFiling)

When you get a filing from a company, you get an `EntityFiling` with additional properties:

```python
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()

# EntityFiling-specific properties
print(f"Acceptance Time: {filing.acceptance_datetime}")
print(f"File Number: {filing.file_number}")
print(f"Size: {filing.size} bytes")
print(f"Primary Doc: {filing.primary_document}")
print(f"Is XBRL: {filing.is_xbrl}")
print(f"Is Inline XBRL: {filing.is_inline_xbrl}")
```

## Viewing Filings

### Open in Browser

Open the filing in your default web browser:

```python
filing.open()  # Opens primary document
```

Open the SEC filing homepage (shows all documents):

```python
filing.open_homepage()  # Opens index page with all files
```

### View in Console

Display the filing directly in your terminal or Jupyter notebook:

```python
filing.view()
```

This uses Rich formatting to display the filing as close to the original as possible.

### Serve Locally

Serve the filing on a local HTTP server:

```python
filing.serve(port=8080)
# Opens http://localhost:8080 in browser
```

## Accessing Filing Content

### Get HTML

```python
html = filing.html()
if html:
    print(f"HTML length: {len(html)} characters")
```

### Get Plain Text

```python
text = filing.text()
print(text[:500])  # First 500 characters
```

### Get Markdown

```python
md = filing.markdown()

# Save to file
with open("filing.md", "w") as f:
    f.write(md)
```

With page breaks:

```python
md = filing.markdown(include_page_breaks=True, start_page_number=1)
```

### Get XML

For filings that contain XML (like ownership forms):

```python
xml = filing.xml()
if xml:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
    # Parse XML data
```

### Get Full Submission

Get the complete SEC text submission file including SGML headers:

```python
full_text = filing.full_text_submission()
print(full_text[:1000])
```

## Working with Attachments

SEC filings often include multiple documents beyond the primary filing.

### List All Attachments

```python
attachments = filing.attachments
print(f"Total attachments: {len(attachments)}")

for att in attachments:
    print(f"{att.sequence}: {att.description}")
    print(f"  Type: {att.document_type}")
    print(f"  File: {att.document}")
```

### Get Primary Document

```python
primary = filing.document
print(f"Primary: {primary.description}")
```

### Access Specific Attachment

By index:

```python
first_att = filing.attachments[0]
```

By document name:

```python
att = filing.attachments["ex-10_1.htm"]
```

### Download Attachments

Download a specific attachment:

```python
attachment = filing.attachments[0]
attachment.download("./downloads/")
```

Download all attachments:

```python
filing.attachments.download("./downloads/")
```

### Work with Exhibits

Exhibits are a subset of attachments:

```python
exhibits = filing.exhibits

for exhibit in exhibits:
    print(f"Exhibit {exhibit.exhibit_number}: {exhibit.description}")

    # Download specific exhibit
    if exhibit.exhibit_number == "10.1":
        exhibit.download("./exhibits/")
```

## Extracting Structured Data

### Get XBRL Data

For filings with XBRL (10-K, 10-Q, etc.):

```python
xbrl = filing.xbrl()

if xbrl:
    # Access financial statements
    statements = xbrl.statements
    income = statements.income_statement()
    balance = statements.balance_sheet()
    cashflow = statements.cash_flow_statement()

    print(income)
```

### Preview the Data Object Type

Before calling `obj()`, you can check what type of object a filing will return:

```python
filing.obj_type  # e.g. 'TenK', 'ThirteenF', 'Form4', None
```

This is useful for filtering filings to only those with structured data objects.

### Get Form-Specific Object

Get a structured object based on the form type:

```python
# For 10-K filing
obj = filing.obj()
print(type(obj))  # <class 'edgar.company_reports.TenK'>

# Access financials from TenK object
if obj.financials:
    income = obj.financials.income_statement
    balance = obj.financials.balance_sheet
    print(income)
```

**Important:** The `financials` property exists on form-specific objects (`TenK`, `TenQ`), not on the base `Filing` class.

**Incorrect:**
```python
# This will fail - Filing doesn't have financials
financials = filing.financials  # AttributeError
```

**Correct:**
```python
# Get form-specific object first
tenk = filing.obj()
if tenk.financials:
    financials = tenk.financials
```

### Form-Specific Objects

Different forms return different object types:

| Form | Object Type | Key Features |
|------|-------------|--------------|
| 10-K | TenK | financials, income_statement, balance_sheet, auditor, subsidiaries, reports |
| 10-Q | TenQ | financials, income_statement, balance_sheet, reports |
| 8-K | EightK | items (material events), reports |
| 20-F | TwentyF | financials for foreign issuers, reports |
| 4 | Form4 | insider transactions |
| 13F-HR | ThirteenF | institutional holdings |
| SC 13D/G | Schedule13 | beneficial ownership |
| DEF 14A | ProxyStatement | proxy voting matters |

**Example - 8-K:**
```python
filing = company.get_filings(form="8-K").latest()
eightk = filing.obj()

print(f"Items: {eightk.items}")  # Material events reported
```

**Example - Form 4:**
```python
filing = company.get_filings(form="4").latest()
form4 = filing.obj()

# Access insider transaction data
html = form4.to_html()
```

## Searching Within a Filing

### Simple Text Search

```python
results = filing.search("artificial intelligence")
print(f"Found {len(results)} mentions")

for result in results[:3]:
    print(result[:200])  # First 200 chars of each match
```

### Regex Search

```python
# Search for email addresses
emails = filing.search(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    regex=True
)

print(f"Found {len(emails)} email addresses")
```

### Search for Financial Terms

```python
# Search for revenue mentions
revenue_mentions = filing.search("revenue")

# Search for risk factors
risk_mentions = filing.search("risk factor")

# Case-sensitive regex
critical_terms = filing.search(r'\b(material weakness|restatement)\b', regex=True)
```

## Parsing Document Sections

### Get Available Sections

```python
sections = filing.sections()
for section in sections:
    print(section)
```

### Parse for Structured Search

```python
doc = filing.parse()
# Use parsed document for advanced operations
```

## Saving and Loading

### Save Filing

```python
# Save to directory (auto-generates filename)
filing.save("./data/filings/")

# Save to specific file
filing.save("./data/apple_10k_2023.pkl")
```

### Load Filing

```python
from edgar import Filing

filing = Filing.load("./data/apple_10k_2023.pkl")
print(filing.company)
```

### Export to Dictionary

```python
data = filing.to_dict()
print(data.keys())
```

### Export Summary

```python
import pandas as pd

summary_df = filing.summary()
print(summary_df)
```

## Common Use Cases

### Extract Revenue from Latest 10-K

```python
from edgar import Company

company = Company("MSFT")
filing = company.get_filings(form="10-K").latest()

tenk = filing.obj()
if tenk.financials:
    income = tenk.financials.income_statement
    print(income)
```

### Download All Exhibits

```python
filing = get_by_accession_number("0001234567-24-000001")

for exhibit in filing.exhibits:
    print(f"Downloading {exhibit.exhibit_number}: {exhibit.description}")
    exhibit.download(f"./exhibits/{exhibit.document}")
```

### Search Across Recent 8-K Filings

```python
from edgar import get_filings

filings = get_filings(2024, 1, form="8-K").head(50)

for filing in filings:
    results = filing.search("earnings")
    if results:
        print(f"{filing.company} ({filing.filing_date}): {len(results)} mentions")
```

### Convert Filing to Markdown for LLM Analysis

```python
company = Company("NVDA")
filing = company.get_filings(form="10-K").latest()

# Export to markdown
md = filing.markdown(include_page_breaks=True)

# Save for processing
with open("nvidia_10k_for_analysis.md", "w") as f:
    f.write(md)

print(f"Saved {len(md)} characters to markdown file")
```

### Batch Download Filings

```python
from edgar import get_filings

filings = get_filings(2023, 4, form="10-K").head(100)

for filing in filings:
    try:
        filing.download(data_directory="./raw_filings/")
        print(f"Downloaded: {filing.company}")
    except Exception as e:
        print(f"Error downloading {filing.company}: {e}")
```

## Error Handling

Always check for None before using optional data:

```python
from edgar import get_by_accession_number

try:
    filing = get_by_accession_number("0000320193-23-000106")

    # Check HTML availability
    html = filing.html()
    if html is None:
        print("HTML content not available")
    else:
        print(f"HTML: {len(html)} characters")

    # Check XBRL availability
    xbrl = filing.xbrl()
    if xbrl is None:
        print("No XBRL data available")
    else:
        print("XBRL data available")

    # Check structured object
    obj = filing.obj()
    if obj:
        # Process object
        pass

except Exception as e:
    print(f"Error processing filing: {e}")
```

## Best Practices

1. **Check form type** - Use `filing.form` to determine filing type before processing
2. **Verify XBRL** - Check `filing.is_xbrl` for EntityFiling before extracting structured data
3. **Handle large files** - Some filings are very large; consider streaming for attachments
4. **Cache content** - Store downloaded content locally to avoid repeated API calls
5. **Respect rate limits** - Be mindful of SEC rate limits when processing many filings
6. **Use obj() for structure** - Prefer `filing.obj()` over HTML parsing for structured data

## Performance Tips

**Efficient pattern:**
```python
# Get form-specific object once
obj = filing.obj()

# Check before using
if obj and hasattr(obj, 'financials') and obj.financials:
    income = obj.financials.income_statement
    # Process income statement
```

**Cache expensive operations:**
```python
# Download once, use multiple times
text = filing.text()

# Search multiple times without re-downloading
results1 = filing.search("revenue")
results2 = filing.search("profit")
```

## See Also

- **[Filing API Reference](../api/filing.md)** - Complete Filing class documentation
- **[Filings API Reference](../api/filings.md)** - Working with filing collections
- **[Extract Financial Statements](extract-statements.md)** - Getting financial data from XBRL
- **[Filing Attachments Guide](filing-attachments.md)** - Working with documents and exhibits
- **[Filtering Filings](filtering-filings.md)** - Finding specific filings
- **[Current Filings](current-filings.md)** - Access today's filings

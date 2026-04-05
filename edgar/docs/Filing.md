# Filing

Access individual SEC filing content, documents, and financial data.

## Quick Start

```python
from edgar import Company

# Get a filing
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()

# Access content
text = filing.text()
html = filing.html()
markdown = filing.markdown()

# Get structured data
xbrl = filing.xbrl()
statements = xbrl.statements
income = statements.income_statement()

# Parse as typed object
tenk = filing.obj()
print(tenk.business)
```

## Creating a Filing

### From Company Filings

```python
company = Company("AAPL")
filings = company.get_filings(form="10-K")
filing = filings.latest()
```

### From Global Search

```python
from edgar import get_filings

filings = get_filings(2024, 1, form="10-K")
filing = filings[0]
```

### From Accession Number

```python
from edgar import get_by_accession_number

filing = get_by_accession_number("0000320193-23-000106")
```

### From SGML Source

```python
# From file path
filing = Filing.from_sgml("/path/to/filing.txt")

# From SGML text
filing = Filing.from_sgml_text(full_text_submission)
```

### From Dictionary

```python
data = {
    'cik': 320193,
    'company': 'Apple Inc.',
    'form': '10-K',
    'filing_date': '2023-11-03',
    'accession_number': '0000320193-23-000106'
}
filing = Filing.from_dict(data)
```

## Properties

### Basic Information

| Property | Type | Description |
|----------|------|-------------|
| `cik` | int | Central Index Key |
| `company` | str | Company name |
| `form` | str | Form type (e.g., "10-K") |
| `filing_date` | str | Filing date (YYYY-MM-DD) |
| `accession_no` | str | SEC accession number |
| `accession_number` | str | Alias for accession_no |
| `period_of_report` | str | Reporting period |

### Filing Header

| Property | Type | Description |
|----------|------|-------------|
| `header` | FilingHeader | SGML filing header |

### Documents & Content

| Property | Type | Description |
|----------|------|-------------|
| `document` | Attachment | Primary display document |
| `primary_documents` | List[Attachment] | All primary documents |
| `attachments` | Attachments | All filing attachments |
| `exhibits` | Attachments | Filing exhibits |

### Financial Data

| Property | Type | Description |
|----------|------|-------------|
| `reports` | Reports | Report structure from filing summary (also accessible via `report.reports` on TenK/TenQ/etc.) |
| `statements` | Statements | Statement structure |

### Multi-Entity Filings

| Property | Type | Description |
|----------|------|-------------|
| `is_multi_entity` | bool | True if multiple entities |
| `all_ciks` | List[int] | All CIKs in filing |
| `all_entities` | List[Dict] | All entity information |

### URLs

| Property | Type | Description |
|----------|------|-------------|
| `homepage_url` | str | Filing homepage URL |
| `filing_url` | str | Main document URL |
| `text_url` | str | Text submission URL |
| `base_dir` | str | Base directory URL |

## Methods

### Content Access

#### html()

Get HTML content of primary document.

```python
html = filing.html()
```

Returns HTML string or None if not available.

#### text()

Convert filing to plain text.

```python
text = filing.text()
```

Returns formatted text suitable for reading or analysis.

#### markdown(include_page_breaks=False, start_page_number=0)

Convert filing to markdown format.

```python
# Basic conversion
md = filing.markdown()

# With page breaks
md = filing.markdown(include_page_breaks=True, start_page_number=1)
```

**Parameters:**
- `include_page_breaks` - Include page break markers
- `start_page_number` - Starting page number for breaks

#### full_text_submission()

Get complete SGML text submission.

```python
full_text = filing.full_text_submission()
```

Returns the entire submission file including headers and documents.

#### xml()

Get XML content if primary document is XML.

```python
xml = filing.xml()
```

Returns XML string or None.

### Structured Data

#### xbrl()

Get XBRL financial data.

```python
xbrl = filing.xbrl()
if xbrl:
    statements = xbrl.statements
    income = statements.income_statement()
    balance = statements.balance_sheet()
```

Returns XBRL object or None if not available.

**Note:** For 10-K/10-Q filings, this is the primary way to access financial statements.

#### obj()

Parse filing as typed object based on form type.

```python
# Form-specific objects
tenk = filing.obj()        # TenK for 10-K filings
tenq = filing.obj()        # TenQ for 10-Q filings
eightk = filing.obj()      # EightK for 8-K filings
form4 = filing.obj()       # Form4 for insider trading
proxy = filing.obj()       # ProxyStatement for DEF 14A
```

**Returns by form type:**
- `10-K` → `TenK`
- `10-Q` → `TenQ`
- `8-K` → `EightK`
- `4` → `Form4`
- `DEF 14A` → `ProxyStatement`
- `13F-HR` → `ThirteenF`
- `SC 13D/G` → `Schedule13`
- And more...

#### parse()

Parse HTML into structured Document for advanced search.

```python
document = filing.parse()

# Use for advanced operations
from edgar.documents.search import DocumentSearch
searcher = DocumentSearch(document)
results = searcher.ranked_search("revenue growth", top_k=5)
```

Returns parsed Document object or None. Use this for:
- Advanced search and extraction
- Section-level analysis
- Structured navigation

**Note:** For simple text, use `text()`. For XBRL data, use `xbrl()`.

### Search & Analysis

#### search(query, regex=False)

Search filing content.

```python
# Text search
results = filing.search("revenue recognition")

# Regex search
results = filing.search(r"\b\d+\.\d+%", regex=True)
```

**Parameters:**
- `query` - Search string or regex pattern
- `regex` - Use regex instead of text search

#### sections()

Get HTML sections for analysis.

```python
sections = filing.sections()
for section in sections:
    print(section[:100])
```

### Display & Browser

#### view()

Display filing in terminal with Rich formatting.

```python
filing.view()
```

#### open()

Open filing document in web browser.

```python
filing.open()
```

#### open_homepage()

Open filing homepage in browser.

```python
filing.open_homepage()
```

#### serve(port=8000)

Serve filing on local HTTP server.

```python
server = filing.serve(port=8000)
# Filing accessible at http://localhost:8000
```

### Persistence

#### save(directory_or_file)

Save filing to disk using pickle.

```python
# Save to directory (creates accession_number.pkl)
filing.save("/path/to/directory/")

# Save to specific file
filing.save("/path/to/filing.pkl")
```

**Note:** Automatically loads SGML content before saving for offline access.

#### Filing.load(path)

Load saved filing from pickle file.

```python
filing = Filing.load("/path/to/filing.pkl")
```

### Company Integration

#### get_entity()

Get Company object for this filing.

```python
company = filing.get_entity()
print(company.name)
```

#### as_company_filing()

Convert to EntityFiling with additional metadata.

```python
company_filing = filing.as_company_filing()
```

#### related_filings()

Get all filings related by file number.

```python
related = filing.related_filings()
```

### Export

#### to_dict()

Convert to dictionary.

```python
data = filing.to_dict()
# {'accession_number': '...', 'cik': 320193, ...}
```

#### summary()

Get summary as DataFrame.

```python
df = filing.summary()
```

#### to_context(detail='standard')

Get AI-optimized text representation.

```python
# For LLM consumption
context = filing.to_context('standard')
print(context)
```

**Detail levels:**
- `'minimal'` - Basic info (~100 tokens)
- `'standard'` - Adds actions and methods (~250 tokens)
- `'full'` - Adds documents and XBRL status (~500 tokens)

## Common Workflows

### Extract Financial Data

```python
filing = company.get_filings(form="10-K").latest()

# Via XBRL (recommended)
xbrl = filing.xbrl()
income = xbrl.statements.income_statement()
print(income)

# Via typed object
tenk = filing.obj()
financials = tenk.financials
if financials:
    print(financials.income_statement)
```

### Search Filing Content

```python
# Parse for structured search
document = filing.parse()
from edgar.documents.search import DocumentSearch
searcher = DocumentSearch(document)

# Find relevant sections
results = searcher.ranked_search("risk factors", top_k=3)
for result in results:
    print(result.text[:200])
```

### Access Exhibits

```python
# Get all exhibits
exhibits = filing.exhibits

# Find specific exhibit
ex_21 = [ex for ex in exhibits if "21" in ex.description]
if ex_21:
    content = ex_21[0].download()
```

### Multi-Entity Analysis

```python
# Check if multiple entities
if filing.is_multi_entity:
    print(f"Entities: {len(filing.all_entities)}")
    for entity in filing.all_entities:
        print(f"  {entity['company']} (CIK {entity['cik']})")
```

### Compare to Previous Filing

```python
# Get all filings in series
related = filing.related_filings()

# Compare to previous
if len(related) >= 2:
    current = related[-1]
    previous = related[-2]
    print(f"Current: {current.filing_date}")
    print(f"Previous: {previous.filing_date}")
```

## Error Handling

### No XBRL Data

```python
xbrl = filing.xbrl()
if xbrl is None:
    print("No XBRL data available")
    # Try typed object instead
    obj = filing.obj()
```

### Document Not Available

```python
html = filing.html()
if html is None:
    # Try text version
    text = filing.text()
```

### Network Errors

```python
try:
    filing = get_by_accession_number("0000320193-23-000106")
except Exception as e:
    print(f"Could not retrieve filing: {e}")
```

## Performance Tips

### Cache Parsed Documents

```python
# parse() is cached - reuse the same filing
document = filing.parse()
# Second call returns cached result
document_again = filing.parse()
```

### Use SGML for Offline Access

```python
# Load SGML once
sgml = filing.sgml()

# Access documents from SGML (no network)
html = sgml.html()
attachments = sgml.attachments
```

### Save for Later

```python
# Save filing with all data
filing.save("filing.pkl")

# Load instantly later (no network)
filing = Filing.load("filing.pkl")
```

## See Also

- `filing.docs` - Display this documentation in terminal
- [Filings](Filings.md) - Working with filing collections
- [Company](../entity/docs/Company.md) - Company-level filing access
- [XBRL](../xbrl/docs/XBRL.md) - XBRL financial data

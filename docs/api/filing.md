# Filing API Reference — Access SEC Filing Content, XBRL Data, and Documents

The `Filing` class represents a single SEC filing and provides comprehensive access to its content, structured data, attachments, and metadata.

**Quick example:**
```python
from edgar import get_by_accession_number

filing = get_by_accession_number("0000320193-23-000106")
print(f"{filing.company} {filing.form} filed {filing.filing_date}")

# Access content
text = filing.text()
xbrl = filing.xbrl()

# Get form-specific object
tenk = filing.obj()  # Returns TenK for 10-K filings
```

## Getting a Filing

```python
from edgar import Company, get_filings, get_by_accession_number

# From a company
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()

# From a search
filings = get_filings(2024, 1, form="10-K")
filing = filings[0]

# By accession number
filing = get_by_accession_number("0000320193-23-000106")
```

## Core Properties

### Basic Information

| Property | Type | Description |
|----------|------|-------------|
| `cik` | int | Central Index Key of the filing entity |
| `company` | str | Company name |
| `form` | str | SEC form type (e.g., "10-K", "10-Q", "8-K") |
| `filing_date` | str | Date filed with SEC (YYYY-MM-DD) |
| `accession_no` | str | Unique SEC accession number |
| `accession_number` | str | Alias for `accession_no` |
| `period_of_report` | str | Reporting period end date |

**Example:**
```python
print(filing.cik)              # 320193
print(filing.company)          # "Apple Inc."
print(filing.form)             # "10-K"
print(filing.filing_date)      # "2023-11-03"
print(filing.period_of_report) # "2023-09-30"
```

### Document Properties

| Property | Type | Description |
|----------|------|-------------|
| `document` | Attachment | Primary display document |
| `primary_documents` | List[Attachment] | All primary documents |
| `attachments` | Attachments | All documents and attachments |
| `exhibits` | Attachments | Exhibits only (subset of attachments) |

**Example:**
```python
# Access primary document
doc = filing.document
print(doc.document_type)

# Loop through all attachments
for att in filing.attachments:
    print(f"{att.sequence}: {att.description}")

# Access exhibits
for exhibit in filing.exhibits:
    print(f"Exhibit {exhibit.exhibit_number}: {exhibit.description}")
```

### URL Properties

| Property | Description |
|----------|-------------|
| `homepage_url` | Filing homepage on SEC website |
| `filing_url` | URL to primary filing document |
| `text_url` | URL to text version |
| `base_dir` | Base directory for all filing files |

**Example:**
```python
print(filing.homepage_url)
# https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106-index.html

print(filing.filing_url)
# https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm
```

### Metadata Properties

| Property | Type | Description |
|----------|------|-------------|
| `header` | FilingHeader | Parsed SGML header information |
| `is_multi_entity` | bool | Whether filing involves multiple entities |
| `all_ciks` | List[int] | All CIK numbers in filing |
| `all_entities` | List[str] | All entity names in filing |

## Content Access Methods

### Raw Content

#### html()
```python
def html(self) -> Optional[str]
```
Get HTML content of the primary document.

**Returns:** HTML string or None if not available

**Example:**
```python
html = filing.html()
if html:
    print(f"HTML length: {len(html)} characters")
```

#### text()
```python
def text(self) -> str
```
Convert filing HTML to clean plain text.

**Returns:** Plain text content

**Example:**
```python
text = filing.text()
# Search within text
if "artificial intelligence" in text.lower():
    print("AI mentioned in filing")
```

#### markdown()
```python
def markdown(
    include_page_breaks: bool = False,
    start_page_number: int = 0
) -> str
```
Convert filing to Markdown format.

**Parameters:**
- `include_page_breaks` (bool): Include page break markers
- `start_page_number` (int): Starting page number for page breaks

**Returns:** Markdown formatted content

**Example:**
```python
md = filing.markdown()
with open("filing.md", "w") as f:
    f.write(md)
```

#### xml()
```python
def xml(self) -> Optional[str]
```
Get XML content if filing contains XML data.

**Returns:** XML string or None

**Example:**
```python
xml = filing.xml()
if xml:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
```

#### full_text_submission()
```python
def full_text_submission(self) -> str
```
Get the complete SEC text submission file.

**Returns:** Full submission text including SGML headers

### Structured Data Access

#### xbrl()
```python
def xbrl(self) -> Optional[XBRL]
```
Get XBRL data object if filing contains XBRL.

**Returns:** `XBRL` object or None

**Example:**
```python
xbrl = filing.xbrl()
if xbrl:
    # Access financial statements
    income = xbrl.statements.income_statement()
    balance = xbrl.statements.balance_sheet()
    cashflow = xbrl.statements.cash_flow_statement()
```

**See also:** [XBRL API Reference](xbrl.md), [Extract Financial Statements Guide](../guides/extract-statements.md)

#### obj() / data_object()
```python
def obj(self)
def data_object(self)  # Alias
```
Get form-specific structured object based on filing type.

**Returns:** Form-specific object (TenK, TenQ, EightK, Form4, etc.)

**Form type mappings:**

| Form Type | Return Class | Module |
|-----------|--------------|--------|
| 10-K | TenK | edgar.company_reports |
| 10-Q | TenQ | edgar.company_reports |
| 8-K | EightK | edgar.company_reports |
| 20-F | TwentyF | edgar.company_reports |
| 4 | Form4 | edgar.ownership |
| 3 | Form3 | edgar.ownership |
| 5 | Form5 | edgar.ownership |
| DEF 14A | ProxyStatement | edgar.proxy |
| 13F-HR | ThirteenF | edgar.holdings |
| SC 13D/G | Schedule13 | edgar.ownership |
| NPORT-P | NportFiling | edgar.nport |
| 144 | Form144 | edgar.ownership |

**Example:**
```python
# For a 10-K filing
tenk = filing.obj()
print(type(tenk))  # <class 'edgar.company_reports.TenK'>

# Access financial statements from TenK object
if tenk.financials:
    income = tenk.financials.income_statement
    balance = tenk.financials.balance_sheet
    cashflow = tenk.financials.cash_flow_statement

    # Or use direct properties
    income = tenk.income_statement
    balance = tenk.balance_sheet

# XBRL report pages (also available via filing.reports)
reports = tenk.reports
```

**Important:** The base `Filing` class does **not** have a `financials` property. To access financial data:
- Use `filing.obj().financials` for 10-K/10-Q filings
- Or use `filing.xbrl().statements` for any XBRL filing

**Incorrect:**
```python
# This will fail - Filing has no financials property
financials = filing.financials  # AttributeError
```

**Correct:**
```python
# Get form-specific object first
tenk = filing.obj()
if tenk.financials:
    financials = tenk.financials

# Or use XBRL directly
xbrl = filing.xbrl()
if xbrl:
    statements = xbrl.statements
```

### Parsing and Search

#### parse()
```python
def parse(self) -> Document
```
Parse filing into structured Document for advanced searching.

**Returns:** Parsed `Document` object

**Example:**
```python
doc = filing.parse()
# Use document methods for structured search
```

#### search()
```python
def search(self, query: str, regex: bool = False) -> List[str]
```
Search for text within filing content.

**Parameters:**
- `query` (str): Search term or pattern
- `regex` (bool): Treat query as regex pattern

**Returns:** List of matching text excerpts

**Example:**
```python
# Simple text search
results = filing.search("revenue recognition")
print(f"Found {len(results)} mentions")

# Regex search for emails
emails = filing.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', regex=True)
```

#### sections()
```python
def sections(self) -> List[str]
```
Get list of available document sections.

**Returns:** List of section names/identifiers

**Example:**
```python
sections = filing.sections()
for section in sections:
    print(section)  # "Item 1", "Item 2", etc.
```

#### sgml()
```python
def sgml(self) -> FilingSGML
```
Get parsed SGML structure of filing.

**Returns:** `FilingSGML` object with document structure

**Example:**
```python
sgml = filing.sgml()
for doc in sgml.documents:
    print(f"{doc.type}: {doc.sequence}")
```

## Interactive Methods

### Viewing and Display

#### view()
```python
def view(self)
```
Display filing in console or Jupyter notebook with Rich formatting.

**Example:**
```python
filing.view()  # Shows formatted filing content
```

#### open()
```python
def open(self)
```
Open primary filing document in default web browser.

**Example:**
```python
filing.open()  # Opens filing in browser
```

#### open_homepage()
```python
def open_homepage(self)
```
Open filing homepage (index page) in default web browser.

**Example:**
```python
filing.open_homepage()  # Opens SEC filing index page
```

#### serve()
```python
def serve(self, port: int = 8000)
```
Serve filing on local HTTP server for viewing.

**Parameters:**
- `port` (int): Server port (default: 8000)

**Example:**
```python
filing.serve(port=8080)  # Access at http://localhost:8080
```

## Entity and Related Data

### get_entity()
```python
def get_entity(self) -> Union[Company, Entity]
```
Get Company or Entity object for this filing.

**Returns:** `Company` or `Entity` instance

**Example:**
```python
entity = filing.get_entity()
print(f"Entity: {entity.name}")
print(f"Industry: {entity.industry}")
```

### as_company_filing()
```python
def as_company_filing(self) -> EntityFiling
```
Convert to EntityFiling with enhanced metadata.

**Returns:** `EntityFiling` object

### related_filings()
```python
def related_filings(self) -> Filings
```
Get filings related by file number.

**Returns:** `Filings` collection

## Persistence and Serialization

### Save and Load

#### save()
```python
def save(self, directory_or_file: PathLike)
```
Save filing using pickle serialization.

**Parameters:**
- `directory_or_file`: Directory or file path

**Example:**
```python
# Save to directory
filing.save("./data/filings/")

# Save to specific file
filing.save("./data/apple_10k_2023.pkl")
```

#### load()
```python
@classmethod
def load(cls, path: PathLike) -> Filing
```
Load filing from pickle file.

**Parameters:**
- `path`: Path to pickle file

**Returns:** `Filing` object

**Example:**
```python
filing = Filing.load("./data/apple_10k_2023.pkl")
```

### Data Export

#### to_dict()
```python
def to_dict(self) -> Dict[str, Union[str, int]]
```
Convert to dictionary representation.

**Returns:** Dictionary with filing data

**Example:**
```python
data = filing.to_dict()
print(data.keys())
# dict_keys(['cik', 'company', 'form', 'filing_date', 'accession_no', ...])
```

#### from_dict()
```python
@classmethod
def from_dict(cls, data: Dict) -> Filing
```
Create Filing from dictionary.

**Parameters:**
- `data`: Dictionary with filing information

**Returns:** `Filing` object

#### summary()
```python
def summary(self) -> pd.DataFrame
```
Get filing summary as pandas DataFrame.

**Returns:** DataFrame with filing metadata

#### to_context()
```python
def to_context(self, detail: str) -> str
```
Generate context string for LLM/AI use.

**Parameters:**
- `detail` (str): Level of detail

**Returns:** Context string

### Download

#### download()
```python
def download(
    self,
    data_directory: Optional[str] = None,
    compress: bool = True,
    compression_level: int = 6,
    upload_to_cloud: bool = False,
    disable_progress: bool = False
)
```
Download filing to local storage.

**Parameters:**
- `data_directory`: Download directory (defaults to Edgar data directory)
- `compress`: Compress downloaded files (default: True)
- `compression_level`: gzip level 1-9 (default: 6)
- `upload_to_cloud`: Upload to cloud storage after download
- `disable_progress`: Disable progress display

**Example:**
```python
# Download with defaults
filing.download()

# Custom directory without compression
filing.download(data_directory="./raw_filings", compress=False)
```

## Common Recipes

### Extract revenue from 10-K

```python
from edgar import Company

company = Company("AAPL")
filings = get_filings(2024, 1, form="10-K")
filing = filings.latest()

# Get TenK object
tenk = filing.obj()

# Access financials
if tenk.financials:
    income = tenk.financials.income_statement
    print(income)
```

### Search across multiple filings

```python
from edgar import get_filings

filings = get_filings(2024, 1, form="8-K").head(100)

for filing in filings:
    results = filing.search("cybersecurity")
    if results:
        print(f"{filing.company} ({filing.filing_date}): {len(results)} mentions")
```

### Download exhibits from a filing

```python
filing = get_by_accession_number("0001234567-24-000001")

for exhibit in filing.exhibits:
    print(f"Downloading {exhibit.exhibit_number}: {exhibit.description}")
    exhibit.download(f"./exhibits/{exhibit.document}")
```

### Convert filing to markdown for analysis

```python
filing = company.get_filings(form="10-K").latest()

# Export to markdown
md = filing.markdown(include_page_breaks=True)

# Save for LLM processing
with open("filing_for_analysis.md", "w") as f:
    f.write(md)
```

## Error Handling

```python
try:
    filing = get_by_accession_number("0000320193-23-000106")

    # Check content availability
    html = filing.html()
    if html is None:
        print("HTML not available")

    # Check XBRL availability
    xbrl = filing.xbrl()
    if xbrl is None:
        print("No XBRL data")

    # Get structured object
    obj = filing.obj()

except Exception as e:
    print(f"Error: {e}")
```

## Performance Tips

1. **Check before accessing** - Test for None before processing optional data
2. **Use obj() for structured data** - More efficient than parsing HTML
3. **Cache expensive operations** - Store results of xbrl(), text(), etc.
4. **Filter attachments** - Use `exhibits` property instead of filtering all attachments

**Efficient pattern:**
```python
# Get structured object once
obj = filing.obj()

# Check before using
if obj and obj.financials:
    income = obj.financials.income_statement
    # Process income statement
```

## See Also

- **[Filings API Reference](filings.md)** - Working with filing collections
- **[Company API Reference](company.md)** - Company-specific filing access
- **[XBRL API Reference](xbrl.md)** - XBRL data extraction
- **[Working with Filings Guide](../guides/working-with-filing.md)** - Practical filing operations
- **[Extract Financial Statements](../guides/extract-statements.md)** - Getting financial data
- **[Filing Attachments Guide](../guides/filing-attachments.md)** - Working with documents and exhibits

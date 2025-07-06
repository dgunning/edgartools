# Filing API Reference

The `Filing` class represents a single SEC filing and provides access to its documents, data, and metadata. It serves as the foundation for all filing-related operations in EdgarTools.

## Class Overview

```python
from edgar import Filing

class Filing:
    """Represents a single SEC filing with access to documents and data."""
```

## Constructor

### Filing(cik, company, form, filing_date, accession_no)

Create a Filing instance with basic filing information.

```python
Filing(
    cik: int,
    company: str, 
    form: str,
    filing_date: str,
    accession_no: str)
```

**Parameters:**
- `cik` (int): Central Index Key of the filing entity
- `company` (str): Company name
- `form` (str): SEC form type (e.g., "10-K", "10-Q", "8-K")
- `filing_date` (str): Filing date in YYYY-MM-DD format
- `accession_no` (str): SEC accession number

**Example:**
```python
filing = Filing(
    cik=320193,
    company="Apple Inc.", 
    form="10-K",
    filing_date="2023-11-03",
    accession_no="0000320193-23-000106"
)
```

## Core Properties

### Basic Information

#### cik
```python
@property
def cik(self) -> int:
    ...
```
Central Index Key of the filing entity.

```python
print(filing.cik)  # 320193
```

#### company
```python
@property  
def company(self) -> str:
    ...
```
Name of the company that filed the document.

```python
print(filing.company)  # "Apple Inc."
```

#### form
```python
@property
def form(self) -> str:
    ...
```
SEC form type.

```python
print(filing.form)  # "10-K"
```

#### filing_date
```python
@property
def filing_date(self) -> str:
    ...
```
Date the filing was submitted to the SEC.

```python
print(filing.filing_date)  # "2023-11-03"
```

#### accession_no / accession_number
```python
@property
def accession_no(self) -> str:
    ...

@property
def accession_number(self) -> str:  # Alias
    ...
```
SEC accession number - unique identifier for the filing.

```python
print(filing.accession_no)  # "0000320193-23-000106"
```

#### period_of_report
```python
@property
def period_of_report(self) -> str:
    ...
```
The reporting period for the filing.

```python
print(filing.period_of_report)  # "2023-09-30"
```

### Document Access

#### document
```python
@property
def document(self) -> Attachment:
    ...
```
Primary display document (usually the main HTML filing).

```python
primary_doc = filing.document
print(primary_doc.document_type)  # "10-K"
```

#### primary_documents
```python
@property
def primary_documents(self) -> List[Attachment]:
    ...
```
All primary documents in the filing.

```python
for doc in filing.primary_documents:
    print(f"{doc.sequence}: {doc.description}")
```

#### attachments
```python
@property
def attachments(self) -> Attachments:
    ...
```
All attachments and documents in the filing.

```python
attachments = filing.attachments
print(f"Total attachments: {len(attachments)}")

# Loop through attachments
for attachment in attachments:
    print(f"{attachment.sequence}: {attachment.description}")
```

#### exhibits
```python
@property
def exhibits(self) -> Attachments
```
All exhibits in the filing (subset of attachments).

```python
exhibits = filing.exhibits
for exhibit in exhibits:
    print(f"Exhibit {exhibit.exhibit_number}: {exhibit.description}")
```

## Content Access Methods

### HTML and Text Content

#### html()
```python
def html(self) -> Optional[str]
```
Get the HTML content of the primary document.

**Returns:** HTML content as string or None if not available

**Example:**
```python
html_content = filing.html()
if html_content:
    print(f"HTML length: {len(html_content)} characters")
```

#### text()
```python
def text(self) -> str
```
Convert the filing HTML to clean plain text.

**Returns:** Plain text content

**Example:**
```python
text_content = filing.text()
print(text_content[:500])  # First 500 characters
```

#### markdown()
```python
def markdown(self) -> str
```
Convert the filing to Markdown format.

**Returns:** Markdown formatted content

**Example:**
```python
markdown_content = filing.markdown()
# Save to file
with open("filing.md", "w") as f:
    f.write(markdown_content)
```

#### xml()
```python
def xml(self) -> Optional[str]
```
Get XML content if the filing contains XML data.

**Returns:** XML content or None

**Example:**
```python
xml_content = filing.xml()
if xml_content:
    # Process XML data
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_content)
```

#### full_text_submission()
```python
def full_text_submission(self) -> str
```
Get the complete text submission file.

**Returns:** Full submission text

### Structured Data Access

#### xbrl()
```python
def xbrl(self) -> Optional[XBRL]
```
Get XBRL document if the filing contains XBRL data.

**Returns:** `XBRL` object or None

**Example:**
```python
xbrl = filing.xbrl()
if xbrl:
    # Access financial statements
    statements = xbrl.statements
    balance_sheet = statements.balance_sheet()
    income_statement = statements.income_statement()
```

#### obj() / data_object()
```python
def obj(self)
def data_object(self)  # Alias
```
Get structured data object based on the filing form type.

**Returns:** Form-specific object (TenK, TenQ, EightK, etc.)

**Example:**
```python
# For 10-K filing
tenk = filing.obj()
print(type(tenk))  # <class 'edgar.company_reports.TenK'>

# Access financial data
financials = tenk.financials
if financials:
    revenue = financials.income_statement().loc['Revenue']
```

#### financials
```python
@property
def financials(self) -> Optional[Financials]
```
Extract financial statements if available (for XBRL filings).

**Returns:** `Financials` object or None

**Example:**
```python
financials = filing.financials
if financials:
    balance_sheet = financials.balance_sheet
    income_statement = financials.income
    cash_flow = financials.cash_flow
```

### Parsing and Metadata

#### header
```python
@property
def header(self) -> FilingHeader
```
Parsed SGML header information.

**Example:**
```python
header = filing.header
print(header.acceptance_datetime)
print(header.filer_info)
```

#### sgml()
```python
def sgml(self) -> FilingSGML
```
Get parsed SGML structure of the filing.

**Returns:** `FilingSGML` object with parsed document structure

**Example:**
```python
sgml = filing.sgml()
for doc in sgml.documents:
    print(f"Document type: {doc.type}")
```

## URL and File Properties

### URLs

#### homepage_url / url
```python
@property
def homepage_url(self) -> str

@property
def url(self) -> str  # Alias
```
URL to the filing homepage on SEC website.

**Example:**
```python
print(filing.homepage_url)
# https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106-index.html
```

#### filing_url
```python
@property
def filing_url(self) -> str
```
URL to the primary filing document.

**Example:**
```python
print(filing.filing_url)
# https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm
```

#### text_url
```python
@property
def text_url(self) -> str
```
URL to the text version of the filing.

**Example:**
```python
print(filing.text_url)
# https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106.txt
```

#### base_dir
```python
@property
def base_dir(self) -> str
```
Base directory URL for all filing files.

**Example:**
```python
print(filing.base_dir)
# https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/
```

## Interactive Methods

### Viewing and Display

#### view()
```python
def view(self)
```
Display the filing content in console or Jupyter notebook.

**Example:**
```python
filing.view()  # Displays formatted filing content
```

#### open()
```python
def open(self)
```
Open the primary filing document in your default web browser.

**Example:**
```python
filing.open()  # Opens filing in browser
```

#### open_homepage()
```python
def open_homepage(self)
```
Open the filing homepage in your default web browser.

**Example:**
```python
filing.open_homepage()  # Opens filing index page
```

#### serve()
```python
def serve(self, port: int = 8000)
```
Serve the filing on a local HTTP server for viewing.

**Parameters:**
- `port` (int): Port number for the server (default: 8000)

**Example:**
```python
filing.serve(port=8080)  # Serves on http://localhost:8080
```

## Search and Analysis

### search()
```python
def search(self, query: str, regex: bool = False) -> List[str]
```
Search for text within the filing content.

**Parameters:**
- `query` (str): Search term or pattern
- `regex` (bool): Whether to treat query as regex (default: False)

**Returns:** List of matching text excerpts

**Example:**
```python
# Simple text search
results = filing.search("revenue")
print(f"Found {len(results)} mentions of 'revenue'")

# Regex search
email_results = filing.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', regex=True)
```

### sections()
```python
def sections(self) -> List[str]
```
Get available document sections.

**Returns:** List of section names

**Example:**
```python
sections = filing.sections()
for section in sections:
    print(section)
# "Item 1", "Item 2", "Part II", etc.
```

## Entity and Related Data

### get_entity()
```python
def get_entity(self)
```
Get the Company/Entity object for this filing.

**Returns:** `Company` or `Entity` object

**Example:**
```python
entity = filing.get_entity()
print(f"Entity: {entity.name}")
print(f"Industry: {entity.industry}")
```

### as_company_filing()
```python
def as_company_filing(self)
```
Convert to EntityFiling with additional metadata.

**Returns:** `EntityFiling` object with enhanced properties

### related_filings()
```python
def related_filings(self)
```
Get related filings by file number.

**Returns:** Related filings

## Persistence and Serialization

### Save and Load

#### save()
```python
def save(self, directory_or_file: PathLike)
```
Save the filing using pickle serialization.

**Parameters:**
- `directory_or_file`: Directory to save in or specific file path

**Example:**
```python
# Save to directory
filing.save("./filings/")

# Save to specific file
filing.save("./apple_10k_2023.pkl")
```

#### load()
```python
@classmethod
def load(cls, path: PathLike) -> 'Filing'
```
Load a filing from a pickle file.

**Parameters:**
- `path`: Path to the pickle file

**Returns:** `Filing` object

**Example:**
```python
loaded_filing = Filing.load("./apple_10k_2023.pkl")
```

### Data Conversion

#### to_dict()
```python
def to_dict(self) -> Dict[str, Union[str, int]]
```
Convert filing to dictionary representation.

**Returns:** Dictionary with filing data

**Example:**
```python
filing_dict = filing.to_dict()
print(filing_dict.keys())
# dict_keys(['cik', 'company', 'form', 'filing_date', 'accession_no', ...])
```

#### from_dict()
```python
@classmethod
def from_dict(cls, data: Dict) -> 'Filing'
```
Create a Filing from dictionary data.

**Parameters:**
- `data`: Dictionary with filing information

**Returns:** `Filing` object

#### summary()
```python
def summary(self) -> pd.DataFrame
```
Get filing summary as a pandas DataFrame.

**Returns:** DataFrame with filing information

**Example:**
```python
summary_df = filing.summary()
print(summary_df)
```

## Specialized Filing Classes

### EntityFiling

Enhanced filing class with additional entity-specific properties:

```python
from edgar.entity.filings import EntityFiling

# Additional properties available:
filing.report_date           # Report date
filing.acceptance_datetime   # SEC acceptance timestamp  
filing.file_number          # SEC file number
filing.items                # Filing items
filing.size                 # Filing size in bytes
filing.primary_document     # Primary document filename
filing.is_xbrl              # Whether contains XBRL
filing.is_inline_xbrl       # Whether contains inline XBRL
```

### Form-Specific Classes

#### TenK, TenQ, TwentyF
Enhanced classes for annual and quarterly reports:

```python
from edgar.company_reports import TenK, TenQ

tenk = filing.obj()  # Returns TenK for 10-K filings

# Enhanced functionality
tenk.financials              # Financial statements
tenk.income_statement        # Direct access to income statement
tenk.balance_sheet          # Direct access to balance sheet
tenk.cash_flow_statement    # Direct access to cash flow

# Access specific items
tenk.items                  # Available items list
tenk["Item 1"]              # Business description
tenk["Item 7"]              # MD&A section

# Chunked document access
doc = tenk.doc              # Parsed document with sections
```

#### EightK
Enhanced class for current reports:

```python
from edgar.company_reports import EightK

eightk = filing.obj()       # Returns EightK for 8-K filings
eightk.items               # Material event items
```

#### Form3, Form4, Form5
Insider ownership filings:

```python
from edgar.ownership import Form4

form4 = filing.obj()        # Returns Form4 for Form 4 filings
form4.to_html()            # Generate HTML representation
```

## Error Handling

```python
try:
    # Access filing content
    html = filing.html()
    if html is None:
        print("HTML content not available")
    
    # Access XBRL data
    xbrl = filing.xbrl()
    if xbrl is None:
        print("XBRL data not available")
    
    # Access financials
    financials = filing.financials
    if financials is None:
        print("Financial statements not available")
        
except Exception as e:
    print(f"Error processing filing: {e}")
```

## Performance Tips

1. **Cache content** - Store HTML/text content if accessing multiple times
2. **Use specific data access** - Use `obj()` for structured data instead of parsing HTML
3. **Filter attachments** - Use `exhibits` property instead of filtering all `attachments`
4. **Check availability** - Test for None before accessing optional properties

```python
# Efficient pattern
if filing.financials:
    revenue = filing.financials.income.loc['Revenue']
else:
    # Fallback to text parsing
    text = filing.text()
    # Parse revenue from text
```

## Complete Example

```python
from edgar import get_filings

# Get a recent 10-K filing
filings = get_filings(form="10-K", limit=1)
filing = filings[0]

# Basic information
print(f"Company: {filing.company}")
print(f"Form: {filing.form}")
print(f"Filing Date: {filing.filing_date}")
print(f"Accession: {filing.accession_no}")

# Access structured data
tenk = filing.obj()
if tenk.financials:
    print("\nFinancial Data Available:")
    income = tenk.financials.income
    revenue = income.loc['Revenue'].iloc[0] if 'Revenue' in income.index else None
    if revenue:
        print(f"Revenue: ${revenue/1e9:.1f}B")

# Search within filing
search_results = filing.search("risk factors")
print(f"\nFound {len(search_results)} mentions of 'risk factors'")

# Access attachments
print(f"\nAttachments: {len(filing.attachments)}")
print(f"Exhibits: {len(filing.exhibits)}")

# XBRL analysis
xbrl = filing.xbrl()
if xbrl:
    print("\nXBRL Data Available:")
    statements = xbrl.statements
    balance_sheet = statements.balance_sheet()
    print(f"Balance sheet periods: {len(balance_sheet.to_dataframe().columns)-1}")

# Save for later use
filing.save("./my_filing.pkl")
```

## See Also

- **[Company API Reference](company.md)** - Working with companies
- **[Filings API Reference](filings.md)** - Working with filing collections
- **[Working with Filings Guide](../guides/working-with-filing.md)** - Filing operations
- **[Extract Financial Statements](../guides/extract-statements.md)** - Getting financial data
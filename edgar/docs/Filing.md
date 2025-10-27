# Filing Class Documentation

## Overview

The `Filing` class is the core object in edgartools for working with individual SEC filings. It provides comprehensive access to filing content, metadata, documents, and related functionality, making it easy to analyze and extract data from SEC filings.

## Common Actions

Quick reference for the most frequently used Filing methods:

### Access Filing Content
```python
# Get HTML content
html = filing.html()

# Get plain text
text = filing.text()

# Get markdown formatted content
markdown = filing.markdown()
```

### Get Structured Data
```python
# Get form-specific object (10-K, 10-Q, 8-K, etc.)
report = filing.obj()

# Get XBRL financial data
xbrl = filing.xbrl()
```

### View in Browser
```python
# Open filing in web browser
filing.open()
```

### Get Attachments
```python
# Access all filing attachments
attachments = filing.attachments
```

## Constructor

```python
Filing(cik: int, company: str, form: str, filing_date: str, accession_no: str)
```

**Parameters:**
- `cik`: Company's Central Index Key (integer)
- `company`: Company name (string) 
- `form`: SEC form type (e.g., "10-K", "8-K", "DEF 14A")
- `filing_date`: Date of filing (YYYY-MM-DD format)
- `accession_no`: Unique SEC accession number

## Core Properties

| Property | Type | Description |
|----------|------|-------------|
| `cik` | int | Company's Central Index Key |
| `company` | str | Company name |
| `form` | str | SEC form type |
| `filing_date` | str | Filing date |
| `accession_no` | str | SEC accession number |
| `accession_number` | str | Alias for accession_no |

## Document Access

### Primary Documents
- **`document`** - The primary display document (HTML/XHTML)
- **`primary_documents`** - List of all primary documents
- **`attachments`** - All filing attachments
- **`exhibits`** - Filing exhibits

### Content Formats
- **`html()`** - HTML content of the primary document
- **`xml()`** - XML content of the primary document  
- **`text()`** - Plain text version of the document
- **`markdown()`** - Markdown formatted version

## Financial Data Access

### XBRL Data
```python
# Access structured financial data
filing.xbrl()  # Returns XBRLInstance with financial statements
filing.statements  # Direct access to financial statements
```

### SGML Data
```python
# Access SGML filing data
filing.sgml()  # Returns SGMLFiling object
```

## Navigation & URLs

| Property/Method | Description |
|----------------|-------------|
| `homepage` | Filing homepage information |
| `homepage_url` | URL to the filing homepage |
| `filing_url` | URL to the main filing document |
| `text_url` | URL to the text version |
| `base_dir` | Base directory URL for the filing |

## Search & Analysis

### Content Search
```python
# Search filing content
results = filing.search("revenue recognition", regex=False)

# Search with regex
results = filing.search(r"\b\d+\.\d+%", regex=True)
```

### Document Structure
- **`sections()`** - Get HTML sections for advanced search
- **`period_of_report`** - Get the reporting period

## Entity Relationships

### Company Integration
```python
# Get the associated Company object
company = filing.get_entity()

# Convert to company filing with additional data
company_filing = filing.as_company_filing()

# Find related filings
related = filing.related_filings()
```

## Display & Interaction

### Console Display
```python
# Rich console display
filing.view()  # Display in console with rich formatting

# String representations
str(filing)    # Concise string representation
repr(filing)   # Detailed representation
```

### Browser Integration
```python
# Open filing in web browser
filing.open()           # Open main document
filing.open_homepage()  # Open filing homepage

# Serve filing locally
filing.serve(port=8000)  # Serve on localhost:8000
```

## Data Export & Persistence

### Export Formats
```python
# Convert to different formats
filing_dict = filing.to_dict()      # Dictionary
filing_df = filing.to_pandas()      # DataFrame
summary_df = filing.summary()       # Summary DataFrame
```

### Save & Load
```python
# Save filing for later use
filing.save("my_filing.pkl")        # Save to file
filing.save("/path/to/directory/")  # Save to directory

# Load saved filing
loaded_filing = Filing.load("my_filing.pkl")
```

## Class Methods

### Alternative Constructors
```python
# Create from dictionary
filing = Filing.from_dict(data_dict)

# Create from JSON file
filing = Filing.from_json("filing_data.json")

# Create from SGML data
filing = Filing.from_sgml(sgml_source)
```

## Common Usage Patterns

### Basic Filing Analysis
```python
# Get a filing and explore its content
filing = company.get_filings(form="10-K").latest(1)[0]

# Access financial statements
statements = filing.xbrl()
income_statement = statements.income_statement

# Search for specific content
results = filing.search("risk factors")

# View in browser
filing.open()
```

### Working with Attachments
```python
# Get all attachments
attachments = filing.attachments

# Find specific exhibits
exhibits = filing.exhibits
exhibit_99_1 = [ex for ex in exhibits if "99.1" in ex.description]

# Access exhibit content
if exhibit_99_1:
    content = exhibit_99_1[0].html()
```

### Financial Data Extraction
```python
# Get financial statements
xbrl = filing.xbrl()

# Access different statement types
balance_sheet = xbrl.balance_sheet
income_statement = xbrl.income_statement  
cash_flow = xbrl.cash_flow_statement

# Get specific facts
revenue = xbrl.get_facts("Revenues")
```

## Error Handling

The Filing class handles various edge cases gracefully:

- **Missing documents**: Returns None or empty collections
- **Network errors**: Raises appropriate HTTP exceptions
- **Malformed data**: Provides informative error messages
- **File access**: Handles permissions and missing files

## Integration with Other Classes

The Filing class works seamlessly with other edgartools components:

- **Company**: Get filings from companies, convert back to company context
- **Filings**: Part of filing collections with filtering and search
- **XBRLInstance**: Access structured financial data
- **Attachments**: Work with filing documents and exhibits

## Performance Considerations

- **Lazy loading**: Documents and data are loaded only when accessed
- **Caching**: Network requests are cached to improve performance  
- **Streaming**: Large documents can be processed in chunks
- **Async support**: Some operations support asynchronous execution

This comprehensive API makes the Filing class the primary interface for working with SEC filing data in edgartools.
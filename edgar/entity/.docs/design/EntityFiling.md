# EntityFiling Class Documentation

## Overview

The `EntityFiling` class is an enhanced version of the base `Filing` class that provides additional metadata and functionality specific to SEC entity filings. It extends the core filing capabilities with entity-specific information such as report dates, file numbers, XBRL indicators, and form items.

## Key Enhancements over Filing

- **Extended Metadata**: Additional properties like report date, file number, and document details
- **XBRL Information**: Built-in indicators for XBRL and inline XBRL availability
- **Form Items**: Access to 8-K form items and other structured data
- **Entity Integration**: Enhanced methods for working with entity relationships
- **File Number Tracking**: Ability to find related filings by file number

## Constructor

```python
EntityFiling(cik: int, company: str, form: str, filing_date: str, 
            report_date: str, acceptance_datetime: str, accession_no: str,
            file_number: str, items: str, size: int, primary_document: str,
            primary_doc_description: str, is_xbrl: bool, is_inline_xbrl: bool)
```

**Parameters:**
- `cik`: Company's Central Index Key
- `company`: Company name
- `form`: SEC form type (e.g., "10-K", "8-K")
- `filing_date`: Date when filing was submitted to SEC
- `report_date`: Period end date for the report
- `acceptance_datetime`: SEC acceptance timestamp
- `accession_no`: Unique SEC accession number
- `file_number`: SEC file number
- `items`: Form items (particularly relevant for 8-K filings)
- `size`: Filing size in bytes
- `primary_document`: Primary document filename
- `primary_doc_description`: Description of the primary document
- `is_xbrl`: Whether filing contains XBRL data
- `is_inline_xbrl`: Whether filing uses inline XBRL format

## Enhanced Properties

### Core Filing Information
| Property | Type | Description |
|----------|------|-------------|
| `cik` | int | Company's Central Index Key |
| `company` | str | Company name |
| `form` | str | SEC form type |
| `filing_date` | str | Filing submission date |
| `accession_no` | str | SEC accession number |

### Extended Metadata
| Property | Type | Description |
|----------|------|-------------|
| `report_date` | str | Report period end date |
| `acceptance_datetime` | str | SEC acceptance timestamp |
| `file_number` | str | SEC file number for tracking related filings |
| `items` | str | Form items (8-K items, exhibit numbers) |
| `size` | int | Filing size in bytes |
| `primary_document` | str | Primary document filename |
| `primary_doc_description` | str | Description of primary document |

### XBRL Indicators
| Property | Type | Description |
|----------|------|-------------|
| `is_xbrl` | bool | True if filing contains XBRL data |
| `is_inline_xbrl` | bool | True if filing uses inline XBRL format |

## Enhanced Methods

### Related Filings
```python
# Find all filings with the same file number
related_filings = filing.related_filings()
```

Returns all filings from the same entity that share the same file number, useful for tracking:
- Amended filings
- Related proxy statements
- Series of filings for the same matter

### Entity Integration
```python
# Get the parent entity/company object
entity = filing.get_entity()
```

Inherits all base Filing methods plus enhanced entity context.

## Content Access Methods

EntityFiling inherits all content access methods from the base Filing class:

### Document Formats
```python
# Access filing content in different formats
html_content = filing.html()          # HTML content
xml_content = filing.xml()            # XML content  
text_content = filing.text()          # Plain text
markdown_content = filing.markdown()  # Markdown format
```

### Structured Data
```python
# Access XBRL financial data (if available)
if filing.is_xbrl:
    xbrl_data = filing.xbrl()         # XBRL instance with financial statements
    
# Access SGML data
sgml_data = filing.sgml()             # SGML filing structure
```

### Attachments & Exhibits
```python
# Access filing attachments
attachments = filing.attachments    # All attachments
exhibits = filing.exhibits          # Filing exhibits
documents = filing.document         # The primary filing document
```

## XBRL Integration

### XBRL and Financials
Some filings contain structured financial data in XBRL format, allowing for detailed financial analysis.
```python
# Check if filing has structured financial data
xb = filing.xbrl()
    
# Access financial statements
income_statement = xb.statements.income_statement()
balance_sheet = xb.statements.balance_sheet()
cash_flow = xb.statements.cash_flow_statement()
```


## Form-Specific Features

### 8-K Filings and Items
```python
# Analyze 8-K filing items
if filing.form == "8-K" and filing.items:
    items_list = filing.items.split(",")
    
    for item in items_list:
        item = item.strip()
        if item == "2.02":
            print("Contains earnings announcement")
        elif item == "1.01":
            print("Contains material agreement")
        elif item == "8.01":
            print("Contains other events")
```

### Common 8-K Items
- **1.01**: Entry into Material Definitive Agreement
- **2.02**: Results of Operations and Financial Condition
- **5.02**: Departure/Appointment of Directors or Principal Officers
- **8.01**: Other Events
- **9.01**: Financial Statements and Exhibits

### File Number Analysis
```python
# Track related filings by file number
print(f"File Number: {filing.file_number}")

# Find all related filings
related = filing.related_filings()
print(f"Found {len(related)} related filings")

# Analyze filing series
for related_filing in related:
    print(f"Form: {related_filing.form}, Date: {related_filing.filing_date}")
```

## Display and Navigation

### Browser Integration
```python
# Open filing in web browser
filing.open()                        # Open primary document
filing.home.open()                   # Open filing homepage          
```

### Console Display
```python
# Rich console display
print(filing)                       # Formatted output
filing.view()                       # Alternative display method

# Check filing details
print(f"Company: {filing.company}")
print(f"Form: {filing.form}")
print(f"Filing Date: {filing.filing_date}")
print(f"Report Date: {filing.report_date}")
print(f"Size: {filing.size:,} bytes")
print(f"XBRL: {'Yes' if filing.is_xbrl else 'No'}")
```

## Common Usage Patterns


### Event Analysis with 8-K Filings
```python
# Analyze recent 8-K filings for events
eight_k_filings = entity.get_filings().filter(form="8-K").head(10)

for filing in eight_k_filings:
    print(f"\nDate: {filing.filing_date}")
    print(f"Items: {filing.items}")
    print(f"Description: {filing.primary_doc_description}")
    
    # Check for specific events
    if filing.items and "2.02" in filing.items:
        print("📊 Earnings announcement detected")
    if filing.items and "5.02" in filing.items:
        print("👤 Management change detected")
```


## Data Export and Persistence

### Save and Load
```python
# Save filing for later analysis
filing.save("apple_10k_2023.pkl")

# Load saved filing
loaded_filing = EntityFiling.load("apple_10k_2023.pkl")
```

### Export to Different Formats
```python
# Convert to dictionary
filing_dict = filing.to_dict()

# Convert to pandas DataFrame (single row)
filing_df = filing.to_pandas()

# Get summary information
summary = filing.summary()
```

## Performance Considerations

- **Lazy Loading**: Document content loaded only when accessed
- **Metadata Caching**: Enhanced metadata available without additional API calls
- **XBRL Optimization**: XBRL flags allow skipping non-structured filings
- **Related Filing Queries**: Efficient file number-based relationship tracking

## Error Handling

EntityFiling handles various edge cases gracefully:

- **Missing XBRL**: `is_xbrl` flag prevents unnecessary parsing attempts
- **Null Metadata**: Handles None values in optional fields
- **File Access**: Manages network timeouts and file permissions
- **Invalid Dates**: Provides fallback for malformed date strings

## Integration with Entity Ecosystem

EntityFiling seamlessly integrates with:
- **EntityFilings**: Collections maintain entity context
- **Entity Objects**: Direct access to parent company
- **XBRL Analysis**: Enhanced financial data extraction
- **Filing Relationships**: File number-based linking

The EntityFiling class provides a comprehensive, entity-aware interface for working with individual SEC filings, making it ideal for detailed financial analysis and regulatory research.
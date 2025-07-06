# Working with a Filing

A Filing represents a single SEC filing document in EdgarTools. It provides access to the filing's metadata, content, and attachments. This guide covers everything you need to know about working with Filing objects.

## Getting a Filing

There are several ways to obtain a Filing object:

### From a Filings Collection

```python
from edgar import get_filings

# Get recent filings across all companies
filings = get_filings()
filing = filings[10]  # Get the 11th filing

print(filing)
print(type(filing))  # edgar._filings.Filing
```

### From a Specific Company

```python
from edgar import Company

company = Company("AAPL")
filings = company.get_filings(form="10-K")
filing = filings.latest()

print(filing)
print(type(filing))  # edgar.entity.filings.EntityFiling
```

### Using the find() Function

```python
from edgar import find

# Find by accession number
filing = find("0001641172-25-017130")
```

### Direct Construction

```python
from edgar import Filing

filing = Filing(
    form='10-Q',
    filing_date='2025-06-30',
    company='Polomar Health Services, Inc.',
    cik=1265521,
    accession_no='0001641172-25-017130'
)
```

## Filing Types and Properties

EdgarTools has two main Filing classes with different sets of properties:

### Basic Filing Properties

The basic `Filing` class includes these key properties:

| Property | Description |
|----------|-------------|
| `cik` | Company's Central Index Key |
| `company` | Company name |
| `form` | SEC form type (e.g., "10-K", "8-K") |
| `filing_date` | Date when filing was submitted to SEC |
| `report_date` | Period end date for the report |
| `accession_no` | Unique SEC accession number |

### EntityFiling Properties

When you get a filing from a specific company, you get an `EntityFiling` object (a subclass of `Filing`) with additional properties:

| Property | Description |
|----------|-------------|
| `cik` | Company's Central Index Key |
| `company` | Company name |
| `form` | SEC form type (e.g., "10-K", "8-K") |
| `filing_date` | Date when filing was submitted to SEC |
| `report_date` | Period end date for the report |
| `acceptance_datetime` | SEC acceptance timestamp |
| `accession_no` | Unique SEC accession number |
| `file_number` | SEC file number |
| `items` | Form items (particularly relevant for 8-K filings) |
| `size` | Filing size in bytes |
| `primary_document` | Primary document filename |
| `primary_doc_description` | Description of the primary document |
| `is_xbrl` | Whether filing contains XBRL data |
| `is_inline_xbrl` | Whether filing uses inline XBRL format |

## Accessing Filing Content

### Opening in Browser

Open the main document in your default browser:

```python
filing.open()
```

### Opening the Filing Homepage

View the SEC's landing page for the filing, which links to all documents and data files:

```python
filing.open_homepage()
```

### Viewing in Console/Notebook

Preview the filing content directly in your console or Jupyter notebook:

```python
filing.view()
```

> **Note**: This downloads the HTML content and displays it as close to the original as possible, but may not be perfect. For an exact copy, use `filing.open()`.

### Getting Raw Content

#### HTML Content

```python
html_content = filing.html()
# Returns the filing's HTML content as a string
```

#### Text Content

```python
text_content = filing.text()
# Returns the plain text content of the filing
```

## Working with Attachments

Filings often contain multiple documents and attachments beyond the main filing document.

### Accessing Attachments

```python
attachments = filing.attachments
print(f"Number of attachments: {len(attachments)}")
```

### Looping Through Attachments

```python
for attachment in filing.attachments:
    print(f"Document: {attachment.document}")
    print(f"Description: {attachment.description}")
    print(f"Type: {attachment.type}")
    print("---")
```

### Getting a Specific Attachment

```python
# Get the first attachment
first_attachment = filing.attachments[0]

# Get attachment by document name
attachment = filing.attachments["ex-10_1.htm"]
```

### Viewing Attachment Content

```python
# View text/HTML attachments in console
attachment.view()

# Get attachment content as string
content = attachment.content()
```

### Downloading Attachments

```python
# Download all attachments to a specific folder
filing.attachments.download("/path/to/download/folder")

# Download a specific attachment
attachment.download("/path/to/save/file.htm")
```

## Common Use Cases

### 1. Analyzing Recent 10-K Filings

```python
from edgar import Company

apple = Company("AAPL")
latest_10k = apple.get_filings(form="10-K").latest()

print(f"Filing Date: {latest_10k.filing_date}")
print(f"Report Period: {latest_10k.report_date}")
print(f"XBRL Available: {latest_10k.is_xbrl}")

# View the business section
latest_10k.view()
```

### 2. Processing Multiple Filings

```python
from edgar import get_filings

recent_filings = get_filings(form="8-K", limit=50)

for filing in recent_filings:
    if "earnings" in filing.text().lower():
        print(f"{filing.company} - {filing.filing_date}")
        # Process earnings-related 8-K
```

### 3. Extracting Exhibits

```python
filing = find("0001065280-24-000123")

# Find all exhibits
exhibits = [att for att in filing.attachments if att.document.startswith("ex-")]

for exhibit in exhibits:
    print(f"Exhibit: {exhibit.document}")
    print(f"Description: {exhibit.description}")
    # Save exhibit content
    exhibit.download(f"./exhibits/{exhibit.document}")
```

## Error Handling

When working with filings, handle common exceptions:

```python
from edgar import Filing, EdgarError

try:
    filing = find("invalid-accession-number")
except EdgarError as e:
    print(f"Filing not found: {e}")

try:
    content = filing.html()
except Exception as e:
    print(f"Error downloading content: {e}")
```

## Best Practices

1. **Check Filing Type**: Use `filing.form` to determine the type of filing before processing
2. **Verify XBRL Availability**: Check `filing.is_xbrl` before attempting to extract structured data
3. **Handle Large Files**: Some filings can be very large; consider streaming or partial downloads for large attachments
4. **Cache Content**: Store downloaded content locally to avoid repeated API calls
5. **Respect Rate Limits**: Be mindful of SEC rate limits when processing many filings

## Next Steps

- Learn about [extracting financial statements](extract-statements.md) from XBRL-enabled filings
- Explore [filing attachments](filing-attachments.md) in more detail
- See how to [filter filings](filtering-filings.md) to find specific types of documents
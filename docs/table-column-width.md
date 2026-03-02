# Table Column Width Control for AI-Friendly Text Extraction

When extracting text from SEC filings for AI/LLM processing, table headings and row labels may be truncated if they exceed the default maximum column width. This guide shows how to control table rendering to get complete, untruncated labels.

## Quick Start

```python
from edgar import Company

# Get a filing
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest(1)

# IMPORTANT: filing.obj() returns a TenK object, not a Document
# You need to access the .document property to get text
tenk = filing.obj()
doc = tenk.document  # This is the Document object with text() method

# Now extract text with custom table width
text = doc.text(
    clean=True,
    include_tables=True,
    table_max_col_width=500  # Wider columns to avoid truncation
)
```

## The Problem

By default, tables are rendered with a maximum column width of 200 characters to ensure reasonable formatting. However, SEC filings often contain very long descriptive labels like:

```
"(Decrease) increase to the long-term Supplemental compensation accrual for equity-based compensation"
```

These can get truncated as:

```
"(Decrease) increase to the long-term Supplemental compensation accr..."
```

## The Solution

The `text()` method now accepts a `table_max_col_width` parameter to control table column width:

### Basic Usage

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K").latest(1)

# Get the Document object from the filing
# Method 1: Via TenK/TenQ object (for 10-K/10-Q filings)
tenk = filing.obj()
doc = tenk.document

# Method 2: Direct document parsing (works for any filing)
from edgar.documents import HTMLParser, ParserConfig
html = filing.html()
parser = HTMLParser(ParserConfig(form=filing.form))
doc = parser.parse(html)

# Now use the text() method with table width control
# Default: max_col_width = 200
text = doc.text()

# Wider columns: max_col_width = 500
text_wide = doc.text(table_max_col_width=500)

# Unlimited width: no truncation
text_unlimited = doc.text(table_max_col_width=None)
```

### For AI/LLM Processing

When preparing text for AI models, use wider columns to preserve complete information:

```python
# Get the document
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest(1)
tenk = filing.obj()  # Returns TenK object
doc = tenk.document   # Get the Document object

# Extract text optimized for AI processing
ai_text = doc.text(
    clean=True,                  # Clean and normalize text
    include_tables=True,         # Include table content
    table_max_col_width=500,     # Wide columns, avoid truncation
    max_length=100000            # Optional: limit total length
)

# Send to your LLM
response = openai.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": f"Analyze this 10-K:\n\n{ai_text}"}
    ]
)
```

## API Reference

### Document.text()

```python
def text(
    clean: bool = True,
    include_tables: bool = True,
    include_metadata: bool = False,
    max_length: Optional[int] = None,
    table_max_col_width: Optional[int] = None
) -> str:
    """
    Extract text from document.
    
    Args:
        clean: Clean and normalize text
        include_tables: Include table content in text
        include_metadata: Include metadata annotations
        max_length: Maximum text length (characters)
        table_max_col_width: Maximum column width for table rendering.
                            Default: 200 characters
                            Set higher (e.g., 500) to avoid truncation
                            Set to None for unlimited width
    
    Returns:
        Extracted text with tables rendered according to width setting
    """
```

### Legacy get_text() method

The deprecated `get_text()` method also supports this parameter:

```python
# Note: This is the old API - filing.obj() returns TenK, not Document
# Document objects don't have get_text() anymore, use text() instead
tenk = filing.obj()
doc = tenk.document
text = doc.text(clean=True, table_max_col_width=500)
```

## Use Cases

### 1. Financial Analysis
Long financial descriptions need full context:
```python
tenk = filing.obj()
doc = tenk.document
text = doc.text(table_max_col_width=500)
```

### 2. RAG (Retrieval Augmented Generation)
When building vector embeddings, preserve complete labels:
```python
tenk = filing.obj()
doc = tenk.document
chunks = doc.text(
    clean=True,
    table_max_col_width=None,  # No truncation
    max_length=50000
)
```

### 3. Compliance Review
Legal descriptions must be complete:
```python
tenk = filing.obj()
doc = tenk.document
compliance_text = doc.text(
    clean=False,              # Keep original formatting
    table_max_col_width=None  # Complete labels
)
```

### 4. Token Budget Management
Balance detail with token limits:
```python
tenk = filing.obj()
doc = tenk.document
# For models with ~128k token limit
text = doc.text(
    table_max_col_width=300,  # Moderate width
    max_length=400000         # ~100k tokens
)
```

## Performance Considerations

- **Default (200)**: Fast, readable, good for most use cases
- **Wide (500)**: Slightly slower, better for AI processing
- **Unlimited (None)**: Slowest, use only when necessary

The rendering uses the FastTableRenderer which is ~30x faster than Rich rendering, so even unlimited width is reasonably performant.

## Examples

### Example 1: Comparing widths

```python
tenk = filing.obj()
doc = tenk.document

# Get first table
table = doc.tables[0]

# Render with different widths
from edgar.documents.renderers.fast_table import FastTableRenderer, TableStyle

# Default
style_default = TableStyle.simple()
renderer_default = FastTableRenderer(style_default)
print(renderer_default.render_table_node(table))

# Custom width
style_wide = TableStyle.simple()
style_wide.max_col_width = 500
renderer_wide = FastTableRenderer(style_wide)
print(renderer_wide.render_table_node(table))
```

### Example 2: Extract specific section with wide tables

```python
tenk = filing.obj()
doc = tenk.document

# Get Item 1A with complete table labels
item_1a = doc.get_section("Item 1A")
if item_1a:
    # Note: Section objects also have text() method
    text = item_1a.text(table_max_col_width=500)
    print(text)
```

### Example 3: Custom text extraction pipeline

```python
from edgar.documents.extractors.text_extractor import TextExtractor

# Get document
tenk = filing.obj()
doc = tenk.document

# Create custom extractor
extractor = TextExtractor(
    clean=True,
    include_tables=True,
    include_metadata=False,
    table_max_col_width=500
)

# Extract from document
text = extractor.extract(doc)
```

## Migration from v4.x

If you were previously using workarounds to avoid truncation:

**Old way:**
```python
# Had to manually render each table
tenk = filing.obj()
doc = tenk.document
for table in doc.tables:
    df = table.to_dataframe()
    # Convert to text manually
```

**New way:**
```python
# Just set the width parameter
tenk = filing.obj()
doc = tenk.document
text = doc.text(table_max_col_width=500)
```

## See Also

- [Text Extraction Guide](./text-extraction.md)
- [AI Integration](./ai-integration.md)
- [Table Processing](./tables.md)

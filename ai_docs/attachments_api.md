# Attachments API

## Overview
The Attachments API provides a unified interface for accessing, filtering, and extracting content from all documents (attachments) in an SEC filing. It is built around two main classes:
- `Attachments`: a collection of `Attachment` objects for a filing
- `Attachment`: represents a single document or file within the filing

This API is designed for programmatic analysis of filings, including exhibits, XBRL, HTML, and other document types.

## Key Classes
- `Attachments`: Collection of all attachments in a filing. Supports iteration, filtering, and advanced queries.
- `Attachment`: Represents an individual document. Provides metadata and methods to extract or download content.

## Accessing Attachments
```python
attachments = filing.attachments  # Attachments object
for attachment in attachments:
    print(attachment.sequence_number, attachment.document, attachment.description, attachment.document_type)
    # Access content
    print(attachment.text())   # plain text content
    # Download to a file or directory
    attachment.download("/tmp/")
```

## Filtering and Querying Attachments
The `attachments.query()` method allows powerful filtering using Python-like expressions.

### Supported Attributes
- `document`: filename
- `description`: SEC-provided description
- `document_type`: SEC document type (e.g., 'EX-99.1', 'HTML', etc.)

### Supported Syntax
- Standard Python expressions: `==`, `!=`, `in`, `not in`, `.endswith()`, `.startswith()`, etc.
- Regex matching: `re.match(pattern, attribute)`
- Combine conditions with `and`, `or`, and parentheses

### Examples
```python
# All HTML documents
html_docs = attachments.query("document_type == 'HTML'")

# All exhibits (type starts with EX-)
exhibits = attachments.query("re.match('EX-', document_type)")

# All attachments with 'XBRL' in the description
xbrl_docs = attachments.query("'XBRL' in description")

# Attachments with filename ending in .xml
xml_files = attachments.query("document.endswith('.xml')")

# Attachments with type in a set
ex_types = attachments.query("document_type in ['EX-99.1', 'EX-99', 'EX-99.01']")

# Combine conditions: all exhibits that are also XML
exhibit_xml = attachments.query("re.match('EX-', document_type) and document.endswith('.xml')")

# Chain queries (returns a new Attachments object)
exhibits = attachments.query("re.match('EX-', document_type)")
xml_exhibits = exhibits.query("document.endswith('.xml')")

# Iterate over filtered attachments
for attachment in xml_exhibits:
    print(attachment.document, attachment.description)
```

## Accessing Metadata and Content
Each `Attachment` provides rich metadata and content extraction methods:
- `attachment.document`: filename
- `attachment.description`: description from SEC filing
- `attachment.document_type`: type (e.g., 'EX-99.1', 'HTML', etc.)
- `attachment.text()`: plain text content
- `attachment.download(path)`: download file
- `attachment.is_html()`, `attachment.is_xml()`, `attachment.is_text()`, etc.

## Common Patterns
- Get all exhibits:
  ```python
  exhibits = attachments.exhibits
  ```
- Get the primary HTML or XML document:
  ```python
  primary_html = attachments.primary_html_document
  primary_xml = attachments.primary_xml_document
  ```
- Get a specific attachment by sequence or filename:
  ```python
  att = attachments[1]  # by sequence number
  att = attachments["myfile.htm"]  # by filename
  ```

## Downloading Attachments
Download all attachments to a directory or as a zip archive:
```python
attachments.download("/tmp/filing_docs/")
attachments.download("/tmp/filing.zip", archive=True)
```

## Advanced: Chaining and Query Composition
Because `query()` returns a new `Attachments` object, you can chain filters for advanced selection:
```python
# All XML exhibits
xml_exhibits = attachments.query("re.match('EX-', document_type)").query("document.endswith('.xml')")
```

## Reference
- See the `edgar.attachments` module for full API details.
- Underlying parsing is handled by `SGMLDocument` (internal).

# ChunkedDocument Item Extraction Process

This document explains how the `ChunkedDocument` class in `edgar.files.htmltools` is used to extract items from SEC filings, particularly 10-K documents, and how the new `Document` implementation could replace this functionality.

## Overview

The `ChunkedDocument` class provides functionality to parse HTML from SEC filings and extract specific sections (items) based on their item numbers (e.g., "Item 1", "Item 1A", etc.). It works by:

1. Breaking the HTML into chunks
2. Identifying item headings
3. Creating a mapping of chunks to item numbers
4. Providing access to specific items through indexing

This functionality is essential for extracting specific sections from 10-K, 10-Q, and other structured SEC filings.

## Key Components of the Extraction Process

### 1. ChunkedDocument Class

The `ChunkedDocument` class is initialized with HTML content and a chunking function:

```python
def __init__(self, html: str, chunk_fn: Callable[[List], pd.DataFrame] = chunks2df):
    self.chunks = chunk(html)
    self._chunked_data = chunk_fn(self.chunks)
    self.chunk_fn = chunk_fn
```

- `html`: The HTML content of the SEC filing
- `chunk_fn`: A function that converts chunks to a DataFrame (defaults to `chunks2df`)

### 2. Chunking Process

The HTML is first broken into chunks using the `chunk` function:

```python
@lru_cache(maxsize=8)
def chunk(html: str):
    document = HtmlDocument.from_html(html)
    return list(document.generate_chunks())
```

This leverages `HtmlDocument.from_html()` and its `generate_chunks()` method to divide the HTML into semantic chunks. The `HtmlDocument` class is part of the older implementation that the new `Document` class aims to replace.

### 3. Chunks to DataFrame Conversion

The chunks are then processed into a DataFrame using the `chunks2df` function:

```python
def chunks2df(chunks: List[List[Block]],
              item_detector: Callable[[pd.Series], pd.Series] = detect_int_items,
              item_adjuster: Callable[[pd.DataFrame, Dict[str, Any]], pd.DataFrame] = adjust_detected_items,
              item_structure=None) -> pd.DataFrame:
```

This function:
- Takes the chunks and creates a DataFrame with columns for text, table flags, etc.
- Detects item headings using the specified `item_detector` (default: `detect_int_items`)
- Applies adjustments via `item_adjuster` (default: `adjust_detected_items`)
- Adds metadata like character count, signature detection, etc.
- Forward-fills item numbers so each chunk is associated with an item

### 4. Item Detection

The item detection process uses regular expressions to identify item headings:

```python
int_item_pattern = r"^(Item\s{1,3}[0-9]{1,2}[A-Z]?)\.?"
decimal_item_pattern = r"^(Item\s{1,3}[0-9]{1,2}\.[0-9]{2})\.?"

def detect_int_items(text: pd.Series):
    return text.str.extract(int_item_pattern, expand=False, flags=re.IGNORECASE | re.MULTILINE)

def detect_decimal_items(text: pd.Series):
    return text.str.extract(decimal_item_pattern, expand=False, flags=re.IGNORECASE | re.MULTILINE)
```

These patterns match standard item headings like "Item 1" or "Item 1.01" and extract them from the text.

### 5. Item Adjustment

After initial detection, the `adjust_detected_items` function ensures the items are in the correct sequence and filters out invalid or out-of-sequence items:

```python
def adjust_detected_items(chunk_df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    # Normalize items
    # Find table of contents
    # Process each item in sequence
    # Validate items against expected sequence
```

This function:
- Normalizes item strings to a comparable format
- Locates the table of contents section
- Validates each detected item against the previous and next valid items
- Creates a sequence of valid items

### 6. Item Access

The `ChunkedDocument` class provides access to items through indexing:

```python
def __getitem__(self, item):
    if isinstance(item, int):
        chunks = [self.chunks[item]]
    elif isinstance(item, str):
        chunks = list(self.chunks_for_item(item))
    else:
        return None
    # Convert chunks to text
    # ...
```

This allows direct access to items by their number (e.g., `document["Item 1"]`) and returns the consolidated text for that item.

### 7. Integration with Company Reports

The `ChunkedDocument` is used by the `CompanyReport` and its subclasses (like `TenK`, `TenQ`, etc.) to provide structured access to filing sections:

```python
class CompanyReport:
    @property
    @lru_cache(maxsize=1)
    def chunked_document(self):
        return ChunkedDocument(self._filing.html())
    
    def __getitem__(self, item_or_part: str):
        item_text = self.chunked_document[item_or_part]
        return item_text
```

This enables usage patterns like:

```python
tenk = TenK(filing)
business_description = tenk["Item 1"]  # Gets the business description section
risk_factors = tenk["Item 1A"]         # Gets the risk factors section
```

## Technical Details

### Chunk Creation and Rendering

Chunks are created from the HTML using `HtmlDocument.from_html(html).generate_chunks()`, which:

1. Parses the HTML using BeautifulSoup
2. Extracts blocks of content (text, tables, etc.)
3. Compresses blocks to avoid unnecessary whitespace
4. Groups related blocks into logical chunks

When rendering a chunk, the original HTML structure of tables is preserved through the `_render_blocks_using_old_markdown_tables` function:

```python
def _render_blocks_using_old_markdown_tables(blocks:List[Block]):
    return "".join([
        table_to_markdown(block.table_element) if isinstance(block, TableBlock) else block.get_text()
        for block in blocks
    ]).strip()
```

### Special Cases

The system handles several special cases:

1. **Table of Contents**: Items in the table of contents are identified and excluded from being treated as section headers.
2. **Signatures**: Signature blocks at the end of filings are identified to prevent them from being treated as regular content.
3. **Empty Items**: Logic in `adjust_for_empty_items` handles cases where an item has no content but is followed by another item.
4. **Decimal Items**: The `decimal_chunk_fn` provides specialized handling for filings like 8-K that use decimal item numbers (e.g., "Item 1.01").

### Data Structure

The key data structure is the DataFrame created by `chunks2df`, which contains columns:

- `Text`: The text content of the chunk
- `Table`: Boolean indicating if the chunk is a table
- `Chars`: Character count of the chunk
- `Signature`: Boolean indicating if the chunk is part of a signature block
- `TocLink`: Boolean indicating if the chunk is a table of contents link
- `Toc`: Boolean indicating if the chunk is part of the table of contents
- `Empty`: Boolean indicating if the chunk is empty
- `Item`: The item number associated with the chunk (forward-filled)

## Replacing with the New Document Implementation

The new `Document` class implementation could replace the `ChunkedDocument` functionality by:

1. **Preserving Document Structure**: The new `Document` class already has a node-based structure that preserves document semantics, including headings, text blocks, and tables.

2. **Item Identification**: Implementing an item detection system that leverages the existing heading detection, perhaps with a specialized function that identifies item headings from `HeadingNode` instances.

3. **Item Association**: Creating a system to associate all nodes following an item heading with that item, similar to the forward-filling approach used in `chunks2df`.

4. **Item Access API**: Implementing an indexing system that allows access to items by their number, similar to `ChunkedDocument.__getitem__`.

### Specific Implementation Steps

1. **Create Item Detector**: Create a function that identifies item headings from `HeadingNode` instances based on their content and level:

```python
def identify_item_headings(document: Document) -> Dict[str, int]:
    """Identify item headings in the document and return a mapping of item names to node indices."""
    item_headings = {}
    for i, node in enumerate(document.nodes):
        if node.type == 'heading':
            match = re.match(r'^(Item\s+[0-9]+[A-Z]?)', node.content, re.IGNORECASE)
            if match:
                item_headings[match.group(1).strip()] = i
    return item_headings
```

2. **Create Item Association**: Create a function that associates nodes with their respective items:

```python
def associate_nodes_with_items(document: Document, item_headings: Dict[str, int]) -> Dict[str, List[BaseNode]]:
    """Associate document nodes with their respective items."""
    item_nodes = {}
    item_indices = sorted(item_headings.values())
    
    for i, idx in enumerate(item_indices):
        item_name = next(k for k, v in item_headings.items() if v == idx)
        next_idx = item_indices[i+1] if i+1 < len(item_indices) else len(document.nodes)
        item_nodes[item_name] = document.nodes[idx:next_idx]
    
    return item_nodes
```

3. **Implement Item Access**: Add an indexing method to `Document` that allows access to items:

```python
def get_item(self, item_name: str) -> Optional[str]:
    """Get a specific item from the document by name."""
    item_headings = identify_item_headings(self)
    if item_name not in item_headings:
        return None
        
    item_nodes = associate_nodes_with_items(self, item_headings)
    
    # Convert nodes to text
    return "\n".join(node.content for node in item_nodes[item_name])
```

4. **Integration with Company Reports**: Update the `CompanyReport` class to use the new `Document` implementation:

```python
@property
@lru_cache(maxsize=1)
def document(self):
    html = self._filing.html()
    return Document.parse(html)

def __getitem__(self, item_or_part: str):
    return self.document.get_item(item_or_part)
```

## Conclusion

The `ChunkedDocument` class provides a robust system for extracting items from SEC filings. While the implementation is complex, it handles many edge cases and provides a clean API for accessing specific sections of filings. 

Replacing this functionality with the new `Document` implementation would require preserving the ability to identify item headings, associate content with items, and provide an item access API. However, the new implementation could benefit from the more structured node-based approach, potentially leading to more accurate item extraction and better handling of complex document structures.

The key challenge will be correctly identifying item boundaries, especially in cases where item headings might be nested or where the document structure is complex. Careful testing against a variety of filings will be essential to ensure the new implementation matches or exceeds the capabilities of the current system.
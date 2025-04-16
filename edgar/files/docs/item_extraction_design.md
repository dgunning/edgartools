# SEC Filing Item Extraction - New Design

## Analysis of Current Implementation

### Strengths
1. Simple item access via dictionary-style indexing (`doc["Item 1"]`)
2. Caching mechanisms for performance optimization
3. Robust detection of item headings with regex patterns
4. Sequence validation to ensure correct item ordering
5. Special handling for edge cases (table of contents, signatures)
6. Strong integration with company report classes

### Weaknesses
1. Overreliance on DataFrame as intermediate representation
2. Complex chunking process that operates on strings rather than document structure
3. Text-based pattern matching instead of leveraging semantic document structure
4. Forward-filling item associations rather than using hierarchical structure
5. Limited metadata about items (just text)
6. Mixing of responsibilities (parsing, chunking, indexing, item detection)
7. Tight coupling between chunking and item detection
8. Limited extensibility for new filing types

## Design Principles

For our new implementation, we'll follow these principles from successful software projects:

1. **Single Responsibility Principle**: Each component should have one clearly defined responsibility
2. **Separation of Concerns**: Parsing, structure analysis, and item extraction should be separate
3. **Fluent, Intuitive API**: Provide a clean, discoverable interface
4. **Progressive Disclosure**: Simple operations should be simple, complex operations possible
5. **Rich Models**: Return structured objects with useful methods, not just strings
6. **Immutability**: Operations produce new objects rather than modifying existing ones
7. **Extensibility**: Design for future enhancements and filing types
8. **Performance**: Optimize for common operations with appropriate caching

## New Design

### Core Components

#### 1. `FilingDocument` Class

A high-level wrapper around `Document` that specializes in SEC filing structure:

```python
class FilingDocument:
    """High-level document class specialized for SEC filings."""
    
    def __init__(self, html: str, filing_type: str = None):
        self._document = Document.parse(html)
        self._filing_type = filing_type
        self._index = None  # Lazy-loaded
        self._toc = None    # Lazy-loaded
    
    @property
    def document(self) -> Document:
        """Access the underlying Document instance."""
        return self._document
    
    @property
    def index(self) -> 'DocumentIndex':
        """Get or create the document index."""
        if self._index is None:
            self._index = DocumentIndex.build(self._document, self._filing_type)
        return self._index
    
    @property
    def items(self) -> 'ItemCollection':
        """Access items in the document."""
        return self.index.items
    
    @property
    def table_of_contents(self) -> 'TableOfContents':
        """Get the table of contents for this document."""
        if self._toc is None:
            self._toc = TableOfContents.extract(self._document)
        return self._toc
    
    @property
    def tables(self) -> List['Table']:
        """Get all tables in the document."""
        return [
            Table(node) for node in self._document.nodes 
            if node.type == 'table'
        ]
    
    def __getitem__(self, key: str) -> 'Item':
        """Dictionary-style access to items."""
        return self.items[key]
```

#### 2. `DocumentIndex` Class

Analyzes document structure and builds indices for fast lookup:

```python
class DocumentIndex:
    """Index of document structure for efficient lookups."""
    
    @classmethod
    def build(cls, document: Document, filing_type: str = None) -> 'DocumentIndex':
        """Build an index from a document."""
        index = cls()
        index._build_heading_index(document)
        index._build_item_index(document, filing_type)
        return index
    
    def _build_heading_index(self, document: Document) -> None:
        """Build an index of all headings in the document."""
        # Implementation details...
    
    def _build_item_index(self, document: Document, filing_type: str = None) -> None:
        """Build an index of items in the document."""
        # Implementation details...
    
    @property
    def items(self) -> 'ItemCollection':
        """Get the collection of items in this document."""
        return ItemCollection(self._items)
```

#### 3. `Item` Class

Represents a logical item in a filing with rich functionality:

```python
class Item:
    """Represents a logical item in an SEC filing."""
    
    def __init__(self, 
                 name: str, 
                 heading_node: Optional[HeadingNode],
                 content_nodes: List[BaseNode],
                 metadata: Dict[str, Any] = None):
        self.name = name
        self.heading_node = heading_node
        self.content_nodes = content_nodes
        self.metadata = metadata or {}
    
    @property
    def title(self) -> str:
        """Get the title of this item."""
        if self.heading_node:
            # Extract title from heading
            return self._extract_title(self.heading_node.content)
        return ""
    
    @property
    def text(self) -> str:
        """Get the text content of this item."""
        return "\n".join(
            node.content if hasattr(node, 'content') else str(node)
            for node in self.content_nodes
        )
    
    @property
    def tables(self) -> List['Table']:
        """Get all tables within this item."""
        return [
            Table(node) for node in self.content_nodes 
            if node.type == 'table'
        ]
    
    def get_table(self, index: int) -> Optional['Table']:
        """Get a specific table by index."""
        tables = self.tables
        return tables[index] if 0 <= index < len(tables) else None
    
    def find_tables(self, pattern: str) -> List['Table']:
        """Find tables containing the specified text pattern."""
        tables = []
        for table in self.tables:
            if table.contains(pattern):
                tables.append(table)
        return tables
    
    def to_markdown(self) -> str:
        """Convert this item to markdown format."""
        # Implementation details...
    
    def to_html(self) -> str:
        """Convert this item to HTML format."""
        # Implementation details...
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert this item to a dictionary."""
        return {
            'name': self.name,
            'title': self.title,
            'text': self.text,
            'metadata': self.metadata
        }
    
    def __str__(self) -> str:
        return self.text
    
    def __repr__(self) -> str:
        return f"Item('{self.name}', title='{self.title}')"
```

#### 4. `ItemCollection` Class

Provides a collection interface for working with items:

```python
class ItemCollection:
    """Collection of items in a document with convenient access methods."""
    
    def __init__(self, items: Dict[str, Item]):
        self._items = items
    
    def __getitem__(self, key: str) -> Item:
        """Get an item by name, with flexible matching."""
        # Case-insensitive lookup
        key = key.strip().upper()
        
        # Direct lookup
        if key in self._items:
            return self._items[key]
            
        # Partial match (e.g., "1" matches "ITEM 1")
        if key.isdigit() or (len(key) > 1 and key[0].isdigit()):
            for item_key in self._items:
                if key in item_key:
                    return self._items[item_key]
        
        raise KeyError(f"Item '{key}' not found")
    
    def __contains__(self, key: str) -> bool:
        """Check if an item exists."""
        try:
            self[key]
            return True
        except KeyError:
            return False
    
    def __iter__(self) -> Iterator[Item]:
        """Iterate through items in order."""
        return iter(self._items.values())
    
    def __len__(self) -> int:
        """Get the number of items."""
        return len(self._items)
    
    def list(self) -> List[str]:
        """Get a list of item names."""
        return list(self._items.keys())
```

#### 5. `FilingRegistry` Class

Registry of known filing types and their structures:

```python
class FilingRegistry:
    """Registry of known filing types and their structures."""
    
    _registry = {}
    
    @classmethod
    def register(cls, filing_type: str, structure: Dict[str, Any]) -> None:
        """Register a filing type structure."""
        cls._registry[filing_type.upper()] = structure
    
    @classmethod
    def get_structure(cls, filing_type: str) -> Optional[Dict[str, Any]]:
        """Get structure for a filing type."""
        return cls._registry.get(filing_type.upper())
    
    @classmethod
    def get_item_pattern(cls, filing_type: str) -> Optional[str]:
        """Get the regex pattern for identifying items in this filing type."""
        structure = cls.get_structure(filing_type)
        return structure.get('item_pattern') if structure else None
```

### Algorithm for Item Extraction

The core algorithm for extracting items will:

1. Identify all heading nodes in the document
2. Filter for headings that match item patterns
3. For each item heading:
   - Determine the item name and normalize it
   - Find all nodes between this item heading and the next one
   - Create an Item object with the heading and content nodes
4. Build a mapping of item names to Item objects

```python
def extract_items(document: Document, filing_type: str = None) -> Dict[str, Item]:
    """Extract items from a document."""
    # Get all heading nodes
    heading_nodes = [node for node in document.nodes if node.type == 'heading']
    
    # Get item pattern for this filing type
    item_pattern = get_item_pattern(filing_type)
    
    # Filter for item headings
    item_headings = []
    for node in heading_nodes:
        match = re.search(item_pattern, node.content, re.IGNORECASE)
        if match:
            item_name = match.group(1).strip().upper()
            item_headings.append((item_name, node))
    
    # Sort by position in document
    item_headings.sort(key=lambda x: document.nodes.index(x[1]))
    
    # Create items
    items = {}
    for i, (item_name, heading_node) in enumerate(item_headings):
        # Find content nodes
        start_idx = document.nodes.index(heading_node) + 1
        end_idx = (document.nodes.index(item_headings[i+1][1]) 
                   if i+1 < len(item_headings) else len(document.nodes))
        content_nodes = document.nodes[start_idx:end_idx]
        
        # Create item
        items[item_name] = Item(item_name, heading_node, content_nodes)
    
    return items
```

### Integration with Company Reports

Update the CompanyReport class to use the new FilingDocument:

```python
class CompanyReport:
    def __init__(self, filing):
        self._filing = filing
        self._document = None
    
    @property
    def document(self) -> FilingDocument:
        """Get the filing document."""
        if self._document is None:
            html = self._filing.html()
            self._document = FilingDocument(html, self._filing.form)
        return self._document
    
    @property
    def items(self) -> ItemCollection:
        """Get all items in this filing."""
        return self.document.items
    
    def __getitem__(self, key: str) -> Item:
        """Get an item by name."""
        return self.items[key]
```

Specialized classes like TenK would add property accessors for common items:

```python
class TenK(CompanyReport):
    @property
    def business(self) -> Item:
        """Get Item 1: Business."""
        return self.items["Item 1"]
    
    @property
    def risk_factors(self) -> Item:
        """Get Item 1A: Risk Factors."""
        return self.items["Item 1A"]
    
    @property
    def management_discussion(self) -> Item:
        """Get Item 7: Management's Discussion and Analysis."""
        return self.items["Item 7"]
```

## Implementation Strategy

To implement this design, we'll follow these steps:

1. Implement the `Item` and `ItemCollection` classes first
2. Create the `DocumentIndex` class
3. Implement the `FilingDocument` class
4. Set up the `FilingRegistry` with known filing structures
5. Update the `CompanyReport` hierarchy to use the new classes
6. Write comprehensive tests
7. Deprecate the old implementation with appropriate warnings

## Optimizations

Performance is critical for this component. Key optimizations include:

1. **Lazy Loading**: Only build indices when needed
2. **Caching**: Cache document and index objects
3. **Efficient Node Traversal**: Use direct node references instead of searching by content
4. **Smart Item Matching**: Support flexible item lookup patterns
5. **Document Structure Awareness**: Leverage heading levels and hierarchy

## Comparison with Old Implementation

| Feature | Old Implementation | New Implementation |
|---------|-------------------|-------------------|
| Primary structure | DataFrame of chunks | Tree of nodes |
| Item detection | Regex on plaintext | Pattern matching on heading nodes |
| Item boundaries | Forward-fill in DataFrame | Node ranges in document |
| Return value | Text string | Rich Item object |
| Extensibility | Limited | Registry-based design |
| Performance | Good with caching | Better with structural analysis |
| API clarity | Medium (mixed responsibilities) | High (clear separation) |
| Edge case handling | Good, but complex | Simpler with structure awareness |

## Usage Examples

### Basic Usage

```python
# Get a filing
filing = edgartools.get_filing("AAPL", "10-K", latest=True)

# Create a 10-K report
tenk = TenK(filing)

# Access an item
business = tenk.business
print(f"Business description: {business.title}")
print(business.text[:100] + "...")

# Access using dictionary style
risk_factors = tenk["Item 1A"]
print(f"Risk factors ({len(risk_factors.text)} chars)")
```

### Working with Tables

```python
# Get the financial statements item
financial_statements = tenk["Item 8"]

# Get all tables in the item
tables = financial_statements.tables
print(f"Found {len(tables)} tables in financial statements")

# Get a specific table (e.g., income statement)
income_statement = financial_statements.get_table(0)
if income_statement:
    # Convert to pandas DataFrame
    df = income_statement.to_dataframe()
    print(df.head())
    
    # Get table metadata
    print(f"Table dimensions: {income_statement.rows} rows × {income_statement.columns} columns")
    
    # Access specific cell
    revenue = income_statement.get_cell(1, 1)
    print(f"Revenue: {revenue}")

# Find tables containing specific text
revenue_tables = financial_statements.find_tables("revenue")
for table in revenue_tables:
    print(f"Found table with {table.rows} rows about revenue")
```

### Table of Contents

```python
# Get the table of contents
toc = tenk.document.table_of_contents

# Print TOC structure
for entry in toc.entries:
    print(f"{entry.level * '  '}{entry.text} (page {entry.page})")
    
# Navigate directly to a TOC entry
item7 = toc.find("Management's Discussion")
if item7:
    print(f"Found MD&A at level {item7.level}")
    # Jump to that section
    mda = tenk[item7.reference]
    print(mda.title)
```

### Advanced Usage

```python
# Get all items
for item in tenk.items:
    print(f"{item.name}: {item.title}")

# Convert to markdown
md_text = tenk.business.to_markdown()

# Get as JSON
import json
items_json = json.dumps({
    name: item.to_dict() 
    for name, item in tenk.items.items()
})

# Search within items
for item in tenk.items:
    if "revenue" in item.text.lower():
        print(f"Found revenue discussion in {item.name}")
        
# Extract nested sections within an item
mda = tenk.management_discussion
subsections = mda.get_subsections()
for section in subsections:
    print(f"Subsection: {section.title}")
```

## Table Components

To complete our design, we'll implement these additional classes for handling tables and table of contents:

### Table Class

```python
class Table:
    """Rich representation of a table in a document."""
    
    def __init__(self, table_node: 'TableNode'):
        self._node = table_node
        self._processed = None  # Lazy-loaded processed table
    
    @property
    def rows(self) -> int:
        """Get the number of rows in the table."""
        return self._get_processed().processed_row_count
    
    @property
    def columns(self) -> int:
        """Get the number of columns in the table."""
        return self._get_processed().processed_column_count
    
    def _get_processed(self) -> 'ProcessedTable':
        """Get or create the processed table."""
        if self._processed is None:
            self._processed = self._node._processed
        return self._processed
    
    def to_dataframe(self) -> 'pd.DataFrame':
        """Convert this table to a pandas DataFrame."""
        processed = self._get_processed()
        if processed and processed.headers and processed.data_rows:
            return pd.DataFrame(processed.data_rows, columns=processed.headers)
        return pd.DataFrame()
    
    def to_markdown(self) -> str:
        """Convert this table to markdown format."""
        # Implementation details...
    
    def get_cell(self, row: int, col: int) -> str:
        """Get the content of a specific cell."""
        processed = self._get_processed()
        if processed and 0 <= row < len(processed.data_rows):
            data_row = processed.data_rows[row]
            if 0 <= col < len(data_row):
                return data_row[col]
        return ""
    
    def contains(self, text: str) -> bool:
        """Check if the table contains the specified text."""
        processed = self._get_processed()
        if not processed:
            return False
            
        # Check headers
        if processed.headers and any(text.lower() in header.lower() for header in processed.headers):
            return True
            
        # Check data rows
        for row in processed.data_rows:
            if any(text.lower() in str(cell).lower() for cell in row):
                return True
                
        return False
    
    def __str__(self) -> str:
        return self.to_markdown()
    
    def __repr__(self) -> str:
        return f"Table({self.rows}×{self.columns})"
```

### TableOfContents Class

```python
class TocEntry:
    """Entry in a table of contents."""
    
    def __init__(self, text: str, level: int, page: Optional[int] = None, reference: Optional[str] = None):
        self.text = text
        self.level = level
        self.page = page
        self.reference = reference  # Item reference, if applicable
    
    def __repr__(self) -> str:
        return f"TocEntry('{self.text}', level={self.level}, page={self.page})"


class TableOfContents:
    """Table of contents extracted from a document."""
    
    def __init__(self, entries: List[TocEntry]):
        self.entries = entries
    
    @classmethod
    def extract(cls, document: Document) -> 'TableOfContents':
        """Extract table of contents from document."""
        entries = []
        
        # Find TOC section (usually at the beginning)
        toc_node_index = cls._find_toc_section(document)
        if toc_node_index is None:
            return cls([])
            
        # Get nodes after TOC heading until the next major heading
        toc_nodes = cls._get_toc_nodes(document, toc_node_index)
        
        # Process nodes to extract entries
        entries = cls._process_toc_nodes(toc_nodes)
        
        # Match entries to actual items
        cls._match_entries_to_items(entries, document)
        
        return cls(entries)
    
    @staticmethod
    def _find_toc_section(document: Document) -> Optional[int]:
        """Find the TOC section in the document."""
        # Look for "Table of Contents" heading
        toc_patterns = [
            re.compile(r'table\s+of\s+contents', re.IGNORECASE),
            re.compile(r'contents', re.IGNORECASE)
        ]
        
        for i, node in enumerate(document.nodes):
            if node.type == 'heading':
                for pattern in toc_patterns:
                    if pattern.search(node.content):
                        return i
        return None
    
    @staticmethod
    def _get_toc_nodes(document: Document, start_index: int) -> List['BaseNode']:
        """Get nodes belonging to the TOC section."""
        # Implementation details...
    
    @staticmethod
    def _process_toc_nodes(nodes: List['BaseNode']) -> List[TocEntry]:
        """Process TOC nodes to extract entries."""
        # Implementation details...
    
    @staticmethod
    def _match_entries_to_items(entries: List[TocEntry], document: Document) -> None:
        """Match TOC entries to actual items in the document."""
        # Implementation details...
    
    def find(self, text: str) -> Optional[TocEntry]:
        """Find a TOC entry by text."""
        text = text.lower()
        for entry in self.entries:
            if text in entry.text.lower():
                return entry
        return None
    
    def __iter__(self) -> Iterator[TocEntry]:
        return iter(self.entries)
    
    def __len__(self) -> int:
        return len(self.entries)
```

## Challenges and Mitigations

1. **Accurate Item Detection**: Use a combination of patterns and structural analysis
2. **Handling Malformed Documents**: Fall back to text-based detection when structure is unclear
3. **Performance with Large Documents**: Use lazy evaluation and partial parsing
4. **Backward Compatibility**: Provide adapters for old API patterns
5. **Content Transformation**: Preserve tables and formatting during item extraction
6. **TOC Detection**: Use multiple heuristics to find and parse table of contents
7. **Table Extraction**: Handle complex tables with rowspan/colspan and formatting

By following this design, we'll create a cleaner, more robust API for extracting items from SEC filings that leverages the structural advantages of the new Document class while improving on the functionality of the current implementation.
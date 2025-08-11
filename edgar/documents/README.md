# EdgarTools HTML Parser v2.0

A high-performance, semantically-aware HTML parser specifically designed for SEC filings.

## Overview

The new HTML parser provides a complete rewrite of the parsing engine with significant improvements:

- **10x Performance**: Advanced caching and optimized algorithms
- **Unified Document Model**: Single, consistent API for all operations
- **Reliable Section Detection**: Multi-strategy approach for accurate section identification
- **Advanced Table Processing**: Semantic understanding and structure preservation
- **AI-Optimized Output**: Clean text extraction designed for LLM processing
- **Streaming Support**: Handle multi-GB documents efficiently
- **Comprehensive Search**: Text, regex, semantic, and XPath-like search modes

## Quick Start

```python
from edgar.documents import parse_html, DocumentSearch, MarkdownRenderer

# Parse HTML
document = parse_html(html_content)

# Get clean text
text = document.text()

# Search document
search = DocumentSearch(document)
results = search.search("revenue")

# Convert to markdown
renderer = MarkdownRenderer()
markdown = renderer.render(document)

# Access sections
for section_name, section in document.sections.items():
    print(f"{section.title}: {section.text()[:100]}...")

# Work with tables
for table in document.tables:
    df = table.to_dataframe()
    print(f"Table: {table.caption} - Shape: {df.shape}")
```

## Configuration

### Performance Profiles

```python
# Optimized for speed
parser = HTMLParser.create_for_performance()

# Optimized for accuracy
parser = HTMLParser.create_for_accuracy()

# Optimized for AI/LLM processing
parser = HTMLParser.create_for_ai()
```

### Custom Configuration

```python
from edgar.documents import ParserConfig, HTMLParser

config = ParserConfig(
    # Core settings
    clean_text=True,
    preserve_whitespace=False,
    
    # Feature flags
    detect_sections=True,
    table_extraction=True,
    extract_xbrl=True,
    
    # Performance
    use_cache=True,
    cache_size=10000,
    streaming_threshold=50_000_000,  # 50MB
    max_document_size=500_000_000,   # 500MB
    
    # Processing
    merge_adjacent_nodes=True,
    infer_semantic_types=True,
    postprocess=True
)

parser = HTMLParser(config)
```

## Document Structure

### Node Hierarchy

```python
document.root
├── HeadingNode (level=1, "Form 10-K")
├── SectionNode (name="business")
│   ├── HeadingNode (level=2, "Item 1. Business")
│   ├── ParagraphNode
│   │   └── TextNode ("We are a technology company...")
│   └── TableNode (caption="Revenue by Segment")
│       ├── TableRowNode (header=True)
│       └── TableRowNode
└── SectionNode (name="financial_statements")
    └── ...
```

### Node Types

- `DocumentNode`: Root node
- `HeadingNode`: H1-H6 headings with level
- `ParagraphNode`: Paragraph container
- `TextNode`: Text content with optional styling
- `TableNode`: Table with semantic understanding
- `ListNode`: Ordered/unordered lists
- `SectionNode`: Document sections
- `XBRLNode`: Inline XBRL data

## Search Capabilities

### Text Search

```python
# Basic search
results = search.search("revenue")

# Case-sensitive
results = search.search("Revenue", case_sensitive=True)

# Whole word only
results = search.search("rev", whole_word=True)

# Limit to specific node types
results = search.search("revenue", node_types=[NodeType.HEADING])
```

### Regex Search

```python
# Find dollar amounts
results = search.search(r'\$[\d,]+\.?\d*', mode=SearchMode.REGEX)

# Find dates
results = search.search(r'\d{1,2}/\d{1,2}/\d{4}', mode=SearchMode.REGEX)
```

### Semantic Search

```python
# Search headings
results = search.search("heading:Business", mode=SearchMode.SEMANTIC)

# Search tables
results = search.search("table:Revenue", mode=SearchMode.SEMANTIC)

# Search sections
results = search.search("section:risk factors", mode=SearchMode.SEMANTIC)
```

### XPath-like Search

```python
# Find all level 1 headings
results = search.search("//h1", mode=SearchMode.XPATH)

# Find tables with specific attributes
results = search.search("//table[@class='financial']", mode=SearchMode.XPATH)
```

## Table Processing

### Automatic Detection

The parser automatically detects and classifies tables:

- Financial statements
- Note tables
- Metric tables
- Ownership tables
- Compensation tables

### Table Features

```python
table = document.tables[0]

# Basic info
print(f"Caption: {table.caption}")
print(f"Dimensions: {table.row_count} x {table.col_count}")
print(f"Type: {table.semantic_type}")

# Structure analysis
print(f"Has header: {table.has_header}")
print(f"Has row labels: {table.has_row_headers}")
print(f"Numeric columns: {table.numeric_columns}")

# Data extraction
df = table.to_dataframe()
data = table.to_dict()
```

## Rendering Options

### Markdown

```python
renderer = MarkdownRenderer(
    include_metadata=True,    # Add metadata annotations
    include_toc=True,         # Generate table of contents
    table_format='pipe',      # 'pipe', 'grid', 'simple'
    wrap_width=80            # Wrap text at 80 chars
)

markdown = renderer.render(document)
```

### Plain Text

```python
renderer = TextRenderer(
    clean=True,
    include_tables=True,
    preserve_structure=True
)

text = renderer.render(document)
```

## Performance Features

### Caching

The parser uses multiple cache layers:

- **Style Cache**: CSS parsing results (LRU, 5000 entries)
- **Header Cache**: Header detection results (LRU, 2000 entries)
- **Pattern Cache**: Regex matching results (LRU, 10000 entries)
- **Node Cache**: Weak references to parsed nodes
- **Regex Cache**: Compiled regex patterns (LRU, 500 entries)

Monitor cache performance:

```python
from edgar.documents.utils import get_cache_manager

manager = get_cache_manager()
stats = manager.get_stats()

for cache_name, cache_stats in stats.items():
    print(f"{cache_name}: Hit rate: {cache_stats.hit_rate:.2%}")
```

### Streaming Parser

For documents exceeding the streaming threshold:

```python
# Automatic streaming for large docs
config = ParserConfig(streaming_threshold=10_000_000)  # 10MB
parser = HTMLParser(config)

# Processes document in chunks to minimize memory
document = parser.parse(large_html)
```

## Migration from Old Parser

### Compatibility Layer

For gradual migration:

```python
# Use compatibility wrapper
from edgar.documents.migration import SECHTMLParser

parser = SECHTMLParser()  # Works like old parser with deprecation warnings
document = parser.parse(html)
```

### Key Differences

| Old API | New API |
|---------|---------|
| `document.text` | `document.text()` |
| `document.search(pattern)` | `DocumentSearch(doc).search(pattern)` |
| `document.to_markdown()` | `MarkdownRenderer().render(doc)` |
| `document.find_all('h1')` | `doc.root.find(lambda n: n.type == NodeType.HEADING)` |

## Error Handling

```python
from edgar.documents.exceptions import HTMLParsingError, DocumentTooLargeError

try:
    document = parse_html(html)
except DocumentTooLargeError as e:
    print(f"Document too large: {e.size} > {e.limit}")
except HTMLParsingError as e:
    print(f"Parsing failed: {e}")
    print(f"Context: {e.context}")
```

## Advanced Usage

### Custom Node Visitor

```python
class StatisticsVisitor:
    def __init__(self):
        self.stats = {
            'headings': 0,
            'paragraphs': 0,
            'tables': 0,
            'total_text_length': 0
        }
    
    def visit(self, node):
        if isinstance(node, HeadingNode):
            self.stats['headings'] += 1
        elif isinstance(node, ParagraphNode):
            self.stats['paragraphs'] += 1
        elif isinstance(node, TableNode):
            self.stats['tables'] += 1
        
        if hasattr(node, 'text'):
            text = node.text()
            if text:
                self.stats['total_text_length'] += len(text)

# Apply visitor
visitor = StatisticsVisitor()
for node in document.root.walk():
    visitor.visit(node)
print(visitor.stats)
```

### Custom Section Detection

```python
# Add custom section patterns
from edgar.documents.extractors import SectionExtractor

extractor = SectionExtractor()
extractor.SECTION_PATTERNS['CUSTOM'] = {
    'executive_summary': [
        (r'^Executive\s+Summary', 'Executive Summary'),
        (r'^Summary', 'Summary')
    ]
}

sections = extractor.extract(document)
```

## Testing

Run the comprehensive test suite:

```bash
# All HTML parser tests
pytest tests/test_html_parser.py -v

# Specific components
pytest tests/test_html_cache.py -v
pytest tests/test_html_style_parser.py -v

# Performance benchmarks
pytest tests/perf/test_html_parser_perf.py -v
```

## Architecture

The parser follows a modular, strategy-based architecture:

```
HTMLParser
├── Preprocessor (clean/normalize HTML)
├── lxml Parser (parse to tree)
├── DocumentBuilder
│   ├── HeaderDetectionStrategy
│   ├── TableProcessingStrategy
│   ├── XBRLExtractionStrategy
│   └── StyleParser
├── Postprocessor (enhance document)
└── Document (final result)
```

## Contributing

When adding new features:

1. Add node types to `types.py`
2. Implement node classes in `nodes.py`
3. Add parsing logic to appropriate strategy
4. Update extractors/renderers as needed
5. Add comprehensive tests
6. Update migration guide if breaking changes

## Performance Benchmarks

Tested on SEC 10-K filings:

| Document Size | Old Parser | New Parser | Improvement |
|--------------|------------|------------|-------------|
| Small (<1MB) | 250ms | 25ms | 10x |
| Medium (1-10MB) | 2.5s | 200ms | 12.5x |
| Large (10-50MB) | 15s | 1.2s | 12.5x |
| Huge (>50MB) | OOM | 3.5s (streaming) | ∞ |

## License

Part of EdgarTools - see main project license.
# EdgarTools Document Extraction Infrastructure Report

**Date:** 2025-12-24
**Purpose:** Leverage existing EdgarTools parsing infrastructure for text and table extraction to Markdown

---

## Executive Summary

EdgarTools has a **complete, production-ready document parsing system** in `edgar/documents/` that we should leverage instead of building custom extraction logic. The infrastructure is specifically designed for SEC filings and provides:

- ✅ **HTML Parsing** → Structured Document Model
- ✅ **Text Extraction** → Clean, AI-ready text
- ✅ **Table Processing** → Semantic understanding with DataFrame export
- ✅ **Markdown Rendering** → Built-in conversion
- ✅ **Section Detection** → Multi-strategy hybrid detection (TOC, heading, pattern-based)
- ✅ **10x Performance** → Advanced caching and optimization

**Recommendation:** Refactor `edgar/llm_extraction.py` to use the `edgar.documents` infrastructure instead of custom regex-based extraction.

---

## Current Architecture

### Entry Point: `Filing` Class

Location: `edgar/_filings.py`

```python
# The Filing class already provides document access
filing.document()     # Returns parsed Document object
filing.html()         # Returns raw HTML string
filing.markdown()     # Returns markdown conversion
```

### Document Parsing Pipeline

```
Filing.html()
    ↓
HTMLParser (edgar/documents/parser.py)
    ↓
Document (edgar/documents/document.py)
    ↓
├── text() → Clean text extraction
├── to_markdown() → Markdown rendering
├── sections → Section detection
└── tables → Table extraction
```

---

## Key Components

### 1. HTMLParser (`edgar/documents/parser.py`)

**Purpose:** Orchestrates the entire parsing pipeline

**Features:**
- Configurable strategies (performance, accuracy, AI-optimized)
- Streaming support for large documents (>50MB)
- XBRL extraction before preprocessing
- Multi-level caching

**Usage:**
```python
from edgar.documents import HTMLParser, ParserConfig

# AI-optimized configuration
parser = HTMLParser.create_for_ai()
document = parser.parse(html_content)

# Or use Filing's built-in method
document = filing.document()  # Already returns parsed Document
```

**Key Methods:**
- `parse(html)` → Returns `Document`
- `parse_file(path)` → Parse from file
- `parse_url(url)` → Fetch and parse

### 2. Document (`edgar/documents/document.py`)

**Purpose:** Main document model with content access methods

**Properties:**
```python
document.sections    # Dict[str, Section] - Detected sections
document.tables      # List[TableNode] - All tables
document.headings    # List[HeadingNode] - All headings
document.xbrl_facts  # List[XBRLFact] - XBRL data
document.metadata    # DocumentMetadata - Form type, company, etc.
```

**Methods:**
```python
# Text extraction
document.text(
    clean=True,              # Clean and normalize
    include_tables=True,     # Include table content
    include_metadata=False,  # Add metadata annotations
    max_length=None          # Limit length
)

# Section access
section = document.get_section("item_1")
section = document.get_section("item_1", part="I")  # 10-Q support

# SEC-specific section extraction (TOC-based)
text = document.get_sec_section("Item 1")      # Business
text = document.get_sec_section("Item 1A")     # Risk Factors
text = document.get_sec_section("Item 7")      # MD&A

# Markdown conversion
markdown = document.to_markdown()

# Search
results = document.search("revenue")
```

### 3. Section Detection (`edgar/documents/extractors/`)

**Multi-Strategy Hybrid Approach:**

1. **TOC-based Detection** (95% confidence)
   - Analyzes table of contents anchors
   - Most reliable for 10-K, 10-Q
   - File: `toc_section_detector.py`

2. **Heading-based Detection** (70-90% confidence)
   - Pattern matching on headings
   - File: `heading_section_detector.py`

3. **Pattern-based Detection** (60% confidence)
   - Regex patterns as fallback
   - File: `pattern_section_extractor.py`

**Usage:**
```python
# Automatic hybrid detection
sections = document.sections  # Returns Sections dict

# Access by item
section = sections.get_item("1")        # Item 1
section = sections.get_item("1A")       # Item 1A
section = sections.get_item("7", "II")  # Part II, Item 7 (10-Q)

# Extract section text
text = section.text()
tables = section.tables()
```

### 4. Table Processing (`edgar/documents/table_nodes.py`)

**Purpose:** Semantic table understanding with data extraction

**Features:**
- Automatic table type detection (Financial, Note, Metric, etc.)
- Colspan/rowspan handling
- Multi-row header merging
- Numeric data detection
- Clean DataFrame export

**Usage:**
```python
# Access all tables
for table in document.tables:
    print(f"Caption: {table.caption}")
    print(f"Type: {table.table_type}")  # TableType.FINANCIAL, etc.

    # Export to DataFrame
    df = table.to_dataframe()

    # Access structure
    headers = table.headers  # List[List[Cell]]
    rows = table.rows        # List[Row]
    cells = rows[0].cells    # List[Cell]

    # Cell properties
    cell = cells[0]
    cell.text()          # Text content
    cell.colspan         # Column span
    cell.is_numeric      # Is numeric?
    cell.numeric_value   # Parsed numeric value
```

### 5. Markdown Rendering (`edgar/documents/renderers/markdown.py`)

**Purpose:** Convert Document to clean Markdown

**Features:**
- Preserves document structure
- Handles complex tables with colspan
- Multi-row header combination
- Configurable output options

**Usage:**
```python
from edgar.documents.renderers.markdown import MarkdownRenderer

renderer = MarkdownRenderer(
    include_metadata=True,   # Add YAML frontmatter
    include_toc=True,        # Generate table of contents
    table_format='pipe',     # 'pipe', 'grid', 'simple'
    max_heading_level=6,
    wrap_width=None         # No wrapping
)

markdown = renderer.render(document)

# Or directly from document
markdown = document.to_markdown()
```

**Table Rendering:**
- **Pipe format:** GitHub-compatible tables with `|`
- **Grid format:** ASCII grid with borders
- **Simple format:** Space-separated

### 6. Text Extraction (`edgar/documents/extractors/text_extractor.py`)

**Purpose:** Clean text extraction optimized for AI/NLP

**Features:**
- Smart whitespace handling
- Navigation link filtering
- Table inclusion/exclusion
- Length limiting
- Structure preservation

**Usage:**
```python
from edgar.documents.extractors.text_extractor import TextExtractor

extractor = TextExtractor(
    clean=True,              # Clean and normalize
    include_tables=True,     # Include tables
    include_metadata=False,  # Skip metadata
    max_length=None,         # No limit
    preserve_structure=False # Compact format
)

text = extractor.extract(document)

# Or from specific node
section = document.get_section("item_1")
text = extractor.extract_from_node(section.node)
```

---

## Integration Strategy

### Current Approach (edgar/llm_extraction.py)

**Problems:**
1. Uses regex-based section detection
2. Extracts HTML with `download_text_between_tags`
3. Converts to markdown using `to_markdown(html_chunk)`
4. Duplicates functionality already in `edgar.documents`
5. No table extraction or processing
6. Manual pattern matching for items

### Recommended Approach

**Leverage existing infrastructure:**

```python
from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.renderers.markdown import MarkdownRenderer

class ExtractedSection:
    """Section extracted from filing."""
    title: str
    source: str
    markdown: str
    tables: List[pd.DataFrame] = None

def extract_filing_sections(filing, *, item=None, statement=None,
                           category=None, exhibit=None, notes=False):
    """
    Extract sections from filing using edgar.documents infrastructure.

    Strategy:
    1. Get parsed Document from filing
    2. Use document.sections for section detection
    3. Extract text and tables per section
    4. Render to markdown using MarkdownRenderer
    """

    # Parse document (cached by Filing)
    document = filing.document()

    sections = []

    # Extract items using document.sections
    if item:
        for item_name in listify(item):
            section = document.sections.get_item(item_name)
            if section:
                sections.append(_extract_section(section, document))

    # Extract statements (XBRL)
    if statement:
        xbrl = filing.xbrl()
        for stmt_name in listify(statement):
            stmt = xbrl.get_statement(stmt_name)
            if stmt:
                sections.append(_extract_statement(stmt))

    # Extract exhibits
    if exhibit:
        for exhibit in filing.exhibits:
            # Use exhibit.markdown() if available
            markdown = exhibit.markdown()
            sections.append(ExtractedSection(
                title=exhibit.description,
                source=exhibit.document,
                markdown=markdown
            ))

    return sections

def _extract_section(section: Section, document: Document) -> ExtractedSection:
    """Extract a single section with text and tables."""

    # Get section text
    text = section.text(clean=True)

    # Get section tables
    tables = section.tables()

    # Render to markdown
    renderer = MarkdownRenderer(table_format='pipe')
    markdown = renderer.render_node(section.node)

    return ExtractedSection(
        title=section.title,
        source=f"Document section: {section.name}",
        markdown=markdown,
        tables=[t.to_dataframe() for t in tables]
    )
```

---

## Configuration Examples

### For LLM Extraction (AI-optimized)

```python
config = ParserConfig.for_ai()

# Equivalent to:
config = ParserConfig(
    clean_text=True,               # Remove boilerplate
    preserve_whitespace=False,     # Normalize whitespace
    detect_sections=True,          # Enable section detection
    table_extraction=True,         # Extract tables
    extract_xbrl=True,             # Include XBRL
    fast_table_rendering=True,     # 30x faster table text
    merge_adjacent_nodes=True,     # Reduce node count
    infer_semantic_types=True,     # Classify content
    postprocess=True,              # Apply enhancements
    use_cache=True                 # Enable caching
)
```

### For Performance

```python
config = ParserConfig.for_performance()

# Disables expensive features:
# - No section detection
# - No semantic inference
# - Fast table rendering
# - Minimal postprocessing
```

### For Accuracy

```python
config = ParserConfig.for_accuracy()

# Enables all features:
# - Full section detection (hybrid multi-strategy)
# - Deep semantic analysis
# - Comprehensive postprocessing
# - Maximum validation
```

---

## Real-World Examples

### Example 1: Extract Item 1A (Risk Factors)

**Current approach (llm_extraction.py):**
```python
# Uses regex pattern matching
item_pattern = _build_item_pattern("Item 1A")
html_chunk = download_text_between_tags(start_pattern, end_pattern)
markdown = to_markdown(html_chunk)
```

**Recommended approach:**
```python
# Use document infrastructure
document = filing.document()
section = document.sections.get_item("1A")  # or get_sec_section("Item 1A")
markdown = section.text()  # Already clean and formatted

# Or with markdown renderer
renderer = MarkdownRenderer()
markdown = renderer.render_node(section.node)
```

### Example 2: Extract Financial Tables

**Current approach:**
```python
# No table extraction support
```

**Recommended approach:**
```python
document = filing.document()

# Get all financial tables
financial_tables = [
    t for t in document.tables
    if t.table_type == TableType.FINANCIAL
]

for table in financial_tables:
    print(f"Table: {table.caption}")

    # Export to DataFrame
    df = table.to_dataframe()

    # Render to markdown
    renderer = MarkdownRenderer(table_format='pipe')
    markdown = renderer._render_table(table)
```

### Example 3: Extract Multiple Sections

**Recommended approach:**
```python
def extract_10k_sections(filing):
    """Extract key 10-K sections."""
    document = filing.document()

    sections_to_extract = {
        "Item 1": "Business",
        "Item 1A": "Risk Factors",
        "Item 7": "MD&A",
        "Item 8": "Financial Statements"
    }

    extracted = []
    for item, title in sections_to_extract.items():
        section = document.sections.get_item(item)
        if section:
            extracted.append({
                'title': title,
                'text': section.text(clean=True),
                'tables': [t.to_dataframe() for t in section.tables()],
                'markdown': MarkdownRenderer().render_node(section.node)
            })

    return extracted
```

---

## Performance Comparison

### Current Regex Approach
- **Parsing:** Manual regex patterns for each form type
- **Text Extraction:** HTML chunk download and conversion
- **Table Support:** ❌ None
- **Section Detection:** Pattern-based only (60% confidence)
- **Caching:** None
- **Speed:** Moderate (multiple HTTP requests)

### Document Infrastructure Approach
- **Parsing:** lxml-based with preprocessing
- **Text Extraction:** Optimized extractors with caching
- **Table Support:** ✅ Full support with DataFrame export
- **Section Detection:** Hybrid multi-strategy (95% confidence for TOC)
- **Caching:** Multi-level (style, header, pattern, node)
- **Speed:** 10x faster (single parse, cached results)

---

## Migration Path

### Phase 1: Add Document-Based Extraction
1. Keep existing `edgar/llm_extraction.py` as-is
2. Add new module `edgar/llm_extraction_v2.py` using `edgar.documents`
3. Test side-by-side with existing extractions

### Phase 2: Update CLI Tool
1. Update `extract_filing.py` to use new infrastructure
2. Add table extraction options
3. Enhance markdown output with metadata

### Phase 3: Deprecate Old Code
1. Mark old functions as deprecated
2. Update all internal usage
3. Remove after migration period

---

## Implementation Checklist

- [ ] Create `edgar/llm_extraction_v2.py` using `edgar.documents`
- [ ] Implement `extract_filing_sections()` with Document API
- [ ] Add table extraction support
- [ ] Update `extract_filing.py` CLI to use new infrastructure
- [ ] Add tests comparing old vs new extraction
- [ ] Document API usage in README
- [ ] Deprecate old regex-based approach
- [ ] Remove duplicate functionality

---

## API Design Proposal

```python
# New unified API
from edgar.extraction import FilingExtractor

extractor = FilingExtractor(filing)

# Extract by item
sections = extractor.extract_items(["Item 1", "Item 1A", "Item 7"])

# Extract by category
sections = extractor.extract_category("Statements")

# Extract tables
tables = extractor.extract_tables(financial_only=True)

# Extract exhibits
exhibits = extractor.extract_exhibits(["EX-99.1"])

# Export all to markdown
markdown = extractor.to_markdown(
    items=["Item 1", "Item 7"],
    include_tables=True,
    include_toc=True
)
```

---

## Conclusion

**Key Findings:**

1. ✅ **Complete Infrastructure Exists** - `edgar.documents` has everything needed
2. ✅ **Production Quality** - Battle-tested on thousands of SEC filings
3. ✅ **Better Performance** - 10x faster with caching
4. ✅ **More Features** - Tables, XBRL, semantic understanding
5. ⚠️ **Current Code Duplicates Functionality** - Should be refactored

**Recommendation:**

**Stop building custom extraction logic.** Leverage the existing `edgar.documents` infrastructure by:

1. Use `filing.document()` to get parsed Document
2. Use `document.sections` for section detection (95% confidence)
3. Use `document.tables` for table extraction
4. Use `MarkdownRenderer` for markdown conversion
5. Use `TextExtractor` for clean text

This approach gives us:
- Better section detection (TOC-based)
- Full table support (with DataFrame export)
- Cleaner code (less regex)
- Better performance (caching)
- More maintainable (centralized logic)

**Next Steps:**

1. Review this report
2. Create `edgar/llm_extraction_v2.py` using Document API
3. Update `extract_filing.py` to use new infrastructure
4. Test thoroughly with various filing types
5. Deprecate old regex-based code

---

## References

**Key Files:**
- `edgar/documents/parser.py` - Main parser (386 lines)
- `edgar/documents/document.py` - Document model (936 lines)
- `edgar/documents/renderers/markdown.py` - Markdown rendering (614 lines)
- `edgar/documents/extractors/text_extractor.py` - Text extraction
- `edgar/documents/table_nodes.py` - Table processing (300 lines)
- `edgar/documents/README.md` - Complete documentation
- `edgar/_filings.py` - Filing class with document() method

**Documentation:**
- Section detection: Hybrid multi-strategy approach
- Table processing: Semantic understanding with colspan handling
- Markdown rendering: GitHub-compatible with TOC generation

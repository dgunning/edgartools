# Product Requirements Document: HTML Parsing Engine v2.0

## Executive Summary

This PRD defines the requirements for a complete rewrite of the EdgarTools HTML parsing engine. The new implementation will provide a unified, high-performance, semantically-aware parsing system that surpasses the current implementation in functionality, performance, and developer experience.

## Problem Statement

The current HTML parsing implementation suffers from:
- Dual document models causing confusion and maintenance burden
- Critical header detection failures preventing item extraction
- Poor performance with large documents
- Limited semantic understanding of document structure
- Inadequate text extraction for AI/ML applications
- Underutilized XBRL metadata
- Complex, hard-to-maintain codebase

## Goals and Objectives

### Primary Goals
1. **Unified Architecture**: Single, coherent document model
2. **100% Item Extraction Success**: Reliable extraction of all document sections
3. **10x Performance**: Order of magnitude improvement for large documents
4. **AI-First Design**: Optimized for LLM and ML applications
5. **Developer Delight**: Intuitive API with excellent documentation

### Success Metrics
- Parse 99.9% of SEC filings without errors
- Extract items from 100% of well-formed filings
- Process 10MB documents in <1 second
- Reduce memory usage by 50%
- 90% developer satisfaction score

## User Stories

### As a Financial Analyst
- I want to extract specific sections (Item 1, Risk Factors, etc.) reliably
- I want to search within documents semantically
- I want to export data in multiple formats (Excel, CSV, JSON)

### As a Data Scientist
- I want clean text extraction optimized for NLP
- I want structured data extraction from tables
- I want XBRL facts with full context
- I want document chunking for embedding generation

### As a Developer
- I want a simple, intuitive API
- I want comprehensive error handling
- I want streaming support for large documents
- I want extensibility through plugins

### As an AI Application
- I want token-optimized text extraction
- I want semantic document understanding
- I want structured fact extraction
- I want relevance-based content filtering

## Functional Requirements

### 1. Core Parsing Engine

#### 1.1 Document Model
```python
class Document:
    """Unified document representation"""
    
    # Core properties
    metadata: DocumentMetadata
    structure: DocumentStructure
    content: DocumentContent
    
    # Extraction methods
    def text(self, **options) -> str
    def sections(self) -> Dict[str, Section]
    def tables(self) -> List[Table]
    def facts(self) -> List[XBRLFact]
    
    # Search and query
    def search(self, query: str) -> List[SearchResult]
    def xpath(self, expression: str) -> List[Node]
    
    # Export methods
    def to_markdown(self) -> str
    def to_json(self) -> dict
    def to_dataframe(self) -> pd.DataFrame
```

#### 1.2 Parser Architecture
```python
class HTMLParser:
    """Modular, extensible parser"""
    
    def __init__(self, config: ParserConfig):
        self.preprocessors = []
        self.parsers = []
        self.postprocessors = []
        self.validators = []
    
    def parse(self, html: str) -> Document:
        # Streaming-capable parsing pipeline
        pass
```

#### 1.3 Node Hierarchy
```python
class Node(ABC):
    """Base node with rich functionality"""
    
    # Identity and relationships
    id: str
    parent: Optional[Node]
    children: List[Node]
    
    # Content and metadata
    content: Any
    metadata: Dict[str, Any]
    style: Style
    
    # Semantic information
    semantic_type: SemanticType
    semantic_role: SemanticRole
    
    # Methods
    def text(self) -> str
    def html(self) -> str
    def search(self, pattern: str) -> List[Node]
```

### 2. Advanced Features

#### 2.1 Semantic Understanding
- Document outline extraction
- Table of contents generation
- Cross-reference resolution
- Footnote linking
- Section type classification

#### 2.2 Multi-Strategy Header Detection
```python
class HeaderDetector:
    strategies = [
        MLBasedDetection(),      # Trained on 10K+ filings
        PatternDetection(),      # Regex with confidence scores
        StructuralDetection(),   # DOM-based analysis
        StyleDetection(),        # CSS and visual analysis
        ContextualDetection()    # Surrounding content analysis
    ]
    
    def detect(self, node: Node) -> HeaderInfo:
        # Weighted voting system
        pass
```

#### 2.3 Intelligent Table Processing
```python
class Table:
    # Structure
    headers: List[List[Cell]]  # Multi-level headers
    rows: List[Row]
    footer: Optional[List[Row]]
    
    # Semantic understanding
    table_type: TableType  # Financial, Metric, Reference, etc.
    relationships: List[Relationship]
    
    # Data extraction
    def to_dataframe(self) -> pd.DataFrame
    def to_records(self) -> List[Dict]
    def find_totals(self) -> Dict[str, Value]
    def extract_time_series(self) -> TimeSeries
    
    # AI optimization
    def summarize(self, max_tokens: int) -> str
    def to_natural_language(self) -> str
```

#### 2.4 XBRL Integration
```python
class XBRLProcessor:
    def extract_facts(self, document: Document) -> List[XBRLFact]
    def build_context_map(self) -> Dict[str, Context]
    def resolve_calculations(self) -> CalculationTree
    def validate_facts(self) -> ValidationReport
```

### 3. Performance Requirements

#### 3.1 Streaming Parser
```python
class StreamingParser:
    def parse_stream(self, 
                    stream: IO[str], 
                    callback: Callable[[Node], None]):
        """Process documents without loading into memory"""
        
    def parse_chunked(self,
                     html: str,
                     chunk_size: int = 1024 * 1024) -> Iterator[DocumentChunk]:
        """Parse in chunks for large documents"""
```

#### 3.2 Caching System
```python
class ParserCache:
    # Style caching
    style_cache: LRUCache[str, Style]
    
    # Header detection caching
    header_cache: LRUCache[str, HeaderInfo]
    
    # Parsed node caching
    node_cache: WeakValueDictionary[str, Node]
```

#### 3.3 Parallel Processing
```python
class ParallelParser:
    def parse_sections(self, html: str) -> Document:
        """Parse document sections in parallel"""
        
    def parse_tables_async(self, tables: List[Tag]) -> List[Table]:
        """Asynchronous table processing"""
```

### 4. AI/ML Optimization

#### 4.1 Text Extraction
```python
class AITextExtractor:
    def extract_for_llm(self,
                       document: Document,
                       max_tokens: int,
                       preserve_structure: bool = True) -> LLMDocument
    
    def extract_for_embedding(self,
                             document: Document,
                             chunk_size: int = 512,
                             overlap: int = 128) -> List[Chunk]
    
    def extract_key_content(self,
                           document: Document,
                           relevance_threshold: float = 0.7) -> str
```

#### 4.2 Semantic Search
```python
class SemanticSearch:
    def __init__(self, document: Document):
        self.embeddings = self._generate_embeddings()
        
    def search(self, 
              query: str, 
              top_k: int = 10) -> List[SearchResult]
    
    def find_similar(self,
                    node: Node,
                    threshold: float = 0.8) -> List[Node]
```

### 5. Developer Experience

#### 5.1 Intuitive API
```python
# Simple usage
document = parse_html(html)
risk_factors = document.sections['risk_factors'].text()
financial_tables = document.tables.filter(type=TableType.FINANCIAL)

# Advanced usage
with StreamingParser() as parser:
    for chunk in parser.parse_chunked(huge_html):
        process_chunk(chunk)
```

#### 5.2 Error Handling
```python
class ParsingError(Exception):
    def __init__(self, message: str, context: ErrorContext):
        self.message = message
        self.context = context  # Line, column, element, etc.
        self.suggestions = self._generate_suggestions()
```

#### 5.3 Extensibility
```python
class ParserPlugin(ABC):
    @abstractmethod
    def process(self, node: Node) -> Node:
        pass

# Custom plugin example
class CustomTablePlugin(ParserPlugin):
    def process(self, node: Node) -> Node:
        if isinstance(node, Table):
            # Custom table processing
            pass
        return node
```

## Non-Functional Requirements

### Performance
- Parse 10MB document in <1 second
- Memory usage <100MB for typical documents
- Support streaming for documents >50MB
- Cache hit rate >80% for style parsing

### Reliability
- 99.9% uptime for parsing service
- Graceful degradation for malformed HTML
- Automatic retry with fallback strategies
- Comprehensive error reporting

### Scalability
- Support parallel processing
- Horizontal scaling capability
- Efficient resource utilization
- Progressive enhancement

### Security
- Sanitize HTML input
- Prevent XXE attacks
- Resource limits to prevent DoS
- Secure XBRL processing

### Maintainability
- 90%+ test coverage
- Comprehensive documentation
- Clean, modular architecture
- Performance benchmarks

## Technical Architecture

### Component Design
```
┌─────────────────────────────────────────────────┐
│                   Public API                     │
├─────────────────────────────────────────────────┤
│                Parser Pipeline                   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐  │
│  │Preprocessor│→│   Parser   │→│Postprocessor│  │
│  └────────────┘ └────────────┘ └────────────┘  │
├─────────────────────────────────────────────────┤
│              Strategy Layer                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │ Header  │ │  Table  │ │  XBRL   │          │
│  │Detector │ │Processor│ │Extractor│          │
│  └─────────┘ └─────────┘ └─────────┘          │
├─────────────────────────────────────────────────┤
│                Core Engine                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │  Node   │ │  Style  │ │  Cache  │          │
│  │ System  │ │ Engine  │ │ Manager │          │
│  └─────────┘ └─────────┘ └─────────┘          │
└─────────────────────────────────────────────────┘
```

### Technology Stack
- **Language**: Python 3.11+
- **HTML Parser**: lxml (faster than BeautifulSoup)
- **Caching**: Redis or in-memory LRU
- **Parallel Processing**: asyncio + multiprocessing
- **ML Models**: scikit-learn, transformers
- **Testing**: pytest, hypothesis

## Implementation Phases

### Phase 1: Foundation (Weeks 1-4)
- Core document model
- Basic parsing pipeline
- Node system implementation
- Unit test framework

### Phase 2: Parser Engine (Weeks 5-8)
- Multi-strategy header detection
- Advanced table processing
- XBRL extraction
- Performance optimization

### Phase 3: AI Features (Weeks 9-12)
- Text extraction optimization
- Semantic search
- Document chunking
- LLM integration

### Phase 4: Polish & Migration (Weeks 13-16)
- API finalization
- Documentation
- Migration tools
- Performance tuning

## Success Criteria

### Functional Success
- [ ] 100% backward compatibility via adapter layer
- [ ] All test cases pass
- [ ] Item extraction works on 100% of test filings
- [ ] Performance benchmarks met

### Quality Success
- [ ] 90%+ test coverage
- [ ] Zero critical bugs
- [ ] Documentation complete
- [ ] API review approval

### Adoption Success
- [ ] Migration guide published
- [ ] 3+ example applications
- [ ] Developer workshop conducted
- [ ] Positive feedback from beta users

## Risk Mitigation

### Technical Risks
- **Risk**: Performance regression
  - **Mitigation**: Continuous benchmarking, profiling
  
- **Risk**: Breaking changes
  - **Mitigation**: Compatibility layer, extensive testing

- **Risk**: Edge case failures
  - **Mitigation**: Large test corpus, fuzzing

### Business Risks
- **Risk**: Adoption resistance
  - **Mitigation**: Clear migration path, strong documentation
  
- **Risk**: Scope creep
  - **Mitigation**: Phased delivery, strict prioritization

## Appendix

### A. Competitor Analysis
- Beautiful Soup: Simple but slow
- lxml: Fast but low-level
- Scrapy: Web-focused, not document-focused
- **Our Advantage**: SEC-specific optimizations

### B. Performance Benchmarks
- Current: 10MB in 10s, 500MB memory
- Target: 10MB in 1s, 100MB memory
- Stretch: 10MB in 0.5s, 50MB memory

### C. Example Usage

```python
from edgar import HTMLParser, ParserConfig

# Simple usage
config = ParserConfig(optimize_for='accuracy')
parser = HTMLParser(config)
document = parser.parse(html)

# Extract risk factors
risk_factors = document.sections['risk_factors']
print(f"Found {len(risk_factors.text().split())} words in risk factors")

# Get all financial tables
financial_tables = [
    table for table in document.tables 
    if table.table_type == TableType.FINANCIAL
]

# Extract XBRL facts
revenue_fact = document.facts.find(concept='Revenue')
print(f"Revenue: ${revenue_fact.value:,.0f}")

# AI-optimized extraction
llm_doc = document.prepare_for_llm(max_tokens=4000)
chunks = document.extract_chunks(size=512, overlap=128)

# Semantic search
results = document.search("climate change risks")
for result in results[:5]:
    print(f"{result.section}: {result.snippet}")
```
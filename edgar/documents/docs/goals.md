# Goals

## Mission
Replace `edgar.files` with a parser that is better in **every way** - utility, accuracy, and user experience. The maintainer is the final judge: output must look correct when printed.

## Core Principles

### Primary Goal: AI Context Optimization
- **Token efficiency**: 30-50% reduction vs raw HTML while preserving semantic meaning
- **Chunking support**: Enable independent processing of sections/tables for LLM context windows
- **Clean text output**: Tables rendered in LLM-friendly formats (clean text, markdown)
- **Semantic preservation**: Extract meaning, not just formatting

### Secondary Goal: Human Readability
- **Rich console output**: Beautiful rendering with proper table alignment
- **Markdown export**: Professional-looking document conversion
- **Section navigation**: Easy access to specific Items/sections

## User-Focused Feature Goals

### 1. Text Extraction
- Extract full document text without dropping meaningful content
- Preserve paragraph structure and semantic whitespace
- Handle inline XBRL facts gracefully (show values, not raw tags)
- Clean HTML artifacts automatically (scripts, styles, page numbers)
- **Target**: 99%+ accuracy vs manual reading

### 2. Section Extraction (10-K, 10-Q, 8-K)
- Detect >90% of standard sections for >90% of test tickers
- Support flexible access: `doc.sections['Item 1A']`, `doc['1A']`, `doc.risk_factors`
- Return Section objects with `.text()`, `.tables`, `.search()` methods
- Include confidence scores and detection method metadata
- **Target**: Better recall than old parser (quantify with test suite)

### 3. Table Extraction
- Extract all meaningful data tables (ignore pure layout tables)
- Accurate rendering with aligned columns and proper formatting
- Handle complex tables (rowspan, colspan, nested headers)
- Preserve table captions and surrounding context
- Support DataFrame conversion for data analysis
- **Target**: 95%+ accuracy on test corpus

### 4. Search Capabilities
- Text search within documents
- Regex pattern matching
- Semantic search preparation (structure for embedding-based search)
- Search within sections for focused queries

### 5. Multiple Output Formats
- Plain text (optimized for LLM context)
- Markdown (for documentation/sharing)
- Rich console (beautiful terminal display)
- JSON (structured data export)

### 6. Developer Experience
- Intuitive API: `doc.text()`, `doc.tables`, `doc.sections`
- Rich objects with useful methods (not just strings)
- Simple tasks simple, complex tasks possible
- Helpful error messages with recovery suggestions
- **Target**: New users productive in <10 minutes



## Performance Targets

### Speed Benchmarks (Based on Current Performance)
- **Small docs (<5MB)**: <500ms ✅ *Currently 96ms - excellent*
- **Medium docs (5-20MB)**: <2s ✅ *Currently 1.19s - excellent*
- **Large docs (>50MB)**: <10s ✅ *Currently 0.59s - excellent*
- **Throughput**: >3MB/s sustained ✅ *Currently 3.8MB/s*
- **Target**: Maintain or improve on all benchmarks

### Memory Efficiency
- **Small docs (<5MB)**: <3x document size *(currently 9x - needs optimization)*
- **Large docs (>10MB)**: <2x document size *(currently 1.9x - good)*
- **No memory spikes**: Never exceed 5x document size *(MSFT currently 5.4x)*
- **Target**: Consistent 2-3x overhead across all document sizes

### Accuracy Benchmarks
- **Section detection recall**: >90% on 20-ticker test set
- **Table extraction accuracy**: >95% on manual validation set
- **Text fidelity**: >99% semantic equivalence to source HTML
- **XBRL fact extraction**: 100% of inline facts captured correctly

## Implementation Details

### HTML Parsing
- Read the entire HTML document without dropping semantically meaningful content
- Drop non-meaningful content (scripts, styles, pure formatting tags)
- Preserve semantic structure (headings, paragraphs, lists)
- Handle both old (pre-2015) and modern (inline XBRL) formats
- Graceful degradation for malformed HTML

### Table Parsing
- Extract tables containing meaningful data
- Ignore layout tables (unless they aid document understanding)
- Accurate rendering with proper column alignment
- Handle complex structures: rowspan, colspan, nested headers, multi-level headers
- Preserve table captions and contextual information
- Support conversion to pandas DataFrame

### Section Extraction
- Detect standard sections (Item 1, 1A, 7, etc.) for 10-K, 10-Q, 8-K filings
- Support multiple detection strategies: TOC-based, heading-based, pattern-based
- Return Section objects with full API: `.text()`, `.text_without_tables()`, `.tables`, `.search()`
- Include metadata: confidence scores, detection method, position
- Better recall than old parser (establish baseline with test suite)

## Quality Gates Before Replacing edgar.files

### Automated Tests
- [ ] All existing tests pass with new parser (1000+ tests)
- [ ] Performance regression tests (<5% slower on any document)
- [ ] Memory regression tests (no >10% increases)
- [ ] Section detection accuracy >90% on test corpus
- [ ] Table extraction accuracy >95% on validation set

### Manual Validation (Maintainer Review)
- [ ] Print full document text for 10 sample filings → verify quality
- [ ] Compare table rendering old vs new → verify improvement
- [ ] Test section extraction on edge cases → verify robustness
- [ ] Review markdown output → verify professional appearance
- [ ] Check memory usage → verify no concerning spikes

### Documentation Requirements
- [ ] Migration guide (old API → new API with examples)
- [ ] Updated user guide showing new features
- [ ] Performance comparison report (old vs new)
- [ ] Known limitations documented clearly
- [ ] API reference complete for all public methods

## Success Metrics

### Launch Criteria
1. **Speed**: Equal or faster on 95% of test corpus
2. **Accuracy**: Maintainer approves output quality on sample set
3. **API**: Clean, intuitive interface (no confusion)
4. **Tests**: Zero regressions, 95%+ coverage on new code
5. **Docs**: Complete with examples for all major use cases

### Post-Launch Monitoring
- Issue reports: <5% related to parser quality/accuracy
- User feedback: Positive sentiment on ease of use
- Performance: No degradation over time (regression tests)
- Adoption: Smooth migration from old parser (deprecation path)

## Feature Parity with Old Parser

### Must-Have (Required for Migration)
- ✅ Get document text (with/without tables)
- ✅ Extract specific sections by name/number
- ✅ List all tables in document
- ✅ Search document content
- ✅ Convert to markdown
- ✅ Handle both old and new SEC filing formats
- ✅ Graceful error handling

### Nice-to-Have (Improvements Over Old Parser)
- 🎯 Semantic search capabilities
- 🎯 Better subsection extraction within Items
- 🎯 Table-of-contents navigation
- 🎯 Export to multiple formats (JSON, clean HTML)
- 🎯 Batch processing optimizations
- 🎯 Section confidence scores and metadata

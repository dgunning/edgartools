# SGML Parser Review & Rewrite Plan

## Part 1: Comprehensive Review

### Architecture Overview

The parser lives in `edgar/sgml/` with 7 files totaling ~3,200 lines:

| File | Lines | Responsibility |
|------|-------|---------------|
| `sgml_parser.py` | 594 | Core parsing: format detection, document extraction, two format parsers |
| `sgml_header.py` | 1031 | Header metadata parsing into domain objects (Filer, ReportingOwner, etc.) |
| `sgml_common.py` | 501 | High-level API (`FilingSGML`), I/O, orchestration |
| `filing_summary.py` | 668 | FilingSummary.xml parsing (separate concern, out of scope) |
| `table_to_dataframe.py` | 352 | HTML table extraction (separate concern, out of scope) |
| `tools.py` | 84 | Content extraction utilities |
| `__init__.py` | 5 | Public exports |

The parser handles two SEC SGML formats:
- **SEC-DOCUMENT format** (1993-present): `<SEC-DOCUMENT>...<SEC-HEADER>...` with tab-indented headers
- **SUBMISSION format** (~2000s-present): `<SUBMISSION>...<FILER>...<COMPANY-DATA>...` with XML-style nesting

### Performance Benchmarks (Apple M-series, Python 3.12)

| File | Size | Parse Time | Peak Memory | Docs | Notes |
|------|------|-----------|-------------|------|-------|
| Apple 10-K | 9.3MB | 52ms | 23.4MB | 102 | Largest common filing |
| SC 13D | 3.3MB | 14ms | 8.6MB | 5 | SUBMISSION format |
| 10-K/A | 2.0MB | 10ms | 4.6MB | 8 | SEC-DOCUMENT format |
| 10-K | 233KB | 3ms | 0.7MB | 14 | Typical modern filing |
| Form 4 | 9KB | 96ms | 0.1MB | 2 | **Anomaly: Entity lookup** |
| 1995 filing | 39KB | 0.5ms | 0.1MB | 2 | Legacy format |

**Memory amplification**: 2.5x input size (9.3MB input -> 23.4MB peak). Documents are stored as full string copies.

### Correctness Assessment

**What it gets right:**
- Two-format detection is reliable with proper ordering (SGML check before HTML check)
- Tag validation (`_is_valid_sgml_tag`) correctly distinguishes SGML from embedded HTML/XBRL
- Hierarchical header parsing handles nested sections properly
- UU-encoded binary content decoded correctly via vendored `uu` module
- Extensive edge case handling for 1990s/2000s format quirks
- Fallback preprocessing for really old filings

**Correctness issues found:**

1. **Regex `[\s\S]*?` non-greedy is fragile for nested DOCUMENT tags** (`sgml_parser.py:569`, `sgml_common.py:140`). If a filing ever contained a literal `</DOCUMENT>` string inside a document's text content, the regex would truncate early. The line-by-line parsers handle this correctly, but `iter_documents()` uses regex and could fail.

2. **`_is_data_tag` false positive** (`sgml_parser.py:292-299`): `line.split('>')` with `len(parts) == 2` will fail on lines like `<TAG>value>more` (value containing `>`). This was partially fixed in the header parser with `split('>', 1)` but not in the submission format parser.

3. **`get_content_type()` is side-effectful** (`sgml_parser.py:97-108`): Calls `self.xml()`, `self.html()`, `self.xbrl()` which each run a regex on the full raw_content. If called just to check the type, it does 3x unnecessary work.

4. **Duplicate `parse_document()`**: Exists in both `sgml_parser.py:577-593` and `sgml_common.py:22-38` with identical code.

5. **`SecDocumentFormatParser` document collection bug** (`sgml_parser.py:501`): `elif document_buffer is not None` is always true because `document_buffer` is initialized as `[]` (truthy after first `<DOCUMENT>`, but the initial value `[]` is not `None`). This means lines before the first `<DOCUMENT>` are silently appended to the empty list.

6. **Entity lookup in header parsing** (`sgml_header.py:849-852`): The `parse_from_sgml_text` method makes a network call (`Entity(cik)`) to check if a reporting owner is a person (for name reversal). This is a **side effect inside a parser** - it can fail, add 100ms+ latency, and makes the parser non-deterministic. This caused the 96ms anomaly for the 9KB Form 4 filing.

7. **Silent exception swallowing** (`sgml_common.py:208-211`): Header parsing catches `Exception` broadly and retries with preprocessing. This hides real bugs.

### Performance Assessment

**Profiling breakdown** (Apple 10-K, 9.3MB):

| Operation | Time | % of Total |
|-----------|------|-----------|
| `splitlines()` | 7.6ms | 22% |
| Line iteration + tag classification | ~15ms | 44% |
| Document buffer join (`'\n'.join()`) | ~8ms | 24% |
| Document metadata regex (4 per doc) | ~0.3ms | 1% |
| Format detection | 0.01ms | <1% |
| **Total** | **~33ms** | |

**Comparative benchmarks** (same 9.3MB file):

| Approach | Time | Relative |
|----------|------|----------|
| Current parser (line-by-line) | 33ms | 1.0x |
| `str.find()` for boundaries + metadata | 3.5ms | **9.4x faster** |
| Regex `finditer` for `<DOCUMENT>` | 115ms | 3.5x slower |

**Key bottlenecks:**
1. **Line-by-line processing**: `splitlines()` + iteration + string joins = ~80% of time. The parser splits the entire multi-MB content into lines, processes each, then joins them back.
2. **String duplication**: Every document's content is copied via `'\n'.join(buffer)`. For a 9.3MB filing, this creates 9.3MB of new strings.
3. **`iter_documents()` regex**: Uses `[\s\S]*?` on multi-MB strings - 115ms vs 3ms for `str.find()`.
4. **Non-compiled regex**: `_is_valid_sgml_tag()` imports `re` and calls `re.match()` on every invocation instead of using a compiled pattern.

### Memory Assessment

| Component | Size | Notes |
|-----------|------|-------|
| Input string | 9.3MB | Kept alive by lazy document references |
| Parsed `data['documents']` list | ~9.3MB | Full content strings in dicts |
| `SGMLDocument.raw_content` | ~9.3MB | Another copy when `from_parsed_data()` called |
| Peak observed | 23.4MB | ~2.5x input |

The content flows through 3 copies:
1. Original input string
2. `'\n'.join(document_buffer)` in parser -> stored in `data['documents'][n]['content']`
3. `SGMLDocument.raw_content` = `data['content']` (same reference, but `data` dict kept alive)

With lazy documents using offsets: **8.77KB** vs **9.31MB** for document metadata storage (1000x reduction). Content only materialized on access.

### Robustness Assessment

**Strengths:**
- Handles 30+ years of SEC format evolution (1993-2025)
- Three specific exception types for SEC errors (identity, not found, HTML response)
- Fallback preprocessing for 1990s headers
- Tag validation prevents HTML/XBRL tag confusion

**Weaknesses:**
- No input size limits (could OOM on malicious input)
- No timeout protection on the Entity network call
- Broad `except Exception` hides bugs
- No validation that document count matches header's `PUBLIC DOCUMENT COUNT`
- Missing handling for truncated/corrupted files (partial `<DOCUMENT>` at end of file)

---

## Part 2: Rewrite Plan

### Goals
1. **10x faster parsing** for large filings (str.find over line-by-line)
2. **2-3x memory reduction** via lazy document content (offsets, not copies)
3. **Zero network calls** during parsing (remove Entity lookup side effect)
4. **Maintain 100% API compatibility** (same classes, same methods, same return types)
5. **Improve robustness** for edge cases and corrupted input

### Architecture

```
sgml_parser.py (rewritten)
  SGMLParser          - Format detection + dispatch
  DocumentIndex       - Lightweight doc registry with (start, end) offsets
  HeaderExtractor     - Extract raw header text by format

sgml_header.py (refactored)
  FilingHeader        - Unchanged public API
  (Remove Entity lookup from parse path)

sgml_common.py (simplified)
  FilingSGML          - Unchanged public API, uses lazy documents internally
  SGMLDocument        - Now stores offset reference instead of content copy
```

### Phase 1: Core Parser Rewrite (sgml_parser.py)

Replace line-by-line parsing with offset-based scanning:

```python
class SGMLParser:
    def parse(self, content: str) -> ParsedSubmission:
        format_type = self.detect_format(content)
        header_text = self._extract_header(content, format_type)
        documents = self._extract_documents(content)
        header_data = self._parse_header_structure(header_text, format_type)
        return ParsedSubmission(format_type, header_text, header_data, documents, content)
```

**Document extraction** - `str.find()` loop instead of regex or line-by-line:
```python
def _extract_documents(self, content: str) -> list[DocumentRef]:
    docs = []
    pos = 0
    while True:
        start = content.find('<DOCUMENT>', pos)
        if start == -1:
            break
        end = content.find('</DOCUMENT>', start)
        if end == -1:
            break  # truncated file
        inner_start = start + 10
        # Extract metadata from first 500 chars only
        meta = self._extract_doc_metadata(content, inner_start, min(inner_start + 500, end))
        docs.append(DocumentRef(meta, inner_start, end))
        pos = end + 11
    return docs
```

**Metadata extraction** - `str.find()` instead of regex:
```python
def _extract_doc_metadata(self, content, start, end):
    region = content[start:end]
    result = {}
    for tag in ('TYPE', 'SEQUENCE', 'FILENAME', 'DESCRIPTION'):
        marker = '<' + tag + '>'
        idx = region.find(marker)
        if idx >= 0:
            val_start = idx + len(marker)
            val_end = region.find('\n', val_start)
            result[tag] = region[val_start:val_end].strip() if val_end >= 0 else region[val_start:].strip()
    return result
```

**Expected improvement**: 33ms -> ~4ms for 9.3MB Apple 10-K (measured in prototype).

### Phase 2: Lazy SGMLDocument

Replace eager string storage with offset references:

```python
@dataclass
class SGMLDocument:
    type: str
    sequence: str
    filename: str
    description: str
    _content_ref: str = field(repr=False)   # reference to original content string
    _start: int = field(repr=False)
    _end: int = field(repr=False)

    @property
    def raw_content(self) -> str:
        """Content materialized on access from original string."""
        return self._content_ref[self._start:self._end]
```

**Expected improvement**: Document metadata storage drops from 9.3MB to ~9KB. Total peak memory from 23.4MB to ~14MB (input string + header objects + one materialized document at a time).

### Phase 3: Header Parser Cleanup (sgml_header.py)

1. **Remove Entity lookup** from `parse_from_sgml_text()` (line 849-852). Move name reversal to display layer or make it opt-in.

2. **Pre-compile regex patterns** at module level:
```python
_ACCEPTANCE_RE = re.compile(r'<ACCEPTANCE-DATETIME>(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})')
_SGML_TAG_RE = re.compile(r'^[A-Z0-9\-]+$')
_DATE_14_RE = re.compile(r'^(20|19)\d{12}$')
_DATE_8_RE = re.compile(r'^(20|19)\d{6}$')
```

3. **Simplify SUBMISSION format header parsing**: The submission format parser already produces a structured dict. The header parser then re-parses it into domain objects with extensive boilerplate (lines 406-625 are almost identical to lines 676-996). Extract shared builder functions.

4. **Fix broad exception catch**: Replace `except Exception` with specific exceptions.

**Expected improvement**: Form 4 parsing drops from 96ms to <2ms (no network call). Header parsing code reduced by ~200 lines.

### Phase 4: Deduplication & Cleanup

1. **Remove duplicate `parse_document()`** - exists in both `sgml_parser.py` and `sgml_common.py`.
2. **Remove `iter_documents()` regex approach** - replace with offset-based scanning consistent with main parser.
3. **Fix `_is_data_tag`** to use `split('>', 1)` consistently.
4. **Remove `import re` inside `_is_valid_sgml_tag`** - use module-level compiled pattern.
5. **Fix `get_content_type()`** to use a single pass instead of 3 sequential regex searches.

### Phase 5: Robustness Hardening

1. **Input size guard**: Warn on files >50MB, reject >200MB (largest real SEC filing is ~50MB).
2. **Truncation detection**: If `</DOCUMENT>` not found after `<DOCUMENT>`, handle gracefully.
3. **Document count validation**: Compare parsed count against header's `PUBLIC DOCUMENT COUNT`.
4. **Encoding detection**: Sniff BOM/encoding before parsing for non-UTF-8 files.

### Migration Strategy

- All changes are internal implementation details
- Public API (`FilingSGML`, `SGMLDocument`, `FilingHeader`, `iter_documents`, etc.) remains identical
- `SGMLDocument.raw_content` changes from stored string to lazy property - **same interface**
- Run existing test suite (`test_filing_sgml.py`, `sgml_tests.py`) against rewrite to verify
- Add performance regression tests with assertions on timing/memory

### Expected Final Performance

| Metric | Current | After Rewrite | Improvement |
|--------|---------|---------------|-------------|
| Parse 9.3MB | 52ms | ~5ms | **10x** |
| Parse 233KB | 3ms | <1ms | **3x** |
| Peak memory (9.3MB input) | 23.4MB | ~14MB | **1.7x** |
| Document storage | 9.3MB copied | 9KB offsets | **1000x** |
| Form 4 with reporting owner | 96ms | <2ms | **48x** |
| `iter_documents()` | 115ms (regex) | ~4ms (find) | **28x** |

### Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Lazy document breaks callers who modify `raw_content` | No callers modify it (read-only usage confirmed) |
| `str.find` misses edge cases vs regex | Comprehensive test suite + fuzz testing on test data |
| Removing Entity lookup changes header output | Name stays as-is (SEC format), reversal only at display |
| Memory reference keeps full content alive | Acceptable tradeoff; can add explicit `detach()` if needed |

### Implementation Order

1. Phase 1 + 2 together (core parse + lazy docs) - biggest impact
2. Phase 3 (header cleanup) - removes the worst performance anomaly
3. Phase 4 (dedup/cleanup) - code quality
4. Phase 5 (robustness) - hardening

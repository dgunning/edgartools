# Memory Usage Analysis - HTML Parser

**Generated**: 2025-10-08
**Investigation**: MSFT 10-K Memory Spike
**Updated**: 2025-10-08 - Memory leak investigation completed

---

## ⚠️ UPDATE (2025-10-08): Memory Leak Investigation Results

**TL;DR**:
- ✅ **NO leak with fast rendering** (now the default)
- ❌ **6.5 MB/doc leak with Rich rendering** (C extension issue)
- ✅ **Python objects ARE properly garbage collected**
- ✅ **Module import overhead (~70 MB) is expected and reused**

**For Full Details**: See `docs-internal/investigations/memory-leak-investigation-2025-10-08.md` and `docs-internal/investigations/rich-rendering-memory-leak.md`

### Key Findings from Investigation

1. **Module Import Overhead (70 MB)**:
   - **Status**: ✅ EXPECTED - Not a leak
   - **Cause**: Python caches imported modules (edgar, pandas, rich, lxml, etc.)
   - **Behavior**: Allocated once, reused for all subsequent parses
   - **Test**: Parsing 5 documents shows no memory growth beyond first parse

2. **Rich Rendering Memory Leak (6.5 MB per document)**:
   - **Status**: ❌ REAL LEAK - But only when `fast_table_rendering=False`
   - **Cause**: C extension allocations in lxml/pygments/Rich dependencies
   - **Impact**: Memory grows linearly with document count
   - **Mitigation**: ✅ Fast rendering made default (2025-10-08)

3. **Fast Rendering (Default)**:
   - **Status**: ✅ NO LEAK
   - **Memory**: Stable at ~70 MB (module imports) + ~4 MB per active document
   - **Performance**: 27% faster than Rich rendering
   - **Recommendation**: Keep as default (already done)

### What Was NOT a Leak

- ❌ Circular references (tested with weak refs - objects ARE collected)
- ❌ TableNode retention (objects ARE garbage collected)
- ❌ Cell/Row retention (objects ARE garbage collected)
- ❌ Module imports (expected caching behavior)

### What IS a Real Leak

- ✅ Rich rendering C extension memory (~6.5 MB per document)
- Only affects users who explicitly use `ParserConfig(fast_table_rendering=False)`
- Estimated impact: <5% of users (most use default)

---

## Executive Summary (Original Analysis)

### Critical Finding: 255MB Memory Leak! 🚨

**MSFT 10-K Analysis**:
- Document size: 7.8MB
- Peak memory: 226.5MB during parse
- **Memory leaked after cleanup**: 255.4MB
- **Memory ratio**: 19x document size

**Problem**: Memory is NOT being released after document deletion and garbage collection!

---

## Memory Usage Comparison

### Cross-Document Analysis

| Document | Size | Peak Usage | Ratio | Leaked | Status |
|----------|------|------------|-------|--------|--------|
| **MSFT.10-K** | 7.8MB | 226.5MB | **19.0x** | **255.4MB** | 🚨 CRITICAL |
| **Apple.10-K** | 1.8MB | 41.5MB | **22.9x** | **41.5MB** | 🚨 CRITICAL |
| Apple.10-Q | 1.1MB | 4.4MB | 4.1x | 4.4MB | ⚠️ WARNING |
| JPM.10-K | 50.2MB | 0.6MB | 0.0x | 0.6MB | ✅ GOOD |

**Key Insights**:
1. **Documents with many tables leak memory** (MSFT: 85 tables, Apple: 63 tables)
2. **Streaming mode (JPM) does NOT leak** - only 0.6MB leaked
3. **Memory ratio inversely correlates with size** - small docs have highest ratio

---

## MSFT 10-K Detailed Lifecycle Analysis

### Memory Growth by Stage

```
1. Before parse:       155.3MB  (baseline)
2. After parse:        381.8MB  (+226.5MB) ← Main allocation
3. After full access:  389.9MB  (+8.1MB)   ← Tables/sections
4. After deref:        397.4MB  (+7.5MB)   ← Still growing!
5. After del doc:      405.1MB  (+7.8MB)   ← Still growing!
6. After GC:           410.7MB  (+5.6MB)   ← STILL GROWING!

Final leaked: 255.4MB (16.4x increase from baseline)
```

**Critical Observation**: Memory continues to **grow** even after:
- Dereferencing all properties
- Deleting the document object
- Running garbage collection

This indicates **strong references** preventing deallocation.

---

## Memory Allocation Hotspots

### Top Memory Allocators (MSFT 10-K)

| Location | Allocation | Objects | Avg Size | Notes |
|----------|------------|---------|----------|-------|
| `nodes.py:354` | +2.16MB | 422 | 5.4KB | **TableNode objects** |
| `table_processing.py:246` | +2.04MB | 38,136 | 56B | **Cell objects** |
| `rich/console.py:2136` | +0.38MB | 85 | 4.7KB | **Rich Console objects** |
| `document_builder.py:547` | +0.39MB | 1,434 | 284B | Text extraction |

**Analysis**:
- **TableNode objects**: 422 TableNodes × 5.4KB = 2.16MB
  - MSFT has only 85 tables, but 422 TableNode objects created
  - **Problem**: Creating multiple TableNode instances per table

- **Cell objects**: 38,136 cells × 56B = 2.04MB
  - Reasonable for table data
  - These ARE released after GC (good)

- **Rich Console**: 0.38MB retained
  - **Problem**: Rich Console objects not being released
  - Likely cached in table rendering

---

## Memory Leak Root Causes

### 1. Rich Library Object Retention 🔥

**Evidence**:
```python
# From profiling:
After GC: -0.38MB from rich/console.py:2136 (85 objects)
```

**Problem**: Rich Console/Table objects are created during parsing but retained somewhere:
- Likely in `_text_cache` or similar caches
- Rich objects hold references to rendered content
- Not cleared when document is deleted

**Impact**: ~0.4MB per 85 tables = 4.7KB per table in Rich objects

### 2. Global Reference Retention

**Evidence**: Memory grows even after `del doc` and `gc.collect()`

**Likely causes**:
1. **Cache Manager**: Global cache not clearing document-specific entries
2. **Rich global state**: Rich may cache console/rendering state globally
3. **lxml tree retention**: lxml ElementTree may be referenced globally

### 3. Circular References

**Evidence**: Memory freed only after explicit `gc.collect()`, but not fully

**Problem**: Circular references in node graph:
```python
# nodes.py
class Node:
    children: List[Node]  # Parent → Child
    parent: Optional[Node]  # Child → Parent
```

**Impact**: Python's reference counting can't clean up circular references without GC

---

## Comparison: Why JPM Doesn't Leak

### JPM 10-K (Streaming Mode) - ✅ NO LEAK

```
Document size: 50.2MB
Peak usage:    0.6MB
Leaked:        0.6MB (minimal)
```

**Why streaming mode works**:
1. **Elements cleared during parsing**:
   ```python
   # streaming.py:100-104
   parent = elem.getparent()
   if parent is not None:
       del parent[0]  # Clears processed elements
   ```

2. **No full tree retention**: Streaming parser doesn't keep entire lxml tree
3. **Lazy table extraction**: Tables extracted on-demand, not eagerly
4. **Minimal caching**: Streaming mode uses minimal caching

**Conclusion**: Streaming mode's aggressive cleanup prevents leaks!

---

## Impact Analysis

### Memory Cost per Document Type

| Form Type | Typical Size | Tables | Memory Cost | Leak | Efficiency |
|-----------|--------------|--------|-------------|------|------------|
| 10-Q | 1-2MB | 30-40 | 40MB | 40MB | Poor (20x) |
| 10-K (Tech) | 2-5MB | 60-80 | 200MB | 200MB | Poor (40x) |
| 10-K (Finance) | 5-10MB | 80-100 | 250MB | 250MB | Poor (25x) |
| 10-K (Large) | >50MB | 500+ | 1MB | 1MB | Good (0.02x) |

**Business Impact**:
- **Batch processing**: Memory accumulates with each document
  - 10 × 10-K filings = 2GB memory consumption
  - Server crashes after processing 20-30 filings

- **API services**: Each request leaks 40-250MB
  - Memory exhaustion after 10-20 requests
  - Requires frequent restarts

---

## Recommended Fixes

### 🔥 CRITICAL: Fix Memory Leaks

#### 1. Clear Global Caches on Document Deletion

```python
# document.py
class Document:
    def __del__(self):
        """Clean up when document is deleted."""
        # Clear text caches
        if hasattr(self, '_text_cache'):
            self._text_cache.clear()

        # Clear table caches
        for table in self._tables:
            if hasattr(table, 'clear_text_cache'):
                table.clear_text_cache()

        # Clear from global cache manager
        get_cache_manager().clear_document(self.metadata.id)
```

#### 2. Avoid Rich for Text Extraction

**Current** (creates Rich objects):
```python
def text(self) -> str:
    return rich_to_text(self.render())  # Creates Rich Console
```

**Fixed** (direct string building):
```python
def text(self) -> str:
    """Fast text extraction without Rich."""
    return self._fast_text_rendering()  # No Rich objects
```

**Expected gain**: Eliminates 0.4MB+ Rich object retention per document

#### 3. Break Circular References

```python
# nodes.py
class Node:
    def clear_references(self):
        """Break circular references for GC."""
        self.parent = None
        for child in self.children:
            child.clear_references()
        self.children.clear()

# document.py
def __del__(self):
    self.root.clear_references()
```

#### 4. Use Weak References for Parent Links

```python
import weakref

class Node:
    def __init__(self):
        self._parent = None  # Use weak reference

    @property
    def parent(self):
        return self._parent() if self._parent else None

    @parent.setter
    def parent(self, value):
        self._parent = weakref.ref(value) if value else None
```

### 🟡 MEDIUM: Optimize Memory Usage

#### 5. Use `__slots__` for Frequently Created Objects

```python
@dataclass(slots=True)
class Cell:
    """Memory-efficient cell with __slots__."""
    content: str
    colspan: int = 1
    rowspan: int = 1
    is_header: bool = False
```

**Expected gain**: 30-40% less memory per cell (2MB → 1.2MB for MSFT)

#### 6. Lazy Table Extraction

```python
@cached_property
def tables(self):
    """Extract tables only when accessed."""
    return self._extract_tables()
```

**Expected gain**: Zero memory for tables if never accessed

---

## Testing Recommendations

### Memory Regression Tests

```python
# tests/perf/test_memory_regression.py

def test_no_memory_leak_after_parse():
    """Ensure memory is released after document deletion."""
    import gc, psutil

    process = psutil.Process()
    mem_before = process.memory_info().rss

    html = Path('data/html/MSFT.10-K.html').read_text()
    doc = parse_html(html)
    _ = doc.tables
    _ = doc.sections
    del doc
    gc.collect()

    mem_after = process.memory_info().rss
    leaked = (mem_after - mem_before) / (1024 * 1024)

    # Allow up to 5MB leak for small overhead
    assert leaked < 5, f"Memory leak detected: {leaked:.1f}MB"
```

---

## Success Criteria

### Memory Targets (after fixes)

| Metric | Current | Target | Priority |
|--------|---------|--------|----------|
| Memory ratio | 19-23x | <3x | CRITICAL |
| Leaked memory | 41-255MB | <5MB | CRITICAL |
| Peak usage | 226MB | <25MB | HIGH |
| GC effectiveness | Poor | Good | HIGH |

**Target**: After fixes, MSFT 10-K should use <25MB peak, leak <5MB

---

## Next Steps

1. ✅ **Memory profiling complete** - Root causes identified
2. 🔧 **Implement leak fixes** - Clear caches, avoid Rich for text
3. 🔧 **Break circular references** - Use weak references
4. 🔧 **Add __slots__** - Reduce per-object overhead
5. 🧪 **Add memory regression tests** - Prevent future leaks
6. 📊 **Re-benchmark** - Validate fixes

---

## Appendix: Detailed Memory Snapshots

Full memory snapshots available via:
```bash
python -m tests.perf.profile_memory --file data/html/MSFT.10-K.html --lifecycle
```

Key files:
- `tests/perf/profile_memory.py` - Memory profiling tool
- `tests/perf/memory_analysis.md` - This report

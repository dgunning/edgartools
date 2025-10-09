# Hot Path Analysis - HTML Parser Performance

**Generated**: 2025-10-08
**Document**: Apple.10-K.html (1.8MB, 5 iterations)
**Total Time**: 5.865s (1.173s per iteration)

---

## Critical Performance Bottlenecks

### 1. **Section Extraction Dominates Parse Time (63%)**

**Time spent**: 3.698s / 5.865s = 63% of total time

**Hot functions**:
- `_enhance_sections`: 3.698s (63%)
- `extract` (section_extractor): 3.688s (63%)
- `_detect_filing_type`: 3.032s (52%)
- `_get_node_position`: 0.587s (10%) - **Very expensive**

**Root cause**:
```
sections property → extract() → _detect_filing_type() → node.text()
                                                       ↓
                                            Calls rich_to_text() on ENTIRE document
                                            to find section patterns
```

**Impact**: For a 1.8MB document, we're rendering 645 tables to text using Rich (2.4s) just to detect sections!

### 2. **Rich Table Rendering in Text Extraction (40%)**

**Time spent**: 2.357s / 5.865s = 40% of total time

**Hot functions**:
- `rich_to_text`: 2.427s (41%)
- `console.print`: 2.357s (40%)
- `table._render`: 2.023s (34%)

**Problem**: Text extraction calls `rich_to_text()` which renders tables using Rich Console:

```python
# table_nodes.py:164
def text(self) -> str:
    """Get text representation of table."""
    return rich_to_text(self.render())  # ← Renders to Rich, then extracts text
```

**Impact**: We're using a **display library** (Rich) for **text extraction** - massive overhead!

### 3. **Regular Expression Overhead (15%)**

**Time spent**: 0.890s / 5.865s = 15% of total time

**Hot pattern**:
- `re.Pattern.sub()`: 0.788s (called 34,675 times!)
- In `_normalize_whitespace`: Applies 10+ regex patterns to entire document

### 4. **Node Walking Inefficiency**

**Time spent**: 0.351s / 5.865s = 6% of total time

**Pattern**:
- `walk()` called 3.5M times (called 738K primitive calls)
- Multiple passes over the same tree for different extractions

---

## Performance Breakdown by Operation

### Parse Pipeline Stages

| Stage | Time | % of Total | Key Operations |
|-------|------|------------|----------------|
| **Section Extraction** | 3.698s | 63% | Text rendering, pattern matching |
| **HTML Preprocessing** | 0.912s | 16% | Regex normalization, entity fixes |
| **Document Building** | 0.979s | 17% | Tree construction, node creation |
| **XBRL Extraction** | 0.213s | 4% | XBRL fact parsing |
| **Postprocessing** | 0.172s | 3% | Statistics, validation |

**Finding**: **Section extraction is 3.8x slower than building the entire document tree!**

---

## Specific Optimization Opportunities

### 🔥 **CRITICAL: Section Detection**

**Current approach**:
1. Extract ALL sections by rendering ENTIRE document to text
2. Apply regex patterns to find "Item 1", "Item 7", etc.
3. For each section, call `text()` on table nodes → renders using Rich

**Problem**: For a 1.8MB document with 63 tables:
- Renders all 63 tables to Rich format
- Converts Rich output to plain text
- Searches text for patterns
- **Total**: 3.7s for section detection alone

**Optimization**:
```python
# Instead of:
text = doc.text()  # ← Renders ALL tables using Rich!
sections = extract_sections_from_text(text)

# Do:
sections = extract_sections_from_headings(doc.headings)  # ← No table rendering
```

**Expected gain**: 60-70% faster (save ~2.5s on Apple 10-K)

### 🔥 **CRITICAL: Table Text Extraction**

**Current**:
```python
def text(self) -> str:
    return rich_to_text(self.render())  # Rich rendering overhead
```

**Optimization**:
```python
def text(self) -> str:
    """Direct text extraction without Rich rendering."""
    return self._fast_text_rendering()  # Direct string building
```

**Expected gain**: 50% faster text extraction (save ~1.2s)

### 🔴 **HIGH PRIORITY: Regex Normalization**

**Current**: Applies 10+ regex patterns sequentially in `_normalize_whitespace`

**Called**: 34,675 times (taking 0.788s)

**Optimization**:
1. Combine multiple patterns into single pass
2. Use compiled patterns
3. Skip normalization for display-only nodes

**Expected gain**: 30-40% faster preprocessing (save ~0.3s)

### 🟡 **MEDIUM: Multiple Tree Walks**

**Current**: Walk tree separately for:
- Sections
- Tables
- Headings
- Text
- XBRL

**Optimization**: Single-pass extraction collecting all data types

**Expected gain**: 20-30% fewer tree operations

---

## Cumulative Time Analysis

### Top 10 Functions by Cumulative Time

| Function | Cumulative | Self | Calls | Impact |
|----------|-----------|------|-------|--------|
| `_enhance_sections` | 3.698s | 0.002s | 5 | 63% - Section detection |
| `rich_to_text` | 2.427s | 0.001s | 315 | 41% - Rich rendering |
| `console.print` | 2.357s | 0.004s | 315 | 40% - Console output |
| `table._render` | 2.023s | 0.105s | 183K | 34% - Table rendering |
| `_process_element` | 0.978s | 0.036s | 10.6K | 17% - Tree building |
| `_normalize_whitespace` | 0.430s | 0.000s | 5 | 7% - Regex processing |

### Top 10 Functions by Self Time

| Function | Self Time | Calls | Time/Call | Type |
|----------|-----------|-------|-----------|------|
| `re.Pattern.sub` | 0.788s | 34,675 | 0.023ms | Regex |
| `walk` | 0.351s | 3.5M | 0.0001ms | Tree traversal |
| `_get_node_position` | 0.172s | 625 | 0.275ms | Position calc |
| `console.render` | 0.128s | 334K | 0.0004ms | Rich rendering |
| `_extract_text` | 0.087s | 31,765 | 0.003ms | Text extraction |

---

## Memory Profiling Insights

From benchmark data (Apple 10-K):
- Document size: 1.8MB
- Peak memory: 12.6MB
- **Memory ratio**: 7x document size

**Potential causes**:
1. Multiple tree representations (lxml + DocumentNode)
2. Rich table objects kept in memory
3. Cached text representations
4. XBRL fact storage

---

## Recommended Optimization Priority

### Phase 1: Quick Wins (1-2 days)

1. ✅ **Fix section detection**
   - Don't render tables for section detection
   - Use heading-based detection
   - **Est. gain**: 2.5s per Apple 10-K (60% faster)

2. ✅ **Fast text extraction for tables**
   - Direct string building instead of Rich rendering
   - **Est. gain**: 1.2s per Apple 10-K (30% faster)

3. ✅ **Optimize regex normalization**
   - Combine patterns
   - Use compiled patterns
   - **Est. gain**: 0.3s per Apple 10-K (5% faster)

**Total expected improvement**: ~4s → ~0.9s (77% faster on Apple 10-K)

### Phase 2: Structural Improvements (3-4 days)

4. **Single-pass extraction**
   - Combine section/table/heading extraction
   - **Est. gain**: 15-20% faster

5. **Lazy loading optimization**
   - Defer expensive operations until accessed
   - **Est. gain**: 30-50% for partial access

6. **Memory optimization**
   - Use __slots__ for frequently created objects
   - Clear lxml tree after parsing
   - **Est. gain**: 3-5x lower memory usage

---

## Next Steps

1. ✅ **Profile MSFT 10-K** - Understand why memory is 5.4x doc size
2. 🔧 **Implement fast text extraction** - Remove Rich dependency for text
3. 🔧 **Fix section detection** - Use headings instead of full text
4. 📊 **Re-benchmark** - Validate improvements
5. 🧪 **Performance regression tests** - Lock in improvements

---

## Appendix: Detailed Profile Data

Full profile data saved to:
- `tests/perf/profile_Apple.10-K.stats`
- View with: `python -m pstats tests/perf/profile_Apple.10-K.stats`
- Visualize with: `snakeviz tests/perf/profile_Apple.10-K.stats`

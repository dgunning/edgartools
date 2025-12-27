# Table Extraction: Detailed Comparison Report

**Date:** 2025-12-24
**Comparing:**
- `edgar/llm_extraction.py` table processing (lines 1390-1990+)
- `edgar/documents/table_nodes.py` TableNode approach

---

## Executive Summary

You're **absolutely correct**. The `edgar/documents` table extraction is **basic** compared to `llm_extraction.py`. The LLM extraction module has **sophisticated, battle-tested table processing** specifically designed for SEC filing complexity that goes far beyond what `edgar.documents` provides.

### Key Finding

**`llm_extraction.py` contains advanced table processing logic that SHOULD be migrated into `edgar.documents` to make it production-grade.**

---

## Side-by-Side Comparison

### 1. Table Preprocessing

| Feature | llm_extraction.py | edgar.documents |
|---------|-------------------|-----------------|
| **Currency Cell Merging** | ✅ Advanced: Merges `$` + value cells, handles colspan | ⚠️ Basic: Only in to_dataframe() |
| **Percent Cell Merging** | ✅ Yes: Merges value + `%` cells (reverse scan) | ❌ No |
| **Width Grid Row Detection** | ✅ Yes: Filters layout rows with width styles | ❌ No |
| **XBRL Metadata Filtering** | ✅ Yes: Detects and skips XBRL namespace tables | ❌ No |

**Code Comparison:**

```python
# llm_extraction.py - Sophisticated preprocessing
def preprocess_currency_cells(table_soup):
    """Merges $ into next cell and adjusts colspan"""
    rows = table_soup.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        i = 0
        while i < len(cells):
            cell = cells[i]
            txt = clean_text(cell.get_text())
            if txt in ["$"] and i + 1 < len(cells):
                next_cell = cells[i + 1]
                next_cell.string = txt + clean_text(next_cell.get_text())
                next_cell["colspan"] = str(int(next_cell.get("colspan", 1)) + 1)
                cell.decompose()  # Remove $ cell
            i += 1

# edgar.documents - Basic approach
# Only merges in to_dataframe(), doesn't modify HTML structure
```

### 2. Header Detection

| Feature | llm_extraction.py | edgar.documents |
|---------|-------------------|-----------------|
| **Auto Header Detection** | ✅ Smart: Uses `<th>` tags + date patterns + label analysis | ⚠️ Basic: Relies on table structure |
| **Date Heading Recognition** | ✅ Yes: Regex patterns for dates → marks as header | ❌ No |
| **Multi-Row Header Handling** | ✅ Yes: Combines header rows intelligently | ✅ Yes: MultiIndex support |
| **Label Column Detection** | ✅ Yes: Scores columns for "labelish" content | ❌ No |
| **Year Detection** | ✅ Yes: Regex for 19\d{2}\|20\d{2} → forces header row | ❌ No |

**Code Comparison:**

```python
# llm_extraction.py - Intelligent header detection
def is_date_heading(value: str) -> bool:
    """Check if value looks like a date heading"""
    if not value:
        return False
    value = value.strip()
    if _looks_like_date_heading(value):
        return True
    return bool(year_re.search(value))  # 19XX or 20XX

# Automatically promotes rows to headers based on:
# 1. <th> tags
# 2. Date patterns (year_re)
# 3. Repeated values across row (title row)
# 4. Label-only content (no numerics)

# edgar.documents - Structure-based
# Uses self.headers list from HTML structure
# No automatic promotion or detection
```

### 3. Column Analysis

| Feature | llm_extraction.py | edgar.documents |
|---------|-------------------|-----------------|
| **Label Column Detection** | ✅ Advanced: Scores each column for labels | ❌ No |
| **Numeric Column Detection** | ✅ Yes: Checks for digits/$ symbols | ✅ Yes: Cell.is_numeric |
| **Date Column Detection** | ✅ Yes: Year regex matching | ❌ No |
| **Empty Column Filtering** | ✅ Yes: Removes placeholder columns | ❌ No |
| **Duplicate Column Detection** | ✅ Yes: Signature-based dedup | ❌ No |

**Code Comparison:**

```python
# llm_extraction.py - Smart column analysis
def is_numericish(s):
    return bool(re.search(r"[\d]", s)) or ("$" in s)

def is_labelish(s):
    return bool(re.search(r"[A-Za-z]", s)) and not is_numericish(s)

# Scores each column for label content
label_scores = []
for c in range(max_cols):
    score = sum(1 for r in matrix if is_labelish(r[c]))
    label_scores.append(score)
label_col = max(range(max_cols), key=lambda c: (label_scores[c], -c))

# edgar.documents - No column analysis
# Just processes all columns as-is
```

### 4. Row Classification

| Feature | llm_extraction.py | edgar.documents |
|---------|-------------------|-----------------|
| **Header Row Detection** | ✅ Multi-factor: `<th>` + dates + patterns + content | ⚠️ Basic: Structure-based |
| **Total Row Detection** | ✅ Yes: Checks first cell for "total" keywords | ✅ Yes: Row.is_total_row |
| **Data Row Validation** | ✅ Yes: Checks for numeric + label content | ❌ No |
| **Empty Row Filtering** | ✅ Yes: Skips rows with no meaningful content | ✅ Yes: Basic check |

**Code Comparison:**

```python
# llm_extraction.py - Multi-factor row classification
is_header = row_has_th  # Start with <th> tags

# Check for year patterns → force header
for c in range(max_cols):
    if c == label_col:
        continue
    if year_re.search(row[c]):  # Contains year
        is_header = True
        break

# Check for repeated values → title row
data_values = [row[c] for c in range(max_cols) if c != label_col and row[c].strip()]
if data_values and len(set(data_values)) == 1:
    is_header = True  # All cells same = title row

# Check for label-only content
label_values = [value for value in data_values if is_labelish(value)]
if label_values and len(set(label_values)) >= 2 and not has_numeric:
    is_header = True  # Multiple labels, no numbers = header

# edgar.documents - Structure-based
# Uses self.headers from HTML parsing
```

### 5. Cell Value Processing

| Feature | llm_extraction.py | edgar.documents |
|---------|-------------------|-----------------|
| **Text Cleaning** | ✅ Yes: `clean_text()` removes `\xa0`, `&nbsp;` | ⚠️ Basic |
| **Pipe Escaping** | ✅ Yes: Escapes `\|` for markdown | ❌ No |
| **Colspan Expansion** | ✅ Yes: Repeats value for colspan cells | ✅ Yes: TableMatrix |
| **Numeric Parsing** | ⚠️ Kept as string | ✅ Yes: Cell.numeric_value |
| **Currency Symbol Handling** | ✅ Advanced: Merges into value cell | ⚠️ Basic |

**Code Comparison:**

```python
# llm_extraction.py - Advanced text processing
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()

# Escape pipes for markdown
txt = clean_text(cell.get_text(" ", strip=True)).replace("|", r"\|")

# edgar.documents - Basic
# Uses cell.text() which preserves most formatting
```

### 6. Column Grouping (Advanced Feature)

| Feature | llm_extraction.py | edgar.documents |
|---------|-------------------|-----------------|
| **Header Grouping** | ✅ Yes: Groups columns by header signature | ❌ No |
| **Best Column Selection** | ✅ Yes: Selects column with most data | ❌ No |
| **Placeholder Header Detection** | ✅ Yes: Filters "col_N", "Row" placeholders | ❌ No |
| **Duplicate Prevention** | ✅ Yes: Signature-based deduplication | ❌ No |

**Code Comparison:**

```python
# llm_extraction.py - Sophisticated column grouping
if header_rows:
    column_groups = {}
    value_keys = [k for k in sorted_keys if k != label_key]

    # Group columns by their header signature
    for key in value_keys:
        signature = tuple(str(row.get(key, "")).strip() for row in header_rows)
        if signature not in column_groups:
            column_groups[signature] = []
        column_groups[signature].append(key)

    # For each group, select the column with most data
    for key in value_keys:
        signature = tuple(str(row.get(key, "")).strip() for row in header_rows)
        if signature in processed_signatures:
            continue  # Already processed

        candidate_keys = column_groups[signature]
        best_key = max(
            candidate_keys,
            key=lambda k: sum(
                1 for row in data_rows
                if str(row.get(k, "")).strip() not in ["", "-"]
            ),
        )

# edgar.documents - No grouping
# All columns processed as-is
```

### 7. Markdown Generation

| Feature | llm_extraction.py | edgar.documents |
|---------|-------------------|-----------------|
| **Table Format** | ✅ Pipe format with header combiner | ✅ Multiple formats (pipe/grid/simple) |
| **Header Deduplication** | ✅ Yes: Multi-row headers with "-" combiner | ⚠️ Basic: MultiIndex |
| **Column Width** | ⚠️ Auto (markdown) | ✅ Advanced: Smart width calculation |
| **Table Title** | ✅ Yes: Derived from first row or caption | ✅ Yes: Caption support |
| **Table Counter** | ✅ Yes: Auto-numbers tables | ❌ No |

**Code Comparison:**

```python
# llm_extraction.py - Markdown with smart headers
def list_of_dicts_to_table(data_list):
    # Multi-row header combination
    if header_rows:
        header_str = " - ".join([p for p in signature if p]) or best_key
        final_headers.append(header_str)

    # Create markdown table
    md = f"| {' | '.join(map(str, headers))} |\n"
    md += f"| {' | '.join(['---'] * len(headers))} |\n"
    for row in rows:
        md += f"| {' | '.join(cleaned_row)} |\n"

# edgar.documents - Rich markdown renderer
renderer = MarkdownRenderer()
markdown = renderer._render_table(table)
# Supports colspan/rowspan but less header intelligence
```

### 8. Table Deduplication

| Feature | llm_extraction.py | edgar.documents |
|---------|-------------------|-----------------|
| **Signature-Based Dedup** | ✅ Yes: Uses title + headers + rows (first 8) | ❌ No |
| **Cross-Section Dedup** | ✅ Yes: Prevents same table appearing twice | ❌ No |
| **Hash Function** | ✅ Custom: _table_signature() | ❌ No |

**Code Comparison:**

```python
# llm_extraction.py - Deduplication
def _table_signature(records, derived_title, max_rows: int = 8):
    """Create unique signature for table dedup"""
    if not records:
        return None
    keys = sorted({key for record in records for key in record.keys()})
    row_sig = []
    for record in records[:max_rows]:
        row_sig.append(
            tuple(_normalize_table_value(record.get(key, "")) for key in keys)
        )
    title_sig = _normalize_table_value(derived_title or "")
    return (title_sig, tuple(keys), tuple(row_sig), len(records))

# Track processed tables
table_signatures = set()
# ...
signature = _table_signature(records, derived_title)
if signature and signature in table_signatures:
    continue  # Skip duplicate
table_signatures.add(signature)

# edgar.documents - No deduplication
```

### 9. Content Integration

| Feature | llm_extraction.py | edgar.documents |
|---------|-------------------|-----------------|
| **Mixed Content** | ✅ Yes: Tables + paragraphs + headings | ✅ Yes: Full document model |
| **Long Row Text Extraction** | ✅ Yes: Rows >300 chars → text blocks | ❌ No |
| **Bold Heading Detection** | ✅ Yes: Extracts `<strong>` as headers | ✅ Yes: HeadingNode |
| **List Processing** | ✅ Yes: `<ul>/<ol>` → markdown lists | ✅ Yes: ListNode |
| **Duplicate Text Filtering** | ✅ Yes: Recent text deque (window=32) | ❌ No |
| **Noise Filtering** | ✅ Yes: XBRL metadata, URLs, etc. | ❌ No |

**Code Comparison:**

```python
# llm_extraction.py - Integrated content processing
def process_content(content, section_title=None):
    output_parts = []
    processed_tables = set()
    table_signatures = set()
    recent_text = deque(maxlen=32)  # Deduplication

    for element in elements:
        if element.name == "table":
            # Process table
            text_blocks, records, derived_title = html_to_json(element)

            # Extract long row text as paragraphs
            for block in text_blocks:
                if block["type"] == "text" and not is_noise_text(block["content"]):
                    output_parts.append(block["content"])

            # Add markdown table
            if records:
                signature = _table_signature(records, derived_title)
                if signature not in table_signatures:  # Dedup
                    md_table = list_of_dicts_to_table(records)
                    output_parts.append(f"\n#### Table: {derived_title}\n{md_table}\n")

        elif element.name in ["p", "div"]:
            # Check for bold headings
            heading_text = _extract_bold_heading(element)
            if heading_text:
                output_parts.append(f"\n### {heading_text}\n")
            else:
                # Regular text
                text = clean_text(element.get_text())
                if not should_skip_duplicate(text, recent_text):
                    output_parts.append(text)
                    recent_text.append(text.lower())

# edgar.documents - Separate rendering
# Document model handles structure
# Renderers handle conversion
```

---

## Repeated Processes

### Both Approaches Handle:

1. ✅ **Colspan/Rowspan** - Both expand to logical columns
2. ✅ **Multi-Row Headers** - Both support combining header rows
3. ✅ **Numeric Detection** - Both identify numeric cells
4. ✅ **Empty Row Filtering** - Both skip empty rows
5. ✅ **Markdown Generation** - Both output markdown tables

### Differences in Implementation:

| Process | llm_extraction.py | edgar.documents |
|---------|-------------------|-----------------|
| **Colspan Expansion** | Manual loop with `build_row_values()` | `TableMatrix.get_expanded_row()` |
| **Header Combining** | String concatenation with " - " | `pd.MultiIndex.from_arrays()` |
| **Numeric Detection** | Regex `[\d]` or `$` | `Cell.is_numeric` property |
| **Output Format** | Markdown string | DataFrame or Markdown via renderer |

---

## Gaps Analysis

### Missing in `edgar.documents`:

1. ❌ **Smart Header Detection**
   - No auto-promotion of date rows to headers
   - No year pattern detection
   - No repeated-value title row detection

2. ❌ **Column Intelligence**
   - No label column scoring
   - No column grouping by header signature
   - No placeholder header filtering
   - No duplicate column removal

3. ❌ **Table Preprocessing**
   - No currency cell merging (only in to_dataframe)
   - No percent cell merging
   - No width grid row filtering
   - No XBRL metadata table filtering

4. ❌ **Table Deduplication**
   - No signature-based duplicate detection
   - Tables can appear multiple times

5. ❌ **Content Integration**
   - No long row text extraction
   - No duplicate text filtering
   - Limited noise filtering

6. ❌ **Markdown Optimization**
   - No multi-row header combination with "-"
   - No auto table numbering
   - No derived titles from content

### Missing in `llm_extraction.py`:

1. ❌ **Structured Data Access**
   - No DataFrame export (only markdown)
   - No Cell/Row objects
   - No table type classification

2. ❌ **Advanced Rendering**
   - No width calculation
   - No alignment detection
   - No grid/simple formats

3. ❌ **Document Model**
   - No node hierarchy
   - No section integration
   - No metadata preservation

---

## Strengths of Each Approach

### `llm_extraction.py` Strengths:

1. ✅ **Battle-Tested for SEC Filings**
   - Handles real-world SEC table quirks
   - Currency/percent cells
   - Multi-row headers with dates
   - XBRL metadata filtering

2. ✅ **Smart Auto-Detection**
   - Header row detection
   - Label column detection
   - Title row extraction
   - Date pattern recognition

3. ✅ **Table Quality**
   - Deduplication prevents repeats
   - Column grouping reduces redundancy
   - Placeholder filtering keeps it clean

4. ✅ **Markdown Optimization**
   - Header combination
   - Table numbering
   - Integrated with text content

5. ✅ **Noise Filtering**
   - XBRL metadata removal
   - Width grid row filtering
   - Duplicate text prevention

### `edgar.documents` Strengths:

1. ✅ **Structured Data Model**
   - Cell, Row, TableNode objects
   - Type-safe access
   - Programmatic manipulation

2. ✅ **DataFrame Export**
   - Pandas DataFrame
   - MultiIndex support
   - Numeric value parsing

3. ✅ **Advanced Rendering**
   - Smart width calculation
   - Column alignment
   - Multiple output formats

4. ✅ **Document Integration**
   - Part of full document model
   - Section-aware
   - XBRL integration

5. ✅ **Clean Architecture**
   - Separation of concerns
   - Extensible strategies
   - Cacheable

---

## Recommendation

### Phase 1: Merge the Best of Both

**Migrate llm_extraction.py table logic INTO edgar.documents:**

```python
# edgar/documents/strategies/table_processing.py

class TableProcessor:
    """Enhanced table processor with llm_extraction logic"""

    def process(self, table_element):
        # 1. Preprocess (from llm_extraction)
        self._preprocess_currency_cells(table_element)
        self._preprocess_percent_cells(table_element)

        # 2. Filter noise (from llm_extraction)
        if self._is_xbrl_metadata_table(table_element):
            return None

        # 3. Parse to structured model (existing)
        table_node = self._parse_table_structure(table_element)

        # 4. Enhance headers (from llm_extraction)
        self._detect_header_rows(table_node)  # Year patterns, dates
        self._detect_label_column(table_node)  # Score columns

        # 5. Clean columns (from llm_extraction)
        self._remove_placeholder_columns(table_node)
        self._group_duplicate_columns(table_node)

        return table_node
```

### Phase 2: Unified API

```python
# Unified table extraction
table_node = document.tables[0]

# Access structured data (existing)
df = table_node.to_dataframe()

# Get clean markdown (enhanced with llm_extraction logic)
markdown = table_node.to_markdown(
    combine_headers=True,      # Use llm_extraction header combiner
    remove_duplicates=True,    # Use llm_extraction dedup
    auto_number=True           # Use llm_extraction numbering
)

# Get records (new - from llm_extraction)
records = table_node.to_records()  # List of dicts
```

### Phase 3: Deprecate Old Code

1. Mark `edgar/llm_extraction.py` table functions as deprecated
2. Update callers to use enhanced `edgar.documents`
3. Remove after migration period

---

## Detailed Code Migration Map

### Functions to Migrate:

| Function (llm_extraction.py) | Target Location | Priority |
|------------------------------|-----------------|----------|
| `preprocess_currency_cells()` | `TableProcessor.__init__` | P0 - Critical |
| `preprocess_percent_cells()` | `TableProcessor.__init__` | P0 - Critical |
| `is_xbrl_metadata_table()` | `TableProcessor.should_skip()` | P0 - Critical |
| `is_width_grid_row()` | `TableProcessor.should_skip()` | P1 - High |
| `html_to_json()` | `TableProcessor.parse()` | P0 - Critical |
| `list_of_dicts_to_table()` | `TableNode.to_markdown()` | P0 - Critical |
| `_table_signature()` | `TableNode.signature` property | P1 - High |
| `is_date_heading()` | `Cell.is_date_heading` property | P2 - Medium |
| `_extract_bold_heading()` | Keep in text extraction | N/A |

### Properties to Add to TableNode:

```python
@property
def signature(self) -> tuple:
    """Unique signature for deduplication (from llm_extraction)"""

@property
def label_column_index(self) -> int:
    """Auto-detected label column (from llm_extraction)"""

@property
def derived_title(self) -> Optional[str]:
    """Title extracted from first row (from llm_extraction)"""

def to_records(self) -> List[Dict]:
    """Convert to list of dicts (from llm_extraction)"""
```

---

## Testing Strategy

### Regression Tests:

1. **Compare Outputs**
   - Run both approaches on 100 SEC tables
   - Compare markdown output
   - Ensure no degradation

2. **Performance Tests**
   - Benchmark table processing time
   - Target: <10% slowdown with new features

3. **Edge Cases**
   - Currency cells (merged/separate)
   - Multi-row headers (3+ rows)
   - Wide tables (50+ columns)
   - XBRL metadata tables
   - Tables with colspan/rowspan

### Validation:

```python
# Test case: Ensure currency merging works
html = """
<table>
  <tr><th>Item</th><th>$</th><th>2024</th></tr>
  <tr><td>Revenue</td><td>$</td><td>100</td></tr>
</table>
"""

# Expected: $ merged into value cells
# | Item | 2024 |
# | Revenue | $100 |
```

---

## Implementation Checklist

- [ ] Create `edgar/documents/strategies/table_enhancement.py`
- [ ] Migrate preprocessing functions
- [ ] Migrate header detection logic
- [ ] Migrate column analysis logic
- [ ] Add `TableNode.to_records()` method
- [ ] Add `TableNode.signature` property
- [ ] Enhance `TableNode.to_markdown()` with llm_extraction logic
- [ ] Add deduplication support to DocumentPostprocessor
- [ ] Create comprehensive test suite
- [ ] Update documentation
- [ ] Deprecate llm_extraction table functions
- [ ] Migration guide for users

---

## Conclusion

**Your instinct was 100% correct.** The `edgar.documents` table extraction is basic compared to `llm_extraction.py`.

### Key Findings:

1. ✅ **llm_extraction.py has superior table intelligence**
   - Auto header detection
   - Label column scoring
   - Column grouping
   - Table deduplication
   - Currency/percent merging

2. ✅ **edgar.documents has better architecture**
   - Structured data model
   - DataFrame export
   - Clean separation of concerns

3. ✅ **Both are needed**
   - Migrate llm_extraction logic into edgar.documents
   - Keep structured model
   - Add intelligent preprocessing

### Next Steps:

1. **Don't replace edgar.documents** - It's architecturally sound
2. **Enhance it** - Add llm_extraction intelligence
3. **Unify** - Single API with both capabilities
4. **Deprecate** - Phase out llm_extraction table code

**Estimated Effort:** 3-5 days for full migration with tests

Would you like me to start implementing the migration?

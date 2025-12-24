# Metadata Usage in Table Conversion

## What You Observed

You noticed tables in markdown files have generic titles like:
- `#### Table 1: Table`
- `#### Table 2: Table`
- `#### Table: Year Ended December 31`

Let me show you **exactly** where these come from and what metadata is actually used.

---

## Metadata Actually Used in Conversion

### ✅ Metadata Used:

| Metadata | Used Where | Purpose |
|----------|------------|---------|
| **`caption`** | `to_markdown_llm()` | Passed as `section_title` to `process_content()` |
| **`derived_title`** | `html_to_json()` | Extracted from first row if it spans all columns |
| **Cell structure** | Throughout | Colspan, rowspan for table matrix |
| **Headers** | `list_of_dicts_to_table()` | Multi-row header merging |
| **Row flags** | `html_to_json()` | Detect header vs data rows |

### ❌ Metadata NOT Used:

- `table_type` - Not used in conversion logic
- `summary` - Not used at all
- `is_financial_table` - Not used in conversion
- `row_count`, `col_count` - Not used (only for metadata queries)
- `has_row_headers` - Not used in markdown generation
- `numeric_columns` - Not used in markdown generation

---

## Title Generation Logic (Where "Table 1" Comes From)

### Flow:

```python
TableNode.to_markdown_llm()
    ↓
    html = self.html()
    ↓
    process_content(html, section_title=self.caption or "Table")
        ↓
        html_to_json(table_element)
            ↓
            Extracts derived_title from first row (if spans all columns)
            ↓
            Returns (text_blocks, records, derived_title)
        ↓
        Generates title:
            If derived_title exists:
                #### Table: {derived_title}
            Else:
                #### Table {counter}: {section_title}
```

### Source Code (edgar/llm_helpers.py:808-811):

```python
header_str = (
    f"#### Table: {derived_title}"
    if derived_title
    else f"#### Table {table_counter}: {section_title or 'Data'}"
)
```

---

## Why You See Generic Titles

### Case 1: "Table 1: Table"
**Reason:**
- `caption` = `None` (not set)
- Defaults to `"Table"` in line 1251: `section_title=self.caption or "Table"`
- No `derived_title` extracted from first row
- Results in: `f"#### Table {counter}: Table"`

**Example:**
```python
table = TableNode()  # No caption set
table.to_markdown_llm()
# Output: #### Table 1: Table
```

### Case 2: "Table: Year Ended December 31"
**Reason:**
- First row of table spans all columns with text "Year Ended December 31"
- `html_to_json()` detects this and extracts it as `derived_title`
- Results in: `f"#### Table: {derived_title}"`

**Example HTML:**
```html
<table>
  <tr><th colspan="5">Year Ended December 31</th></tr>
  <tr><th></th><th>2024</th><th>2023</th><th>2022</th></tr>
  ...
</table>
```

**Extraction Logic (edgar/llm_helpers.py:376-385):**
```python
# Extract derived title (first row with single unique value spanning all columns)
derived_title = None
if len(matrix) > 1:
    first_row = matrix[0]
    unique_vals = set(v for v in first_row if v.strip())
    if len(unique_vals) == 1:
        title_candidate = list(unique_vals)[0]
        if 3 < len(title_candidate) < 150:  # Must be 3-150 chars
            derived_title = title_candidate
            matrix.pop(0)  # Remove title row from table
            row_flags.pop(0)
```

### Case 3: "Table 2: Data"
**Reason:**
- No caption
- No derived_title
- `section_title` defaults to `"Data"`
- Results in: `f"#### Table 2: Data"`

---

## Complete Metadata Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ TableNode                                                    │
│                                                              │
│ ✓ caption: Optional[str]         ← USED as section_title   │
│ ✗ summary: Optional[str]         ← NOT USED                │
│ ✗ table_type: TableType          ← NOT USED                │
│ ✓ headers: List[List[Cell]]      ← USED for header merging │
│ ✓ rows: List[Row]                ← USED for data           │
│ ✓ footer: List[Row]              ← USED if present         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ to_markdown_llm()                                           │
│                                                              │
│ 1. Convert to HTML: html = self.html()                     │
│ 2. Pass to process_content():                              │
│    process_content(html, section_title=self.caption or "Table") │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ process_content(html, section_title)                        │
│                                                              │
│ 1. Parse HTML with BeautifulSoup                           │
│ 2. For each <table>:                                        │
│    - Call html_to_json(table)                              │
│    - Returns: (text_blocks, records, derived_title)        │
│ 3. Generate title:                                          │
│    if derived_title:                                        │
│        title = f"#### Table: {derived_title}"              │
│    else:                                                    │
│        title = f"#### Table {counter}: {section_title}"    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ html_to_json(table_soup)                                    │
│                                                              │
│ ✓ Cell.colspan, Cell.rowspan     ← USED for matrix build  │
│ ✓ Cell.is_header (th vs td)      ← USED for row detection │
│ ✓ First row single value         ← USED for derived_title │
│ ✗ Cell.align                      ← NOT USED               │
│ ✗ Cell.is_numeric                 ← NOT USED               │
│                                                              │
│ Extracts derived_title if:                                  │
│ - First row has single unique value                        │
│ - Value length is 3-150 characters                         │
│ - Spans all columns                                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ list_of_dicts_to_table(records)                             │
│                                                              │
│ ✓ Header rows (empty label)      ← USED for multi-row merge │
│ ✓ Column signatures               ← USED for deduplication │
│ ✗ Numeric detection                ← NOT USED in headers   │
│                                                              │
│ Creates markdown table with merged headers                  │
└─────────────────────────────────────────────────────────────┘
                           ↓
                    Final Markdown
```

---

## Why Most Tables Show "Table 1", "Table 2", etc.

**Root Cause:** `TableNode.caption` is rarely set!

### When caption is set:
```python
table = TableNode(caption="Consolidated Balance Sheet")
md = table.to_markdown_llm()
# Output: #### Table 1: Consolidated Balance Sheet
```

### When caption is NOT set (99% of cases):
```python
table = TableNode()  # caption = None
md = table.to_markdown_llm()
# Output: #### Table 1: Table  (defaults to "Table")
```

### When first row has spanning title:
```python
# HTML:
# <tr><th colspan="5">Quarterly Revenue by Region</th></tr>
# <tr><th>Region</th><th>Q1</th><th>Q2</th><th>Q3</th><th>Q4</th></tr>

table = TableNode()  # Parse from HTML
md = table.to_markdown_llm()
# Output: #### Table: Quarterly Revenue by Region
#         (derived_title extracted and first row removed)
```

---

## What Metadata SHOULD Be Used But Isn't

### Currently Unused but Valuable:

1. **`table_type`** - Could customize formatting
   ```python
   if table.table_type == TableType.FINANCIAL:
       # Apply financial table formatting
   ```

2. **`summary`** - Could be included in output
   ```python
   if table.summary:
       output.append(f"*{table.summary}*\n")
   ```

3. **`is_financial_table`** - Could affect rendering
   ```python
   if table.is_financial_table:
       # Right-align numeric columns
   ```

---

## How to Get Better Titles

### Option 1: Set caption explicitly
```python
from edgar.documents.table_nodes import TableNode

table = TableNode(
    caption="Consolidated Income Statement",
    headers=[...],
    rows=[...]
)

md = table.to_markdown_llm()
# Output: #### Table 1: Consolidated Income Statement
```

### Option 2: Ensure first row has title
```html
<table>
  <tr><th colspan="4">Summary of Stock Compensation Expense</th></tr>
  <tr><th>Category</th><th>2024</th><th>2023</th><th>2022</th></tr>
  <tr><td>RSUs</td><td>$100M</td><td>$90M</td><td>$80M</td></tr>
</table>
```
Result: `#### Table: Summary of Stock Compensation Expense`

### Option 3: Parse from HTML with better extraction
The parser could be enhanced to look for:
- `<caption>` tags in HTML
- Table titles in surrounding text
- XBRL metadata

---

## Summary: Metadata Usage

### What IS Used:
✅ `caption` (as section_title)
✅ `derived_title` (extracted from first row)
✅ `headers` (for multi-row merging)
✅ `rows` (for data)
✅ `Cell.colspan`, `Cell.rowspan` (for matrix)
✅ `Cell.is_header` (th vs td detection)

### What is NOT Used:
❌ `table_type`
❌ `summary`
❌ `is_financial_table`
❌ `row_count`, `col_count`
❌ `has_row_headers`
❌ `numeric_columns`
❌ `Cell.align`
❌ `Cell.is_numeric` (in title/header logic)
❌ `Row.is_total_row`
❌ `Row.is_numeric_row`

### Why You See Generic Titles:
1. **`caption` is rarely set** → defaults to "Table"
2. **First row often doesn't span all columns** → no `derived_title`
3. **Result:** `"Table 1: Table"`, `"Table 2: Table"`, etc.

### How to Improve:
1. Set `caption` when creating TableNode
2. Ensure first table row has spanning title (if appropriate)
3. Enhance parser to extract captions from `<caption>` tags
4. Use surrounding context to infer table purpose

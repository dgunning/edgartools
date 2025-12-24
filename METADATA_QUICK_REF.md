# Quick Reference: What Metadata Is Actually Used

## TL;DR

**Only 2 metadata fields affect table titles:**
1. **`caption`** - If set, used as section_title
2. **`derived_title`** - If first row spans all columns, extracted as title

Everything else (`table_type`, `summary`, `is_financial_table`, etc.) is **NOT used** in markdown conversion!

---

## Why You See Generic Titles

### "Table 1: Table"
- `caption` = None (default)
- No spanning first row
- Defaults to: `f"Table {counter}: Table"`

### "Table: Year Ended December 31"
- `caption` = None
- First row has "Year Ended December 31" spanning all columns
- Extracted as `derived_title`
- Becomes: `f"Table: {derived_title}"`

---

## Metadata Usage Chart

| Metadata Field | Used? | Where Used | Purpose |
|----------------|-------|------------|---------|
| **caption** | ✅ YES | `to_markdown_llm()` | Passed as `section_title` |
| **derived_title** | ✅ YES | `html_to_json()` | Extracted from spanning first row |
| **headers** | ✅ YES | `list_of_dicts_to_table()` | Multi-row header merging |
| **rows** | ✅ YES | Throughout | Table data |
| **footer** | ✅ YES | `process_content()` | Footer rows |
| **Cell.colspan** | ✅ YES | `build_row_values()` | Matrix building |
| **Cell.rowspan** | ✅ YES | `build_row_values()` | Matrix building |
| **Cell.is_header** | ✅ YES | `html_to_json()` | Detect header rows |
| | | | |
| **table_type** | ❌ NO | - | Not used |
| **summary** | ❌ NO | - | Not used |
| **is_financial_table** | ❌ NO | - | Not used |
| **row_count** | ❌ NO | - | Metadata queries only |
| **col_count** | ❌ NO | - | Metadata queries only |
| **has_row_headers** | ❌ NO | - | Not used |
| **numeric_columns** | ❌ NO | - | Not used |
| **Cell.align** | ❌ NO | - | Not used |
| **Cell.is_numeric** | ❌ NO | - | Not used in titles |
| **Row.is_total_row** | ❌ NO | - | Not used |
| **Row.is_numeric_row** | ❌ NO | - | Not used |

---

## Title Generation Code

**Source:** `edgar/llm_helpers.py:808-811`

```python
header_str = (
    f"#### Table: {derived_title}"
    if derived_title
    else f"#### Table {table_counter}: {section_title or 'Data'}"
)
```

**Where `section_title` comes from:**

`edgar/documents/table_nodes.py:1251`
```python
markdown = process_content(
    html,
    section_title=self.caption or "Table"  # <-- Here!
)
```

---

## Derived Title Extraction

**Source:** `edgar/llm_helpers.py:376-385`

```python
# Extract derived title (first row with single unique value spanning all columns)
derived_title = None
if len(matrix) > 1:
    first_row = matrix[0]
    unique_vals = set(v for v in first_row if v.strip())
    if len(unique_vals) == 1:
        title_candidate = list(unique_vals)[0]
        if 3 < len(title_candidate) < 150:
            derived_title = title_candidate
            matrix.pop(0)  # Remove title row
            row_flags.pop(0)
```

**Requirements for derived_title:**
1. First row must have single unique value
2. Value must be 3-150 characters
3. Row is then removed from table

---

## Examples

### Example 1: No Caption, No Derived Title
```python
table = TableNode(
    headers=[[Cell(""), Cell("2024"), Cell("2023")]],
    rows=[Row([Cell("Revenue"), Cell("$100"), Cell("$90")])]
)
md = table.to_markdown_llm()
# Output: #### Table 1: Table
```

### Example 2: With Caption
```python
table = TableNode(
    caption="Income Statement",
    headers=[[Cell(""), Cell("2024"), Cell("2023")]],
    rows=[Row([Cell("Revenue"), Cell("$100"), Cell("$90")])]
)
md = table.to_markdown_llm()
# Output: #### Table 1: Income Statement
```

### Example 3: Spanning First Row
```html
<table>
  <tr><th colspan="3">Year Ended December 31</th></tr>
  <tr><th></th><th>2024</th><th>2023</th></tr>
  <tr><td>Revenue</td><td>$100</td><td>$90</td></tr>
</table>
```
```python
# After parsing:
md = table.to_markdown_llm()
# Output: #### Table: Year Ended December 31
# (First row removed from table)
```

---

## How to Get Better Titles

### Option 1: Set Caption
```python
table.caption = "Consolidated Balance Sheet"
```

### Option 2: Use Spanning First Row
```html
<table>
  <caption>Balance Sheet</caption>  <!-- NOT currently used -->
  <tr><th colspan="5">Assets and Liabilities</th></tr>  <!-- USED -->
  <tr><th>Item</th><th>2024</th>...</tr>
</table>
```

### Option 3: Enhance Parser (Future)
- Extract from `<caption>` tags
- Infer from surrounding context
- Use XBRL metadata

---

## Summary

**Used (7 fields):**
- caption
- derived_title
- headers
- rows
- footer
- Cell.colspan, Cell.rowspan, Cell.is_header

**Not Used (12 fields):**
- table_type
- summary
- is_financial_table
- row_count, col_count
- has_row_headers
- numeric_columns
- Cell.align, Cell.is_numeric
- Row.is_total_row, Row.is_numeric_row

**Why generic titles:**
- `caption` rarely set (None default)
- First row often doesn't span → no `derived_title`
- Result: "Table 1: Table"

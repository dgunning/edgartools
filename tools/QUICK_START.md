# Quick Start Guide: New LLM Extraction Features

## Overview

Two new parameters added to `extract_markdown()`:

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `show_dimension` | bool | `True` | Control visibility of XBRL dimension columns |
| `show_filtered_data` | bool | `False` | Show metadata about filtered/omitted data |

---

## Basic Usage

```python
from edgar import Company
from edgar.llm import extract_markdown

# Get a filing
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest(1)

# Default extraction (all features visible)
markdown = extract_markdown(filing, item="7")
```

---

## Feature 1: Hide Dimension Columns

**Problem:** XBRL statements include metadata columns (level, abstract, dimension) that add noise for LLM analysis.

**Solution:** Use `show_dimension=False`

### Before (show_dimension=True - Default)
```python
markdown = extract_markdown(filing, statement="income", show_dimension=True)
```

**Output includes:**
```markdown
| label | level | abstract | dimension | 2024 | 2023 | 2022 |
| --- | --- | --- | --- | --- | --- | --- |
| Revenue | 0 | False | None | $100M | $90M | $80M |
| Operating Expenses | 1 | True | None | - | - | - |
| Research & Development | 2 | False | None | $20M | $18M | $16M |
```

### After (show_dimension=False)
```python
markdown = extract_markdown(filing, statement="income", show_dimension=False)
```

**Output includes:**
```markdown
| label | 2024 | 2023 | 2022 |
| --- | --- | --- | --- |
| Revenue | $100M | $90M | $80M |
| Operating Expenses | - | - | - |
| Research & Development | $20M | $18M | $16M |
```

**When to use:**
- ✅ Feeding to LLMs (reduces tokens by ~30%)
- ✅ Financial analysis (focus on numbers, not structure)
- ✅ Data extraction pipelines

**When NOT to use:**
- ❌ XBRL taxonomy analysis
- ❌ Understanding statement hierarchy
- ❌ Debugging XBRL structure issues

---

## Feature 2: Show Filtered Data

**Problem:** You can't see what data was filtered/omitted during extraction.

**Solution:** Use `show_filtered_data=True`

### Without Metadata (show_filtered_data=False - Default)
```python
markdown = extract_markdown(filing, notes=True, show_filtered_data=False)
```

**Output:** Just the extracted notes (no metadata about what was filtered)

### With Metadata (show_filtered_data=True)
```python
markdown = extract_markdown(filing, notes=True, show_filtered_data=True)
```

**Output includes metadata section at end:**
```markdown
[... extracted content ...]

---
## FILTERED DATA METADATA

Total items filtered: 45
- XBRL metadata tables: 42
- Duplicate tables: 3
- Filtered text blocks: 0

### Details:
1. Type: xbrl_metadata_table
   Preview: Name: us-gaap_AccountingPoliciesAbstract Namespace Prefix...
2. Type: duplicate_table
   Title: Cash Flow Summary
3. Type: xbrl_metadata_table
   Preview: Name: us-gaap_RevenueFromContractWithCustomerTextBlock...
```

**When to use:**
- ✅ Data quality audits
- ✅ Debugging missing data
- ✅ Understanding extraction behavior
- ✅ Validating filtered items are correct

**When NOT to use:**
- ❌ Production pipelines (adds noise)
- ❌ LLM prompts (unnecessary context)

---

## Combining Both Features

```python
# Clean output + transparency
markdown = extract_markdown(
    filing,
    item=["1", "7"],          # Extract multiple items
    statement="income",        # Extract income statement
    notes=True,                # Extract notes
    show_dimension=False,      # Hide XBRL metadata columns
    show_filtered_data=True    # Show what was filtered
)

# Result:
# - Clean financial statements (no dimension clutter)
# - All requested content
# - Metadata section showing what was omitted
```

---

## Real-World Examples

### Example 1: LLM Analysis
```python
# Optimize for LLM token usage
markdown = extract_markdown(
    filing,
    statement=["income", "balance", "cash"],
    show_dimension=False  # Reduce tokens
)

# Feed to LLM
response = llm.analyze(markdown)
```

### Example 2: Data Quality Check
```python
# See what's being filtered
markdown = extract_markdown(
    filing,
    notes=True,
    show_filtered_data=True  # Audit filtered items
)

# Check the metadata section at the end
# Verify filtered items are correct
```

### Example 3: Production Pipeline
```python
# Efficient extraction with audit trail
markdown = extract_markdown(
    filing,
    item=["1", "1A", "7", "7A"],
    statement=["income", "balance", "cash"],
    notes=True,
    show_dimension=False,      # Efficient
    show_filtered_data=True    # Transparent
)

# Save both content and metadata
save_to_database(markdown)
```

### Example 4: Full XBRL Analysis
```python
# Keep everything for detailed analysis
markdown = extract_markdown(
    filing,
    statement=["income", "balance"],
    show_dimension=True,       # Keep XBRL structure
    show_filtered_data=False   # No metadata needed
)

# Analyze XBRL taxonomy
analyze_xbrl_structure(markdown)
```

---

## Migration Guide

### Old Code (Still Works)
```python
# Your existing code works unchanged
markdown = extract_markdown(filing, item="7")
# Uses defaults: show_dimension=True, show_filtered_data=False
```

### Optimized for LLMs
```python
# Add one parameter for cleaner output
markdown = extract_markdown(
    filing,
    item="7",
    show_dimension=False  # ← Add this
)
```

### With Transparency
```python
# Add parameter to see filtered data
markdown = extract_markdown(
    filing,
    notes=True,
    show_filtered_data=True  # ← Add this
)
```

---

## Parameter Reference

### show_dimension (bool, default=True)

Controls visibility of XBRL metadata columns in financial statements.

**Columns affected:**
- `level` - Hierarchy level in statement
- `abstract` - Whether row is a subtotal/section header
- `dimension` - XBRL dimension information

**Impact:**
- `True`: Show all columns (verbose, complete)
- `False`: Hide metadata columns (clean, concise)

**Applies to:**
- Financial statements (income, balance, cash flow)
- XBRL data extracted via `statement` parameter

**Does NOT apply to:**
- Items (already optimized)
- Notes (already optimized)
- Non-XBRL tables

---

### show_filtered_data (bool, default=False)

Controls whether metadata about filtered/omitted data is appended to output.

**Metadata includes:**
- Count of XBRL metadata tables filtered
- Count of duplicate tables removed
- Count of text blocks filtered
- Preview/title of each filtered item (first 10)

**Impact:**
- `False`: No metadata appended (default)
- `True`: Metadata section added at end

**Applies to:**
- All extraction types (items, statements, notes)
- All filtering operations

**Location:**
- Appended at end of markdown under "## FILTERED DATA METADATA"

---

## Tips & Best Practices

1. **For LLM prompts:** Use `show_dimension=False` to reduce tokens
2. **For debugging:** Use `show_filtered_data=True` to see what's missing
3. **For production:** Combine both for efficiency + transparency
4. **For XBRL analysis:** Keep `show_dimension=True` (default)
5. **Default is safe:** No parameters = backward compatible

---

## Performance Impact

| Parameter | Impact on Size | Impact on Speed |
|-----------|----------------|-----------------|
| `show_dimension=False` | -20% to -40% | Minimal |
| `show_filtered_data=True` | +1% to +5% | Minimal |

Both parameters have negligible impact on extraction speed.

---

## Troubleshooting

### Q: My statements are missing columns!
**A:** You might have `show_dimension=False`. This is intentional - it hides metadata columns. Use `show_dimension=True` to see all columns.

### Q: I can't see what was filtered
**A:** Use `show_filtered_data=True` to add a metadata section at the end.

### Q: The metadata section is too long
**A:** Metadata is limited to first 10 filtered items. If you need more, use the programmatic API (see Advanced Usage).

### Q: Does this work with all filing types?
**A:** Yes! Both parameters work globally for all forms (10-K, 10-Q, 8-K, etc.).

---

## Advanced Usage

For programmatic access to filtered data:

```python
from edgar.llm import extract_sections

# Get sections and filtered data separately
sections, filtered_data = extract_sections(
    filing,
    notes=True,
    track_filtered=True  # Returns tuple: (sections, metadata)
)

# Access counts
print(f"XBRL tables filtered: {filtered_data['xbrl_metadata_tables']}")
print(f"Duplicate tables: {filtered_data['duplicate_tables']}")
print(f"Text blocks: {filtered_data['filtered_text_blocks']}")

# Access details (all items, not just first 10)
for detail in filtered_data['details']:
    print(f"{detail['type']}: {detail.get('preview', detail.get('title'))}")
```

---

## Summary

**New parameters in `extract_markdown()`:**

```python
extract_markdown(
    filing,
    item=...,
    statement=...,
    notes=...,
    show_dimension=True,     # NEW: Show XBRL metadata columns
    show_filtered_data=False # NEW: Show filtered data metadata
)
```

**Quick decision matrix:**

| Use Case | show_dimension | show_filtered_data |
|----------|----------------|-------------------|
| LLM analysis | `False` | `False` |
| Data audit | `True` | `True` |
| Production | `False` | `True` |
| XBRL analysis | `True` | `False` |
| Default/Safe | `True` | `False` |

---

For more examples, see `tools/usage_examples.py`

# How to Extract Different Sections from Filings

## Quick Reference

```python
from edgar import Company
from edgar.llm import extract_markdown

# Get a filing
snap = Company("SNAP")
filing = snap.get_filings(form='10-K').latest()
```

## 1. Extract Specific Items

### Single Item
```python
# Extract Item 8 (Financial Statements)
markdown = extract_markdown(filing, item="8")

# Extract Item 7 (MD&A)
markdown = extract_markdown(filing, item="7")

# Extract Item 1 (Business)
markdown = extract_markdown(filing, item="1")

# Extract Item 1A (Risk Factors)
markdown = extract_markdown(filing, item="1A")
```

### Multiple Items
```python
# Extract multiple items at once
markdown = extract_markdown(filing, item=["1", "1A", "7", "8"])
```

### All Available Items (10-K)
- **Item 1** - Business
- **Item 1A** - Risk Factors
- **Item 1B** - Unresolved Staff Comments
- **Item 1C** - Cybersecurity
- **Item 2** - Properties
- **Item 3** - Legal Proceedings
- **Item 4** - Mine Safety Disclosures
- **Item 5** - Market for Registrant's Common Equity
- **Item 6** - Reserved
- **Item 7** - Management's Discussion and Analysis
- **Item 7A** - Quantitative and Qualitative Disclosures About Market Risk
- **Item 8** - Financial Statements and Supplementary Data
- **Item 9** - Changes in and Disagreements with Accountants
- **Item 9A** - Controls and Procedures
- **Item 9B** - Other Information
- **Item 9C** - Disclosure Regarding Foreign Jurisdictions
- **Item 10** - Directors, Executive Officers and Corporate Governance
- **Item 11** - Executive Compensation
- **Item 12** - Security Ownership
- **Item 13** - Certain Relationships and Related Transactions
- **Item 14** - Principal Accounting Fees and Services
- **Item 15** - Exhibits, Financial Statement Schedules

---

## 2. Extract Financial Statements

```python
# Extract Income Statement
markdown = extract_markdown(filing, statement="IncomeStatement")

# Extract Balance Sheet
markdown = extract_markdown(filing, statement="BalanceSheet")

# Extract Cash Flow Statement
markdown = extract_markdown(filing, statement="CashFlowStatement")

# Extract Statement of Stockholders' Equity
markdown = extract_markdown(filing, statement="StockholdersEquity")

# Extract multiple statements
markdown = extract_markdown(
    filing,
    statement=["IncomeStatement", "BalanceSheet", "CashFlowStatement"]
)
```

---

## 3. Extract Notes (THIS IS WHAT YOU ASKED ABOUT!)

### Include All Notes
```python
# Extract notes along with statements
markdown = extract_markdown(
    filing,
    statement="IncomeStatement",
    notes=True  # <-- This extracts ALL financial statement notes
)

# Or extract ONLY notes (no items or statements)
markdown = extract_markdown(filing, notes=True)
```

### What Notes Include
When you set `notes=True`, it extracts:
- Note 1 - Summary of Significant Accounting Policies
- Note 2 - Revenue Recognition
- Note 3 - Fair Value Measurements
- Note 4 - Property and Equipment
- Note 5 - Goodwill and Intangible Assets
- Note 6 - Debt
- Note 7 - Stockholders' Equity
- Note 8 - Stock-Based Compensation
- ... and all other notes in the filing

---

## 4. Extract by Category (ADVANCED)

If you need more control, you can use the filing's reports directly:

```python
# Get the filing object
tenk = filing.obj()

# Extract notes category
notes_reports = tenk.reports.get_by_category("Notes")
for note in notes_reports:
    print(f"Note: {note.short_name}")
    html_content = note.content
    # Process as needed

# Extract other categories
statements = tenk.reports.get_by_category("Statements")
for stmt in statements:
    print(f"Statement: {stmt.short_name}")

# Extract cover page
cover = tenk.reports.get_by_category("Cover")

# Extract tables
tables = tenk.reports.get_by_category("Tables")

# Extract all categories
all_reports = tenk.reports.all()
for report in all_reports:
    print(f"{report.category}: {report.short_name}")
```

---

## 5. Combine Everything

```python
# Extract everything: items, statements, and notes
markdown = extract_markdown(
    filing,
    item=["1", "7", "8"],  # Business, MD&A, Financial Statements
    statement=["IncomeStatement", "BalanceSheet"],  # Specific statements
    notes=True,  # All notes
    include_header=True,  # Include filing metadata
    show_dimension=True,  # Show dimension columns in statements
    show_filtered_data=False  # Don't show what was filtered
)
```

---

## 6. Advanced Options

### Control What's Included

```python
markdown = extract_markdown(
    filing,
    item="7",
    statement="IncomeStatement",
    notes=True,

    # Options:
    include_header=True,        # Add filing metadata at top (default: True)
    optimize_for_llm=True,      # Apply LLM optimizations (default: True)
    show_dimension=True,        # Include dimension columns (default: True)
    show_filtered_data=False    # Show metadata about filtered data (default: False)
)
```

### See What Was Filtered Out

```python
# Show metadata about filtered/omitted data
markdown = extract_markdown(
    filing,
    item="8",
    show_filtered_data=True  # <-- Appends section showing what was filtered
)

# This will add a section like:
# ## FILTERED DATA METADATA
# Total items filtered: 15
# - XBRL metadata tables: 8
# - Duplicate tables: 5
# - Filtered text blocks: 2
```

---

## 7. Using extract_sections (Lower Level)

If you need structured objects instead of markdown:

```python
from edgar.llm import extract_sections

# Get sections as objects
sections, filtered_data = extract_sections(
    filing,
    item=["1", "7"],
    statement="IncomeStatement",
    notes=True,
    track_filtered=True  # Get filtered data metadata
)

# Process each section
for section in sections:
    print(f"Title: {section.title}")
    print(f"Is XBRL: {section.is_xbrl}")
    print(f"Source: {section.source}")
    print(f"Markdown length: {len(section.markdown)}")
    print(section.markdown[:200])  # First 200 chars
```

---

## 8. Examples for Common Use Cases

### Extract Complete 10-K for Analysis
```python
markdown = extract_markdown(
    filing,
    item=["1", "1A", "7", "8"],  # Key sections
    statement=["IncomeStatement", "BalanceSheet", "CashFlowStatement"],
    notes=True,  # All notes
    show_dimension=True
)

# Save to file
with open("snap_10k.md", "w", encoding="utf-8") as f:
    f.write(markdown)
```

### Extract Only Financial Data
```python
markdown = extract_markdown(
    filing,
    statement=["IncomeStatement", "BalanceSheet", "CashFlowStatement"],
    notes=True  # Include all accounting notes
)
```

### Extract Risk Factors and MD&A
```python
markdown = extract_markdown(
    filing,
    item=["1A", "7"]  # Risk Factors + MD&A
)
```

### Extract Everything
```python
markdown = extract_markdown(
    filing,
    item=["1", "1A", "1B", "2", "3", "7", "7A", "8", "9", "9A"],
    statement=["IncomeStatement", "BalanceSheet", "CashFlowStatement", "StockholdersEquity"],
    notes=True,
    show_dimension=True,
    show_filtered_data=True
)
```

---

## 9. What You Get

All extractions now include our improvements:
- ✅ **Better table titles** (from caption tags, spanning rows, content inference)
- ✅ **Right-aligned numeric columns** (professional formatting)
- ✅ **Bolded total rows** (visual clarity)
- ✅ **LLM-optimized** (deduplicated, cleaned, token-efficient)

---

## Summary

**Your Question:** How to extract notes or other categories?

**Answer:**
```python
# Extract notes:
markdown = extract_markdown(filing, notes=True)

# Extract notes + Item 8:
markdown = extract_markdown(filing, item="8", notes=True)

# Extract specific category (advanced):
tenk = filing.obj()
notes = tenk.reports.get_by_category("Notes")
statements = tenk.reports.get_by_category("Statements")
```

The `notes=True` parameter is what you need!

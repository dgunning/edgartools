# HTML Parser Quality Improvement Strategy

## Overview

Simple, iterative testing strategy for the HTML parser rewrite. The goal is rapid feedback loops where we compare OLD vs NEW parser output, identify visual/functional issues, fix them, and repeat until satisfied.

## Test Corpus

### 10 Representative Documents

Selected to cover different filing types, companies, and edge cases:

| # | Company | Filing Type | File Path | Rationale |
|---|---------|-------------|-----------|-----------|
| 1 | Apple | 10-K | `data/html/Apple.10-K.html` | Large complex filing, existing test file |
| 2 | Oracle | 10-K | `data/html/Oracle.10-K.html` | Complex financials, existing test file |
| 3 | Nvidia | 10-K | `data/html/Nvidia.10-K.html` | Tech company, existing test file |
| 4 | Microsoft | 10-K | `data/html/Microsoft.10-K.html` | Popular company, complex tables |
| 5 | Tesla | 10-K | `data/html/Tesla.10-K.html` | Manufacturing sector, different formatting |
| 6 | [TBD] | 10-Q | TBD | Quarterly report format |
| 7 | [TBD] | 10-Q | TBD | Another quarterly for variety |
| 8 | [TBD] | 8-K | `data/html/BuckleInc.8-K.html` | Event-driven filing |
| 9 | [TBD] | Proxy (DEF 14A) | TBD | Proxy statement with compensation tables |
| 10 | [TBD] | Edge case | TBD | Unusual formatting or very large file |

**Note**: Fill in TBD entries as we identify good test candidates.

## The 4-Step Loop

### Step 1: Run Comparison

Use existing test scripts to compare OLD vs NEW parsers:

```bash
# Full comparison with metrics
python tests/manual/check_parser_comparison.py

# Table-focused comparison with rendering
python tests/manual/check_tables.py

# Or run on specific file
python tests/manual/check_html_rewrite.py
```

**Outputs to review**:
- Console output with side-by-side Rich panels
- Metrics (parse time, table count, section detection)
- Rendered tables (old vs new)

### Step 2: Human Review

**Visual Inspection Process**:
1. Look at console output directly (Rich rendering)
2. For detailed text comparison, optionally dump to files:
   - OLD parser: `doc.text()` → `output/old_apple.txt`
   - NEW parser: `doc.text()` → `output/new_apple.txt`
   - Use `diff` or visual diff tool
3. Take screenshots for complex table issues
4. Focus on:
   - Table alignment and formatting
   - Currency symbol placement (should be merged: `$1,234` not `$ | 1,234`)
   - Column count (fewer is better after removing spacing columns)
   - Section detection accuracy
   - Text readability for LLM context

**Quality Criteria** (from goals.md):
- Semantic meaning preserved
- Tables render correctly when printed
- Better than old parser in speed, accuracy, features
- **You are the final judge**: "Does this look right?"

### Step 3: Document Bugs

Record issues in the tracker below as you find them:

| Bug # | Status | Priority | Description | File/Location | Notes |
|-------|--------|----------|-------------|---------------|-------|
| Example | Fixed | High | Currency symbols not merging in balance sheet | Apple 10-K, Table 5 | Issue in CurrencyColumnMerger |
| | | | | | |
| | | | | | |
| | | | | | |

**Status values**: Open, In Progress, Fixed, Won't Fix, Deferred
**Priority values**: Critical, High, Medium, Low

**Bug Description Template**:
- What's wrong: Clear description of the issue
- Where: Which file/table/section
- Expected: What it should look like
- Actual: What it currently looks like
- Impact: How it affects usability/readability

### Step 4: Fix & Repeat

1. Pick highest priority bug
2. Fix the code
3. Re-run comparison on affected file(s)
4. Verify fix doesn't break other files
5. Mark bug as Fixed
6. Repeat until exit criteria met

**Quick verification**:
```bash
# Re-run just the problematic file
python -c "
from edgar.documents import parse_html
from pathlib import Path
html = Path('data/html/Apple.10-K.html').read_text()
doc = parse_html(html)
# Quick inspection
print(f'Tables: {len(doc.tables)}')
print(doc.tables[5].render(width=200))  # Check specific table
"
```

## Exit Criteria

We're done when:
1. ✅ All 10 test documents parse successfully
2. ✅ Visual output looks correct (maintainer approval)
3. ✅ Tables render cleanly with proper alignment
4. ✅ No critical or high priority bugs remain
5. ✅ Performance is equal or better than old parser
6. ✅ Text extraction is complete and clean for AI context

**Final approval**: Maintainer says "This is good enough to ship."

## Testing Infrastructure

### Primary Tool: compare_parsers.py

Simple command-line tool for the quality improvement loop:

```bash
# Quick overview comparison (using shortcuts!)
python tests/manual/compare_parsers.py aapl

# See all tables in a document
python tests/manual/compare_parsers.py aapl --tables

# Compare specific table (OLD vs NEW side-by-side)
python tests/manual/compare_parsers.py aapl --table 5

# Compare text extraction
python tests/manual/compare_parsers.py msft --text

# See section detection
python tests/manual/compare_parsers.py orcl --sections

# Test with 10-Q filings
python tests/manual/compare_parsers.py 'aapl 10-q'

# Run all test files at once
python tests/manual/compare_parsers.py --all
```

**Shortcuts available**:
- Companies: `aapl`, `msft`, `tsla`, `nvda`, `orcl`
- Filing types: `10-k` (default), `10-q`, `8-k`
- Or use full file paths

**Features**:
- Clean command-line interface
- Side-by-side OLD vs NEW comparison
- Rich console output with colors and tables
- Performance metrics
- Individual table inspection

### Other Available Scripts

Additional tools for specific testing:

- `tests/manual/check_parser_comparison.py` - Full comparison with metrics
- `tests/manual/check_tables.py` - Table-specific comparison with rendering
- `tests/manual/check_html_rewrite.py` - General HTML parsing checks
- `tests/manual/check_html_parser_real_files.py` - Real filing tests

## Quick Reference

For day-to-day testing commands and usage examples, see [TESTING.md](TESTING.md).

## Notes

- **Keep it simple**: This is about rapid iteration, not comprehensive automation
- **Visual inspection is key**: Automated metrics don't catch layout/formatting issues
- **Use screenshots**: When describing bugs, screenshots speak louder than words
- **Iterative approach**: Don't try to fix everything at once, prioritize
- **Trust your judgment**: If it looks wrong, it probably is wrong

## Bug Tracker

### Active Issues

(Add bugs here as they're discovered)

### Fixed Issues

(Move completed bugs here for history)

### Deferred Issues

(Issues that aren't blocking release but could be improved later)

---

**Status**: Initial draft
**Last Updated**: 2025-10-07
**Maintainer**: Dwight Gunning

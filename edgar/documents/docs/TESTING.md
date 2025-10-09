# HTML Parser Testing Quick Start

Quick reference for testing the HTML parser rewrite during quality improvement.

## Quick Start

```bash
# Use shortcuts (easy!)
python tests/manual/compare_parsers.py aapl              # Apple 10-K
python tests/manual/compare_parsers.py nvda --tables     # Nvidia tables
python tests/manual/compare_parsers.py 'aapl 10-q'       # Apple 10-Q
python tests/manual/compare_parsers.py orcl --table 5    # Oracle table #5

# Or use full paths
python tests/manual/compare_parsers.py data/html/Apple.10-K.html

# Run all test files
python tests/manual/compare_parsers.py --all
```

**Available shortcuts:**
- **Companies**: `aapl`, `msft`, `tsla`, `nvda`, `orcl` (or full names like `apple`)
- **Filing types**: `10-k` (default), `10-q`, `8-k`
- **Combine**: `'aapl 10-q'`, `'orcl 8-k'`

## Common Use Cases

### 1. First Look at a Filing

```bash
# Get overview: speed, table count, sections
python tests/manual/compare_parsers.py orcl
```

**Shows**:
- Parse time comparison (OLD vs NEW)
- Tables found
- Text length
- Sections detected
- New features (headings, XBRL)

### 2. Check Table Rendering

```bash
# List all tables with dimensions (shows first 20 tables)
python tests/manual/compare_parsers.py aapl --tables

# Compare specific table side-by-side (FULL table, no truncation)
python tests/manual/compare_parsers.py aapl --table 7

# Compare a range of tables
python tests/manual/compare_parsers.py aapl --range 5:10
```

**Look for**:
- Currency symbols merged: `$1,234` not `$ | 1,234`
- Proper column alignment
- Correct row/column counts
- Clean rendering without extra spacing columns

**Note**: `--table N` shows the **complete table** with all rows - no truncation!

### 3. Verify Text Extraction

```bash
# See first 50 lines side-by-side (default limit)
python tests/manual/compare_parsers.py msft --text

# Show more lines (configurable)
python tests/manual/compare_parsers.py msft --text --lines 100

# Show first 200 lines
python tests/manual/compare_parsers.py msft --text --lines 200
```

**Check**:
- Semantic meaning preserved
- No missing content
- Clean formatting for LLM consumption

**Note**: Text mode shows first N lines only (default: 50). Use `--lines N` to adjust.

### 4. Check Section Detection

```bash
python tests/manual/compare_parsers.py aapl --sections
```

**Verify**:
- Standard sections identified (10-K/10-Q)
- Section boundaries correct
- Text length reasonable per section

### 5. Run Full Test Suite

```bash
# Test all files in corpus
python tests/manual/compare_parsers.py --all
```

**Results**:
- Summary table across all files
- Performance comparison
- Table detection comparison

## Test Files

Available in `data/html/`:

- `Apple.10-K.html` - 1.8MB, complex financials
- `Oracle.10-K.html` - Large filing
- `Nvidia.10-K.html` - Tech company
- `Apple.10-Q.html` - Quarterly format
- More files as needed...

## Command Reference

```
python tests/manual/compare_parsers.py [FILE] [OPTIONS]

Options:
  --all           Run on all test files
  --tables        Show tables summary (first 20 tables)
  --table N       Show specific table N side-by-side (FULL table)
  --range START:END  Show range of tables (e.g., 5:10)
  --text          Show text comparison (first 50 lines by default)
  --sections      Show sections comparison
  --lines N       Number of text lines to show (default: 50, only for --text)
  --help          Show full help
```

### Output Limits Summary

| Mode          | Limit      | Configurable      | Notes                           |
|---------------|------------|-------------------|---------------------------------|
| `--table N`   | None       | N/A               | Shows **complete table**        |
| `--range N:M` | None       | N/A               | Shows **complete tables** in range |
| `--tables`    | 20 tables  | No                | Lists first 20 tables only      |
| `--text`      | 50 lines   | Yes (`--lines N`) | Preview only                    |
| `--sections`  | None       | N/A               | Shows all sections              |

## Output Interpretation

### Overview Table

```
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Metric        ┃ Old Parser ┃ New Parser ┃ Notes      ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Parse Time    │ 454ms      │ 334ms      │ 1.4x faster│
│ Tables Found  │ 63         │ 63         │ +0         │
│ Text Length   │ 0          │ 159,388    │ NEW!       │
└───────────────┴────────────┴────────────┴────────────┘
```

**Good signs**:
- ✅ New parser faster or similar speed
- ✅ Same or more tables found
- ✅ Text extracted (old parser shows 0)
- ✅ Sections detected

**Red flags**:
- ❌ Significantly slower
- ❌ Fewer tables (unless removing layout tables)
- ❌ Much shorter text (content missing)

### Table Comparison

```
Old Parser:
┌─────────┬──────────┬──────────┐
│ Year    │ Revenue  │ Profit   │
├─────────┼──────────┼──────────┤
│ 2023    │ $ 100M   │ $ 20M    │  <- Currency separated
└─────────┴──────────┴──────────┘

New Parser:
┌─────────┬──────────┬──────────┐
│ Year    │ Revenue  │ Profit   │
├─────────┼──────────┼──────────┤
│ 2023    │ $100M    │ $20M     │  <- Currency merged ✅
└─────────┴──────────┴──────────┘
```

**Look for**:
- Currency symbols merged with values
- No extra empty columns
- Proper alignment
- Clean numeric formatting

## Tips

1. **Start with overview** - Get the big picture first
2. **Check tables visually** - Automated metrics miss formatting issues
3. **Use specific table inspection** - Don't scroll through 60 tables manually
4. **Compare text for semantics** - Does it make sense for an LLM?
5. **Run --all periodically** - Catch regressions across files

## Troubleshooting

### Script fails with import error

```bash
# Clear cached modules
find . -type d -name __pycache__ -exec rm -rf {} +
python tests/manual/compare_parsers.py data/html/Apple.10-K.html
```

### File not found

```bash
# Check available files
ls -lh data/html/*.html

# Use full path
python tests/manual/compare_parsers.py /full/path/to/file.html
```

### Old parser shows 0 text

This is expected - old parser has different text extraction. Focus on:
- Table comparison
- Parse time
- Visual quality of output

## Next Steps

1. Run comparison on all test files
2. Document bugs in `quality-improvement-strategy.md`
3. Fix issues
4. Repeat until satisfied

See `edgar/documents/docs/quality-improvement-strategy.md` for full process.

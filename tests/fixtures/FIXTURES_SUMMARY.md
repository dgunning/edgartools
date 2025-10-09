# Test Fixtures Summary

## Overview

EdgarTools test fixtures are organized to support comprehensive testing of the HTML parser and XBRL processing across diverse companies, industries, and filing types.

## Directory Structure

```
tests/fixtures/
├── html/                          # HTML filing fixtures (NEW)
│   ├── {ticker}/                 # 16 companies
│   │   ├── 10k/                  # Annual reports
│   │   └── 10q/                  # Quarterly reports
│   ├── README.md                 # HTML fixtures documentation
│   └── download_html_fixtures.py # Download script
│
├── xbrl2/                         # XBRL test data
│   ├── {ticker}/                 # Company-specific XBRL data
│   │   ├── 10k/                  # Historical 10-K data
│   │   ├── 10q/                  # Historical 10-Q data
│   │   └── *.xml                 # XBRL taxonomy files
│   └── special_cases/            # Edge case XBRL data
│
└── download_html_fixtures.py     # Central download script
```

## HTML Fixtures (New)

**Purpose**: Comprehensive HTML parser testing across diverse filings

**Coverage**:
- **Companies**: 16 tickers across 6 industries
- **Files**: 32 HTML filings (16 × 2 forms)
- **Size**: 155.3MB total (0.8MB to 21.7MB per file)
- **Forms**: 10-K, 10-Q
- **Date**: 2024-2025 (latest filings)

**Industries**:
- Technology (5): AAPL, MSFT, NVDA, IBM, HUBS
- Finance (3): JPM, GS, GBDC
- Consumer (3): KO, PG, JNJ
- Industrial (3): TSLA, BA, UNP
- Energy (1): XOM
- Media (1): NFLX

**Size Distribution**:
- Small (<2MB): 11 files - Fast parsing tests
- Medium (2-8MB): 15 files - Standard complexity
- Large (>8MB): 6 files - Memory/performance tests

See [html/README.md](html/README.md) for detailed documentation.

## XBRL Fixtures (Existing)

**Purpose**: XBRL parsing and financial data extraction testing

**Coverage**:
- Historical XBRL data across multiple years
- Company-specific taxonomy files
- Special cases and edge conditions

**Companies**: Same tickers as HTML fixtures for consistency

## Test Usage

### Quick Corpus Validation

```python
# Use in corpus validation tests
from pathlib import Path
from edgar.documents import parse_html

fixtures_dir = Path('tests/fixtures/html')

for html_file in fixtures_dir.rglob('*.html'):
    html = html_file.read_text()
    doc = parse_html(html)
    # Validate parsing...
```

### Performance Benchmarking

```python
# Size-based performance testing
small_docs = fixtures_dir.glob('*/10k/*-10-k-*.html')  # < 2MB
medium_docs = ...  # 2-8MB
large_docs = ...   # > 8MB
```

### Industry-Specific Testing

```python
# Test finance industry filings (complex tables)
finance = ['jpm', 'gs', 'gbdc']

for ticker in finance:
    html_file = fixtures_dir / ticker / '10k' / f'{ticker}-10-k-*.html'
    # Test complex financial tables...
```

## Maintenance

### Updating HTML Fixtures

```bash
# Download latest filings for all companies
cd tests/fixtures
python download_html_fixtures.py

# The script:
# - Skips existing files (caching)
# - Downloads latest 10-K and 10-Q for each ticker
# - Organizes by company and form type
# - Reports success/failure
```

### Adding New Companies

Edit `download_html_fixtures.py`:

```python
TICKERS = [
    'AAPL', 'MSFT', ...,
    'NEWCO',  # Add new ticker
]
```

Then run:
```bash
python download_html_fixtures.py --tickers NEWCO
```

## Test Integration

These fixtures are used by:

1. **Corpus Validation** (`tests/corpus/test_corpus_validation.py`)
   - Validates parser against all fixtures
   - Checks section detection, table extraction
   - Measures success rates

2. **Performance Tests** (`tests/perf/`)
   - Benchmarks parsing speed
   - Profiles memory usage
   - Regression testing

3. **Integration Tests** (`tests/test_html_parser_integration.py`)
   - Tests with real SEC filings
   - Validates backward compatibility

4. **Edge Case Tests** (`tests/test_html_parser_edge_cases.py`)
   - Tests specific document quirks
   - Validates handling of unusual structures

## Benefits

### Comprehensive Coverage
- **16 industries** - Captures diverse formatting styles
- **32 filings** - Both annual and quarterly reports
- **Size range** - 0.8MB to 21.7MB tests scalability
- **Recency** - Latest filings ensure real-world accuracy

### Reproducible Testing
- **Fixed dataset** - Consistent results across test runs
- **Cached files** - No network dependency for most tests
- **Easy refresh** - Single command updates all fixtures

### Performance Validation
- **Small files** - Fast test suite execution
- **Large files** - Memory/streaming validation
- **Diverse sizes** - Realistic performance profiling

## Statistics

| Metric | Value |
|--------|-------|
| **Total fixtures** | 32 files |
| **Total size** | 155.3MB |
| **Companies** | 16 |
| **Industries** | 6 |
| **Form types** | 2 (10-K, 10-Q) |
| **Years** | 2024-2025 |
| **Smallest file** | 0.8MB (TSLA 10-K) |
| **Largest file** | 21.7MB (GBDC 10-Q) |
| **Avg size** | 4.9MB |

## Future Enhancements

Potential additions:
- [ ] 8-K filings (event-driven reports)
- [ ] S-1/S-4 filings (IPO/merger documents)
- [ ] Proxy statements (DEF 14A)
- [ ] Historical filings (2010-2020) for trend analysis
- [ ] International filings (if supported)

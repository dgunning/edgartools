# HTML Test Fixtures

HTML filings for testing the HTML parser across diverse companies and industries.

## Organization

```
tests/fixtures/html/
├── {ticker}/          # One directory per company
│   ├── 10k/          # 10-K annual reports
│   └── 10q/          # 10-Q quarterly reports
└── download_html_fixtures.py  # Download script
```

## Coverage

**16 companies** across multiple industries:

### Technology
- **AAPL** (Apple) - Consumer electronics
- **MSFT** (Microsoft) - Software/cloud
- **NVDA** (NVIDIA) - Semiconductors
- **IBM** (IBM) - Enterprise tech
- **HUBS** (HubSpot) - SaaS

### Finance
- **JPM** (JP Morgan) - Banking (12.3MB 10-K)
- **GS** (Goldman Sachs) - Investment banking (9.6MB 10-K)
- **GBDC** (Golub Capital) - BDC (21.6MB 10-K)

### Consumer Goods
- **KO** (Coca-Cola) - Beverages
- **PG** (Procter & Gamble) - Consumer products
- **JNJ** (Johnson & Johnson) - Healthcare/pharma

### Industrial/Energy
- **TSLA** (Tesla) - Automotive
- **BA** (Boeing) - Aerospace
- **UNP** (Union Pacific) - Transportation
- **XOM** (Exxon Mobil) - Energy

### Media
- **NFLX** (Netflix) - Streaming

## Statistics

- **Total files**: 32 (16 companies × 2 forms)
- **Total size**: 155.3MB
- **Form types**: 10-K, 10-Q
- **Size range**: 0.8MB (Tesla 10-K) to 21.7MB (GBDC 10-Q)
- **Date range**: 2024-2025 (most recent filings)

## Document Size Distribution

### Small (< 2MB)
- AAPL 10-Q (0.8MB), TSLA 10-K (0.8MB), IBM 10-K (1.1MB)
- NVDA 10-Q (1.3MB), PG 10-Q (1.3MB), UNP 10-Q (1.3MB)
- AAPL 10-K (1.4MB), TSLA 10-Q (1.4MB)
- NFLX 10-Q (1.6MB), XOM 10-Q (1.9MB), NFLX 10-K (1.9MB)

### Medium (2-8MB)
- BA 10-Q (2.0MB), KO 10-Q (2.0MB), UNP 10-K (2.0MB), NVDA 10-K (2.0MB)
- PG 10-K (2.4MB), JNJ 10-Q (2.6MB)
- BA 10-K (3.2MB), JNJ 10-K (3.5MB), IBM 10-Q (3.6MB), HUBS 10-Q (3.5MB)
- KO 10-K (3.7MB), HUBS 10-K (4.5MB)
- XOM 10-K (5.7MB)
- MSFT 10-Q (6.7MB), MSFT 10-K (7.8MB)

### Large (> 8MB)
- GS 10-Q (8.9MB), GS 10-K (9.6MB)
- JPM 10-Q (10.9MB), JPM 10-K (12.3MB)
- GBDC 10-K (21.6MB), GBDC 10-Q (21.7MB)

## Usage

### Download/Update Fixtures

```bash
# Download latest filings for all tickers
python tests/fixtures/download_html_fixtures.py

# Download for specific tickers
python tests/fixtures/download_html_fixtures.py --tickers AAPL MSFT

# Download multiple filings per form
python tests/fixtures/download_html_fixtures.py --max-per-form 3
```

### Use in Tests

```python
from pathlib import Path

# Load a specific fixture
html_path = Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html')
html = html_path.read_text()

# Iterate all fixtures
fixtures_dir = Path('tests/fixtures/html')
for html_file in fixtures_dir.rglob('*.html'):
    ticker = html_file.parent.parent.name
    form = html_file.parent.name
    # Test with html_file...
```

## Test Coverage Value

These fixtures provide:

1. **Industry diversity** - Tech, finance, consumer, industrial, energy
2. **Size diversity** - 0.8MB to 21.7MB
3. **Complexity diversity** - Simple to complex table structures
4. **Form diversity** - Both 10-K and 10-Q
5. **Recency** - All filings from 2024-2025

This enables comprehensive testing of:
- Parser performance across document sizes
- Section extraction accuracy
- Table parsing edge cases
- Memory efficiency
- Industry-specific formatting quirks

## Maintenance

Re-run the download script periodically to get the latest filings:

```bash
python tests/fixtures/download_html_fixtures.py
```

The script skips already-downloaded files, so it's safe to re-run.

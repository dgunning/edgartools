# Datamule Integration Research

**Date**: 2026-02-12
**GitHub Issue**: #212
**Status**: Evaluation

## Executive Summary

Datamule is a Python package (507 GitHub stars, MIT license) for working with SEC filings at scale, created by John Friedman. It has evolved significantly since issue #212 was filed in Jan 2025. The **original SGML blocker has been resolved** — datamule now has a dedicated `secsgml` package that parses SGML files and extracts metadata. However, the two projects have diverged in architecture: datamule stores parsed filings as **tar archives with metadata.json**, while edgartools stores **raw .nc (SGML) files**. Integration is feasible but the value proposition needs careful consideration.

## What is Datamule?

### Project Overview
- **Repo**: [john-friedman/datamule-python](https://github.com/john-friedman/datamule-python)
- **Stars**: 507 | **License**: MIT
- **Author**: John Friedman
- **Website**: [datamule.xyz](https://datamule.xyz)
- **Scale**: Serves 170TB+ data, 1.5B+ API requests

### Ecosystem (9 packages)
| Package | Purpose |
|---------|---------|
| `datamule` | Core package — download, search, process filings |
| `secsgml` | Parse SEC SGML files (powers datamule) |
| `secxbrl` | Fast, lightweight inline XBRL parser |
| `doc2dict` | Document-to-dictionary conversion |
| `txt2dataset` | Create datasets from unstructured text |
| `company-fundamentals` | Standardize XBRL into financial metrics |
| `datamule-data` | Daily-updating data repository |
| `datamule-indicators` | SEC data indicator creation |
| `secbrowser` | Flask-based filing browser |

## Architecture Comparison

### Datamule Download Architecture

**Two providers:**

1. **SEC Provider (free)** — Downloads SGML from SEC at rate limit (~5 req/s)
   - Uses SEC EFTS API to discover filing locations
   - Downloads SGML `.txt` files from `sec.gov/Archives/edgar/data/`
   - Parses with `secsgml` → extracts documents + metadata
   - Writes to **tar archives** with `metadata.json` + individual document files

2. **Datamule Cloud Provider (paid, $1/100k downloads)** — Downloads from datamule's cloud
   - Endpoint: `https://sec-library.datamule.xyz/` (SGML) or `https://sec-library.tar.datamule.xyz/` (pre-parsed tar)
   - No rate limits, ~100 concurrent downloads
   - Pre-parsed tar format with byte-level document indexing
   - ~10 days of SEC downloads → ~1 hour via datamule cloud

**Key classes:**
- `Portfolio(path)` — Main entry point, manages a collection of submissions on disk
- `Submission` — Single filing with metadata, documents, XBRL parsing
- `Downloader` / `TarDownloader` — Async download engines

**Storage format:**
```
portfolio_dir/
├── {accession_no_dash}.tar     # Individual submission tars
├── batch_000_001.tar           # Batched tars (for bulk)
└── errors.json                 # Download error log

# Inside each tar:
{accession}/
├── metadata.json               # Filing metadata (CIK, form type, dates, document list)
├── primary_doc.htm             # Main filing document
├── R1.htm, R2.htm              # Additional documents
└── exhibit.xml                 # Exhibits
```

### EdgarTools Local Storage Architecture

**Single provider:** Downloads from SEC EDGAR Feed archives

- Downloads `.nc.tar.gz` daily feed files from `sec.gov/Archives/edgar/Feed/`
- Extracts individual `.nc` (SGML) files per filing
- Optional gzip compression (`.nc.gz`)
- Metadata stays embedded in the SGML — parsed on demand via `SGMLParser`

**Storage format:**
```
~/.edgar/
├── filings/
│   └── YYYYMMDD/
│       ├── {accession-number}.nc       # Raw SGML file
│       └── {accession-number}.nc.gz    # Compressed SGML
├── companyfacts/                        # Pre-processed financial facts
├── submissions/                         # Company metadata indexes
└── reference/                           # Ticker/CIK mappings
```

**Key difference**: EdgarTools keeps the **raw SGML** and parses on access, giving full control over metadata extraction. Datamule **pre-parses into tar** with extracted documents + metadata.json.

## SGML Gap Analysis (Original Blocker)

### Status: RESOLVED

The `secsgml` package (53 stars) now provides:

```python
from secsgml import parse_sgml_content_into_memory, write_sgml_file_to_tar

# Parse SGML into memory — returns metadata dict + document list
result = parse_sgml_content_into_memory(filepath="filing.nc")

# Write SGML to tar — extracts documents into tar archive
write_sgml_file_to_tar("output.tar", input_path="filing.nc")
```

**Capabilities:**
- Parses both daily archives and individual submission SGML files
- Standardizes metadata (e.g., `CENTRAL INDEX KEY` → `cik`)
- Document type filtering with optional metadata retention
- Byte-level document locations in tar (v0.2.4+)
- Tested on entire SEC corpus
- Performance: 500MB SGML → 1,940ms (memory) / 3,960ms (tar)

**However**, datamule's download pipeline uses `secsgml` to **parse SGML into tar format**, discarding the raw SGML. EdgarTools needs raw SGML or would need an adapter to read datamule's tar format.

## Integration Options

### Option A: Use Datamule as Fast Download Backend (Replace SEC Feed Downloads)

**Concept**: Use datamule's cloud to download raw SGML files faster than SEC rate limits.

**Feasibility**: LOW
- Datamule's cloud stores **pre-parsed tars**, not raw SGML
- The SGML endpoint (`sec-library.datamule.xyz`) serves individual SGML files but requires API key
- Would need datamule to expose raw SGML downloads or add an endpoint for `.nc` files
- Requires paid API key ($1/100k downloads)

### Option B: Read Datamule's Downloaded Tar Files (Adapter Pattern)

**Concept**: Users download with datamule, edgartools reads the tar files.

**Feasibility**: MEDIUM
- Write a `DatamuleTarAdapter` that reads datamule's tar format
- Map datamule's `metadata.json` to edgartools' `FilingHeader` / `SGMLDocument` structure
- Documents are already extracted in the tar — no SGML re-parsing needed

**Pros:**
- Users who already have datamule downloads can use edgartools immediately
- No dependency on datamule package itself — just reads the file format
- Could be significantly faster for users needing both bulk download + analysis

**Cons:**
- Maintaining compatibility with datamule's evolving tar format
- Loss of raw SGML means some edgartools features may not work (e.g., correction files)
- Metadata fields may not map 1:1

### Option C: Optional Datamule Dependency for Bulk Downloads

**Concept**: `pip install edgartools[datamule]` adds datamule as optional dependency for faster bulk downloads.

**Feasibility**: MEDIUM-HIGH
- Wrap datamule's `Portfolio.download_submissions()` as an alternative download backend
- After download, convert datamule's tar format to edgartools' `.nc` format, or...
- Keep tar format and add a tar-aware storage reader

**Pros:**
- Users get a single `download_filings()` call with `provider='datamule'` option
- Leverages datamule's optimized download infrastructure
- Clean separation — datamule handles download, edgartools handles analysis

**Cons:**
- Adds dependency on external paid service
- Datamule package pulls in `secsgml`, `secxbrl`, `company-fundamentals`, `zstandard`, etc.
- Version coupling between datamule and edgartools

### Option D: Shared SGML Storage Standard (Collaboration)

**Concept**: Agree on a common storage format with John Friedman so both tools interoperate.

**Feasibility**: HIGH (long-term best option)
- Both projects already parse SGML from the same SEC feeds
- Standardize on a format both can read/write
- Could be: raw `.nc` files (edgartools' current format) or tar-with-metadata (datamule's format)

**Pros:**
- True interoperability — download with either tool, analyze with either tool
- No runtime dependency between packages
- Community benefit — any SEC tool could adopt the standard

**Cons:**
- Requires coordination and agreement from both authors
- One or both projects would need format migration

## Competitive Analysis

| Capability | EdgarTools | Datamule |
|-----------|------------|----------|
| **Bulk download** | SEC feeds only (~5 req/s) | SEC + cloud ($1/100k, ~100 concurrent) |
| **Download speed** | Days for large datasets | ~1 hour via cloud |
| **SGML parsing** | Custom `SGMLParser` | `secsgml` package |
| **XBRL parsing** | Full XBRL engine (`edgar/xbrl/`) | `secxbrl` (inline XBRL) |
| **Financial statements** | Rich statement objects, standardization | `company-fundamentals` package |
| **Company API** | `Company("AAPL")`, entity search | Portfolio-based access |
| **Filing analysis** | `TenK`, `TenQ`, `EightK` report objects | Document-level access |
| **Storage** | Local + cloud (S3/GCS/Azure/R2) | Local tar files |
| **Real-time monitoring** | `get_current_filings()` | `Monitor` class, websocket support |
| **License** | MIT | MIT |

**Key insight**: Datamule excels at **bulk download speed**. EdgarTools excels at **filing analysis and API ergonomics**. They're complementary, not competitive.

## Risks and Concerns

1. **Paid service dependency**: Datamule's speed advantage requires paid cloud access ($1/100k). Free path is SEC-rate-limited (same as edgartools).

2. **Maintenance risk**: Datamule is a solo developer project. Format changes, API endpoint changes, or project abandonment would break integration.

3. **Dependency bloat**: Datamule pulls in `secsgml`, `secxbrl`, `company-fundamentals`, `zstandard`, `aiohttp`, and more. Heavy for an optional feature.

4. **Format stability**: Datamule's tar format has evolved (batch tars, byte locations in v0.2.4). No formal schema versioning.

5. **Overlap concerns**: Both projects parse SGML and XBRL. Pulling in datamule means shipping duplicate functionality.

## Recommendation

### Short-term: Option B (Tar Adapter) — Low effort, high value

Build a read-only adapter that can load filings from datamule's tar format into edgartools' `Filing` / `SGMLDocument` objects. This:
- Requires zero dependency on datamule package
- Lets users who already downloaded with datamule use edgartools for analysis
- Is a small, self-contained module (~200-300 lines)
- Can be documented as: "Downloaded filings with datamule? Point edgartools at the directory."

### Medium-term: Option D (Shared Standard) — Discuss with John

Resume the conversation with John Friedman about a shared storage format. The `secsgml` package's metadata standardization (`header_standardization.py`) is a good starting point. Aligning on a common on-disk format would make both tools interoperable without runtime dependencies.

### Not recommended: Option C (Optional Dependency)

The dependency cost is too high for the benefit. Users who want datamule's speed can install it separately and use the tar adapter.

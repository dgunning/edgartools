---
description: Extract business descriptions, AIF sections, MD&A content, and XBRL financials from Canadian 40-F annual report filings.
---

# FortyF: Parse Canadian 40-F Annual Reports

Form 40-F is the annual report filed by ~200 Canadian companies cross-listed on US exchanges under the Multijurisdictional Disclosure System (MJDS). Unlike 10-K filings where the HTML contains business text directly, a 40-F is an iXBRL wrapper — the actual business content lives in a separate **Annual Information Form (AIF)** exhibit. Some filers also include a standalone **MD&A** exhibit. This guide details all data available from the `FortyF` class for building datasets and views.

---

## Overview

| Property | Type | Description |
|----------|------|-------------|
| Class Name | `FortyF` | |
| Forms Handled | `40-F`, `40-F/A` | |
| Module | `edgar.company_reports.forty_f` | |
| Source Data | AIF exhibit (HTML), MD&A exhibit (HTML), iXBRL wrapper | |
| Notable Filers | Shopify (SHOP), Royal Bank (RY), Barrick Gold (GOLD), Manulife (MFC), Enbridge (ENB), Canadian National (CNI) | |

---

## Getting a FortyF Object

```python
from edgar import Company

# From a company
company = Company("SHOP")
filing = company.get_filings(form="40-F").latest()
forty_f = filing.obj()    # FortyF instance

# From a specific filing
from edgar import Filing
filing = Filing(company='SHOPIFY INC.', cik=1594805, form='40-F',
                filing_date='2024-02-13', accession_no='0001594805-24-000007')
forty_f = filing.obj()
```

---

## Basic Metadata

Inherited from `CompanyReport` base class.

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `company` | `str` | Company name | `"SHOPIFY INC."` |
| `form` | `str` | Filing form type | `"40-F"` |
| `filing_date` | `date` | Date filed with SEC | `2024-02-13` |
| `period_of_report` | `date` | Fiscal year end | `2023-12-31` |

---

## AIF Document Access

The AIF (Annual Information Form) is the primary business content document in a 40-F filing. FortyF locates it automatically using a 5-tier priority chain (EX-1 standard MJDS exhibits, description match, filename keywords, content sniffing, inline fallback).

| Property | Type | Description |
|----------|------|-------------|
| `aif_attachment` | `Attachment` or `None` | The identified AIF exhibit attachment object |
| `aif_html` | `str` or `None` | Full raw HTML of the AIF document |
| `aif_text` | `str` or `None` | Full plain text of the AIF (via BeautifulSoup) |
| `aif_document` | `Document` or `None` | Parsed Document object from the AIF HTML |

### Usage for Datasets

```python
# Get the full AIF plain text for NLP / LLM pipelines
text = forty_f.aif_text
if text:
    print(f"AIF length: {len(text):,} characters")

# Get the raw HTML for web rendering or conversion
html = forty_f.aif_html
if html:
    # Save for downstream processing
    with open("shop_aif.html", "w") as f:
        f.write(html)
```

### Typical Sizes

| Filer | AIF HTML | AIF Text |
|-------|----------|----------|
| Shopify (SHOP) | ~690 KB | ~300 KB |
| Manulife (MFC) | ~1.6 MB | ~700 KB |
| Canadian Natural (CNQ) | Inline in 40-F wrapper | Varies |

---

## MD&A Document Access

Some Canadian filers include a separate MD&A (Management's Discussion and Analysis) as a distinct EX-99.x exhibit. FortyF discovers it using description matching, filename keywords (e.g. `annualmdareport`), and content sniffing. The AIF is excluded from candidates to avoid false matches.

| Property | Type | Description |
|----------|------|-------------|
| `mda_attachment` | `Attachment` or `None` | The identified MD&A exhibit attachment object |
| `mda_html` | `str` or `None` | Full raw HTML of the MD&A document |
| `mda_text` | `str` or `None` | Full plain text of the MD&A (via BeautifulSoup) |

### Usage for Datasets

```python
# Check if this filer has a separate MD&A
if forty_f.mda_attachment:
    mda = forty_f.mda_text
    print(f"MD&A length: {len(mda):,} characters")
else:
    print("No separate MD&A exhibit (may be embedded in annual report)")
```

### Which Filers Have Separate MD&A?

Not all 40-F filers include a standalone MD&A exhibit. Filers like Manulife (MFC) do; others like Shopify (SHOP) embed MD&A within a combined annual report or don't file it as a separate exhibit. Always check `mda_attachment is not None` before using.

---

## AIF Section Properties

The AIF follows Canadian NI 51-102 structure. FortyF detects section headings via regex and exposes them as named properties. All return `str` (plain text of that section) or `None` if the section is not found.

| Property | Type | Description |
|----------|------|-------------|
| `business` | `str` or `None` | Business description (extracted via dedicated algorithm) |
| `risk_factors` | `str` or `None` | Risk Factors section |
| `corporate_structure` | `str` or `None` | Corporate Structure section |
| `dividends` | `str` or `None` | Dividends section |
| `capital_structure` | `str` or `None` | Description of Capital Structure section |
| `directors_and_officers` | `str` or `None` | Directors and Officers section |
| `legal_proceedings` | `str` or `None` | Legal Proceedings section |

### Usage for Datasets

```python
# Build a dataset of business descriptions across Canadian filers
record = {
    "company": forty_f.company,
    "period": str(forty_f.period_of_report),
    "business": forty_f.business,
    "risk_factors": forty_f.risk_factors,
    "corporate_structure": forty_f.corporate_structure,
    "dividends": forty_f.dividends,
    "directors_and_officers": forty_f.directors_and_officers,
    "legal_proceedings": forty_f.legal_proceedings,
}
```

### Section Availability by Filer

Not every AIF contains all NI 51-102 sections. Sections return `None` when absent.

| Section | SHOP | MFC | CNQ | RY |
|---------|------|-----|-----|-----|
| Business | Yes | Yes | Yes | Yes |
| Risk Factors | Yes | Partial* | Yes | Yes |
| Corporate Structure | Yes | Yes | Yes | Yes |
| Dividends | Yes | Yes | Yes | Yes |
| Capital Structure | No | Yes | Yes | Yes |
| Directors and Officers | Yes | Yes | Yes | Yes |
| Legal Proceedings | Yes | Yes | Yes | Yes |

*Manulife's AIF contains "Risk Management" rather than "Risk Factors". The actual risk discussion is in the MD&A exhibit.

---

## Section Discovery and Lookup

For sections beyond the named properties, use the generic lookup interface.

| Property / Method | Type | Description |
|-------------------|------|-------------|
| `items` | `List[str]` | All detected section names (Title Case) |
| `forty_f[key]` | `str` or `None` | Look up any section by name |

### Lookup Rules

- **Exact match** (case-insensitive): `forty_f["Risk Factors"]`
- **Keyword containment**: `forty_f["business"]` matches "Description Of The Business"
- **Missing sections**: return `None`
- **Non-string keys**: raise `TypeError`

### Usage for Datasets

```python
# Discover what sections a filer includes
print(forty_f.items)
# ['Corporate Structure', 'Description Of The Business', 'Risk Factors',
#  'Dividends', 'Directors And Officers', 'Legal Proceedings', ...]

# Extract a section by name
section_text = forty_f["Market For Securities"]

# Build a complete section map
sections = {}
for name in forty_f.items:
    sections[name] = forty_f[name]
```

---

## XBRL Financial Statements

The 40-F wrapper document contains iXBRL data. Financial statements are accessed via properties inherited from the `CompanyReport` base class.

| Property | Type | Description |
|----------|------|-------------|
| `financials` | `Financials` or `None` | Complete XBRL financial statements object |
| `income_statement` | `Statement` or `None` | Income statement |
| `balance_sheet` | `Statement` or `None` | Balance sheet |
| `cash_flow_statement` | `Statement` or `None` | Cash flow statement |
| `auditor` | `AuditorInfo` or `None` | Auditor name, location, PCAOB firm ID, ICFR attestation |
| `reports` | `Reports` or `None` | XBRL viewer report pages (statements, notes, tables, details) from FilingSummary.xml |

### Usage for Datasets

```python
# Get financial data
financials = forty_f.financials
if financials:
    income = forty_f.income_statement
    balance = forty_f.balance_sheet
    cashflow = forty_f.cash_flow_statement
```

---

## LLM Context

| Method | Returns | Description |
|--------|---------|-------------|
| `to_context('minimal')` | `str` | Company, period, AIF/MD&A status |
| `to_context('standard')` | `str` | + detected sections, available properties |
| `to_context('full')` | `str` | + section text previews (first 150 chars each) |

```python
# Feed to an LLM for analysis
context = forty_f.to_context('standard')
```

---

## Batch Processing Pattern

```python
from edgar import Company
import pandas as pd

tickers = ["SHOP", "MFC", "RY", "GOLD", "ENB", "CNI", "BMO", "BN", "TU", "STN"]
records = []

for ticker in tickers:
    try:
        company = Company(ticker)
        filing = company.get_filings(form="40-F").latest()
        f = filing.obj()

        records.append({
            "ticker": ticker,
            "company": f.company,
            "period": str(f.period_of_report),
            "filed": str(f.filing_date),
            "has_aif": f.aif_attachment is not None,
            "has_mda": f.mda_attachment is not None,
            "sections_detected": len(f.items),
            "sections": f.items,
            "business_length": len(f.business) if f.business else 0,
            "aif_text_length": len(f.aif_text) if f.aif_text else 0,
            "mda_text_length": len(f.mda_text) if f.mda_text else 0,
            "has_financials": f.financials is not None,
        })
    except Exception as e:
        records.append({"ticker": ticker, "error": str(e)})

df = pd.DataFrame(records)
```

---

## Notes for Implementation

1. **AIF is Always a Single HTML File** — All AIF sections are embedded in one monolithic HTML document. They are not separate attachments. Section boundaries are detected via regex on the plain text.

2. **Two HTML Formats** — Workiva-generated AIFs use sequential HTML with `<div id="...">` anchors. CSS-positioned AIFs (e.g. Manulife) use absolute positioning but DOM order equals reading order, so `get_text()` works correctly for both.

3. **Section Text is Plain Text** — Named properties (`.business`, `.risk_factors`, etc.) and `__getitem__` return plain text, not HTML. Use `.aif_html` if you need the raw HTML for rendering.

4. **MD&A is Optional** — Only some filers include a standalone MD&A exhibit. Always check `mda_attachment is not None` before using `.mda_html` or `.mda_text`.

5. **Inline AIF Pattern** — A few filers (e.g. Canadian Natural Resources, CNQ) embed the AIF directly in the main 40-F document rather than as a separate exhibit. FortyF handles this transparently.

6. **Rate Limiting** — AIF and MD&A downloads hit the SEC EDGAR servers. When batch processing, respect SEC rate limits (10 requests/second). EdgarTools handles this internally, but large batches will take time.

7. **cached_property Semantics** — All document and section properties use `@cached_property`, so repeated access is free after the first call. But the first access to `.aif_html` triggers a network download, and the first access to `.business` triggers both the download and text extraction.

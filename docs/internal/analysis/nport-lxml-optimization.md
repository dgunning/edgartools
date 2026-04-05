# N-PORT XML Parsing Optimization: BeautifulSoup to lxml

## The Problem

EdgarTools parses N-PORT filings -- SEC-mandated portfolio disclosure reports filed by mutual funds and ETFs. These filings contain detailed holdings data: every security a fund owns, its value, identifiers, debt characteristics, derivative positions, and more.

A single N-PORT filing can contain thousands of holdings. Fidelity 500 Index Fund (FXAIX), for example, reports 3,819 holdings in a 3.3 MB XML document. Our existing parser used BeautifulSoup, a forgiving and developer-friendly HTML/XML parser. But for structured, well-formed XML like N-PORT filings, that friendliness comes at a steep cost.

Parsing FXAIX took **2.4 seconds** and consumed **139 MB** of peak memory -- just to read the XML into Python objects.

## Why BeautifulSoup Is Slow for This

BeautifulSoup is designed to handle messy, malformed HTML. It builds a full tree of `Tag` objects with navigation capabilities (`.parent`, `.next_sibling`, `.find_all` with recursive descent). Every element gets wrapped in a Python object with dictionaries for attributes and a navigable tree structure.

For N-PORT XML, which is consistently well-formed and schema-validated by the SEC, that overhead is pure waste. We don't need fault tolerance or fuzzy matching. We need fast, sequential access to known element paths.

## The lxml Approach

lxml wraps the C libraries libxml2 and libxslt. It operates on a C-level tree, exposing thin Python wrappers only when accessed. Element attribute access goes through C code, not Python dictionaries. XPath and `find()` operations traverse the C tree directly.

The rewrite touched two files:

- **`edgar/funds/reports.py`** -- The main N-PORT parser that extracts header data, fund info, and the full list of investment holdings
- **`edgar/funds/models/derivatives.py`** -- Models for derivative instruments (forwards, swaps, futures, options, swaptions)

### Core parsing change

Before:
```python
from bs4 import Tag
from edgar.xmltools import child_text, find_element, optional_decimal

root = find_element(xml, "edgarSubmission")
```

After:
```python
from lxml import etree

xml_bytes = xml.encode('utf-8') if isinstance(xml, str) else xml
root = etree.fromstring(xml_bytes)
_strip_namespaces(root)
```

`etree.fromstring()` parses the entire document in C and returns an element tree. We strip XML namespaces in a single pass so that subsequent lookups use clean tag names like `"invstOrSec"` instead of `"{http://www.sec.gov/edgar/nport}invstOrSec"`.

### Element access patterns

BeautifulSoup's `find()` searches all descendants by default. lxml's `find()` searches only direct children, matching XPath `./child` semantics. This is actually what we want most of the time -- it's more precise and faster.

Before (BeautifulSoup):
```python
# Searches ALL descendants -- works but wasteful
name = child_text(tag, "name")
value = optional_decimal(tag, "valUSD")
attr = element.attrs.get("period1Yr", "0")
```

After (lxml):
```python
# Searches direct children only -- precise and fast
name = _text(tag, "name")
value = _opt_decimal(tag, "valUSD")
attr = element.get("period1Yr", "0")
```

The helper functions are minimal:

```python
def _text(parent, tag):
    """Get text of a direct child element, or None."""
    if parent is None:
        return None
    el = parent.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return None

def _opt_decimal(parent, tag):
    """Get optional Decimal from child element text."""
    text = _text(parent, tag)
    if text:
        try:
            return Decimal(text)
        except (ValueError, TypeError, ArithmeticError):
            return None
    return None
```

### The descendant search gotcha

The one place where BeautifulSoup's default descendant search was actually needed: `issuerCredentials` is nested under `filerInfo > filer > issuerCredentials`, not directly under `filerInfo`. BeautifulSoup found it automatically. lxml requires an explicit descendant search:

```python
# lxml: use ".//tag" for descendant search
cred_tag = filer_info_tag.find(".//issuerCredentials")
```

This was the only bug we hit during the migration. Every other `find()` call worked correctly with direct-child semantics because N-PORT XML is relatively flat within each section.

### Reducing code in derivatives.py

The derivative models had significant code duplication -- each of the five derivative types (forwards, swaps, futures, options, swaptions) repeated the same `derivAddlInfo` and `counterparties` parsing blocks. The rewrite extracted shared helpers:

```python
def _parse_deriv_addl_info(tag):
    """Parse derivAddlInfo block common to all derivative types."""
    ...

def _parse_counterparties(tag):
    """Parse counterparties block. Returns (name, lei) tuple."""
    ...

def _parse_ref_instrument_identifiers(identifiers_el):
    """Parse identifiers block within a reference instrument."""
    ...
```

This cut the derivatives file from 659 lines of parsing code to 572 lines, while also making each `from_xml()` method clearer.

## Benchmark Results

We benchmarked three funds of increasing size, measuring parse time (average of 5 iterations after warm-up) and peak memory allocation:

### Before (BeautifulSoup)

| Fund | Ticker | Holdings | XML Size | Parse Time | Peak Memory | Per Holding |
|------|--------|----------|----------|------------|-------------|-------------|
| Vanguard 500 Index | VFIAX | 186 | 185 KB | 124 ms | 7,252 KB | 0.667 ms |
| SPDR S&P 500 ETF | SPY | 503 | 442 KB | 310 ms | 18,347 KB | 0.616 ms |
| Fidelity 500 Index | FXAIX | 3,819 | 3,338 KB | 2,397 ms | 138,768 KB | 0.628 ms |

### After (lxml)

| Fund | Ticker | Holdings | XML Size | Parse Time | Peak Memory | Per Holding |
|------|--------|----------|----------|------------|-------------|-------------|
| Vanguard 500 Index | VFIAX | 186 | 185 KB | 12.1 ms | 1,175 KB | 0.065 ms |
| SPDR S&P 500 ETF | SPY | 503 | 442 KB | 31.0 ms | 3,008 KB | 0.062 ms |
| Fidelity 500 Index | FXAIX | 3,819 | 3,338 KB | 244.5 ms | 22,839 KB | 0.064 ms |

### Improvement

| Metric | Improvement | Notes |
|--------|-------------|-------|
| Parse speed | **~10x faster** | Consistent across all sizes |
| Memory usage | **~6x less** | Consistent across all sizes |
| Per-holding cost | **~10x lower** | 0.63 ms/holding -> 0.064 ms/holding |

The speedup is remarkably consistent: approximately 10x for parse time and 6x for memory, regardless of filing size. This linearity suggests the improvement is per-element, not overhead-related.

## What Didn't Change

- **The public API is identical.** `FundReport.parse_fund_xml(xml)` takes the same input and returns the same dictionary structure. All Pydantic models remain unchanged.
- **All 1,363 existing tests pass.** No behavioral regressions.
- **Error handling is preserved.** lxml falls back to a recovery parser for malformed XML, just as BeautifulSoup would attempt to repair it.
- **The net line count decreased.** 572 insertions, 659 deletions -- we removed more code than we added, thanks to extracting shared parsing helpers in the derivatives module.

## When to Use This Pattern

This optimization works well when:

1. **The XML is well-formed and schema-defined** -- N-PORT filings are validated by the SEC before acceptance
2. **You're doing sequential, structured extraction** -- reading known fields from known paths, not searching or scraping
3. **The documents are large** -- the C-level parsing advantage grows with document size
4. **You're processing many documents** -- the per-document savings compound across a corpus

It's less compelling when dealing with malformed HTML, when you need BeautifulSoup's CSS selector syntax, or when XML structure varies unpredictably across documents.

## The Namespace Stripping Pattern

N-PORT XML uses XML namespaces:
```xml
<edgarSubmission xmlns="http://www.sec.gov/edgar/nport"
                 xmlns:com="http://www.sec.gov/edgar/common">
```

lxml preserves these as `{http://www.sec.gov/edgar/nport}invstOrSec`, making every `find()` call verbose. We strip namespaces in a single upfront pass:

```python
def _strip_namespaces(root):
    for el in root.iter():
        tag = el.tag
        if isinstance(tag, str) and '}' in tag:
            el.tag = tag.split('}', 1)[1]
        attrib = el.attrib
        keys_to_fix = [k for k in attrib if '}' in k]
        for k in keys_to_fix:
            new_key = k.split('}', 1)[1]
            attrib[new_key] = attrib.pop(k)
```

This costs microseconds on the full tree traversal and saves complexity in every subsequent lookup. The alternative -- using `nsmap` or qualified names everywhere -- adds visual noise and is fragile to namespace prefix changes across filings.

## Prior Art

This follows the same pattern we used to optimize 13F-HR (institutional holdings) parsing, which saw similar speedups. The N-PORT case is more complex due to the variety of data types (debt securities, derivatives, security lending info), but the approach is the same: replace the Python-heavy parser with C-backed lxml and use simple helper functions for the repetitive field extraction pattern.

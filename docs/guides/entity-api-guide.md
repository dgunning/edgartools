# Entity/Company API Guide

This guide covers the Entity and Company API improvements in EdgarTools v5.3.0, including filer category identification and company icon retrieval.

## Table of Contents

1. [Filer Category API](#filer-category-api)
2. [Company Icon API](#company-icon-api)
3. [Integration Examples](#integration-examples)

---

## Filer Category API

The SEC classifies public companies into filer categories based on their public float (market value of voting and non-voting common equity held by non-affiliates). EdgarTools v5.3.0 provides structured access to this classification data.

### Filer Status Classifications

| Status | Public Float Threshold | Filing Deadlines |
|--------|----------------------|------------------|
| Large Accelerated Filer | >= $700 million | 60 days (10-K), 40 days (10-Q) |
| Accelerated Filer | >= $75M and < $700M | 75 days (10-K), 40 days (10-Q) |
| Non-Accelerated Filer | < $75 million | 90 days (10-K), 45 days (10-Q) |

### Filer Qualifications

In addition to the base status, companies may have these qualifications:

- **Smaller Reporting Company (SRC)**: < $250M public float OR < $100M annual revenue
- **Emerging Growth Company (EGC)**: < $1.235B revenue, IPO within 5 years

### Quick Usage

```python
from edgar import Company

company = Company("AAPL")

# Boolean property checks
if company.is_large_accelerated_filer:
    print("Large accelerated filer - earliest filing deadlines")

if company.is_smaller_reporting_company:
    print("Qualifies for scaled disclosure requirements")

if company.is_emerging_growth_company:
    print("May use EGC accommodations")
```

### Available Properties

| Property | Type | Description |
|----------|------|-------------|
| `filer_category` | `FilerCategory` | Full parsed category object |
| `is_large_accelerated_filer` | `bool` | Public float >= $700M |
| `is_accelerated_filer` | `bool` | Public float >= $75M and < $700M |
| `is_non_accelerated_filer` | `bool` | Public float < $75M |
| `is_smaller_reporting_company` | `bool` | Qualifies as SRC |
| `is_emerging_growth_company` | `bool` | Qualifies as EGC |

### Working with FilerCategory Object

For more detailed analysis, use the `filer_category` property:

```python
from edgar import Company
from edgar.enums import FilerStatus, FilerQualification

company = Company("AAPL")
category = company.filer_category

# Access the base status enum
status = category.status  # FilerStatus.LARGE_ACCELERATED

# Check specific status
if category.status == FilerStatus.LARGE_ACCELERATED:
    print("Large accelerated filer")

# Get all qualifications as a list
qualifications = category.qualifications
# Returns: [FilerQualification.SMALLER_REPORTING_COMPANY, ...]

# String representation (original SEC format)
print(str(category))  # "Large accelerated filer"
```

### Parsing SEC Category Strings

The SEC returns category as a compound string with `|` separator:

```python
from edgar.enums import FilerCategory

# Parse SEC format strings directly
category = FilerCategory.from_string("Accelerated filer | Smaller reporting company")

print(category.status)                      # FilerStatus.ACCELERATED
print(category.is_smaller_reporting_company)  # True
print(category.is_emerging_growth_company)    # False

# Handle compound qualifications
category = FilerCategory.from_string(
    "Non-accelerated filer | Smaller reporting company | Emerging growth company"
)
print(len(category.qualifications))  # 2
```

### Enums Reference

```python
from edgar.enums import FilerStatus, FilerQualification

# FilerStatus values
FilerStatus.LARGE_ACCELERATED  # "Large accelerated filer"
FilerStatus.ACCELERATED        # "Accelerated filer"
FilerStatus.NON_ACCELERATED    # "Non-accelerated filer"

# FilerQualification values
FilerQualification.SMALLER_REPORTING_COMPANY  # "Smaller reporting company"
FilerQualification.EMERGING_GROWTH_COMPANY    # "Emerging growth company"
```

---

## Company Icon API

EdgarTools provides access to company logo/icon images via the `get_icon_from_ticker` function. Icons are sourced from the [nvstly/icons](https://github.com/nvstly/icons) repository on GitHub.

### Basic Usage

```python
from edgar import get_icon_from_ticker

# Get icon as PNG bytes
icon_bytes = get_icon_from_ticker("AAPL")

if icon_bytes:
    # Save to file
    with open("apple_logo.png", "wb") as f:
        f.write(icon_bytes)
```

### Function Signature

```python
def get_icon_from_ticker(ticker: str) -> Optional[bytes]:
    """
    Download an icon for a given ticker as a PNG image, if available.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT", "BRK-B")

    Returns:
        bytes: PNG image data if icon exists
        None: If no icon is available for this ticker

    Raises:
        ValueError: If ticker is invalid (empty, contains invalid characters)
    """
```

### Handling Hyphenated Tickers

As of v5.3.0, hyphenated tickers are fully supported:

```python
# Berkshire Hathaway Class B shares
icon = get_icon_from_ticker("BRK-B")  # Works correctly

# The function strips hyphens internally since the icon repository
# stores icons as BRKB.png, not BRK-B.png
```

### Validation Rules

The ticker must:
- Be a non-empty string
- Contain only alphabetic characters (A-Z) and hyphens (-)
- Not contain numbers, spaces, or special characters

```python
# Valid tickers
get_icon_from_ticker("AAPL")    # OK
get_icon_from_ticker("BRK-B")   # OK (hyphenated)
get_icon_from_ticker("msft")    # OK (case insensitive)

# Invalid tickers - raise ValueError
get_icon_from_ticker("")        # Empty string
get_icon_from_ticker("AAPL123") # Contains numbers
get_icon_from_ticker("AA PL")   # Contains space
get_icon_from_ticker(None)      # Not a string
```

### Caching

The function uses LRU caching (maxsize=4) to avoid repeated network requests:

```python
# First call fetches from network
icon1 = get_icon_from_ticker("AAPL")

# Subsequent calls return cached result
icon2 = get_icon_from_ticker("AAPL")  # Instant, no network call
```

### Building Icon URLs

If you need the URL directly (e.g., for client-side rendering):

```python
from edgar.reference.tickers import get_ticker_icon_url

url = get_ticker_icon_url("AAPL")
# Returns: "https://raw.githubusercontent.com/nvstly/icons/main/ticker_icons/AAPL.png"
```

**Note**: For hyphenated tickers, you need to strip the hyphen manually for the URL:

```python
ticker = "BRK-B"
url = f"https://raw.githubusercontent.com/nvstly/icons/main/ticker_icons/{ticker.replace('-', '').upper()}.png"
# Returns: "https://raw.githubusercontent.com/nvstly/icons/main/ticker_icons/BRKB.png"
```

---

## Integration Examples

### SaaS Dashboard: Company Card Component

```python
from edgar import Company, get_icon_from_ticker
import base64

def get_company_card_data(ticker: str) -> dict:
    """
    Build company card data for a SaaS dashboard.
    """
    company = Company(ticker)

    # Get icon as base64 for embedding in HTML/JSON
    icon_bytes = get_icon_from_ticker(ticker)
    icon_base64 = base64.b64encode(icon_bytes).decode() if icon_bytes else None

    # Determine regulatory tier for UI badges
    if company.is_large_accelerated_filer:
        regulatory_tier = "Large Cap"
        tier_color = "blue"
    elif company.is_accelerated_filer:
        regulatory_tier = "Mid Cap"
        tier_color = "green"
    else:
        regulatory_tier = "Small Cap"
        tier_color = "gray"

    # Build badges list
    badges = [regulatory_tier]
    if company.is_smaller_reporting_company:
        badges.append("SRC")
    if company.is_emerging_growth_company:
        badges.append("EGC")

    return {
        "ticker": ticker,
        "name": company.name,
        "cik": company.cik,
        "icon_base64": icon_base64,
        "icon_url": f"data:image/png;base64,{icon_base64}" if icon_base64 else None,
        "regulatory_tier": regulatory_tier,
        "tier_color": tier_color,
        "badges": badges,
        "filer_category_raw": str(company.filer_category),
    }

# Usage
card = get_company_card_data("AAPL")
# {
#     "ticker": "AAPL",
#     "name": "Apple Inc.",
#     "cik": 320193,
#     "icon_base64": "iVBORw0KGgo...",
#     "regulatory_tier": "Large Cap",
#     "tier_color": "blue",
#     "badges": ["Large Cap"],
#     "filer_category_raw": "Large accelerated filer"
# }
```

### Filtering Companies by Filer Status

```python
from edgar import Company

def filter_by_filer_status(tickers: list[str], status: str) -> list[str]:
    """
    Filter tickers by their SEC filer status.

    Args:
        tickers: List of ticker symbols
        status: One of "large_accelerated", "accelerated", "non_accelerated"

    Returns:
        List of tickers matching the specified status
    """
    results = []

    for ticker in tickers:
        try:
            company = Company(ticker)

            match status:
                case "large_accelerated":
                    if company.is_large_accelerated_filer:
                        results.append(ticker)
                case "accelerated":
                    if company.is_accelerated_filer:
                        results.append(ticker)
                case "non_accelerated":
                    if company.is_non_accelerated_filer:
                        results.append(ticker)
        except Exception:
            continue  # Skip invalid tickers

    return results

# Find all emerging growth companies
def find_egc_companies(tickers: list[str]) -> list[str]:
    return [t for t in tickers if Company(t).is_emerging_growth_company]
```

### API Response Builder

```python
from edgar import Company, get_icon_from_ticker
from edgar.enums import FilerStatus
import json

def build_company_api_response(ticker: str) -> dict:
    """
    Build a complete API response for company data.
    """
    company = Company(ticker)
    category = company.filer_category

    return {
        "company": {
            "ticker": ticker,
            "name": company.name,
            "cik": company.cik,
        },
        "filer_classification": {
            "status": category.status.value if category.status else None,
            "status_code": category.status.name if category.status else None,
            "is_large_accelerated": company.is_large_accelerated_filer,
            "is_accelerated": company.is_accelerated_filer,
            "is_non_accelerated": company.is_non_accelerated_filer,
        },
        "qualifications": {
            "smaller_reporting_company": company.is_smaller_reporting_company,
            "emerging_growth_company": company.is_emerging_growth_company,
        },
        "branding": {
            "icon_available": get_icon_from_ticker(ticker) is not None,
            "icon_url": f"/api/company/{ticker}/icon",  # Your API endpoint
        },
        "raw_sec_category": str(category),
    }

# Example output for AAPL:
# {
#     "company": {"ticker": "AAPL", "name": "Apple Inc.", "cik": 320193},
#     "filer_classification": {
#         "status": "Large accelerated filer",
#         "status_code": "LARGE_ACCELERATED",
#         "is_large_accelerated": True,
#         "is_accelerated": False,
#         "is_non_accelerated": False
#     },
#     "qualifications": {
#         "smaller_reporting_company": False,
#         "emerging_growth_company": False
#     },
#     "branding": {
#         "icon_available": True,
#         "icon_url": "/api/company/AAPL/icon"
#     },
#     "raw_sec_category": "Large accelerated filer"
# }
```

### Flask/FastAPI Icon Endpoint

```python
# Flask example
from flask import Flask, Response, abort
from edgar import get_icon_from_ticker

app = Flask(__name__)

@app.route("/api/company/<ticker>/icon")
def company_icon(ticker: str):
    try:
        icon_bytes = get_icon_from_ticker(ticker.upper())
        if icon_bytes is None:
            abort(404, description="Icon not available for this ticker")
        return Response(icon_bytes, mimetype="image/png")
    except ValueError as e:
        abort(400, description=str(e))
```

```python
# FastAPI example
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from edgar import get_icon_from_ticker

app = FastAPI()

@app.get("/api/company/{ticker}/icon")
async def company_icon(ticker: str):
    try:
        icon_bytes = get_icon_from_ticker(ticker.upper())
        if icon_bytes is None:
            raise HTTPException(status_code=404, detail="Icon not available")
        return Response(content=icon_bytes, media_type="image/png")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

## Notes and Limitations

### Filer Category API

- Filer category data comes from SEC submission metadata
- The `filer_category` property is cached per Company instance
- Some older or unusual entities may not have category data (returns empty `FilerCategory`)

### Icon API

- Icons are sourced from a third-party GitHub repository (nvstly/icons)
- Not all tickers have icons available - check for `None` return
- The repository focuses on popular US stocks
- Icon format is PNG
- Results are cached (LRU cache, maxsize=4)
- Network errors (other than 404) are propagated as exceptions

### Performance Considerations

```python
# For batch operations, consider caching at the application level
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_company_data_cached(ticker: str):
    company = Company(ticker)
    return {
        "name": company.name,
        "is_large_accelerated": company.is_large_accelerated_filer,
        # ... etc
    }
```

# Data Objects Guide

Data objects parse SEC filing data into typed Python objects with structured fields and methods.

---

## The `obj()` Function

The `obj()` function converts a `Filing` into a structured data object.

```python
from edgar import Company

filing = Company("AAPL").get_filings(form="10-K")[0]
data_obj = filing.obj()
```

### Return Behavior

`filing.obj()` returns one of three outcomes:

| Condition | Returns | Example |
|-----------|---------|---------|
| Form has a mapped data object | The specific data object | `TenK`, `Form4`, `ThirteenF` |
| No mapping, but filing has XBRL | `XBRL` object | Generic XBRL for S-1, 10-K/A without mapping |
| No mapping and no XBRL | `None` | Text-only filings like comment letters |

### Determining Object Type

```python
data_obj = filing.obj()

if data_obj is None:
    # No structured data available
    pass
elif isinstance(data_obj, XBRL):
    # Fallback XBRL object (no specific data object for this form)
    pass
else:
    # Specific data object - check type
    obj_type = type(data_obj).__name__  # e.g., "TenK", "Form4"
```

---

## Data Objects Reference

Each data object type requires its own view. Grouped by data object class:

### Company Reports

| Data Object | Forms | Module | Data Extracted |
|-------------|-------|--------|----------------|
| `TenK` | 10-K, 10-K/A | `edgar.company_reports` | Annual financials (XBRL), MD&A, risk factors, business description, exhibits |
| `TenQ` | 10-Q, 10-Q/A | `edgar.company_reports` | Quarterly financials (XBRL), interim MD&A, liquidity updates |
| `EightK` | 8-K, 8-K/A | `edgar.company_reports` | Event items (1.01-9.01), press releases, material agreements, exhibits |
| `TwentyF` | 20-F, 20-F/A | `edgar.company_reports` | Foreign issuer annual report, full financials (XBRL), business overview |
| `CurrentReport` | 6-K, 6-K/A | `edgar.company_reports` | Foreign issuer current events, material disclosures |

### Insider & Ownership

| Data Object | Forms | Module | Data Extracted |
|-------------|-------|--------|----------------|
| `Form3` | 3, 3/A | `edgar.ownership` | Initial ownership: insider name, relationship, securities held (direct/indirect) |
| `Form4` | 4, 4/A | `edgar.ownership` | Transactions: insider, buy/sell, shares, price, date, holdings after transaction |
| `Form5` | 5, 5/A | `edgar.ownership` | Annual summary: year-end positions, late-reported transactions, gifts |
| `Form144` | 144, 144/A | `edgar.form144` | Restricted stock sale notice: seller, issuer, shares, approximate sale date, broker |

### Institutional Holdings

| Data Object | Forms | Module | Data Extracted |
|-------------|-------|--------|----------------|
| `ThirteenF` | 13F-HR, 13F-HR/A | `edgar.thirteenf` | Portfolio holdings table: security name, CUSIP, shares, market value, investment discretion |

### Beneficial Ownership

| Data Object | Forms | Module | Data Extracted |
|-------------|-------|--------|----------------|
| `Schedule13D` | SC 13D, SC 13D/A | `edgar.beneficial_ownership` | Active 5%+ holder: filer identity, ownership percentage, purpose/intentions, funding source |
| `Schedule13G` | SC 13G, SC 13G/A | `edgar.beneficial_ownership` | Passive 5%+ holder: filer identity, ownership percentage, filing category |

### Offerings

| Data Object | Forms | Module | Data Extracted |
|-------------|-------|--------|----------------|
| `FormD` | D, D/A | `edgar.offerings` | Private placement: offering amount, exemption (506b/506c/etc), investor count, sales commissions |
| `FormC` | C, C/A, C-U, C-AR, C-TR | `edgar.offerings` | Crowdfunding: target/max amount, deadline, use of proceeds, financials, intermediary |

### Fund Reports

| Data Object | Forms | Module | Data Extracted |
|-------------|-------|--------|----------------|
| `FundReport` | NPORT-P, NPORT-EX | `edgar.funds` | Portfolio holdings: all securities, quantities, values, asset type, country, liquidity classification |

### Other

| Data Object | Forms | Module | Data Extracted |
|-------------|-------|--------|----------------|
| `MunicipalAdvisorForm` | MA-I, MA-I/A | `edgar.muniadvisors` | Advisor registration: firm info, personnel, disciplinary history |
| `Effect` | EFFECT | `edgar.effect` | Registration effectiveness: effective date, related registration statement |

### Fallback

| Data Object | Forms | Module | Data Extracted |
|-------------|-------|--------|----------------|
| `XBRL` | Any with XBRL | `edgar.xbrl` | Financial statements, facts, labels, calculations (when no specific data object exists) |

---

## View Routing Logic

For building views per data object type:

```python
from edgar import XBRL
from edgar.company_reports import TenK, TenQ, EightK, TwentyF, CurrentReport
from edgar.ownership import Form3, Form4, Form5
from edgar.form144 import Form144
from edgar.thirteenf import ThirteenF
from edgar.beneficial_ownership import Schedule13D, Schedule13G
from edgar.offerings import FormD, FormC
from edgar.funds import FundReport
from edgar.muniadvisors import MunicipalAdvisorForm
from edgar.effect import Effect

def get_view_type(filing):
    """Determine which view to render for a filing."""
    data_obj = filing.obj()

    if data_obj is None:
        return "no_data"

    # Map data object type to view
    view_map = {
        TenK: "tenk_view",
        TenQ: "tenq_view",
        EightK: "eightk_view",
        TwentyF: "twentyf_view",
        CurrentReport: "current_report_view",
        Form3: "form3_view",
        Form4: "form4_view",
        Form5: "form5_view",
        Form144: "form144_view",
        ThirteenF: "thirteenf_view",
        Schedule13D: "schedule13d_view",
        Schedule13G: "schedule13g_view",
        FormD: "formd_view",
        FormC: "formc_view",
        FundReport: "fund_report_view",
        MunicipalAdvisorForm: "muni_advisor_view",
        Effect: "effect_view",
        XBRL: "xbrl_fallback_view",
    }

    return view_map.get(type(data_obj), "unknown")
```

---

## Summary: 17 Data Object Types

| # | Data Object | View Required |
|---|-------------|---------------|
| 1 | `TenK` | Annual report view |
| 2 | `TenQ` | Quarterly report view |
| 3 | `EightK` | Current events view |
| 4 | `TwentyF` | Foreign annual view |
| 5 | `CurrentReport` | Foreign current view |
| 6 | `Form3` | Initial ownership view |
| 7 | `Form4` | Transaction view |
| 8 | `Form5` | Annual ownership view |
| 9 | `Form144` | Restricted sale view |
| 10 | `ThirteenF` | Holdings table view |
| 11 | `Schedule13D` | Active ownership view |
| 12 | `Schedule13G` | Passive ownership view |
| 13 | `FormD` | Private offering view |
| 14 | `FormC` | Crowdfunding view |
| 15 | `FundReport` | Fund portfolio view |
| 16 | `MunicipalAdvisorForm` | Muni advisor view |
| 17 | `Effect` | Effectiveness view |
| -- | `XBRL` | Fallback XBRL view |

# Data Objects (ai_doc)

## Overview

Data Objects in EdgarTools provide structured, programmatic access to the contents of SEC filings. Each Data Object is tailored to a specific filing type, extracting and organizing relevant data fields in a consistent, user-friendly interface. This abstraction makes it easy to work with complex SEC filings across many forms.

Data Objects are typically constructed via the `obj()` function, which returns the appropriate data object for a given `Filing` instance. This function inspects the filing type and returns an object with methods and properties specific to that form.

---

## How to Use Data Objects

1. **Obtain a Filing**: Use EdgarTools search or retrieval functions to get a `Filing` object (e.g., from accession number, CIK, ticker, etc.).
2. **Get the Data Object**: Pass the `Filing` to `edgar.obj()` to obtain the structured Data Object.

```python
from edgar import find, obj

filing = find("0000320193-23-000119")  # Example accession number
filing_data = obj(filing)

# Now, filing_data is a type-specific object, e.g., TenK, ThirteenF, FundReport, etc.
```

---

## Supported Filing Types and Data Objects

| Form                       | Data Object                  | Description                           |
|----------------------------|------------------------------|---------------------------------------|
| 10-K                       | `TenK`                       | Annual report                         |
| 10-Q                       | `TenQ`                       | Quarterly report                      |
| 8-K                        | `EightK`                     | Current report                        |
| MA-I                       | `MunicipalAdvisorForm`       | Municipal advisor initial filing      |
| Form 144                   | `Form144`                    | Notice of proposed sale of securities |
| C, C-U, C-AR, C-TR         | `FormC`                      | Form C Crowdfunding Offering          |
| D                          | `FormD`                      | Form D Offering                       |
| 3, 4, 5                    | `Ownership`, `Form3`, `Form4`, `Form5` | Ownership reports           |
| 13F-HR                     | `ThirteenF`                  | 13F Holdings Report                   |
| NPORT-P                    | `FundReport`                 | Fund Report                           |
| EFFECT                     | `Effect`                     | Notice of Effectiveness               |
| Any filing with XBRL       | `FilingXbrl`                 | XBRL-enabled filing                   |

---

## Data Object Details by Form

### 10-K — `TenK`
**Description:** Annual report. Provides structured access to business description, risk factors, financial statements, and more.
**Typical attributes/methods:**
- `business_description`
- `risk_factors`
- `financials`
- `get_section(name)`

**Example:**
```python
filing = find("<10-K accession>")
tenk = obj(filing)
print(tenk.business_description)
```

---

### 10-Q — `TenQ`
**Description:** Quarterly report. Similar to `TenK` but for quarterly periods.
**Typical attributes/methods:**
- `financials`
- `get_section(name)`

---

### 8-K — `EightK`
**Description:** Current report. Provides access to significant corporate events.
**Typical attributes/methods:**
- `items` (list of reported events)
- `get_item(number)`

---

### MA-I — `MunicipalAdvisorForm`
**Description:** Municipal advisor initial filing.
**Typical attributes/methods:**
- `advisor_name`
- `registration_details`

---

### Form 144 — `Form144`
**Description:** Notice of proposed sale of securities.
**Typical attributes/methods:**
- `issuer`
- `sale_amount`

---

### C, C-U, C-AR, C-TR — `FormC`
**Description:** Crowdfunding offering forms.
**Typical attributes/methods:**
- `offering_details`
- `issuer`

---

### D — `FormD`
**Description:** Form D offering.
**Typical attributes/methods:**
- `issuer`
- `offering_amount`

---

### 3, 4, 5 — `Ownership`, `Form3`, `Form4`, `Form5`
**Description:** Insider ownership reports.
**Typical attributes/methods:**
- `reporting_owner`
- `transactions`

---

### 13F-HR — `ThirteenF`
**Description:** 13F Holdings Report. Provides portfolio holdings for institutional investment managers.
**Typical attributes/methods:**
- `holdings` (DataFrame)
- `summary`

---

### NPORT-P — `FundReport`
**Description:** Fund portfolio report.
**Typical attributes/methods:**
- `portfolio` (DataFrame)
- `fund_info`

---

### EFFECT — `Effect`
**Description:** Notice of effectiveness.
**Typical attributes/methods:**
- `effective_date`
- `related_filing`

---

### XBRL-enabled filings — `FilingXbrl`
**Description:** Any filing with XBRL data. Provides structured access to XBRL facts.
**Typical attributes/methods:**
- `facts`
- `contexts`
- `get_fact(name)`

---

## Notes

- If a filing type is not supported, `obj()` may return `None` or raise a `DataObjectException`.
- For filings with XBRL data, the returned object will be of type `FilingXbrl`.
- Data Objects expose attributes and methods specific to their filing type (see documentation for each class).

---

## Example: Accessing Data from a 13F Filing

```python
from edgar import find, obj

filing = find("0000950123-23-004567")  # 13F-HR accession number
thirteenf = obj(filing)

holdings = thirteenf.holdings  # Access the holdings DataFrame
```

---

## Exception Handling

If `obj()` cannot create a Data Object for a filing, it raises a `DataObjectException` with details about the failure.

```python
from edgar import obj, DataObjectException

try:
    data = obj(filing)
except DataObjectException as e:
    print(e)
```

---

For more details, see the EdgarTools documentation for each specific Data Object class.

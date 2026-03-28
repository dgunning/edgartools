---
description: Parse SEC DRS draft registration statement filings with Python. Detect the underlying form type (S-1, F-1, S-4, 20-F) and access the full registration data object using edgartools.
---

# DRS: Draft Registration Statements with Python

EdgarTools parses DRS and DRS/A filings into a `DraftRegistrationStatement` object. A DRS is a confidential submission companies file with the SEC before going public — the content is identical to an S-1 or F-1, but the filing remains confidential until the company proceeds with the registration.

```python
from edgar import find

filing = find("0001193125-23-276353")   # any DRS accession number
drs = filing.obj()                      # DraftRegistrationStatement
```

## What the Object Contains

EDGAR's metadata for DRS filings says only "DRS" or "DRS/A" — it does not tell you whether the underlying document is an S-1, F-1, S-4, or another form. `DraftRegistrationStatement` reads the cover page text to detect the form type, then builds a fully parsed data object for the underlying registration when one is available.

```python
drs.form              # "DRS" or "DRS/A"
drs.underlying_form   # "S-1", "F-1", "S-4", "S-3", "20-F", "Form 10", ...
drs.is_amendment      # True if DRS/A
drs.amendment_number  # 2 for "Amendment No. 2", else None
drs.registration_number  # "377-01234" or None
```

## Access the Underlying Registration Object

When the detected form type is S-1 or F-1, `underlying_object` returns a fully parsed `RegistrationS1` with all its properties — cover page, fee table, offering type, and more.

```python
obj = drs.underlying_object  # RegistrationS1, RegistrationS3, or None

if obj is not None:
    print(obj.offering_type.display_name)

    cp = obj.cover_page
    print(cp.state_of_incorporation)
    print(cp.sic_code)
    print(cp.ein)

    ft = obj.fee_table        # fee table if present
```

`underlying_object` is `None` for form types without a dedicated data object (S-4, 20-F, Form 10, etc.). Always check before accessing its properties.

## Check Amendment Status

```python
if drs.is_amendment:
    print(f"Amendment No. {drs.amendment_number}")
```

`amendment_number` is extracted from the cover page text (e.g., "Amendment No. 2"). It can be `None` if the filing is an amendment but the number is not parseable.

## Quick Reference

### Properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `form` | `str` | Filing form code | `"DRS"` |
| `underlying_form` | `str` | Detected form type | `"S-1"` |
| `company` | `str` | Company name | `"Acme Corp"` |
| `company_name` | `str` | Alias for `company` | `"Acme Corp"` |
| `filing_date` | `date` | Date filed | `2023-10-15` |
| `accession_number` | `str` | EDGAR accession number | `"0001193125-23-276353"` |
| `is_amendment` | `bool` | True if DRS/A | `False` |
| `amendment_number` | `int \| None` | Amendment sequence number | `2` |
| `registration_number` | `str \| None` | 377-series reg number | `"377-01234"` |
| `underlying_object` | `RegistrationS1 \| RegistrationS3 \| None` | Full data object for the underlying form | — |
| `filing` | `Filing` | Source `Filing` object | — |

### Underlying Form Coverage

| Detected Form | `underlying_object` type |
|---------------|--------------------------|
| S-1, F-1 | `RegistrationS1` |
| S-3 | `RegistrationS3` |
| S-4, F-4, 20-F, 40-F, Form 10 | `None` |
| Unknown | `None` |

## Things to Know

`underlying_form` is detected from the first 8,000 characters of the cover page HTML. Detection succeeds for the common forms; unusual formatting may yield `"Unknown"`.

The `registration_number` has a `377-` prefix, which distinguishes DRS submissions from standard registration numbers. It may be `None` for early submissions before the SEC assigns a number.

Once a company proceeds with a public offering, they file the same content as a public S-1 or F-1. The DRS and the subsequent public filing are separate EDGAR filings.

## Related

- [S-1 Registration Statement](registration-s1-data-object-guide.md) — the public counterpart to a DRS wrapping an S-1
- [S-3 Registration Statement](registration-s3-data-object-guide.md) — shelf registration data object

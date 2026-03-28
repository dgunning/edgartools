---
description: Parse SEC EFFECT filings with Python. Access registration effectiveness dates and navigate to source filings using edgartools.
---

# EFFECT: Parse SEC Registration Effectiveness Notices with Python

When the SEC declares a registration statement effective, it issues an EFFECT filing. EdgarTools parses these into `Effect` objects, giving you the effective date and a direct path back to the original registration filing.

```python
from edgar import find

filing = find("0000038723-22-000118")  # an EFFECT filing
effect = filing.obj()                 # Effect

effect.effective_date          # "2022-11-22"
effect.source_submission_type  # "POS AM"
effect.entity                  # "1st FRANKLIN FINANCIAL CORP"
```

## Navigate to the Source Filing

The main use for `Effect` is finding the filing that was declared effective. `get_source_filing()` returns the original `Filing` object by accession number lookup, or by file number and form type if no accession number is present.

```python
source = effect.get_source_filing()  # Filing object for the POS AM / S-1 / etc.
source.form                          # "POS AM"
source.filing_date                   # date the original was filed
```

From there you can call `source.obj()`, access documents, or parse XBRL data — the full filing API is available.

## Get a Summary

`summary()` returns a one-row DataFrame with the key facts:

```python
effect.summary()
# entity                           cik  source  live  effective
# 1st FRANKLIN FINANCIAL CORP  38723  POS AM  True  2022-11-22
```

Columns: `cik`, `entity`, `source` (the source form type), `live` (True for production submissions), `effective` (the effectiveness date string).

## Quick Reference

### Properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `submission_type` | `str` | Always `"EFFECT"` | `"EFFECT"` |
| `effective_date` | `str` | Date the registration was declared effective | `"2024-06-15"` |
| `cik` | `str` | CIK of the registrant | `"0000038723"` |
| `entity` | `str` | Entity name | `"ACME CORP"` |
| `source_submission_type` | `str` | Form type that was made effective | `"S-1"`, `"POS AM"`, `"S-3"` |
| `source_accession_no` | `str \| None` | Accession number of the source filing | `"0001234567-24-000001"` |
| `is_live` | `bool` | `True` for live submissions, `False` for test | `True` |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_source_filing()` | `Filing \| None` | Navigate to the filing that was declared effective |
| `summary()` | `pd.DataFrame` | One-row summary: cik, entity, source, live, effective |

## Things to Know

`source_accession_no` is `None` on some older EFFECT filings. In that case, `get_source_filing()` falls back to a file number + form type search.

The `effective_date` is returned as a string in `YYYY-MM-DD` format, not a `datetime` object.

## Related

- [Working with Filings](../guides/working-with-filing.md)
- [Registration S-3 Data Object Guide](../guides/registration-s3-data-object-guide.md)

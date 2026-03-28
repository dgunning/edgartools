---
description: Parse SEC S-1 registration statements with Python. Extract offering type, cover page, fee tables, and navigate to 424B takedowns for IPOs and resale registrations using edgartools.
---

# S-1 Registration Statement: Parse SEC Filings with Python

S-1 filings are full registration statements required any time a company wants to offer securities to the public without the abbreviated incorporation-by-reference that S-3 shelves allow. EdgarTools parses S-1, S-1/A, F-1, and F-1/A filings into a `RegistrationS1` object, automatically classifying the offering type and extracting the cover page, fee table, and key financial tables.

```python
from edgar import find

filing = find("0001213900-26-015175")   # Solidion Technology S-1 (IPO)
s1 = filing.obj()                       # RegistrationS1
s1
```

![S-1 registration statement parsed with Python edgartools showing cover page and fee table](../images/registration-s1-overview.webp)

You can also reach an S-1 through a company search:

```python
from edgar import Company

company = Company("WOLF")                        # Wolfspeed
filing = company.get_filings(form="S-1")[0]
s1 = filing.obj()                                # RegistrationS1
```

---

## Classify the Offering Type

The first thing most analysts want to know is whether the filing is an IPO, a SPAC, a resale registration, or something else. The `offering_type` property answers that.

```python
s1.offering_type              # S1OfferingType.IPO
s1.offering_type.display_name # "Initial Public Offering"
```

| Value | Display Name | Typical use |
|-------|-------------|-------------|
| `IPO` | Initial Public Offering | First-time listing; no prior public float |
| `SPAC` | SPAC IPO | Blank check company; trust account language |
| `RESALE` | Resale Registration | Selling stockholders; company receives no proceeds |
| `DEBT` | Debt Offering | Debt securities only |
| `FOLLOW_ON` | Follow-On Offering | Secondary offering by already-public company |
| `UNKNOWN` | Unknown | Classification could not determine type |

```python
# SPAC example
filing = find("0001213900-26-025801")   # BEST SPAC II
s1 = filing.obj()
s1.offering_type              # S1OfferingType.SPAC
s1.total_offering             # 129375000.0

# Resale example
filing = find("0001193125-26-098748")   # Wolfspeed resale registration
s1 = filing.obj()
s1.offering_type              # S1OfferingType.RESALE
```

---

## Read the Cover Page

The cover page captures who is filing, how the SEC classifies them, and which registration rules apply. This is the filer's self-reported profile at the time of filing.

```python
cp = s1.cover_page                          # S1CoverPage

cp.company_name                             # "SOLIDION TECHNOLOGY INC."
cp.registration_number                      # "333-293402"
cp.state_of_incorporation                   # "Delaware"
cp.sic_code                                 # "3359"
cp.ein                                      # "87-1993879"

# Filer category checkboxes
cp.is_large_accelerated_filer               # False
cp.is_non_accelerated_filer                 # True
cp.is_smaller_reporting_company             # True
cp.is_emerging_growth_company               # True

# Rule checkboxes
cp.is_rule_415                              # True if delayed/continuous offering
cp.is_rule_462b                             # True if Rule 462(b) amendment

# Extraction quality indicator
cp.confidence                               # "high", "medium", or "low"
```

Shortcut properties on the `RegistrationS1` object delegate to the cover page:

```python
s1.registration_number        # same as s1.cover_page.registration_number
s1.state_of_incorporation     # same as s1.cover_page.state_of_incorporation
s1.sic_code                   # same as s1.cover_page.sic_code
s1.ein                        # same as s1.cover_page.ein
s1.is_amendment               # True when form contains "/A"
```

The `confidence` score reflects how many fields were successfully extracted: `"high"` (4+ fields), `"medium"` (2-3 fields), `"low"` (0-1 fields). Older filings with non-standard layouts tend to score lower.

---

## Read the Fee Table

Every S-1 filed since 2022 includes Exhibit 107 (EX-FILING FEES) stating the total offering size and the SEC fee owed. EdgarTools extracts this from the exhibit automatically.

```python
s1.total_offering    # 14490000.0   (total registered amount in dollars)
s1.net_fee           # 2001.07      (SEC registration fee owed)

# Per-security breakdown
for sec in s1.securities:
    print(sec.security_type, sec.security_title, sec.max_aggregate_amount)
```

For more detail, access the fee table object directly:

```python
ft = s1.fee_table                   # RegistrationFeeTable | None
ft.total_offering_amount            # 14490000.0
ft.net_fee_due                      # 2001.07
len(ft.securities)                  # 3 (one row per registered security class)
```

`fee_table` is `None` for filings before the 2022 rule change requiring Exhibit 107.

---

## Access IPO-Specific Tables

For IPO registrations, the S-1 body includes dilution and capitalization tables that summarize the company's pre- and post-offering financial position.

```python
# Dilution table — shows NAV per share before and after offering
dilution = s1.dilution              # DilutionData | None
if dilution:
    print(dilution.net_tangible_book_value_per_share_after_offering)

# Capitalization table — total equity before and after
cap = s1.capitalization             # CapitalizationData | None
if cap:
    print(cap.total_stockholders_equity_actual)
    print(cap.total_stockholders_equity_as_adjusted)
```

These are parsed lazily on first access and cached. They return `None` when the filing does not contain the relevant tables (common for resale and debt registrations).

---

## Access Resale Registration Data

For resale registrations, the S-1 identifies the selling stockholders who will offer shares. The company typically receives no proceeds.

```python
sellers = s1.selling_stockholders   # SellingStockholdersData | None
if sellers:
    for holder in sellers.holders:
        print(holder.name, holder.shares_offered)
```

---

## Get Underwriting Information

When the offering includes a bank or broker-dealer acting as underwriter, the underwriting section names them.

```python
uw = s1.underwriting                # UnderwritingInfo | None
if uw:
    for entry in uw.underwriters:
        print(entry.name)
```

---

## Check Effectiveness and Navigate to Takedowns

After filing, the SEC reviews the S-1 and issues an EFFECT notice when it is declared effective. From that point forward the company can sell shares. If they file follow-on 424B prospectuses under the same registration number, you can reach those from the `RegistrationS1` object.

```python
s1.is_effective       # True / False
s1.effective_date     # "2024-08-15" (date of EFFECT filing) or None

# 424B takedowns under this registration
takedowns = s1.takedowns        # Filings | None
if takedowns:
    for filing in takedowns:
        print(filing.form, filing.filing_date)
        prospectus = filing.obj()   # Prospectus424B
```

To see every filing under the same registration file number (including the EFFECT notice and any amendments):

```python
all_filings = s1.related_filings    # Filings | None
```

Both `.takedowns` and `.related_filings` require a network call and are cached after first access.

---

## Get AI-Friendly Context

`.to_context()` returns a structured text summary suitable for language model prompts:

```python
print(s1.to_context())
# S-1 REGISTRATION STATEMENT: SOLIDION TECHNOLOGY INC. (S-1)
#
# Filed: 2026-02-27
# Offering Type: Initial Public Offering
# Registration No.: 333-293402
# State: Delaware
# SIC Code: 3359
# ...

print(s1.to_context(detail='full'))     # includes available properties/actions
print(s1.to_context(detail='minimal'))  # filing header only
```

---

## Supported Form Variants

| Form | Description |
|------|-------------|
| `S-1` | Full registration statement (domestic companies) |
| `S-1/A` | Amendment to an S-1 |
| `F-1` | Full registration statement (foreign private issuers) |
| `F-1/A` | Amendment to an F-1 |

All four are dispatched automatically by `filing.obj()`. F-1 forms follow the same structure as S-1 but are filed by foreign private issuers. The `RegistrationS1` class handles all four.

---

## Quick Reference

### RegistrationS1 Properties

| Property | Type | Description |
|----------|------|-------------|
| `form` | `str` | Form type (`"S-1"`, `"S-1/A"`, `"F-1"`, `"F-1/A"`) |
| `company` | `str` | Company name from filing metadata |
| `filing_date` | `date` | Date the filing was submitted |
| `accession_number` | `str` | SEC accession number |
| `offering_type` | `S1OfferingType` | Classification enum |
| `cover_page` | `S1CoverPage` | Extracted cover page fields |
| `fee_table` | `RegistrationFeeTable \| None` | Parsed Exhibit 107 |
| `total_offering` | `float \| None` | Total registered offering amount in dollars |
| `net_fee` | `float \| None` | Net SEC registration fee owed |
| `securities` | `list` | Per-security rows from fee table |
| `registration_number` | `str \| None` | File number (`"333-XXXXXX"`) |
| `state_of_incorporation` | `str \| None` | State of incorporation |
| `sic_code` | `str \| None` | SIC industry code |
| `ein` | `str \| None` | Employer identification number |
| `is_amendment` | `bool` | True when form contains `/A` |
| `is_effective` | `bool` | True when an EFFECT filing exists |

### RegistrationS1 Cached Properties

| Property | Type | Description |
|----------|------|-------------|
| `dilution` | `DilutionData \| None` | Dilution table (IPO registrations) |
| `capitalization` | `CapitalizationData \| None` | Capitalization table (IPO registrations) |
| `selling_stockholders` | `SellingStockholdersData \| None` | Selling stockholder table (resale registrations) |
| `underwriting` | `UnderwritingInfo \| None` | Underwriter list |
| `takedowns` | `Filings \| None` | 424B filings under this registration (network call) |
| `related_filings` | `Filings \| None` | All filings under this file number (network call) |
| `effective_date` | `str \| None` | Date of EFFECT filing (network call) |

### RegistrationS1 Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_context(detail)` | `str` | AI-formatted text (`'minimal'`, `'standard'`, `'full'`) |

### S1CoverPage Fields

| Property | Type | Description |
|----------|------|-------------|
| `company_name` | `str` | Company name |
| `registration_number` | `str \| None` | SEC file number |
| `state_of_incorporation` | `str \| None` | State of incorporation |
| `sic_code` | `str \| None` | SIC code |
| `ein` | `str \| None` | EIN |
| `is_large_accelerated_filer` | `bool \| None` | Checkbox state |
| `is_accelerated_filer` | `bool \| None` | Checkbox state |
| `is_non_accelerated_filer` | `bool \| None` | Checkbox state |
| `is_smaller_reporting_company` | `bool \| None` | Checkbox state |
| `is_emerging_growth_company` | `bool \| None` | Checkbox state |
| `is_rule_415` | `bool` | Delayed/continuous offering |
| `is_rule_462b` | `bool` | Rule 462(b) amendment |
| `is_rule_462e` | `bool` | Rule 462(e) |
| `security_description` | `str \| None` | Description of securities from cover text |
| `confidence` | `str` | Extraction confidence (`"low"`, `"medium"`, `"high"`) |

### S1OfferingType Values

| Enum Value | display_name | When |
|------------|-------------|------|
| `IPO` | Initial Public Offering | No prior public float; first listing |
| `SPAC` | SPAC IPO | Blank check company; trust account language |
| `RESALE` | Resale Registration | Selling stockholders; company receives no proceeds |
| `DEBT` | Debt Offering | Debt securities only |
| `FOLLOW_ON` | Follow-On Offering | Already-public company issuing additional shares |
| `UNKNOWN` | Unknown | Classification failed |

---

## Things to Know

Unlike S-3 filings, S-1s contain complete financial statements rather than incorporating them by reference from prior 10-K/10-Q filings. This makes them significantly larger documents (often 200KB to several MB).

The dilution, capitalization, selling stockholders, and underwriting properties are all parsed lazily on first access. Each makes one pass through the filing's HTML to extract tables. For large filings this can take a few seconds.

`fee_table` is `None` for S-1 filings submitted before the November 2022 rule change that required Exhibit 107. Older filings need the fee amount extracted from the cover page text, which the current extractor does not attempt.

The `confidence` field on `cover_page` reflects how many structured fields were found. A score of `"low"` does not mean the filing is invalid; it means the cover page HTML used a non-standard layout that the extractor could not fully parse.

Foreign private issuer F-1 filings use different country-of-incorporation conventions. The `state_of_incorporation` field may contain a full country name (e.g., `"British Virgin Islands"`) rather than a US state.

---

## Related

- [S-3 Shelf Registrations](registration-s3-data-object-guide.md) -- the abbreviated shelf form used by seasoned issuers
- [Prospectus Supplements (424B)](prospectus424b-data-object-guide.md) -- parse the 424B takedowns that follow a registration
- [Working with Filings](working-with-filing.md) -- how to navigate from a filing to its data object
- [Finding Companies](finding-companies.md) -- how to look up companies by ticker, CIK, or name

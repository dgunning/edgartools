# ThirteenF Data Object Guide

Form 13F-HR is a quarterly holdings report filed by institutional investment managers with over $100 million in qualifying assets under management. It discloses equity holdings and is due within 45 days of quarter-end. This guide details all data available from the `ThirteenF` class for building views.

---

## Overview

| Property | Type | Description |
|----------|------|-------------|
| Class Name | `ThirteenF` | |
| Forms Handled | `13F-HR`, `13F-HR/A`, `13F-NT`, `13F-NT/A`, `13F-CTR`, `13F-CTR/A` | |
| Module | `edgar.thirteenf` | |
| Source Data | XML primary document + XML/TXT information table | |

### Form Type Descriptions

| Form | Description |
|------|-------------|
| `13F-HR` | Holdings Report - full quarterly disclosure of equity holdings |
| `13F-HR/A` | Amendment to Holdings Report |
| `13F-NT` | Notice - notification that holdings report will be filed later |
| `13F-NT/A` | Amendment to Notice |
| `13F-CTR` | Combination Report - filed by managers with sub-managers |
| `13F-CTR/A` | Amendment to Combination Report |

---

## Basic Metadata

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `form` | `str` | Form type | `"13F-HR"` |
| `filing_date` | `str` | Date filed with SEC | `"2024-02-14"` |
| `report_period` | `str` | Quarter-end date (YYYY-MM-DD) | `"2023-12-31"` |
| `accession_number` | `str` | SEC accession number | `"0001140361-24-005678"` |

---

## Summary Metrics

High-level portfolio statistics from the cover/summary pages:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `total_value` | `Decimal` | Total portfolio value (thousands $) | `314159265` |
| `total_holdings` | `int` | Number of distinct holdings | `42` |

**Note**: Value is reported in thousands of dollars as per SEC format.

---

## Manager Information

### Management Company (Primary)

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `management_company_name` | `str` | Legal name of investment firm | `"Berkshire Hathaway Inc"` |
| `investment_manager` | `FilingManager` | Full manager object | See FilingManager below |
| `other_managers` | `list[OtherManager]` | Other included managers (multi-manager filings) | See OtherManager below |

### Other Managers (Multi-Manager Filings)

Large institutions often consolidate filings for multiple affiliated managers. The `other_managers` property provides direct access to these:

```python
thirteen_f = filing.obj()
for manager in thirteen_f.other_managers:
    print(f"{manager.name} (CIK: {manager.cik})")
```

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `other_managers` | `list[OtherManager]` | Affiliated entities in consolidated filing | `[OtherManager(...), ...]` |

This is commonly seen in filings from institutions like State Street, Bank of America, and other large financial holding companies that report holdings for multiple subsidiary managers.

### Filing Signer

The person who signs the 13F (typically an administrative officer, not the portfolio manager):

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `filing_signer_name` | `str` | Name of signer | `"Marc D. Hamburg"` |
| `filing_signer_title` | `str` | Signer's title | `"Senior Vice President"` |
| `signer` | `str` | Alias for filing_signer_name | `"Marc D. Hamburg"` |

### FilingManager Object

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Manager name |
| `address` | `Address` | Business address |

### Address Object

| Property | Type | Description |
|----------|------|-------------|
| `street1` | `str` | Street line 1 |
| `street2` | `str` | Street line 2 |
| `city` | `str` | City |
| `state_or_country` | `str` | State/country code |
| `zipcode` | `str` | ZIP code |

---

## Holdings Data

### Primary Access: `holdings` Property (Recommended)

The `holdings` property returns an aggregated view with one row per security. This is the recommended view for most users as it matches industry-standard presentation (CNBC, Bloomberg, etc.).

```python
thirteen_f = filing.obj()
holdings_df = thirteen_f.holdings  # pd.DataFrame
```

### Holdings DataFrame Columns

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `Issuer` | `str` | Company name | `"APPLE INC"` |
| `Class` | `str` | Security class | `"COM"` |
| `Cusip` | `str` | CUSIP identifier | `"037833100"` |
| `Ticker` | `str` | Stock ticker (if mapped) | `"AAPL"` |
| `Value` | `int` | Market value (thousands $) | `157500` |
| `SharesPrnAmount` | `int` | Number of shares | `1000000` |
| `Type` | `str` | Shares or Principal | `"Shares"` |
| `PutCall` | `str` | Put/Call indicator | `""` or `"PUT"` or `"CALL"` |
| `SoleVoting` | `int` | Sole voting authority shares | `1000000` |
| `SharedVoting` | `int` | Shared voting authority shares | `0` |
| `NonVoting` | `int` | No voting authority shares | `0` |

### Alternative Access: `infotable` Property

For multi-manager filings, returns disaggregated data with separate rows for each manager's holdings:

```python
infotable_df = thirteen_f.infotable  # pd.DataFrame - disaggregated by manager
```

Additional column in `infotable`:

| Column | Type | Description |
|--------|------|-------------|
| `OtherManager` | `str` | Manager identifier for multi-manager filings |
| `InvestmentDiscretion` | `str` | `"SOLE"`, `"SHARED"`, or `"DFND"` (defined) |

### Comparison

| View | Rows for Berkshire Example | Use Case |
|------|---------------------------|----------|
| `holdings` | 40 (aggregated) | Standard portfolio view |
| `infotable` | 121 (disaggregated) | Multi-manager analysis |

---

## Holdings Availability

Not all 13F forms contain holdings data:

| Method | Returns | Description |
|--------|---------|-------------|
| `has_infotable()` | `bool` | True for 13F-HR forms, False for 13F-NT |

```python
if thirteen_f.has_infotable():
    holdings = thirteen_f.holdings
else:
    # This is a 13F-NT (notice only, no holdings)
    pass
```

---

## Portfolio Manager Information

13F filings do NOT contain individual portfolio manager names. The class provides methods to access curated external data:

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_portfolio_managers()` | `list[dict]` | Known portfolio managers (external data) |
| `get_manager_info_summary()` | `dict` | Comprehensive breakdown of available info |
| `is_filing_signer_likely_portfolio_manager()` | `bool` | Heuristic check on signer role |

### Portfolio Manager Dict Structure

```python
{
    'name': 'Warren Buffett',
    'title': 'Chairman & CEO',
    'status': 'active',
    'source': 'public_records',
    'last_updated': '2024-01-01'
}
```

### Manager Info Summary Structure

```python
{
    'from_13f_filing': {
        'management_company': 'Berkshire Hathaway Inc',
        'filing_signer': 'Marc D. Hamburg',
        'signer_title': 'Senior Vice President',
        'form': '13F-HR',
        'period_of_report': '2023-12-31'
    },
    'external_sources': {
        'portfolio_managers': [...],
        'manager_count': 1
    },
    'limitations': [
        '13F filings do not contain individual portfolio manager names',
        'External manager data may not be current or complete',
        ...
    ]
}
```

---

## Cover Page Information

Available via `primary_form_information.cover_page`:

| Property | Type | Description |
|----------|------|-------------|
| `report_calendar_or_quarter` | `str` | Reporting quarter |
| `report_type` | `str` | Type of report |
| `filing_manager` | `FilingManager` | Primary filing manager |
| `other_managers` | `List[OtherManager]` | Additional managers |

### OtherManager Object

| Property | Type | Description |
|----------|------|-------------|
| `cik` | `str` | Manager's CIK |
| `name` | `str` | Manager's name |
| `file_number` | `str` | SEC file number |
| `sequence_number` | `int` | Manager sequence in consolidated filing |

---

## Summary Page Information

Available via `primary_form_information.summary_page`:

| Property | Type | Description |
|----------|------|-------------|
| `other_included_managers_count` | `int` | Number of other managers in consolidated filing |
| `total_value` | `Decimal` | Total portfolio value (thousands $) |
| `total_holdings` | `int` | Number of holdings |
| `other_managers` | `List[OtherManager]` | Other managers in consolidated filing |

**Note**: The `other_managers` list is parsed from the summary page's `otherManagers2Info` section, which contains the complete manager information for multi-manager filings. Use the top-level `other_managers` property for convenient access.

---

## Signature Information

Available via `primary_form_information.signature`:

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Signer name |
| `title` | `str` | Signer title |
| `phone` | `str` | Contact phone |
| `signature` | `str` | Signature text |
| `city` | `str` | Signer city |
| `state_or_country` | `str` | Signer state/country |
| `date` | `str` | Signature date |

---

## Historical Comparison

Access previous quarter's filing for comparison:

```python
previous = thirteen_f.previous_holding_report()
if previous:
    # Compare holdings between quarters
    current_holdings = thirteen_f.holdings
    previous_holdings = previous.holdings
```

| Method | Returns | Description |
|--------|---------|-------------|
| `previous_holding_report()` | `ThirteenF` or `None` | Previous quarter's 13F |

---

## Raw Data Access

For advanced use cases:

| Property | Returns | Description |
|----------|---------|-------------|
| `infotable_xml` | `str` or `None` | Raw XML content (2013+ filings) |
| `infotable_txt` | `str` or `None` | Raw TXT content (pre-2013 filings) |
| `primary_form_information` | `PrimaryDocument13F` or `None` | Parsed cover/summary/signature |

---

## View Design Recommendations

### Primary View Components

1. **Header Section**
   - Management company name (prominent)
   - Form type (13F-HR, 13F-HR/A, etc.)
   - Report period (quarter-end date)
   - Filing date

2. **Summary Cards**
   - Total portfolio value (formatted with $ and commas)
   - Number of holdings
   - Filing signer name and title

3. **Holdings Table** (main content)
   - Sortable by value (default: descending)
   - Columns: Ticker, Issuer, Shares, Value, % of Portfolio
   - Put/Call indicator where applicable
   - Voting authority breakdown (collapsible)

4. **Manager Information Panel**
   - Management company details
   - Filing signer vs. portfolio manager distinction
   - Address information (collapsible)

5. **Historical Comparison** (optional)
   - Quarter-over-quarter changes
   - New positions / Sold positions
   - Increased / Decreased positions

### Data Priority for Display

| Priority | Data | Reason |
|----------|------|--------|
| High | Management company name | Primary identifier |
| High | Holdings table (top positions) | Core disclosure |
| High | Total value, total holdings | Portfolio overview |
| Medium | Report period, filing date | Timing context |
| Medium | Ticker symbols | User-friendly identification |
| Medium | Voting authority breakdown | Governance analysis |
| Low | Filing signer details | Administrative info |
| Low | Address information | Reference data |
| Low | CUSIP numbers | Technical identifier |

### Value Formatting

- All values in 13F are reported in **thousands of dollars**
- Display: `$157,500` for value of 157500 (= $157.5 million)
- Or multiply by 1000 and display: `$157,500,000`

### Holdings Table Suggested Columns

| Column | Width | Alignment | Format |
|--------|-------|-----------|--------|
| Ticker | 60px | Left | Bold if available |
| Issuer | flex | Left | Truncate with tooltip |
| Shares | 120px | Right | Comma-separated |
| Value ($000s) | 120px | Right | `$XXX,XXX` |
| % Portfolio | 80px | Right | `XX.X%` |
| Type | 60px | Center | SH/PRN badge |
| Put/Call | 60px | Center | Badge if present |

### Visual Indicators (Suggested)

| Condition | Visual Treatment |
|-----------|------------------|
| Amendment (`13F-HR/A`) | Yellow "Amendment" badge |
| Notice only (`13F-NT`) | Gray "Notice Only" banner |
| Large position (>5% portfolio) | Highlighted row |
| Put option | Red "PUT" badge |
| Call option | Green "CALL" badge |
| Missing ticker | Gray italic issuer name |

### Put/Call Color Coding

| Type | Color | Meaning |
|------|-------|---------|
| (empty) | None | Standard equity position |
| `PUT` | Red | Put option position |
| `CALL` | Green | Call option position |

---

## Example Data Structure

```python
{
    # Metadata
    "form": "13F-HR",
    "filing_date": "2024-02-14",
    "report_period": "2023-12-31",
    "accession_number": "0001140361-24-005678",

    # Summary
    "total_value": 314159265,  # In thousands ($314.2 billion)
    "total_holdings": 42,

    # Manager info
    "management_company_name": "Berkshire Hathaway Inc",
    "filing_signer_name": "Marc D. Hamburg",
    "filing_signer_title": "Senior Vice President",

    "investment_manager": {
        "name": "Berkshire Hathaway Inc",
        "address": {
            "street1": "3555 Farnam Street",
            "city": "Omaha",
            "state_or_country": "NE",
            "zipcode": "68131"
        }
    },

    # Other managers (for multi-manager filings like State Street, BofA)
    "other_managers": [
        {
            "cik": "0001102113",
            "name": "BANK OF AMERICA NA",
            "file_number": "028-12456",
            "sequence_number": 1
        }
        # ... more managers for consolidated filings
    ],

    # Holdings (aggregated view)
    "holdings": [
        {
            "Issuer": "APPLE INC",
            "Class": "COM",
            "Cusip": "037833100",
            "Ticker": "AAPL",
            "Value": 157500000,  # $157.5 billion (in thousands)
            "SharesPrnAmount": 905560000,
            "Type": "Shares",
            "PutCall": "",
            "SoleVoting": 905560000,
            "SharedVoting": 0,
            "NonVoting": 0
        },
        {
            "Issuer": "BANK OF AMER CORP",
            "Class": "COM",
            "Cusip": "060505104",
            "Ticker": "BAC",
            "Value": 34800000,
            "SharesPrnAmount": 1032852006,
            "Type": "Shares",
            "PutCall": "",
            "SoleVoting": 1032852006,
            "SharedVoting": 0,
            "NonVoting": 0
        }
        // ... more holdings
    ],

    # Portfolio managers (external data)
    "portfolio_managers": [
        {
            "name": "Warren Buffett",
            "title": "Chairman & CEO",
            "status": "active",
            "source": "public_records"
        }
    ],

    # Flags
    "has_infotable": True,
    "is_amendment": False
}
```

---

## Notes for Implementation

1. **Value Units**: All monetary values in 13F filings are in **thousands of dollars**. Multiply by 1000 for actual dollar amounts, or clearly label as "($000s)".

2. **Ticker Mapping**: Not all CUSIPs map to tickers. The `Ticker` column may be empty/null for some holdings (delisted, private, or unmapped securities).

3. **Form Types Matter**:
   - `13F-HR` / `13F-HR/A`: Full holdings data available
   - `13F-NT` / `13F-NT/A`: Notice only, no holdings (`has_infotable()` returns False)
   - `13F-CTR`: Combination report for managers with sub-managers

4. **Historical Data**: Pre-2013 filings use TXT format instead of XML. The class handles both transparently, but some data may be less structured.

5. **Multi-Manager Filings**: Large institutions (State Street, Bank of America, etc.) often consolidate filings for multiple affiliated managers. Access the list of other managers via `other_managers` property. Use `holdings` for aggregated view or `infotable` for per-manager breakdown.

6. **Put/Call Options**: The `PutCall` field indicates derivative positions. Empty string means standard equity, "PUT" or "CALL" indicates options.

7. **Voting Authority**: Three types of voting authority are reported:
   - `SoleVoting`: Manager has sole discretion
   - `SharedVoting`: Voting shared with others
   - `NonVoting`: No voting authority

8. **Quarter-End Dates**: Report periods are typically quarter-ends: March 31, June 30, September 30, December 31.

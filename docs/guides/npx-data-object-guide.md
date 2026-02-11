---
description: Access mutual fund proxy voting data from SEC N-PX filings. See how funds voted on shareholder proposals.
---

# N-PX: Parse Mutual Fund Proxy Voting Records

Form N-PX is an annual proxy voting record filed by registered investment companies (mutual funds) to report how they voted on proxy matters for securities they held during the 12-month period ending June 30. This guide details all data available from the `NPX` class for building views.

---

## Overview

| Property | Type | Description |
|----------|------|-------------|
| Class Name | `NPX` | |
| Forms Handled | `N-PX`, `N-PX/A` | |
| Module | `edgar.npx` | |
| Source Data | XML primary document + XML proxy vote table | |

### Form Type Descriptions

| Form | Description |
|------|-------------|
| `N-PX` | Annual proxy voting record report |
| `N-PX/A` | Amendment to proxy voting record report |

---

## Basic Metadata

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `submission_type` | `str` | Form type | `"N-PX"` |
| `period_of_report` | `str` | Reporting period end date | `"2023-06-30"` |
| `report_calendar_year` | `str` | Calendar year of report | `"2023"` |
| `is_amendment` | `bool` | Whether this is an amendment | `False` |
| `amendment_no` | `str` | Amendment number if applicable | `"1"` |
| `amendment_type` | `str` | Type of amendment | `None` |

---

## Fund Information

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `fund_name` | `str` | Name of the reporting fund | `"Vanguard Index Funds"` |
| `cik` | `str` | Central Index Key | `"0000102909"` |
| `report_type` | `str` | Type of report | `"FUND VOTING REPORT"` |
| `investment_company_type` | `str` | Investment company type | `"N-1A"` |
| `year_or_quarter` | `str` | Year or quarter indicator | `"YEAR"` |
| `series_count` | `str` | Number of series in filing | `"5"` |

### Report Types

| Type | Description |
|------|-------------|
| `FUND VOTING REPORT` | Standard fund proxy voting report |
| `MANAGER VOTING REPORT` | Investment manager voting report |

---

## Regulatory Identifiers

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `lei_number` | `str` | Legal Entity Identifier | `"549300QSHYB96X84H026"` |
| `crd_number` | `str` | Central Registration Depository number | `"12345"` |
| `filer_sec_file_number` | `str` | SEC file number of filer | `"811-00234"` |
| `npx_file_number` | `str` | N-PX specific file number | `"811-00234"` |

---

## Contact Information

### Fund Address

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `address` | `str` | Formatted full address | `"100 Vanguard Blvd\nMalvern, PA 19355"` |
| `phone_number` | `str` | Fund phone number | `"610-669-1000"` |

### Agent for Service

| Property | Type | Description |
|----------|------|-------------|
| `agent_for_service_name` | `str` | Name of agent for service |
| `agent_for_service_address` | `str` | Formatted agent address |
| `agent_for_service_address_street1` | `str` | Street line 1 |
| `agent_for_service_address_street2` | `str` | Street line 2 |
| `agent_for_service_address_city` | `str` | City |
| `agent_for_service_address_state_country` | `str` | State/country |
| `agent_for_service_address_zip_code` | `str` | ZIP code |

### Contact Person

| Property | Type | Description |
|----------|------|-------------|
| `contact_name` | `str` | Contact person name |
| `contact_phone_number` | `str` | Contact phone number |
| `contact_email_address` | `str` | Contact email address |

---

## Signature Information

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `signer_name` | `str` | Name of person who signed | `"John W. Smith"` |
| `signer_title` | `str` | Title of signer | `"Principal Executive Officer"` |
| `signature_date` | `str` | Date filing was signed | `"2023-08-28"` |
| `tx_printed_signature` | `str` | Printed signature text | `None` |

---

## Proxy Voting Data

### Primary Access: `proxy_votes` Property

The `proxy_votes` property returns a `ProxyVotes` container with all voting records:

```python
npx = filing.obj()
votes = npx.proxy_votes  # ProxyVotes container

# Convert to DataFrame
votes_df = votes.to_dataframe()

# Get vote count
print(f"Total matters voted: {len(votes)}")
```

### ProxyVotes Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dataframe()` | `pd.DataFrame` | All votes as DataFrame |
| `filter_by_issuer(name)` | `ProxyVotes` | Filter by issuer name (case-insensitive partial match) |
| `filter_by_vote(how_voted)` | `ProxyVotes` | Filter by vote type (FOR, AGAINST, ABSTAIN, etc.) |
| `filter_by_category(category)` | `ProxyVotes` | Filter by vote category |
| `against_management()` | `ProxyVotes` | Filter to votes against management recommendation |
| `management_alignment_rate()` | `float` | Rate of alignment with management (0.0 to 1.0) |
| `summary()` | `pd.DataFrame` | Vote counts by vote type |
| `summary_by_category()` | `pd.DataFrame` | Voting patterns by category |

### Filter Examples

```python
# Filter by issuer
apple_votes = npx.proxy_votes.filter_by_issuer("APPLE")

# Filter by vote type
against_votes = npx.proxy_votes.filter_by_vote("AGAINST")

# Filter by category
climate_votes = npx.proxy_votes.filter_by_category("CLIMATE")

# Find dissenting votes
dissent = npx.proxy_votes.against_management()
print(f"Voted against management {len(dissent)} times")

# Calculate alignment rate
alignment = npx.proxy_votes.management_alignment_rate()
print(f"Aligned with management {alignment:.1%} of the time")
```

### Vote Categories

Common vote categories in N-PX filings:

| Category | Description |
|----------|-------------|
| `DIRECTOR ELECTIONS` | Board of directors elections |
| `SECTION 14A SAY-ON-PAY VOTES` | Executive compensation advisory votes |
| `AUDIT-RELATED` | Auditor ratification and related |
| `COMPENSATION` | Compensation plans and amendments |
| `ENVIRONMENT OR CLIMATE` | Environmental and climate proposals |
| `CORPORATE GOVERNANCE` | Governance structure changes |
| `OTHER` | Other proposal types |

---

## DataFrame Columns

### `proxy_votes.to_dataframe()` Columns

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `issuer_name` | `str` | Company name | `"APPLE INC"` |
| `meeting_date` | `str` | Shareholder meeting date | `"2023-03-10"` |
| `vote_description` | `str` | Description of the matter | `"Elect Director Tim Cook"` |
| `total_shares_voted` | `float` | Total shares voted on matter | `1500000.0` |
| `shares_on_loan` | `float` | Shares on loan | `0.0` |
| `cusip` | `str` | CUSIP identifier | `"037833100"` |
| `isin` | `str` | ISIN identifier | `"US0378331005"` |
| `figi` | `str` | FIGI identifier | `None` |
| `other_vote_description` | `str` | Additional vote description | `None` |
| `vote_source` | `str` | Source of vote | `None` |
| `vote_series` | `str` | Series information | `None` |
| `vote_other_info` | `str` | Additional info | `None` |
| `vote_categories` | `str` | Categories (comma-separated) | `"DIRECTOR ELECTIONS"` |
| `other_managers` | `str` | Other managers (comma-separated) | `None` |
| `how_voted` | `str` | How fund voted | `"FOR"` |
| `shares_voted` | `float` | Shares voted in this record | `1500000.0` |
| `management_recommendation` | `str` | Management's recommendation | `"FOR"` |

### How Voted Values

| Value | Description |
|-------|-------------|
| `FOR` | Voted in favor |
| `AGAINST` | Voted against |
| `ABSTAIN` | Abstained from voting |
| `WITHHOLD` | Withheld vote (typically for directors) |
| `NONE` | Did not vote |

---

## Analysis Summary Methods

### `summary()` - Vote Type Distribution

```python
summary = npx.proxy_votes.summary()
# Returns DataFrame with columns: vote_type, count
```

### `summary_by_category()` - Category Analysis

```python
by_category = npx.proxy_votes.summary_by_category()
```

| Column | Type | Description |
|--------|------|-------------|
| `category` | `str` | Vote category type |
| `total_votes` | `int` | Total vote records |
| `for_votes` | `int` | FOR votes |
| `against_votes` | `int` | AGAINST votes |
| `abstain_votes` | `int` | ABSTAIN votes |
| `other_votes` | `int` | Other vote types |
| `with_management` | `int` | Aligned with management |
| `against_management` | `int` | Dissented from management |

---

## Included Managers

For consolidated filings that include multiple investment managers:

| Property | Type | Description |
|----------|------|-------------|
| `other_included_managers_count` | `str` | Count of other managers |
| `included_managers` | `list[IncludedManager]` | List of included managers |

### IncludedManager Object

| Property | Type | Description |
|----------|------|-------------|
| `serial_no` | `str` | Manager sequence number |
| `name` | `str` | Manager name |
| `form13f_file_number` | `str` | Form 13F file number |
| `sec_file_number` | `str` | SEC file number |

```python
for manager in npx.included_managers:
    print(f"{manager.serial_no}: {manager.name}")
```

---

## Series and Class Information

For funds with multiple series:

| Property | Type | Description |
|----------|------|-------------|
| `series_count` | `str` | Number of series |
| `series_reports` | `list[SeriesReport]` | Series report details |
| `report_series_class_infos` | `list[ReportSeriesClassInfo]` | Series/class mappings |

### SeriesReport Object

| Property | Type | Description |
|----------|------|-------------|
| `id_of_series` | `str` | Series identifier |
| `name_of_series` | `str` | Series name |
| `lei_of_series` | `str` | Series LEI |

### ReportSeriesClassInfo Object

| Property | Type | Description |
|----------|------|-------------|
| `series_id` | `str` | Series identifier |
| `class_infos` | `list[ClassInfo]` | List of class identifiers |

---

## Administrative Fields

| Property | Type | Description |
|----------|------|-------------|
| `confidential_treatment` | `str` | Confidential treatment flag (Y/N) |
| `notice_explanation` | `str` | Notice explanation text |
| `explanatory_choice` | `str` | Explanatory choice flag |
| `registrant_type` | `str` | Registrant type (RMIC, IA, etc.) |
| `live_test_flag` | `str` | Live/Test flag |
| `de_novo_request_choice` | `str` | De novo request choice |
| `conf_denied_expired` | `str` | Confidential treatment denied/expired |

---

## Raw Data Access

| Property | Returns | Description |
|----------|---------|-------------|
| `primary_doc` | `PrimaryDoc` | Raw primary document data |
| `filing` | `Filing` | Source Filing object |

---

## Utility Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dataframe()` | `pd.DataFrame` | Filing metadata as single-row DataFrame |
| `__str__()` | `str` | String representation |
| `__rich__()` | `Rich object` | Rich console rendering |

---

## View Design Recommendations

### Primary View Components

1. **Header Section**
   - Fund name (prominent)
   - Form type (N-PX or N-PX/A)
   - Reporting period
   - Total proxy votes count

2. **Summary Cards**
   - Total matters voted
   - Management alignment rate
   - Vote breakdown (FOR/AGAINST/ABSTAIN)

3. **Voting Table** (main content)
   - Sortable by issuer, date, vote type
   - Columns: Issuer, Meeting Date, Description, How Voted, Shares
   - Category badges
   - Highlight votes against management

4. **Analysis Panels**
   - Vote category breakdown chart
   - Management alignment statistics
   - Top issuers by vote count

5. **Filter Controls**
   - By issuer name
   - By vote type (FOR, AGAINST, etc.)
   - By category
   - By management alignment

### Data Priority for Display

| Priority | Data | Reason |
|----------|------|--------|
| High | Fund name | Primary identifier |
| High | Proxy votes table | Core disclosure |
| High | Total vote count | Volume indicator |
| High | Management alignment rate | Key metric |
| Medium | Period of report | Timing context |
| Medium | Vote categories | Analysis dimension |
| Medium | Against management votes | Stewardship indicator |
| Low | Signer details | Administrative |
| Low | Series information | Reference data |
| Low | Regulatory identifiers | Technical |

### Visual Indicators (Suggested)

| Condition | Visual Treatment |
|-----------|------------------|
| Amendment (`N-PX/A`) | Yellow "Amendment" badge |
| Vote against management | Red highlight |
| High alignment rate (>95%) | Green indicator |
| Climate/ESG category | Green badge |
| Director election | Blue badge |

### Vote Color Coding

| How Voted | Color | Meaning |
|-----------|-------|---------|
| `FOR` | Green | Voted in favor |
| `AGAINST` | Red | Voted against |
| `ABSTAIN` | Gray | Abstained |
| `WITHHOLD` | Orange | Withheld vote |

---

## Example Data Structure

```python
{
    # Metadata
    "submission_type": "N-PX",
    "period_of_report": "2023-06-30",
    "report_calendar_year": "2023",
    "is_amendment": False,

    # Fund info
    "fund_name": "Vanguard Index Funds",
    "cik": "0000102909",
    "report_type": "FUND VOTING REPORT",
    "investment_company_type": "N-1A",

    # Identifiers
    "lei_number": "549300QSHYB96X84H026",
    "npx_file_number": "811-00234",

    # Signature
    "signer_name": "John W. Smith",
    "signer_title": "Principal Executive Officer",
    "signature_date": "2023-08-28",

    # Contact
    "address": "100 Vanguard Blvd\nMalvern, PA 19355",
    "phone_number": "610-669-1000",

    # Included managers (for consolidated filings)
    "other_included_managers_count": "3",
    "included_managers": [
        {
            "serial_no": "1",
            "name": "Vanguard Fixed Income Group",
            "form13f_file_number": "028-12345",
            "sec_file_number": "801-12345"
        }
    ],

    # Proxy votes
    "proxy_votes": [
        {
            "issuer_name": "APPLE INC",
            "cusip": "037833100",
            "meeting_date": "2023-03-10",
            "vote_description": "Elect Director Tim Cook",
            "total_shares_voted": 1500000.0,
            "shares_on_loan": 0.0,
            "vote_categories": ["DIRECTOR ELECTIONS"],
            "vote_records": [
                {
                    "how_voted": "FOR",
                    "shares_voted": 1500000.0,
                    "management_recommendation": "FOR"
                }
            ]
        },
        {
            "issuer_name": "MICROSOFT CORP",
            "cusip": "594918104",
            "meeting_date": "2023-12-07",
            "vote_description": "Report on Climate Lobbying",
            "total_shares_voted": 2000000.0,
            "shares_on_loan": 50000.0,
            "vote_categories": ["ENVIRONMENT OR CLIMATE"],
            "vote_records": [
                {
                    "how_voted": "FOR",
                    "shares_voted": 2000000.0,
                    "management_recommendation": "AGAINST"
                }
            ]
        }
    ],

    # Flags
    "proxy_vote_count": 1500
}
```

---

## Notes for Implementation

1. **Reporting Period**: N-PX filings cover the 12-month period ending June 30. The `period_of_report` will typically be `YYYY-06-30`.

2. **Vote Records**: Each proxy matter can have multiple `vote_records` if the fund voted different ways on behalf of different accounts or series.

3. **Categories**: A single vote can belong to multiple categories. The `vote_categories` column contains comma-separated values.

4. **Security Identifiers**: Not all votes include CUSIP. Some use ISIN or FIGI. Check all three when matching to other data sources.

5. **Management Alignment**: The `management_alignment_rate()` method provides a key stewardship metric. High alignment (>95%) is typical; low alignment may indicate active voting policies.

6. **Against Management Analysis**: Use `against_management()` to identify controversial votes where the fund disagreed with management's recommendation.

7. **Large Filings**: Major fund families (Vanguard, BlackRock, Fidelity) may have thousands of proxy votes. Consider pagination or lazy loading for UI.

8. **Category Analysis**: The `summary_by_category()` method is useful for understanding voting patterns across different proposal types.

9. **Series Complexity**: Large fund families report votes for multiple series (individual funds). The `series_count` and related properties track this.

10. **Data Quality**: Some older filings may have missing fields. Always check for `None` values before displaying.

# Form D Data Object Guide

## Overview

**Form D** is an SEC filing used by companies seeking to raise capital through private placements under Regulation D exemptions. These filings provide critical insights into private fundraising activity, including offering amounts, investor counts, and the parties involved in the capital raise.

The `FormD` class in edgartools parses Form D XML filings into structured Python objects, making it easy to extract and display offering data programmatically.

## Access Pattern

```python
from edgar import Filing

# Get a Form D filing
filing = Filing(form="D", ...)

# Parse into FormD object
form_d = filing.obj()
```

---

## Core Data Structure

### FormD (Top-Level Object)

| Property | Type | Description |
|----------|------|-------------|
| `submission_type` | `str` | Filing type (e.g., "D", "D/A" for amendments) |
| `is_live` | `bool` | Whether this is a live filing (vs. test) |
| `is_new` | `bool` | Whether this is a new offering (vs. amendment) |
| `primary_issuer` | `Issuer` | The company raising capital |
| `related_persons` | `List[Person]` | Executives, directors, and promoters involved |
| `offering_data` | `OfferingData` | Details about the capital raise |
| `signature_block` | `SignatureBlock` | Filing signatures and authorization |

---

## Issuer Information

### Issuer

The `primary_issuer` property contains the company raising capital.

| Property | Type | Description | UI Usage |
|----------|------|-------------|----------|
| `cik` | `str` | SEC Central Index Key | Link to SEC filings |
| `entity_name` | `str` | Legal name of company | Primary display name |
| `entity_type` | `str` | Legal structure (LLC, Corporation, LP, etc.) | Company type badge |
| `primary_address` | `Address` | Business address | Contact/location display |
| `phone_number` | `str` | Contact phone | Contact info |
| `jurisdiction` | `str` | State/country of incorporation | Jurisdiction badge |
| `year_of_incorporation` | `str` | Year company was formed | Age indicator |
| `incorporated_within_5_years` | `bool` | Recently formed flag | Startup indicator |
| `issuer_previous_names` | `List[str]` | Prior company names | Name history |
| `edgar_previous_names` | `List[str]` | Prior names in SEC system | Name history |

### Address

| Property | Type | Description |
|----------|------|-------------|
| `street1` | `str` | Street address line 1 |
| `street2` | `str` | Street address line 2 (optional) |
| `city` | `str` | City |
| `state_or_country` | `str` | State/country code (e.g., "CA", "DE") |
| `state_or_country_description` | `str` | Full state/country name |
| `zipcode` | `str` | Postal code |
| `empty` | `bool` (property) | True if address has no data |

---

## Offering Details

### OfferingData

The `offering_data` property contains the core capital raise information.

| Property | Type | Description | UI Usage |
|----------|------|-------------|----------|
| `industry_group` | `IndustryGroup` | Industry classification | Industry filtering/display |
| `revenue_range` | `str` | Issuer's revenue bracket | Size indicator |
| `federal_exemptions` | `List[str]` | Reg D exemptions claimed (506(b), 506(c), etc.) | Exemption badges |
| `is_new` | `bool` | New offering vs. amendment | Status indicator |
| `date_of_first_sale` | `str` | When sales began | Timeline display |
| `more_than_one_year` | `bool` | Offering duration flag | Duration indicator |
| `is_equity` | `bool` | Equity securities offered | Security type badge |
| `is_pooled_investment` | `bool` | Pooled investment fund type | Fund type indicator |
| `business_combination_transaction` | `BusinessCombinationTransaction` | M&A related flag | Transaction type |
| `minimum_investment` | `str` | Minimum investor commitment | Investment threshold |
| `offering_sales_amounts` | `OfferingSalesAmounts` | Capital raise metrics | Key financial metrics |
| `investors` | `Investors` | Investor information | Investor stats |
| `sales_compensation_recipients` | `List[SalesCompensationRecipient]` | Brokers/finders involved | Sales team display |
| `sales_commission_finders_fees` | `SalesCommissionFindersFees` | Commission amounts | Fee breakdown |
| `use_of_proceeds` | `UseOfProceeds` | How funds will be used | Proceeds allocation |

### OfferingSalesAmounts

**Key metrics for displaying offering progress.**

| Property | Type | Description | UI Usage |
|----------|------|-------------|----------|
| `total_offering_amount` | `object` | Target raise amount | Progress bar max |
| `total_amount_sold` | `object` | Amount already raised | Progress bar current |
| `total_remaining` | `object` | Amount still to raise | Progress bar remaining |
| `clarification_of_response` | `str` | Additional notes | Tooltip/details |

### Investors

| Property | Type | Description | UI Usage |
|----------|------|-------------|----------|
| `has_non_accredited_investors` | `bool` | Non-accredited investors allowed | Investor type badge |
| `total_already_invested` | `object` | Number of investors | Investor count display |

### IndustryGroup

| Property | Type | Description |
|----------|------|-------------|
| `industry_group_type` | `str` | Industry category (Real Estate, Technology, etc.) |
| `investment_fund_info` | `InvestmentFundInfo` | Fund-specific info if applicable |

### InvestmentFundInfo (for pooled funds)

| Property | Type | Description |
|----------|------|-------------|
| `investment_fund_type` | `str` | Fund type (Hedge Fund, Private Equity, Venture Capital, etc.) |
| `is_40_act` | `bool` | Whether fund is registered under Investment Company Act |

---

## Sales Compensation

### SalesCompensationRecipient

**Brokers, finders, and placement agents who receive compensation for the offering.**

| Property | Type | Description | UI Usage |
|----------|------|-------------|----------|
| `name` | `str` | Individual/firm name | Broker name display |
| `crd` | `str` | FINRA CRD number | BrokerCheck link |
| `associated_bd_name` | `str` | Associated broker-dealer name | BD relationship |
| `associated_bd_crd` | `str` | BD's CRD number | BD BrokerCheck link |
| `address` | `Address` | Contact address | Location display |
| `states_of_solicitation` | `List[str]` | States where they can solicit | Geographic scope |

### SalesCommissionFindersFees

| Property | Type | Description |
|----------|------|-------------|
| `sales_commission` | `object` | Total sales commissions paid |
| `finders_fees` | `object` | Total finders fees paid |
| `clarification_of_response` | `str` | Additional notes |

### UseOfProceeds

| Property | Type | Description |
|----------|------|-------------|
| `gross_proceeds_used` | `object` | Amount of proceeds already used |
| `clarification_of_response` | `str` | Description of use |

---

## Related Persons

### Person

**Executives, directors, and promoters associated with the offering.**

| Property | Type | Description |
|----------|------|-------------|
| `first_name` | `str` | Person's first name |
| `last_name` | `str` | Person's last name |
| `address` | `Address` | Contact address |

---

## Signatures

### SignatureBlock

| Property | Type | Description |
|----------|------|-------------|
| `authorized_representative` | `bool` | Whether signer is authorized representative |
| `signatures` | `List[Signature]` | List of signatures on filing |

### Signature

| Property | Type | Description |
|----------|------|-------------|
| `issuer_name` | `str` | Name of issuing entity |
| `signature_name` | `str` | Signature as signed |
| `name_of_signer` | `str` | Signer's printed name |
| `title` | `str` | Signer's title |
| `date` | `str` | Date signed |

---

## Federal Exemptions Reference

Common exemption codes found in `federal_exemptions`:

| Code | Description |
|------|-------------|
| `06b` | Rule 506(b) - Private placement, no general solicitation |
| `06c` | Rule 506(c) - General solicitation allowed, accredited only |
| `04` | Rule 504 - Up to $10M in 12 months |
| `3C` | Section 3(c) - Investment company exemption |
| `3C.1` | Section 3(c)(1) - 100 investor limit |
| `3C.7` | Section 3(c)(7) - Qualified purchasers only |

---

## Industry Group Types

Common values for `industry_group_type`:

- `Real Estate`
- `Banking & Financial Services`
- `Technology`
- `Health Care`
- `Manufacturing`
- `Retailing`
- `Energy`
- `Pooled Investment Fund`
- `Other`

---

## UI Component Recommendations

### Summary Card
Display the key offering metrics prominently:
- Issuer name and entity type
- Total offering amount / amount sold (progress indicator)
- Number of investors
- Minimum investment
- Date of first sale
- Federal exemptions (as badges)

### Issuer Details Panel
- Entity name, type, jurisdiction
- Year of incorporation (with "startup" badge if < 5 years)
- Address and phone
- Previous names (if any)

### Offering Metrics Dashboard
- Offering amount vs. sold (bar chart or progress ring)
- Investor count
- Minimum investment threshold
- Security type (equity badge)
- Duration indicator

### Related Persons Table
- Name column
- Address column (expandable)
- Useful for due diligence

### Sales Compensation Table
- Broker/finder name
- CRD number (link to FINRA BrokerCheck)
- Associated broker-dealer
- States of solicitation (collapsed list with expand)

### Signatures Panel
- Signer name and title
- Date signed
- Authorization status

---

## Common Queries and Filters

For SAAS features, consider enabling filters by:

1. **Offering Size** - Filter by `total_offering_amount` ranges
2. **Industry** - Filter by `industry_group_type`
3. **Exemption Type** - Filter by `federal_exemptions` (506(b) vs 506(c))
4. **Investor Type** - Filter by `has_non_accredited_investors`
5. **Entity Type** - Filter by issuer `entity_type`
6. **Jurisdiction** - Filter by issuer `jurisdiction`
7. **Date Range** - Filter by `date_of_first_sale`
8. **New vs Amendment** - Filter by `is_new`

---

## Data Quality Notes

1. **Monetary amounts** - Stored as strings/objects; may need parsing for numeric operations
2. **Optional fields** - Many fields can be `None`; handle gracefully in UI
3. **States of solicitation** - May contain "All States" as a single value
4. **Previous names** - Filter out literal "None" strings
5. **Date formats** - May vary; normalize for display

---

## Example Data Access

```python
# Get filing and parse
form_d = filing.obj()

# Access issuer info
print(form_d.primary_issuer.entity_name)
print(form_d.primary_issuer.jurisdiction)

# Access offering metrics
print(form_d.offering_data.offering_sales_amounts.total_offering_amount)
print(form_d.offering_data.offering_sales_amounts.total_amount_sold)
print(form_d.offering_data.investors.total_already_invested)

# List exemptions
for exemption in form_d.offering_data.federal_exemptions:
    print(f"Exemption: {exemption}")

# List related persons
for person in form_d.related_persons:
    print(f"{person.first_name} {person.last_name}")

# List sales compensation recipients
for recipient in form_d.offering_data.sales_compensation_recipients:
    print(f"{recipient.name} (CRD: {recipient.crd})")
    print(f"  States: {', '.join(recipient.states_of_solicitation)}")
```
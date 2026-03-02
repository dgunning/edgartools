---
description: Extract proposed sale data from SEC Form 144 filings including seller details, share amounts, and sale dates.
---

# Form 144: Parse Insider Restricted Stock Sale Notices

Form 144 is a notice of proposed sale of restricted securities under SEC Rule 144. Filed by company insiders (officers, directors, 10%+ shareholders) before selling restricted or control securities. This guide details all data available from the `Form144` class for building views.

---

## Overview

| Property | Type | Description |
|----------|------|-------------|
| Class Name | `Form144` | |
| Forms Handled | `144`, `144/A` | |
| Module | `edgar.form144` | |
| Source Data | XML document | |

---

## Basic Metadata

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `filing_date` | `str` | Date filed with SEC | `"2023-04-18"` |
| `is_amendment` | `bool` | Whether this is a 144/A amendment | `False` |

---

## Seller Information

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `person_selling` | `str` | Name of person selling | `"John Smith"` |
| `relationships` | `List[str]` | Relationship(s) to issuer | `["Director", "Officer"]` |
| `address` | `Address` | Seller's address | See Address object |
| `filer` | `Filer` | SEC filer credentials | CIK, entity name, file number |
| `contact` | `Contact` | Contact information | Name, phone, email |

### Address Object

| Property | Type | Description |
|----------|------|-------------|
| `street1` | `str` | Street line 1 |
| `street2` | `str` | Street line 2 |
| `city` | `str` | City |
| `state_or_country` | `str` | State/country code |
| `zipcode` | `str` | ZIP code |

---

## Issuer Information

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `issuer_name` | `str` | Company name | `"Owens Corning"` |
| `issuer_cik` | `str` | Company CIK | `"1370946"` |
| `sec_file_number` | `str` | SEC file number | `"001-36390"` |
| `issuer_contact_phone` | `str` | Issuer contact phone | `"419-248-8000"` |
| `company` | `Company` | Full Company object | Lazy-loaded from CIK |

---

## Securities Information (Proposed Sale)

The core data about the securities to be sold.

### Quick Access Properties (Single Security)

For filings with one security type (most common):

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `units_to_be_sold` | `int` | Total shares to sell | `3000` |
| `market_value` | `float` | Total market value | `300000.0` |
| `security_class` | `str` | Security type | `"Common"` |
| `approx_sale_date` | `str` | Approximate sale date | `"04/18/2023"` |
| `exchange_name` | `str` | Exchange for sale | `"NYSE"` |
| `broker_name` | `str` | Broker executing sale | `"Fidelity Brokerage Services LLC"` |

### Aggregation Properties (Multi-Security)

For filings with multiple security types:

| Property | Type | Description |
|----------|------|-------------|
| `total_units_to_be_sold` | `int` | Sum across all securities |
| `total_market_value` | `float` | Sum across all securities |
| `num_securities` | `int` | Count of security types |
| `is_multi_security` | `bool` | Whether multiple security types |

### Securities Information Holder

Access the full DataFrame via `securities_info`:

```python
form144 = filing.obj()

# Holder object with aggregation methods
holder = form144.securities_info

# Properties
holder.empty                    # bool - is data empty?
holder.total_units_to_be_sold   # int - sum of all units
holder.total_market_value       # float - sum of market values
holder.security_classes         # List[str] - all security types
holder.exchanges                # List[str] - unique exchanges
holder.brokers                  # List[str] - unique brokers
holder.percent_of_outstanding   # float - % of outstanding shares
holder.avg_price_per_unit       # float - market_value / units

# Iteration
for row in holder:
    print(row.security_class, row.units_to_be_sold)

# Raw DataFrame
df = form144.securities_information  # pd.DataFrame
```

### Securities Information DataFrame Columns

| Column | Type | Description |
|--------|------|-------------|
| `security_class` | `str` | Security type (Common, Preferred, etc.) |
| `units_to_be_sold` | `int` | Number of units |
| `market_value` | `float` | Aggregate market value |
| `units_outstanding` | `int` | Total outstanding shares |
| `approx_sale_date` | `str` | Expected sale date (MM/DD/YYYY) |
| `exchange_name` | `str` | Exchange code (NYSE, NASDAQ, etc.) |
| `broker_name` | `str` | Broker/market maker name |

---

## Securities To Be Sold (Acquisition History)

Details about how/when the seller acquired the securities.

### Access

```python
# Holder with aggregation
holder = form144.securities_selling

holder.empty                  # bool
holder.total_amount_acquired  # int - sum of all acquired
holder.acquisition_dates      # List[str] - unique dates
holder.has_gift_transactions  # bool - any gifts?

# Iteration
for row in holder:
    print(row.acquired_date, row.amount_acquired)

# Raw DataFrame
df = form144.securities_to_be_sold
```

### Securities To Be Sold DataFrame Columns

| Column | Type | Description |
|--------|------|-------------|
| `security_class` | `str` | Security type |
| `acquired_date` | `str` | Date acquired (MM/DD/YYYY) |
| `amount_acquired` | `int` | Shares acquired |
| `nature_of_acquisition` | `str` | How acquired (e.g., "Employee Stock Award") |
| `acquired_from` | `str` | Person/entity acquired from |
| `is_gift` | `str` | Gift transaction? ("Y"/"N") |
| `donar_acquired_date` | `str` | If gift, when donor acquired |
| `payment_date` | `str` | Date payment made |
| `nature_of_payment` | `str` | Payment type (e.g., "CASH") |

---

## Securities Sold Past 3 Months

Prior sales within the last 90 days (SEC Rule 144 volume limits).

### Access

```python
# Holder with aggregation
holder = form144.recent_sales

holder.empty                 # bool
holder.total_amount_sold     # int - sum of amounts
holder.total_gross_proceeds  # float - sum of proceeds
holder.sellers               # List[str] - unique seller names

# Iteration
for row in holder:
    print(row.sale_date, row.amount_sold, row.gross_proceeds)

# Raw DataFrame
df = form144.securities_sold_past_3_months

# Flag for no activity
form144.nothing_to_report    # bool - no sales in past 3 months
```

### Aggregation Properties

| Property | Type | Description |
|----------|------|-------------|
| `total_amount_sold_past_3_months` | `int` | Total shares sold recently |
| `total_gross_proceeds_past_3_months` | `float` | Total proceeds |

### Securities Sold Past 3 Months DataFrame Columns

| Column | Type | Description |
|--------|------|-------------|
| `security_class` | `str` | Security type |
| `seller_name` | `str` | Seller name |
| `sale_date` | `str` | Date of sale (MM/DD/YYYY) |
| `amount_sold` | `int` | Shares sold |
| `gross_proceeds` | `float` | Sale proceeds |

---

## Analyst Metrics (Computed Properties)

Pre-computed metrics for investment analysis:

### Percentage Metrics

| Property | Type | Description |
|----------|------|-------------|
| `percent_of_holdings` | `float` | % of outstanding shares being sold |
| `avg_price_per_unit` | `float` | Market value / units to sell |

### Holding Period Analysis

| Property | Type | Description |
|----------|------|-------------|
| `holding_period_days` | `int` or `None` | Avg days held before sale |
| `holding_period_years` | `float` or `None` | Avg years held |

### 10b5-1 Plan Compliance

| Property | Type | Description |
|----------|------|-------------|
| `is_10b5_1_plan` | `bool` | Sale under 10b5-1 trading plan |
| `days_since_plan_adoption` | `int` or `None` | Days from plan adoption to sale |
| `cooling_off_compliant` | `bool` or `None` | 90-day cooling off observed (post-2022 rule) |

### Anomaly Detection Flags

| Property | Type | Description |
|----------|------|-------------|
| `is_large_liquidation` | `bool` | Selling >5% of outstanding |
| `is_short_hold` | `bool` | Holding period <1 year |
| `has_multiple_plans` | `bool` | Multiple 10b5-1 plan dates |
| `anomaly_flags` | `List[str]` | All triggered flags |

**Possible Anomaly Flags:**
- `LARGE_LIQUIDATION` - Selling >5% of outstanding shares
- `SHORT_HOLD` - Held <1 year before selling
- `COOLING_OFF_VIOLATION` - <90 days since 10b5-1 plan adoption
- `MULTIPLE_PLANS` - Multiple 10b5-1 plan adoption dates

---

## Notice Signature

| Property | Type | Description |
|----------|------|-------------|
| `notice_signature.notice_date` | `str` | Date notice signed |
| `notice_signature.signature` | `str` | Signature text |
| `notice_signature.plan_adoption_dates` | `List[str]` | 10b5-1 plan dates |

---

## Remarks

| Property | Type | Description |
|----------|------|-------------|
| `remarks` | `str` | Additional remarks from filer |

---

## Summary Methods

### get_summary()

Returns dict with key filing info:

```python
summary = form144.get_summary()
# Returns:
{
    'person_selling': str,
    'issuer': str,
    'issuer_cik': str,
    'relationships': List[str],
    'num_securities': int,
    'total_units_to_be_sold': int,
    'total_market_value': float,
    'security_classes': List[str],
    'exchanges': List[str],
    'nothing_to_report_past_3_months': bool,
    'total_sold_past_3_months': int,
    'is_amendment': bool,
    'filing_date': str,
}
```

### to_analyst_summary()

Returns dict optimized for investment screening:

```python
summary = form144.to_analyst_summary()
# Returns:
{
    # Identity
    'person_selling': str,
    'issuer': str,
    'issuer_cik': str,
    'relationships': List[str],
    'filing_date': str,

    # Sale metrics
    'units_to_sell': int,
    'market_value': float,
    'percent_of_holdings': float,
    'avg_price_per_unit': float,

    # Timing
    'sale_date': str,
    'holding_period_years': float or None,

    # 10b5-1 Plan
    'is_10b5_1_plan': bool,
    'days_since_plan_adoption': int or None,
    'cooling_off_compliant': bool or None,

    # Recent activity
    'sold_past_3_months': int,
    'proceeds_past_3_months': float,

    # Flags
    'anomaly_flags': List[str],

    # Metadata
    'is_amendment': bool,
    'exchange': str,
    'broker': str,
}
```

### to_dataframe()

Returns DataFrame with one row per security:

```python
df = form144.to_dataframe()
# Columns: security_class, units_to_be_sold, market_value, units_outstanding,
#          approx_sale_date, exchange_name, broker_name, person_selling,
#          issuer, issuer_cik, filing_date, is_amendment
```

---

## View Design Recommendations

### Primary View Components

1. **Header Section**
   - Issuer name + CIK
   - Form type (144 or 144/A amendment)
   - Filing date
   - Amendment indicator if applicable

2. **Seller Panel**
   - Person selling (prominent)
   - Relationship(s) to issuer (badges/tags)
   - Contact info (collapsible)

3. **Sale Summary Card**
   - Units to be sold (large, highlighted)
   - Market value
   - % of holdings
   - Avg price per unit
   - Approximate sale date
   - Exchange / Broker

4. **Compliance Panel**
   - 10b5-1 Plan: Yes/No indicator
   - Days since plan adoption
   - Cooling off status (green checkmark or red warning)
   - Anomaly flags (warning badges)

5. **Securities Information Table**
   - Security class, units, market value, sale date
   - Exchange, broker for each

6. **Acquisition History Table** (collapsible)
   - How/when securities were acquired
   - Gift transaction indicators

7. **Recent Sales Table** (collapsible)
   - Past 3 months activity
   - Or "Nothing to report" message

8. **Signature Footer**
   - Notice date
   - Signature
   - Plan adoption dates

### Data Priority for Display

| Priority | Data | Reason |
|----------|------|--------|
| High | Person selling + relationships | Who is selling |
| High | Units, market value, % holdings | Sale magnitude |
| High | Anomaly flags | Risk indicators |
| Medium | 10b5-1 compliance | Regulatory context |
| Medium | Sale date, exchange, broker | Transaction details |
| Medium | Recent sales (past 3 months) | Volume limit context |
| Low | Acquisition history | Background detail |
| Low | Full address, contact | Administrative |

### Visual Indicators (Suggested)

| Condition | Visual Treatment |
|-----------|------------------|
| `is_amendment` | Yellow "Amendment" badge |
| `is_large_liquidation` | Red warning icon |
| `is_short_hold` | Orange warning icon |
| `cooling_off_compliant == False` | Red "Violation" badge |
| `is_10b5_1_plan` | Blue "10b5-1" badge |
| Large `market_value` (>$1M) | Emphasized styling |

### Anomaly Flags Color Coding

| Flag | Color | Meaning |
|------|-------|---------|
| `LARGE_LIQUIDATION` | Red | >5% of company being sold |
| `SHORT_HOLD` | Orange | Held less than 1 year |
| `COOLING_OFF_VIOLATION` | Red | 10b5-1 rule violation |
| `MULTIPLE_PLANS` | Yellow | Unusual plan activity |

---

## Example Data Structure

```python
{
    # Identity
    "person_selling": "Brian O. Chambers",
    "issuer_name": "Owens Corning",
    "issuer_cik": "1370946",
    "relationships": ["Officer"],
    "filing_date": "2023-04-18",
    "is_amendment": False,

    # Sale summary
    "units_to_be_sold": 3000,
    "market_value": 300000.0,
    "percent_of_holdings": 0.0028,
    "avg_price_per_unit": 100.0,
    "security_class": "Common",
    "approx_sale_date": "04/18/2023",
    "exchange_name": "NYSE",
    "broker_name": "Fidelity Brokerage Services LLC",

    # Compliance
    "is_10b5_1_plan": True,
    "days_since_plan_adoption": 120,
    "cooling_off_compliant": True,
    "holding_period_years": 2.5,

    # Flags
    "anomaly_flags": [],

    # Recent activity
    "nothing_to_report": True,
    "total_sold_past_3_months": 0,
    "total_proceeds_past_3_months": 0.0,

    # Securities info (array)
    "securities_information": [
        {
            "security_class": "Common",
            "units_to_be_sold": 3000,
            "market_value": 300000.0,
            "units_outstanding": 107000000,
            "approx_sale_date": "04/18/2023",
            "exchange_name": "NYSE",
            "broker_name": "Fidelity Brokerage Services LLC"
        }
    ],

    # Acquisition history (array)
    "securities_to_be_sold": [
        {
            "security_class": "Common",
            "acquired_date": "03/15/2021",
            "amount_acquired": 500,
            "nature_of_acquisition": "Employee Stock Award",
            "acquired_from": "Issuer",
            "is_gift": "N"
        }
        // ... more entries
    ],

    # Signature
    "notice_date": "04/17/2023",
    "signature": "/s/ Brian O. Chambers",
    "plan_adoption_dates": ["01/15/2023"]
}
```

---

## Notes for Implementation

1. **XML-Only**: Form 144 data comes exclusively from XML. Filings before ~2015 may not have XML and will return `None` from `filing.obj()`.

2. **Multiple Securities**: Some filings contain multiple security types. Always use aggregation properties (`total_*`) or iterate through `securities_info`.

3. **Placeholder Dates**: SEC forms use `01/01/1933` as placeholder dates. The class filters these out in computed metrics.

4. **Holding Period**: Calculated from acquisition dates to sale date. Returns `None` if dates are invalid or missing.

5. **Cooling Off Rule**: The 90-day requirement took effect in 2022. Earlier filings may show "violations" that weren't violations at the time.

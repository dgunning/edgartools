---
description: Understand how EdgarTools automatically classifies SEC entities by filer type, business category, and regulatory status.
---

# Company Classification

EdgarTools automatically classifies every SEC entity across multiple dimensions: whether it is a domestic or foreign registrant, what kind of business it operates, and its regulatory filing status. These properties are derived from SEC data — SIC codes, state of incorporation, and filing history — so you rarely need to look anything up manually.

## Filer Type: Domestic, Foreign, or Canadian

The `filer_type` property tells you where a company is incorporated. This matters for understanding which annual report form the company files: domestic companies file 10-K, foreign private issuers file 20-F, and Canadian issuers file 40-F.

```python
from edgar import Company

Company("AAPL").filer_type   # 'Domestic'
Company("BABA").filer_type   # 'Foreign'
Company("CNQ").filer_type    # 'Canadian'
```

The `is_foreign` convenience property returns `True` for both Foreign and Canadian filers:

```python
Company("BABA").is_foreign   # True
Company("CNQ").is_foreign    # True
Company("AAPL").is_foreign   # False
```

### How filer type is determined

EdgarTools uses a two-stage approach:

1. **State of incorporation** (preferred): The SEC stores a state or country code for each registered entity. A US state code means domestic; a country code from outside Canada means foreign; Canada codes mean Canadian.

2. **Filing history fallback**: When the state of incorporation is absent, EdgarTools inspects the entity's recent filings. A 40-F signals Canadian; a 20-F or 6-K signals foreign; a 10-K or 10-Q signals domestic. Extended fallbacks cover ADR deposit registrations (`F-6`), foreign registration statements (`F-1`, `F-3`), and domestic-only forms like Regulation Crowdfunding (`C`).

## Business Category

The `business_category` property classifies what kind of entity a company is. This is useful when building screens or analysis pipelines that should behave differently for, say, a bank versus a REIT versus an ordinary operating company.

```python
from edgar import Company

Company("AAPL").business_category   # 'Operating Company'
Company("AGNC").business_category   # 'REIT'
Company("JPM").business_category    # 'Bank'
Company("MET").business_category    # 'Insurance Company'
Company("ARCC").business_category   # 'BDC'
```

### Available categories

| Category | Description |
|---|---|
| `Operating Company` | Standard corporation — the default for most SEC filers |
| `REIT` | Real Estate Investment Trust (SIC 6798) |
| `Bank` | Commercial banks and savings institutions |
| `Insurance Company` | Life, casualty, title, and similar insurers |
| `ETF` | Exchange-traded fund |
| `Mutual Fund` | Open-end registered investment company |
| `Closed-End Fund` | Closed-end registered investment company |
| `BDC` | Business Development Company |
| `Investment Manager` | Asset manager or institutional investment adviser |
| `Holding Company` | Pure holding company (SIC 6719) |
| `SPAC` | Blank check / special purpose acquisition company |
| `Unknown` | Insufficient signals for classification |

### Convenience predicates

Three boolean methods let you check the broad category without pattern-matching strings:

```python
company = Company("AAPL")

company.is_operating_company()      # True
company.is_fund()                   # False
company.is_financial_institution()  # False
```

```python
company = Company("JPM")

company.is_operating_company()      # False
company.is_financial_institution()  # True  (Banks, Insurance, Investment Managers, BDCs)
```

```python
company = Company("SPY")

company.is_fund()                   # True  (ETF, Mutual Fund, Closed-End Fund)
```

### How business category is determined

Classification uses a priority chain:

1. **Definitive SIC codes**: SIC 6798 → REIT; SIC 6770 → SPAC; SIC 6021–6036 → Bank; SIC 6311–6371 → Insurance Company.
2. **Investment company forms**: Primary investment forms (`N-CSR`, `NPORT-P`) trigger fund classification; the name and entity type then distinguish ETF from Mutual Fund from Closed-End Fund.
3. **BDC signals**: Operating entities that file `N-2` forms or whose names contain "Capital Corp".
4. **Investment manager signals**: Entities with SIC 6211 or 6282, or that file `13F-HR`.
5. **Holding company**: SIC 6719.
6. **Default**: Operating Company.

## Filer Category: SEC Accelerated Filer Status

The SEC requires companies above certain public float thresholds to file on accelerated timelines. The `filer_category` property captures this classification.

```python
from edgar import Company

apple = Company("AAPL")

apple.is_large_accelerated_filer    # True  (public float >= $700M)
apple.is_accelerated_filer          # False
apple.is_smaller_reporting_company  # False
apple.is_emerging_growth_company    # False
```

For smaller companies:

```python
# A hypothetical small-cap company
company = Company("BYFC")

company.is_non_accelerated_filer        # True  (public float < $75M)
company.is_smaller_reporting_company    # True  (public float < $250M or revenue < $100M)
```

### Filer status thresholds

| Status | Public Float |
|---|---|
| Large Accelerated Filer | >= $700 million |
| Accelerated Filer | >= $75 million and < $700 million |
| Non-Accelerated Filer | < $75 million |

Two additional qualifications may apply alongside any base status:

- **Smaller Reporting Company (SRC)**: Public float below $250 million, or annual revenue below $100 million with no public float above $700 million. SRCs may use scaled disclosure requirements.
- **Emerging Growth Company (EGC)**: Revenue below $1.235 billion and IPO within the past five years. EGCs may defer certain accounting standards.

For the full `FilerCategory` object with enum access:

```python
from edgar import Company
from edgar.enums import FilerStatus, FilerCategory

category = Company("AAPL").filer_category

category.status                     # FilerStatus.LARGE_ACCELERATED
str(category)                       # 'Large accelerated filer'
category.qualifications             # []
category.is_smaller_reporting_company  # False
```

## Industry: SIC Code and Description

Every SEC registrant is assigned a Standard Industrial Classification (SIC) code. EdgarTools exposes both the code and its human-readable description:

```python
from edgar import Company

apple = Company("AAPL")
apple.sic        # 3571
apple.industry   # 'Electronic Computers'

jpm = Company("JPM")
jpm.sic          # 6022
jpm.industry     # 'State commercial banks-Federal Reserve members & state (non members)'
```

## Entity vs. Individual

Not every SEC filer is a company. Insiders and beneficial owners file ownership forms (Forms 3, 4, 5 and Schedule 13D/G) as individuals. EdgarTools distinguishes these automatically:

```python
from edgar import Company

Company("AAPL").is_company      # True
Company("AAPL").is_individual   # False
```

When you load an entity by CIK and that entity turns out to be a person rather than a company, `is_individual` returns `True`. This typically happens when looking up a CIK obtained from an ownership filing.

Classification uses a nine-signal priority chain: exchange listings, state of incorporation, entity type from SEC data, filing history, EIN, and name keywords. Companies with tickers or a state of incorporation are definitively classified as companies. Filers with only insider ownership forms in their history are classified as individuals.

## Quick Reference

| Property | Type | Returns |
|---|---|---|
| `filer_type` | `str \| None` | `'Domestic'`, `'Foreign'`, `'Canadian'`, or `None` |
| `is_foreign` | `bool` | `True` for Foreign or Canadian registrants |
| `business_category` | `str` | See business category table above |
| `is_operating_company()` | `bool` | `True` for standard operating companies |
| `is_fund()` | `bool` | `True` for ETF, Mutual Fund, or Closed-End Fund |
| `is_financial_institution()` | `bool` | `True` for Bank, Insurance, Investment Manager, or BDC |
| `sic` | `int \| None` | Standard Industrial Classification code |
| `industry` | `str \| None` | SIC description |
| `filer_category` | `FilerCategory` | Full parsed filer category object |
| `is_large_accelerated_filer` | `bool` | Public float >= $700M |
| `is_accelerated_filer` | `bool` | Public float >= $75M and < $700M |
| `is_non_accelerated_filer` | `bool` | Public float < $75M |
| `is_smaller_reporting_company` | `bool` | Qualifies as SRC |
| `is_emerging_growth_company` | `bool` | Qualifies as EGC |
| `is_company` | `bool` | `True` if the filer is a company |
| `is_individual` | `bool` | `True` if the filer is a person |

## Related Guides

- [Finding Companies](finding-companies.md) — Look up companies by ticker, CIK, or name
- [Entity API Guide](entity-api-guide.md) — Filer category details and company icons
- [BDC Guide](bdc-guide.md) — Working with Business Development Companies
- [Fund Entity Guide](fund-entity-guide.md) — ETFs, mutual funds, and closed-end funds

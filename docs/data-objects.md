---
description: Convert any SEC filing into a structured Python object. Supported forms include 10-K, 10-Q, 8-K, 13F, Form 4, DEF 14A, and more.
---

# SEC Filing Data Objects: Parsed Python Objects for Every Form Type

Every SEC filing can be parsed into a structured Python object with one call:

```python
filing.obj()  # returns a TenK, EightK, ThirteenF, etc.
```

Browse the filing types below to find what you need.

---

## Fund Entities

Look up mutual funds and ETFs by ticker, series ID, or CIK. Navigate fund hierarchies and access portfolio reports.

```python
from edgar import Fund, find_funds
fund = Fund("VFINX")                          # Ticker, series ID, or CIK
fund.get_portfolio()                           # Latest portfolio holdings
```

[:octicons-arrow-right-24: Fund Entities guide](guides/fund-entity-guide.md)

---

## Annual & Quarterly Reports (10-K / 10-Q)

Read a company's financials, risk factors, and business description.

```python
tenk = filing.obj()                        # TenK or TenQ
tenk.income_statement                      # formatted financial statement
tenk.risk_factors                          # full section text
tenk.auditor                               # auditor name, PCAOB ID, location
tenk.subsidiaries                          # subsidiaries from Exhibit 21 (10-K only)
tenk.reports                               # XBRL viewer pages (statements, notes, details)
```

[:octicons-arrow-right-24: Annual & Quarterly Reports](concepts/data-objects.md)

---

## Current Events (8-K)

Find out what just happened -- acquisitions, officer changes, earnings releases.

```python
eightk = filing.obj()                      # EightK
eightk.items                               # list of reported event codes
eightk.press_releases                      # attached press releases
```

[:octicons-arrow-right-24: Current Events guide](guides/eightk-data-object-guide.md)

---

## Insider Trades (Form 4)

See who bought or sold shares and at what price.

```python
form4 = filing.obj()                       # Ownership
form4.reporting_owner                      # insider name
form4.transactions                         # buy/sell details with prices
```

[:octicons-arrow-right-24: Insider Trades guide](insider-filings.md)

!!! tip "See it live on edgar.tools"
    Every filing type above — 10-K, 8-K, Form 4, 13F, proxy statements — is also browsable on **edgar.tools** with AI enrichment layered on top:

    - **[Browse Apple's filings, financials, and insider trades →](https://app.edgar.tools/companies/AAPL?utm_source=edgartools-docs&utm_medium=see-live&utm_content=data-objects)**
    - **[Watch filings arrive in real time →](https://app.edgar.tools/filings?utm_source=edgartools-docs&utm_medium=see-live&utm_content=data-objects)**
    - **[Search disclosures across 12 XBRL topics →](https://app.edgar.tools/disclosures?utm_source=edgartools-docs&utm_medium=see-live&utm_content=data-objects)**

    Includes AI-classified 8-K events, insider sentiment analysis, and multi-year disclosure comparison. Free tier available.

---

## Beneficial Ownership (Schedule 13D/G)

Track activist investors and large institutional holders who own 5%+ of a company.

```python
schedule = filing.obj()                    # Schedule13D or Schedule13G
schedule.total_shares                      # aggregate beneficial ownership
schedule.items.item4_purpose_of_transaction  # activist intent (13D only)
```

[:octicons-arrow-right-24: Beneficial Ownership guide](guides/schedule13dg-data-object-guide.md)

---

## Institutional Portfolios (13F)

Explore hedge fund and institutional investor holdings.

```python
thirteenf = filing.obj()                   # ThirteenF
thirteenf.infotable                        # full holdings table
thirteenf.total_value                      # portfolio market value
```

[:octicons-arrow-right-24: Institutional Portfolios guide](guides/thirteenf-data-object-guide.md)

---

## Proxy & Governance (DEF 14A)

Review executive compensation, board nominees, and shareholder proposals.

```python
proxy = filing.obj()                       # ProxyStatement
proxy.executive_compensation               # pay tables
proxy.proposals                            # shareholder vote items
```

[:octicons-arrow-right-24: Proxy & Governance guide](guides/proxystatement-data-object-guide.md)

---

## Private Offerings (Form D)

Track exempt securities offerings and the companies raising capital.

```python
formd = filing.obj()                       # FormD
formd.offering                             # offering details and amounts
formd.recipients                           # related persons
```

[:octicons-arrow-right-24: Private Offerings guide](guides/formd-data-object-guide.md)

---

## Crowdfunding Offerings (Form C)

Monitor crowdfunding campaigns under Regulation CF, including offering terms and issuer financials.

```python
formc = filing.obj()                       # FormC
formc.offering_information                 # target amount, deadline, securities
formc.annual_report_disclosure             # issuer financials (if C-AR)
```

[:octicons-arrow-right-24: Crowdfunding guide](guides/formc-data-object-guide.md)

---

## Insider Sale Notices (Form 144)

Monitor planned insider sales before they happen.

```python
form144 = filing.obj()                     # Form144
form144.proposed_sale_amount               # shares to be sold
form144.securities                         # security details
```

[:octicons-arrow-right-24: Insider Sale Notices guide](guides/form144-data-object-guide.md)

---

## Fund Shareholder Reports (N-CSR / N-CSRS)

Parse certified annual and semiannual shareholder reports with expense ratios, performance data, and share class details.

```python
report = filing.obj()                      # FundShareholderReport
report.expense_data()                      # expense ratios per share class
report.performance_data()                  # annual returns per share class
```

[:octicons-arrow-right-24: Fund Shareholder Reports guide](guides/fundshareholderreport-data-object-guide.md)

---

## Fund Portfolio Holdings (NPORT-P)

Parse monthly mutual fund and ETF portfolio holdings -- every stock, bond, and derivative position.

```python
report = filing.obj()                          # FundReport
report.investment_data()                       # All portfolio positions as DataFrame
```

[:octicons-arrow-right-24: Fund Portfolio Holdings guide](guides/nport-data-object-guide.md)

---

## Money Market Funds (N-MFP)

Parse money market fund filings with portfolio holdings, yields, NAV, and liquidity metrics.

```python
mmf = filing.obj()                             # MoneyMarketFund
mmf.portfolio_data()                           # Securities sorted by market value
```

[:octicons-arrow-right-24: Money Market Funds guide](guides/moneymarketfund-data-object-guide.md)

---

## Fund Census (N-CEN)

Parse annual fund census filings with series data, service providers, and ETF details.

```python
census = filing.obj()                          # FundCensus
census.series_data()                           # Fund series summary
```

[:octicons-arrow-right-24: Fund Census guide](guides/fundcensus-data-object-guide.md)

---

## Fund Voting Records (N-PX)

See how mutual funds voted on shareholder proposals.

```python
npx = filing.obj()                         # FundReport
npx.votes                                  # vote records by proposal
```

[:octicons-arrow-right-24: Fund Voting Records guide](guides/npx-data-object-guide.md)

---

## ABS Distribution Reports (Form 10-D)

Extract structured CMBS loan and property data from asset-backed securities distribution reports.

```python
ten_d = filing.obj()                       # TenD (CMBS only)
ten_d.loans                                # loan-level DataFrame
ten_d.properties                           # property-level DataFrame
ten_d.asset_data.summary()                 # pool statistics
```

[:octicons-arrow-right-24: ABS Distribution Reports guide](guides/tend-data-object-guide.md)

---

## Municipal Advisors (MA-I)

Look up municipal advisor registrations and disciplinary history.

```python
mai = filing.obj()                         # MunicipalAdvisorForm
mai.advisor_name                           # advisor details
```

[:octicons-arrow-right-24: Municipal Advisors guide](guides/mai-data-object-guide.md)

---

## Prospectus Supplements (424B)

Extract offering terms, pricing, underwriting, and dilution from shelf takedown prospectuses.

```python
prospectus = filing.obj()                  # Prospectus424B
deal = prospectus.deal                     # Deal: normalized deal summary
deal.price                                 # per-share price (float)
deal.gross_proceeds                        # total offering amount
deal.discount_rate                         # underwriting fee as fraction of price
```

[:octicons-arrow-right-24: Prospectus Supplements guide](guides/prospectus424b-data-object-guide.md)

---

## Draft Registration Statements (DRS)

Identify the underlying form type of confidential draft registrations before they go public.

```python
drs = filing.obj()                         # DraftRegistrationStatement
drs.underlying_form                        # 'S-1', 'F-1', 'S-4', '20-F', 'Form 10', etc.
drs.underlying_object                      # delegated RegistrationS1 (if S-1/F-1)
drs.registration_number                    # '377-09148'
drs.is_amendment                           # True for DRS/A
```

Filter DRS filings by underlying type:

```python
filings = get_filings(form="DRS")
s1_drafts = [f for f in filings if f.obj().underlying_form == 'S-1']
```

---

## Regulatory Registrations (XML Forms)

Generic access to broker-dealer reports, transfer agent filings, crowdfunding portals, swap entity registrations, and other XML-based regulatory forms.

```python
xf = filing.obj()                          # XmlFiling
xf['brokerDealerName']                     # deep key lookup into XML data
xf.form_data                               # full dict of parsed XML
xf.to_html()                               # SEC's official rendered view
```

| Form | Description |
|------|-------------|
| X-17A-5 | Broker-dealer financial report |
| TA-1 / TA-2 | Transfer agent registration and annual report |
| CFPORTAL | Crowdfunding portal registration |
| SBSE / SBSE-A | Security-based swap entity registration |
| ATS-N-C | Alternative trading system cessation |

---

## How it works

Call `filing.obj()` on any supported filing. EdgarTools detects the form type, parses the raw HTML/XML/XBRL, and returns the right data object. If a filing type isn't supported yet, you'll get an `UnsupportedFilingTypeError`.

```python
from edgar import Company

apple = Company("AAPL")
filing = apple.get_latest_filing("10-K")
tenk = filing.obj()          # returns a TenK with all sections and financials
```

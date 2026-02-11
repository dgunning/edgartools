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

## Annual & Quarterly Reports (10-K / 10-Q)

Read a company's financials, risk factors, and business description.

```python
tenk = filing.obj()                        # TenK or TenQ
tenk.income_statement                      # formatted financial statement
tenk.risk_factors                          # full section text
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

## Insider Sale Notices (Form 144)

Monitor planned insider sales before they happen.

```python
form144 = filing.obj()                     # Form144
form144.proposed_sale_amount               # shares to be sold
form144.securities                         # security details
```

[:octicons-arrow-right-24: Insider Sale Notices guide](guides/form144-data-object-guide.md)

---

## Fund Voting Records (N-PX)

See how mutual funds voted on shareholder proposals.

```python
npx = filing.obj()                         # FundReport
npx.votes                                  # vote records by proposal
```

[:octicons-arrow-right-24: Fund Voting Records guide](guides/npx-data-object-guide.md)

---

## Municipal Advisors (MA-I)

Look up municipal advisor registrations and disciplinary history.

```python
mai = filing.obj()                         # MunicipalAdvisorForm
mai.advisor_name                           # advisor details
```

[:octicons-arrow-right-24: Municipal Advisors guide](guides/mai-data-object-guide.md)

---

## How it works

Call `filing.obj()` on any supported filing. EdgarTools detects the form type, parses the raw HTML/XML/XBRL, and returns the right data object. If a filing type isn't supported yet, you'll get an `UnsupportedFilingTypeError`.

```python
from edgar import Company

apple = Company("AAPL")
filing = apple.get_latest_filing("10-K")
tenk = filing.obj()          # returns a TenK with all sections and financials
```

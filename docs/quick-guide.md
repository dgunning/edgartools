# Cheat Sheet

Common EdgarTools operations at a glance. For a step-by-step introduction, see the [Quick Start](quickstart.md).

### Setup

|                                      | Code                                                  |
|--------------------------------------|-------------------------------------------------------|
| Set your EDGAR identity in Linux/Mac | `export EDGAR_IDENTITY="email@domain.com"` |
| Set your EDGAR identity in Windows   | `set EDGAR_IDENTITY="email@domain.com"`    |
| Set identity in Windows Powershell   | `$env:EDGAR_IDENTITY="email@domain.com"`   |
| Set identity in Python               | `set_identity("email@domain.com")`         |
| Importing the library                | `from edgar import *`                                 |

### Working with a company 🏢

> See also: [Find a Company](guides/finding-companies.md)

|                                          | Code                                                          |
|------------------------------------------|---------------------------------------------------------------|
| 🔍 Get a company by ticker              | `company = Company("AAPL")`                                   |
| 🔍 Get a company by CIK                 | `company = Company("0000320193")`                             |
| 🔎 Find filings by form and ticker      | `find(form="10-K", ticker="AAPL")`                            |
| 📊 Get shares outstanding               | `company.shares_outstanding`                                  |
| 💰 Get public float                     | `company.public_float`                                        |
| 🏭 Get industry                         | `company.industry`                                            |
| 📋 Get company facts                    | `company.get_facts()`                                         |
| 🐼 Get company facts as a DataFrame     | `company.get_facts().to_pandas()`                             |

### Financial statements 💵

> See also: [Financial Statements Guide](guides/financial-data.md)

|                                          | Code                                                          |
|------------------------------------------|---------------------------------------------------------------|
| 📊 Get a company's financials            | `financials = company.get_financials()`                       |
| 📈 Get the income statement              | `financials.income_statement()`                               |
| 🏦 Get the balance sheet                 | `financials.balance_sheet()`                                  |
| 💸 Get the cash flow statement           | `financials.cashflow_statement()`                             |
| 💰 Get revenue                           | `financials.get_revenue()`                                    |
| 💵 Get net income                        | `financials.get_net_income()`                                 |
| 📊 Get operating income                  | `financials.get_operating_income()`                           |
| 🐼 Export statement to DataFrame         | `financials.income_statement().to_dataframe()`                |

### Working with filings 📁

> See also: [Working with Filings](guides/working-with-filing.md) · [Search & Filter](guides/searching-filings.md)

#### 🔍 Getting Filings

|                                        | Code                                            |
|----------------------------------------|-------------------------------------------------|
| 📅 Get filings for the year to date    | `filings = get_filings()`                       |
| 📊 Get only XBRL filings               | `filings = get_filings(index="xbrl")`           |
| 📆 Get filings for a specific year     | `filings = get_filings(2020)`                   |
| 🗓️ Get filings for a specific quarter | `filings = get_filings(2020, 1)`                |
| 📚 Get filings for multiple years      | `filings = get_filings([2020, 2021])`           |
| 📈 Get filings for a range of years    | `filings = get_filings(year=range(2010, 2020))` |
| 📈 Get filings released just now       | `filings = get_latest_filings()`                |

#### 📄 Filtering Filings

|                                     | Code                                                             |
|-------------------------------------|------------------------------------------------------------------|
| 📝 Filter by form type              | `filings.filter(form="10-K")`                                    |
| 📑 Filter by multiple forms         | `filings.filter(form=["10-K", "10-Q"])`                          |
| 🔄 Include form amendments          | `filings.filter(form="10-K", amendments=True)`                   |
| 🏢 Filter by CIK                    | `filings.filter(cik="0000320193")`                               |
| 🏙️ Filter by multiple CIKs         | `filings.filter(cik=["0000320193", "1018724"])`                  |
| 🏷️ Filter by ticker                | `filings.filter(ticker="AAPL")`                                  |
| 🏷️🏷️ Filter by multiple tickers   | `filings.filter(ticker=["AAPL", "MSFT"])`                        |
| 📅 Filter on a specific date        | `filings.filter(date="2020-01-01")`                              |
| 📅↔️📅 Filter between dates         | `filings.filter(date="2020-01-01:2020-03-01")`                   |
| 📅⬅️ Filter before a date           | `filings.filter(date=":2020-03-01")`                             |
| 📅➡️ Filter after a date            | `filings.filter(date="2020-03-01:")`                             |
| 🔀 Combine multiple filters         | `filings.filter(form="10-K", date="2020-01-01:", ticker="AAPL")` |

#### 📊 Viewing and Manipulating Filings

|                                      | Code                  |
|--------------------------------------|-----------------------|
| ⏭️ Show the next page of filings     | `filings.next()`      |
| ⏮️ Show the previous page of filings | `filings.previous()`  |
| 🔝 Get the first n filings           | `filings.head(20)`    |
| 🔚 Get the last n filings            | `filings.tail(20)`    |
| 🕒 Get the latest n filings by date  | `filings.latest(20)`  |
| 🎲 Get a random sample of filings    | `filings.sample(20)`  |
| 🐼 Get filings as a pandas DataFrame | `filings.to_pandas()` |

### Company filings 📂

> See also: [Find a Company](guides/finding-companies.md)

|                                          | Code                                                          |
|------------------------------------------|---------------------------------------------------------------|
| 📁 Get company filings                   | `company.get_filings()`                                       |
| 📝 Get company filings by form           | `company.get_filings(form="10-K")`                            |
| 🕒 Get the latest 10-Q                   | `company.latest("10-Q")`                                      |
| 📑 Get the last 5 10-Qs                  | `company.get_filings(form="10-Q").head(5)`                    |
| 🔢 Get a filing by accession number      | `company.get_filing(accession_number="0000320193-21-000139")` |

### Working with a filing 📄

> See also: [Working with Filings](guides/working-with-filing.md)

#### 🔍 Accessing and Viewing a Filing

|                                     | Code                                                      |
|-------------------------------------|-----------------------------------------------------------|
| 📌 Get a single filing              | `filing = filings[3]`                                     |
| 🔢 Get a filing by accession number | `filing = get_by_accession_number("0000320193-20-34576")` |
| 🏠 Get the filing homepage          | `filing.homepage`                                         |
| 🌐 Open a filing in the browser     | `filing.open()`                                           |
| 🏠 Open homepage in the browser     | `filing.homepage.open()`                                  |
| 💻 View the filing in the terminal  | `filing.view()`                                           |

#### 📊 Extracting Filing Content

|                                     | Code                         |
|-------------------------------------|-----------------------------|
| 🌐 Get the HTML of the filing       | `filing.html()`              |
| 📊 Get the XBRL of the filing       | `filing.xbrl()`              |
| 📝 Get the filing as markdown       | `filing.markdown()`          |
| 📄 Get the full submission text     | `filing.full_text_submission()` |
| 🔍 Preview data object type         | `filing.obj_type`            |
| 🔢 Get and parse filing data object | `filing.obj()`               |
| 📑 Get filing header                | `filing.header`              |

#### 🔎 Searching Inside a Filing

|                             | Code                                    |
|-----------------------------|----------------------------------------|
| 🔍 Search within the filing | `filing.search("query")`                |
| 🔍 Search with regex        | `filing.search("pattern", regex=True)`  |
| 📊 Get filing sections      | `filing.sections()`                     |

#### 📎 Working with Attachments

> See also: [Filing Attachments](guides/filing-attachments.md)

|                               | Code                                 |
|-------------------------------|--------------------------------------|
| 📁 Get all filing attachments | `filing.attachments`                 |
| 📄 Get a single attachment    | `attachment = filing.attachments[0]` |
| 🌐 Open attachment in browser | `attachment.open()`                  |
| ⬇️ Download an attachment     | `content = attachment.download()`    |

### 10-K Annual Report data 📊

> See also: [Working with Filings](guides/working-with-filing.md)

|                                          | Code                                                          |
|------------------------------------------|---------------------------------------------------------------|
| 📄 Get 10-K as data object              | `tenk = company.get_filings(form="10-K").latest().obj()`      |
| 🏢 Get auditor information              | `tenk.auditor`                                                |
| 🏢 Get auditor name                     | `tenk.auditor.name`                                           |
| 🔢 Get PCAOB firm ID                    | `tenk.auditor.firm_id`                                        |
| 🏗️ Get subsidiaries                     | `tenk.subsidiaries`                                           |
| 🐼 Subsidiaries as DataFrame            | `tenk.subsidiaries.to_dataframe()`                            |

### Proxy statements (executive compensation) 💼

> See also: [Proxy Statements Guide](guides/proxystatement-data-object-guide.md)

|                                          | Code                                                          |
|------------------------------------------|---------------------------------------------------------------|
| 📋 Get latest proxy statement            | `proxy = company.get_filings(form="DEF 14A").latest().obj()`  |
| 👤 Get CEO name                          | `proxy.peo_name`                                              |
| 💰 Get CEO total compensation            | `proxy.peo_total_comp`                                        |
| 📊 Get 5-year exec compensation DataFrame| `proxy.executive_compensation`                                |
| 📈 Get pay vs performance DataFrame      | `proxy.pay_vs_performance`                                    |
| 📉 Get company TSR                       | `proxy.total_shareholder_return`                               |
| 📉 Get peer group TSR                    | `proxy.peer_group_tsr`                                        |

!!! tip "Prefer a visual interface?"
    Every operation above also works through **[edgar.tools](https://app.edgar.tools?utm_source=edgartools-docs&utm_medium=see-live&utm_content=cheat-sheet)** — the same SEC data in a web UI, no code required.

    - **[Browse any company's filings and financials →](https://app.edgar.tools/companies/AAPL?utm_source=edgartools-docs&utm_medium=see-live&utm_content=cheat-sheet)**
    - **[Watch filings arrive in real time →](https://app.edgar.tools/filings?utm_source=edgartools-docs&utm_medium=see-live&utm_content=cheat-sheet)**
    - **[Search disclosures across 12 XBRL topics →](https://app.edgar.tools/disclosures?utm_source=edgartools-docs&utm_medium=see-live&utm_content=cheat-sheet)**

    Also includes a REST API (20+ endpoints), hosted MCP server, and data exports. Free tier: 100 API calls/day.

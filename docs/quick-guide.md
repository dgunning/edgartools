# Quick Guide

|                                      | Code                                                  |
|--------------------------------------|-------------------------------------------------------|
| Set your EDGAR identity in Linux/Mac | `export EDGAR_IDENTITY="email@domain.com"` |
| Set your EDGAR identity in Windows   | `set EDGAR_IDENTITY="email@domain.com"`    |
| Set identity in Windows Powershell   | `$env:EDGAR_IDENTITY="email@domain.com"`   |
| Set identity in Python               | `set_identity("email@domain.com")`         |
| Importing the library                | `from edgar import *`                                 |

### Working with filings 📁

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
| 🐼 Get filings as a pandas dataframe | `filings.to_pandas()` |

### Working with a filing 📄

#### 🔍 Accessing and viewing a Filing

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
| 🔢 Get and parse filing data object | `filing.obj()`               |
| 📑 Get filing header                | `filing.header`              |

#### 🔎 Searching inside a Filing

|                             | Code                                    |
|-----------------------------|----------------------------------------|
| 🔍 Search within the filing | `filing.search("query")`                |
| 🔍 Search with regex        | `filing.search("pattern", regex=True)`  |
| 📊 Get filing sections      | `filing.sections()`                     |

#### 📎 Working with Attachments

|                               | Code                                 |
|-------------------------------|--------------------------------------|
| 📁 Get all filing attachments | `filing.attachments`                 |
| 📄 Get a single attachment    | `attachment = filing.attachments[0]` |
| 🌐 Open attachment in browser | `attachment.open()`                  |
| ⬇️ Download an attachment     | `content = attachment.download()`    |

### Working with a company

|                                          | Code                                                          |
|------------------------------------------|---------------------------------------------------------------|
| Get a company by ticker                  | `company = Company("AAPL")`                                   |
| Get a company by CIK                     | `company = Company("0000320193")`                             |
| Get company facts                        | `company.get_facts()`                                         |
| Get company facts as a pandas dataframe  | `company.get_facts().to_pandas()`                             |
| Get company filings                      | `company.get_filings()`                                       |
| Get company filings by form              | `company.get_filings(form="10-K")`                            |
| Get the latest 10-Q                      | `company.latest("10-Q")`                                      |
| Get the last 5 10-Q's                    | `company.get_filings(form="10-Q", 5)`                         |
| Get a company filing by accession_number | `company.get_filing(accession_number="0000320193-21-000139")` |
| Get the company's financials             | `company.get_financials()`                                    |
| Get the company's balance sheet          | `company.financials.balance_sheet()`                          |
| Get the company's income statement       | `company.financials.income_statement()`                       |
| Get the company's cash flow statement    | `company.financials.cashflow_statement()`                     |

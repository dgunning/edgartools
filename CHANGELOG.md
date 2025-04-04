# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.14.5] - 2025-04-04

### Changed

- By default `get_filings` will now return all filings for the year to date


## [3.14.4] - 2025-04-03

### Fixed

- Fix bug when rendering monetary values due to incorrect determination of `is_monetary`
- Fix bug when finding statements when XBRL contains company tags.

### Changed

- Refactored standardization to be more robust
- Add more comprehensive statement resolution. This is related to the bug above
- Add early March cusip ticker mappings

## [3.14.3] - 2025-04-01

### Fixed

- Fix critical bug on April 1st where `get_filings` fails due to an empty index file

## [3.14.2] - 2025-03-31

### Fixed

- Fixed bug where balance sheet parenthetical was incorrectly selected as the consolidated balance sheet
- Fixed bug in insider transaction `Ownership` when the shares contain text like footnotes
- Patch SGML header parsing due to occasional failures due to malformed header
- Fix bug where press release urls were not properly printed
- Ensure raw values are placed in financial statements `to_dataframe`

### Added

- Add Financial Ratios module `edgar.xbrl2.ratios`


## [3.14.1] - 2025-03-27

### Added

- Add `RenderedStatement` class as an intermediate representation of a statement that can be rendered in different formats

### Changed
- Refactored the rendering path to use the `RenderedStatement` class
- Change `to_dataframe` to use the `RenderedStatement` class to render statements to dataframe
- Change the period headers of dataframe to `YYYY-MM-DD` format

## [3.14.0] - 2025-03-26

### Added
- Add transparent httpx caching using hishel

### Changed
- Improve selection and order when querying facts
- Modified the facts query interface to be more user-friendly
- Rename `xbrl.facts_view` property to `xbrl.facts` to make it more intuitive
- Add facts query by statement
- Default max_periods displayed when stitching to the number of statements plus 2



## [3.13.10] - 2025-03-25

## Added
- Implemented display of dimensioned statement

## Changed
- Major refactoring to improve performance of rendering statements
- Increased the default number of periods to 8 when stitching statements

## [3.13.9] - 2025-03-22

### Fixed
- Fixed incorrect statement selection when stitching statements
- Fixed bug when parsing html with `colspan=''`

## [3.13.8] - 2025-03-21

### Fixed
- Added `xbrl2/data` module to the library build so that it shows up deployed library

## [3.13.7] - 2025-03-21

### Fixed
- Fix for missing periods when stitching statements
- Fix for get_optimal_periods not using the `document_period_end_date` when stitching statements

### Added
- Added more standardized concepts


## [3.13.6] - 2025-03-20

### Fixed
- Fixed bug where `show_date_range` was not being applied when rendering statements
- Fix bug where non-quarterly periods were being selected when rendering quarterly statements
- Make Statement selection more robust by checking for statement specific facts in each statement

### Added

- Add filtering by columns in the `FactsQuery.to_dataframe` method
- Add `query` method on the `XBRl` class` to query facts using a `FactsQuery` object


## [3.13.5] - 2025-03-19

### Fixed

- Apply calculation weights to facts based on calculation linkbase information. This addresses the bugs where values shown with the wrong sign

## [3.13.4] - 2025-03-18

### Added

- Add a `facts` module to xbrl2 to provide a more user-friendly interface for querying XBRL facts
- Add `FactQuery` and `FactsView` classes to provide a fluent interface for building fact queries
- Add key filtering capabilities to the Facts API to filter facts by financial statement, period view, text search, value, label, and dimension
- Add `get_available_period_views` and `get_facts_by_period_view` methods to the Facts API to provide predefined period views

### Changed

- Refactored the `edgar.xbrl2.rendering` module for maitainability and readability

## [3.13.3] - 2025-03-15

### Changed

- Separate earnings labels into Basic and Diluted
- Increase data density threshold to 8% to filter out low-density columns
- Add more standardized cash flow concepts
- Format share amounts using their decimal values

## [3.13.2] - 2025-03-14

### Changed

- Implement merging of rows on concepts when stitching statements
- Add `get_optimum_periods` to determine the best periods to use when stitching statements
- Add more standardized concepts
- Add `to_dataframe` to `Statement` to get the data in a consistent way. This replaces `to_pandas`

## [3.13.1] - 2025-03-11

### Added
- Add stitching of statements to produce a single statement across multiple filings
- Add `Statement` class to represent a single statement and `Statements` class to represent multiple statements
- Add `XBRLS` class to combine data from multiple periods with intelligent handling of concept changes
- Add `XBRLS.from_filings` to create a `XBRLS` object from a list of filings
- Add `XBRLS.statements` property to get the statements from the `XBRLS` object

## [3.13.0] - 2025-03-11

### Added

- A preview rewrite of XBRL functionality is added in the `edgar.xbrl2`. The goal is to test this for a few weeks. The `edgar.xbrl` module will be deprecated in the future.

## [3.12.2] - 2025-03-09

### Fixed

- Fixed bug about Live Rich Display when calling `get_by_accession_number` on a same day filing
- Fix parsing of SGML header when the header has double newlines

### Changed

- Improve XBRL instance `query_facts` by dropping empty columns
- For Funds get all filings by looping through the extra pages not just the first page
- Improve numeric handling for Insider Transaction values with footnotes e.g. `7500 [F1]`

## [3.12.1] - 2025-03-02

### Changed
- Add Derivative transactions to the `TransactionSummary` class
- Made panel border around Filings not expand to the full width of the screen

## [3.12.0] - 2025-03-01

### Changed

- Improved the styling of the `Ownership` classes
- Revamped the data structure of the `Ownership` classes to make it easier to access the data
- Changed from getting the header from the filing homepage to getting it from the SGML

### Added

- Add `to_dataframe` method to `Ownership` classes to convert the data to a pandas DataFrame
- Add `InitialOwnershipSummary` class to summarize the initial ownership of insiders in a company
- Add `TransactionSummary` class to summarize the transactions of insiders in a company

## [3.11.5] - 2025-02-19

### Added 

- Add `FilingSGML.from_text()` to create a `FilingSGML` object from text in addition to files and a URL
- Add `num_documents` property to `FilingHeader` to get the number of documents in the SGML

### Changed

- Use filing form types to `Entity.is_individual` to make determining if an entity is an individual or a company more accurate

## [3.11.4] - 2025-02-17

### Fixed

- Fixed bug that caused **Filers**, **SubjectCompany** to be missing when parsing SGML files


## [3.11.3] - 2025-02-14

### Fixed

- Fixed bug when parsing SGML from files with the .nc format

### Changed

- Add `lru_cache` to `find_ticker` function

## Added

- Add function `get_ticker_icon_url` in `reference.tickers` to get the icon url for a ticker


## [3.11.2] - 2025-02-11

### Changed
- Styling improvements to the `Attachments`, `Attachment` and `Filing` classes
- Refactored classes in `filing.sgml` package

### Added
- Add `Filing.reports` property to get the reports directly from a filing if they exist
- Add `Filing.statements` property to get the financial statement documents directly from a filing if they exist


## [3.11.1] - 2025-02-10

### Fixed
- Add code to align date headers over value columns in HTML table
- Optimize the width of column headers and labels to fit more table data on the screen

### Added
- Added filtering by exchange to `Filings` e.g `filings.filter(exchange='NASDAQ')` will return filings for companies listed on the NASDAQ exchange

## [3.11.0] - 2025-02-08

### Changed
- Improved the styling of the `Filing` class

### Fixed
- Fixed issue when passing a string path to `download_file`
- Add **20-F** to the list of filings from which financials can be created
- Handle issue when parsing **NPORT-EX** with no XML attached

## [3.10.6] - 2025-02-07

### Fixed
- Fixed bug when getting related filings when using local storage
- Fixed bug when getting binary content from an attachment

## [3.10.5] - 2025-02-03

### Fixed
- Nested HTML tables are now parsed and displayed correctly

### Changed
- Report attachments for **10-K** filings now display just the primary table in the report


## [3.10.4] - 2025-02-02

### Added
- Added function `strip_ansi` to remove ansi characters from text generated from rich objects

### Changed
- The `rich_to_text` function now uses the output of `repr_rich` and `strip_ansi` to remove ansi characters
- Use `rich_to_text` when getting text of `CurrentReport` 
- Remove borders from panels when rendering text

### Fixed
- The `text()` function of `Attachment` and `Filing` now use an amended version of `rich_to_text` that strips ansi characters

## [3.10.3] - 2025-02-01

### Added
- Add class `CurrentReport` as the data object for the **8-K** and **6-K** forms
- Add class `SixK` as an alias for `CurrentReport`

### Changed
- `EightK` is now an alias for `CurrentReport`
- Plain text files are now read as text rather than html
- For Forms, **3**, **4**, **5** filings the html is downloaded from the filing homepage instead of from the SGML

### Fixed
- Made `pct_value` optional when parsing `FundReports` to avoid a ValidationError

## [3.10.2] - 2025-01-30

### Added
- Add `attachments.get_by_index` to get attachments by index. Indexing starts at 0. There is also `get_by_sequence` that starts at 1

### Changed
- Improved the styling of Attachments using emoticons for different file types
- Add descriptions of reports from the `FilingSummary.xml`
- Add getting attachment text using `attachment.text()`
- Getting attachments using`[]` uses `get_by_sequence` rather than `get_by_index`

### Fixed
- Fixed bug when calling `repr(FilingSGML)`


## [3.10.1] - 2025-01-29

### Added
- Improved rich styling of attachments
- Implement parsing of FilingSummary
- Implement getting content of individual SGML reports
- Implement viewing individual attachments in the SGML report e.g. balance sheet, income statement, etc.

### Changed
- `EDGAR_USE_LOCAL_DATA` now accepts more boolean values `'y', 'yes', 't', 'true', 'on', '1'` or `'n', 'no', 'f', 'false', 'off', '0'` to enable or disable local storage. This is to make it easier to set the environment variable in different environments.

## [3.10.0] - 2025-01-26

### Changed
- This release uses SGML as the primary means of getting attachments and text from SEC filings. This is a significant change from the previous release that used the Filing homepage and access the documents directly. This will make it work better with local storage

### Added
- Implement getting attachments from the SGML text file
- Implement getting html and xml from the SGML attachments
- Add uu_decode function to decode uuencoded files

### Fixed
- Download related filings from the SEC when local storage is enabled but not yet refreshed
- Return empty filings when no filings are found for a company

## [3.9.1] - 2025-01-23

### Fixed
- Fixed bug when downloading data to local storage


## [3.9.0] - 2025-01-20


### Changed
- Refactored the code that used HTTPX client connections to reuse connections. Reusing HTTPX client connections yields about a 20ms savings per request in retrieval in limited tests. (Thanks to paul @ igmo)
- Consolidated the httpx client connection to a single edgartools.httpclient module. This will allow for more control over the client and the ability to pass the client explicitly to functions that need it.
- More logging statements when downloading filings to local storage
- Set throttling when listing the SEC filing bulk files

## [3.8.4] - 2025-01-19

### Added 
- `edgar.company` module to consolidate functions related to companies
- `public_companies` iterator over the public companies in the SEC dcik tickers list

## [3.8.3] - 2025-01-17

### Fixed
- Fix for Form **F-1** files not being detected as HTML

## [3.8.2] - 2025-01-16

### Fixed
- Fix issue with text being inadvertently printed to a notebook
- Allow for filing HTML inside <DOCUMENT> tags to be read as html

## [3.8.1] - 2025-01-15
- Minor fix for incorrect import statement introduced in 3.8.0

## [3.8.0] - 2025-01-15

### Added
- `edgar.storage` module to consolidate functions related to local storage
- Add `edgar.storage.download_filings` to download complete filings to local storage

### Changed
- Moved functions related to local storage to `edgar.storage` module
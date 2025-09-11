# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## Release 4.12.0 - 2025-01-11

### Added
- **Portfolio Manager Enhancement (FEAT-021)**: Major enhancement to 13F filing analysis with curated portfolio manager database
  - `thirteen_f.management_company_name` - Legal name of the investment management company
  - `thirteen_f.filing_signer_name` - Name of the person who signed the filing  
  - `thirteen_f.filing_signer_title` - Title of the filing signer
  - `thirteen_f.get_portfolio_managers()` - Get actual portfolio manager information for investment firms
  - `thirteen_f.get_manager_info_summary()` - Summary of manager data availability
  - **Coverage**: 75 portfolio managers across 40 major investment firms ($26+ trillion AUM)
  - **Accuracy**: CIK-based matching eliminates false positives from name-based searching
  - **Key Firms**: BlackRock, Fidelity, State Street, Citadel, Bridgewater, Renaissance Technologies, and more

- **Enhanced Type System (FEAT-002 to FEAT-005)**: Comprehensive type safety and validation improvements
  - `FormType` enumeration for type-safe form parameter usage
  - `PeriodType` classification for enhanced period filtering  
  - `StatementType` classifications for intelligent statement type detection
  - Enhanced parameter validation with intelligent correction suggestions
  - Comprehensive type hints throughout the API

### Fixed
- **Data Quality**: Fixed test assertions to match actual portfolio manager database structure

### Enhanced
- **Current Period API**: Enhanced Statement object support with improved defaults
- **Documentation**: Comprehensive 13F filings guide, quick reference guides for type enumerations
- **GitHub Integration**: Issue templates for bug reports, feature requests, performance issues, and data quality
- **Development Workflow**: Enhanced feature development workflow with systematic tracking and follow-up planning

## Release 4.11.1 - 2025-09-07

### Fixed
- **Issue #427**: Fixed XBRLS DataFrame column ordering and amendment filtering to ensure consistent and predictable data presentation
- **Issue #429**: Resolved regression in Statement object defaults that was causing test failures after CurrentPeriod API enhancements

### Enhanced
- **CurrentPeriod API improvements**: Added Statement object support with improved defaults for better user experience when accessing current period financial data

## Release 4.11.0 - 2025-09-06

### Added
- **Current Period API (#425)**: New simplified API for accessing the most recent period's financial data without comparative information
  - `xbrl.current_period.balance_sheet()` - Automatic period detection and clean single-period output
  - `xbrl.current_period.income_statement(raw_concepts=True)` - Support for raw XBRL concept names
  - `xbrl.current_period.get_fact()` - Individual fact lookup with optional raw concept access
  - `xbrl.current_period.notes()` - Access to notes sections
  - `current_period.to_dict()` - Dictionary export functionality
- **Filing creation from full SGML text (#413/#414)**: New `Filing.from_sgml_text()` method to create Filing objects directly from complete SGML submission text
- **Dimensional segment data control**: Added `include_dimensions` parameter for controlling display of dimensional segment data in financial statements

### Fixed
- **Inconsistent parameter naming in stitched statements (#403)**: Fixed issue where documentation showed `standard=True` parameter but stitched statement methods only accepted `standardize` parameter. All statement methods now consistently accept the `standard` parameter as documented:
  - `statements.income_statement(standard=True/False)`
  - `statements.balance_sheet(standard=True/False)`
  - `statements.cashflow_statement(standard=True/False)`
  - `statements.statement_of_equity(standard=True/False)`
  - `statements.comprehensive_income(standard=True/False)`
- **Missing parent totals in dimensional breakdowns (#416)**: Fixed Tesla income statement test failure where dimensional display hid parent total lines. Parent totals like "Contract Revenue: $25,500M" now display alongside dimensional children (Auto: $19,878M, Energy: $3,014M)

### Changed
- **Standardized parameter naming**: Removed the deprecated `standardize` parameter from all stitched statement methods and internal APIs in favor of the consistent `standard` parameter
- **API method rename**: Changed `Filing.from_text()` to `Filing.from_sgml_text()` for clarity about expected input format
- **Dimensional display defaults**: Enhanced dimensional segment data is now shown by default (`include_dimensions=True`) with user control to disable if needed

### Enhanced
- **Documentation alignment**: API now matches documentation examples exactly, enabling seamless cross-period concept standardization for Revenue, Gross Profit, Net Income, and other financial metrics
- **Internal API consistency**: Updated XBRLS.get_statement() and StitchedFactsView.get_facts() to use standard parameter throughout the call chain
- **Beginner-friendly current period access**: No complex period filtering required - automatic detection of most recent period with clean DataFrame output
- **Rich dimensional data visibility**: Surfaces product/service segment breakdowns that were always in XBRL but previously hidden
- **Improved stitching compatibility**: Enhanced dimensional display works seamlessly with multi-period stitched statements

### Technical
- **Comprehensive test coverage**: Added regression tests and verification scripts to prevent future parameter naming inconsistencies
- **Current period implementation**: 420 lines of new functionality with 30 comprehensive test cases achieving 100% pass rate
- **Enhanced XBRL parsing**: Improved handling of dimensional facts and parent-child relationships in statements
- **Backwards compatibility**: All changes maintain existing functionality while adding new capabilities

## Release 4.10.1 - 2025-09-05

### Fixed
- **CurrentReport (6-K/8-K) missing financials attribute (#332)**: Fixed AttributeError when accessing financials on 6-K and 8-K filings. CurrentReport now properly inherits from CompanyReport, providing consistent access to financial data across all filing types.

## Release 4.10.0 - 2025-09-05

### Fixed
- **Calculation weights causing inconsistent expense signs across companies (#334)**: Fixed a critical issue where R&D expenses and other operating expenses showed inconsistent signs (positive vs negative) across different companies due to variations in XBRL calculation weight structures. MSFT R&D expenses now show as positive $32.5B (previously negative), consistent with AAPL's positive $31.4B and the SEC CompanyFacts API.

### Enhanced  
- **Improved cross-company financial data consistency**: Enhanced XBRL parser to selectively preserve positive values for 15+ expense concept categories (R&D, SG&A, Marketing, Share-based Compensation, etc.) while maintaining proper calculation weight functionality for cash flow items and legitimate negative values (tax benefits, foreign exchange gains/losses).

### Technical
- **XBRL calculation weights processing**: Updated `_apply_calculation_weights()` method to ensure consistent expense representation across companies while preserving backwards compatibility and maintaining accuracy for cash flow calculations.

## Release 4.9.1 - 2025-09-03

### Changed
- Remove the dependency on the `packaging` library. This will ease installation issues caused through library conflicts

## Release 4.9.0 - 2025-08-29

### Added
- Add `comprehensive_income()` method to XBRL Statements class for consistent API access to comprehensive income statements (#396)

### Enhanced
- Implement smart period selection for XBRL statements to eliminate sparse columns
- Add statement-specific scoring thresholds for better data availability assessment
- Introduce Cash Flow statement-specific period selection (60/40 investor/data weight vs 75/25 for other statements)
- Add post-selection sparsity filter to remove periods with insufficient data (minimum 5 facts for Cash Flow)
- Set filing color scheme as default for XBRL statements (professional black-and-white formatting)

### Fixed
- Fix sparse column issue in financial statements where companies like JPM showed quarterly periods with 1-2 facts alongside YTD periods with 40+ facts
- Improve period selection for companies with YTD-only cash flow reporting patterns
- Enhance visual hierarchy and contextual information placement in statement rendering

## Release 4.8.3 - 2025-08-28

### Fixed
-  Fix annual period selection showing quarterly values (#408) by improving the filtering of periods when selecting annual statements

### Changed
- Enhance financial statement display by changing the color scheme for visibility and removing duplicate items

## Release 4.8.2 - 2025-08-23

### Changed
- Made the period detection selection logic more lenient to allow periods with limited data

## Release 4.8.1 - 2025-08-21

### Changed
- Reduce logging level for the `httpxthrottlecache` library to avoid excessive debug logs
- Change cachedir due to the serialization change
- Add warning when creating xbrl from amended filings

### Added
- Add markdown conversion support for HTML attachments and add support for optional page breaks 

## Release 4.8.0 - 2025-08-14

### Added
- Add `edgar.entity.company_subsets` module to allow for easy access to company subsets like `sp500`, `nasdaq100`, etc.
- Add derivative parsing for **NPORT** filings
### Fixed
- Fix `fetch_daily_filing_index` which used a different date format from the one used for quarterly indexes
- Code cleanup across the library to remove unused imports and functions

### Changed
- Improve XBRL query by dimension to allow for more flexible querying of XBRL facts e.g. without namespaces
- Improve the assignment of facts to statements in the EntityFacts using a learning approach
- Improve the display of EntityFact statements
- HTTP caching and throttling moved to a separate library `httpxthrottlecache`

## 4.7.0 - 2025-08-11

### Changed
- Ensure only HTTP 200 responses are cached in the HTTP cache
- Switch serializer, the default jsonserializer is very slow for large responses
- Enable `http2`, if installed
- Add `_make_request_conditional` to ensure proper revalidation of cached responses
- Bypass cache for large files
- Add 3.13 to to classifiers for PyPI

### Fixed
- Use a single global rate limiter even for async requests to avoid exceeding the SEC rate limits
- Cleanup unused async path
- Fix negative sign display in `moneyfmt` function

## 4.6.3 - 2025-08-07

### Fixed
- Fix bug where local storage downloads failed due to an error in the rate limiter handling of async http requests

## 4.6.2 - 2025-08-05

### Fixed
- Fix bug in period selection for quarterly statements from XBRL that caused some statements to not display data

## 4.6.1 - 2025-08-04

### Added
- Added parsing of footnotes from XBRL
- Add `accepted` field to `CurrentFilings` to indicate when a filing was accepted by the SEC

### Changed
- Refactored current filings into its own module `edgar.current_filings`

## 4.6.0 - 2025-08-03

### Added
- Added HTTP caching in the `edgar.httpclient_cache` module to cache HTTP requests and responses
- Add `FactQuery.by_text` to filter facts by text search
- 

### Changed
- Changed fron using a custom `Throttler` to using `pyratelimiter`. This allows for more flexible rate limiting and caching of HTTP requests


## 4.5.1 - 2025-07-31

### Changed
- Cleanup the `edgar.entity` package and remove the old implementation of `Facts`
- Add rich display to `EntityFacts`, `FactsQuery`, and `FinancialStatement` classes

## 4.5.0 - 2025-07-30

### Changed
- The Company Facts API has been completely rewritten to improve accuracy and easy of use

### Fixed
- Fix bug in XBRL parser not picking up the typedmember correctly

### Added
- Attachment Reports and Statements now have a `to_dataframe` method to convert the data to a pandas DataFrame


## 4.4.5 - 2025-07-25

## Fixed
- Fix bug in period selection for `XBRLS` (multiple period financials) that caused some statements to be missing for some companies
- Fix for some missing functions in Fund classes

## 4.4.4 - 2025-07-22

### Changed
- Late July Cusip ticker mappings added
- Minor fix to is_company check
- Add `owner_name` and `position` properties to `OwnershipForm` parent class of `Form3`, `Form4`, `Form5`
- Increase logging in `edgar.storage` module
- More robust handling of errors when getting storage
- Improvements to downloading of filings to local storage making it easier to incrementally add filings

## 4.4.3 - 2025-07-19

### Added
- Add a function `set_local_storage_path` to set the local storage path for the EDGAR library

### Changed
- Simplify how local storage can be turned on by combining setting the local storage path and turning on local storage 
- Remove unnecessary network calls when displaying a filing
- The `Filing.period_of_report` now comes from the SGML rather than the Filing Home page. This eliminates a network call when displaying a filing

## 4.4.2 - 2025-07-18

### Fixed
- Fixed bug where `MultiFinancials` class returned None 
- Fixed bug in `get_current_filings` where it did not return the last page of current filings

### Added
- Added `get_all_current_filings` to accumulate all current (most recent unpublished) filings 


## 4.4.1 - 2025-07-17

### Fixed
- Fix incorrect labels for **Total Current Assets** and **Total Current Liabilities** in the standardization mappings
- Fix bug in finding statement data for some companies when stitching statements

### Changed
- Don't infer concept labels during standardization. This allows for the original label to be shown if no standardization mapping is found. 


## 4.4.0 - 2025-07-16

## Fixed
- Improved ordering of line items when stitching statements

## Changed

- Early July Cusip ticker mappings added
- Several improvements to HTML parsing and item selection and rendering - Thanks to [zhangchmeng](https://github.com/zhangchmeng)
- Switch from the `limiter` package to `pyrate_limiter` for HTTP caching and rate limiting. 
- Used the scanned PDF as the main filing document for filings with `.paper` as the primary attachment type
- Use disk when streaming large files such as in `download_filings`
- Additional standardization mappings for financial concepts in the Income Statement

## 4.3.1 - 2025-06-29

### Fixed
- Fixed parsing of company specific concepts to allow for company specific concepts to be parsed correctly

### Changed
- Increase the width of the Form column in the `Filings` rich display 
- Add Company standardization for BRK-A



## 4.3.0 - 2025-06-28

### Added
- Added hierarchical standardization mappings for financial concepts
- Added standard labels for several key financial concepts to the standardization mappings
- Added company specific standardization for tsla and msft


## 4.2.2 2025-06-25

### Fixed

- Fixed missing standardization mappings json file
- Added standard concepts like **Current Marketable Securities** to the standardization mappings
- Fixed per share values being set to 0.00


## 4.2.1 - 2025-06-22

### Fixed 
- Fixed standardization of **Marketable Securities** concepts to distinguish between **Current** and **Non-current** marketable securities

### Added
- Add filtering of facts with no dimensions to the `FactsQuery` class

## 4.2.0 - 2025-06-20

### Added
- Add querying of facts from `XBRLS` which makes it easier to see what facts are selected

### Fixed
- Fixed duplicate columns in xbrl facts query

### Changed
- Improved display of XBRL Facts query results

## 4.1.3 - 2025-06-17

### Changed
- PDF is added as a supported format for SGL parsing
- Use the `versioning` package for more robust parsing of pandas version numbers

### Fixed
- Fix bug when parsing XBRL that includes non-text tags
- Silence uu_decode warning

## 4.1.2 - 2025-06-05

### Added
- Allow SSL verification to be disabled by setting `EDGAR_VERIFY_SSL` to `False`. This is useful for testing purposes or when using self-signed certificates or sometimes in a corporate environment.

### Fixed
- Fixed bug in selecting periods for quarterly statements 

## 4.1.1 - 2025-05-29

### Added
- Add filter by year and quarter to `Company.get_filings` to make it consistent with `get_filings`

### Changed
- Rename `priority_forms` to `priority_sorted_forms` in `get_filings` to clarify that it sorts the forms by priority
- Small enhancement to `EntityFiling` rich display
- Enhance rich styling of `accession_number` to show its constituent parts
- Simplify query facts by making "-" and ":" interchangeable in the concept name
- Rename the `edgar.filters` to `edgar.filtering`

## [4.1.0] - 2025-05-25

### Added
- Add `Docs` class to represent the documentation of an object in the library
- Add `docs` property to `Filing`, 'Filings` and 'EntityFilings` to display the documentation using e.g. `filing.docs`
- Add rich rendering to XBRL query class

### Changed
- Rename `XBRL.parse_directory` to `XBRL.from_directory` to be more consistent with the rest of the library
- Minor display changes for `Filing` class

## [4.0.4] - 2025-05-18

### Changed
- Include decimals when displaying fact query results

### Added
- Compress filings when downloading to local storage
- Add exception when downloading filings using `filings.download()` to be thrown if files cannot be listed


## [4.0.3] - 2025-05-13

### Fixed
- Fixed bug where the incorrect period was being selected for income statements
- Fixed incorrect import in entity submissions
- Ensure max_periods are used when stitching statements

### Changed
- Show progress when extracting files in `download_edgar_data()`

### Added

- Allow search for accession numbers with no dash e.g `find('000123456724123456')`
- Add `__bool__` to `Entity` so we can do `if Entity:` and `if Company:` to check if the entity/company is found


## [4.0.2] - 2025-05-09

### Fixed

- Fixed bug where Document parsing returns empty text for certain filings with `<pre>` tags
- Fixed bug where text extracts ignore SGML local content when available

### Added
- Add `to_html` to Ownership forms to generate html from insider forms
- Handle searches for invalid accession numbers

### Changed

- Changed `Filing.html` to generate html from plain text if html is not available. 
- Changed `Filing.html` to generate HTML for Insider forms instead of downloading from the SEC
- Relaxed the detection of html in filing documents to allow the code to work with more form types

## [4.0.1] - 2025-05-03

### Added
- Add missing properties like `industry`, `sic`, `fiscal_end_date` to the `Company` class

### Changed
- Improve how basic dei information about a company (dei) are extracted from XBRL


### Changed
- Remove `fastcore` dependency 
- Refactor `entities` to dedicated `entity` module
- Remove `filing.prev` - use `filing.previous()` instead
- `XBRL` and `Financials` completely rewritten
- Rewrote XBRL concept standardization
- `Fund` completely rewritten

### Added
- Create `Filing` from SGML file
- `Filings` can now be used to filter downloads
- Add financial ratio calculation

### Fixed
- Fixed issue with optional ratio concepts causing ratio calculations to fail


## [3.15.1] - 2025-04-15

### Added

- Add `cover_page()` accessor to `xbrl.statements` to get the cover page of the Statements


## [3.15.0] - 2025-04-04

### Fixed
- Fix bug in parsing index files for forms containing spaces e.g. ""


## [3.14.6] - 2025-04-04

### Fixed
- Fix issue where debug logs were displayed when rendering statements

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
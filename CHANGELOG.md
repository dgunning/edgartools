# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## Release 4.19.0 - 2025-10-13

### Fixed
- **Issue #460: Quarterly Income Statement Fiscal Period Labels** - Fixed quarterly period labels showing fiscal years 1 year ahead
  - **Problem**: Quarterly statements displayed fiscal periods 1 year in the future (e.g., "Q3 2025" instead of "Q3 2024")
  - **Root Cause**: SEC Facts API provides forward-looking fiscal_year values for quarterly facts (indicating which fiscal year the quarter contributes to, not for labeling purposes)
  - **Solution**: Enhanced quarterly label calculation in `enhanced_statement.py`:
    - Added `calculate_fiscal_year_for_label()` to calculate fiscal year from period_end date based on company's fiscal year end month
    - Added `detect_fiscal_year_end()` to automatically determine fiscal year end from FY facts
    - Filters out FY periods from quarterly output to prevent confusion
    - Handles 52/53-week calendar edge cases (early January periods)
  - **Impact**: Quarterly financial statements now show correct fiscal year labels that match the actual period dates
  - **Coverage**: Comprehensive regression tests for Apple (Sept FYE), Microsoft (June FYE), and Walmart (Jan FYE)
  - **Verification**: All statement types (income, balance sheet, cash flow) display correct quarterly labels

## Release 4.18.0 - 2025-10-10

### Added
- **Sections Wrapper Class**: New convenient interface for accessing filing sections
  - `Sections` class provides rich display of all available sections in a filing
  - Flexible access patterns: by item number, by part, or by full section identifier
  - Supports multiple key formats (e.g., "Item 1", "item1", "1" all work)
  - Convenient properties for common sections: `business`, `risk_factors`, `mda`, `financials`
  - Integrated with filing objects for seamless section navigation
  - Example:
    ```python
    filing = Company("AAPL").get_filings(form="10-K").latest()
    sections = filing.sections  # Rich display shows all available sections
    business = sections.business  # Access by property
    item1 = sections["Item 1"]   # Access by item number
    ```

### Fixed
- **Issue #455: Per-Share Metric Scaling in XBRL Balance Sheets** - Fixed incorrect scaling of per-share metrics
  - **Problem**: MainStreet Capital's NAV per share displayed as $0.03 instead of correct $31.65
  - **Root Cause**: Per-share metrics were incorrectly treated as regular monetary values, applying standard scaling (millions/thousands) when they should remain as-is
  - **Solution**: Enhanced XBRL rendering to detect per-share concepts and preserve their original scale
  - **Impact**: All per-share metrics (NAV per share, book value per share, etc.) now display with correct values
  - **Verification**: Tested against SEC filings and company-reported values

- **Issue #453: Missing Item 1C (Cybersecurity) in 10-K Structure** - Added support for Cybersecurity disclosure section
  - **Problem**: Item 1C (Cybersecurity) was missing from 10-K filing structure definition
  - **Solution**: Added Item 1C to TenK FilingStructure to support SEC's cybersecurity disclosure requirements
  - **Impact**: Enables access to cybersecurity disclosures in 10-K filings filed after the SEC rule effective date
  - **Coverage**: Properly handles both filings with and without Item 1C for backwards compatibility

### Enhanced
- **Code Quality**: Import optimizations and code hygiene improvements across multiple modules
  - Removed unused imports and dead code
  - Consolidated duplicate utilities to improve maintainability
  - Enhanced test coverage and documentation
  - Improved code organization in documents package

### Technical
- **HTML Parsing Infrastructure**: Comprehensive rewrite of HTML parsing and section detection
  - Replaced legacy parsing with high-performance streaming parser
  - Implemented confidence-based section detection with multiple strategies
  - Added hybrid orchestration for robust section identification
  - Enhanced table rendering with FastTableRenderer for improved performance
  - Support for both TOC-based and pattern-based section detection
  - Increased default max_document_size from 50MB to 100MB for large filings
  - Added comprehensive HTML fixtures and test coverage

## Release 4.17.1 - 2025-10-06

### Fixed
- **Dimensional Member Display (Issue #416 Regression)** - Fixed regression where segment member concepts were incorrectly filtered from dimensional displays
  - **Problem**: After Issue #450 fix, dimensional member concepts (like `us-gaap_ProductMember`, `us-gaap_ServiceOtherMember`) were being filtered from Income Statements with dimensional breakdowns
  - **Root Cause**: Member filtering logic was too aggressive, removing Members without values even in dimensional display contexts where they serve as category headers
  - **Solution**: Enhanced filtering logic in `edgar/xbrl/rendering.py` to:
    - Detect dimensional display mode by checking for dimensional items in statement data
    - Keep Member concepts in dimensional displays even without values (they're category headers)
    - Continue filtering Members from Statement of Equity (where they're structural column headers)
  - **Impact**: Product and service segment values now correctly appear in dimensional income statements
  - **Verification**: Issue #416 regression tests pass; Issue #450 Statement of Equity still works correctly

- **Statement of Equity Rendering (Issue #450)** - Fixed three critical rendering issues plus added clearer labeling

  **Issue #1: Missing Total Stockholders' Equity Values**
  - **Problem**: Total Stockholders' Equity rows appeared twice (beginning and ending balance) but both showed empty values, or later both showed the same ending balance value
  - **Root Cause**: Statement of Equity shows duration periods (quarters) but Total Stockholders' Equity is an instant fact. Initial fix matched instant facts at end_date for both occurrences, causing both rows to show ending balance instead of distinct beginning/ending balances
  - **Solution**: Enhanced instant fact matching in `edgar/xbrl/rendering.py` (lines 1511-1531) to distinguish concept occurrences:
    - First occurrence: Match instant at `start_date - 1 day` (beginning balance)
    - Later occurrences: Match instant at `end_date` (ending balance)
    - Tracks concept occurrence count to determine position in roll-forward structure
  - **Impact**: Total Stockholders' Equity displays correct values for both beginning and ending balances

  **Issue #2: Wrong Abstract Positioning**
  - **Problem**: Abstract headers (like RollForward) appeared AFTER their children instead of before them
  - **Root Cause**: Dimensional axis members (`CommonStockMember`, `RetainedEarningsMember`) were being rendered as regular rows before abstract headers
  - **Solution**: Enhanced filtering in `edgar/xbrl/rendering.py` (lines 1471-1480) to skip dimensional members based on:
    - Concept name suffix patterns (Member, Axis, Domain, LineItems, Table)
    - Special handling for Statement of Equity where dimensional members are always structural
  - **Impact**: Abstract headers now appear at the top of their hierarchical sections, before their children

  **Issue #3: Incorrect Abstract Flagging**
  - **Root Cause**: US-GAAP taxonomy schemas are referenced externally and not parsed, causing standard taxonomy concepts to be added to the element catalog without abstract attribute information (defaulting to `abstract=False`)
  - **Solution**: Implemented multi-tier abstract detection strategy:
    - Pattern-based matching for common abstract concepts (endings: Abstract, RollForward, Table, Axis, Domain, LineItems)
    - Known abstract concepts list for explicitly marked abstracts in US-GAAP taxonomy
    - Schema abstract attribute fallback (when available)
    - Structural heuristics for edge cases
  - **Changes**:
    - Added `edgar/xbrl/abstract_detection.py` module
    - Updated `edgar/xbrl/parsers/presentation.py` to use enhanced abstract detection
    - Updated `edgar/xbrl/parser.py` to use enhanced abstract detection
    - Fixed `edgar/xbrl/xbrl.py` line 798 to use `node.is_abstract` instead of hardcoding `False`
  - **Impact**: Abstract concepts like `IncreaseDecreaseInStockholdersEquityRollForward` are now correctly marked as `abstract=True`

  **Enhancement: Clearer Beginning/Ending Balance Labels**
  - **Feature**: Automatically appends " - Beginning balance" and " - Ending balance" to labels for concepts that appear multiple times in Statement of Equity (like Total Stockholders' Equity)
  - **Implementation**: Added label enhancement in `edgar/xbrl/rendering.py` (lines 1490-1500)
  - **Impact**: Users can immediately distinguish between beginning and ending balances without examining values

  **Testing**: Comprehensive regression tests in `tests/issues/regression/test_issue_450_equity_statement_abstract_flags.py` validate all fixes

  **Example**:
    ```python
    from edgar import Company
    c = Company("AAPL")
    equity = c.get_filings(form="10-Q").latest(1).xbrl().statements.statement_of_equity()
    df = equity.to_dataframe()

    # Issue #3: RollForward concepts now correctly marked as abstract
    rollforward = df[df['concept'] == 'us-gaap_IncreaseDecreaseInStockholdersEquityRollForward']
    assert rollforward['abstract'].iloc[0] == True

    # Issue #2: RollForward appears at index 0 (before its children)
    assert rollforward.index[0] == 0

    # Issue #1: Total Stockholders' Equity shows distinct beginning and ending values
    equity_rows = df[df['concept'] == 'us-gaap_StockholdersEquity']
    assert len(equity_rows) >= 2  # Beginning and ending balance rows
    # Labels now clearly indicate: "Total Stockholders' Equity - Beginning balance"
    #                              "Total Stockholders' Equity - Ending balance"
    ```

## Release 4.17.0 - 2025-10-05

### Added
- **Storage Management Dashboard (FEAT-436)** - Comprehensive tools for local storage visibility, analytics, and optimization
  - **Storage Analytics**: New `storage_info()` function and `StorageInfo` dataclass provide comprehensive storage statistics
    - Total size, disk usage, compression ratios, file counts, and breakdown by data type
    - 60-second caching for performance on large storage directories
    - Beautiful Rich Panel display with automatic REPL rendering
  - **Filing Availability Checks**: Efficient offline filing detection
    - `check_filing()`: Check if single filing is available locally
    - `check_filings_batch()`: Efficiently check multiple filings at once
    - `availability_summary()`: Get formatted availability summary strings
  - **Storage Analysis**: Intelligent recommendations with `analyze_storage()` and `StorageAnalysis`
    - Detects uncompressed files and estimates potential savings
    - Identifies large cache directories consuming space
    - Flags old filings (over 1 year) when substantial
    - Provides actionable optimization recommendations
  - **Storage Optimization Operations**: Safe storage management with dry-run defaults
    - `optimize_storage()`: Compress uncompressed files (typically 70% space savings)
    - `cleanup_storage()`: Remove old filings beyond specified age
    - `clear_cache()`: Clear HTTP cache directories (safe, rebuilds on demand)
  - **Safety Features**: All destructive operations default to `dry_run=True` for safety
  - **Documentation**: Comprehensive guide with workflows, examples, and best practices
  - **Coverage**: 12 tests with full coverage for all storage management functionality
  - **Impact**: Enables users to understand, monitor, and optimize their local SEC filing storage
  - **Example**:
    ```python
    from edgar import storage_info, analyze_storage, optimize_storage

    # View storage statistics
    info = storage_info()  # Beautiful Rich panel display

    # Get optimization recommendations
    analysis = analyze_storage()

    # Compress files to save space (dry-run first)
    result = optimize_storage(dry_run=True)
    result = optimize_storage(dry_run=False)
    ```

### Fixed
- **Quarterly Balance Sheets**: Fixed duplicate fiscal periods appearing in quarterly balance sheets
  - **Problem**: Quarterly statements showed duplicate periods (e.g., "Q3 2025" appearing twice with different values: $331.2B and $365.0B)
  - **Root Cause**: SEC Facts API includes comparative period data from filings and tags ALL facts with the filing's fiscal_year and fiscal_period, regardless of which period the data actually represents. For example, Apple's Q3 2025 10-Q filing includes both current Q3 2025 data AND prior year Q4 2024 comparative data, but both are tagged as fiscal_period='Q3'
  - **Solution**: Enhanced quarterly period selection logic in `enhanced_statement.py`:
    - Added `validate_quarterly_period_end()` to verify period_end matches expected month for fiscal_period
    - Added `detect_fiscal_year_end()` to automatically detect company's fiscal year end from FY facts
    - Validates Q1-Q4 periods end in appropriate months based on fiscal year end (Q3 for Sept FYE should end in June, not Sept)
    - Allows ±1 month flexibility for 52/53-week calendars
    - Groups by period label and keeps most recent filing when duplicates exist
  - **Impact**: Eliminates confusing duplicate columns in quarterly financial statements, ensures correct quarterly values are displayed
  - **Coverage**: Comprehensive regression tests for Apple, Microsoft, Google, Amazon covering balance sheets, income statements, and cash flow statements
  - **Example**: `Company("AAPL").balance_sheet(annual=False)` now shows unique Q3 2025 with correct $331B assets (June 2025 data) instead of duplicate Q3 2025 columns

- **Issue #452**: Incorrect revenue values for companies with fiscal year-end changes
  - **Problem**: EdgarTools showed $1.530B for DNUT's FY 2023 revenue instead of correct $1.686B
  - **Root Cause**: SEC Company Facts API provides duplicate periods with inconsistent fiscal_year values when companies change fiscal year-ends. Krispy Kreme's transition from January to December FYE created mislabeled comparative periods.
  - **Solution**: Added fiscal year validation in `enhanced_statement.py` to filter invalid fiscal_year/period_end combinations:
    - Validates fiscal_year aligns with period_end (early January → year-1, normal dates → year)
    - Enhanced deduplication to prefer periods where fiscal_year matches expected value
    - Rejects mislabeled comparative data from SEC API
  - **Impact**: Fixes incorrect financial values for companies during fiscal year-end transitions
  - **Testing**: Regression test added for DNUT FY 2023 revenue verification

## Release 4.16.1 - 2025-10-03

### Technical
- **XBRL Code Refactoring** - Eliminated duplication and improved maintainability
  - **Created Shared Concepts Module**: New `edgar/xbrl/parsers/concepts.py` centralizes positive value concepts and legitimate negative concepts
  - **Eliminated Duplication**: Removed ~240 lines of duplicated concept definitions across parser.py, calculation.py, and instance.py
  - **Enhanced Financing Concepts**: Added PaymentsForRepurchaseOfCommonStock and PaymentsOfDividends to financing activity concepts
  - **Improved Consistency**: Single source of truth for XBRL concept sign handling across all parsers
  - **Test Alignment**: Updated test expectations for cost of goods sold to align with issues #290 and #451
  - **Impact**: Better code maintainability, reduced risk of inconsistent behavior across XBRL parsing components

## Release 4.16.0 - 2025-09-30

### Added
- **EntityFacts DataFrame Export** - Direct DataFrame export capability for custom analysis
  - **New EntityFacts.to_dataframe() method**: Convert entity facts directly to pandas DataFrame for custom analysis
  - **Parameters**: `include_metadata` (bool) to control metadata columns, `columns` (list) for custom column selection
  - **Coverage**: Exports all fact data with configurable metadata (labels, units, decimals) and custom column filtering
  - **Impact**: Transforms EntityFacts from view-only to analysis-ready data structure, enabling seamless integration with pandas workflows
  - **Example**:
    ```python
    facts = company.get_facts()
    df = facts.to_dataframe(include_metadata=True)
    # Now use df with standard pandas operations
    ```

- **Multi-Entity Filing Support (Issue #400)** - Comprehensive support for filings covering multiple entities
  - **New Filing properties**: `is_multi_entity`, `all_ciks`, `all_entities` for multi-entity detection and access
  - **New enriched access method**: `get_by_accession_number_enriched()` provides full entity information for multi-entity filings
  - **Enhanced find() function**: Updated to handle multi-entity filings with proper entity resolution
  - **Visual indicators**: Rich display shows clear grouping for multi-entity filings with visual separators
  - **Coverage**: Complete multi-entity workflow from detection through entity-specific data access
  - **Impact**: Enables proper handling of investment fund filings and other multi-entity submissions that previously appeared incomplete

### Fixed
- **Issue #408**: Filter empty string periods in financial statements
  - **Problem**: Older XBRL filings (2016-2018) included empty period columns causing confusing blank columns in financial statements
  - **Solution**: Enhanced period filtering to detect and remove periods containing only empty string values
  - **Coverage**: Automatically filters empty periods while preserving all valid data columns
  - **Impact**: Cleaner financial statement displays for historical filings without confusing empty columns

### Enhanced
- **Multi-Entity Visual Grouping** - Improved display clarity for multi-entity filings
  - **Rich Display Enhancement**: Added visual grouping indicators to clearly separate multiple entities in filing displays
  - **Coverage**: Automatic visual separation in terminal/notebook displays when viewing multi-entity filings
  - **Impact**: Improved clarity when reviewing filings that cover multiple related entities

- **Header Access Logging** - Informative diagnostics for filing header issues
  - **Enhancement**: Added clear logging messages when filing header access fails
  - **Coverage**: Provides actionable diagnostic information for troubleshooting filing access issues
  - **Impact**: Easier debugging of filing access problems with clear error context

## Release 4.15.0 - 2025-09-26

### Added
- **Period Type Filtering API** - Intuitive period filtering for enhanced developer experience
  - **New get_facts() parameter**: Direct period type filtering with `company.get_facts(period_type=PeriodType.ANNUAL)`
  - **FactQuery.by_period_type()**: Chainable period filtering in query interface
  - **EntityFacts.filter_by_period_type()**: Direct filtering on facts objects
  - **Coverage**: Supports ANNUAL, QUARTERLY, MONTHLY period types with automatic period length mapping
  - **Impact**: Transforms period filtering from "knowledge-required" to "intuitive" for common EdgarTools operations

- **Enhanced ETF Support** - Comprehensive ETF ticker and series resolution
  - **ETF Series Search (FEAT-417)**: Enhanced Fund class with ticker-to-series resolution
  - **ETF Ticker Holdings (FEAT-418)**: Intelligent ticker resolution with CUSIP fallback for NPORT-P filings
  - **Smart ETF Fallback**: 100% success rate with popular ETFs (SPY, QQQ) via company ticker resolution
  - **New Services**: TickerResolutionService and TickerSeriesResolver with comprehensive caching
  - **Coverage**: Automatic ticker resolution in holdings data with clear diagnostics
  - **Impact**: Fund("SPY") now works perfectly, enabling seamless ETF analysis

### Fixed
- **SGML Parser Regression with HTML Content Detection** - Resolved false positive HTML detection in valid SGML
  - **Problem**: Valid SGML containing HTML/XBRL content within `<TEXT>` sections was incorrectly flagged as HTML
  - **Solution**: Reordered detection logic to check for valid SGML structure before HTML content detection
  - **Coverage**: Maintains protection against SEC HTML error responses while fixing inline XBRL parsing
  - **Impact**: Fixes regression in SGML parsing for filings with inline XBRL content

### Enhanced
- **Test Infrastructure Improvements** - Enhanced test reliability and isolation
  - **Cache Contamination Fixes**: Proper cache clearing to prevent test interference
  - **Test Isolation**: Monkeypatch-based EDGAR_IDENTITY handling for better test isolation
  - **Pytest Marks**: More accurate test categorization for selective test execution
  - **Coverage**: All 51 ETF feature tests pass consistently in isolation and full suite
  - **Impact**: Improved test reliability and developer experience

## Release 4.14.2 - 2025-09-24

### Enhanced
- **Enhanced SEC Error Handling in SGML Parsing**: Improved error reporting with specific, actionable exceptions
  - **Problem**: When SEC returns error responses (HTML/XML), users received generic "Unknown SGML format" errors that provided no guidance
  - **Solution**: Added custom exception classes (`SECIdentityError`, `SECFilingNotFoundError`, `SECHTMLResponseError`) with specific error detection and actionable error messages
  - **Coverage**: Handles SEC identity errors, AWS S3 NoSuchKey errors, and other HTML/XML error responses
  - **Impact**: Users now receive clear guidance on how to resolve SEC API issues, including proper EDGAR_IDENTITY setup and filing availability checks

## Release 4.14.1 - 2025-09-23

### Fixed
- **Issue #446**: Fixed missing values in 20-F filings by adding IFRS taxonomy support
  - **Problem**: 20-F filings using IFRS taxonomy showed sparse financial data due to missing concept mappings
  - **Solution**: Added comprehensive IFRS taxonomy support with proper concept recognition and mapping
  - **Impact**: Enables accurate financial data extraction from international companies filing 20-F forms with IFRS standards

- **JSONDecodeError from corrupted submissions cache files**: Resolved cache corruption issues causing parsing failures
  - **Problem**: Corrupted cache files were causing JSONDecodeError exceptions when accessing company submissions data
  - **Solution**: Enhanced cache validation and error handling to detect and recover from corrupted cache entries
  - **Impact**: Improved reliability of company data access with graceful handling of cache corruption

### Enhanced
- **Early September CUSIP Tickers Update**: Updated CUSIP to ticker mappings with latest September data
  - **Coverage**: Refreshed ticker mappings to ensure accurate company identification and symbol resolution
  - **Impact**: Maintains accuracy of company lookups and ensures current ticker symbols are properly recognized

## Release 4.14.0 - 2025-09-19

### Added
- **Unified XBRL Period Selection System** - Complete architectural improvement with 85% code reduction
  - **New PeriodSelector class**: Centralized, sophisticated period selection logic replacing scattered implementations
  - **Intelligent Quarterly Period Logic**: Enhanced quarterly period selection with sophisticated investor logic for accurate quarterly data access
  - **Fiscal Year Alignment**: Advanced fiscal year alignment scoring for proper period matching across different company fiscal calendars
  - **Document Date Filtering**: Robust filtering of future-dated periods to prevent Bristol Myers future date bugs
  - **Statement Type Optimization**: Period selection optimized for specific statement types (balance sheet instant periods, income statement duration periods)
  - **Coverage**: Unified system handles all XBRL period selection scenarios across entity facts, statements, and financial data access
  - **Key Benefits**: Eliminates inconsistent period selection, improves data accuracy, and provides reliable quarterly/annual financial data access

- **Large File Architecture Refactoring** - Major code organization and maintainability improvements
  - **Entity Package Restructuring**: Reorganized entity/core.py with improved separation of concerns and better code organization
  - **Funds Package Enhancement**: Refactored funds/reports.py with enhanced 13F handling and better data structure organization
  - **XBRL Parser Modularization**: Complete restructuring of xbrl/parser.py into specialized parser modules for improved maintainability
  - **New Parser Architecture**: Created specialized parsers for instance, calculation, presentation, definition, labels, and schema handling
  - **Improved Code Organization**: Better separation of parsing concerns with coordinator pattern for parser orchestration

### Fixed
- **Critical Period Selection Bug (Bristol Myers Case)**: Fixed future-dated period selection causing incorrect financial data display
  - **Problem**: Period selector included future-dated periods in financial statements, leading to inaccurate data presentation
  - **Solution**: Implemented robust document date filtering in PeriodSelector to exclude periods dated after filing document date
  - **Impact**: Ensures financial statements only display data from periods actually covered by the filing

- **Multi-Year Period Selection (Visa Case)**: Resolved incorrect handling of multi-year period spans in quarterly reports
  - **Problem**: Quarterly filings incorrectly included multi-year duration periods alongside quarterly periods
  - **Solution**: Enhanced period detection logic to filter out multi-year periods when quarterly data is expected
  - **Impact**: Provides accurate quarterly financial data without contamination from multi-year period aggregates

- **API Documentation Accuracy**: Fixed PeriodType documentation with correct API usage examples
  - **Problem**: Documentation showed outdated API patterns that no longer match current implementation
  - **Solution**: Updated all PeriodType documentation examples to reflect current API usage patterns
  - **Impact**: Eliminates user confusion and provides accurate implementation guidance

### Enhanced
- **GitHub Actions CI/CD Pipeline**: Significant improvements to automated testing and build processes
  - **Hatch JSON Filter Fix**: Resolved GitHub Actions hatch JSON filter issues preventing proper build automation
  - **Workflow Optimization**: Enhanced python-smoke-recent-filings.yml workflow for better reliability
  - **Test Dependencies**: Fixed missing test dependencies and pytest markers for consistent test execution
  - **Build Process**: Improved build reliability by addressing workflow configuration issues

- **Code Quality and Hygiene**: Comprehensive code improvement program across the entire codebase
  - **Logging Standards (G004)**: Fixed 1000+ logging f-string usage issues for better performance and consistency
  - **Exception Handling**: Enhanced exception chaining and error handling patterns throughout the codebase
  - **Pandas Modernization**: Updated pandas usage patterns for better performance and current best practices
  - **Import Organization**: Cleaned up and organized imports across all modules for better maintainability
  - **Memory Management**: Fixed memory leak risks from cached instance methods
  - **Code Style**: Comprehensive cleanup of whitespace, formatting, and code organization issues

### Technical
- **XBRL Processing Architecture**: 85% reduction in XBRL period selection code through unified architecture
  - **Removed Legacy Code**: Eliminated obsolete smart_periods.py module (558 lines) in favor of unified PeriodSelector
  - **Modular Parser Design**: Created specialized XBRL parser modules replacing monolithic parser implementation
  - **Enhanced Test Coverage**: Added comprehensive test suite for PeriodSelector with 34 test cases covering edge cases and integration scenarios
  - **Performance Improvements**: Optimized period selection performance through better algorithms and reduced code complexity

- **Documentation and Developer Experience**: Enhanced internal documentation and development workflows
  - **Architecture Documentation**: Added comprehensive XBRL period selection architecture documentation
  - **Code Organization**: Better separation of concerns across entity, funds, and XBRL packages
  - **Error Handling**: Improved error messages and exception handling for better debugging experience

### Maintenance
- **Dependency Management**: Updated and cleaned up package dependencies for better compatibility
- **Test Infrastructure**: Enhanced test configuration and coverage across all major features
- **Development Tools**: Improved development workflow with better CI/CD automation and code quality tools

## Release 4.13.0 - 2025-09-18

### Added
- **FEAT-411: Standardized Financial Concepts API** - Complete implementation of standardized financial concept access
  - **New Methods in EntityFacts**: 7 standardized getter methods for consistent financial data access
    - `get_revenue()` - handles various revenue concept names across companies
    - `get_net_income()` - standardizes net income access
    - `get_total_assets()` - consistent asset reporting
    - `get_total_liabilities()` - standardized liability access
    - `get_shareholders_equity()` - equity across entity types
    - `get_operating_income()` - operating income normalization
    - `get_gross_profit()` - gross profit with fallback calculation
  - **Advanced Features**: Priority-based concept matching, XBRL namespace handling, period-specific access, intelligent fallback calculations
  - **Validation**: 100% success rate tested across 40+ companies including FAANG, Tech Giants, and Mega-Cap companies
  - **User Impact**: Eliminates need for company-specific XBRL knowledge when accessing key financial metrics

- **Comprehensive Unit Handling System** - Enhanced unit compatibility and conversion logic
  - **UnitCompatibilityMode**: Configurable unit handling with Strict, Lenient, and Convert modes
  - **Unit Analysis Tools**: Built-in unit compatibility checking and conversion utilities
  - **Entity Facts Integration**: Seamless unit handling within standardized financial concept API

### Fixed
- **Issue #439**: Fixed XBRL order and balance_type parsing in linkbases
  - **Problem**: XBRL parser failed to properly handle both 'xlink:order' (XBRL standard) and 'order' attributes in calculation, presentation, and definition linkbases
  - **Solution**: Added robust `_parse_order_attribute()` method with proper fallback handling for both attribute formats
  - **Impact**: Improves XBRL data structure parsing accuracy and prevents parsing failures in diverse XBRL document formats

- **Issue #441**: Improved error handling in CurrentFilings
  - **Problem**: Assertion errors when handling malformed filing data
  - **Solution**: Replaced assertions with proper error handling and logging
  - **Impact**: More robust filing data processing with graceful error recovery

### Enhanced
- **Currency Display Performance** - Optimized currency display performance and memory usage
  - Reduced memory footprint for financial statement rendering
  - Improved performance when displaying large datasets with currency formatting

- **Test Infrastructure** - Enhanced test configuration and coverage
  - Added comprehensive regression tests for new standardized concepts API
  - Improved test configuration for currency and filing access tests
  - Added unit compatibility mode testing with extensive validation scenarios

### Technical Details
- **New Files Added** (22 files, 10,464+ lines):
  - `edgar/entity/entity_facts.py`: Extended with standardized financial concept methods (327 lines)
  - `edgar/entity/unit_handling.py`: Comprehensive unit handling system (419 lines)
  - `edgar/entity/tools.py`: Enhanced entity analysis tools (16 lines)
  - `tests/test_standardized_concepts.py`: Complete test suite for new API (354 lines)
  - `tests/test_unit_handling.py`: Unit handling validation tests (538 lines)
  - Additional test files for company groups and compatibility modes

- **Core Improvements**:
  - Enhanced `edgar/xbrl/parser.py` with robust order attribute parsing (57 lines modified)
  - Optimized currency display components for better performance
  - Improved error handling patterns across multiple modules
  - Zero breaking changes - all existing functionality preserved and enhanced

## Release 4.12.2 - 2025-09-14

### Fixed
- **Issue #412**: Resolved missing historical balance sheet data for companies like TSLA
  - **Problem**: Historical periods (FY 2021-2022) showed sparse data (~2% completeness) despite comprehensive data being available in Facts API
  - **Root Cause**: Period selection logic prioritized recent filing dates over data completeness, selecting amended filings with sparse comparative data
  - **Solution**: Implemented "Recency + Availability" approach that filters periods requiring ≥5 facts before selecting most recent filing
  - **Results**: TSLA historical periods improved from 2% to 54.9% data completeness
  - **Impact**: Affects balance sheets, income statements, and cash flow statements for companies with amendment filing patterns

- **Issue #438**: Resolved missing revenue facts and duplicate entries in NVDA income statements
  - **Problem**: NVDA income statements showed missing revenue data and potential duplicate entries when fixed
  - **Root Cause**: STATEMENT_MAPPING missing "Revenues" concept, plus multiple revenue concepts creating duplicates
  - **Solution**: Two-part fix - concept mapping enhancement + intelligent revenue deduplication
  - **Results**: Revenue data properly classified (267 facts) with no duplicate entries, optimal revenue concept selected
  - **Impact**: Affects companies using plural "Revenues" concept or multiple revenue representations in XBRL

### Enhanced
- **Financial Statement Completeness**: Comprehensive historical financial data now available for affected companies
- **XBRL Concept Mapping**: Enhanced revenue concept classification with intelligent deduplication preventing duplicate entries
- **Revenue Processing**: Smart hierarchical precedence system automatically selects optimal revenue concept from multiple representations
- **Test Coverage**: Added extensive regression tests (`test_412_regression.py`, `test_issue_438_regression.py`) preventing future occurrences  
- **Data Quality**: Maintains accuracy through recency component while ensuring comprehensive historical data

### Technical Details
- Modified `edgar/entity/enhanced_statement.py:1057-1074` with improved period selection logic (Issue #412)
- Enhanced `edgar/entity/parser.py` STATEMENT_MAPPING with additional revenue concept coverage (Issue #438)
- Added `edgar/xbrl/deduplication_strategy.py` for intelligent revenue deduplication (Issue #438)
- Integrated deduplication with XBRL statement generation in `edgar/xbrl/xbrl.py`
- Zero performance impact - same filtering process with better selection criteria
- Backwards compatible - all existing functionality preserved
- Added comprehensive test suites verifying data completeness and concept mapping accuracy

## Release 4.12.1 - 2025-09-13

### Fixed
- **Issue #412**: Fixed SGML parser robustness for filings with mixed content types
  - Resolved "ValueError: too many values to unpack (expected 2)" when parsing XBRL inline content with multiple '>' characters
  - Enhanced SGML parser with tag validation to distinguish SGML from HTML/XBRL content
  - Added `_is_valid_sgml_tag()` method to prevent interference from HTML/XBRL tags during header parsing
  - Fixed TSLA financial data access issues and other filings with embedded XBRL data
  - Maintains full backwards compatibility with existing SGML parsing (all 35 existing tests pass)

### Enhanced
- **SGML Parser Robustness**: Improved handling of SEC filings with mixed SGML/HTML/XBRL content
- **Test Coverage**: Added comprehensive regression tests for Issue #412 with minimal test data files
- **Error Handling**: Enhanced graceful handling of malformed SGML lines without proper formatting

### Technical Details
- Modified `sgml_header.py` to split only on first '>' character using `split('>', 1)`
- Added tag validation to skip non-SGML content during header parsing
- Zero performance impact on existing functionality
- Enables parsing of complex SEC filings that previously failed

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
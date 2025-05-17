# XBRL Period Selection Logic

This document explains how the EdgarTools XBRL module selects periods for display when rendering financial statements. Understanding this process helps users predict which time periods will appear in a rendered statement.

## Overview

When rendering an XBRL financial statement, the system must determine which time periods to display. The logic varies based on several factors:

1. The type of statement (Balance Sheet, Income Statement, etc.)
2. The fiscal period focus of the filing (Annual/FY, Quarterly/Q1-Q4)
3. Available periods in the XBRL data
4. User-specified period filters or views

## Period Selection Process

The period selection logic follows this order of priority:

1. If a specific `period_filter` is provided, only that exact period is used
2. If a named `period_view` is specified, the periods defined in that view are used
3. Otherwise, apply default selection logic based on statement type

## Statement-Specific Logic

### Balance Sheets

Balance sheets use **instant periods** (specific dates) rather than duration periods. The selection logic is:

1. **Current Period**: The most recent date is always selected first
2. **Comparison Period**: The system searches for an appropriate comparison period
   - For annual reports, it looks for a date from the previous fiscal year that is close to the fiscal year-end date
   - For quarterly reports, it looks for a date from the previous year with a similar month/day pattern
3. **Additional Periods**: For annual reports, up to one additional fiscal year-end period may be added (for a total of 3)

### Income Statements and Cash Flow Statements

These statements use **duration periods** (spans of time). The selection logic is:

1. **Annual Reports** (fiscal_period_focus = 'FY'): The system uses a sophisticated approach to find the most appropriate annual periods:
   - **First pass**: Identifies all periods with durations between 350-380 days (approximately one year)
   - **Second pass**: Scores these periods based on how well they align with the company's fiscal year end
     * Perfect match (score 100): Same month and day as fiscal year end
     * Strong match (score 75): Same month and within 15 days of fiscal year end
     * Moderate match (score 50): Month before/after and close to fiscal year end day
   - **Selection**: Takes up to 3 periods with the highest fiscal alignment scores
   - **Key improvement**: This ensures that periods like `duration_2013-07-01_2014-06-30` are preferred over `duration_2013-01-01_2013-12-31` when the company's fiscal year ends in June
   - If no annual periods are found that match the 350-380 day criteria, it falls back to showing the 3 most recent duration periods

2. **Quarterly Reports** (fiscal_period_focus = Q1, Q2, Q3, Q4): When processing non-annual filings
   - The code doesn't attempt to filter for quarterly durations when no period view is specified
   - Instead, it simply takes up to 3 most recent duration periods
   - **Key reason for 2 periods**: If there are only 2 duration periods in the XBRL data, only 2 will be displayed
   - This is common in quarterly reports that may only include current quarter and year-to-date periods

### Other Statement Types

For other statement types, the system uses a combination of known preferences and heuristics:

1. **Known Statement Types**:
   - Statement of Equity: Duration periods, up to 3 periods
   - Comprehensive Income: Duration periods, up to 3 periods
   - Cover Page: Single instant period (most recent)
   - Notes: Single instant period (most recent)

2. **Unknown Statement Types**:
   - For annual reports: Prefer duration periods, up to 2 periods
   - For interim reports: Default to a single period

## Technical Details: Period Selection Code Path

When an Income Statement is rendered, the system follows these steps to determine which periods to display:

1. **First check**: If a `period_filter` or `period_view` parameter is provided, use those specific periods

2. **Default path** (when no period filter/view is specified):
   - The code checks if the statement type is 'IncomeStatement' or 'CashFlowStatement'
   - It sorts all duration periods by end date (most recent first)
   - For annual reports (fiscal_period_focus = 'FY'):
     - It attempts to find periods with durations of 350-380 days (annual periods)
     - If annual periods are found, it takes up to 3 most recent ones
     - **Why only 2 periods might appear**: If only 2 annual periods exist in the data, only 2 will be shown
   - For non-annual reports OR if no annual periods are found:
     - It simply takes the 3 most recent duration periods (or fewer if not available)
     - **Common scenario**: Quarterly reports often only include 2 duration periods in the XBRL data
       (typically the current quarter and year-to-date figures)

3. **Code location**: This logic is implemented in the `determine_periods_to_display` function in `edgar/xbrl/periods.py`

## Common Scenarios: Why Fewer Than 3 Periods Might Appear

Here are the most common reasons why an Income Statement might render with only 2 periods instead of 3:

1. **Limited Source Data**: The XBRL filing itself contains only 2 periods of data
   - SEC regulations only require 2 years of comparative data for Income Statements
   - Companies often provide just the minimum required data

2. **Fiscal Year Alignment**: When processing annual reports
   - The system now scores periods based on how well they match the company's fiscal year end
   - Periods that don't align with the company's fiscal year pattern (even if they're 365 days long) receive lower scores
   - Example: For a company with June fiscal year end, a July-June period will be preferred over a January-December period
   - This prevents mixing of different fiscal patterns in the same statement

3. **Quarterly Report Structure**: For quarterly reports
   - Many quarterly filings include only 2 duration periods by design:
     * Current quarter (3-month period)
     * Year-to-date figures
   - The code takes what's available (up to 3 periods)

4. **New Companies**: Companies with short operating histories
   - Recently IPO'd companies may only have 1-2 years of financial data available

5. **Filing Type Transition**: When companies change filing types
   - A company transitioning from smaller reporting formats may have fewer historical periods

## Customizing Period Selection

Users can override the default period selection logic using:

1. **Period Filter**: Specify a single period key to display just that period
   ```python
   statements.income_statement(period_filter="duration_2023-01-01_2023-12-31")
   ```

2. **Period View**: Specify a named set of periods defined for the statement
   ```python
   statements.income_statement(period_view="Annual Comparison")
   ```

3. **View Available Period Options**: Get information about available period views
   ```python
   statements.get_period_views("IncomeStatement")
   ```

## Common Period Views

Depending on the statement type and available periods, the system typically offers these period views:

- **Annual Comparison**: Shows two fiscal years for comparison
- **Three-Year Annual Comparison**: Shows three fiscal years for comparison
- **Current vs. Previous Period**: Shows the current period and the previous comparable period
- **Quarterly Comparison**: Shows the current quarter and the same quarter from the previous year
- **Three Recent Periods**: Shows the three most recent reporting periods

## Special Handling for Fiscal Year Reporting

The system incorporates fiscal year information when available to ensure meaningful period comparisons:

1. It identifies fiscal year-end dates based on the filing's metadata
2. For annual reports, it prioritizes periods that align with the entity's fiscal year-end
3. When looking for comparison periods, it matches periods from similar fiscal positions

This approach ensures that statements display periods that make logical sense for financial analysis, such as comparing Q3 2023 with Q3 2022 rather than with Q2 2023.

## Edge Case: Fiscal Year Changes

When a company changes its fiscal year end, our period selection logic may encounter challenges:

1. **Transition Period Anomalies**: 
   - The transition year often has a non-standard duration (shorter or longer than 12 months)
   - This period may be misclassified by duration-based identification (350-380 days)

2. **Fiscal Alignment Score Issues**:
   - Historical periods that aligned with the previous fiscal year end receive artificially low scores
   - This may exclude relevant comparison periods that were correctly aligned under the previous fiscal calendar

3. **Year-over-Year Comparison Problems**:
   - Annual comparison views may include periods that aren't truly comparable
   - The "Three-Year Annual Comparison" might mix different fiscal calendars, reducing analytical value

4. **Limited Metadata**:
   - XBRL filings typically only reflect current fiscal year end dates
   - Historical fiscal year end information may not be accessible within the filing

The current implementation uses the most recent fiscal year end information available, which may lead to sub-optimal period selection when a company has recently changed its fiscal year. Users should be aware of this limitation when analyzing companies that have undergone fiscal year changes and may need to manually select appropriate periods using the `period_filter` parameter.

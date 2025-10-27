"""
Helper functions for common SEC filing analysis tasks.

These convenience wrappers provide simple, high-level access to EdgarTools functionality
for common SEC filing analysis patterns.
"""
from typing import Optional, List, Dict, Union
from edgar import get_filings, get_current_filings, Company

__all__ = [
    'get_filings_by_period',
    'get_today_filings',
    'get_revenue_trend',
    'get_filing_statement',
    'compare_companies_revenue',
]


def get_filings_by_period(
    year: int,
    quarter: int,
    form: Optional[str] = None,
    filing_date: Optional[str] = None
):
    """
    Get published filings for a specific time period from SEC quarterly indexes.

    This is a convenience wrapper around get_filings() with clear parameter names.

    Args:
        year: Year (e.g., 2023)
        quarter: Quarter 1-4 (1=Jan-Mar, 2=Apr-Jun, 3=Jul-Sep, 4=Oct-Dec)
        form: Optional form type filter (e.g., "10-K", "10-Q", "S-1")
        filing_date: Optional date or range filter (e.g., "2023-02-01:2023-02-28")

    Returns:
        Filings collection that can be further filtered or iterated

    Raises:
        HTTPError: If SEC API request fails
        ValueError: If year/quarter parameters are invalid

    Examples:
        >>> # Get all filings from Q1 2023
        >>> filings = get_filings_by_period(2023, 1)

        >>> # Get only 10-K filings from Q1 2023
        >>> filings = get_filings_by_period(2023, 1, form="10-K")

        >>> # Get S-1 filings from February 2023
        >>> filings = get_filings_by_period(
        ...     2023, 1,
        ...     form="S-1",
        ...     filing_date="2023-02-01:2023-02-28"
        ... )

    See Also:
        - get_filings() - The underlying raw API function
        - get_today_filings() - For real-time filings (last 24h)
        - Company.get_filings() - For company-specific filings
    """
    return get_filings(year, quarter, form=form, filing_date=filing_date)


def get_today_filings():
    """
    Get current filings from the last ~24 hours using SEC RSS feed.

    This is a convenience wrapper around get_current_filings() for simpler naming.

    Returns:
        CurrentFilings collection with recent submissions

    Raises:
        HTTPError: If SEC RSS feed request fails

    Examples:
        >>> # Get all recent filings
        >>> current = get_today_filings()
        >>> print(f"Found {len(current)} filings in last 24 hours")

        >>> # Filter for specific forms
        >>> reports = current.filter(form=["10-K", "10-Q"])

        >>> # Filter for specific companies
        >>> tech_filings = current.filter(ticker=["AAPL", "MSFT", "GOOGL"])

    See Also:
        - get_current_filings() - The underlying raw API function
        - get_filings_by_period() - For historical filings by quarter
    """
    return get_current_filings()


def get_revenue_trend(
    ticker: str,
    periods: int = 3,
    quarterly: bool = False
):
    """
    Get income statement trend for revenue analysis using Entity Facts API.

    This is the most efficient way to get multi-period financial data as it
    uses a single API call to retrieve comparative periods.

    Args:
        ticker: Company ticker symbol (e.g., "AAPL", "MSFT", "GOOGL")
        periods: Number of periods to retrieve (default: 3)
            - For annual: Gets last N fiscal years
            - For quarterly: Gets last N quarters
        quarterly: If True, get quarterly data; if False, get annual data
            (default: False for annual)

    Returns:
        MultiPeriodStatement object containing income statement data across
        multiple periods. Can be printed directly or accessed programmatically
        via .periods attribute.

    Raises:
        ValueError: If ticker is invalid or company not found
        HTTPError: If SEC Company Facts API request fails
        NoCompanyFactsFound: If company has no financial data

    Examples:
        >>> # Get 3 fiscal years of revenue data (default)
        >>> income = get_revenue_trend("AAPL")
        >>> print(income)  # Shows 3-year revenue trend

        >>> # Get 4 quarters of revenue data
        >>> quarterly = get_revenue_trend("TSLA", periods=4, quarterly=True)
        >>> print(quarterly)  # Shows 4-quarter trend

        >>> # Get 5 years for long-term analysis
        >>> long_term = get_revenue_trend("MSFT", periods=5)

        >>> # Access specific period programmatically
        >>> income = get_revenue_trend("AAPL", periods=3)
        >>> fy2023_data = income.periods[0]  # Most recent period

    See Also:
        - Company.income_statement() - The underlying raw API method
        - get_filing_statement() - For statement from specific filing
        - compare_companies_revenue() - For multi-company comparison
    """
    company = Company(ticker)
    return company.income_statement(periods=periods, annual=not quarterly)


def get_filing_statement(
    ticker: str,
    year: int,
    form: str,
    statement_type: str = "income"
):
    """
    Get a specific financial statement from a company's filing using XBRL.

    This provides the most detailed financial data from a specific filing,
    including all line items as filed. For multi-period comparison, consider
    using get_revenue_trend() instead (more efficient).

    Args:
        ticker: Company ticker symbol (e.g., "AAPL", "MSFT")
        year: Filing year (e.g., 2023)
        form: Form type (e.g., "10-K" for annual, "10-Q" for quarterly)
        statement_type: Type of statement to retrieve (default: "income")
            - "income" - Income statement
            - "balance" - Balance sheet
            - "cash_flow" - Cash flow statement

    Returns:
        Statement object with detailed line items from the filing.
        Can be printed directly or accessed programmatically.

    Raises:
        ValueError: If statement_type is not recognized or ticker invalid
        HTTPError: If SEC API request fails
        IndexError: If no filing found for the specified year/form
        XBRLError: If XBRL parsing fails

    Examples:
        >>> # Get income statement from Apple's 2023 10-K
        >>> income = get_filing_statement("AAPL", 2023, "10-K", "income")
        >>> print(income)

        >>> # Get balance sheet from quarterly filing
        >>> balance = get_filing_statement("AAPL", 2023, "10-Q", "balance")

        >>> # Get cash flow statement
        >>> cash_flow = get_filing_statement("MSFT", 2023, "10-K", "cash_flow")

        >>> # Get all three major statements
        >>> income = get_filing_statement("GOOGL", 2023, "10-K", "income")
        >>> balance = get_filing_statement("GOOGL", 2023, "10-K", "balance")
        >>> cash = get_filing_statement("GOOGL", 2023, "10-K", "cash_flow")

    See Also:
        - Filing.xbrl() - The underlying XBRL parsing method
        - get_revenue_trend() - More efficient for multi-period data
        - Company.get_filings() - For accessing filings directly
    """
    company = Company(ticker)
    filing = company.get_filings(year=year, form=form)[0]
    xbrl = filing.xbrl()

    if statement_type == "income":
        return xbrl.statements.income_statement()
    elif statement_type == "balance":
        return xbrl.statements.balance_sheet()
    elif statement_type == "cash_flow":
        return xbrl.statements.cash_flow_statement()
    else:
        raise ValueError(
            f"Unknown statement type: {statement_type}. "
            f"Must be 'income', 'balance', or 'cash_flow'"
        )


def compare_companies_revenue(
    tickers: Union[List[str], tuple],
    periods: int = 3
) -> Dict[str, 'MultiPeriodStatement']:
    """
    Compare revenue trends across multiple companies using Entity Facts API.

    This is the most efficient way to compare companies as it makes one API
    call per company (vs. multiple calls if using individual filings).

    Args:
        tickers: List or tuple of ticker symbols (e.g., ["AAPL", "MSFT", "GOOGL"])
        periods: Number of periods to compare (default: 3 fiscal years)

    Returns:
        Dictionary mapping ticker symbol to MultiPeriodStatement.
        Access individual company data via results["TICKER"].

    Raises:
        ValueError: If any ticker is invalid
        HTTPError: If SEC Company Facts API request fails for any company

    Examples:
        >>> # Compare three tech companies
        >>> results = compare_companies_revenue(["AAPL", "MSFT", "GOOGL"], periods=3)
        >>> print("Apple Revenue:")
        >>> print(results["AAPL"])
        >>> print("\nMicrosoft Revenue:")
        >>> print(results["MSFT"])

        >>> # Compare with tuple of tickers
        >>> results = compare_companies_revenue(("AAPL", "MSFT"), periods=5)

        >>> # Iterate through all results
        >>> results = compare_companies_revenue(["AAPL", "MSFT", "GOOGL"])
        >>> for ticker, statement in results.items():
        ...     print(f"\n{ticker} Revenue Trend:")
        ...     print(statement)

        >>> # Handle errors gracefully
        >>> tickers = ["AAPL", "INVALID", "MSFT"]
        >>> results = {}
        >>> for ticker in tickers:
        ...     try:
        ...         company = Company(ticker)
        ...         results[ticker] = company.income_statement(periods=3)
        ...     except Exception as e:
        ...         print(f"Error with {ticker}: {e}")

    See Also:
        - get_revenue_trend() - For single company analysis
        - Company.income_statement() - The underlying method used
    """
    results = {}
    for ticker in tickers:
        company = Company(ticker)
        results[ticker] = company.income_statement(periods=periods)
    return results

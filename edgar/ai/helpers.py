"""
Helper functions for common SEC filing analysis tasks.

These convenience wrappers provide simple, high-level access to EdgarTools functionality
for common SEC filing analysis patterns.
"""
from typing import Optional, List, Dict, Union
import pandas as pd
from edgar import get_filings, get_current_filings, Company

__all__ = [
    # Filing retrieval
    'get_filings_by_period',
    'get_today_filings',
    # Financial analysis
    'get_revenue_trend',
    'get_filing_statement',
    'compare_companies_revenue',
    # Industry and company subset filtering
    'filter_by_industry',
    'filter_by_company_subset',
    # Company subset convenience functions
    'get_companies_by_state',
    'get_pharmaceutical_companies',
    'get_biotechnology_companies',
    'get_software_companies',
    'get_semiconductor_companies',
    'get_banking_companies',
    'get_investment_companies',
    'get_insurance_companies',
    'get_real_estate_companies',
    'get_oil_gas_companies',
    'get_retail_companies',
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


def filter_by_industry(
    filings: 'Filings',
    sic: Optional[Union[int, List[int]]] = None,
    sic_range: Optional[tuple[int, int]] = None,
    sic_description_contains: Optional[str] = None,
) -> 'Filings':
    """
    Filter filings by industry using comprehensive company dataset (EFFICIENT).

    This REPLACES the old implementation which made N SEC API calls.
    New approach uses the comprehensive company dataset to identify target
    companies instantly (zero API calls), then filters filings by CIK.

    Performance Comparison:
        - OLD: ~9 minutes for Q4 2023 8-K (5,400 API calls)
        - NEW: ~30s first time, <1s cached (zero API calls)
        - 100x+ faster for large filing sets

    Args:
        filings: Filings collection to filter (from get_filings() or similar)
        sic: Single SIC code or list (e.g., 2834 or [2834, 2835, 2836])
        sic_range: SIC range tuple (e.g., (7300, 7400) for tech)
            Note: Use EXCLUSIVE upper bound (7400 means up to 7399)
        sic_description_contains: Search SIC description (e.g., "software")

    Returns:
        Filtered Filings collection containing only filings from companies
        in the specified industry

    Raises:
        ValueError: If no filter parameters provided

    Examples:
        >>> from edgar import get_filings
        >>> from edgar.ai.helpers import filter_by_industry
        >>>
        >>> # Filter filings to pharmaceutical companies
        >>> filings = get_filings(2023, 4, form="10-K")
        >>> pharma_10ks = filter_by_industry(filings, sic=2834)
        >>>
        >>> # Filter to technology companies (SIC 7300-7399)
        >>> filings = get_filings(2023, 4, form="8-K")
        >>> tech_8ks = filter_by_industry(filings, sic_range=(7300, 7400))
        >>>
        >>> # Filter using description search
        >>> filings = get_filings(2023, 4)
        >>> software = filter_by_industry(filings, sic_description_contains="software")
        >>>
        >>> # Combine with other filters
        >>> filings = get_filings(2023, 4, form="10-K")  # Pre-filter by form
        >>> nyse = filings.filter(exchange="NYSE")        # Pre-filter by exchange
        >>> pharma_nyse = filter_by_industry(nyse, sic=2834)  # Then by industry

    See Also:
        - filter_by_company_subset() - Filter using CompanySubset fluent interface
        - get_companies_by_industry() - Get company list directly (from edgar.reference)
        - Filings.filter() - The underlying filter method
    """
    from edgar.reference import get_companies_by_industry

    # Validate inputs
    if len(filings) == 0:
        return filings

    # Get companies in target industry (instant, local, zero API calls)
    companies = get_companies_by_industry(
        sic=sic,
        sic_range=sic_range,
        sic_description_contains=sic_description_contains
    )

    # Extract CIKs
    target_ciks = companies['cik'].tolist()

    if not target_ciks:
        # Return empty Filings collection with same structure
        return filings.filter(cik=[])

    # Filter filings using target CIKs (instant, PyArrow operation)
    return filings.filter(cik=target_ciks)


def filter_by_company_subset(
    filings: 'Filings',
    companies: Union['CompanySubset', pd.DataFrame]
) -> 'Filings':
    """
    Filter filings using a CompanySubset or company DataFrame.

    This enables advanced company filtering using the CompanySubset fluent
    interface (industry + state + sampling + etc) or any custom company DataFrame.

    Args:
        filings: Filings collection to filter
        companies: CompanySubset object or pandas DataFrame with 'cik' column

    Returns:
        Filtered Filings collection

    Raises:
        ValueError: If companies DataFrame doesn't have 'cik' column

    Examples:
        >>> from edgar import get_filings
        >>> from edgar.reference import CompanySubset
        >>> from edgar.ai.helpers import filter_by_company_subset
        >>>
        >>> # Get filings
        >>> filings = get_filings(2023, 4, form="10-K")
        >>>
        >>> # Filter to Delaware pharmaceutical companies, sample 10
        >>> companies = (CompanySubset()
        ...     .from_industry(sic=2834)
        ...     .from_state('DE')
        ...     .sample(10, random_state=42))
        >>> pharma_de_filings = filter_by_company_subset(filings, companies)
        >>>
        >>> # Or pass the DataFrame directly
        >>> from edgar.reference import get_pharmaceutical_companies
        >>> pharma = get_pharmaceutical_companies()
        >>> pharma_filings = filter_by_company_subset(filings, pharma)

    See Also:
        - filter_by_industry() - Simpler industry-only filtering
        - CompanySubset - Fluent interface for complex filtering (from edgar.reference)
    """
    from edgar.reference import CompanySubset

    # Extract DataFrame if CompanySubset passed
    if isinstance(companies, CompanySubset):
        companies = companies.get()

    # Extract CIKs
    if 'cik' not in companies.columns:
        raise ValueError("companies DataFrame must have 'cik' column")

    target_ciks = companies['cik'].tolist()

    if not target_ciks:
        return filings.filter(cik=[])

    return filings.filter(cik=target_ciks)


# ============================================================================
# Company Subset Convenience Functions
# ============================================================================

def get_companies_by_state(states: Union[str, List[str]]) -> pd.DataFrame:
    """
    Get companies by state of incorporation.

    Args:
        states: State code(s) (e.g., 'DE' or ['DE', 'NV'])

    Returns:
        DataFrame with companies incorporated in specified state(s).
        Columns: cik, ticker, name, exchange, sic, sic_description,
                 state_of_incorporation, state_of_incorporation_description,
                 fiscal_year_end, entity_type, ein

    Examples:
        >>> # Delaware companies (most common)
        >>> de_companies = get_companies_by_state('DE')
        >>> print(f"Found {len(de_companies)} Delaware companies")
        >>>
        >>> # Multiple states
        >>> tech_hubs = get_companies_by_state(['DE', 'CA', 'NV'])
        >>> print(tech_hubs[['ticker', 'name', 'state_of_incorporation']].head())

    See Also:
        - filter_by_company_subset() - Filter filings by company subset
        - CompanySubset.from_state() - Fluent interface (from edgar.reference)
    """
    from edgar.reference import get_companies_by_state as _get_by_state
    return _get_by_state(states)


def get_pharmaceutical_companies() -> pd.DataFrame:
    """
    Get all pharmaceutical companies (SIC 2834 - Pharmaceutical Preparations).

    Returns:
        DataFrame with pharmaceutical companies and comprehensive metadata.

    Examples:
        >>> pharma = get_pharmaceutical_companies()
        >>> print(f"Found {len(pharma)} pharmaceutical companies")
        >>> print(pharma[['ticker', 'name']].head())

    See Also:
        - get_biotechnology_companies() - Broader biotech category
        - filter_by_industry() - Filter filings by industry
    """
    from edgar.reference import get_pharmaceutical_companies as _get_pharma
    return _get_pharma()


def get_biotechnology_companies() -> pd.DataFrame:
    """
    Get all biotechnology companies (SIC 2833-2836).

    Returns:
        DataFrame with biotechnology companies and comprehensive metadata.

    Examples:
        >>> biotech = get_biotechnology_companies()
        >>> print(f"Found {len(biotech)} biotechnology companies")

    See Also:
        - get_pharmaceutical_companies() - Narrower pharma category
        - filter_by_industry() - Filter filings by industry
    """
    from edgar.reference import get_biotechnology_companies as _get_biotech
    return _get_biotech()


def get_software_companies() -> pd.DataFrame:
    """
    Get all software companies (SIC 7371-7379 - Computer Programming and Software).

    Returns:
        DataFrame with software companies and comprehensive metadata.

    Examples:
        >>> software = get_software_companies()
        >>> print(f"Found {len(software)} software companies")
        >>> # Get recent 10-K filings from software companies
        >>> from edgar import get_filings
        >>> filings = get_filings(2023, 4, form="10-K")
        >>> software_10ks = filter_by_company_subset(filings, software)

    See Also:
        - get_semiconductor_companies() - Hardware tech companies
        - filter_by_industry() - Filter filings by industry
    """
    from edgar.reference import get_software_companies as _get_software
    return _get_software()


def get_semiconductor_companies() -> pd.DataFrame:
    """
    Get all semiconductor companies (SIC 3674 - Semiconductors and Related Devices).

    Returns:
        DataFrame with semiconductor companies and comprehensive metadata.

    Examples:
        >>> semis = get_semiconductor_companies()
        >>> print(f"Found {len(semis)} semiconductor companies")

    See Also:
        - get_software_companies() - Software tech companies
        - filter_by_industry() - Filter filings by industry
    """
    from edgar.reference import get_semiconductor_companies as _get_semi
    return _get_semi()


def get_banking_companies() -> pd.DataFrame:
    """
    Get all banking companies (SIC 6020-6029 - Commercial Banks).

    Returns:
        DataFrame with banking companies and comprehensive metadata.

    Examples:
        >>> banks = get_banking_companies()
        >>> print(f"Found {len(banks)} banking companies")

    See Also:
        - get_investment_companies() - Investment/securities firms
        - get_insurance_companies() - Insurance companies
        - filter_by_industry() - Filter filings by industry
    """
    from edgar.reference import get_banking_companies as _get_banks
    return _get_banks()


def get_investment_companies() -> pd.DataFrame:
    """
    Get all investment companies (SIC 6200-6299 - Security and Commodity Brokers).

    Returns:
        DataFrame with investment companies and comprehensive metadata.

    Examples:
        >>> investments = get_investment_companies()
        >>> print(f"Found {len(investments)} investment companies")

    See Also:
        - get_banking_companies() - Commercial banks
        - get_insurance_companies() - Insurance companies
        - filter_by_industry() - Filter filings by industry
    """
    from edgar.reference import get_investment_companies as _get_invest
    return _get_invest()


def get_insurance_companies() -> pd.DataFrame:
    """
    Get all insurance companies (SIC 6300-6399 - Insurance Carriers).

    Returns:
        DataFrame with insurance companies and comprehensive metadata.

    Examples:
        >>> insurance = get_insurance_companies()
        >>> print(f"Found {len(insurance)} insurance companies")

    See Also:
        - get_banking_companies() - Commercial banks
        - get_investment_companies() - Investment firms
        - filter_by_industry() - Filter filings by industry
    """
    from edgar.reference import get_insurance_companies as _get_insurance
    return _get_insurance()


def get_real_estate_companies() -> pd.DataFrame:
    """
    Get all real estate companies (SIC 6500-6599 - Real Estate).

    Returns:
        DataFrame with real estate companies and comprehensive metadata.

    Examples:
        >>> real_estate = get_real_estate_companies()
        >>> print(f"Found {len(real_estate)} real estate companies")

    See Also:
        - filter_by_industry() - Filter filings by industry
    """
    from edgar.reference import get_real_estate_companies as _get_re
    return _get_re()


def get_oil_gas_companies() -> pd.DataFrame:
    """
    Get all oil and gas companies (SIC 1300-1399 - Oil and Gas Extraction).

    Returns:
        DataFrame with oil and gas companies and comprehensive metadata.

    Examples:
        >>> oil_gas = get_oil_gas_companies()
        >>> print(f"Found {len(oil_gas)} oil and gas companies")

    See Also:
        - filter_by_industry() - Filter filings by industry
    """
    from edgar.reference import get_oil_gas_companies as _get_oil_gas
    return _get_oil_gas()


def get_retail_companies() -> pd.DataFrame:
    """
    Get all retail companies (SIC 5200-5999 - Retail Trade).

    Returns:
        DataFrame with retail companies and comprehensive metadata.

    Examples:
        >>> retail = get_retail_companies()
        >>> print(f"Found {len(retail)} retail companies")

    See Also:
        - filter_by_industry() - Filter filings by industry
    """
    from edgar.reference import get_retail_companies as _get_retail
    return _get_retail()

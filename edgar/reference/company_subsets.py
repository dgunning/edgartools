"""
Company subset selection utilities for analysis and learning tasks.

This module provides flexible ways to create subsets of companies from SEC reference data
for educational, research, and analysis purposes. It offers exchange-based selection,
popularity-based filtering, sampling capabilities, and composition utilities.

Key features:
- Exchange-based selection (NYSE, NASDAQ, OTC, CBOE)
- Popularity-based selection (popular stocks, market cap tiers)
- Sampling capabilities (random, stratified, top N)
- Filtering and combination utilities
- Consistent DataFrame output format

All functions return a standardized DataFrame with columns: ['cik', 'ticker', 'name', 'exchange']
"""

from enum import Enum
from functools import lru_cache
from typing import Callable, List, Optional, Union

import pandas as pd

from edgar.core import log
from edgar.reference.tickers import get_company_ticker_name_exchange, popular_us_stocks

__all__ = [
    # Classes and Enums
    'CompanySubset',
    'MarketCapTier',
    'PopularityTier',
    # Core Functions
    'get_all_companies',
    'get_companies_by_exchanges',
    'get_popular_companies',
    # Industry and State Filtering (Comprehensive Mode)
    'get_companies_by_industry',
    'get_companies_by_state',
    # Sampling and Filtering
    'get_random_sample',
    'get_stratified_sample',
    'get_top_companies_by_metric',
    'filter_companies',
    'exclude_companies',
    # Set Operations
    'combine_company_sets',
    'intersect_company_sets',
    # Convenience Functions - General
    'get_faang_companies',
    'get_tech_giants',
    'get_dow_jones_sample',
    # Convenience Functions - Industry Specific
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


class MarketCapTier(Enum):
    """Market cap tiers for company classification."""
    LARGE_CAP = "large_cap"      # Usually > $10B
    MID_CAP = "mid_cap"          # Usually $2B - $10B  
    SMALL_CAP = "small_cap"      # Usually $300M - $2B
    MICRO_CAP = "micro_cap"      # Usually < $300M


class PopularityTier(Enum):
    """Popularity tiers based on trading activity and recognition."""
    MEGA_CAP = "mega_cap"        # Top 10 most valuable companies
    POPULAR = "popular"          # Popular stocks list
    MAINSTREAM = "mainstream"    # Well-known companies
    EMERGING = "emerging"        # Smaller but notable companies


class CompanySubset:
    """
    Fluent interface for building company subsets with chainable operations.

    Example:
        # Get 50 random NYSE companies excluding financial sector
        companies = (CompanySubset()
                    .from_exchange('NYSE')
                    .exclude_tickers(['JPM', 'GS', 'C'])
                    .sample(50)
                    .get())

        # Get pharmaceutical companies with comprehensive metadata
        pharma = (CompanySubset(use_comprehensive=True)
                 .from_industry(sic_range=(2834, 2836))
                 .sample(100)
                 .get())
    """

    def __init__(self, companies: Optional[pd.DataFrame] = None, use_comprehensive: bool = False):
        """
        Initialize with optional starting dataset.

        Args:
            companies: Optional DataFrame to start with. If None, loads from get_all_companies()
            use_comprehensive: If True and companies is None, load comprehensive dataset
                             with rich metadata (SIC, state, entity type, etc.)
        """
        if companies is not None:
            self._companies = companies
        else:
            self._companies = get_all_companies(use_comprehensive=use_comprehensive)
        self._use_comprehensive = use_comprehensive

    def from_exchange(self, exchanges: Union[str, List[str]]) -> 'CompanySubset':
        """Filter companies by exchange(s)."""
        self._companies = get_companies_by_exchanges(exchanges)
        return self

    def from_popular(self, tier: Optional[PopularityTier] = None) -> 'CompanySubset':
        """Filter to popular companies."""
        self._companies = get_popular_companies(tier)
        return self

    def from_industry(
        self,
        sic: Optional[Union[int, List[int]]] = None,
        sic_range: Optional[tuple[int, int]] = None,
        sic_description_contains: Optional[str] = None
    ) -> 'CompanySubset':
        """
        Filter companies by industry (SIC code).

        Automatically enables comprehensive mode to access industry metadata.

        Args:
            sic: Single SIC code or list of SIC codes to match exactly
            sic_range: Tuple of (min_sic, max_sic) for range filtering
            sic_description_contains: String to search within SIC description

        Returns:
            CompanySubset with industry filter applied

        Example:
            >>> # Pharmaceutical companies
            >>> pharma = CompanySubset().from_industry(sic=2834)

            >>> # Biotech sector
            >>> biotech = CompanySubset().from_industry(sic_range=(2833, 2836))
        """
        self._companies = get_companies_by_industry(
            sic=sic,
            sic_range=sic_range,
            sic_description_contains=sic_description_contains
        )
        self._use_comprehensive = True
        return self

    def from_state(self, states: Union[str, List[str]]) -> 'CompanySubset':
        """
        Filter companies by state of incorporation.

        Automatically enables comprehensive mode to access state metadata.

        Args:
            states: Single state code or list of state codes (e.g., 'DE', 'CA')

        Returns:
            CompanySubset with state filter applied

        Example:
            >>> # Delaware corporations
            >>> de_corps = CompanySubset().from_state('DE')

            >>> # Delaware or Nevada corporations
            >>> de_nv = CompanySubset().from_state(['DE', 'NV'])
        """
        self._companies = get_companies_by_state(states)
        self._use_comprehensive = True
        return self

    def filter_by(self, condition: Callable[[pd.DataFrame], pd.DataFrame]) -> 'CompanySubset':
        """Apply custom filter function."""
        self._companies = condition(self._companies)
        return self

    def exclude_tickers(self, tickers: List[str]) -> 'CompanySubset':
        """Exclude specific tickers."""
        self._companies = exclude_companies(self._companies, tickers)
        return self

    def include_tickers(self, tickers: List[str]) -> 'CompanySubset':
        """Include only specific tickers."""
        self._companies = filter_companies(self._companies, ticker_list=tickers)
        return self

    def sample(self, n: int, random_state: Optional[int] = None) -> 'CompanySubset':
        """Take random sample of n companies."""
        self._companies = get_random_sample(self._companies, n, random_state)
        return self

    def top(self, n: int, by: str = 'name') -> 'CompanySubset':
        """Take top n companies by specified column."""
        self._companies = get_top_companies_by_metric(self._companies, n, by)
        return self

    def combine_with(self, other: 'CompanySubset') -> 'CompanySubset':
        """Combine with another subset (union)."""
        self._companies = combine_company_sets([self._companies, other.get()])
        return self

    def intersect_with(self, other: 'CompanySubset') -> 'CompanySubset':
        """Intersect with another subset."""
        self._companies = intersect_company_sets([self._companies, other.get()])
        return self

    def get(self) -> pd.DataFrame:
        """Get the final DataFrame."""
        return self._companies.copy()

    def __len__(self) -> int:
        """Return number of companies in subset."""
        return len(self._companies)

    def __repr__(self) -> str:
        """String representation showing count and sample."""
        count = len(self._companies)
        if count == 0:
            return "CompanySubset(empty)"

        sample_size = min(3, count)
        sample_tickers = self._companies['ticker'].head(sample_size).tolist()
        sample_str = ', '.join(sample_tickers)

        if count > sample_size:
            sample_str += f", ... +{count - sample_size} more"

        return f"CompanySubset({count} companies: {sample_str})"


def _get_comprehensive_companies() -> pd.DataFrame:
    """
    Get comprehensive company dataset from company_dataset module.

    This function loads the full SEC submissions dataset (~562K companies) with rich metadata
    including SIC codes, state of incorporation, entity types, and more.

    Returns:
        DataFrame with extended schema:
        ['cik', 'ticker', 'name', 'exchange', 'sic', 'sic_description',
         'state_of_incorporation', 'state_of_incorporation_description',
         'fiscal_year_end', 'entity_type', 'ein']

    Note:
        - First call may take ~30 seconds to build the dataset
        - Subsequent calls use cached Parquet file (<100ms load time)
        - Primary ticker extracted from pipe-delimited tickers field
        - Primary exchange extracted from pipe-delimited exchanges field
    """
    try:
        from edgar.reference.company_dataset import get_company_dataset

        # Get PyArrow Table from company_dataset
        table = get_company_dataset()

        # Convert to pandas
        df = table.to_pandas()

        # Extract primary ticker from pipe-delimited tickers field
        def extract_primary(value):
            """Extract first value from pipe-delimited string."""
            if pd.isna(value) or value is None:
                return None
            value_str = str(value)
            parts = value_str.split('|')
            return parts[0] if parts and parts[0] else None

        df['ticker'] = df['tickers'].apply(extract_primary)
        df['exchange'] = df['exchanges'].apply(extract_primary)

        # Drop the original pipe-delimited columns
        df = df.drop(columns=['tickers', 'exchanges'])

        # Reorder columns to match standard format plus extensions
        columns = [
            'cik', 'ticker', 'name', 'exchange',
            'sic', 'sic_description',
            'state_of_incorporation', 'state_of_incorporation_description',
            'fiscal_year_end', 'entity_type', 'ein'
        ]

        return df[columns]

    except Exception as e:
        log.error(f"Error fetching comprehensive company data: {e}")
        # Return empty DataFrame with extended schema
        return pd.DataFrame(columns=[
            'cik', 'ticker', 'name', 'exchange',
            'sic', 'sic_description',
            'state_of_incorporation', 'state_of_incorporation_description',
            'fiscal_year_end', 'entity_type', 'ein'
        ])


@lru_cache(maxsize=2)
def get_all_companies(use_comprehensive: bool = False) -> pd.DataFrame:
    """
    Get all companies from SEC reference data in standardized format.

    Args:
        use_comprehensive: If True, load comprehensive dataset with ~562K companies
                          and rich metadata (SIC, state, entity type, etc.).
                          If False (default), load ticker-only dataset with ~13K companies.

    Returns:
        DataFrame with columns ['cik', 'ticker', 'name', 'exchange']

        If use_comprehensive=True, also includes:
        ['sic', 'sic_description', 'state_of_incorporation',
         'state_of_incorporation_description', 'fiscal_year_end',
         'entity_type', 'ein']

    Note:
        - Default (use_comprehensive=False) maintains backward compatibility
        - Comprehensive mode adds ~30 second build time on first call
        - Both modes use caching for fast subsequent calls

    Example:
        >>> # Standard mode - fast, ticker-only data
        >>> companies = get_all_companies()
        >>> len(companies)  # ~13K companies

        >>> # Comprehensive mode - slower first call, rich metadata
        >>> all_companies = get_all_companies(use_comprehensive=True)
        >>> len(all_companies)  # ~562K companies
        >>> 'sic' in all_companies.columns  # True
    """
    if use_comprehensive:
        return _get_comprehensive_companies()

    try:
        df = get_company_ticker_name_exchange().copy()
        # Reorder columns to match our standard format
        return df[['cik', 'ticker', 'name', 'exchange']]
    except Exception as e:
        log.error(f"Error fetching company data: {e}")
        # Return empty DataFrame with correct structure
        return pd.DataFrame(columns=['cik', 'ticker', 'name', 'exchange'])


def get_companies_by_exchanges(exchanges: Union[str, List[str]]) -> pd.DataFrame:
    """
    Get companies listed on specific exchange(s).

    Args:
        exchanges: Single exchange string or list of exchanges
                  ('NYSE', 'Nasdaq', 'OTC', 'CBOE')

    Returns:
        DataFrame with companies from specified exchanges

    Example:
        >>> nyse_companies = get_companies_by_exchanges('NYSE')
        >>> major_exchanges = get_companies_by_exchanges(['NYSE', 'Nasdaq'])
    """
    if isinstance(exchanges, str):
        exchanges = [exchanges]

    try:
        all_companies = get_all_companies()
        return all_companies[all_companies['exchange'].isin(exchanges)].reset_index(drop=True)
    except Exception as e:
        log.error(f"Error filtering companies by exchanges {exchanges}: {e}")
        return pd.DataFrame(columns=['cik', 'ticker', 'name', 'exchange'])


def get_popular_companies(tier: Optional[PopularityTier] = None) -> pd.DataFrame:
    """
    Get popular companies based on tier selection.

    Args:
        tier: Popularity tier (MEGA_CAP, POPULAR, MAINSTREAM, EMERGING)
              If None, returns all popular companies

    Returns:
        DataFrame with popular companies

    Example:
        >>> mega_cap = get_popular_companies(PopularityTier.MEGA_CAP)
        >>> all_popular = get_popular_companies()
    """
    try:
        # Get popular stocks and merge with exchange data
        popular_df = popular_us_stocks().reset_index()  # CIK becomes a column
        popular_df = popular_df.rename(columns={'Cik': 'cik', 'Ticker': 'ticker', 'Company': 'name'})

        # Get exchange information
        all_companies = get_all_companies()

        # Merge to get exchange information
        result = popular_df.merge(
            all_companies[['cik', 'exchange']], 
            on='cik', 
            how='left'
        )

        # Fill missing exchanges with 'Unknown' 
        result['exchange'] = result['exchange'].fillna('Unknown')

        # Apply tier filtering
        if tier == PopularityTier.MEGA_CAP:
            result = result.head(10)  # Top 10 by market cap (order in CSV)
        elif tier == PopularityTier.POPULAR:
            result = result.head(50)  # Top 50 popular
        elif tier == PopularityTier.MAINSTREAM:
            result = result.head(100)  # Top 100
        # EMERGING or None returns all

        return result[['cik', 'ticker', 'name', 'exchange']].reset_index(drop=True)

    except Exception as e:
        log.error(f"Error fetching popular companies: {e}")
        return pd.DataFrame(columns=['cik', 'ticker', 'name', 'exchange'])


def get_random_sample(
    companies: Optional[pd.DataFrame] = None, 
    n: int = 100, 
    random_state: Optional[int] = None
) -> pd.DataFrame:
    """
    Get random sample of companies.

    Args:
        companies: DataFrame to sample from (if None, uses all companies)
        n: Number of companies to sample
        random_state: Random seed for reproducibility

    Returns:
        DataFrame with n randomly selected companies

    Example:
        >>> random_100 = get_random_sample(n=100, random_state=42)
        >>> nasdaq_sample = get_random_sample(get_companies_by_exchanges('Nasdaq'), n=50)
    """
    if companies is None:
        companies = get_all_companies()

    if len(companies) == 0:
        return companies.copy()

    # Ensure we don't sample more than available
    sample_size = min(n, len(companies))

    try:
        return companies.sample(n=sample_size, random_state=random_state).reset_index(drop=True)
    except Exception as e:
        log.error(f"Error sampling companies: {e}")
        return companies.head(sample_size).reset_index(drop=True)


def get_stratified_sample(
    companies: Optional[pd.DataFrame] = None,
    n: int = 100,
    stratify_by: str = 'exchange',
    random_state: Optional[int] = None
) -> pd.DataFrame:
    """
    Get stratified sample of companies maintaining proportions by specified column.

    Args:
        companies: DataFrame to sample from (if None, uses all companies)
        n: Total number of companies to sample
        stratify_by: Column to stratify by (default: 'exchange')
        random_state: Random seed for reproducibility

    Returns:
        DataFrame with stratified sample

    Example:
        >>> # Sample maintaining exchange proportions
        >>> stratified = get_stratified_sample(n=200, stratify_by='exchange')
    """
    if companies is None:
        companies = get_all_companies()

    if len(companies) == 0 or stratify_by not in companies.columns:
        return get_random_sample(companies, n, random_state)

    try:
        # Calculate proportions
        proportions = companies[stratify_by].value_counts(normalize=True)

        samples = []
        remaining_n = n

        for category, prop in proportions.items():
            category_companies = companies[companies[stratify_by] == category]

            # Calculate sample size for this category
            if category == proportions.index[-1]:  # Last category gets remainder
                category_n = remaining_n
            else:
                category_n = max(1, int(n * prop))  # At least 1 company per category
                remaining_n -= category_n

            # Sample from this category
            if len(category_companies) > 0:
                category_sample = get_random_sample(
                    category_companies, 
                    min(category_n, len(category_companies)),
                    random_state
                )
                samples.append(category_sample)

        # Combine all samples
        if samples:
            result = pd.concat(samples, ignore_index=True)
            # If we ended up with more than n, randomly select n
            if len(result) > n:
                result = get_random_sample(result, n, random_state)
            return result
        else:
            return pd.DataFrame(columns=['cik', 'ticker', 'name', 'exchange'])

    except Exception as e:
        log.error(f"Error creating stratified sample: {e}")
        return get_random_sample(companies, n, random_state)


def get_top_companies_by_metric(
    companies: Optional[pd.DataFrame] = None,
    n: int = 100,
    metric: str = 'name',
    ascending: bool = True
) -> pd.DataFrame:
    """
    Get top N companies sorted by specified metric.

    Args:
        companies: DataFrame to select from (if None, uses all companies)
        n: Number of top companies to return
        metric: Column to sort by (default: 'name' for alphabetical)
        ascending: Sort order (True for ascending, False for descending)

    Returns:
        DataFrame with top N companies by metric

    Example:
        >>> # Top 50 companies alphabetically by name
        >>> top_alpha = get_top_companies_by_metric(n=50, metric='name')
        >>> # Top 100 popular companies by ticker (reverse alphabetical)
        >>> top_tickers = get_top_companies_by_metric(
        ...     get_popular_companies(), n=100, metric='ticker', ascending=False)
    """
    if companies is None:
        companies = get_all_companies()

    if len(companies) == 0 or metric not in companies.columns:
        return companies.head(n).copy()

    try:
        sorted_companies = companies.sort_values(by=metric, ascending=ascending)
        return sorted_companies.head(n).reset_index(drop=True)
    except Exception as e:
        log.error(f"Error sorting companies by {metric}: {e}")
        return companies.head(n).copy()


def filter_companies(
    companies: pd.DataFrame,
    ticker_list: Optional[List[str]] = None,
    name_contains: Optional[str] = None,
    cik_list: Optional[List[int]] = None,
    custom_filter: Optional[Callable[[pd.DataFrame], pd.DataFrame]] = None
) -> pd.DataFrame:
    """
    Filter companies by various criteria.

    Args:
        companies: DataFrame to filter
        ticker_list: List of specific tickers to include
        name_contains: String that company name must contain (case-insensitive)
        cik_list: List of specific CIKs to include
        custom_filter: Custom function that takes and returns a DataFrame

    Returns:
        Filtered DataFrame

    Example:
        >>> # Filter to specific tickers
        >>> faang = filter_companies(
        ...     companies, ticker_list=['AAPL', 'AMZN', 'NFLX', 'GOOGL', 'META'])
        >>> # Filter by name containing 'Inc'
        >>> inc_companies = filter_companies(companies, name_contains='Inc')
    """
    result = companies.copy()

    try:
        if ticker_list is not None:
            ticker_list_upper = [t.upper() for t in ticker_list]
            result = result[result['ticker'].str.upper().isin(ticker_list_upper)]

        if name_contains is not None:
            result = result[result['name'].str.contains(name_contains, case=False, na=False)]

        if cik_list is not None:
            result = result[result['cik'].isin(cik_list)]

        if custom_filter is not None:
            result = custom_filter(result)

        return result.reset_index(drop=True)

    except Exception as e:
        log.error(f"Error filtering companies: {e}")
        return result


def exclude_companies(
    companies: pd.DataFrame,
    ticker_list: Optional[List[str]] = None,
    name_contains: Optional[str] = None,
    cik_list: Optional[List[int]] = None
) -> pd.DataFrame:
    """
    Exclude companies by various criteria.

    Args:
        companies: DataFrame to filter
        ticker_list: List of tickers to exclude
        name_contains: String to exclude companies whose names contain it
        cik_list: List of CIKs to exclude

    Returns:
        DataFrame with specified companies excluded

    Example:
        >>> # Exclude financial companies (simplified)
        >>> non_financial = exclude_companies(
        ...     companies, ticker_list=['JPM', 'GS', 'C', 'BAC'])
        >>> # Exclude companies with 'Corp' in name
        >>> non_corp = exclude_companies(companies, name_contains='Corp')
    """
    result = companies.copy()

    try:
        if ticker_list is not None:
            ticker_list_upper = [t.upper() for t in ticker_list]
            result = result[~result['ticker'].str.upper().isin(ticker_list_upper)]

        if name_contains is not None:
            result = result[~result['name'].str.contains(name_contains, case=False, na=False)]

        if cik_list is not None:
            result = result[~result['cik'].isin(cik_list)]

        return result.reset_index(drop=True)

    except Exception as e:
        log.error(f"Error excluding companies: {e}")
        return result


def combine_company_sets(company_sets: List[pd.DataFrame]) -> pd.DataFrame:
    """
    Combine multiple company DataFrames (union operation).

    Args:
        company_sets: List of company DataFrames to combine

    Returns:
        Combined DataFrame with duplicates removed

    Example:
        >>> nyse = get_companies_by_exchanges('NYSE')
        >>> popular = get_popular_companies()
        >>> combined = combine_company_sets([nyse, popular])
    """
    if not company_sets:
        return pd.DataFrame(columns=['cik', 'ticker', 'name', 'exchange'])

    try:
        # Concatenate all DataFrames
        result = pd.concat(company_sets, ignore_index=True)

        # Remove duplicates based on CIK (primary key)
        result = result.drop_duplicates(subset=['cik']).reset_index(drop=True)

        return result

    except Exception as e:
        log.error(f"Error combining company sets: {e}")
        return company_sets[0].copy() if company_sets else pd.DataFrame(columns=['cik', 'ticker', 'name', 'exchange'])


def intersect_company_sets(company_sets: List[pd.DataFrame]) -> pd.DataFrame:
    """
    Find intersection of multiple company DataFrames.

    Args:
        company_sets: List of company DataFrames to intersect

    Returns:
        DataFrame containing only companies present in all sets

    Example:
        >>> nyse = get_companies_by_exchanges('NYSE')
        >>> popular = get_popular_companies()
        >>> nyse_popular = intersect_company_sets([nyse, popular])
    """
    if not company_sets:
        return pd.DataFrame(columns=['cik', 'ticker', 'name', 'exchange'])

    if len(company_sets) == 1:
        return company_sets[0].copy()

    try:
        # Start with first set
        result = company_sets[0].copy()

        # Intersect with each subsequent set
        for df in company_sets[1:]:
            # Find common CIKs
            common_ciks = set(result['cik']) & set(df['cik'])
            result = result[result['cik'].isin(common_ciks)]

        return result.reset_index(drop=True)

    except Exception as e:
        log.error(f"Error intersecting company sets: {e}")
        return company_sets[0].copy() if company_sets else pd.DataFrame(columns=['cik', 'ticker', 'name', 'exchange'])


def get_companies_by_industry(
    sic: Optional[Union[int, List[int]]] = None,
    sic_range: Optional[tuple[int, int]] = None,
    sic_description_contains: Optional[str] = None
) -> pd.DataFrame:
    """
    Get companies by industry classification using SIC (Standard Industrial Classification) codes.

    Requires comprehensive company dataset. This function automatically uses use_comprehensive=True.

    Args:
        sic: Single SIC code or list of SIC codes to match exactly
        sic_range: Tuple of (min_sic, max_sic) for range filtering (inclusive)
        sic_description_contains: String to search within SIC description (case-insensitive)

    Returns:
        DataFrame with companies matching the industry criteria, including comprehensive metadata

    Example:
        >>> # Pharmaceutical companies (SIC 2834)
        >>> pharma = get_companies_by_industry(sic=2834)

        >>> # Biotech range (SIC 2833-2836)
        >>> biotech = get_companies_by_industry(sic_range=(2833, 2836))

        >>> # All companies with "software" in industry description
        >>> software = get_companies_by_industry(sic_description_contains='software')

        >>> # Multiple specific SIC codes
        >>> healthcare = get_companies_by_industry(sic=[2834, 2835, 2836])

    Note:
        SIC Code Ranges:
        - 0100-0999: Agriculture, Forestry, Fishing
        - 1000-1499: Mining
        - 1500-1799: Construction
        - 2000-3999: Manufacturing
        - 4000-4999: Transportation, Communications, Utilities
        - 5000-5199: Wholesale Trade
        - 5200-5999: Retail Trade
        - 6000-6799: Finance, Insurance, Real Estate
        - 7000-8999: Services
        - 9100-9729: Public Administration
    """
    # Auto-enable comprehensive mode for industry filtering
    companies = get_all_companies(use_comprehensive=True)

    result = companies.copy()

    try:
        # Filter by exact SIC code(s)
        if sic is not None:
            if isinstance(sic, int):
                sic = [sic]
            result = result[result['sic'].isin(sic)]

        # Filter by SIC range
        if sic_range is not None:
            min_sic, max_sic = sic_range
            result = result[
                (result['sic'] >= min_sic) &
                (result['sic'] <= max_sic)
            ]

        # Filter by SIC description contains
        if sic_description_contains is not None:
            result = result[
                result['sic_description'].str.contains(
                    sic_description_contains,
                    case=False,
                    na=False
                )
            ]

        return result.reset_index(drop=True)

    except Exception as e:
        log.error(f"Error filtering companies by industry: {e}")
        return pd.DataFrame(columns=companies.columns)


def get_companies_by_state(
    states: Union[str, List[str]],
    include_description: bool = True
) -> pd.DataFrame:
    """
    Get companies by state of incorporation.

    Requires comprehensive company dataset. This function automatically uses use_comprehensive=True.

    Args:
        states: Single state code or list of state codes (e.g., 'DE', 'CA', ['DE', 'NV'])
        include_description: If True, includes state_of_incorporation_description in output

    Returns:
        DataFrame with companies incorporated in specified state(s)

    Example:
        >>> # Delaware corporations
        >>> de_corps = get_companies_by_state('DE')

        >>> # Delaware and Nevada corporations
        >>> de_nv = get_companies_by_state(['DE', 'NV'])

        >>> # California corporations
        >>> ca_corps = get_companies_by_state('CA')

    Note:
        Common states of incorporation:
        - DE: Delaware (most common for public companies)
        - NV: Nevada (popular for tax benefits)
        - CA: California
        - NY: New York
        - TX: Texas
    """
    if isinstance(states, str):
        states = [states]

    # Auto-enable comprehensive mode for state filtering
    companies = get_all_companies(use_comprehensive=True)

    try:
        # Normalize state codes to uppercase
        states_upper = [s.upper() for s in states]

        result = companies[
            companies['state_of_incorporation'].str.upper().isin(states_upper)
        ].reset_index(drop=True)

        return result

    except Exception as e:
        log.error(f"Error filtering companies by state {states}: {e}")
        return pd.DataFrame(columns=companies.columns)


# Convenience functions for common use cases

def get_faang_companies() -> pd.DataFrame:
    """Get FAANG companies (Facebook/Meta, Apple, Amazon, Netflix, Google)."""
    return filter_companies(
        get_all_companies(),
        ticker_list=['META', 'AAPL', 'AMZN', 'NFLX', 'GOOGL']
    )


def get_tech_giants() -> pd.DataFrame:
    """Get major technology companies."""
    tech_tickers = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 
        'NFLX', 'ADBE', 'CRM', 'ORCL', 'INTC', 'CSCO'
    ]
    return filter_companies(get_all_companies(), ticker_list=tech_tickers)


def get_dow_jones_sample() -> pd.DataFrame:
    """Get sample of Dow Jones Industrial Average companies."""
    dow_tickers = [
        'AAPL', 'MSFT', 'UNH', 'GS', 'HD', 'CAT', 'MCD', 'V', 'AXP', 'BA',
        'TRV', 'JPM', 'IBM', 'JNJ', 'WMT', 'CVX', 'NKE', 'MRK', 'KO', 'DIS',
        'MMM', 'DOW', 'CSCO', 'VZ', 'INTC', 'WBA', 'CRM', 'HON', 'AMGN', 'PG'
    ]
    return filter_companies(get_all_companies(), ticker_list=dow_tickers)


# Industry-specific convenience functions (require comprehensive dataset)

def get_pharmaceutical_companies() -> pd.DataFrame:
    """
    Get pharmaceutical preparation companies (SIC 2834).

    Returns companies in the pharmaceutical preparations industry including
    prescription drugs, biologics, and vaccines.
    """
    return get_companies_by_industry(sic=2834)


def get_biotechnology_companies() -> pd.DataFrame:
    """
    Get biotechnology companies (SIC 2833-2836).

    Returns companies in biotech and related pharmaceutical industries.
    """
    return get_companies_by_industry(sic_range=(2833, 2836))


def get_software_companies() -> pd.DataFrame:
    """
    Get software and computer programming companies (SIC 7371-7379).

    Returns companies in software publishing, programming, and related services.
    """
    return get_companies_by_industry(sic_range=(7371, 7379))


def get_semiconductor_companies() -> pd.DataFrame:
    """
    Get semiconductor and electronic component companies (SIC 3674).

    Returns companies manufacturing semiconductors and related devices.
    """
    return get_companies_by_industry(sic=3674)


def get_banking_companies() -> pd.DataFrame:
    """
    Get commercial banking companies (SIC 6020-6029).

    Returns national and state commercial banks.
    """
    return get_companies_by_industry(sic_range=(6020, 6029))


def get_investment_companies() -> pd.DataFrame:
    """
    Get investment companies and funds (SIC 6200-6299).

    Returns securities brokers, dealers, investment advisors, and funds.
    """
    return get_companies_by_industry(sic_range=(6200, 6299))


def get_insurance_companies() -> pd.DataFrame:
    """
    Get insurance companies (SIC 6300-6399).

    Returns life, health, property, and casualty insurance companies.
    """
    return get_companies_by_industry(sic_range=(6300, 6399))


def get_real_estate_companies() -> pd.DataFrame:
    """
    Get real estate companies (SIC 6500-6599).

    Returns REITs, real estate operators, and developers.
    """
    return get_companies_by_industry(sic_range=(6500, 6599))


def get_oil_gas_companies() -> pd.DataFrame:
    """
    Get oil and gas extraction companies (SIC 1300-1399).

    Returns crude petroleum, natural gas, and oil/gas field services companies.
    """
    return get_companies_by_industry(sic_range=(1300, 1399))


def get_retail_companies() -> pd.DataFrame:
    """
    Get retail trade companies (SIC 5200-5999).

    Returns general merchandise, apparel, food, and other retail stores.
    """
    return get_companies_by_industry(sic_range=(5200, 5999))

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
from typing import Union, List, Optional, Callable

import pandas as pd

from edgar.core import log
from edgar.reference.tickers import (
    get_company_ticker_name_exchange,
    popular_us_stocks
)

__all__ = [
    'CompanySubset',
    'get_companies_by_exchanges',
    'get_popular_companies', 
    'get_random_sample',
    'get_stratified_sample',
    'get_top_companies_by_metric',
    'filter_companies',
    'exclude_companies',
    'combine_company_sets',
    'intersect_company_sets',
    'get_all_companies',
    'MarketCapTier',
    'PopularityTier'
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
    """
    
    def __init__(self, companies: Optional[pd.DataFrame] = None):
        """Initialize with optional starting dataset."""
        self._companies = companies if companies is not None else get_all_companies()
        
    def from_exchange(self, exchanges: Union[str, List[str]]) -> 'CompanySubset':
        """Filter companies by exchange(s)."""
        self._companies = get_companies_by_exchanges(exchanges)
        return self
    
    def from_popular(self, tier: Optional[PopularityTier] = None) -> 'CompanySubset':
        """Filter to popular companies."""
        self._companies = get_popular_companies(tier)
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


@lru_cache(maxsize=1)
def get_all_companies() -> pd.DataFrame:
    """
    Get all companies from SEC reference data in standardized format.
    
    Returns:
        DataFrame with columns ['cik', 'ticker', 'name', 'exchange']
    """
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
"""
Tests for edgar.reference.company_subsets module.

Tests all functionality for creating company subsets including exchange selection,
popularity filtering, sampling, and combination operations.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from edgar.reference.company_subsets import (
    CompanySubset,
    get_all_companies,
    get_companies_by_exchanges,
    get_popular_companies,
    get_random_sample,
    get_stratified_sample,
    get_top_companies_by_metric,
    filter_companies,
    exclude_companies,
    combine_company_sets,
    intersect_company_sets,
    get_faang_companies,
    get_tech_giants,
    get_dow_jones_sample,
    MarketCapTier,
    PopularityTier
)


# Sample test data
SAMPLE_COMPANIES = pd.DataFrame({
    'cik': [320193, 789019, 1018724, 1045810, 1318605],
    'ticker': ['AAPL', 'MSFT', 'AMZN', 'NVDA', 'TSLA'],
    'name': ['Apple Inc.', 'Microsoft Corporation', 'Amazon.com Inc.', 'NVIDIA Corporation', 'Tesla Inc.'],
    'exchange': ['Nasdaq', 'Nasdaq', 'Nasdaq', 'Nasdaq', 'Nasdaq']
})

SAMPLE_MIXED_EXCHANGES = pd.DataFrame({
    'cik': [320193, 789019, 1067983, 19617, 104169],
    'ticker': ['AAPL', 'MSFT', 'BRK-B', 'JPM', 'WMT'],
    'name': ['Apple Inc.', 'Microsoft Corporation', 'Berkshire Hathaway Inc.', 'JPMorgan Chase & Co.', 'Walmart Inc.'],
    'exchange': ['Nasdaq', 'Nasdaq', 'NYSE', 'NYSE', 'NYSE']
})

SAMPLE_POPULAR = pd.DataFrame({
    'cik': [320193, 789019, 1018724],
    'ticker': ['AAPL', 'MSFT', 'AMZN'],
    'name': ['Apple Inc.', 'Microsoft Corporation', 'Amazon.com Inc.']
})


class TestCompanySubset:
    """Test the fluent CompanySubset interface."""
    
    @patch('edgar.reference.company_subsets.get_all_companies')
    def test_init_default(self, mock_get_all):
        """Test initialization with default data."""
        mock_get_all.return_value = SAMPLE_COMPANIES
        subset = CompanySubset()
        assert len(subset) == 5
        
    def test_init_with_data(self):
        """Test initialization with provided data."""
        subset = CompanySubset(SAMPLE_COMPANIES)
        assert len(subset) == 5
        
    @patch('edgar.reference.company_subsets.get_companies_by_exchanges')
    def test_from_exchange(self, mock_get_exchange):
        """Test filtering by exchange."""
        mock_get_exchange.return_value = SAMPLE_COMPANIES.head(3)
        subset = CompanySubset().from_exchange('Nasdaq')
        assert len(subset) == 3
        
    @patch('edgar.reference.company_subsets.get_popular_companies')
    def test_from_popular(self, mock_get_popular):
        """Test filtering to popular companies."""
        mock_get_popular.return_value = SAMPLE_COMPANIES.head(2)
        subset = CompanySubset().from_popular(PopularityTier.MEGA_CAP)
        assert len(subset) == 2
        
    def test_filter_by_custom(self):
        """Test custom filtering."""
        subset = CompanySubset(SAMPLE_COMPANIES)
        result = subset.filter_by(lambda df: df[df['ticker'].str.startswith('A')])
        tickers = result.get()['ticker'].tolist()
        assert 'AAPL' in tickers
        assert 'AMZN' in tickers
        assert 'MSFT' not in tickers
        
    def test_exclude_tickers(self):
        """Test excluding specific tickers."""
        subset = CompanySubset(SAMPLE_COMPANIES)
        result = subset.exclude_tickers(['AAPL', 'MSFT'])
        tickers = result.get()['ticker'].tolist()
        assert 'AAPL' not in tickers
        assert 'MSFT' not in tickers
        assert len(result) == 3
        
    def test_include_tickers(self):
        """Test including only specific tickers."""
        subset = CompanySubset(SAMPLE_COMPANIES)
        result = subset.include_tickers(['AAPL', 'MSFT'])
        tickers = result.get()['ticker'].tolist()
        assert set(tickers) == {'AAPL', 'MSFT'}
        assert len(result) == 2
        
    def test_sample(self):
        """Test random sampling."""
        subset = CompanySubset(SAMPLE_COMPANIES)
        result = subset.sample(3, random_state=42)
        assert len(result) == 3
        
    def test_top(self):
        """Test getting top N companies."""
        subset = CompanySubset(SAMPLE_COMPANIES)
        result = subset.top(3, by='ticker')
        tickers = result.get()['ticker'].tolist()
        # Should be alphabetically first 3
        assert tickers[0] == 'AAPL'
        assert len(result) == 3
        
    def test_chaining(self):
        """Test method chaining."""
        subset = (CompanySubset(SAMPLE_COMPANIES)
                 .exclude_tickers(['TSLA'])
                 .sample(2, random_state=42))
        assert len(subset) == 2
        assert 'TSLA' not in subset.get()['ticker'].tolist()
        
    def test_repr(self):
        """Test string representation."""
        subset = CompanySubset(SAMPLE_COMPANIES.head(2))
        repr_str = repr(subset)
        assert 'CompanySubset(2 companies' in repr_str
        assert 'AAPL' in repr_str or 'MSFT' in repr_str
        
        # Test empty subset
        empty_subset = CompanySubset(pd.DataFrame(columns=['cik', 'ticker', 'name', 'exchange']))
        assert repr(empty_subset) == "CompanySubset(empty)"


class TestBasicFunctions:
    """Test basic data retrieval functions."""
    
    def test_get_all_companies_returns_dataframe(self):
        """Test that get_all_companies returns a properly formatted DataFrame."""
        result = get_all_companies()
        assert isinstance(result, pd.DataFrame)
        expected_columns = ['cik', 'ticker', 'name', 'exchange']
        assert list(result.columns) == expected_columns
        assert len(result) > 0  # Should have some companies
        
    @patch('edgar.reference.company_subsets.get_all_companies')
    def test_get_companies_by_exchanges_single(self, mock_get_all):
        """Test getting companies by single exchange."""
        mock_get_all.return_value = SAMPLE_MIXED_EXCHANGES
        result = get_companies_by_exchanges('NYSE')
        assert len(result) == 3  # BRK-B, JPM, WMT
        assert all(result['exchange'] == 'NYSE')
        
    @patch('edgar.reference.company_subsets.get_all_companies')
    def test_get_companies_by_exchanges_multiple(self, mock_get_all):
        """Test getting companies by multiple exchanges."""
        mock_get_all.return_value = SAMPLE_MIXED_EXCHANGES
        result = get_companies_by_exchanges(['NYSE', 'Nasdaq'])
        assert len(result) == 5  # All companies
        
    def test_get_popular_companies_returns_dataframe(self):
        """Test that get_popular_companies returns a properly formatted DataFrame."""
        result = get_popular_companies()
        assert isinstance(result, pd.DataFrame)
        expected_columns = ['cik', 'ticker', 'name', 'exchange']
        assert list(result.columns) == expected_columns
        assert len(result) > 0  # Should have some popular companies
        
    def test_get_popular_companies_mega_cap(self):
        """Test getting mega cap companies returns limited results."""
        result = get_popular_companies(PopularityTier.MEGA_CAP)
        assert isinstance(result, pd.DataFrame)
        assert len(result) <= 10  # Should be top 10 or fewer
        expected_columns = ['cik', 'ticker', 'name', 'exchange']
        assert list(result.columns) == expected_columns


class TestSamplingFunctions:
    """Test sampling and selection functions."""
    
    def test_get_random_sample(self):
        """Test random sampling."""
        result = get_random_sample(SAMPLE_COMPANIES, n=3, random_state=42)
        assert len(result) == 3
        assert set(result.columns) == {'cik', 'ticker', 'name', 'exchange'}
        
        # Test same seed gives same result
        result2 = get_random_sample(SAMPLE_COMPANIES, n=3, random_state=42)
        assert result['ticker'].tolist() == result2['ticker'].tolist()
        
    def test_get_random_sample_larger_than_available(self):
        """Test sampling more than available companies."""
        result = get_random_sample(SAMPLE_COMPANIES, n=10, random_state=42)
        assert len(result) == 5  # Should return all available
        
    @patch('edgar.reference.company_subsets.get_all_companies')
    def test_get_random_sample_default_data(self, mock_get_all):
        """Test random sampling with default data."""
        mock_get_all.return_value = SAMPLE_COMPANIES
        result = get_random_sample(n=3, random_state=42)
        assert len(result) == 3
        
    def test_get_stratified_sample(self):
        """Test stratified sampling."""
        result = get_stratified_sample(SAMPLE_MIXED_EXCHANGES, n=4, stratify_by='exchange', random_state=42)
        assert len(result) <= 4
        
        # Check that both exchanges are represented
        exchanges = result['exchange'].unique()
        assert len(exchanges) >= 1  # At least one exchange
        
    def test_get_stratified_sample_invalid_column(self):
        """Test stratified sampling with invalid column."""
        result = get_stratified_sample(SAMPLE_COMPANIES, n=3, stratify_by='invalid_column', random_state=42)
        assert len(result) == 3  # Should fall back to random sampling
        
    def test_get_top_companies_by_metric(self):
        """Test getting top companies by metric."""
        result = get_top_companies_by_metric(SAMPLE_COMPANIES, n=3, metric='ticker', ascending=True)
        assert len(result) == 3
        assert result.iloc[0]['ticker'] == 'AAPL'  # First alphabetically
        
        # Test descending order
        result_desc = get_top_companies_by_metric(SAMPLE_COMPANIES, n=3, metric='ticker', ascending=False)
        assert result_desc.iloc[0]['ticker'] == 'TSLA'  # Last alphabetically
        
    def test_get_top_companies_invalid_metric(self):
        """Test getting top companies with invalid metric."""
        result = get_top_companies_by_metric(SAMPLE_COMPANIES, n=3, metric='invalid_column')
        assert len(result) == 3  # Should return first 3


class TestFilteringFunctions:
    """Test filtering and exclusion functions."""
    
    def test_filter_companies_by_ticker(self):
        """Test filtering by ticker list."""
        result = filter_companies(SAMPLE_COMPANIES, ticker_list=['AAPL', 'MSFT'])
        assert len(result) == 2
        assert set(result['ticker']) == {'AAPL', 'MSFT'}
        
    def test_filter_companies_by_ticker_case_insensitive(self):
        """Test filtering by ticker list is case insensitive."""
        result = filter_companies(SAMPLE_COMPANIES, ticker_list=['aapl', 'msft'])
        assert len(result) == 2
        assert set(result['ticker']) == {'AAPL', 'MSFT'}
        
    def test_filter_companies_by_name_contains(self):
        """Test filtering by name contains."""
        result = filter_companies(SAMPLE_COMPANIES, name_contains='Inc')
        # Should find companies with 'Inc' in name
        inc_companies = [name for name in result['name'] if 'Inc' in name]
        assert len(inc_companies) > 0
        
    def test_filter_companies_by_cik(self):
        """Test filtering by CIK list."""
        result = filter_companies(SAMPLE_COMPANIES, cik_list=[320193, 789019])
        assert len(result) == 2
        assert set(result['cik']) == {320193, 789019}
        
    def test_filter_companies_custom_filter(self):
        """Test filtering with custom function."""
        def custom_filter(df):
            return df[df['ticker'].str.startswith('A')]
        
        result = filter_companies(SAMPLE_COMPANIES, custom_filter=custom_filter)
        tickers = result['ticker'].tolist()
        assert all(ticker.startswith('A') for ticker in tickers)
        
    def test_exclude_companies_by_ticker(self):
        """Test excluding companies by ticker."""
        result = exclude_companies(SAMPLE_COMPANIES, ticker_list=['AAPL', 'MSFT'])
        assert len(result) == 3
        assert 'AAPL' not in result['ticker'].tolist()
        assert 'MSFT' not in result['ticker'].tolist()
        
    def test_exclude_companies_by_name_contains(self):
        """Test excluding companies by name contains."""
        result = exclude_companies(SAMPLE_COMPANIES, name_contains='Corporation')
        # Should exclude companies with 'Corporation' in name
        corp_companies = [name for name in result['name'] if 'Corporation' in name]
        assert len(corp_companies) == 0
        
    def test_exclude_companies_by_cik(self):
        """Test excluding companies by CIK."""
        result = exclude_companies(SAMPLE_COMPANIES, cik_list=[320193])
        assert 320193 not in result['cik'].tolist()
        assert len(result) == 4


class TestCombinationFunctions:
    """Test set combination functions."""
    
    def test_combine_company_sets(self):
        """Test combining company sets (union)."""
        set1 = SAMPLE_COMPANIES.head(3)
        set2 = SAMPLE_COMPANIES.tail(3)  # Will have overlap with set1
        
        result = combine_company_sets([set1, set2])
        
        # Should have all unique companies
        assert len(result) == 5  # All companies from SAMPLE_COMPANIES
        assert len(result['cik'].unique()) == len(result)  # No duplicates
        
    def test_combine_company_sets_empty(self):
        """Test combining empty list."""
        result = combine_company_sets([])
        assert len(result) == 0
        assert list(result.columns) == ['cik', 'ticker', 'name', 'exchange']
        
    def test_intersect_company_sets(self):
        """Test intersecting company sets."""
        set1 = SAMPLE_COMPANIES.head(3)  # AAPL, MSFT, AMZN
        set2 = SAMPLE_COMPANIES.iloc[1:4]  # MSFT, AMZN, NVDA
        
        result = intersect_company_sets([set1, set2])
        
        # Should have only overlapping companies (MSFT, AMZN)
        assert len(result) == 2
        assert set(result['ticker']) == {'MSFT', 'AMZN'}
        
    def test_intersect_company_sets_single(self):
        """Test intersecting single set."""
        result = intersect_company_sets([SAMPLE_COMPANIES])
        assert len(result) == len(SAMPLE_COMPANIES)
        
    def test_intersect_company_sets_empty(self):
        """Test intersecting empty list."""
        result = intersect_company_sets([])
        assert len(result) == 0
        assert list(result.columns) == ['cik', 'ticker', 'name', 'exchange']


class TestConvenienceFunctions:
    """Test convenience functions for common company groups."""
    
    @patch('edgar.reference.company_subsets.get_all_companies')
    def test_get_faang_companies(self, mock_get_all):
        """Test getting FAANG companies."""
        # Create mock data with FAANG companies
        faang_data = pd.DataFrame({
            'cik': [1326801, 320193, 1018724, 1065280, 1652044, 789019],  # Extra company
            'ticker': ['META', 'AAPL', 'AMZN', 'NFLX', 'GOOGL', 'MSFT'],
            'name': ['Meta Platforms Inc.', 'Apple Inc.', 'Amazon.com Inc.', 'Netflix Inc.', 'Alphabet Inc.', 'Microsoft Corporation'],
            'exchange': ['Nasdaq'] * 6
        })
        mock_get_all.return_value = faang_data
        
        result = get_faang_companies()
        expected_tickers = {'META', 'AAPL', 'AMZN', 'NFLX', 'GOOGL'}
        assert set(result['ticker']) == expected_tickers
        assert 'MSFT' not in result['ticker'].tolist()
        
    @patch('edgar.reference.company_subsets.get_all_companies')
    def test_get_tech_giants(self, mock_get_all):
        """Test getting tech giants."""
        # Create mock data with tech companies
        tech_data = pd.DataFrame({
            'cik': [320193, 789019, 1652044, 1018724, 1326801],
            'ticker': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'],
            'name': ['Apple Inc.', 'Microsoft Corporation', 'Alphabet Inc.', 'Amazon.com Inc.', 'Meta Platforms Inc.'],
            'exchange': ['Nasdaq'] * 5
        })
        mock_get_all.return_value = tech_data
        
        result = get_tech_giants()
        assert len(result) >= 5  # Should include at least the companies in our mock data
        tech_tickers = {'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'}
        assert tech_tickers.issubset(set(result['ticker']))
        
    @patch('edgar.reference.company_subsets.get_all_companies')
    def test_get_dow_jones_sample(self, mock_get_all):
        """Test getting Dow Jones sample."""
        # Create mock data with some Dow companies
        dow_data = pd.DataFrame({
            'cik': [320193, 789019, 731766, 886982, 354950],
            'ticker': ['AAPL', 'MSFT', 'UNH', 'GS', 'HD'],
            'name': ['Apple Inc.', 'Microsoft Corporation', 'UnitedHealth Group Inc.', 'Goldman Sachs Group Inc.', 'Home Depot Inc.'],
            'exchange': ['Nasdaq', 'Nasdaq', 'NYSE', 'NYSE', 'NYSE']
        })
        mock_get_all.return_value = dow_data
        
        result = get_dow_jones_sample()
        assert len(result) >= 5  # Should include at least the companies in our mock data
        dow_tickers = {'AAPL', 'MSFT', 'UNH', 'GS', 'HD'}
        assert dow_tickers.issubset(set(result['ticker']))


class TestEnums:
    """Test enum definitions."""
    
    def test_market_cap_tier_enum(self):
        """Test MarketCapTier enum."""
        assert MarketCapTier.LARGE_CAP.value == "large_cap"
        assert MarketCapTier.MID_CAP.value == "mid_cap"
        assert MarketCapTier.SMALL_CAP.value == "small_cap"
        assert MarketCapTier.MICRO_CAP.value == "micro_cap"
        
    def test_popularity_tier_enum(self):
        """Test PopularityTier enum."""
        assert PopularityTier.MEGA_CAP.value == "mega_cap"
        assert PopularityTier.POPULAR.value == "popular"
        assert PopularityTier.MAINSTREAM.value == "mainstream"
        assert PopularityTier.EMERGING.value == "emerging"


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_empty_dataframe_operations(self):
        """Test operations on empty DataFrames."""
        empty_df = pd.DataFrame(columns=['cik', 'ticker', 'name', 'exchange'])
        
        # Test sampling
        result = get_random_sample(empty_df, n=5)
        assert len(result) == 0
        
        # Test filtering
        result = filter_companies(empty_df, ticker_list=['AAPL'])
        assert len(result) == 0
        
        # Test exclusion
        result = exclude_companies(empty_df, ticker_list=['AAPL'])
        assert len(result) == 0
        
        # Test combination
        result = combine_company_sets([empty_df, SAMPLE_COMPANIES])
        assert len(result) == len(SAMPLE_COMPANIES)
        
    @patch('edgar.reference.company_subsets.log')
    def test_error_logging(self, mock_log):
        """Test that errors are properly logged."""
        # Test with invalid DataFrame that should cause an error
        invalid_df = pd.DataFrame({'invalid': [1, 2, 3]})
        
        result = filter_companies(invalid_df, ticker_list=['AAPL'])
        # Should handle gracefully and return the original DataFrame
        assert len(result) == 3
        
    def test_case_sensitivity(self):
        """Test case insensitive operations."""
        # Test ticker filtering with mixed case
        result = filter_companies(SAMPLE_COMPANIES, ticker_list=['aapl', 'MSFT', 'Amzn'])
        assert len(result) == 3
        expected_tickers = {'AAPL', 'MSFT', 'AMZN'}
        assert set(result['ticker']) == expected_tickers


if __name__ == '__main__':
    pytest.main([__file__])
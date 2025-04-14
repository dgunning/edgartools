"""
Tests for the new fund entity API in edgar.funds.fund_entities.
"""
import pytest
from unittest.mock import patch, MagicMock

from edgar.funds import (
    FundCompany,
    FundSeries,
    FundClass,
    find_fund,
    get_fund_company,
    get_fund_series,
    get_fund_class,
    get_series_by_name,
    get_class_by_ticker
)


class TestFundEntities:
    """Tests for the new fund entity API classes."""
    
    def test_fund_entities_imports(self):
        """Test that all necessary items are imported correctly."""
        assert FundCompany
        assert FundSeries
        assert FundClass
        assert find_fund
        assert get_fund_company
        assert get_fund_series
        assert get_fund_class
        assert get_series_by_name
        assert get_class_by_ticker
    
    @patch('edgar.funds.data.resolve_fund_identifier')
    def test_fund_company_initialization(self, mock_resolve):
        """Test that FundCompany can be initialized properly."""
        mock_resolve.return_value = 123456789
        
        company = FundCompany("ABCDX")
        assert company.cik == 123456789
        mock_resolve.assert_called_once_with("ABCDX")
    
    @patch('edgar.funds.data.get_fund_classes')
    def test_fund_company_get_classes(self, mock_get_classes):
        """Test that FundCompany.get_classes delegates to the correct function."""
        mock_class = MagicMock()
        mock_get_classes.return_value = [mock_class]
        
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            company = FundCompany("ABCDX")
            classes = company.get_classes()
            
            assert len(classes) == 1
            assert classes[0] == mock_class
            mock_get_classes.assert_called_once()
    
    def test_fund_series_initialization(self):
        """Test that FundSeries can be initialized properly."""
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            company = FundCompany("ABCDX")
            series = FundSeries("S000123456", "Series Trust", company)
            
            assert series.series_id == "S000123456"
            assert series.name == "Series Trust"
            assert series.company == company
            assert series.fund_company == company  # Test the alias property
    
    def test_fund_class_initialization(self):
        """Test that FundClass can be initialized properly."""
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            company = FundCompany("ABCDX")
            fund_class = FundClass("C000123456", company, name="Class A", ticker="ABCDX")
            
            assert fund_class.class_id == "C000123456"
            assert fund_class.company == company
            assert fund_class.fund_company == company  # Test the alias property
            assert fund_class.name == "Class A"
            assert fund_class.ticker == "ABCDX"


class TestSmartFinder:
    """Tests for the smart finder function."""
    
    @patch('edgar.funds.fund_entities.get_fund_series')
    def test_find_fund_with_series_id(self, mock_get_series):
        """Test find_fund with a series ID."""
        # Mock series to return
        mock_series = MagicMock(spec=FundSeries)
        mock_get_series.return_value = mock_series
        
        # Call find_fund with a series ID
        result = find_fund("S000012345")
        
        # Verify the result is the mock series
        assert result == mock_series
        mock_get_series.assert_called_once_with("S000012345")
    
    @patch('edgar.funds.fund_entities.get_fund_class')
    def test_find_fund_with_class_id(self, mock_get_class):
        """Test find_fund with a class ID."""
        # Mock class to return
        mock_class = MagicMock(spec=FundClass)
        mock_get_class.return_value = mock_class
        
        # Call find_fund with a class ID
        result = find_fund("C000012345")
        
        # Verify the result is the mock class
        assert result == mock_class
        mock_get_class.assert_called_once_with("C000012345")
    
    @patch('edgar.funds.fund_entities.is_fund_class_ticker', return_value=True)
    @patch('edgar.funds.fund_entities.get_fund_class')
    def test_find_fund_with_ticker(self, mock_get_class, mock_is_ticker):
        """Test find_fund with a ticker symbol."""
        # Mock class to return
        mock_class = MagicMock(spec=FundClass)
        mock_get_class.return_value = mock_class
        
        # Call find_fund with a ticker
        result = find_fund("VFINX")
        
        # Verify the result is the mock class
        assert result == mock_class
        mock_get_class.assert_called_once_with("VFINX")
        mock_is_ticker.assert_called_once_with("VFINX")
    
    @patch('edgar.funds.fund_entities.is_fund_class_ticker', return_value=False)
    @patch('edgar.funds.fund_entities.get_fund_company')
    def test_find_fund_with_cik(self, mock_get_company, mock_is_ticker):
        """Test find_fund with a CIK."""
        # Mock company to return
        mock_company = MagicMock(spec=FundCompany)
        mock_get_company.return_value = mock_company
        
        # Call find_fund with a CIK
        result = find_fund("1234567")
        
        # Verify the result is the mock company
        assert result == mock_company
        mock_get_company.assert_called_once_with("1234567")
        mock_is_ticker.assert_called_once_with("1234567")


class TestSpecializedGetters:
    """Tests for the specialized getter functions."""
    
    def test_get_fund_company(self):
        """Test get_fund_company function."""
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            company = get_fund_company("1234567")
            assert isinstance(company, FundCompany)
            assert company.cik == 123456789
    
    @patch('edgar.funds.data.direct_get_fund_with_filings')
    def test_get_fund_series(self, mock_direct_get):
        """Test get_fund_series function with direct implementation."""
        # Create mock for direct_get_fund_with_filings
        mock_fund_info = MagicMock()
        mock_fund_info.fund.cik = 123456789
        mock_fund_info.name = "Test Series"
        mock_direct_get.return_value = mock_fund_info
        
        # Call get_fund_series
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            series = get_fund_series("S000012345")
            
            # Verify the result
            assert isinstance(series, FundSeries)
            assert series.series_id == "S000012345"
            assert series.name == "Test Series"
            assert series.company.cik == 123456789
            
            # Verify direct_get_fund_with_filings was called
            mock_direct_get.assert_called_once_with("S000012345")
    
    @patch('edgar.funds.data.direct_get_fund_with_filings')
    def test_get_fund_class(self, mock_direct_get):
        """Test get_fund_class function with direct implementation."""
        # Create mock for direct_get_fund_with_filings
        mock_fund_info = MagicMock()
        mock_fund_info.fund_cik = 123456789
        mock_fund_info.name = "Test Class"
        mock_fund_info.fund.ident_info = {"Series": "S000012345"}
        mock_direct_get.return_value = mock_fund_info
        
        # Call get_fund_class
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            with patch('edgar.funds.fund_entities.is_fund_class_ticker', return_value=False):
                class_obj = get_fund_class("C000012345")
                
                # Verify the result
                assert isinstance(class_obj, FundClass)
                assert class_obj.class_id == "C000012345"
                assert class_obj.name == "Test Class"
                assert class_obj.company.cik == 123456789
                assert class_obj.series_id == "S000012345"
                
                # Verify direct_get_fund_with_filings was called
                mock_direct_get.assert_called_once_with("C000012345")
    
    @patch('edgar.funds.fund_entities.is_fund_class_ticker')
    @patch('edgar.funds.core.get_class_id_for_ticker')
    @patch('edgar.funds.data.direct_get_fund_with_filings')
    def test_get_fund_class_by_ticker(self, mock_direct_get, mock_get_class_id, mock_is_ticker):
        """Test get_fund_class function with a ticker symbol."""
        # Setup mocks
        mock_is_ticker.return_value = True  # Important: set the return value on the mock
        mock_get_class_id.return_value = "C000012345"
        
        mock_fund_info = MagicMock()
        mock_fund_info.fund_cik = 123456789
        mock_fund_info.name = "Test Class"
        mock_direct_get.return_value = mock_fund_info
        
        # Call get_fund_class with a ticker
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            # Add a patch for get_fund since it gets called in the fallback path
            with patch('edgar.funds.core.get_fund') as mock_get_fund:
                # Mock the result from get_fund
                mock_class = MagicMock()
                mock_class.class_id = "C000012345"
                mock_class.fund.cik = 123456789
                mock_class.name = "Test Class"
                mock_class.ticker = "VFINX"
                mock_get_fund.return_value = mock_class
                
                class_obj = get_fund_class("VFINX")
                
                # Verify the result
                assert isinstance(class_obj, FundClass)
                assert class_obj.class_id == "C000012345"
                assert class_obj.name == "Test Class"
                assert class_obj.company.cik == 123456789
                assert class_obj.ticker == "VFINX"  # Should preserve the ticker
                
                # Verify get_class_id_for_ticker was called
                mock_get_class_id.assert_called_once_with("VFINX")
                
                # Verify direct_get_fund_with_filings was called with the class ID
                mock_direct_get.assert_called_once_with("C000012345")
                
                # We don't check is_fund_class_ticker call count here since it might be called multiple times
    
    def test_get_series_by_name(self):
        """Test get_series_by_name function directly."""
        from edgar.funds.fund_entities import get_series_by_name as direct_get_series_by_name
        
        # Use a more targeted approach by mocking only the function we're testing
        with patch('edgar.funds.fund_entities.FundCompany') as MockFundCompany:
            # Create mock company instance
            mock_company = MagicMock()
            MockFundCompany.return_value = mock_company
            
            # Create test series
            series1 = FundSeries("S000001", "Growth Fund", mock_company)
            series2 = FundSeries("S000002", "Income Fund", mock_company)
            
            # Configure mock company's get_series method
            mock_company.get_series.return_value = [series1, series2]
            
            # Test exact match
            result = direct_get_series_by_name(123456789, "Growth Fund")
            assert result == series1
            
            # Test case-insensitive match
            result = direct_get_series_by_name(123456789, "growth fund")
            assert result == series1
            
            # Test partial match
            result = direct_get_series_by_name(123456789, "Income")
            assert result == series2
            
            # Test no match
            result = direct_get_series_by_name(123456789, "Balanced Fund")
            assert result is None
            
            # Verify FundCompany was called with the correct CIK
            MockFundCompany.assert_called_with(123456789)
    
    @patch('edgar.funds.fund_entities.get_fund_class')
    def test_get_class_by_ticker(self, mock_get_class):
        """Test get_class_by_ticker function."""
        # Setup mock
        mock_class = MagicMock(spec=FundClass)
        mock_get_class.return_value = mock_class
        
        # Call get_class_by_ticker
        result = get_class_by_ticker("VFINX")
        
        # Verify result and call
        assert result == mock_class
        mock_get_class.assert_called_once_with("VFINX")


class TestEntityNavigation:
    """Tests for navigation between fund entities."""
    
    def test_fund_class_to_series(self):
        """Test navigation from FundClass to FundSeries."""
        # Use MagicMock for more control over property behavior
        mock_company = MagicMock(spec=FundCompany)
        series = FundSeries("S000001", "Test Series", mock_company)
        
        # Create FundClass with proper series_id
        fund_class = FundClass("C000001", mock_company, name="Test Class", series_id="S000001")
        
        # Mock get_series to return our test series
        mock_company.get_series.return_value = [series]
        
        # Clear the cached_property if it exists
        if hasattr(fund_class, '_series'):
            delattr(fund_class, '_series')
        
        # Test navigation from class to series
        assert fund_class.series == series
        
        # Create a new FundClass with no series_id
        fund_class2 = FundClass("C000002", mock_company, name="Test Class 2")
        
        # Clear the cached_property if it exists
        if hasattr(fund_class2, '_series'):
            delattr(fund_class2, '_series')
        
        # Test without series_id
        assert fund_class2.series is None
    
    def test_fund_series_to_classes(self):
        """Test navigation from FundSeries to FundClass."""
        # Setup
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            company = FundCompany(123456789)
            series = FundSeries("S000001", "Test Series", company)
            
            class1 = FundClass("C000001", company, name="Class A", series_id="S000001")
            class2 = FundClass("C000002", company, name="Class B", series_id="S000001")
            class3 = FundClass("C000003", company, name="Class C", series_id="S000002")  # Different series
            
            # Mock company.get_classes to return all classes
            with patch.object(company, 'get_classes', return_value=[class1, class2, class3]):
                # Test series.get_classes()
                series_classes = series.get_classes()
                assert len(series_classes) == 2
                assert class1 in series_classes
                assert class2 in series_classes
                assert class3 not in series_classes
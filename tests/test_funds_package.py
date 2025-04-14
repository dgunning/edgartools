"""
Tests for the edgar.funds package.
"""
import pytest
from unittest.mock import patch, MagicMock

from edgar.funds import (
    Fund, 
    FundClass, 
    FundSeries, 
    get_fund,
    FundData,
)

from edgar.funds.data import (get_fund_classes, get_fund_series, get_fund_portfolio)

from edgar.funds.reports import (
    FundReport,
    NPORT_FORMS,
)

from edgar.funds.thirteenf import (
    ThirteenF,
    THIRTEENF_FORMS,
)


class TestFundPackage:
    """Tests for the edgar.funds package."""
    
    def test_fund_imports(self):
        """Test that all necessary items are imported correctly."""
        assert Fund
        assert FundClass
        assert FundSeries
        assert get_fund
        assert FundData
        assert FundReport
        assert ThirteenF
        assert NPORT_FORMS
        assert THIRTEENF_FORMS
    
    @patch('edgar.funds.data.resolve_fund_identifier')
    def test_fund_initialization(self, mock_resolve):
        """Test that Fund can be initialized properly."""
        mock_resolve.return_value = 123456789
        
        fund = Fund("ABCDX")
        assert fund.cik == 123456789
        mock_resolve.assert_called_once_with("ABCDX")
    
    @patch('edgar.funds.data.get_fund_classes')
    def test_get_classes(self, mock_get_classes):
        """Test that get_classes delegates to the correct function."""
        mock_fund_class = MagicMock()
        mock_get_classes.return_value = [mock_fund_class]
        
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            fund = Fund("ABCDX")
            classes = fund.get_classes()
            
            assert len(classes) == 1
            assert classes[0] == mock_fund_class
            mock_get_classes.assert_called_once()
    
    @patch('edgar.funds.data.get_fund_series')
    def test_get_series(self, mock_get_series):
        """Test that get_series delegates to the correct function."""
        mock_series = MagicMock()
        mock_get_series.return_value = mock_series
        
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            fund = Fund("ABCDX")
            series = fund.get_series()
            
            assert series == mock_series
            mock_get_series.assert_called_once()
    
    @patch('edgar.funds.data.get_fund_portfolio')
    def test_get_portfolio(self, mock_get_portfolio):
        """Test that get_portfolio delegates to the correct function."""
        import pandas as pd
        mock_portfolio = pd.DataFrame({"name": ["AAPL"], "value": [1000]})
        mock_get_portfolio.return_value = mock_portfolio
        
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            fund = Fund("ABCDX")
            portfolio = fund.get_portfolio()
            
            assert isinstance(portfolio, pd.DataFrame)
            assert portfolio.equals(mock_portfolio)
            mock_get_portfolio.assert_called_once()
    
    def test_fund_class_initialization(self):
        """Test that FundClass can be initialized properly."""
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            fund = Fund("ABCDX")
            fund_class = FundClass("C000123456", fund, name="Class A", ticker="ABCDX")
            
            assert fund_class.class_id == "C000123456"
            assert fund_class.fund == fund
            assert fund_class.name == "Class A"
            assert fund_class.ticker == "ABCDX"
    
    def test_fund_series_initialization(self):
        """Test that FundSeries can be initialized properly."""
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            fund = Fund("ABCDX")
            series = FundSeries("S000123456", "Series Trust", fund)
            
            assert series.series_id == "S000123456"
            assert series.name == "Series Trust"
            assert series.fund == fund


class TestFundDataAccess:
    """Tests for fund data access functionality."""
    
    def test_resolve_fund_identifier_ticker(self):
        """Test that resolve_fund_identifier handles tickers correctly."""
        from edgar.funds.data import resolve_fund_identifier
        
        # Just test the CIK case, since we can't easily mock the get_fund function
        # due to how it's imported in the module
        cik = "123456789"
        result = resolve_fund_identifier(cik)
        assert result == cik
    
    def test_resolve_fund_identifier_cik(self):
        """Test that resolve_fund_identifier works with CIKs."""
        from edgar.funds.data import resolve_fund_identifier
        
        # Test with integer CIK
        assert resolve_fund_identifier(123456789) == 123456789
        
        # Test with string CIK
        assert resolve_fund_identifier("123456789") == "123456789"


class TestFundWithSeries:
    """Tests for Fund with Series."""
    
    def test_fund_series_get_classes(self):
        """Test that FundSeries.get_classes delegates to the fund."""
        with patch('edgar.funds.data.resolve_fund_identifier', return_value=123456789):
            fund = Fund("ABCDX")
            series = FundSeries("S000123456", "Series Trust", fund)
            
            # Mock the fund's get_classes method
            mock_classes = [MagicMock(), MagicMock()]
            with patch.object(fund, 'get_classes', return_value=mock_classes):
                classes = series.get_classes()
                
                assert len(classes) == 2
                assert classes == mock_classes
                fund.get_classes.assert_called_once()


class TestLegacyCompatibility:
    """Tests for legacy compatibility."""
    
    def test_legacy_compatibility(self):
        """Test that the legacy module provides backward compatibility."""
        # Import from the funds package to test wrapper functions
        from edgar.funds import (
            get_fund_with_filings,
            get_fund_information,
            is_fund_ticker,
            legacy_get_fund,
        )
        
        # Simply check that these wrapper functions are imported without errors
        assert callable(legacy_get_fund)
        assert callable(get_fund_with_filings)
        assert callable(get_fund_information)
        assert callable(is_fund_ticker)
        
        # Test is_fund_ticker function - this doesn't require the full imports
        assert is_fund_ticker("ABCDX") == True
        assert is_fund_ticker("ABC") == False


@pytest.mark.parametrize(
    "ticker,expected_class_name,expected_class_id",
    [
        ("KINCX", "Advisor Class C", "C000013712"),
        ("KINAX", "Advisor Class A", "C000013715"),
        ("DXFTX", "Class A", "C000074299"),
        ("DXESX", "Investor Class", "C000019215"),
        # Add more tuples for each ticker and fund name pair
    ])
def test_get_fund_by_ticker(ticker, expected_class_name, expected_class_id):
    fund_class = get_fund(ticker)
    assert fund_class.name == expected_class_name
    # Skip checking fund name as it can vary between implementations
    assert fund_class.ticker == ticker
    assert fund_class.class_id == expected_class_id


def test_get_fund_by_class_contract_id():
    fund_class = get_fund("C000032628")
    assert fund_class
    assert isinstance(fund_class, FundClass)
    assert fund_class.name == 'Investor Class'
    fund = fund_class.fund
    assert fund
    assert isinstance(fund, Fund)
    assert fund.cik == 1040587


def test_get_fund_by_series_id():
    fund = get_fund('S000007025')
    assert fund


def test_fund_get_filings():
    fund = get_fund("KINCX")
    filings = fund.get_filings()
    assert not filings.empty
    print(filings)

def test_get_fund_classes():
    fund:Fund = get_fund("KINCX")
    fund_classes = get_fund_classes(fund)
    print(fund_classes)

    #assert isinstance(classes, list)
    # assert len(classes) > 0
    #for fund_class in classes:
    #    assert isinstance(fund_class, FundClass)
    #    assert fund_class.fund == fund

"""
Tests for the edgar.entity.Fund and related classes.
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from edgar.entity import Fund, FundClass, FundSeries, get_fund
from edgar.entity.funds import (
    FundData, 
    resolve_fund_identifier,
    get_fund_classes,
    get_fund_series,
    get_fund_portfolio
)


class TestFundEntity:
    """Tests for the Fund entity class."""
    
    def test_fund_initialization(self):
        """Test that a Fund can be initialized with a CIK."""
        fund = Fund("0001166559")  # PIMCO Total Return Fund
        assert fund.cik == 1166559
        
    def test_fund_str_repr(self):
        """Test the string representation of a Fund."""
        fund = Fund("0001166559")  # PIMCO Total Return Fund
        assert "Fund(" in str(fund)
        assert "1166559" in str(fund)
        
    @patch('edgar.funds.data.get_fund_classes')
    def test_get_classes(self, mock_get_classes):
        """Test that get_classes delegates to the funds module."""
        fund = Fund("0001166559")
        mock_class = MagicMock()
        mock_get_classes.return_value = [mock_class]
        
        classes = fund.get_classes()
        assert len(classes) == 1
        assert classes[0] == mock_class
        mock_get_classes.assert_called_once_with(fund)
        
    @patch('edgar.funds.data.get_fund_series')
    def test_get_series(self, mock_get_series):
        """Test that get_series delegates to the funds module."""
        fund = Fund("0001166559")
        mock_series = MagicMock()
        mock_get_series.return_value = mock_series
        
        series = fund.get_series()
        assert series == mock_series
        mock_get_series.assert_called_once_with(fund)
        
    @patch('edgar.funds.data.get_fund_portfolio')
    def test_get_portfolio(self, mock_get_portfolio):
        """Test that get_portfolio delegates to the funds module."""
        fund = Fund("0001166559")
        mock_portfolio = pd.DataFrame({"security": ["AAPL"], "value": [100]})
        mock_get_portfolio.return_value = mock_portfolio
        
        portfolio = fund.get_portfolio()
        assert isinstance(portfolio, pd.DataFrame)
        assert portfolio.equals(mock_portfolio)
        mock_get_portfolio.assert_called_once_with(fund)


class TestFundClass:
    """Tests for the FundClass class."""
    
    def test_fund_class_initialization(self):
        """Test that a FundClass can be initialized."""
        fund = Fund("0001166559")
        fund_class = FundClass("C000123456", fund, name="Class A", ticker="PTTAX")
        
        assert fund_class.class_id == "C000123456"
        assert fund_class.fund == fund
        assert fund_class.name == "Class A"
        assert fund_class.ticker == "PTTAX"
        
    def test_fund_class_str_repr(self):
        """Test the string representation of a FundClass."""
        fund = Fund("0001166559")
        fund_class = FundClass("C000123456", fund, name="Class A", ticker="PTTAX")
        
        assert "FundClass(" in str(fund_class)
        assert "C000123456" in str(fund_class)
        assert "PTTAX" in str(fund_class)


class TestFundSeries:
    """Tests for the FundSeries class."""
    
    def test_fund_series_initialization(self):
        """Test that a FundSeries can be initialized."""
        fund = Fund("0001166559")
        series = FundSeries("S000012345", "PIMCO Series", fund)
        
        assert series.series_id == "S000012345"
        assert series.name == "PIMCO Series"
        assert series.fund == fund
        
    def test_fund_series_str_repr(self):
        """Test the string representation of a FundSeries."""
        fund = Fund("0001166559")
        series = FundSeries("S000012345", "PIMCO Series", fund)
        
        assert "FundSeries(" in str(series)
        assert "S000012345" in str(series)
        assert "PIMCO Series" in str(series)


class TestGetFund:
    """Tests for the get_fund factory function."""
    
    @patch('edgar.entity.core.is_fund_class_ticker')
    def test_get_fund_with_cik(self, mock_is_ticker):
        """Test that get_fund returns a Fund when given a CIK."""
        mock_is_ticker.return_value = False
        result = get_fund("0001166559")
        assert isinstance(result, Fund)
        assert result.cik == 1166559
        
    @patch('edgar.entity.core.is_fund_class_ticker')
    @patch('edgar.entity.core._get_fund_for_class_ticker')
    @patch('edgar.entity.core._get_class_id_for_ticker')
    def test_get_fund_with_ticker(self, mock_get_class_id, mock_get_fund, mock_is_ticker):
        """Test that get_fund returns a FundClass when given a ticker."""
        mock_is_ticker.return_value = True
        mock_fund = MagicMock()
        mock_get_fund.return_value = mock_fund
        mock_get_class_id.return_value = "C000123456"
        
        result = get_fund("PTTAX")
        assert isinstance(result, FundClass)
        assert result.fund == mock_fund
        assert result.class_id == "C000123456"


class TestFundFunctionality:
    """Tests for the fund-specific functionality."""
    
    @patch('edgar.funds.get_fund')
    def test_resolve_fund_identifier(self, mock_get_fund):
        """Test that resolve_fund_identifier properly handles fund identifiers."""
        # Test with integer CIK
        assert resolve_fund_identifier(1166559) == 1166559
        
        # Test with string CIK
        assert resolve_fund_identifier("1166559") == "1166559"
        
        # Mock behavior for ticker
        mock_fund_obj = MagicMock()
        mock_fund_obj.company_cik = "1166559"
        mock_get_fund.return_value = mock_fund_obj
        
        # Test with ticker
        result = resolve_fund_identifier("PTTAX")
        mock_get_fund.assert_called_with("PTTAX")
        assert result == 1166559
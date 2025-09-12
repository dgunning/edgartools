"""
Tests for the Fund wrapper class.
"""
import unittest
from unittest.mock import patch, MagicMock

from edgar.funds import Fund, FundCompany, FundSeries, FundClass
import pytest

class TestFundWrapper(unittest.TestCase):
    """Test the Fund wrapper class."""

    @pytest.mark.fast
    @patch('edgar.funds.core.find_fund')
    def test_fund_from_ticker(self, mock_find_fund):
        # Mock a FundClass returned by find_fund
        mock_series = MagicMock(spec=FundSeries)
        mock_series.name = "Vanguard 500 Index Fund"
        mock_series.series_id = "S000002277"
        
        mock_company = MagicMock(spec=FundCompany)
        mock_company.name = "Vanguard"
        mock_company.cik = "0000102909"
        
        mock_series.fund_company = mock_company
        
        mock_class = MagicMock(spec=FundClass)
        mock_class.name = "Vanguard 500 Index Fund Admiral Shares"
        mock_class.class_id = "C000012345"
        mock_class.ticker = "VFIAX"
        mock_class.series = mock_series
        
        mock_find_fund.return_value = mock_class
        
        # Create a Fund from a ticker
        fund = Fund("VFIAX")
        
        # Verify the hierarchy is correctly set up
        self.assertEqual(fund.name, "Vanguard 500 Index Fund Admiral Shares")
        self.assertEqual(fund.share_class.ticker, "VFIAX")
        self.assertEqual(fund.series.name, "Vanguard 500 Index Fund")
        self.assertEqual(fund.company.name, "Vanguard")

    @pytest.mark.fast
    @patch('edgar.funds.core.find_fund')
    def test_fund_from_series_id(self, mock_find_fund):
        # Mock a FundSeries returned by find_fund
        mock_company = MagicMock(spec=FundCompany)
        mock_company.name = "Vanguard"
        mock_company.cik = "0000102909"
        
        mock_series = MagicMock(spec=FundSeries)
        mock_series.name = "Vanguard 500 Index Fund"
        mock_series.series_id = "S000002277"
        mock_series.fund_company = mock_company
        
        mock_find_fund.return_value = mock_series
        
        # Create a Fund from a series ID
        fund = Fund("S000002277")
        
        # Verify the hierarchy is correctly set up
        self.assertEqual(fund.name, "Vanguard 500 Index Fund")
        self.assertIsNone(fund.share_class)
        self.assertEqual(fund.series.name, "Vanguard 500 Index Fund")
        self.assertEqual(fund.company.name, "Vanguard")

    @pytest.mark.fast
    @patch('edgar.funds.core.find_fund')
    def test_fund_from_company_cik(self, mock_find_fund):
        # Mock a FundCompany returned by find_fund
        mock_company = MagicMock(spec=FundCompany)
        mock_company.name = "Vanguard"
        mock_company.cik = "0000102909"
        
        mock_find_fund.return_value = mock_company
        
        # Create a Fund from a company CIK
        fund = Fund("0000102909")
        
        # Verify the hierarchy is correctly set up
        self.assertEqual(fund.name, "Vanguard")
        self.assertIsNone(fund.share_class)
        self.assertIsNone(fund.series)
        self.assertEqual(fund.company.name, "Vanguard")


if __name__ == "__main__":
    unittest.main()

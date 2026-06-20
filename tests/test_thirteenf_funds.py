"""
Unit tests for edgar.funds.thirteenf module.

Fast, offline tests covering constants, lazy imports, and get_thirteenf_portfolio.
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from edgar.funds.thirteenf import THIRTEENF_FORMS, ThirteenF, get_ThirteenF, get_thirteenf_portfolio


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestThirteenFConstants:

    def test_forms_list(self):
        assert THIRTEENF_FORMS == ['13F-HR', "13F-HR/A", "13F-NT", "13F-NT/A", "13F-CTR", "13F-CTR/A"]

    def test_forms_contains_hr(self):
        assert "13F-HR" in THIRTEENF_FORMS

    def test_forms_contains_amendments(self):
        assert "13F-HR/A" in THIRTEENF_FORMS
        assert "13F-NT/A" in THIRTEENF_FORMS
        assert "13F-CTR/A" in THIRTEENF_FORMS

    def test_forms_contains_nt(self):
        assert "13F-NT" in THIRTEENF_FORMS

    def test_forms_contains_ctr(self):
        assert "13F-CTR" in THIRTEENF_FORMS

    def test_forms_length(self):
        assert len(THIRTEENF_FORMS) == 6


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestThirteenFLazyImport:

    def test_get_ThirteenF_returns_class(self):
        cls = get_ThirteenF()
        assert cls is not None
        assert cls.__name__ == "ThirteenF"

    def test_ThirteenF_function_returns_class(self):
        cls = ThirteenF()
        assert cls is not None
        assert cls.__name__ == "ThirteenF"

    def test_get_ThirteenF_is_same_class(self):
        cls1 = get_ThirteenF()
        cls2 = ThirteenF()
        assert cls1 is cls2


# ---------------------------------------------------------------------------
# get_thirteenf_portfolio
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestGetThirteenFPortfolio:

    @patch("edgar.funds.thirteenf.get_ThirteenF")
    def test_no_infotable_returns_empty(self, mock_get_cls):
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.has_infotable.return_value = False
        mock_cls.return_value = mock_instance
        mock_get_cls.return_value = mock_cls

        filing = MagicMock()
        filing.accession_no = "0001234567-00-000001"
        result = get_thirteenf_portfolio(filing)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch("edgar.funds.thirteenf.get_ThirteenF")
    def test_none_infotable_returns_empty(self, mock_get_cls):
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.has_infotable.return_value = True
        mock_instance.infotable = None
        mock_cls.return_value = mock_instance
        mock_get_cls.return_value = mock_cls

        filing = MagicMock()
        filing.accession_no = "0001234567-00-000002"
        result = get_thirteenf_portfolio(filing)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch("edgar.funds.thirteenf.get_ThirteenF")
    def test_exception_returns_empty(self, mock_get_cls):
        mock_get_cls.side_effect = Exception("import error")

        filing = MagicMock()
        filing.accession_no = "0001234567-00-000003"
        result = get_thirteenf_portfolio(filing)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch("edgar.funds.thirteenf.get_ThirteenF")
    def test_successful_extraction(self, mock_get_cls):
        """Test that get_thirteenf_portfolio processes infotable data correctly.

        The mock infotable uses the canonical PascalCase schema that the real
        parsers emit for every parse path (edgartools-i5wx).
        """
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.has_infotable.return_value = True
        mock_instance.infotable = [
            {
                "Issuer": "APPLE INC",
                "Class": "COM",
                "Cusip": "037833100",
                "Value": 1000000,
                "SharesPrnAmount": 5000,
                "Type": "SH",
                "InvestmentDiscretion": "SOLE",
            },
            {
                "Issuer": "MICROSOFT CORP",
                "Class": "COM",
                "Cusip": "594918104",
                "Value": 500000,
                "SharesPrnAmount": 2000,
                "Type": "SH",
                "InvestmentDiscretion": "SOLE",
            },
        ]
        mock_cls.return_value = mock_instance
        mock_get_cls.return_value = mock_cls

        filing = MagicMock()
        filing.accession_no = "0001234567-00-000004"

        with patch("edgar.funds.thirteenf.pd.DataFrame", wraps=pd.DataFrame):
            result = get_thirteenf_portfolio(filing)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        # Canonical schema is preserved (no lowercase aliasing)
        assert "Value" in result.columns
        assert "nameOfIssuer" not in result.columns and "value_usd" not in result.columns

    @patch("edgar.funds.thirteenf.get_ThirteenF")
    def test_empty_infotable_returns_empty_df(self, mock_get_cls):
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.has_infotable.return_value = True
        mock_instance.infotable = []
        mock_cls.return_value = mock_instance
        mock_get_cls.return_value = mock_cls

        filing = MagicMock()
        filing.accession_no = "0001234567-00-000005"
        result = get_thirteenf_portfolio(filing)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch("edgar.funds.thirteenf.get_ThirteenF")
    def test_successful_with_columns_and_pct(self, mock_get_cls):
        """Test the pct_value calculation and value-descending sort path."""
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.has_infotable.return_value = True
        mock_instance.infotable = [
            {
                "Issuer": "MICROSOFT CORP",
                "Class": "COM",
                "Cusip": "594918104",
                "Value": 250000,
                "SharesPrnAmount": 1000,
                "Type": "SH",
                "InvestmentDiscretion": "SOLE",
            },
            {
                "Issuer": "APPLE INC",
                "Class": "COM",
                "Cusip": "037833100",
                "Value": 750000,
                "SharesPrnAmount": 5000,
                "Type": "SH",
                "InvestmentDiscretion": "SOLE",
            },
        ]
        mock_cls.return_value = mock_instance
        mock_get_cls.return_value = mock_cls

        filing = MagicMock()
        filing.accession_no = "0001234567-00-000006"

        with patch("edgar.funds.thirteenf.pd.DataFrame", wraps=pd.DataFrame):
            result = get_thirteenf_portfolio(filing)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        # Canonical schema, sorted by Value descending (Apple's 750k first)
        assert result.iloc[0]["Issuer"] == "APPLE INC"
        # pct_value computed off the canonical 'Value' column and sums to 100
        assert "pct_value" in result.columns
        assert result["pct_value"].sum() == pytest.approx(100.0, rel=1e-2)
        assert result.iloc[0]["pct_value"] == pytest.approx(75.0, rel=1e-2)


# ---------------------------------------------------------------------------
# __all__ exports
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestExports:

    def test_all_exports(self):
        from edgar.funds import thirteenf
        assert "ThirteenF" in thirteenf.__all__
        assert "THIRTEENF_FORMS" in thirteenf.__all__
        assert "get_thirteenf_portfolio" in thirteenf.__all__

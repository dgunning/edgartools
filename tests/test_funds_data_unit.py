"""
Unit tests for edgar.funds.data module.

Fast, offline tests covering parse_fund_data, _FundDTO, _FundCompanyInfo,
_FundClassOrSeries, _FundClass, _FundSeries, FundData, is_fund_ticker,
resolve_fund_identifier, get_fund_information, and get_fund_object.
"""
import re
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from edgar.funds.data import (
    FundData,
    _FundClass,
    _FundCompanyInfo,
    _FundDTO,
    _FundSeries,
    direct_get_fund_with_filings,
    get_fund_information,
    get_fund_object,
    is_fund_ticker,
    parse_fund_data,
    resolve_fund_identifier,
)


# ---------------------------------------------------------------------------
# _FundDTO
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestFundDTO:

    def test_str(self):
        dto = _FundDTO(
            company_cik="001", company_name="Acme",
            name="Acme Growth", series="S001",
            ticker="ACMEX", class_contract_id="C001",
            class_contract_name="Class A",
        )
        s = str(dto)
        assert "Acme Growth" in s
        assert "ACMEX" in s
        assert "C001" in s

    def test_fields(self):
        dto = _FundDTO("001", "Acme", "Acme Growth", "S001", "ACMEX", "C001", "Class A")
        assert dto.company_cik == "001"
        assert dto.company_name == "Acme"
        assert dto.name == "Acme Growth"
        assert dto.series == "S001"
        assert dto.ticker == "ACMEX"
        assert dto.class_contract_id == "C001"
        assert dto.class_contract_name == "Class A"


# ---------------------------------------------------------------------------
# parse_fund_data
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestParseFundData:

    SAMPLE_SGML = """
<SERIES-AND-CLASSES-CONTRACTS-DATA>
<EXISTING-SERIES-AND-CLASSES-CONTRACTS>
<SERIES>
<OWNER-CIK>0001090372
<SERIES-ID>S000071967
<SERIES-NAME>Jacob Forward ETF
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000227599
<CLASS-CONTRACT-NAME>Jacob Forward ETF
<CLASS-CONTRACT-TICKER-SYMBOL>JFWD
</CLASS-CONTRACT>
</SERIES>
</EXISTING-SERIES-AND-CLASSES-CONTRACTS>
</SERIES-AND-CLASSES-CONTRACTS-DATA>
"""

    def test_parse_single_series(self):
        df = parse_fund_data(self.SAMPLE_SGML)
        assert len(df) == 1
        assert df.iloc[0]["Fund"] == "Jacob Forward ETF"
        assert df.iloc[0]["Ticker"] == "JFWD"
        assert df.iloc[0]["SeriesID"] == "S000071967"
        assert df.iloc[0]["ContractID"] == "C000227599"

    def test_parse_columns(self):
        df = parse_fund_data(self.SAMPLE_SGML)
        expected_cols = {"Fund", "Ticker", "SeriesID", "ContractID", "Class", "CIK"}
        assert set(df.columns) == expected_cols

    def test_parse_empty(self):
        df = parse_fund_data("")
        assert len(df) == 0

    def test_parse_multiple_series(self):
        sgml = """
<SERIES>
<OWNER-CIK>0001111111
<SERIES-ID>S000001111
<SERIES-NAME>Fund A
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000001111
<CLASS-CONTRACT-NAME>Class A
<CLASS-CONTRACT-TICKER-SYMBOL>AAAAX
</CLASS-CONTRACT>
</SERIES>
<SERIES>
<OWNER-CIK>0001111111
<SERIES-ID>S000002222
<SERIES-NAME>Fund B
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000002222
<CLASS-CONTRACT-NAME>Class B
<CLASS-CONTRACT-TICKER-SYMBOL>BBBBX
</CLASS-CONTRACT>
</SERIES>
"""
        df = parse_fund_data(sgml)
        assert len(df) == 2
        assert df.iloc[0]["Fund"] == "Fund A"
        assert df.iloc[1]["Fund"] == "Fund B"


# ---------------------------------------------------------------------------
# is_fund_ticker
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestIsFundTicker:

    def test_valid_fund_ticker(self):
        assert is_fund_ticker("VFINX") is True

    def test_valid_fund_ticker_2(self):
        assert is_fund_ticker("ACMEX") is True

    def test_not_fund_ticker_too_short(self):
        assert is_fund_ticker("AAPL") is False

    def test_not_fund_ticker_no_x(self):
        assert is_fund_ticker("ABCDE") is False

    def test_not_fund_ticker_lowercase(self):
        assert is_fund_ticker("vfinx") is False

    def test_not_fund_ticker_empty(self):
        assert is_fund_ticker("") is False

    def test_not_fund_ticker_none(self):
        assert is_fund_ticker(None) is False

    def test_not_fund_ticker_number(self):
        assert is_fund_ticker(12345) is False

    def test_not_fund_ticker_6_chars(self):
        assert is_fund_ticker("ABCDEX") is False


# ---------------------------------------------------------------------------
# FundData
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestFundData:

    def _make_fund_data(self, **extra):
        from unittest.mock import MagicMock
        defaults = dict(
            cik=123, name="Test Fund", tickers=[], exchanges=[],
            sic="6726", sic_description="Investment Offices", ein="123456789",
            entity_type="fund", fiscal_year_end="1231",
            filings=MagicMock(), business_address=MagicMock(),
            mailing_address=MagicMock(), state_of_incorporation="DE",
        )
        defaults.update(extra)
        return FundData(**defaults)

    def test_is_fund_property(self):
        fd = self._make_fund_data()
        assert fd.is_fund is True

    def test_series_id(self):
        fd = self._make_fund_data(series_id="S000099")
        assert fd.series_id == "S000099"

    def test_class_ids_default(self):
        fd = self._make_fund_data()
        assert fd.class_ids == []

    def test_fund_classes_default(self):
        fd = self._make_fund_data()
        assert fd._fund_classes == []


# ---------------------------------------------------------------------------
# resolve_fund_identifier
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestResolveFundIdentifier:

    def test_integer_passthrough(self):
        assert resolve_fund_identifier(123456789) == 123456789

    def test_plain_string_passthrough(self):
        assert resolve_fund_identifier("123456789") == "123456789"

    def test_non_matching_string(self):
        assert resolve_fund_identifier("random") == "random"

    @patch("edgar.funds.data.direct_get_fund_with_filings")
    def test_series_id_resolved(self, mock_get):
        mock_fund = MagicMock()
        mock_fund.fund_cik = "0001234567"
        mock_get.return_value = mock_fund
        result = resolve_fund_identifier("S000012345")
        assert result == 1234567
        mock_get.assert_called_once_with("S000012345")

    @patch("edgar.funds.data.direct_get_fund_with_filings")
    def test_class_id_resolved(self, mock_get):
        mock_fund = MagicMock()
        mock_fund.fund_cik = "0007654321"
        mock_get.return_value = mock_fund
        result = resolve_fund_identifier("C000054321")
        assert result == 7654321

    @patch("edgar.funds.data.direct_get_fund_with_filings")
    def test_series_id_none_fallback(self, mock_get):
        mock_get.return_value = None
        result = resolve_fund_identifier("S000012345")
        assert result == "S000012345"

    @patch("edgar.funds.data.direct_get_fund_with_filings")
    def test_series_id_error_fallback(self, mock_get):
        mock_get.side_effect = Exception("network error")
        result = resolve_fund_identifier("S000012345")
        assert result == "S000012345"


# ---------------------------------------------------------------------------
# direct_get_fund_with_filings
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestDirectGetFundWithFilings:

    def test_invalid_identifier_returns_none(self):
        assert direct_get_fund_with_filings("XYZ") is None

    def test_invalid_format_returns_none(self):
        assert direct_get_fund_with_filings("12345") is None


# ---------------------------------------------------------------------------
# _FundCompanyInfo
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestFundCompanyInfo:

    def _make_company_info(self):
        from edgar._filings import Filings
        import pyarrow as pa

        schema = pa.schema([
            ('form', pa.string()),
            ('company', pa.string()),
            ('cik', pa.int32()),
            ('filing_date', pa.date32()),
            ('accession_number', pa.string()),
        ])
        empty_table = pa.table({
            'form': pa.array([], type=pa.string()),
            'company': pa.array([], type=pa.string()),
            'cik': pa.array([], type=pa.int32()),
            'filing_date': pa.array([], type=pa.date32()),
            'accession_number': pa.array([], type=pa.string()),
        }, schema=schema)
        filings = Filings(filing_index=empty_table)
        return _FundCompanyInfo(
            name="Test Fund Company",
            cik="0001234567",
            ident_info={
                "State location": "NY",
                "State of Inc.": "DE",
                "Class/Contract": "C000012345 Class A",
                "Series": "S000099999 Test Series",
                "Ticker Symbol": "TESTX",
            },
            addresses=["123 Main St\nNew York, NY"],
            filings=filings,
        )

    def test_state(self):
        ci = self._make_company_info()
        assert ci.state == "NY"

    def test_state_of_incorporation(self):
        ci = self._make_company_info()
        assert ci.state_of_incorporation == "DE"

    def test_id_and_name_class_contract(self):
        ci = self._make_company_info()
        result = ci.id_and_name("Class/Contract")
        assert result == ("C000012345", "Class A")

    def test_id_and_name_series(self):
        ci = self._make_company_info()
        result = ci.id_and_name("Series")
        assert result == ("S000099999", "Test Series")

    def test_id_and_name_missing(self):
        ci = self._make_company_info()
        result = ci.id_and_name("NonExistent")
        assert result is None


# ---------------------------------------------------------------------------
# _FundClass and _FundSeries
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestFundClassAndSeries:

    def _make_company_info(self):
        from edgar._filings import Filings
        import pyarrow as pa

        schema = pa.schema([
            ('form', pa.string()),
            ('company', pa.string()),
            ('cik', pa.int32()),
            ('filing_date', pa.date32()),
            ('accession_number', pa.string()),
        ])
        empty_table = pa.table({
            'form': pa.array([], type=pa.string()),
            'company': pa.array([], type=pa.string()),
            'cik': pa.array([], type=pa.int32()),
            'filing_date': pa.array([], type=pa.date32()),
            'accession_number': pa.array([], type=pa.string()),
        }, schema=schema)
        filings = Filings(filing_index=empty_table)
        return _FundCompanyInfo(
            name="Vanguard Inc",
            cik="0000102909",
            ident_info={
                "Class/Contract": "C000012345 Admiral Shares",
                "Series": "S000099999 500 Index Fund",
                "Ticker Symbol": "VFIAX",
            },
            addresses=[],
            filings=filings,
        )

    def test_fund_class_properties(self):
        ci = self._make_company_info()
        fc = _FundClass(ci)
        assert fc.fund_cik == "0000102909"
        assert fc.fund_name == "Vanguard Inc"
        assert fc.id == "C000012345"
        assert fc.name == "Admiral Shares"
        assert fc.ticker == "VFIAX"

    def test_fund_class_description(self):
        ci = self._make_company_info()
        fc = _FundClass(ci)
        desc = fc.description
        assert "Vanguard Inc" in desc
        assert "C000012345" in desc
        assert "Admiral Shares" in desc
        assert "VFIAX" in desc

    def test_fund_class_filings(self):
        ci = self._make_company_info()
        fc = _FundClass(ci)
        assert fc.filings is not None

    def test_fund_series_properties(self):
        ci = self._make_company_info()
        fs = _FundSeries(ci)
        assert fs.fund_cik == "0000102909"
        assert fs.fund_name == "Vanguard Inc"
        assert fs.id == "S000099999"
        assert fs.name == "500 Index Fund"

    def test_fund_series_description(self):
        ci = self._make_company_info()
        fs = _FundSeries(ci)
        desc = fs.description
        assert "Vanguard Inc" in desc
        assert "S000099999" in desc

    def test_fund_class_no_ticker(self):
        from edgar._filings import Filings
        import pyarrow as pa

        schema = pa.schema([
            ('form', pa.string()),
            ('company', pa.string()),
            ('cik', pa.int32()),
            ('filing_date', pa.date32()),
            ('accession_number', pa.string()),
        ])
        empty_table = pa.table({
            'form': pa.array([], type=pa.string()),
            'company': pa.array([], type=pa.string()),
            'cik': pa.array([], type=pa.int32()),
            'filing_date': pa.array([], type=pa.date32()),
            'accession_number': pa.array([], type=pa.string()),
        }, schema=schema)
        filings = Filings(filing_index=empty_table)
        ci = _FundCompanyInfo(
            name="NoTicker Inc", cik="001",
            ident_info={"Class/Contract": "C000099 Some Class"},
            addresses=[], filings=filings,
        )
        fc = _FundClass(ci)
        assert fc.ticker is None

    def test_id_and_name_no_match(self):
        """When ident_info has no matching key, id and name are None."""
        from edgar._filings import Filings
        import pyarrow as pa

        schema = pa.schema([
            ('form', pa.string()),
            ('company', pa.string()),
            ('cik', pa.int32()),
            ('filing_date', pa.date32()),
            ('accession_number', pa.string()),
        ])
        empty_table = pa.table({
            'form': pa.array([], type=pa.string()),
            'company': pa.array([], type=pa.string()),
            'cik': pa.array([], type=pa.int32()),
            'filing_date': pa.array([], type=pa.date32()),
            'accession_number': pa.array([], type=pa.string()),
        }, schema=schema)
        filings = Filings(filing_index=empty_table)
        ci = _FundCompanyInfo(
            name="Empty", cik="001",
            ident_info={},
            addresses=[], filings=filings,
        )
        fs = _FundSeries(ci)
        assert fs.id is None
        assert fs.name is None


# ---------------------------------------------------------------------------
# get_fund_information
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestGetFundInformation:

    def test_none_header(self):
        result = get_fund_information(None)
        assert result is not None  # returns empty FundSeriesAndContracts

    def test_header_without_text(self):
        mock_header = MagicMock(spec=[])  # no .text attribute
        result = get_fund_information(mock_header)
        assert result is not None

    def test_header_with_series_data(self):
        mock_header = MagicMock()
        mock_header.text = """
<SERIES-AND-CLASSES-CONTRACTS-DATA>
<SERIES>
<OWNER-CIK>0001111111
<SERIES-ID>S000001111
<SERIES-NAME>Fund A
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000001111
<CLASS-CONTRACT-NAME>Class A
<CLASS-CONTRACT-TICKER-SYMBOL>AAAAX
</CLASS-CONTRACT>
</SERIES>
</SERIES-AND-CLASSES-CONTRACTS-DATA>
"""
        result = get_fund_information(mock_header)
        assert result is not None

    def test_header_with_no_series_data_fallback(self):
        """Test fallback regex parsing when no SERIES-AND-CLASSES-CONTRACTS-DATA block."""
        mock_header = MagicMock()
        mock_header.text = "Some random header text with no fund info"
        result = get_fund_information(mock_header)
        assert result is not None

    def test_header_with_fallback_series_id_and_contract(self):
        """Test fallback path that uses SERIES-ID/CONTRACT-ID regex."""
        mock_header = MagicMock()
        mock_header.text = """
<FILER>
<COMPANY-DATA>
<CONFORMED-NAME>Test Fund Corp
</COMPANY-DATA>
</FILER>
<SERIES-ID>S000099999
<CONTRACT-ID>C000088888
<TICKER-SYMBOL>TESTX
"""
        result = get_fund_information(mock_header)
        assert result is not None


# ---------------------------------------------------------------------------
# get_fund_object
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestGetFundObject:

    def test_invalid_identifier_returns_none(self):
        # Clear the lru_cache to avoid stale results
        get_fund_object.cache_clear()
        result = get_fund_object("invalid_identifier_xyz")
        assert result is None

    def test_invalid_format_returns_none(self):
        get_fund_object.cache_clear()
        result = get_fund_object("abc123")
        assert result is None

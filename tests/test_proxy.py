"""
Tests for the ProxyStatement data object (DEF 14A filings).

Tests cover:
- Basic creation and metadata
- Executive compensation properties
- Pay vs performance metrics
- Governance indicators
- DataFrame generation
- Rich display
- Form validation
"""
from decimal import Decimal

import pandas as pd
import pytest

from edgar import Company, Filing
from edgar.proxy import ProxyStatement, PROXY_FORMS


# Sample filing for testing - Apple DEF 14A
AppleDEF14A = Filing(
    form='DEF 14A',
    filing_date='2025-01-10',
    company='Apple Inc.',
    cik=320193,
    accession_no='0001308179-25-000008'
)


class TestProxyStatementCreation:
    """Tests for ProxyStatement instantiation."""

    def test_create_from_filing(self):
        """Test creating ProxyStatement from a Filing."""
        proxy = ProxyStatement.from_filing(AppleDEF14A)
        assert proxy is not None
        assert isinstance(proxy, ProxyStatement)

    def test_create_via_obj_method(self):
        """Test creating ProxyStatement via filing.obj()."""
        proxy = AppleDEF14A.obj()
        assert proxy is not None
        assert isinstance(proxy, ProxyStatement)

    def test_invalid_form_raises_error(self):
        """Test that non-proxy form types raise AssertionError."""
        invalid_filing = Filing(
            form='10-K',
            filing_date='2025-01-10',
            company='Apple Inc.',
            cik=320193,
            accession_no='0000320193-24-000093'
        )
        with pytest.raises(AssertionError):
            ProxyStatement(invalid_filing)

    def test_proxy_forms_constant(self):
        """Test that PROXY_FORMS contains expected form types."""
        assert 'DEF 14A' in PROXY_FORMS
        assert 'DEF 14A/A' in PROXY_FORMS
        assert 'DEFA14A' in PROXY_FORMS
        assert 'DEFM14A' in PROXY_FORMS


class TestProxyStatementMetadata:
    """Tests for basic metadata properties."""

    @pytest.fixture
    def proxy(self):
        return ProxyStatement.from_filing(AppleDEF14A)

    def test_form(self, proxy):
        """Test form property."""
        assert proxy.form == 'DEF 14A'

    def test_filing_date(self, proxy):
        """Test filing_date property."""
        assert proxy.filing_date == '2025-01-10'

    def test_cik(self, proxy):
        """Test CIK property."""
        assert proxy.cik == '320193'

    def test_accession_number(self, proxy):
        """Test accession_number property."""
        assert proxy.accession_number == '0001308179-25-000008'

    def test_company_name(self, proxy):
        """Test company_name property from XBRL."""
        assert proxy.company_name == 'Apple Inc.'

    def test_filing_property(self, proxy):
        """Test filing property returns the source filing."""
        assert proxy.filing is not None
        assert proxy.filing.accession_no == AppleDEF14A.accession_no


class TestExecutiveCompensation:
    """Tests for executive compensation properties."""

    @pytest.fixture
    def proxy(self):
        return ProxyStatement.from_filing(AppleDEF14A)

    def test_peo_name(self, proxy):
        """Test PEO (CEO) name extraction."""
        assert proxy.peo_name is not None
        assert 'Cook' in proxy.peo_name

    def test_peo_total_comp(self, proxy):
        """Test PEO total compensation."""
        assert proxy.peo_total_comp is not None
        assert isinstance(proxy.peo_total_comp, Decimal)
        assert proxy.peo_total_comp > 0

    def test_peo_actually_paid_comp(self, proxy):
        """Test PEO compensation actually paid."""
        assert proxy.peo_actually_paid_comp is not None
        assert isinstance(proxy.peo_actually_paid_comp, Decimal)
        assert proxy.peo_actually_paid_comp > 0

    def test_neo_avg_total_comp(self, proxy):
        """Test NEO average total compensation."""
        assert proxy.neo_avg_total_comp is not None
        assert isinstance(proxy.neo_avg_total_comp, Decimal)
        assert proxy.neo_avg_total_comp > 0

    def test_neo_avg_actually_paid_comp(self, proxy):
        """Test NEO average compensation actually paid."""
        assert proxy.neo_avg_actually_paid_comp is not None
        assert isinstance(proxy.neo_avg_actually_paid_comp, Decimal)
        assert proxy.neo_avg_actually_paid_comp > 0


class TestPayVsPerformance:
    """Tests for pay vs performance metrics."""

    @pytest.fixture
    def proxy(self):
        return ProxyStatement.from_filing(AppleDEF14A)

    def test_total_shareholder_return(self, proxy):
        """Test TSR extraction."""
        assert proxy.total_shareholder_return is not None
        assert isinstance(proxy.total_shareholder_return, Decimal)

    def test_peer_group_tsr(self, proxy):
        """Test peer group TSR extraction."""
        assert proxy.peer_group_tsr is not None
        assert isinstance(proxy.peer_group_tsr, Decimal)

    def test_net_income(self, proxy):
        """Test net income extraction."""
        assert proxy.net_income is not None
        assert isinstance(proxy.net_income, Decimal)

    def test_company_selected_measure(self, proxy):
        """Test company-selected performance measure name."""
        assert proxy.company_selected_measure is not None
        assert isinstance(proxy.company_selected_measure, str)

    def test_company_selected_measure_value(self, proxy):
        """Test company-selected measure value."""
        assert proxy.company_selected_measure_value is not None
        assert isinstance(proxy.company_selected_measure_value, Decimal)

    def test_performance_measures(self, proxy):
        """Test list of performance measures."""
        measures = proxy.performance_measures
        assert isinstance(measures, list)
        assert len(measures) > 0


class TestGovernance:
    """Tests for governance indicators."""

    @pytest.fixture
    def proxy(self):
        return ProxyStatement.from_filing(AppleDEF14A)

    def test_insider_trading_policy_adopted(self, proxy):
        """Test insider trading policy flag."""
        # Should be a boolean or None
        value = proxy.insider_trading_policy_adopted
        assert value is None or isinstance(value, bool)


class TestDataFrames:
    """Tests for DataFrame generation."""

    @pytest.fixture
    def proxy(self):
        return ProxyStatement.from_filing(AppleDEF14A)

    def test_executive_compensation_dataframe(self, proxy):
        """Test executive_compensation DataFrame."""
        df = proxy.executive_compensation
        assert isinstance(df, pd.DataFrame)
        assert 'fiscal_year_end' in df.columns
        assert 'peo_total_comp' in df.columns
        assert 'peo_actually_paid_comp' in df.columns
        assert 'neo_avg_total_comp' in df.columns
        assert 'neo_avg_actually_paid_comp' in df.columns

    def test_executive_compensation_has_data(self, proxy):
        """Test executive_compensation has 5-year data."""
        df = proxy.executive_compensation
        # Pay vs Performance data is typically 5 years
        assert len(df) >= 1

    def test_pay_vs_performance_dataframe(self, proxy):
        """Test pay_vs_performance DataFrame."""
        df = proxy.pay_vs_performance
        assert isinstance(df, pd.DataFrame)
        assert 'fiscal_year_end' in df.columns
        assert 'peo_actually_paid_comp' in df.columns
        assert 'total_shareholder_return' in df.columns
        assert 'peer_group_tsr' in df.columns
        assert 'net_income' in df.columns

    def test_pay_vs_performance_has_data(self, proxy):
        """Test pay_vs_performance has data."""
        df = proxy.pay_vs_performance
        assert len(df) >= 1


class TestNamedExecutives:
    """Tests for named executive officer data."""

    @pytest.fixture
    def proxy(self):
        return ProxyStatement.from_filing(AppleDEF14A)

    def test_has_individual_executive_data(self, proxy):
        """Test detection of dimensional executive data."""
        value = proxy.has_individual_executive_data
        assert isinstance(value, bool)

    def test_named_executives(self, proxy):
        """Test named executives list."""
        executives = proxy.named_executives
        assert isinstance(executives, list)
        # May be empty if dimensional data not available


class TestDisplay:
    """Tests for string and rich display methods."""

    @pytest.fixture
    def proxy(self):
        return ProxyStatement.from_filing(AppleDEF14A)

    def test_str_representation(self, proxy):
        """Test __str__ output."""
        s = str(proxy)
        assert 'DEF 14A' in s
        assert 'Apple' in s

    def test_repr_representation(self, proxy):
        """Test __repr__ output (rich display)."""
        r = repr(proxy)
        assert 'DEF 14A' in r
        # Rich output should include compensation data
        assert '$' in r

    def test_rich_method(self, proxy):
        """Test __rich__ returns Group object."""
        from rich.console import Group
        rich_output = proxy.__rich__()
        assert isinstance(rich_output, Group)


class TestAmendments:
    """Tests for handling amendment filings."""

    def test_amendment_in_str(self):
        """Test that amendments show in string representation."""
        # Create a mock amendment filing (if available)
        # For now, test the string formatting logic
        proxy = ProxyStatement.from_filing(AppleDEF14A)
        s = str(proxy)
        # Regular DEF 14A should not show Amendment
        if '/A' not in proxy.form:
            assert 'Amendment' not in s


class TestXBRLAvailability:
    """Tests for XBRL data availability."""

    @pytest.fixture
    def proxy(self):
        return ProxyStatement.from_filing(AppleDEF14A)

    def test_has_xbrl_property(self, proxy):
        """Test has_xbrl property returns True for AAPL."""
        assert proxy.has_xbrl is True

    def test_has_xbrl_is_python_bool(self, proxy):
        """Test has_xbrl returns Python bool, not numpy bool."""
        assert isinstance(proxy.has_xbrl, bool)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_fiscal_year_end_may_be_none(self):
        """Test graceful handling when fiscal_year_end is not available."""
        proxy = ProxyStatement.from_filing(AppleDEF14A)
        # Should not raise even if fiscal_year_end is None
        fiscal_year = proxy.fiscal_year_end
        # Just ensure it doesn't crash
        assert fiscal_year is None or isinstance(fiscal_year, str)

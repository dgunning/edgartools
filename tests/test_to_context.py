"""Tests for to_context() implementations on DataObject classes."""
from decimal import Decimal

import pytest

from edgar.display.formatting import format_currency_short


class TestFormatCurrencyShort:
    """Unit tests for the shared currency formatting helper."""

    def test_none_returns_empty(self):
        assert format_currency_short(None) == ""

    def test_nan_returns_empty(self):
        assert format_currency_short(float('nan')) == ""

    def test_zero(self):
        assert format_currency_short(0) == "$0.00"

    def test_small_value(self):
        assert format_currency_short(42.50) == "$42.50"

    def test_thousands(self):
        assert format_currency_short(42_500) == "$42,500"

    def test_millions(self):
        assert format_currency_short(18_550_000) == "$18.6M"

    def test_billions(self):
        assert format_currency_short(394_328_000_000) == "$394.3B"

    def test_negative(self):
        assert format_currency_short(-1_200_000) == "-$1.2M"

    def test_decimal_input(self):
        result = format_currency_short(Decimal('1234567890'))
        assert result == "$1.2B"

    def test_non_numeric_returns_empty(self):
        assert format_currency_short("not a number") == ""

    def test_boundary_million(self):
        assert format_currency_short(1_000_000) == "$1.0M"

    def test_boundary_billion(self):
        assert format_currency_short(1_000_000_000) == "$1.0B"


class TestTenKToContext:
    """Tests for TenK.to_context() using a known filing."""

    @pytest.fixture(scope="class")
    def tenk(self):
        """Load a real Apple 10-K for testing."""
        from edgar import Company
        filing = Company("AAPL").get_filings(form="10-K").latest()
        return filing.obj()

    @pytest.mark.network
    def test_minimal_format(self, tenk):
        ctx = tenk.to_context('minimal')
        assert isinstance(ctx, str)
        assert ctx.startswith("TENK:")
        assert "Apple" in ctx
        assert "Period:" in ctx or "Filed:" in ctx

    @pytest.mark.network
    def test_minimal_token_budget(self, tenk):
        ctx = tenk.to_context('minimal')
        tokens = len(ctx) // 4
        assert tokens < 200

    @pytest.mark.network
    def test_standard_format(self, tenk):
        ctx = tenk.to_context('standard')
        assert "AVAILABLE ACTIONS:" in ctx
        assert ".financials" in ctx
        assert "SECTIONS:" in ctx
        assert "FINANCIALS:" in ctx

    @pytest.mark.network
    def test_standard_token_budget(self, tenk):
        ctx = tenk.to_context('standard')
        tokens = len(ctx) // 4
        assert 150 < tokens < 500

    @pytest.mark.network
    def test_full_has_more_than_standard(self, tenk):
        std = tenk.to_context('standard')
        full = tenk.to_context('full')
        assert len(full) > len(std)

    @pytest.mark.network
    def test_full_has_auditor(self, tenk):
        ctx = tenk.to_context('full')
        assert "AUDITOR:" in ctx

    @pytest.mark.network
    def test_no_duplicate_financials_in_standard(self, tenk):
        ctx = tenk.to_context('standard')
        # Revenue should only appear once (in FINANCIALS section, not at top)
        assert ctx.count("Revenue:") == 1


class TestForm4ToContext:
    """Tests for Form4.to_context() using a known filing."""

    @pytest.fixture(scope="class")
    def form4(self):
        """Load a real Form 4."""
        from edgar import get_filings
        filings = get_filings(form="4")
        filing = filings[0]
        return filing.obj()

    @pytest.mark.network
    def test_minimal_format(self, form4):
        ctx = form4.to_context('minimal')
        assert isinstance(ctx, str)
        assert ctx.startswith("FORM4:") or ctx.startswith("FORM3:") or ctx.startswith("FORM5:")
        assert "Issuer:" in ctx
        assert "Owner:" in ctx

    @pytest.mark.network
    def test_standard_format(self, form4):
        ctx = form4.to_context('standard')
        assert "AVAILABLE ACTIONS:" in ctx
        assert "Relationship:" in ctx

    @pytest.mark.network
    def test_standard_has_transactions_or_holdings(self, form4):
        ctx = form4.to_context('standard')
        # Should have either TRANSACTIONS (Form 4/5) or HOLDINGS (Form 3)
        assert "TRANSACTIONS:" in ctx or "HOLDINGS:" in ctx or "No securities" in ctx

    @pytest.mark.network
    def test_standard_token_budget(self, form4):
        ctx = form4.to_context('standard')
        tokens = len(ctx) // 4
        assert tokens < 600


class TestTenQToContext:
    """Tests for TenQ.to_context()."""

    @pytest.fixture(scope="class")
    def tenq(self):
        from edgar import Company
        filing = Company("MSFT").get_filings(form="10-Q").latest()
        return filing.obj()

    @pytest.mark.network
    def test_minimal_format(self, tenq):
        ctx = tenq.to_context('minimal')
        assert ctx.startswith("TENQ:")
        assert "Quarterly Report" in ctx
        assert "Period:" in ctx or "Filed:" in ctx

    @pytest.mark.network
    def test_standard_has_actions(self, tenq):
        ctx = tenq.to_context('standard')
        assert "AVAILABLE ACTIONS:" in ctx
        assert ".financials" in ctx

    @pytest.mark.network
    def test_standard_token_budget(self, tenq):
        ctx = tenq.to_context('standard')
        tokens = len(ctx) // 4
        assert tokens < 500


class TestCurrentReportToContext:
    """Tests for CurrentReport/EightK.to_context()."""

    @pytest.fixture(scope="class")
    def eightk(self):
        from edgar import get_filings
        filing = get_filings(form="8-K")[0]
        return filing.obj()

    @pytest.mark.network
    def test_minimal_format(self, eightk):
        ctx = eightk.to_context('minimal')
        assert "Current Report" in ctx
        assert "Filed:" in ctx

    @pytest.mark.network
    def test_minimal_has_items(self, eightk):
        ctx = eightk.to_context('minimal')
        assert "Items:" in ctx or "Filed:" in ctx  # Items may be empty for some filings

    @pytest.mark.network
    def test_standard_has_actions(self, eightk):
        ctx = eightk.to_context('standard')
        assert "AVAILABLE ACTIONS:" in ctx
        assert ".items" in ctx

    @pytest.mark.network
    def test_standard_token_budget(self, eightk):
        ctx = eightk.to_context('standard')
        tokens = len(ctx) // 4
        assert tokens < 600


class TestProxyStatementToContext:
    """Tests for ProxyStatement.to_context()."""

    @pytest.fixture(scope="class")
    def proxy(self):
        from edgar import Company
        filing = Company("AAPL").get_filings(form="DEF 14A").latest()
        return filing.obj()

    @pytest.mark.network
    def test_minimal_format(self, proxy):
        ctx = proxy.to_context('minimal')
        assert ctx.startswith("PROXY:")
        assert "Filed:" in ctx

    @pytest.mark.network
    def test_standard_has_compensation(self, proxy):
        ctx = proxy.to_context('standard')
        assert "EXECUTIVE COMPENSATION:" in ctx or "AVAILABLE ACTIONS:" in ctx

    @pytest.mark.network
    def test_standard_has_actions(self, proxy):
        ctx = proxy.to_context('standard')
        assert "AVAILABLE ACTIONS:" in ctx

    @pytest.mark.network
    def test_standard_token_budget(self, proxy):
        ctx = proxy.to_context('standard')
        tokens = len(ctx) // 4
        assert tokens < 600


class TestStatementToContext:
    """Tests for individual Statement.to_context()."""

    @pytest.fixture(scope="class")
    def statement(self):
        from edgar import Company
        fin = Company("AAPL").get_financials()
        return fin.income_statement()

    @pytest.mark.network
    def test_minimal_format(self, statement):
        ctx = statement.to_context('minimal')
        assert ctx.startswith("STATEMENT:")
        assert "Entity:" in ctx
        assert "Line Items:" in ctx

    @pytest.mark.network
    def test_standard_has_key_items(self, statement):
        ctx = statement.to_context('standard')
        assert "KEY LINE ITEMS:" in ctx
        assert "$" in ctx  # Should have formatted dollar values

    @pytest.mark.network
    def test_standard_has_actions(self, statement):
        ctx = statement.to_context('standard')
        assert "AVAILABLE ACTIONS:" in ctx
        assert ".to_dataframe()" in ctx

    @pytest.mark.network
    def test_no_rich_markup_leak(self, statement):
        ctx = statement.to_context('standard')
        # No Rich markup tags should leak into output
        assert "[italic]" not in ctx
        assert "[/italic]" not in ctx
        assert "[bold]" not in ctx

    @pytest.mark.network
    def test_standard_token_budget(self, statement):
        ctx = statement.to_context('standard')
        tokens = len(ctx) // 4
        assert tokens < 600


class TestThirteenFToContext:
    """Tests for ThirteenF.to_context() using a known filing."""

    @pytest.fixture(scope="class")
    def thirteenf(self):
        """Load a real 13F-HR."""
        from edgar import get_filings
        filings = get_filings(form="13F-HR")
        filing = filings[0]
        return filing.obj()

    @pytest.mark.network
    def test_minimal_format(self, thirteenf):
        ctx = thirteenf.to_context('minimal')
        assert isinstance(ctx, str)
        assert ctx.startswith("THIRTEENF:")
        assert "Report Date:" in ctx
        assert "Total Value:" in ctx

    @pytest.mark.network
    def test_minimal_token_budget(self, thirteenf):
        ctx = thirteenf.to_context('minimal')
        tokens = len(ctx) // 4
        assert tokens < 150

    @pytest.mark.network
    def test_standard_format(self, thirteenf):
        ctx = thirteenf.to_context('standard')
        assert "TOP HOLDINGS:" in ctx
        assert "AVAILABLE ACTIONS:" in ctx
        assert "$" in ctx  # Should have dollar values

    @pytest.mark.network
    def test_standard_token_budget(self, thirteenf):
        ctx = thirteenf.to_context('standard')
        tokens = len(ctx) // 4
        assert 150 < tokens < 600

    @pytest.mark.network
    def test_full_has_more_than_standard(self, thirteenf):
        std = thirteenf.to_context('standard')
        full = thirteenf.to_context('full')
        assert len(full) >= len(std)

    @pytest.mark.network
    def test_standard_top_holdings_count(self, thirteenf):
        ctx = thirteenf.to_context('standard')
        # Count lines with $ in TOP HOLDINGS section
        in_holdings = False
        holding_lines = 0
        for line in ctx.split('\n'):
            if line == "TOP HOLDINGS:":
                in_holdings = True
                continue
            if in_holdings:
                if line.startswith("  ") and "$" in line:
                    holding_lines += 1
                elif not line.startswith("  "):
                    break
        assert holding_lines <= 5

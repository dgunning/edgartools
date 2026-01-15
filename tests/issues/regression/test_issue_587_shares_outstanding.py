"""
Regression test for Issue #587: Add get_shares_outstanding to Financials API

Feature request to add standardized access to weighted average shares outstanding
alongside other normalized methods like get_revenue(), get_net_income(), etc.

User requested:
- company.get_financials().get_shares_outstanding_basic(period_offset=X)
- company.get_quarterly_financials().get_shares_outstanding_basic(period_offset=X)

Implementation:
- Added get_shares_outstanding_basic() for basic weighted average shares
- Added get_shares_outstanding_diluted() for diluted weighted average shares
- Both methods search by XBRL concept name for reliability across companies

Reporter: maupardh1 (Hadrien Maupard)
See: https://github.com/dgunning/edgartools/issues/587
"""
import pytest


class TestIssue587SharesOutstanding:
    """Test shares outstanding methods on Financials class."""

    @pytest.fixture
    def aapl_financials(self):
        """Get AAPL annual financials for testing."""
        from edgar import Company
        company = Company("AAPL")
        return company.get_financials()

    @pytest.fixture
    def aapl_quarterly(self):
        """Get AAPL quarterly financials for testing."""
        from edgar import Company
        company = Company("AAPL")
        return company.get_quarterly_financials()

    @pytest.mark.network
    def test_get_shares_outstanding_basic(self, aapl_financials):
        """Test that get_shares_outstanding_basic() returns valid data for AAPL."""
        shares = aapl_financials.get_shares_outstanding_basic()

        assert shares is not None, "AAPL should have basic shares data"
        assert isinstance(shares, (int, float)), "Shares should be numeric"
        assert shares > 1_000_000_000, "AAPL should have billions of shares"
        assert shares < 100_000_000_000, "Shares should be reasonable"

    @pytest.mark.network
    def test_get_shares_outstanding_diluted(self, aapl_financials):
        """Test that get_shares_outstanding_diluted() returns valid data for AAPL."""
        shares = aapl_financials.get_shares_outstanding_diluted()

        assert shares is not None, "AAPL should have diluted shares data"
        assert isinstance(shares, (int, float)), "Shares should be numeric"
        assert shares > 1_000_000_000, "AAPL should have billions of shares"

    @pytest.mark.network
    def test_diluted_greater_than_basic(self, aapl_financials):
        """Test that diluted shares >= basic shares (dilution effect)."""
        basic = aapl_financials.get_shares_outstanding_basic()
        diluted = aapl_financials.get_shares_outstanding_diluted()

        assert basic is not None and diluted is not None
        assert diluted >= basic, "Diluted shares should be >= basic shares"

    @pytest.mark.network
    def test_period_offset(self, aapl_financials):
        """Test that period_offset parameter works correctly."""
        current = aapl_financials.get_shares_outstanding_basic(period_offset=0)
        previous = aapl_financials.get_shares_outstanding_basic(period_offset=1)

        assert current is not None, "Current period should have data"
        assert previous is not None, "Previous period should have data"
        # Values should be different (AAPL has been buying back shares)
        assert current != previous, "Different periods should have different values"

    @pytest.mark.network
    def test_quarterly_financials(self, aapl_quarterly):
        """Test that shares outstanding works with quarterly financials.

        This was specifically requested in Issue #587.
        """
        shares = aapl_quarterly.get_shares_outstanding_basic()

        # Quarterly financials should also have shares data
        assert shares is not None, "Quarterly financials should have shares data"
        assert isinstance(shares, (int, float))
        assert shares > 1_000_000_000

    @pytest.mark.network
    def test_get_financial_metrics_includes_shares(self, aapl_financials):
        """Test that get_financial_metrics() includes shares outstanding."""
        metrics = aapl_financials.get_financial_metrics()

        assert 'shares_outstanding_basic' in metrics
        assert 'shares_outstanding_diluted' in metrics
        assert metrics['shares_outstanding_basic'] is not None
        assert metrics['shares_outstanding_diluted'] is not None

    @pytest.mark.network
    def test_msft_shares_outstanding(self):
        """Test shares outstanding for MSFT (different company)."""
        from edgar import Company
        company = Company("MSFT")
        financials = company.get_financials()

        basic = financials.get_shares_outstanding_basic()
        diluted = financials.get_shares_outstanding_diluted()

        assert basic is not None, "MSFT should have basic shares data"
        assert diluted is not None, "MSFT should have diluted shares data"
        assert basic > 5_000_000_000, "MSFT should have billions of shares"

    @pytest.mark.network
    def test_returns_none_when_unavailable(self):
        """Test that method returns None gracefully when data unavailable.

        Some companies don't report weighted average shares in the standard
        income statement format (e.g., GOOGL only reports EPS).
        """
        from edgar import Company

        # GOOGL is known to not have shares in income statement
        company = Company("GOOGL")
        financials = company.get_financials()

        # Should return None, not raise an exception
        basic = financials.get_shares_outstanding_basic()
        diluted = financials.get_shares_outstanding_diluted()

        # None is acceptable - just verify no exception
        # (GOOGL might have data in some periods, so we don't assert None)
        assert basic is None or isinstance(basic, (int, float))
        assert diluted is None or isinstance(diluted, (int, float))

    @pytest.mark.network
    def test_user_example_from_issue(self):
        """Test the exact example from Issue #587.

        User's requested API:
        company.get_financials().get_shares_outstanding(period_offset=3)
        company.get_quarterly_financials().get_shares_outstanding(period_offset=2)

        Note: We implemented as get_shares_outstanding_basic() and
        get_shares_outstanding_diluted() for clarity between the two metrics.
        """
        from edgar import Company

        company = Company("AAPL")

        # Annual financials with period_offset
        financials = company.get_financials()
        shares_annual = financials.get_shares_outstanding_basic(period_offset=0)
        assert shares_annual is not None

        # Quarterly financials with period_offset
        quarterly = company.get_quarterly_financials()
        shares_quarterly = quarterly.get_shares_outstanding_basic(period_offset=0)
        assert shares_quarterly is not None

        # Both should return reasonable values for AAPL
        assert shares_annual > 10_000_000_000  # ~15B shares
        assert shares_quarterly > 10_000_000_000

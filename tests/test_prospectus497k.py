"""
Verification tests for Prospectus497K (497K Summary Prospectus data object).

Ground truth values are hand-verified from actual SEC filings.
"""
import pytest
from decimal import Decimal

from edgar import find, get_obj_info
from edgar.funds.prospectus497k import Prospectus497K, ShareClassFees, PerformanceReturn


# ---------------------------------------------------------------------------
# Ground truth: Vanguard California Long-Term Tax-Exempt Fund
# Filing: 0001683863-25-002784, Series S000002567
# ---------------------------------------------------------------------------

class TestVanguard497K:
    """Vanguard 497K with 2 share classes: Investor (VCITX) and Admiral (VCLAX)."""

    @pytest.fixture(scope="class")
    def prospectus(self):
        filing = find("0001683863-25-002784")
        p = filing.obj()
        assert isinstance(p, Prospectus497K)
        return p

    @pytest.mark.network
    @pytest.mark.vcr
    def test_fund_identity(self, prospectus):
        assert prospectus.fund_name == "Vanguard California Long-Term Tax-Exempt Fund"
        assert prospectus.series_id == "S000002567"
        assert prospectus.tickers == ["VCITX", "VCLAX"]
        assert prospectus.num_share_classes == 2

    @pytest.mark.network
    @pytest.mark.vcr
    def test_investor_shares_fees(self, prospectus):
        investor = prospectus.share_classes[0]
        assert investor.class_name == "Investor Shares"
        assert investor.ticker == "VCITX"
        assert investor.management_fee == Decimal("0.13")
        assert investor.total_annual_expenses == Decimal("0.14")
        assert investor.twelve_b1_fee is None

    @pytest.mark.network
    @pytest.mark.vcr
    def test_admiral_shares_fees(self, prospectus):
        admiral = prospectus.share_classes[1]
        assert admiral.class_name == "Admiral Shares"
        assert admiral.ticker == "VCLAX"
        assert admiral.management_fee == Decimal("0.08")
        assert admiral.total_annual_expenses == Decimal("0.09")

    @pytest.mark.network
    @pytest.mark.vcr
    def test_expense_example(self, prospectus):
        investor = prospectus.share_classes[0]
        assert investor.expense_1yr == 14
        assert investor.expense_3yr == 45
        assert investor.expense_5yr == 79
        assert investor.expense_10yr == 179

        admiral = prospectus.share_classes[1]
        assert admiral.expense_1yr == 9

    @pytest.mark.network
    @pytest.mark.vcr
    def test_performance_returns(self, prospectus):
        df = prospectus.performance
        assert not df.empty

        # Investor Shares 1yr return = 2.09%
        before_tax = df[df['label'] == 'Return Before Taxes']
        assert len(before_tax) >= 1
        assert before_tax.iloc[0]['1yr'] == Decimal("2.09")

        # Admiral Shares 1yr return = 2.17%
        assert before_tax.iloc[1]['1yr'] == Decimal("2.17")

    @pytest.mark.network
    @pytest.mark.vcr
    def test_benchmark_returns(self, prospectus):
        df = prospectus.performance
        bloomberg = df[df['label'].str.contains('Bloomberg CA Municipal', na=False)]
        assert len(bloomberg) >= 1
        assert bloomberg.iloc[0]['1yr'] == Decimal("1.02")

    @pytest.mark.network
    @pytest.mark.vcr
    def test_best_worst_quarter(self, prospectus):
        best = prospectus.best_quarter
        assert best is not None
        assert best[0] == Decimal("8.80")
        assert "December 31, 2023" in best[1]

        worst = prospectus.worst_quarter
        assert worst is not None
        assert worst[0] == Decimal("-6.78")
        assert "March 31, 2022" in worst[1]

    @pytest.mark.network
    @pytest.mark.vcr
    def test_portfolio_turnover(self, prospectus):
        assert prospectus.portfolio_turnover == Decimal("81")

    @pytest.mark.network
    @pytest.mark.vcr
    def test_fees_dataframe(self, prospectus):
        df = prospectus.fees
        assert len(df) == 2
        assert list(df.columns) == [
            'class_name', 'ticker', 'management_fee', 'twelve_b1_fee',
            'other_expenses', 'total_annual_expenses', 'fee_waiver', 'net_expenses'
        ]

    @pytest.mark.network
    @pytest.mark.vcr
    def test_expense_example_dataframe(self, prospectus):
        df = prospectus.expense_example
        assert len(df) == 2
        assert '1yr' in df.columns
        assert '10yr' in df.columns


# ---------------------------------------------------------------------------
# Ground truth: Fidelity Equity-Income Fund
# Filing: 0000035341-25-000099, Series S000006064
# ---------------------------------------------------------------------------

class TestFidelity497K:
    """Fidelity 497K with 2 share classes in separate HTML sections."""

    @pytest.fixture(scope="class")
    def prospectus(self):
        filing = find("0000035341-25-000099")
        p = filing.obj()
        assert isinstance(p, Prospectus497K)
        return p

    @pytest.mark.network
    @pytest.mark.vcr
    def test_fund_identity(self, prospectus):
        assert prospectus.fund_name == "Fidelity Equity-Income Fund"
        assert prospectus.series_id == "S000006064"
        assert set(prospectus.tickers) == {"FEQIX", "FEIKX"}

    @pytest.mark.network
    @pytest.mark.vcr
    def test_class_k_fees(self, prospectus):
        # Class K (FEIKX) has mgmt=0.45%, total=0.46%
        class_k = next(sc for sc in prospectus.share_classes if sc.ticker == "FEIKX")
        assert class_k.management_fee == Decimal("0.45")
        assert class_k.total_annual_expenses == Decimal("0.46")

    @pytest.mark.network
    @pytest.mark.vcr
    def test_class_k_expense_example(self, prospectus):
        class_k = next(sc for sc in prospectus.share_classes if sc.ticker == "FEIKX")
        assert class_k.expense_1yr == 47
        assert class_k.expense_3yr == 148

    @pytest.mark.network
    @pytest.mark.vcr
    def test_class_k_performance(self, prospectus):
        df = prospectus.performance
        class_k_rows = df[df['label'] == 'Class K']
        assert len(class_k_rows) >= 1
        assert class_k_rows.iloc[0]['1yr'] == Decimal("15.37")
        assert class_k_rows.iloc[0]['5yr'] == Decimal("10.05")
        assert class_k_rows.iloc[0]['10yr'] == Decimal("9.33")

    @pytest.mark.network
    @pytest.mark.vcr
    def test_best_worst_quarter(self, prospectus):
        best = prospectus.best_quarter
        assert best is not None
        assert best[0] == Decimal("15.54")
        assert "December 31, 2020" in best[1]

        worst = prospectus.worst_quarter
        assert worst is not None
        assert worst[0] == Decimal("-22.03")
        assert "March 31, 2020" in worst[1]


# ---------------------------------------------------------------------------
# Dispatch and integration tests
# ---------------------------------------------------------------------------

class TestProspectus497KDispatch:

    @pytest.mark.network
    @pytest.mark.vcr
    def test_obj_dispatches_for_497k(self):
        filing = find("0001683863-25-002784")
        p = filing.obj()
        assert isinstance(p, Prospectus497K)

    def test_get_obj_info(self):
        has_obj, name, desc = get_obj_info("497K")
        assert has_obj is True
        assert name == "Prospectus497K"
        assert "summary prospectus" in desc

    def test_import_from_funds(self):
        from edgar.funds import Prospectus497K as P497K, PROSPECTUS497K_FORMS
        assert P497K is Prospectus497K
        assert "497K" in PROSPECTUS497K_FORMS


# ---------------------------------------------------------------------------
# Display and context tests
# ---------------------------------------------------------------------------

class TestProspectus497KDisplay:

    @pytest.fixture(scope="class")
    def prospectus(self):
        filing = find("0001683863-25-002784")
        return filing.obj()

    @pytest.mark.network
    @pytest.mark.vcr
    def test_str(self, prospectus):
        s = str(prospectus)
        assert "Prospectus497K" in s
        assert "Vanguard" in s

    @pytest.mark.network
    @pytest.mark.vcr
    def test_repr(self, prospectus):
        r = repr(prospectus)
        assert "Vanguard" in r

    @pytest.mark.network
    @pytest.mark.vcr
    def test_to_context_minimal(self, prospectus):
        ctx = prospectus.to_context('minimal')
        assert "PROSPECTUS497K" in ctx
        assert "VCITX" in ctx

    @pytest.mark.network
    @pytest.mark.vcr
    def test_to_context_standard(self, prospectus):
        ctx = prospectus.to_context('standard')
        assert "AVAILABLE ACTIONS" in ctx
        assert "Total Expenses" in ctx

    @pytest.mark.network
    @pytest.mark.vcr
    def test_to_context_full(self, prospectus):
        ctx = prospectus.to_context('full')
        assert "PERFORMANCE:" in ctx

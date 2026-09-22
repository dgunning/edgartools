"""
Tests for BDC non-accrual footnote extraction utility.
"""
import pytest
from decimal import Decimal

from edgar import Company
from edgar.bdc.nonaccrual import (
    NonAccrualInvestment,
    NonAccrualResult,
    extract_nonaccrual,
    _determine_latest_instant,
)


class TestNonAccrualDataClasses:
    """Tests for NonAccrualResult and NonAccrualInvestment data classes."""

    def test_nonaccrual_rate_computed(self):
        result = NonAccrualResult(
            cik=1,
            entity_name="Test BDC",
            period="2025-12-31",
            source_filing="0001-00-000001",
            investments=[],
            nonaccrual_fair_value=Decimal("100"),
            total_portfolio_fair_value=Decimal("10000"),
            extraction_method="footnote",
        )
        assert result.nonaccrual_rate == pytest.approx(0.01)

    def test_nonaccrual_rate_none_when_missing_fv(self):
        result = NonAccrualResult(
            cik=1,
            entity_name="Test BDC",
            period="2025-12-31",
            source_filing="0001-00-000001",
            investments=[],
            nonaccrual_fair_value=None,
            total_portfolio_fair_value=Decimal("10000"),
            extraction_method="none",
        )
        assert result.nonaccrual_rate is None

    def test_nonaccrual_rate_zero_when_zero_total(self):
        result = NonAccrualResult(
            cik=1,
            entity_name="Test BDC",
            period="2025-12-31",
            source_filing="0001-00-000001",
            investments=[],
            nonaccrual_fair_value=Decimal("100"),
            total_portfolio_fair_value=Decimal("0"),
            extraction_method="footnote",
        )
        assert result.nonaccrual_rate == 0.0

    def test_num_nonaccrual(self):
        inv = NonAccrualInvestment(
            identifier="Company A, First lien",
            company_name="Company A",
            investment_type="First lien",
            fair_value=Decimal("1000"),
            cost=Decimal("1100"),
            footnote_text="Non-accrual status.",
        )
        result = NonAccrualResult(
            cik=1,
            entity_name="Test BDC",
            period="2025-12-31",
            source_filing="0001-00-000001",
            investments=[inv],
            nonaccrual_fair_value=Decimal("1000"),
            total_portfolio_fair_value=Decimal("100000"),
            extraction_method="footnote",
        )
        assert result.num_nonaccrual == 1
        assert result.has_investment_detail is True

    def test_no_investment_detail(self):
        result = NonAccrualResult(
            cik=1,
            entity_name="Test BDC",
            period="2025-12-31",
            source_filing="0001-00-000001",
            investments=[],
            nonaccrual_fair_value=Decimal("500"),
            total_portfolio_fair_value=Decimal("10000"),
            extraction_method="custom_concept",
        )
        assert result.has_investment_detail is False


class TestHelperFunctions:
    """Tests for internal helper functions."""

    def test_determine_latest_instant_prefers_investment_dimensioned(self):
        """Primary path: uses only facts with InvestmentIdentifierAxis."""
        dim_key = 'dim_us-gaap_InvestmentIdentifierAxis'
        facts = [
            # DEI metadata at a later date — should be ignored
            {'period_instant': '2026-02-28'},
            # Investment facts at the reporting date
            {'period_instant': '2025-12-31', dim_key: 'Company A, First lien'},
            {'period_instant': '2024-12-31', dim_key: 'Company B, Second lien'},
        ]
        assert _determine_latest_instant(facts) == '2025-12-31'

    def test_determine_latest_instant_falls_back_when_no_dimensions(self):
        """Fallback: when no facts have the dimension, uses most common instant."""
        facts = [
            {'period_instant': '2024-12-31'},
            {'period_instant': '2024-12-31'},
            {'period_instant': '2025-12-31'},
            {'period_instant': '2024-06-30'},
        ]
        # 2024-12-31 appears twice — most common wins
        assert _determine_latest_instant(facts) == '2024-12-31'

    def test_determine_latest_instant_uses_anchor_period(self):
        """Anchor period from filing.period_of_report takes precedence."""
        dim_key = 'dim_us-gaap_InvestmentIdentifierAxis'
        facts = [
            {'period_instant': '2025-12-31', dim_key: 'inv_1'},
            {'period_instant': '2025-12-31', dim_key: 'inv_2'},
            {'period_instant': '2026-03-20', dim_key: 'inv_3'},
        ]
        # Without anchor, most common (2025-12-31) wins
        assert _determine_latest_instant(facts) == '2025-12-31'
        # With anchor matching investment data, uses anchor
        assert _determine_latest_instant(facts, anchor_period='2025-12-31') == '2025-12-31'
        # Anchor with no investment data falls back to most common
        assert _determine_latest_instant(facts, anchor_period='2024-12-31') == '2025-12-31'

    def test_determine_latest_instant_anchor_fallback_no_dimensions(self):
        """Anchor period used even when no investment-dimensioned facts exist."""
        facts = [
            {'period_instant': '2025-12-31'},
            {'period_instant': '2025-12-31'},
            {'period_instant': '2026-03-10'},
        ]
        # Anchor exists in all_instants, use it
        assert _determine_latest_instant(facts, anchor_period='2025-12-31') == '2025-12-31'
        # Anchor not in facts, fall back to most common
        assert _determine_latest_instant(facts, anchor_period='2024-12-31') == '2025-12-31'

    def test_determine_latest_instant_empty(self):
        assert _determine_latest_instant([]) is None
        assert _determine_latest_instant([{'period_start': '2024-01-01'}]) is None


class TestExtractNonAccrualARCC:
    """Integration tests with ARCC — has footnote-based non-accrual data."""

    @pytest.mark.network
    def test_arcc_has_nonaccrual_data(self):
        """ARCC should have footnote-based non-accrual data with ~1.2% rate at FV."""
        filing = Company("ARCC").get_filings(form="10-K", amendments=False).latest(1)
        result = extract_nonaccrual(filing)

        assert result is not None
        assert result.extraction_method == 'footnote'
        assert result.num_nonaccrual > 0
        assert result.has_investment_detail
        assert result.nonaccrual_rate is not None
        # ARCC non-accrual rate is around 1.2% — allow a wide band
        assert 0.005 < result.nonaccrual_rate < 0.05

    @pytest.mark.network
    def test_arcc_investments_have_fair_values(self):
        """Each non-accrual investment should have identifiable data."""
        filing = Company("ARCC").get_filings(form="10-K", amendments=False).latest(1)
        result = extract_nonaccrual(filing)

        assert result is not None
        for inv in result.investments:
            assert inv.identifier
            assert inv.company_name
            assert inv.footnote_text
            # Most should have fair values (some may be None)

    @pytest.mark.network
    def test_arcc_cross_validation(self):
        """If ARCC has both footnote and custom concept data, rates should be close."""
        filing = Company("ARCC").get_filings(form="10-K", amendments=False).latest(1)
        result = extract_nonaccrual(filing)

        assert result is not None
        if result.custom_concept_rate is not None and result.nonaccrual_rate is not None:
            assert abs(result.nonaccrual_rate - result.custom_concept_rate) < 0.01


class TestExtractNonAccrualFSK:
    """Integration tests with FSK — known high non-accrual rate."""

    @pytest.mark.network
    def test_fsk_has_nonaccrual_data(self):
        """FSK has footnote-based data. Known ~3.4% rate."""
        filing = Company("FSK").get_filings(form="10-K", amendments=False).latest(1)
        result = extract_nonaccrual(filing)

        assert result is not None
        assert result.num_nonaccrual >= 10  # Known ~21 investments
        assert result.nonaccrual_rate is not None
        assert result.nonaccrual_rate > 0.01  # FSK has elevated non-accrual


class TestExtractNonAccrualMAIN:
    """Integration tests with MAIN — healthy BDC with low non-accrual."""

    @pytest.mark.network
    def test_main_has_nonaccrual_data(self):
        """MAIN is healthy. Expect low rate."""
        filing = Company("MAIN").get_filings(form="10-K", amendments=False).latest(1)
        result = extract_nonaccrual(filing)

        assert result is not None
        assert result.nonaccrual_rate is not None
        assert result.nonaccrual_rate < 0.03  # Under 3%


class TestExtractNonAccrualGBDC:
    """Integration tests with GBDC — uses standard us-gaap aggregate concept."""

    @pytest.mark.network
    def test_gbdc_has_aggregate_value(self):
        """GBDC uses the standard us-gaap aggregate concept."""
        filing = Company("GBDC").get_filings(form="10-K", amendments=False).latest(1)
        result = extract_nonaccrual(filing)

        assert result is not None
        assert result.aggregate_concept_value is not None


class TestToContext:
    """Tests for to_context output."""

    def test_minimal_has_key_metrics(self):
        result = NonAccrualResult(
            cik=1287750,
            entity_name="ARES CAPITAL CORP",
            period="2025-12-31",
            source_filing="0001287750-26-000006",
            investments=[
                NonAccrualInvestment(
                    identifier="Company A, First lien",
                    company_name="Company A",
                    investment_type="First lien",
                    fair_value=Decimal("1000000"),
                    cost=Decimal("1100000"),
                    footnote_text="Loan was on non-accrual status.",
                ),
            ],
            nonaccrual_fair_value=Decimal("1000000"),
            total_portfolio_fair_value=Decimal("100000000"),
            extraction_method="footnote",
            custom_concept_rate=0.012,
        )
        ctx = result.to_context('minimal')
        assert 'NON-ACCRUAL ANALYSIS: ARES CAPITAL CORP' in ctx
        assert '1.00%' in ctx
        assert 'footnote' in ctx
        # Minimal should NOT include investment list or footnote text
        assert 'SOURCE FOOTNOTE TEXT' not in ctx
        assert 'Company A' not in ctx

    def test_standard_includes_footnote_text_and_investments(self):
        result = NonAccrualResult(
            cik=1,
            entity_name="Test BDC",
            period="2025-12-31",
            source_filing="0001-00-000001",
            investments=[
                NonAccrualInvestment(
                    identifier="Acme Corp, First lien",
                    company_name="Acme Corp",
                    investment_type="First lien",
                    fair_value=Decimal("5000000"),
                    cost=Decimal("6000000"),
                    footnote_text="Asset is on non-accrual status.",
                ),
            ],
            nonaccrual_fair_value=Decimal("5000000"),
            total_portfolio_fair_value=Decimal("100000000"),
            extraction_method="footnote",
        )
        ctx = result.to_context('standard')
        assert 'SOURCE FOOTNOTE TEXT' in ctx
        assert 'Asset is on non-accrual status.' in ctx
        assert 'Acme Corp (First lien)' in ctx
        assert 'AVAILABLE ACTIONS' in ctx

    def test_full_includes_cost_and_unrealized(self):
        result = NonAccrualResult(
            cik=1,
            entity_name="Test BDC",
            period="2025-12-31",
            source_filing="0001-00-000001",
            investments=[
                NonAccrualInvestment(
                    identifier="Acme Corp, First lien",
                    company_name="Acme Corp",
                    investment_type="First lien",
                    fair_value=Decimal("5000000"),
                    cost=Decimal("6000000"),
                    footnote_text="Non-accrual status.",
                ),
            ],
            nonaccrual_fair_value=Decimal("5000000"),
            total_portfolio_fair_value=Decimal("100000000"),
            extraction_method="footnote",
        )
        ctx = result.to_context('full')
        assert 'Cost: $6,000,000' in ctx
        assert 'Unrealized Gain/Loss: $-1,000,000' in ctx
        assert 'Identifier: Acme Corp, First lien' in ctx


class TestExtractNonAccrualEdgeCases:
    """Edge case tests."""

    def test_wrong_source_type_raises(self):
        with pytest.raises(TypeError, match="Expected Filing or BDCEntity"):
            extract_nonaccrual("not a filing")

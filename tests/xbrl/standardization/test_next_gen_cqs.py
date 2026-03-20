"""Tests for next-generation CQS loop improvements."""
import pytest
from unittest.mock import MagicMock, patch
from edgar.xbrl.standardization.tools.auto_eval import (
    CQSResult, CompanyCQS, MetricGap, derive_gaps_from_cqs,
)
from edgar.xbrl.standardization.tools.auto_eval_loop import ProposalCache


def _make_company_cqs(ticker, failed_metrics, **overrides):
    """Helper to construct CompanyCQS with correct positional fields."""
    defaults = dict(
        ticker=ticker, pass_rate=0.8, mean_variance=5.0,
        coverage_rate=1.0, golden_master_rate=0.5,
        regression_count=0, metrics_total=10, metrics_mapped=10,
        metrics_valid=8, metrics_excluded=0, cqs=0.85,
        ef_pass_rate=0.9, sa_pass_rate=0.8, ef_cqs=0.9, sa_cqs=0.8,
        failed_metrics=failed_metrics,
    )
    defaults.update(overrides)
    return CompanyCQS(**defaults)


def _make_cqs_result(company_scores):
    """Helper to construct CQSResult with correct positional fields."""
    return CQSResult(
        pass_rate=0.8, mean_variance=5.0, coverage_rate=1.0,
        golden_master_rate=0.5, regression_rate=0.0, cqs=0.85,
        companies_evaluated=len(company_scores),
        total_metrics=50, total_mapped=45, total_valid=40,
        total_regressions=0,
        company_scores=company_scores, duration_seconds=10.0,
    )


class TestDeriveGapsFromCQS:
    """Test gap derivation from an existing CQSResult (no orchestrator re-run)."""

    def test_derive_gaps_returns_gaps_for_failing_metrics(self):
        """Gaps should be derived from company_scores without re-running orchestrator."""
        company_scores = {
            "AAPL": _make_company_cqs("AAPL", ["Revenue", "COGS"]),
        }
        cqs = _make_cqs_result(company_scores)

        gaps = derive_gaps_from_cqs(cqs, graveyard_counts={})
        assert len(gaps) == 2
        assert {g.metric for g in gaps} == {"Revenue", "COGS"}
        assert all(g.ticker == "AAPL" for g in gaps)

    def test_derive_gaps_respects_dead_ends(self):
        """Dead-end gaps (graveyard >= 6) should be filtered out."""
        company_scores = {
            "AAPL": _make_company_cqs(
                "AAPL", ["Revenue"],
                metrics_total=5, metrics_mapped=5, metrics_valid=4,
            ),
        }
        cqs = _make_cqs_result(company_scores)

        graveyard_counts = {"AAPL:Revenue": 7}
        gaps = derive_gaps_from_cqs(cqs, graveyard_counts=graveyard_counts)
        assert len(gaps) == 0

    def test_derive_gaps_multiple_companies(self):
        """Gaps from multiple companies should all be included."""
        company_scores = {
            "AAPL": _make_company_cqs("AAPL", ["Revenue"]),
            "JPM": _make_company_cqs("JPM", ["COGS", "SGA"]),
        }
        cqs = _make_cqs_result(company_scores)

        gaps = derive_gaps_from_cqs(cqs, graveyard_counts={})
        assert len(gaps) == 3
        assert {g.ticker for g in gaps} == {"AAPL", "JPM"}

    def test_derive_gaps_empty_when_no_failures(self):
        """No gaps when no metrics have failed."""
        company_scores = {
            "AAPL": _make_company_cqs("AAPL", []),
        }
        cqs = _make_cqs_result(company_scores)
        gaps = derive_gaps_from_cqs(cqs, graveyard_counts={})
        assert len(gaps) == 0


class TestProposalCache:
    """Test in-session proposal dedup cache."""

    def test_cache_blocks_duplicate_proposals(self):
        cache = ProposalCache()
        assert not cache.was_tried("AAPL", "Revenue", "add_concept:RevenueFromContractWithCustomerExcludingAssessedTax")
        cache.record("AAPL", "Revenue", "add_concept:RevenueFromContractWithCustomerExcludingAssessedTax")
        assert cache.was_tried("AAPL", "Revenue", "add_concept:RevenueFromContractWithCustomerExcludingAssessedTax")

    def test_cache_allows_different_proposals_for_same_gap(self):
        cache = ProposalCache()
        cache.record("AAPL", "Revenue", "add_concept:Revenues")
        assert not cache.was_tried("AAPL", "Revenue", "add_concept:SalesRevenueNet")

    def test_cache_allows_same_proposal_for_different_companies(self):
        cache = ProposalCache()
        cache.record("AAPL", "Revenue", "add_concept:Revenues")
        assert not cache.was_tried("MSFT", "Revenue", "add_concept:Revenues")

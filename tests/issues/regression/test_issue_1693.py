"""Regression test for GitHub Issue #1693.

``TTMCalculator._is_additive_concept`` decided from the period type and unit
alone whether a quarter could be derived by subtraction (Q4 = FY - 9M,
Q2 = 6M - Q1). Some monetary duration concepts are defined so that their
quarters do not add up to the year: revenue recognized out of the contract
liability balance at the START of the period (ASC 606-10-50-8(b)), two-class
EPS allocations made per period (ASC 260-10-45-60B), and amounts measured for
another period. A reviewed list of such concepts is now excluded from
derivation.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1693
"""
import json
from datetime import date
from pathlib import Path

import pytest

from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.ttm.calculator import TTMCalculator

pytestmark = pytest.mark.regression

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "snow_facts.json"
CONTRACT_LIABILITY = "ContractWithCustomerLiabilityRevenueRecognized"

# The issue also names NetIncomeLossAvailableToCommonStockholdersBasic. It stays
# derivable: net income less preferred dividends adds up unless participating
# securities share undistributed earnings, and it is the basic EPS numerator whose
# derived Q4 a derived Q4 EPS needs (GH #1692).
ISSUE_CONCEPTS = [
    "us-gaap:UndistributedEarningsLossAllocatedToParticipatingSecuritiesBasic",
    "us-gaap:DistributedEarnings",
    "us-gaap:ContractWithCustomerLiabilityRevenueRecognized",
    "us-gaap:DeferredIncomeRevenueRecognized",
    "us-gaap:BusinessAcquisitionsPurchasePriceAllocationYearOfAcquisitionNetEffectOnIncome",
    "us-gaap:ManagingMemberOrGeneralPartnerSubsequentDistributionAmount",
    "srt:PreviouslyEstimatedDevelopmentCostsIncurred",
]


def _fact(concept, value, start, end, fp, unit="USD"):
    return FinancialFact(concept=concept, taxonomy=concept.split(":")[0], label=concept,
                         value=value, numeric_value=value, unit=unit, period_start=start,
                         period_end=end, period_type="duration", fiscal_year=2025, fiscal_period=fp)


@pytest.mark.parametrize("concept", ISSUE_CONCEPTS)
def test_concepts_whose_quarters_do_not_add_up_are_not_derivable(concept):
    fact = _fact(concept, 1.0, date(2025, 1, 1), date(2025, 12, 31), "FY")
    assert TTMCalculator([])._is_additive_concept(fact) is False


@pytest.mark.parametrize("concept", ["us-gaap:Revenues", "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic"])
def test_ordinary_monetary_flow_is_still_derivable(concept):
    fact = _fact(concept, 1.0, date(2025, 1, 1), date(2025, 12, 31), "FY")
    assert TTMCalculator([])._is_additive_concept(fact) is True


def test_issue_reproduction_derives_no_q4():
    c = "us-gaap:ContractWithCustomerLiabilityRevenueRecognized"
    fy = _fact(c, 100.0, date(2025, 1, 1), date(2025, 12, 31), "FY")
    ytd9 = _fact(c, 90.0, date(2025, 1, 1), date(2025, 9, 30), "Q3")
    # Before the fix: one Q4 of 10.0, derived_q4_fy_minus_ytd9.
    assert TTMCalculator([fy, ytd9])._derive_q4_from_fy([], [ytd9], [fy]) == []


def test_snowflake_contract_liability_revenue_has_no_derived_q4():
    """Snowflake FY2025 (year ended 2025-01-31), revenue recognized that was in
    the deferred revenue balance at the start of each period, read from the
    filings' XBRL:

    10-Q 0001640147-24-000250: three months to 2024-10-31 = 678,500,000;
    nine months to 2024-10-31 = 1,600,000,000.
    10-K 0001640147-25-000052: fiscal year = 1,800,000,000.

    The fiscal year counts only the year's opening balance, so FY - 9M (200M)
    is not a fourth quarter: the three reported quarters alone (673.5M, 642.7M,
    678.5M) already exceed the nine-month figure.
    """
    facts = EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))
    concept_facts = [f for f in facts if f.concept.endswith(CONTRACT_LIABILITY)]

    quarters = {q.period_end: q for q in TTMCalculator(concept_facts).quarterize()}
    assert quarters[date(2024, 10, 31)].numeric_value == 678_500_000
    assert quarters[date(2024, 10, 31)].calculation_context is None   # reported, not derived

    nine_months = [f for f in concept_facts
                   if f.period_start == date(2024, 2, 1) and f.period_end == date(2024, 10, 31)]
    fiscal_year = [f for f in concept_facts
                   if f.period_start == date(2024, 2, 1) and f.period_end == date(2025, 1, 31)]
    assert {f.numeric_value for f in nine_months} == {1_600_000_000}
    assert {f.numeric_value for f in fiscal_year} == {1_800_000_000}

    # Before the fix: a derived Q4 of 200,000,000 ending 2025-01-31.
    assert date(2025, 1, 31) not in quarters
    assert all(q.calculation_context is None for q in quarters.values())

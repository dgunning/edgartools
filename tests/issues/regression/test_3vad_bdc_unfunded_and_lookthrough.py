"""BDC rows summed above the balance sheet for reasons the 6xxb rules missed (edgartools-3vad).

- FSK (+11.5%) was not double counting: its schedule rows are funded positions
  and its 13,008.6M total is net of -1,448.1M of unfunded commitments tagged
  only as totals by investment type.
- OBDC (+6.4%): 742.6M of cost-less company totals the prefix rule could not
  see (a footnote mark "LLC(d)", a shared "(dba PLI)", a footnote breakdown of
  "Windows Entities"), plus a 303.9M srt:RangeAxis maximum read as a holding.
- BCSF (+90%) and NMFC (+25%) list their senior loan programs' portfolios on the
  identifier axis under InvestmentCompanyNonconsolidatedSubsidiaryAxis.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from edgar.bdc.investments import (
    PortfolioInvestment,
    PortfolioInvestments,
    _exclude_restated_rows,
    _unfunded_commitments_fair_value,
)

PERIOD = '2025-12-31'


def holding(identifier, fair_value, cost=None, company=None):
    return PortfolioInvestment(
        identifier=identifier, company_name=company or identifier.split(' | ')[0], investment_type='First lien',
        fair_value=Decimal(fair_value), cost=None if cost is None else Decimal(cost))


def excluded_ids(excluded):
    return sorted(e.investment.identifier for e in excluded)


def _total(value, dims=None, decimals='-5'):
    fact = {'concept': 'us-gaap:InvestmentOwnedAtFairValue', 'period_instant': PERIOD, 'period_type': 'instant',
            'numeric_value': value, 'decimals': decimals, 'unit_ref': 'usd'}
    fact.update(dims or {})
    return fact


def _fact(identifier, concept, value, **dims):
    fact = {'concept': f'us-gaap:{concept}', 'period_instant': PERIOD, 'period_type': 'instant',
            'numeric_value': value, 'unit_ref': 'usd', 'dim_us-gaap_InvestmentIdentifierAxis': identifier}
    fact.update(dims)
    return fact


def _portfolio(facts):
    xbrl = SimpleNamespace(facts=SimpleNamespace(get_facts=lambda: facts), element_catalog={})
    return PortfolioInvestments.from_xbrl(xbrl, include_untyped=True)


TYPE = 'dim_us-gaap_InvestmentTypeAxis'


@pytest.mark.fast
class TestUnfundedNetting:

    FSK_TOTALS = [
        _total(13_008_600_000.0),
        _total(8_861_800_000.0, {TYPE: 'fsk:FundedSeniorSecuredLoansFirstLienMember'}),
        _total(-1_338_400_000.0, {TYPE: 'fsk:UnfundedSeniorSecuredLoansFirstLienMember'}),
        _total(-1_600_000.0, {TYPE: 'fsk:UnfundedDebtCommitmentsMember'}),
        _total(-98_900_000.0, {TYPE: 'fsk:UnfundedAssetBasedFinanceNettingMember'}),
        _total(-9_200_000.0, {TYPE: 'fsk:UnfundedEquityOtherCommitmentsMember'}),
        # Netting nested under another axis is a breakdown, not counted again
        _total(-3_000_000.0, {TYPE: 'obdc:MiscellaneousDebtCommitmentsNettingMember',
                              'dim_us-gaap_InvestmentIssuerAffiliationAxis': 'us-gaap:InvestmentUnaffiliatedIssuerMember'}),
    ]

    def test_fsk_nets_1448_1m_of_unfunded_commitments(self):
        assert _unfunded_commitments_fair_value(self.FSK_TOTALS, PERIOD) == Decimal('-1448100000.0')

    def test_the_gap_is_measured_against_the_gross_total(self):
        """Funded rows of 14,456.7M against 13,008.6M net is +11.1%; gross it is 0."""
        facts = self.FSK_TOTALS + [
            _fact('Alpha LLC | First lien', 'InvestmentOwnedAtFairValue', 14_456_700_000.0),
            _fact('Alpha LLC | First lien', 'InvestmentOwnedAtCost', 14_400_000_000.0),
        ]
        portfolio = _portfolio(facts)

        assert portfolio.reported_total_fair_value == Decimal('13008600000.0')
        assert portfolio.unfunded_commitments_fair_value == Decimal('-1448100000.0')
        assert portfolio.reconciliation_gap == pytest.approx(0.0, abs=1e-9)

    def test_netting_the_rows_already_carry_is_not_added_back(self):
        """OBDC itemizes its unfunded commitments as negative rows."""
        facts = [
            _total(100_000_000.0),
            _total(-3_400_000.0, {TYPE: 'obdc:PortfolioCommitmentsMember'}),
            _fact('Beta LLC | First lien', 'InvestmentOwnedAtFairValue', 103_400_000.0),
            _fact('Beta LLC | First lien', 'InvestmentOwnedAtCost', 103_000_000.0),
            _fact('Beta LLC | First lien delayed draw', 'InvestmentOwnedAtFairValue', -3_400_000.0),
        ]
        assert _portfolio(facts).reconciliation_gap == pytest.approx(0.0, abs=1e-9)

    def test_no_netting_tagged_is_none(self):
        assert _unfunded_commitments_fair_value([_total(1.0)], PERIOD) is None


@pytest.mark.fast
class TestNonHoldingAxes:

    def test_a_joint_ventures_holdings_and_a_range_are_not_rows(self):
        facts = [
            _total(50_000_000.0),
            _fact('Own Holding LLC | First lien', 'InvestmentOwnedAtFairValue', 50_000_000.0),
            _fact('Own Holding LLC | First lien', 'InvestmentOwnedAtCost', 49_000_000.0),
            _fact('JV Borrower Inc | First lien', 'InvestmentOwnedAtFairValue', 20_000_000.0,
                  **{'dim_us-gaap_InvestmentCompanyNonconsolidatedSubsidiaryAxis': 'bcsf:BainCapitalSeniorLoanProgramLlcMember'}),
            _fact('CLO Borrower Inc | Term loan', 'InvestmentOwnedAtFairValue', 5_000_000.0,
                  **{'dim_dei_LegalEntityAxis': 'sar:SaratogaInvestmentCorpCLO20131LtdMember'}),
            _fact('Blue Owl Cross-Strategy Opportunities LLC (BOCSO)', 'InvestmentOwnedAtFairValue', 303_900_000.0,
                  **{'dim_srt_RangeAxis': 'srt:MaximumMember'}),
        ]
        portfolio = _portfolio(facts)
        assert [inv.identifier for inv in portfolio] == ['Own Holding LLC | First lien']
        assert portfolio.reconciliation_gap == 0.0


@pytest.mark.fast
class TestCostlessTotals:
    """OBDC 0001655888-26-000010 rows, in millions as filed."""

    def test_a_footnote_mark_does_not_hide_a_company_total(self):
        rows = [
            holding('AAM Series 2.1 Aviation Feeder, LLC(d)', 143_200_000),
            holding('AAM Series 2.1 Aviation Feeder, LLC | Specialty finance debt investment', 88_800_000, cost=88_619_000),
            holding('AAM Series 2.1 Aviation Feeder, LLC | Specialty finance equity investment', 54_400_000, cost=35_325_000),
        ]
        kept, excluded = _exclude_restated_rows(rows)
        assert excluded_ids(excluded) == ['AAM Series 2.1 Aviation Feeder, LLC(d)']

    def test_a_shared_dba_ties_a_total_to_its_companies(self):
        rows = [
            holding('New PLI Holdings, LLC (dba PLI)', 202_300_000),
            holding('New PLI Holdings, LLC (dba PLI) | Class A Common Units', 87_400_000, cost=48_007_000),
            holding('Swipe Acquisition Corporation (dba PLI) | First lien senior secured loan', 72_500_000, cost=72_000_000),
            holding('Swipe Acquisition Corporation (dba PLI) | First lien senior secured loan 2', 42_400_000, cost=42_000_000),
            holding('Sentinel Buyer Corp. (dba SimpliSafe) | First lien senior secured loan', 39_900_000, cost=39_000_000),
        ]
        kept, excluded = _exclude_restated_rows(rows)
        assert excluded_ids(excluded) == ['New PLI Holdings, LLC (dba PLI)']

    def test_a_footnote_breakdown_of_one_holding_is_excluded(self):
        """Footnote (32): "Windows Entities" is Midwest $24.1M, Greater Toronto $10.0M, ..."""
        parts = [('Midwest Custom Windows, LLC', 24_100_000), ('Greater Toronto Custom Windows, Corp.', 10_000_000),
                 ('Garden State Custom Windows, LLC', 33_400_000), ('Long Island Custom Windows, LLC', 28_900_000),
                 ('Jemico, LLC', 23_200_000), ('Atlanta Custom Windows, LLC', 11_500_000),
                 ('Fairchester Custom Windows', 7_600_000)]
        rows = ([holding('Windows Entities | LLC Units | Non-Affiliated', 138_637_000, cost=120_000_000)]
                + [holding(name, value) for name, value in parts])
        kept, excluded = _exclude_restated_rows(rows)
        assert [inv.identifier for inv in kept] == ['Windows Entities | LLC Units | Non-Affiliated']
        assert len(excluded) == 7

    def test_unrelated_company_rows_do_not_match_by_coincidence(self):
        """GBDC: three cost-less company rows sum to a fourth row's value, but each
        company has its own tranches, so they are not a footnote breakdown."""
        rows = [
            holding('G & H Wire Company, Inc', 6_070_000),
            holding('G & H Wire Company, Inc., One stop 1', 2_847_000, cost=2_847_000, company='G & H Wire Company, Inc'),
            holding('IMPLUS Footcare, LLC', 23_769_000),
            holding('IMPLUS Footcare, LLC, One stop 1', 7_708_000, cost=7_738_000, company='IMPLUS Footcare, LLC'),
            holding('Reaction Biology Corporation', 7_259_000),
            holding('Reaction Biology Corporation, One stop 1', 2_777_000, cost=2_923_000, company='Reaction Biology Corporation'),
            holding('Unrelated Holdings | First lien', 37_098_000, cost=37_000_000),
        ]
        kept, excluded = _exclude_restated_rows(rows)
        assert excluded == []


@pytest.mark.network
@pytest.mark.parametrize("accession, reported, max_gap", [
    ("0001628280-26-011734", Decimal("13008600000.0"), 0.005),   # FSK, was +11.47%
    ("0001655888-26-000010", Decimal("16470893000.0"), 0.001),   # OBDC, was +6.35%
    ("0001193125-26-077703", None, 0.001),                       # BCSF, was +90.5%
])
def test_latest_10ks_reconcile_to_the_balance_sheet(accession, reported, max_gap):
    from edgar import find
    portfolio = PortfolioInvestments.from_xbrl(find(accession).xbrl(), include_untyped=True)
    if reported is not None:
        assert portfolio.reported_total_fair_value == reported
    assert abs(portfolio.reconciliation_gap) < max_gap


@pytest.mark.network
def test_fsk_unfunded_commitments_ground_truth():
    from edgar import find
    portfolio = PortfolioInvestments.from_xbrl(find("0001628280-26-011734").xbrl(), include_untyped=True)
    assert portfolio.unfunded_commitments_fair_value == Decimal("-1448100000.0")

"""Regression: non-accruals are read from schedules not tagged on InvestmentIdentifierAxis.

Bead: edgartools-jv32z

``extract_nonaccrual`` only followed footnote links to facts on
``InvestmentIdentifierAxis`` and summed its total from that axis too. Schedules
tagged the older way name a holding by several axes instead, so their
recognized non-accrual footnotes resolved nothing and the result was
``extraction_method='none'`` with no rate.

TriplePoint Venture Growth FY2024 (0001580345-25-000005) names a loan by
industry, instrument, loan and ``tpvg:PortfolioCompaniesAxis``, and links its
non-accrual footnote to company and industry subtotals as well as the loans.
Its footnote states the answer: "Non-accrual investments as of December 31,
2024 had a total cost and fair value of $38.1 million and $20.6 million".

Oxford Square Capital FY2024 (0001213900-25-020801) names a holding by
``RelatedPartyTransactionsByRelatedPartyAxis`` and has no undimensioned
total; its balance sheet splits investments into non-affiliated (256,238,759)
and affiliated (4,614,100). Its footnote: "The aggregate fair value of these
investments was approximately $5.1 million."
"""
from decimal import Decimal

import pytest

from edgar.bdc.nonaccrual import _affiliation_split_total, _drop_subtotals, _portfolio_total_fair_value

FV = 'us-gaap:InvestmentOwnedAtFairValue'
AFFILIATION = 'dim_us-gaap_InvestmentIssuerAffiliationAxis'


def _fact(value, **dims):
    return {'concept': FV, 'period_instant': '2024-12-31', 'numeric_value': value, 'decimals': '0', **dims}


def test_a_flagged_roll_up_of_other_flagged_facts_is_dropped():
    industry = {'dim_us-gaap_EquitySecuritiesByIndustryAxis': 'x:ConsumerMember'}
    company = {**industry, 'dim_x_PortfolioCompaniesAxis': 'x:NakdMember'}
    loan_1 = _fact(5294000.0, **company, **{'dim_us-gaap_InvestmentTypeAxis': 'x:Loan1Member'})
    loan_2 = _fact(3176000.0, **company, **{'dim_us-gaap_InvestmentTypeAxis': 'x:Loan2Member'})
    flagged = [(_fact(8470000.0, **company), 'fn'), (loan_1, 'fn'), (_fact(8470000.0, **industry), 'fn'),
               (loan_2, 'fn')]
    assert [fact['numeric_value'] for fact, _ in _drop_subtotals(flagged)] == [5294000.0, 3176000.0]


def test_balance_sheet_affiliation_lines_add_up_to_the_total():
    facts = [
        _fact(256238759.0, **{AFFILIATION: 'oxsq:NonControlAndNonAffiliateInvestmentsIssuerMember'}),
        _fact(4614100.0, **{AFFILIATION: 'us-gaap:InvestmentAffiliatedIssuerMember'}),
    ]
    assert _portfolio_total_fair_value(facts, '2024-12-31') == (Decimal('260852859.0'), 'balance_sheet')


def test_affiliation_parent_is_not_added_to_its_children():
    facts = [
        _fact(100.0, **{AFFILIATION: 'us-gaap:InvestmentUnaffiliatedIssuerMember'}),
        _fact(30.0, **{AFFILIATION: 'us-gaap:InvestmentAffiliatedIssuerMember'}),
        _fact(10.0, **{AFFILIATION: 'us-gaap:InvestmentAffiliatedIssuerControlledMember'}),
        _fact(20.0, **{AFFILIATION: 'us-gaap:InvestmentAffiliatedIssuerNoncontrolledMember'}),
    ]
    assert _affiliation_split_total(facts, '2024-12-31') == Decimal('130.0')


def test_one_affiliation_line_is_not_taken_for_the_total():
    facts = [_fact(4614100.0, **{AFFILIATION: 'us-gaap:InvestmentAffiliatedIssuerMember'})]
    assert _affiliation_split_total(facts, '2024-12-31') is None


@pytest.mark.network
@pytest.mark.vcr
def test_triplepoint_fy2024_non_accruals_match_its_footnote():
    """Ground truth: TriplePoint Venture Growth 10-K for 2024-12-31, accession 0001580345-25-000005."""
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    result = extract_nonaccrual(find('0001580345-25-000005'))
    assert result.extraction_method == 'footnote'
    assert result.num_nonaccrual == 8
    assert result.nonaccrual_fair_value == Decimal('20586000')
    assert sum(inv.cost for inv in result.investments) == Decimal('38095000')
    assert result.total_portfolio_fair_value == Decimal('676249000')
    assert sorted({inv.company_name for inv in result.investments}) == [
        'Mind Candy Limited', 'Nakdcom One World AB', 'Project 1920, Inc.', 'Synapse Financial Technologies, Inc.',
    ]


@pytest.mark.network
@pytest.mark.vcr
def test_oxford_square_fy2024_non_accruals_match_its_footnote():
    """Ground truth: Oxford Square Capital 10-K for 2024-12-31, accession 0001213900-25-020801."""
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    result = extract_nonaccrual(find('0001213900-25-020801'))
    assert result.extraction_method == 'footnote'
    assert result.nonaccrual_fair_value == Decimal('5101312')
    assert result.total_portfolio_fair_value == Decimal('260852859')
    assert result.total_source == 'balance_sheet'
    assert ('UniTek Global Services, Inc.', 'Series B Super Senior Preferred Stock', Decimal('4614100')) in {
        (inv.company_name, inv.investment_type, inv.fair_value) for inv in result.investments}

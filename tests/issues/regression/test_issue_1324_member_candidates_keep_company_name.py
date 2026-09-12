"""Regression test for issue #1324.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1324

`PortfolioInvestments.from_xbrl()` cut the first word off a borrower's name
when that word was the terse label of a standard-taxonomy member. On BXSL's
FY2025 10-K (0001736035-26-000004) and Q2 2026 10-Q (0001736035-26-000016)
the four `High Street Buyer, Inc. N | Non-Affiliated Issuer` positions came
back as `company_name='Street Buyer, Inc. N'` with `industry='High'` and
`industry_source='identifier'`, on every one of 674 and 703 positions the
only rows that differed from `parse_investment_identifier()` on the same
identifier and candidates.

The `High` was BXSL's own terse label on `srt:MaximumMember`, the way it heads
its interest-rate range table (CGBD labels the same members `High` and `Low`
too; ARCC, HTGC, TRIN and TSLX keep `Maximum` and `Minimum`, which would cut a
borrower opening with either word just the same). `_get_investment_member_candidates`
admitted every `*Member` element in the catalog from every taxonomy and every
label role, and `_industry_before_company` trusts a one-word span that is in
the candidate set, so the 5.58.0 industry fill read `High` as a schedule
grouping and sliced it off the name. The members of `srt:RangeAxis` bound a
range, never a company or an industry, and are no longer candidates; every
other member still is, so the filer's own groupings still bound its names
(the Truck-Lite control below is the case upstream's own test pins).

Offline: the catalog is stubbed the way tests/bdc/test_bdc_industry.py stubs
it, with the two label roles copied from BXSL's filing.
"""

from decimal import Decimal
from types import SimpleNamespace

from edgar.bdc.investments import PortfolioInvestments, _get_investment_member_candidates

LABEL = 'http://www.xbrl.org/2003/role/label'
TERSE = 'http://www.xbrl.org/2003/role/terseLabel'

HIGH_STREET = 'High Street Buyer, Inc. 2 | Non-Affiliated Issuer'
HIGH_STREET_FAIR_VALUE = Decimal('77686000')            # the 10-K's row, in dollars
TRUCK_LITE = 'Debt Investments Automotive Truck-Lite Co., LLC Investment First-lien loan'
TRUCK_LITE_TERM_LOAN = 42_713_000

# srt:MaximumMember and srt:MinimumMember exactly as BXSL's element catalog carries them.
SRT_MAXIMUM = SimpleNamespace(labels={LABEL: 'Maximum [Member]', TERSE: 'High'})
SRT_MINIMUM = SimpleNamespace(labels={LABEL: 'Minimum [Member]', TERSE: 'Low'})


def _fact(identifier, value, **extra):
    fact = {
        'concept': 'us-gaap:InvestmentOwnedAtFairValue', 'period_type': 'instant',
        'period_instant': '2025-12-31', 'numeric_value': float(value), 'value': value,
        'unit_ref': 'usd', 'dim_us-gaap_InvestmentIdentifierAxis': identifier,
    }
    fact.update(extra)
    return fact


def _xbrl(facts, catalog):
    return SimpleNamespace(facts=SimpleNamespace(get_facts=lambda: facts), element_catalog=catalog)


def test_a_standard_taxonomy_terse_label_does_not_open_an_industry():
    facts = [_fact(HIGH_STREET, HIGH_STREET_FAIR_VALUE)]
    catalog = {'srt_MaximumMember': SRT_MAXIMUM, 'srt_MinimumMember': SRT_MINIMUM}

    investments = PortfolioInvestments.from_xbrl(_xbrl(facts, catalog))

    inv = investments[0]
    assert (inv.identifier, inv.company_name, inv.industry, inv.industry_source) == (
        HIGH_STREET, 'High Street Buyer, Inc. 2', None, None)
    assert inv.fair_value == HIGH_STREET_FAIR_VALUE


def test_the_name_is_the_same_with_and_without_the_standard_members():
    facts = [_fact(HIGH_STREET, HIGH_STREET_FAIR_VALUE)]
    with_members = PortfolioInvestments.from_xbrl(_xbrl(facts, {'srt_MaximumMember': SRT_MAXIMUM}))[0]
    without = PortfolioInvestments.from_xbrl(_xbrl(facts, {}))[0]
    assert (with_members.company_name, with_members.industry) == (without.company_name, without.industry)
    assert without.company_name == 'High Street Buyer, Inc. 2'


def test_range_bound_members_are_not_candidates_and_every_other_member_still_is():
    catalog = {
        'srt_MaximumMember': SRT_MAXIMUM,
        'srt:MinimumMember': SRT_MINIMUM,
        'srt_WeightedAverageMember': SimpleNamespace(labels={LABEL: 'Weighted Average [Member]'}),
        'us-gaap_InvestmentsMember': SimpleNamespace(labels={LABEL: 'Investments [Member]', TERSE: 'Total'}),
        'bxsl_SoftwareMember': SimpleNamespace(labels={LABEL: 'Software [Member]'}),
        'bxsl:HealthCareProvidersAndServicesMember': SimpleNamespace(
            labels={LABEL: 'Health Care Providers and Services [Member]'}),
    }
    candidates = _get_investment_member_candidates(SimpleNamespace(element_catalog=catalog))
    assert sorted(candidates) == ['health care provider and service', 'investment', 'software', 'total']


def test_the_filers_own_grouping_still_bounds_the_company_name():
    # The control from tests/bdc/test_bdc_industry.py: a grouping written into
    # the identifier is still recognised and stripped when the filer's own
    # rows name it, standard members or not.
    facts = [
        _fact(TRUCK_LITE, TRUCK_LITE_TERM_LOAN),
        _fact('Debt Investments Automotive', TRUCK_LITE_TERM_LOAN),     # the grouping subtotal
    ]
    catalog = {'srt_MaximumMember': SRT_MAXIMUM, 'srt_MinimumMember': SRT_MINIMUM}

    investments = PortfolioInvestments.from_xbrl(_xbrl(facts, catalog))

    truck = next(inv for inv in investments if inv.identifier == TRUCK_LITE)
    assert (truck.industry, truck.industry_source, truck.company_name) == (
        'Automotive', 'identifier', 'Truck-Lite Co., LLC')
    assert truck.fair_value == TRUCK_LITE_TERM_LOAN

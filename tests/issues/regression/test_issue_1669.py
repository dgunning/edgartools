"""Regression test for issue #1669.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1669

Ares Capital's FY2025 10-K (accession 0001287750-26-000006) has no industry
axis or enumeration on its schedule of investments, so every industry comes
from the identifier text. Five rows came back with something that is not an
industry, with ``industry_source='identifier'``:

* ``LiveBarn Inc., Middle preferred shares`` -> ``Middle`` (a tranche name)
* ``Talon Buyer Inc. and Talon Holdings SCSP, ...`` -> ``SCSP`` (a Luxembourg
  legal form, read past the ``Inc.`` inside the company name)
* ``Nordic Ferry Infrastructure AS, Senior subordinated loan`` -> the company
  itself, because ARCC's taxonomy has a member with that name and member
  labels are industry candidates.

Over the latest 10-Ks of 39 BDCs the fix changes 7 of 17,061 rows, all of
them non-industries (the five above and OBDC's ``Patriot Holdings SCSp``),
and no real industry is lost. Holdings and amounts are untouched.
"""

import pytest

from edgar.bdc.investments import identifier_industry, parse_investment_identifier

LIVEBARN = 'LiveBarn Inc., Middle preferred shares'
TALON = 'Talon Buyer Inc. and Talon Holdings SCSP, First lien senior secured loan'
NORDIC = 'Nordic Ferry Infrastructure AS, Senior subordinated loan'
PATRIOT = 'Patriot Holdings SCSp (dba Corza Health, Inc.) | Class A Units | Non-Affiliated'


def test_a_tranche_word_is_not_an_industry():
    assert identifier_industry(LIVEBARN, company_name='LiveBarn Inc.') is None


@pytest.mark.parametrize('identifier', [TALON, PATRIOT])
def test_a_partnership_legal_form_is_not_an_industry(identifier):
    assert identifier_industry(identifier) is None
    assert identifier_industry(identifier, company_name='Talon Buyer Inc. and Talon Holdings SCSP') is None


def test_a_member_that_is_the_company_is_not_its_industry():
    # ARCC's element catalog carries a member labelled with the issuer's name.
    candidates = ('Nordic Ferry Infrastructure AS',)
    assert identifier_industry(NORDIC, company_name='Nordic Ferry Infrastructure AS', candidates=candidates) is None
    parsed = parse_investment_identifier(f'us-gaap:InvestmentIdentifierAxis: {NORDIC}', candidates)
    assert parsed.company_name == 'Nordic Ferry Infrastructure AS'
    assert parsed.industry is None


def test_real_industries_are_still_read():
    # Saratoga 10-K 0001213900-26-052176: the industry sits between company and instrument.
    saratoga = ('Non-control/Non-affiliate investments - 256.5% - BQE Software, Inc. - '
                'Architecture & Engineering Software - First Lien Term Loan (3M USD TERM SOFR+5.50%), '
                '9.67% Cash, 4/13/2028 - One')
    assert identifier_industry(saratoga) == 'Architecture & Engineering Software'
    # A filer's own grouping in front of the company still counts when it is not the company.
    truck_lite = 'Debt Investments Automotive Truck-Lite Co., LLC Investment First-lien loan'
    assert identifier_industry(truck_lite, company_name='Truck-Lite Co., LLC',
                               candidates=('Automotive',)) == 'Automotive'


@pytest.mark.network
def test_arcc_fy2025_has_no_false_identifier_industries():
    from edgar import find
    from edgar.bdc.investments import PortfolioInvestments

    investments = PortfolioInvestments.from_xbrl(find('0001287750-26-000006').xbrl())
    assert len(investments) == 1417
    assert [r.industry for r in investments if r.industry_source == 'identifier'] == []
    livebarn = [r for r in investments if r.identifier == LIVEBARN]
    assert len(livebarn) == 1
    assert livebarn[0].fair_value == 25_900_000
    assert livebarn[0].industry is None and livebarn[0].sector is None

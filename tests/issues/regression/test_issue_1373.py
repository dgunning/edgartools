"""Regression test: a company the filer tags as a member is stripped as a prefix.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1373

Some identifiers lead with the company: "<Company> | <Industry> | <Instrument>".
When the filer also tags that company as a member, its label is one of the
member candidates, and `_match_company_candidate`'s prefix loop stripped it as
a grouping, then the industry, and returned what was left before the
instrument cut: "First Lien", "Ordinary Shares", "9.1%". The same call with no
candidates named the company. `PortfolioInvestments.from_xbrl` passes the
filing's candidates, so `company_name` carried the instrument: before the fix,
wrong on 187 of PSEC's 300 positions (10-K 0001287032-26-000269), 155 of
CSWC's 579 (10-Q 0000017313-26-000095) and 113 of TPVG's 310 (10-Q
0001580345-26-000025).

A candidate that fills the whole first pipe segment is now the company. SLRC
also tags its headings ("Senior Secured Loans"), so a segment that holds an
instrument or a portfolio category is still stripped as a prefix; those
heading-led identifiers are GH #1372's.

Every identifier below is verbatim from those filings; the candidate is the
company's own label, as each filer tags it. Offline.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from edgar.bdc.investments import PortfolioInvestments, _normalize_member_text, parse_investment_identifier

FIRST_TOWER = 'First Tower Finance Company LLC | Consumer Finance | First Lien Term Loan to First Tower, LLC'


@pytest.mark.parametrize(
    ('identifier', 'company_name', 'wrong_before'),
    [
        (FIRST_TOWER, 'First Tower Finance Company LLC', 'First Lien'),          # PSEC
        ('CLUTCH, INC. | First Lien - Term Loan B', 'CLUTCH, INC.', 'First Lien'),  # TPVG
        ('Revolut Ltd | Ordinary Shares | Equity Investments', 'Revolut Ltd', 'Ordinary Shares'),  # TPVG
        ('Jocassee Partners LLC | 9.1% Member Interest', 'Jocassee Partners LLC', '9.1%'),  # CSWC
    ],
)
def test_the_tagged_company_is_not_stripped_as_a_prefix(identifier, company_name, wrong_before):
    candidates = (_normalize_member_text(company_name),)

    parsed = parse_investment_identifier(identifier, member_candidates=candidates)

    assert parsed.company_name == company_name != wrong_before
    assert parse_investment_identifier(identifier).company_name == company_name


def _member(label):
    return SimpleNamespace(labels={'http://www.xbrl.org/2003/role/label': f'{label} [Member]'})


def test_from_xbrl_names_the_company_when_the_filer_tags_it():
    fact = {
        'concept': 'us-gaap:InvestmentOwnedAtFairValue', 'value': Decimal('466000000'),
        'numeric_value': 466000000.0, 'period_instant': '2026-06-30',
        'period_type': 'instant', 'unit_ref': 'usd',
        'dim_us-gaap_InvestmentIdentifierAxis': FIRST_TOWER,
    }
    # PSEC's element catalog tags the company and the industry as members.
    catalog = {
        'psec_FirstTowerFinanceCompanyLLCMember': _member('First Tower Finance Company LLC'),
        'psec_ConsumerFinanceMember': _member('Consumer Finance'),
    }
    xbrl = SimpleNamespace(facts=SimpleNamespace(get_facts=lambda: [fact]), element_catalog=catalog)

    held = PortfolioInvestments.from_xbrl(xbrl)

    assert [position.company_name for position in held] == ['First Tower Finance Company LLC']

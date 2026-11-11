"""Regression: a footnote linked to a holding's rate, spread or principal flags that holding.

Bead: edgartools-jv8b8

Only linked ``InvestmentOwnedAtFairValue`` facts counted. New Mountain Finance
attaches "Investment is on non-accrual status" to a position's PIK rate and
spread, SuRo to its principal, so the footnote was recognized but resolved no
holdings and the filing read ``'none'``. A linked fact of any concept now
stands for its holding's fair value at the same instant.

Across the latest 10-K or 10-Q of 179 active BDCs: 2 filings move from
``'none'`` to a footnote read (New Mountain Finance, New Mountain Guardian IV)
and 5 already-read filings gain a row they flag only on another cell (Biolam
at Barings Capital Investment, B+T at Gladstone Investment, AppLogic at
Monroe, Sentrics at Remora, Unifrax at Sixth Street Lending Partners), each
checked against the footnote's text. Duration facts do not resolve: Logan
Ridge flags its Q1 2025 industry name for a loan its schedule does not mark,
and its stated 2.2% would have read 4.5%.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from edgar.bdc.nonaccrual import _extract_nonaccrual_from_xbrl

DIM = 'dim_us-gaap_InvestmentIdentifierAxis'
P = '2026-09-30'


def _fact(fact_id, concept, value, member=None, instant=P, **extra):
    fact = {'fact_id': fact_id, 'concept': concept, 'numeric_value': value, 'period_instant': instant, **extra}
    if member:
        fact[DIM] = member
    return fact


def _xbrl(footnote_text, linked_ids):
    footnote = SimpleNamespace(text=footnote_text, lang='en-US', related_fact_ids=linked_ids)
    return SimpleNamespace(footnotes={'fn1': footnote}, element_catalog={})


FACTS = [
    _fact('fv-a', 'us-gaap:InvestmentOwnedAtFairValue', 16_000_000.0, 'Acme Corp, First lien'),
    _fact('pik-a', 'us-gaap:InvestmentInterestRatePaidInKind', 0.0675, 'Acme Corp, First lien'),
    _fact('fv-b', 'us-gaap:InvestmentOwnedAtFairValue', 50_000_000.0, 'Beta Inc, First lien'),
    _fact('name-b', 'xx:IndustryName', None, 'Beta Inc, First lien', instant=None,
          period_start='2026-07-01', period_end=P),
    _fact('total', 'us-gaap:InvestmentOwnedAtFairValue', 1_000_000_000.0),
    _fact('rate-total', 'us-gaap:InvestmentInterestRate', 0.09),
]


def test_a_flag_on_the_pik_rate_reads_the_holdings_fair_value():
    result = _extract_nonaccrual_from_xbrl(_xbrl('Investment is on non-accrual status.', ['pik-a']),
                                           period=P, all_facts=FACTS)
    assert result.extraction_method == 'footnote'
    assert [inv.fair_value for inv in result.investments] == [Decimal('16000000.0')]


def test_a_flag_on_a_duration_fact_or_an_undimensioned_total_resolves_nothing():
    result = _extract_nonaccrual_from_xbrl(_xbrl('Investment is on non-accrual status.', ['name-b', 'rate-total']),
                                           period=P, all_facts=FACTS)
    assert result.investments == []
    assert result.extraction_method == 'none'


@pytest.mark.network
@pytest.mark.vcr
def test_new_mountain_guardian_iv_reads_a_flag_on_the_pik_rate():
    """New Mountain Guardian IV BDC 10-Q for 2026-09-30 (0001925531-26-000020).

    The printed schedule lists LogRhythm, Inc.'s First Lien at cost $4,180K and
    fair value $3,454K; "Investment is on non-accrual status as of September
    30, 2026" is linked to its PIK rate, never its fair value.

    New Mountain Finance's 10-Q for the same date (0001496099-26-000034) reads
    9 rows the same way, American Achievement's first lien at $16,000K; its
    cassette would pass GitHub's 100 MB file limit.
    """
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    result = extract_nonaccrual(find('0001925531-26-000020'))
    assert result.extraction_method == 'footnote'
    logrhythm = [inv for inv in result.investments if inv.company_name == 'LogRhythm, Inc.']
    assert len(logrhythm) == 1
    assert logrhythm[0].fair_value == Decimal('3454000')
    assert logrhythm[0].cost == Decimal('4180000')
    assert result.num_nonaccrual == 2

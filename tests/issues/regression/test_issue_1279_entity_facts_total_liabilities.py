"""EntityFacts.get_total_liabilities() returned total assets for any company
that files no standalone us-gaap:Liabilities line.

GH #1279 fixed this on the XBRL path, ``Financials.get_total_liabilities()``.
On the company-facts path, ``Company(...).get_facts().get_total_liabilities()``
kept ``LiabilitiesAndStockholdersEquity`` as its last concept variant. That
concept is the right-hand total of the balance sheet, so it always equals total
assets. For a filer with no ``Liabilities`` fact it was the only candidate, and
the getter returned it.

NIKE's FY2026 10-K (0000320187-26-000088) reports no ``Liabilities`` total.
``get_total_liabilities()`` returned $38,410,000,000, its total assets, against
$23,545,000,000 of actual liabilities (assets less $14,865,000,000 of
shareholders' equity; NIKE has no noncontrolling or temporary equity). Measured
on 2026-09-27 across 51 large US filers, 16 of them returned exactly their total
assets: AMZN, WMT, KO, ORCL, T, DIS, MCD, VZ, INTC, LLY, MRK, ABT, UPS, FDX,
TGT and NKE. ``edgar_compare``'s "liabilities" metric reads this getter.

Now the getter returns None when there is no standalone total, which is what
``Financials.get_total_liabilities()`` and ``get_concept('total_liabilities')``
already return for the same companies.

Ground truth, from each company's own 10-K:
  NKE  FY2026 (2026-05-31)  Assets 38,410,000,000   Liabilities not reported
  AAPL FY2025 (2025-09-27)  Assets 359,241,000,000  Liabilities 285,508,000,000

GitHub Issue: https://github.com/dgunning/edgartools/issues/1279
"""

from datetime import date

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact

LABELS = {
    "Assets": "Assets",
    "Liabilities": "Liabilities",
    "LiabilitiesAndStockholdersEquity": "Liabilities and Equity",
    "StockholdersEquity": "Stockholders' Equity Attributable to Parent",
}


def _balance(concept, value, period_end, *, accession, filing_date, fiscal_year):
    return FinancialFact(
        concept=f"us-gaap:{concept}",
        taxonomy="us-gaap",
        label=LABELS[concept],
        value=value,
        numeric_value=float(value),
        unit="USD",
        period_end=period_end,
        period_type="instant",
        fiscal_year=fiscal_year,
        fiscal_period="FY",
        filing_date=filing_date,
        form_type="10-K",
        accession=accession,
    )


def _nike_fy2026():
    """NIKE, FY2026 10-K: no us-gaap:Liabilities fact, as filed."""
    filed = dict(accession="0000320187-26-000088", filing_date=date(2026, 7, 15), fiscal_year=2026)
    facts = []
    for period_end, assets, equity in [
        (date(2026, 5, 31), 38_410_000_000, 14_865_000_000),
        (date(2025, 5, 31), 36_579_000_000, 13_213_000_000),
    ]:
        facts += [
            _balance("Assets", assets, period_end, **filed),
            _balance("LiabilitiesAndStockholdersEquity", assets, period_end, **filed),
            _balance("StockholdersEquity", equity, period_end, **filed),
        ]
    return EntityFacts(cik=320187, name="NIKE, Inc.", facts=facts)


def _apple_fy2025():
    """Apple, FY2025 10-K: files both the standalone total and the combined one."""
    filed = dict(accession="0000320193-25-000079", filing_date=date(2025, 10, 31), fiscal_year=2025)
    facts = []
    for period_end, assets, liabilities in [
        (date(2025, 9, 27), 359_241_000_000, 285_508_000_000),
        (date(2024, 9, 28), 364_980_000_000, 308_030_000_000),
    ]:
        facts += [
            _balance("Assets", assets, period_end, **filed),
            _balance("LiabilitiesAndStockholdersEquity", assets, period_end, **filed),
            _balance("Liabilities", liabilities, period_end, **filed),
        ]
    return EntityFacts(cik=320193, name="Apple Inc.", facts=facts)


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"annual": False},
        {"period": "2026-FY"},
    ],
    ids=["annual", "most-recent", "explicit-period"],
)
def test_liabilities_and_equity_is_not_returned_as_liabilities(kwargs):
    facts = _nike_fy2026()

    assert facts.get_total_assets(**kwargs) == 38_410_000_000
    # Was 38,410,000,000: the combined total, equal to total assets.
    assert facts.get_total_liabilities(**kwargs) is None


def test_matches_get_concept_on_the_same_object():
    """Both getters answer "total liabilities" and must not disagree."""
    facts = _nike_fy2026()

    assert facts.get_concept("total_liabilities") is None
    assert facts.get_total_liabilities() is None


def test_a_standalone_liabilities_total_is_still_returned():
    """Control: a filer that reports the total keeps getting it."""
    facts = _apple_fy2025()

    assert facts.get_total_liabilities() == 285_508_000_000
    assert facts.get_total_liabilities(period="2025-FY") == 285_508_000_000

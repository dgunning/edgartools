"""Regression: ``get_stockholders_equity()`` returned the liabilities-and-equity total, or None.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1659

The getter matched balance-sheet labels only. r'Total.*Stockholders.*Equity'
matches "Total liabilities and stockholders' equity (deficit)", so American
Airlines' FY2025 10-K returned 61,774,000,000 (its total assets) for a
stockholders' deficit of -3,727,000,000. NovaGold labels its
us-gaap:StockholdersEquity row "Equity, Attributable to Parent", which no
pattern matched, so it got None.

The getter now looks up the concept first, as ``get_total_liabilities()`` does
(GH #1279): the parent-attributable total, then the total including
noncontrolling interest when that is the only one filed (#1442). The label
fallback rejects any caption that also names liabilities.
"""
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from edgar.financials import Financials
from edgar.xbrl import XBRL


def _stub(rows):
    """A Financials whose balance sheet is ``rows`` of (concept, label, value)."""
    df = pd.DataFrame(
        [{'concept': c, 'label': lbl, 'abstract': False, '2025-12-31': v} for c, lbl, v in rows])
    financials = Financials(object())
    financials._render_statement_frame = lambda statement_type: (None, df.copy())
    return financials


COMBINED = ('us-gaap_LiabilitiesAndStockholdersEquity',
            "Total liabilities and stockholders' equity (deficit)", 61774000000)


@pytest.mark.fast
def test_equity_is_the_concept_not_the_combined_total():
    financials = _stub([COMBINED, ('us-gaap_StockholdersEquity', "Total stockholders' deficit", -3727000000)])
    assert financials.get_stockholders_equity() == -3727000000


@pytest.mark.fast
def test_parent_equity_wins_and_nci_inclusive_is_the_fallback():
    both = _stub([
        ('us-gaap_StockholdersEquity', 'Equity, Attributable to Parent', 387255000),
        ('us-gaap_StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest', 'Total equity', 390000000),
        COMBINED,
    ])
    assert both.get_stockholders_equity() == 387255000

    nci_only = _stub([
        ('us-gaap_StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest', 'Total equity', 390000000),
        COMBINED,
    ])
    assert nci_only.get_stockholders_equity() == 390000000


@pytest.mark.fast
def test_label_fallback_never_matches_the_combined_caption():
    assert _stub([COMBINED]).get_stockholders_equity() is None
    assert _stub([
        COMBINED, ('custom_EquityTotal', "Total stockholders' equity", 3313051000),
    ]).get_stockholders_equity() == 3313051000


# Shell plc FY2025 20-F (accession 0001628280-26-017024), consolidated balance
# sheet at 2025-12-31, read from the filing's XBRL.
SHELL_TOTAL_LIABILITIES_AND_EQUITY = (
    'ifrs-full_EquityAndLiabilities', 'Total liabilities and equity', 370350000000)
SHELL_PARENT = ('ifrs-full_EquityAttributableToOwnersOfParent',
                'Equity attributable to Shell plc shareholders', 174392000000)
SHELL_TOTAL = ('ifrs-full_Equity', 'Total equity', 175319000000)


@pytest.mark.fast
def test_ifrs_parent_equity_wins_over_total_equity():
    # IFRS splits equity like ASC 810 (IAS 1.54(q)-(r)); before the IFRS
    # concepts were looked up, the label fallback returned "Total equity",
    # which includes Shell's $927M non-controlling interest.
    shell = _stub([SHELL_PARENT, SHELL_TOTAL, SHELL_TOTAL_LIABILITIES_AND_EQUITY])
    assert shell.get_stockholders_equity() == 174392000000

    total_only = _stub([SHELL_TOTAL, SHELL_TOTAL_LIABILITIES_AND_EQUITY])
    assert total_only.get_stockholders_equity() == 175319000000


def _filed_equity(financials, period_key):
    return {Decimal(f["value"]) for f in financials.xb.facts.query()
            .by_concept("us-gaap:StockholdersEquity", exact=True)
            .by_period_key(period_key)
            .by_custom(lambda f: not f["is_dimensioned"]).execute()}


@pytest.mark.fast
@pytest.mark.parametrize("directory, period_key, expected", [
    # American Airlines 10-K FY2025, 0000006201-26-000014: the reported case.
    ("tests/fixtures/xbrl/aal/10k_2025", "instant_2025-12-31", -3727000000),
    # Coca-Cola 10-K for FY2023: parent equity, not the 27,480,000,000 NCI-inclusive total.
    ("tests/fixtures/xbrl/ko/10k_2024", "instant_2023-12-31", 25941000000),
    # Golub Capital BDC 10-Q for 2025-03-31: "Total Net Assets", previously None.
    ("tests/fixtures/xbrl/gbdc", "instant_2025-03-31", 4043498000),
])
def test_fixture_filings_return_the_filed_stockholders_equity(directory, period_key, expected):
    financials = Financials(XBRL.from_directory(Path(directory)))
    assert financials.get_stockholders_equity() == expected
    assert _filed_equity(financials, period_key) == {Decimal(expected)}


@pytest.mark.network
@pytest.mark.vcr
def test_starbucks_reports_its_deficit_not_total_assets():
    """Starbucks 10-Q 2026-06-28, 0000829224-26-000130: total shareholders' deficit
    -7,674.3M (2025-09-28: -8,096.6M); total assets 28,294.7M."""
    from edgar import Filing

    sbux = Financials(Filing(form='10-Q', filing_date='2026-07-29', company='STARBUCKS CORP',
                             cik=829224, accession_no='0000829224-26-000130').xbrl())
    assert sbux.get_stockholders_equity() == -7674300000
    assert sbux.get_stockholders_equity(1) == -8096600000


@pytest.mark.network
@pytest.mark.vcr
def test_novagold_reports_its_uncaptioned_equity_total():
    """NovaGold 10-Q 2026-08-31, 0001171843-26-006530: equity 387,255 thousand
    (2025-11-30: 163,794), tagged us-gaap:StockholdersEquity."""
    from edgar import Filing

    novagold = Financials(Filing(form='10-Q', filing_date='2026-10-08', company='NOVAGOLD RESOURCES INC',
                                 cik=1173420, accession_no='0001171843-26-006530').xbrl())
    assert novagold.get_stockholders_equity() == 387255000
    assert novagold.get_stockholders_equity(1) == 163794000

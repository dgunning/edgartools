"""Regression: ``get_current_assets()`` / ``get_current_liabilities()`` returned a
narrower company subtotal, or None, instead of the filed current totals.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1661

Both getters matched balance-sheet labels only. r'Total Current Assets' is
unanchored, so ADP's "Total current assets before funds held for clients"
(adp_TotalAssetsBeforeFundsHeldClients, $8.603B), which sits above the real
total, was returned in place of us-gaap:AssetsCurrent ($52.561B), and
``current_ratio`` read 1.534 instead of 1.051. A total captioned "Assets,
Current, Total" (BlackBerry) matched no pattern and gave None.

The getters now look up the concept first, as ``get_total_assets()`` does, and
the label fallback is anchored at both ends.
"""
import pandas as pd
import pytest

from edgar.financials import Financials


def _stub(rows):
    """A Financials whose balance sheet is ``rows`` of (concept, label, value)."""
    df = pd.DataFrame(
        [{'concept': c, 'label': lbl, 'abstract': False, '2026-06-30': v} for c, lbl, v in rows])
    financials = Financials(object())
    financials._render_statement_frame = lambda statement_type: (None, df.copy())
    return financials


@pytest.mark.fast
def test_current_totals_are_the_concepts_not_a_subtotal_above_them():
    financials = _stub([
        ('adp_TotalAssetsBeforeFundsHeldClients', 'Total current assets before funds held for clients', 8603300000),
        ('us-gaap_AssetsCurrent', 'Total current assets', 52561100000),
        ('adp_TotalCurrentLiabilitiesBeforeClientFundsObligations',
         'Total current liabilities before client funds obligations', 5609400000),
        ('us-gaap_LiabilitiesCurrent', 'Total current liabilities', 50024900000),
    ])
    assert financials.get_current_assets() == 52561100000
    assert financials.get_current_liabilities() == 50024900000


@pytest.mark.fast
def test_label_fallback_is_anchored():
    """No component or subtotal matches; an unmapped total still does."""
    components_only = _stub([
        ('custom_A', 'Total current assets before funds held for clients', 8603300000),
        ('custom_B', 'Current assets of discontinued operations', 75),
        ('custom_C', 'Current liabilities of discontinued operations', 40),
    ])
    assert components_only.get_current_assets() is None
    assert components_only.get_current_liabilities() is None

    unmapped_totals = _stub([
        ('custom_B', 'Current assets of discontinued operations', 75),
        ('custom_TotalCA', 'Assets, Current, Total', 1000),
        ('custom_TotalCL', 'Total current liabilities', 600),
    ])
    assert unmapped_totals.get_current_assets() == 1000
    assert unmapped_totals.get_current_liabilities() == 600


def _xbrl_only(**filing):
    """The filing's XBRL, read from the documents its index page lists.

    The full submission (.txt) carries every exhibit (ADP's is 143 MB);
    FilingSGML.from_homepage is the library's own fallback that reads each
    document separately, so the cassette holds only the files parsed.
    """
    from edgar import Filing
    from edgar.sgml.sgml_common import FilingSGML

    filing = Filing(**filing)
    filing._sgml = FilingSGML.from_homepage(filing.homepage)
    return filing.xbrl()


@pytest.mark.network
@pytest.mark.vcr
def test_adp_reports_its_filed_current_totals():
    """ADP 10-K 2026-06-30, 0000008670-26-000030 (millions): Total current assets
    52,561.1 (prior 43,252.2); Total current liabilities 50,024.9 (prior 41,278.3)."""
    adp = Financials(_xbrl_only(form='10-K', filing_date='2026-08-05',
                                company='AUTOMATIC DATA PROCESSING INC', cik=8670,
                                accession_no='0000008670-26-000030'))
    assert adp.get_current_assets() == 52561100000
    assert adp.get_current_assets(1) == 43252200000
    assert adp.get_current_liabilities() == 50024900000
    assert adp.get_current_liabilities(1) == 41278300000
    assert round(adp.get_financial_metrics()['current_ratio'], 3) == 1.051

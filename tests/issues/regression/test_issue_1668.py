"""Regression: the share-count getters returned None for the combined
basic-and-diluted weighted-average row.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1668

A filer whose basic and diluted counts are the same tags one row with
us-gaap:WeightedAverageNumberOfShareOutstandingBasicAndDiluted. The element name
has a singular "Share", so none of the getters' plural patterns matched it and
both returned None; 10x Genomics' FY2019 10-K presents 39,091,366.
"""
import pandas as pd
import pytest

from edgar.financials import Financials

COMBINED = 'us-gaap_WeightedAverageNumberOfShareOutstandingBasicAndDiluted'


def _stub(rows):
    df = pd.DataFrame(
        [{'concept': c, 'label': lbl, 'abstract': False, '2019-12-31': v} for c, lbl, v in rows])
    financials = Financials(object())
    financials._render_statement_frame = lambda statement_type: (None, df.copy())
    return financials


@pytest.mark.fast
def test_combined_row_serves_both_getters():
    financials = _stub([
        ('us-gaap_EarningsPerShareBasicAndDiluted', 'Net loss per share, basic and diluted', -0.8),
        (COMBINED, 'Weighted-average shares used to compute net loss per share, basic and diluted', 39091366),
    ])
    assert financials.get_shares_outstanding_basic() == 39091366
    assert financials.get_shares_outstanding_diluted() == 39091366


@pytest.mark.fast
def test_combined_row_comes_before_period_end_shares():
    """The weighted average, not the period-end count, is the EPS denominator."""
    financials = _stub([
        ('us-gaap_CommonStockSharesOutstanding', 'Common stock, shares outstanding', 99999999),
        (COMBINED, 'Weighted-average shares, basic and diluted', 39091366),
    ])
    assert financials.get_shares_outstanding_basic() == 39091366


@pytest.mark.fast
def test_separate_rows_still_win():
    financials = _stub([
        ('us-gaap_WeightedAverageNumberOfSharesOutstandingBasic', 'Basic', 100),
        ('us-gaap_WeightedAverageNumberOfDilutedSharesOutstanding', 'Diluted', 110),
        (COMBINED, 'Basic and diluted', 999),
    ])
    assert financials.get_shares_outstanding_basic() == 100
    assert financials.get_shares_outstanding_diluted() == 110


def _xbrl_only(**filing):
    """The filing's XBRL, read from the documents its index page lists
    (FilingSGML.from_homepage), so the cassette holds only the files parsed."""
    from edgar import Filing
    from edgar.sgml.sgml_common import FilingSGML

    filing = Filing(**filing)
    filing._sgml = FilingSGML.from_homepage(filing.homepage)
    return filing.xbrl()


@pytest.mark.network
@pytest.mark.vcr
def test_10x_genomics_reports_its_combined_share_count():
    """10x Genomics 10-K FY2019, 0001193125-20-052640: "Weighted-average shares used
    to compute net loss per share, basic and diluted" 39,091,366 (2018: 13,392,273)."""
    txg = Financials(_xbrl_only(form='10-K', filing_date='2020-02-27', company='10x Genomics, Inc.',
                                cik=1770787, accession_no='0001193125-20-052640'))
    assert txg.get_shares_outstanding_basic() == 39091366
    assert txg.get_shares_outstanding_diluted() == 39091366
    assert txg.get_shares_outstanding_basic(1) == 13392273
    assert txg.get_shares_outstanding_diluted(1) == 13392273

"""Regression: ``get_revenue()`` returned None, or a component, for utilities
whose operating revenue total is us-gaap:RegulatedAndUnregulatedOperatingRevenue.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1665

No revenue mapping carries that concept, and the captions utilities give it
("OPERATING REVENUES", "Total operating revenues") match no label pattern.
NextEra's Q2 2026 10-Q got None for $7,534M; MGE Energy's got its "Gas revenue"
line ($29.6M), the only label ending in "revenue", for a $161.2M total.
"""
import pandas as pd
import pytest

from edgar.financials import Financials

TOTAL = 'us-gaap_RegulatedAndUnregulatedOperatingRevenue'


def _stub(rows):
    df = pd.DataFrame(
        [{'concept': c, 'label': lbl, 'abstract': False, '2026-06-30': v} for c, lbl, v in rows])
    financials = Financials(object())
    financials._render_statement_frame = lambda statement_type: (None, df.copy())
    return financials


@pytest.mark.fast
def test_utility_total_is_revenue_not_a_component():
    financials = _stub([
        ('us-gaap_RegulatedOperatingRevenueElectricNonNuclear', 'Electric revenues', 131594000),
        ('us-gaap_RegulatedOperatingRevenueGas', 'Gas revenue', 29601000),
        (TOTAL, 'Total Operating Revenues', 161195000),
    ])
    assert financials.get_revenue() == 161195000


@pytest.mark.fast
def test_utility_total_comes_before_contract_revenue_and_after_revenues():
    with_contract_component = _stub([
        ('us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenue from contracts', 3000),
        (TOTAL, 'Total operating revenues', 3119),
    ])
    assert with_contract_component.get_revenue() == 3119

    with_revenues_total = _stub([
        (TOTAL, 'Utility operating revenues', 3119),
        ('us-gaap_Revenues', 'Total revenues', 3500),
    ])
    assert with_revenues_total.get_revenue() == 3500


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
def test_nextera_reports_its_operating_revenue_total():
    """NextEra 10-Q Q2 2026, 0000753308-26-000060: OPERATING REVENUES 7,534 (2025: 6,700) $M."""
    nextera = Financials(_xbrl_only(form='10-Q', filing_date='2026-07-24', company='NEXTERA ENERGY INC',
                                    cik=753308, accession_no='0000753308-26-000060'))
    assert nextera.get_revenue() == 7534000000
    assert nextera.get_revenue(1) == 6700000000


@pytest.mark.network
@pytest.mark.vcr
def test_mge_reports_its_total_not_its_gas_revenue_line():
    """MGE Energy 10-Q Q2 2026, 0001193125-26-333969 ($K): Total Operating Revenues
    161,195 (2025: 159,452); its Gas revenue line, returned before, is 29,601."""
    mge = Financials(_xbrl_only(form='10-Q', filing_date='2026-08-05', company='MGE ENERGY INC',
                                cik=1161728, accession_no='0001193125-26-333969'))
    assert mge.get_revenue() == 161195000
    assert mge.get_revenue(1) == 159452000

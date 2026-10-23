"""Regression: ``get_capital_expenditures()`` returned accrued, unpaid capital
expenditures as capex when the cash capex row is on an unmapped concept.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1660

The concept pass only knows PaymentsToAcquirePropertyPlantAndEquipment and
PaymentsToAcquireProductiveAssets. When the investing row is tagged otherwise
(Thor: PaymentsToAcquireOtherPropertyPlantAndEquipment; Essential Utilities:
PaymentsToAcquireBuildings), the unanchored label pattern r'Capital
Expenditures' matched the supplemental noncash row
us-gaap:CapitalExpendituresIncurredButNotYetPaid, captioned "Capital
expenditures in accounts payable" or displayed as plain "Capital Expenditures".
Essential's free cash flow came out +440,461,000 instead of -73,187,000.
"""
import pandas as pd
import pytest

from edgar.financials import Financials

ACCRUED = 'us-gaap_CapitalExpendituresIncurredButNotYetPaid'


def _stub(rows):
    df = pd.DataFrame(
        [{'concept': c, 'label': lbl, 'abstract': False, '2026-06-30': v} for c, lbl, v in rows])
    financials = Financials(object())
    financials._render_statement_frame = lambda statement_type: (None, df.copy())
    return financials


@pytest.mark.fast
@pytest.mark.parametrize("cash_concept, cash_label, accrued_label", [
    ('us-gaap_PaymentsToAcquireOtherPropertyPlantAndEquipment',
     'Purchases of property, plant and equipment', 'Capital expenditures in accounts payable'),
    ('us-gaap_PaymentsToAcquireBuildings',
     'Property, plant and equipment additions, including the debt component of AFUDC', 'Capital Expenditures'),
])
def test_cash_capex_not_the_noncash_disclosure(cash_concept, cash_label, accrued_label):
    """The noncash row sorts first only when it comes first; put it first."""
    financials = _stub([
        ('us-gaap_NetCashProvidedByUsedInOperatingActivities', 'Net cash from operating activities', 588980000),
        (ACCRUED, accrued_label, 148519000),
        (cash_concept, cash_label, 662167000),
    ])
    assert financials.get_capital_expenditures() == 662167000
    assert financials.get_free_cash_flow() == 588980000 - 662167000


@pytest.mark.fast
def test_only_a_noncash_row_gives_none():
    financials = _stub([
        (ACCRUED, 'Capital Expenditures', 148519000),
        ('custom_AccruedCapex', 'Accrued capital expenditures', 5),
    ])
    assert financials.get_capital_expenditures() is None
    assert financials.get_free_cash_flow() is None


@pytest.mark.fast
@pytest.mark.parametrize("label", [
    "Capital expenditures", "Capital expenditure", "Additions to property and equipment",
    "Purchases of property and equipment", "Payments for capital expenditures",
    "Capital expenditures, net of grants",
])
def test_unmapped_cash_capex_still_resolves_by_label(label):
    assert _stub([('custom_Capex', label, 42)]).get_capital_expenditures() == 42


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
def test_essential_utilities_reports_cash_capex():
    """Essential Utilities 10-Q, six months to 2026-06-30, 0000078128-26-000077 ($K):
    Property, plant and equipment additions 662,167 (2025: 612,629); operating cash
    flow 588,980; noncash Capital Expenditures 148,519."""
    wtrg = Financials(_xbrl_only(form='10-Q', filing_date='2026-08-05', company='Essential Utilities, Inc.',
                                 cik=78128, accession_no='0000078128-26-000077'))
    assert wtrg.get_capital_expenditures() == 662167000
    assert wtrg.get_capital_expenditures(1) == 612629000
    assert wtrg.get_free_cash_flow() == -73187000


@pytest.mark.network
@pytest.mark.vcr
def test_thor_reports_cash_capex():
    """Thor Industries 10-K FY2026, 0000730263-26-000027 ($K): Purchases of property,
    plant and equipment 152,387 (FY2025: 122,987); operating cash flow 321,223;
    Capital expenditures in accounts payable 6,303."""
    thor = Financials(_xbrl_only(form='10-K', filing_date='2026-09-22', company='THOR INDUSTRIES INC',
                                 cik=730263, accession_no='0000730263-26-000027'))
    assert thor.get_capital_expenditures() == 152387000
    assert thor.get_capital_expenditures(1) == 122987000
    assert thor.get_free_cash_flow() == 168836000

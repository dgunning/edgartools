"""
``us-gaap:RegulatedAndUnregulatedOperatingRevenue`` is a utility's total operating revenue
("The total amount of operating revenues recognized during the period"), regulated and
unregulated, electric, gas and water alike. The mapping gave it ``ElectricUtilityRevenue``, so
a ``standard_concept == "Revenue"`` filter found no top line for a utility, and selecting
``ElectricUtilityRevenue`` picked up gas and water revenue. It now maps to ``Revenue`` and is a
listed member of that total (``total_membership.json``, GH #1444), so the closed-membership
guard lets it through.

Ground truth: MGE Energy 10-Q for Q2 2026, accession 0001193125-26-333969, consolidated
statements of income ($K): Electric revenues 131,594, Gas revenue 29,601, Total Operating
Revenues 161,195 (2025: 159,452). The total was ``ElectricUtilityRevenue`` although it
includes the gas line; it is now ``Revenue``. The same holds for American Water Works'
Q2 2026 10-Q (0001410636-26-000120), whose $1,355M "Operating revenues" is water and
wastewater revenue.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1844
"""

import json
from pathlib import Path

import pytest

from edgar.financials import Financials
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import ReverseIndex

_STANDARDIZATION = Path(reverse_index_module.__file__).parent
TOTAL_MEMBERSHIP = json.loads((_STANDARDIZATION / "total_membership.json").read_text(encoding="utf-8"))["totals"]
TAG = "RegulatedAndUnregulatedOperatingRevenue"


@pytest.fixture(scope="module")
def index():
    return ReverseIndex()


@pytest.mark.fast
@pytest.mark.parametrize("spelling", [TAG, f"us-gaap:{TAG}", f"us-gaap_{TAG}"])
def test_utility_operating_revenue_total_is_revenue(index, spelling):
    result = index.lookup(spelling)
    assert result is not None
    assert result.standard_concepts == ["Revenue"]
    assert result.display_names == ["Revenue"]
    assert index.get_standard_concept(spelling, {"is_total": True}) == "Revenue"


@pytest.mark.fast
def test_it_is_a_listed_member_of_the_revenue_total():
    assert TAG in TOTAL_MEMBERSHIP["Revenue"]


@pytest.mark.fast
def test_electric_utility_revenue_keeps_its_own_element(index):
    """Only the total moved; the electric element still has the electric concept."""
    assert index.lookup("ElectricUtilityRevenue").standard_concepts == ["ElectricUtilityRevenue"]
    assert index.concept_to_display_name("ElectricUtilityRevenue") == "Electric Utility Revenue"


# The cassette is the one test_issue_1665.py recorded from live SEC for the same filing.
@pytest.fixture
def vcr_cassette_name():
    return "test_mge_reports_its_total_not_its_gas_revenue_line"


def _xbrl_only(**filing):
    """The filing's XBRL, read from the documents its index page lists (as in test_issue_1665)."""
    from edgar import Filing
    from edgar.sgml.sgml_common import FilingSGML
    filing = Filing(**filing)
    filing._sgml = FilingSGML.from_homepage(filing.homepage)
    return filing.xbrl()


@pytest.mark.network
@pytest.mark.vcr
def test_mge_operating_revenue_total_is_revenue_not_electric():
    """MGE Energy 10-Q Q2 2026, 0001193125-26-333969 ($K): Total Operating Revenues 161,195."""
    xbrl = _xbrl_only(form='10-Q', filing_date='2026-08-05', company='MGE ENERGY INC',
                      cik=1161728, accession_no='0001193125-26-333969')
    frame = xbrl.statements.income_statement().to_dataframe(standard=True)
    frame = frame[~frame["dimension"]]

    revenue = frame[frame["standard_concept"] == "Revenue"]
    assert revenue["concept"].tolist() == [f"us-gaap_{TAG}"]
    assert revenue["2026-06-30 (Q2)"].tolist() == [161_195_000]
    assert revenue["2025-06-30 (Q2)"].tolist() == [159_452_000]
    assert (frame["standard_concept"] == "ElectricUtilityRevenue").sum() == 0

    gas = frame[frame["concept"] == "us-gaap_RegulatedOperatingRevenueGas"]
    assert gas["2026-06-30 (Q2)"].tolist() == [29_601_000]
    # The revenue getter (GH #1665) still returns the total.
    assert Financials(xbrl).get_revenue() == 161_195_000

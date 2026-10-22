"""
Financials.get_revenue() returned a component of a bank's revenue, not its top line.

Bead: edgartools-u9yc9

Banks report total revenue as us-gaap:RevenuesNetOfInterestExpense ("Total net
revenue"), which the standardization's 'Revenue' mapping does not carry. So
get_revenue() fell to whatever matched next:

- JPMorgan's statement has no other mapped concept, so the label patterns ran
  and ``Revenue$`` took "Noninterest revenue": $87.0B of $182.4B for FY2025.
- Wells Fargo's fee lines are tagged as contract revenue, which was searched
  before the bank total: "Fee income", $16.1B of $83.7B.
- American Express: $37.4B of $72.2B.
- U.S. Bancorp presents no total on its income statement, and the label
  patterns took "Card revenue", $1.7B.

The bank total is now searched after Revenues and before contract revenue. On a
bank's statement (one with a us-gaap:NoninterestIncome row) the label patterns
are skipped, because every "... revenue" label there is a component.

Bead: edgartools-hmj0j. That left U.S. Bancorp and Capital One with no value.
Both file the total off the face statement as a non-dimensional
us-gaap:Revenues fact, next to dimensioned segment values of the same concept,
and get_revenue() now reads it for the statement's period.
"""
from types import SimpleNamespace

import pandas as pd
import pytest

from edgar.financials import Financials
from tests.paths import FIXTURES_DIR

# JPMorgan Chase 10-K for FY2023, accession 0000019617-24-000225, from
# data.sec.gov companyconcept: us-gaap:RevenuesNetOfInterestExpense 2023 and 2022.
# us-gaap:NoninterestIncome in the same filing is 68,837,000,000 and
# 61,985,000,000, which is what get_revenue() returned before the fix.
JPM_FY2023_TOTAL_NET_REVENUE = 158_104_000_000
JPM_FY2022_TOTAL_NET_REVENUE = 128_695_000_000


@pytest.mark.fast
def test_jpmorgan_revenue_is_total_net_revenue_not_noninterest_revenue():
    from edgar.xbrl import XBRL
    xb = XBRL.from_directory(FIXTURES_DIR / "xbrl" / "jpm" / "10k_2024")
    financials = Financials(xb)
    assert financials.get_revenue() == JPM_FY2023_TOTAL_NET_REVENUE
    assert financials.get_revenue(1) == JPM_FY2022_TOTAL_NET_REVENUE


class _Facts:
    """``xb.facts`` holding the given rows of the instance's fact frame."""

    def __init__(self, rows):
        self._frame = pd.DataFrame(rows, columns=[
            "concept", "numeric_value", "period_start", "period_end", "is_dimensioned"])

    def query(self):
        return self

    def by_concept(self, concept, exact=False):
        self._concept = concept
        return self

    def to_dataframe(self):
        return self._frame[self._frame["concept"] == self._concept]


def _financials_with_income_statement(monkeypatch, rows, facts=()):
    """A Financials whose income statement is exactly `rows` (concept, label, value),
    for the year 2025, and whose instance holds `facts`."""
    df = pd.DataFrame(
        [{"concept": c, "label": label, "2025-12-31": value, "level": 1, "abstract": False}
         for c, label, value in rows]
    )
    period = SimpleNamespace(start_date="2025-01-01", end_date="2025-12-31", quarter=None,
                             label="2025", is_duration=True)
    financials = Financials(xb=SimpleNamespace(facts=_Facts(list(facts))))
    monkeypatch.setattr(financials, "_render_statement_frame",
                        lambda statement_type: (SimpleNamespace(periods=[period]), df))
    return financials


_USB_FACE_ROWS = [
    ("us-gaap_InterestIncomeExpenseNet", "Net interest income", 16_649_000_000),
    ("us-gaap_FeeAndCommissionCreditAndDebitCards", "Card revenue", 1_735_000_000),
    ("usb_CapitalMarketsRevenue", "Capital markets revenue", 1_633_000_000),
    ("us-gaap_NoninterestIncome", "Total noninterest income", 11_891_000_000),
]


@pytest.mark.fast
def test_bank_total_beats_a_contract_revenue_fee_line(monkeypatch):
    """Wells Fargo's shape: fee lines tagged as contract revenue, above the total."""
    financials = _financials_with_income_statement(monkeypatch, [
        ("us-gaap_InterestIncomeExpenseNet", "Net interest income", 47_484_000_000),
        ("us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax", "Fee income", 16_081_000_000),
        ("us-gaap_NoninterestIncome", "Total noninterest income", 36_215_000_000),
        ("us-gaap_RevenuesNetOfInterestExpense", "Total revenue", 83_699_000_000),
    ])
    assert financials.get_revenue() == 83_699_000_000


@pytest.mark.fast
def test_a_bank_without_any_total_reports_no_revenue_rather_than_a_component(monkeypatch):
    """U.S. Bancorp's face statement, in a filing with no us-gaap:Revenues fact."""
    financials = _financials_with_income_statement(monkeypatch, _USB_FACE_ROWS)
    assert financials.get_revenue() is None


@pytest.mark.fast
def test_a_bank_without_a_total_row_reports_its_filed_total(monkeypatch):
    """U.S. Bancorp's shape, 0000036104-26-000011: the total is filed only as a
    non-dimensional us-gaap:Revenues fact. Segment values of the same concept are
    dimensioned, and a prior year's total is another period; neither is taken."""
    financials = _financials_with_income_statement(monkeypatch, _USB_FACE_ROWS, facts=[
        ("us-gaap:Revenues", 12_083_000_000, "2025-01-01", "2025-12-31", True),
        ("us-gaap:Revenues", 7_607_000_000, "2025-01-01", "2025-12-31", True),
        ("us-gaap:Revenues", 27_455_000_000, "2024-01-01", "2024-12-31", False),
        ("us-gaap:Revenues", 28_656_000_000, "2025-01-01", "2025-12-31", False),
    ])
    assert financials.get_revenue() == 28_656_000_000
    assert financials.get_revenue(1) is None  # the statement has one period


@pytest.mark.fast
def test_label_fallback_still_serves_a_non_bank(monkeypatch):
    """The bank guard must not switch off the label patterns for everyone else."""
    financials = _financials_with_income_statement(monkeypatch, [
        ("acme_ServiceRevenue", "Total Revenue", 5_000_000),
        ("us-gaap_CostOfRevenue", "Cost of revenue", 3_000_000),
    ])
    assert financials.get_revenue() == 5_000_000


@pytest.mark.network
@pytest.mark.parametrize("accession, expected", [
    # data.sec.gov companyconcept, us-gaap:RevenuesNetOfInterestExpense, FY2025
    ("0000072971-26-000133", 83_699_000_000),   # Wells Fargo
    ("0000004962-26-000080", 72_229_000_000),   # American Express
    ("0001628280-26-008131", 182_447_000_000),  # JPMorgan Chase
    # No total row on the face statement; the non-dimensional us-gaap:Revenues
    # fact in the filing's instance, FY2025 (edgartools-hmj0j)
    ("0000036104-26-000011", 28_656_000_000),   # U.S. Bancorp
    ("0000927628-26-000024", 53_434_000_000),   # Capital One
], ids=["WFC", "AXP", "JPM", "USB", "COF"])
def test_bank_10k_revenue_matches_sec(accession, expected):
    from edgar import find
    financials = Financials(find(accession).xbrl())
    assert financials.get_revenue() == expected

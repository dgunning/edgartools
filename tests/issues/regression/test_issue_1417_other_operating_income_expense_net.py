"""
``OtherOperatingIncomeExpenseNet`` (704 companies) was stored as ``OtherIncomeIS``,
"Other Income", a total in Non-Operating Items. FASB defines the element as other
income and expense from the normal revenue-producing operations, inside
operating income, so an amount that counts toward operating income was shown
below it.

The vocabulary had no operating "other income (expense), net" concept, and
``OtherOperatingExpense`` would put a credit-normal net amount in an expense
concept. The maintainer chose a new concept, ``OtherOperatingIncomeExpenseNet``,
in Operating Expenses (the open choice in #1417).

Ground truth: Amazon's FY2022 10-K (0001018724-23-000004) reports "Other
operating expense (income), net" of $1,263 million inside total operating
expenses of $501,735 million.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1417
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization.reverse_index import get_reverse_index
from edgar.xbrl.standardization.sections import get_section_membership

AMZN_FY2022 = Path("tests/fixtures/xbrl/special_cases/segments/amzn")


def test_the_element_maps_to_the_operating_concept():
    result = get_reverse_index().lookup("OtherOperatingIncomeExpenseNet")

    assert result is not None
    assert result.standard_concepts == ["OtherOperatingIncomeExpenseNet"]
    assert not result.is_ambiguous


def test_the_concept_sits_in_operating_expenses_not_non_operating_items():
    sections = get_section_membership()

    assert sections.get_section("OtherOperatingIncomeExpenseNet", "IncomeStatement") == "Operating Expenses"
    assert "OtherOperatingIncomeExpenseNet" not in sections.get_concepts_in_section("IncomeStatement", "Non-Operating Items")


@pytest.fixture(scope="module")
def amzn_income_statement():
    return XBRL.from_directory(AMZN_FY2022).statements.income_statement().to_dataframe()


def test_amazon_fy2022_row_is_standardized_inside_operating_income(amzn_income_statement):
    df = amzn_income_statement
    rows = df[df["concept"] == "us-gaap_OtherOperatingIncomeExpenseNet"]
    assert len(rows) == 1
    row = rows.iloc[0]

    assert row["standard_concept"] == "OtherOperatingIncomeExpenseNet"
    assert row["2022-12-31 (FY)"] == 1_263_000_000
    # Filer label kept: standardization reports the concept, it does not relabel the row.
    assert row["label"] == "Other operating expense (income), net"

    position = list(df["concept"])
    assert position.index("us-gaap_OtherOperatingIncomeExpenseNet") < position.index("us-gaap_OperatingIncomeLoss")


def test_other_income_keeps_only_non_operating_members():
    """The concept the element left still holds the non-operating other-income tags."""
    index = get_reverse_index()

    assert index.lookup("OtherIncome").standard_concepts == ["OtherIncomeIS"]
    members = {tag for tag, entry in index._index.items()
               if isinstance(entry, dict) and "OtherIncomeIS" in entry.get("standard_tags", [])}
    assert "OtherOperatingIncomeExpenseNet" not in members

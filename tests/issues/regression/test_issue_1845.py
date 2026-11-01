"""
IFRS 16 lease-liability interest (``InterestExpenseOnLeaseLiabilities``, bare and
``ifrs-full_`` keys, 39 companies) was standardized as ``OperatingLeaseExpense``. IFRS 16.49
makes it a finance cost, separate from right-of-use depreciation, and the us-gaap
``FinanceLeaseInterestExpense`` already maps to ``InterestExpense``. Both keys now take
``InterestExpense``. ``DepreciationRightofuseAssets`` is left alone here (GH #1451).

Ground truth: Opera Ltd FY2025 20-F (IFRS), accession 0001737450-26-000005, Note 6 Finance
income and finance expenses: "Interest expense on lease liabilities" $461K (2024: $518K,
2023: $356K), part of finance expense. It was ``OperatingLeaseExpense``; it is now
``InterestExpense``. Shell's FY2025 20-F (0001628280-26-017024) reports the same element,
$1,866M, which the issue measured.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1845
"""

import json
from pathlib import Path

import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import ReverseIndex

_STANDARDIZATION = Path(reverse_index_module.__file__).parent
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def index():
    return ReverseIndex()


@pytest.mark.fast
@pytest.mark.parametrize(
    "spelling",
    [
        "InterestExpenseOnLeaseLiabilities",
        "ifrs-full_InterestExpenseOnLeaseLiabilities",
        "ifrs-full:InterestExpenseOnLeaseLiabilities",
        "ifrs:InterestExpenseOnLeaseLiabilities",
    ],
)
def test_lease_liability_interest_is_interest_expense(index, spelling):
    result = index.lookup(spelling)
    assert result is not None
    assert result.standard_concepts == ["InterestExpense"]
    assert result.display_names == ["Interest Expense"]


@pytest.mark.fast
def test_entry_metadata_follows_finance_lease_interest():
    entry = GAAP_MAPPINGS["InterestExpenseOnLeaseLiabilities"]
    sibling = GAAP_MAPPINGS["FinanceLeaseInterestExpense"]
    assert sibling["standard_tags"] == ["InterestExpense"]
    for field in ("standard_tags", "display_name", "statement", "section"):
        assert entry[field] == sibling[field], field
    assert entry["is_total"] is False
    assert GAAP_MAPPINGS["ifrs-full_InterestExpenseOnLeaseLiabilities"] == {"standard_tags": ["InterestExpense"]}


@pytest.mark.fast
def test_us_gaap_operating_lease_cost_keeps_its_concept(index):
    assert index.lookup("us-gaap:OperatingLeaseCost").standard_concepts == ["OperatingLeaseExpense"]


# Opera's FY2025 20-F (IFRS). The schema embeds the presentation and label linkbases. The
# cassette is the one test_issue_1446_fx_and_lease_mappings.py recorded from live SEC for the
# same two documents.
OPRA_20F_FOLDER = "https://www.sec.gov/Archives/edgar/data/1737450/000173745026000005/"
OPRA_20F_XBRL_FILES = ("opra-20251231.xsd", "opra-20251231_htm.xml")
FINANCE_EXPENSE_ROLE = (
    "http://www.opera.com/20251231/taxonomy/role/DisclosureNote6FinanceIncomeAndFinanceExpensesSummaryOf"
    "ItemsOfFinanceIncomeAndFinanceExpensesIncludingForeignExchangeGainsAndLossesDet"
)


@pytest.fixture
def vcr_cassette_name():
    return "test_opera_exchange_rate_effect_is_not_the_net_change_in_cash"


@pytest.mark.network
@pytest.mark.vcr
def test_opera_lease_interest_is_interest_expense(tmp_path):
    """Opera Ltd FY2025 20-F, 0001737450-26-000005, Note 6: interest expense on lease
    liabilities $461K (2024: $518K, 2023: $356K)."""
    for name in OPRA_20F_XBRL_FILES:
        (tmp_path / name).write_text(download_file(OPRA_20F_FOLDER + name), encoding="utf-8")
    statement = XBRL.from_directory(tmp_path).statements[FINANCE_EXPENSE_ROLE]
    assert statement is not None
    frame = statement.render(standard=True).to_dataframe()
    rows = frame[(frame["concept"] == "ifrs-full_InterestExpenseOnLeaseLiabilities") & ~frame["dimension"]]
    assert rows["standard_concept"].tolist() == ["InterestExpense"]
    assert rows["2025-12-31"].tolist() == [461_000]
    assert rows["2024-12-31"].tolist() == [518_000]
    assert rows["2023-12-31"].tolist() == [356_000]
    assert (frame["standard_concept"] == "OperatingLeaseExpense").sum() == 0

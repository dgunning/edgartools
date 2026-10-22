"""
Bank, insurer, fund, REIT and utility line items were mapped to totals or to
concepts of another nature. Deposit components resolved to TotalDeposits,
interest-income components to NetInterestIncome, loan-loss provisions to
NetCashFromOperatingActivities, FHLB advances and repurchase agreements to
Liabilities, and fund fees to TotalOperatingExpenses. On Auburn National's
FY2023 balance sheet three rows carried TotalDeposits, so summing by standard
concept gave $1,792.5M against the filed $896.2M.

The 45 rows follow the issue's table: 39 remap to the concept their FASB
definition supports, and 6 with no fitting concept are removed.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1441
GitHub Issue: https://github.com/dgunning/edgartools/issues/1638
"""

import json
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.core import ConceptMapper, MappingStore, standardize_statement
from edgar.xbrl.standardization.exclusions import EXCLUDED_TAGS
from edgar.xbrl.standardization.reverse_index import get_reverse_index
from edgar.xbrl.standardization.sections import get_section_for_concept, get_statement_for_concept
from edgar.xbrl.standardization.sic_industry import _FF48_SIC_RANGES

EXPECTED = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "standardization" / "issue_1441_industry_expected.json").read_text(encoding="utf-8")
)
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))
FIXTURES = Path(__file__).parents[2] / "fixtures" / "xbrl"

# Pin the removals independently of the expected-mapping fixture.
DELETED_TAGS = {
    "DepositsFairValueDisclosure",
    "IncreaseDecreaseInDeposits",
    "InterestBearingDepositLiabilities",
    "LoansAndLeasesReceivableImpairedTroubledDebtInterestIncome",
    "NoninterestBearingDepositLiabilities",
    "TimeDeposits",
}
# The two rows that are themselves totals: total interest income, and a fund's net assets.
TOTAL_TAGS = {"InterestAndDividendIncomeOperating", "AssetsNet"}
# FHLB advances sit in either section; the balance-sheet section picks the side.
AMBIGUOUS_TAGS = {"AdvancesFromFederalHomeLoanBanks"}

INDUSTRIES = sorted({code for _, _, code in _FF48_SIC_RANGES})
STATEMENT_TYPES = ["BalanceSheet", "IncomeStatement", "CashFlowStatement", ""]


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


@pytest.fixture(scope="module")
def mapper():
    return ConceptMapper(MappingStore(read_only=True))


def test_expected_entries_are_the_issue_rows():
    assert len(EXPECTED) == 45
    assert {tag for tag, concepts in EXPECTED.items() if concepts is None} == DELETED_TAGS
    assert sum(concepts is not None for concepts in EXPECTED.values()) == 39
    assert len(INDUSTRIES) == 48


@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_corrected_entries(index, tag):
    expected = EXPECTED[tag]
    if expected is None:
        assert tag not in GAAP_MAPPINGS
    else:
        assert GAAP_MAPPINGS[tag]["standard_tags"] == expected
    result = index.lookup(f"us-gaap:{tag}")
    if expected is None:
        assert result is None
    else:
        assert result is not None
        assert result.standard_concepts == expected
        assert result.display_names == [DISPLAY_NAMES[concept] for concept in expected]
        assert result.is_ambiguous is (tag in AMBIGUOUS_TAGS)


def test_explicit_lookups(index):
    """The rows the issue reproduces, spelled out."""
    assert index.lookup("us-gaap:InterestAndDividendIncomeOperating").standard_concepts == ["TotalInterestIncomeOperating"]
    assert index.lookup("us-gaap:InterestAndFeeIncomeLoansAndLeases").standard_concepts == ["InterestIncome"]
    assert index.lookup("us-gaap:OtherNoninterestExpense").standard_concepts == ["OtherNonInterestExpense"]
    assert index.lookup("us-gaap:PaidInKindInterest").standard_concepts == ["OtherNonCashItemsCF"]
    assert index.lookup("us-gaap:ProvisionForLoanLeaseAndOtherLosses").standard_concepts == ["ProvisionForCreditLosses"]
    assert index.lookup("us-gaap:IncreaseDecreaseInDeposits") is None
    assert index.lookup("us-gaap:NoninterestBearingDepositLiabilities") is None
    assert index.lookup("us-gaap:BankOwnedLifeInsurance").display_names == ["Other Non-Operating Non-Current Assets"]
    assert index.lookup("us-gaap:AssetsNet").display_names == ["Total Equity"]
    assert index.lookup("us-gaap:RegulatoryLiabilityNoncurrent").standard_concepts == ["RegulatedLiabilities"]


@pytest.mark.parametrize(
    "section, expected",
    [("Non-Current Liabilities", "LongTermDebt"), ("Current Liabilities", "ShortTermDebt"), (None, "LongTermDebt")],
)
def test_fhlb_advances_take_the_side_of_their_section(index, section, expected):
    context = {"statement_type": "BalanceSheet", "section": section} if section else None
    assert index.get_standard_concept("us-gaap:AdvancesFromFederalHomeLoanBanks", context=context) == expected


def test_none_of_the_rows_is_excluded():
    assert set(EXPECTED) & EXCLUDED_TAGS == set()


@pytest.mark.parametrize("tag", sorted(EXPECTED))
@pytest.mark.parametrize("industry", INDUSTRIES)
def test_no_industry_brings_the_old_concept_back(index, tag, industry):
    expected = EXPECTED[tag]
    result = index.lookup(f"us-gaap:{tag}", industry=industry)
    if expected is None:
        assert result is None
    else:
        assert result is not None and result.standard_concepts == expected


def test_no_corrected_entry_keeps_an_industry_override():
    assert [tag for tag in EXPECTED if "industry_overrides" in GAAP_MAPPINGS.get(tag, {})] == []


@pytest.mark.parametrize("tag", sorted(tag for tag, concepts in EXPECTED.items() if concepts))
def test_corrected_entry_metadata_matches_its_concept(tag):
    concept = EXPECTED[tag][0]
    entry = GAAP_MAPPINGS[tag]
    statement = get_statement_for_concept(concept)
    assert entry["display_name"] == DISPLAY_NAMES[concept]
    assert entry["statement"] == statement
    assert entry["section"] == get_section_for_concept(concept, statement)
    assert entry["is_total"] is (tag in TOTAL_TAGS)
    assert entry["confidence"] == 0.9
    assert entry.get("ambiguous", False) is (tag in AMBIGUOUS_TAGS)


@pytest.mark.parametrize("tag", sorted(EXPECTED))
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
def test_standardization_preserves_filed_data(mapper, tag, statement_type):
    item = {
        "concept": f"us-gaap_{tag}",
        "label": "Filed disclosure label",
        "values": {"2023-12-31": 123_456},
        "statement_type": statement_type,
    }
    result = standardize_statement([item], mapper)
    assert len(result) == 1
    assert {key: value for key, value in result[0].items() if key != "standard_concept"} == item
    expected = EXPECTED[tag]
    if expected is None:
        assert "standard_concept" not in result[0]
    else:
        assert result[0]["standard_concept"] in expected


def test_no_total_concept_holds_these_line_items(index):
    totals = {"TotalDeposits", "NetInterestIncome", "NetCashFromOperatingActivities",
              "NetCashFromFinancingActivities", "NetCashFromInvestingActivities",
              "Assets", "Liabilities", "TotalOperatingExpenses"}
    members = {tag for tag, entry in index._index.items()
               if isinstance(entry, dict) and totals & set(entry.get("standard_tags", []))}
    assert not members & set(EXPECTED)


# --- statements from a real filing ----------------------------------------------

def _frame(directory, statement):
    xbrl = XBRL.from_directory(FIXTURES / directory)
    frame = getattr(xbrl.statements, statement)().to_dataframe()
    return frame[~frame["dimension"]]


def test_auburn_deposits_sum_to_the_filed_total():
    """Auburn National Bancorporation FY2023 10-K (0001193125-24-067944): total deposits $896,243,000 at Dec 31, 2023.

    Noninterest-bearing ($270,723,000) and interest-bearing ($625,520,000) deposits also carried
    TotalDeposits, so summing by standard concept gave $1,792,486,000.
    """
    frame = _frame("aubn/10k_2023", "balance_sheet")
    deposits = frame[frame["standard_concept"] == "TotalDeposits"]
    assert list(deposits["concept"]) == ["us-gaap_Deposits"]
    assert list(deposits["2023-12-31"]) == [896_243_000]
    parts = frame[frame["concept"].isin(["us-gaap_NoninterestBearingDepositLiabilities",
                                         "us-gaap_InterestBearingDepositLiabilities"])]
    assert sorted(parts["2023-12-31"]) == [270_723_000, 625_520_000]
    assert parts["standard_concept"].isna().all()

    boli = frame[frame["concept"] == "us-gaap_BankOwnedLifeInsurance"]
    assert list(boli["standard_concept"]) == ["OtherNonOperatingNonCurrentAssets"]
    assert list(frame.loc[frame["standard_concept"] == "Assets", "concept"]) == ["us-gaap_Assets"]


def test_auburn_interest_income_is_not_net_interest_income():
    """Auburn National FY2023 10-K (0001193125-24-067944): total interest income $34,374,000, net interest income $26,328,000.

    The interest-income lines and their total all carried NetInterestIncome, five rows summing to $94,403,000.
    """
    frame = _frame("aubn/10k_2023", "income_statement")
    period = "2023-12-31 (FY)"
    net = frame[frame["standard_concept"] == "NetInterestIncome"]
    assert list(net["concept"]) == ["us-gaap_InterestIncomeExpenseNet"]
    assert list(net[period]) == [26_328_000]
    total = frame[frame["standard_concept"] == "TotalInterestIncomeOperating"]
    assert list(total["concept"]) == ["us-gaap_InterestAndDividendIncomeOperating"]
    assert list(total[period]) == [34_374_000]
    # The components now sum to the filed total.
    assert frame.loc[frame["standard_concept"] == "InterestIncome", period].sum() == 34_374_000


def test_auburn_other_noninterest_lines_are_not_their_totals():
    """Auburn National FY2023 10-K (0001193125-24-067944): total noninterest expense $22,594,000,
    of which other noninterest expense $5,609,000; other noninterest income $1,870,000.

    The issue proposed the totals' concepts for the "other" lines. In SEC's CY2023 frames 387 of
    the 400 filers of OtherNoninterestExpense also file NoninterestExpense (median 10% of it), so
    those lines get their own concepts. (BankOwnedLifeInsuranceIncome, EquipmentExpense and the
    FDIC premium still map to the totals; they are outside this issue.)
    """
    frame = _frame("aubn/10k_2023", "income_statement")
    period = "2023-12-31 (FY)"
    expense = frame[frame["standard_concept"] == "NonInterestExpense"]
    assert list(expense.loc[expense["concept"] == "us-gaap_NoninterestExpense", period]) == [22_594_000]
    other_expense = frame[frame["standard_concept"] == "OtherNonInterestExpense"]
    assert list(other_expense["concept"]) == ["us-gaap_OtherNoninterestExpense"]
    assert list(other_expense[period]) == [5_609_000]
    income_rows = set(frame.loc[frame["standard_concept"] == "NonInterestIncome", "concept"])
    assert "us-gaap_NoninterestIncome" in income_rows
    assert "us-gaap_NoninterestIncomeOther" not in income_rows
    other_income = frame[frame["standard_concept"] == "OtherNonInterestIncome"]
    assert list(other_income["concept"]) == ["us-gaap_NoninterestIncomeOther"]
    assert list(other_income[period]) == [1_870_000]

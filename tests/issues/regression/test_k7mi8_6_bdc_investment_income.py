"""
Regression test: a BDC's net investment income was standardized as Revenue and
its total expenses as nonoperating income (sibling of GH #1842)

An investment company's statement of operations runs total investment income
(``us-gaap:GrossInvestmentIncomeOperating``), less expenses
(``us-gaap:InvestmentIncomeInvestmentExpense``), equals net investment income
(``us-gaap:NetInvestmentIncome``). gaap_mappings.json mapped the last to
``Revenue`` and the expenses to ``NonoperatingIncomeExpense``, and (after #1842
removed a wrong mapping) the top line to nothing, so a BDC's "Revenue" row was
its net investment income and ``Financials.get_revenue()`` returned None.

Now: GrossInvestmentIncomeOperating -> ``Revenue`` (a member of the closed
Revenue total in place of NetInvestmentIncome), InvestmentIncomeInvestmentExpense
-> new ``InvestmentExpenses``, NetInvestmentIncome -> new ``NetInvestmentIncome``.
``get_revenue()`` reads GrossInvestmentIncomeOperating after the 'Revenue'
concepts, so an insurer, which files Revenues, is unchanged.

Ground truth (read from the filings):
- Golub Capital BDC 10-Q, quarter ended 2025-03-31, accession 0001476765-25-000040
  (tracked fixture): total investment income $213,892,000, total expenses
  $115,230,000, net investment income before tax $98,662,000.
- Main Street Capital FY2025 10-K, accession 0001396440-26-000016: total
  investment income $566,391,000, total expenses $199,650,000, net investment
  income before taxes $366,741,000.
- Travelers FY2025 10-K, accession 0000086312-26-000065: net investment income
  $3,959M inside total revenues of $48,828M.

Bead: edgartools-k7mi8.6
GitHub Issue: https://github.com/dgunning/edgartools/issues/1842
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from edgar.entity.mappings_loader import get_primary_statement, load_virtual_trees
from edgar.financials import Financials
from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import get_reverse_index

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
GBDC = FIXTURES / "xbrl" / "gbdc"
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))
TOTALS = json.loads((_STANDARDIZATION / "total_membership.json").read_text(encoding="utf-8"))["totals"]

# element -> (standard concept, display name)
ELEMENTS = {
    "GrossInvestmentIncomeOperating": ("Revenue", "Revenue"),
    "InvestmentIncomeInvestmentExpense": ("InvestmentExpenses", "Investment Expenses"),
    "NetInvestmentIncome": ("NetInvestmentIncome", "Net Investment Income"),
}


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


def _face_rows(statement) -> pd.DataFrame:
    df = statement.to_dataframe(standard=True, presentation=False)
    return df[~df["dimension"].astype(bool)]


def _one(df: pd.DataFrame, concept: str) -> pd.Series:
    rows = df[df["concept"] == concept]
    assert len(rows) == 1, concept
    return rows.iloc[0]


# ---------------------------------------------------------------------------
# Lookups and entry shape (offline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("element", sorted(ELEMENTS))
@pytest.mark.parametrize("context", [None, {"statement_type": "IncomeStatement", "section": "Revenue"},
                                     {"statement_type": "IncomeStatement", "section": "Non-Operating Items"}])
def test_each_element_maps_to_its_concept(index, element, context):
    concept, display_name = ELEMENTS[element]
    result = index.lookup(f"us-gaap:{element}")
    assert result.standard_concepts == [concept]
    assert result.primary_display_name == display_name
    assert index.get_standard_concept(f"us-gaap:{element}", context=context) == concept


@pytest.mark.parametrize("element", sorted(ELEMENTS))
def test_entry_shape_follows_the_hand_added_convention(element):
    entry = GAAP_MAPPINGS[element]
    assert entry["confidence"] == 0.9
    assert entry["statement"] == "IncomeStatement"
    assert entry["is_total"] is True
    assert entry["comment"]
    # No generator statistics carried over from the wrong mapping
    assert not {"occurrence_rate", "temporal_consistency", "years_present"} & set(entry)


def test_revenue_total_takes_total_investment_income_not_net():
    assert "GrossInvestmentIncomeOperating" in TOTALS["Revenue"]
    assert "NetInvestmentIncome" not in TOTALS["Revenue"]


def test_no_investment_company_line_is_nonoperating(index):
    """The #1842 defect stays fixed: nothing on a BDC's operations statement reads as nonoperating."""
    for element in ELEMENTS:
        assert index.get_standard_concept(f"us-gaap:{element}") != "NonoperatingIncomeExpense"


# ---------------------------------------------------------------------------
# Golub Capital BDC 10-Q (tracked fixture, offline)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def gbdc():
    return XBRL.from_directory(GBDC)


def test_gbdc_statement_of_operations(gbdc):
    df = _face_rows(gbdc.statements.income_statement())
    income = _one(df, "us-gaap_GrossInvestmentIncomeOperating")
    expenses = _one(df, "us-gaap_InvestmentIncomeInvestmentExpense")
    net = _one(df, "us-gaap_NetInvestmentIncome")
    assert (income["standard_concept"], income["2025-03-31 (Q2)"]) == ("Revenue", 213_892_000)
    assert (expenses["standard_concept"], expenses["2025-03-31 (Q2)"]) == ("InvestmentExpenses", 115_230_000)
    assert (net["standard_concept"], net["2025-03-31 (Q2)"]) == ("NetInvestmentIncome", 98_662_000)
    assert 213_892_000 - 115_230_000 == 98_662_000
    # One Revenue row, and it is the top line
    assert list(df.loc[df["standard_concept"] == "Revenue", "concept"]) == ["us-gaap_GrossInvestmentIncomeOperating"]


def test_gbdc_income_by_portfolio_category_takes_no_concept(gbdc):
    df = gbdc.statements.income_statement().to_dataframe(standard=True, presentation=False)
    by_category = df[df["dimension"].astype(bool) & (df["concept"] == "us-gaap_GrossInvestmentIncomeOperating")]
    assert len(by_category) == 3
    assert by_category["standard_concept"].isna().all()


def test_gbdc_get_revenue_is_total_investment_income(gbdc):
    financials = Financials(gbdc)
    assert financials.get_revenue() == 213_892_000      # was None
    assert financials.get_revenue(1) == 164_230_000     # quarter ended 2024-03-31


# ---------------------------------------------------------------------------
# EntityFacts (offline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("element", sorted(ELEMENTS))
def test_entity_facts_gives_each_element_the_income_statement(element):
    assert get_primary_statement(element) == "IncomeStatement"


@pytest.mark.parametrize("element", ["GrossInvestmentIncomeOperating", "InvestmentIncomeInvestmentExpense"])
def test_entity_facts_tree_shows_the_lines_only_for_a_filer_that_reports_them(element):
    nodes = load_virtual_trees()["IncomeStatement"]["nodes"]
    assert nodes[element]["parent"] == "IncomeStatementAbstract"
    assert element in nodes["IncomeStatementAbstract"]["children"]
    assert nodes[element]["occurrence_rate"] < 0.3


# ---------------------------------------------------------------------------
# Filed statements (network, cassettes)
# ---------------------------------------------------------------------------

def _xbrl(tmp_path, folder, names):
    for name in names:
        (tmp_path / name).write_text(download_file(folder + name), encoding="utf-8")
    return XBRL.from_directory(tmp_path)


MAIN_FOLDER = "https://www.sec.gov/Archives/edgar/data/1396440/000139644026000016/"
MAIN_FILES = ("main-20251231.xsd", "main-20251231_pre.xml", "main-20251231_lab.xml", "main-20251231_cal.xml",
              "main-20251231_def.xml", "main-20251231_htm.xml")
TRV_FOLDER = "https://www.sec.gov/Archives/edgar/data/86312/000008631226000065/"
TRV_FILES = ("trv-20251231.xsd", "trv-20251231_pre.xml", "trv-20251231_lab.xml", "trv-20251231_cal.xml",
             "trv-20251231_def.xml", "trv-20251231_htm.xml")


@pytest.mark.network
@pytest.mark.vcr
def test_main_street_revenue_is_total_investment_income(tmp_path):
    """Main Street Capital FY2025 10-K, 0001396440-26-000016."""
    xbrl = _xbrl(tmp_path, MAIN_FOLDER, MAIN_FILES)
    df = _face_rows(xbrl.statements.income_statement())
    year = "2025-12-31 (FY)"
    assert _one(df, "us-gaap_GrossInvestmentIncomeOperating")[["standard_concept", year]].tolist() == [
        "Revenue", 566_391_000]
    assert _one(df, "us-gaap_InvestmentIncomeInvestmentExpense")[["standard_concept", year]].tolist() == [
        "InvestmentExpenses", 199_650_000]   # was NonoperatingIncomeExpense
    assert _one(df, "us-gaap_NetInvestmentIncome")[["standard_concept", year]].tolist() == [
        "NetInvestmentIncome", 366_741_000]  # was Revenue
    assert Financials(xbrl).get_revenue() == 566_391_000  # was None


@pytest.mark.network
@pytest.mark.vcr
def test_travelers_revenue_is_unchanged(tmp_path):
    """Travelers FY2025 10-K, 0000086312-26-000065: an insurer's net investment income is one
    line inside revenues; it leaves the Revenue concept and total revenue does not move."""
    xbrl = _xbrl(tmp_path, TRV_FOLDER, TRV_FILES)
    df = _face_rows(xbrl.statements.income_statement())
    year = "2025-12-31 (FY)"
    assert _one(df, "us-gaap_NetInvestmentIncome")[["standard_concept", year]].tolist() == [
        "NetInvestmentIncome", 3_959_000_000]
    assert _one(df, "us-gaap_Revenues")[year] == 48_828_000_000
    assert "us-gaap_NetInvestmentIncome" not in set(df.loc[df["standard_concept"] == "Revenue", "concept"])
    assert Financials(xbrl).get_revenue() == 48_828_000_000

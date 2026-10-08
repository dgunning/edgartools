"""
Amortization, impairment, labor, revenue and operating items were stored as a
concept they are not: goodwill impairment, cost of revenue, restructuring or
non-operating income. ``lookup()`` then labeled the row with that concept, so
JPMorgan Chase's FY2023 compensation expense, $46,465 million, came back as
cost of revenue.

These are the 59 rows of the #1417 follow-up, the three reported tags among
them. A null row is a deleted entry: no concept fits, so ``lookup()`` returns
``None``.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1417
"""

import json
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import get_reverse_index

EXPECTED = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "standardization" / "issue_1417_same_defect_mappings_expected.json").read_text(encoding="utf-8")
)
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))

# These 21 rows repeated the old concept in every industry override.
HAD_OVERRIDES = [
    "AdjustmentForAmortization",
    "DeconsolidationGainOrLossAmount",
    "EmployeeBenefitsAndShareBasedCompensation",
    "GainLossOnDispositionOfAssets1",
    "GoodwillAndIntangibleAssetImpairment",
    "ImpairmentLossRecognisedInProfitOrLoss",
    "ImpairmentOfIntangibleAssetsExcludingGoodwill",
    "ImpairmentOfOilAndGasProperties",
    "ImpairmentOfRealEstate",
    "InventoryWriteDown",
    "LaborAndRelatedExpense",
    "NetPeriodicDefinedBenefitsExpenseReversalOfExpenseExcludingServiceCostComponent",
    "OtherAssetImpairmentCharges",
    "OtherCostAndExpenseOperating",
    "OtherExpenses",
    "OtherGeneralExpense",
    "OtherNonrecurringIncomeExpense",
    "OtherOperatingIncome",
    "RevenueNotFromContractWithCustomer",
    "RevenueNotFromContractWithCustomerOther",
    "TangibleAssetImpairmentCharges",
]


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


def _members(index, concept):
    return {tag for tag, entry in index._index.items() if isinstance(entry, dict) and concept in entry.get("standard_tags", [])}


@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_corrected_entries(index, tag):
    expected = EXPECTED[tag]
    result = index.lookup(tag)
    if expected is None:
        assert result is None
        assert tag not in index._gaap_mappings
    else:
        assert result is not None and result.standard_concepts == expected


@pytest.mark.parametrize("tag", HAD_OVERRIDES)
@pytest.mark.parametrize("industry", ["Banks", "BusSv", "Drugs", "Fin", "Insur", "Trans", "Hlth", "RlEst", "Oil"])
def test_no_industry_brings_the_old_concept_back(index, tag, industry):
    """The old answer was repeated in every industry override."""
    plain = index.lookup(tag)
    with_industry = index.lookup(tag, industry=industry)
    if plain is None:
        assert with_industry is None
    else:
        assert with_industry is not None
        assert with_industry.standard_concepts == plain.standard_concepts


def test_no_corrected_entry_keeps_an_industry_override():
    """The guard above samples nine industries; an override left in any other would hide there."""
    assert [tag for tag in EXPECTED if "industry_overrides" in GAAP_MAPPINGS.get(tag, {})] == []


def test_single_candidate_display_name_matches_the_catalog():
    """A stale display_name would still pass the concept check above."""
    for tag, concepts in EXPECTED.items():
        if not concepts or len(concepts) != 1:
            continue
        assert GAAP_MAPPINGS[tag]["display_name"] == DISPLAY_NAMES[concepts[0]], tag


@pytest.mark.parametrize(
    "tag, concept, display",
    [
        ("CostOfGoodsAndServicesSoldAmortization", "AmortizationOfIntangibles", "Amortization of Intangibles"),
        ("LaborAndRelatedExpense", "LaborExpenses", "Labor and Employee Benefits"),
        ("RevenueNotFromContractWithCustomer", "Revenue", "Revenue"),
        ("RevenueNotFromContractWithCustomerOther", "Revenue", "Revenue"),
        ("AdjustmentForAmortization", "DepreciationAmortizationCF", "Depreciation & Amortization (CF)"),
        ("GoodwillImpairmentLoss", "GoodwillWriteoffs", "Goodwill Impairment"),
        ("GoodwillAndIntangibleAssetImpairment", "AssetImpairmentChargesIS", "Asset Impairment Charges"),
        ("ImpairmentOfIntangibleAssetsFinitelived", "AssetImpairmentChargesIS", "Asset Impairment Charges"),
        ("ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill", "AssetImpairmentChargesIS", "Asset Impairment Charges"),
        ("EmployeeBenefitsAndShareBasedCompensation", "LaborExpenses", "Labor and Employee Benefits"),
        ("OtherOperatingIncome", "Revenue", "Revenue"),
    ],
)
def test_concept_follows_the_element_definition(index, tag, concept, display):
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == [concept]
    assert result.display_names == [display]


def test_goodwill_impairment_holds_only_goodwill(index):
    """None of the eight former members was the goodwill impairment element itself."""
    assert _members(index, "GoodwillWriteoffs") == {"GoodwillImpairmentLoss"}


def test_amortization_of_intangibles_holds_no_impairment(index):
    """Three intangible-asset impairment elements used to sit here."""
    assert _members(index, "AmortizationOfIntangibles") == {
        "AmortisationExpense",
        "AmortizationOfIntangibleAssets",
        "CostOfGoodsAndServicesSoldAmortization",
        "ifrs-full_AmortisationExpense",
    }


def test_jpmorgan_compensation_expense_is_labor_not_cost_of_revenue():
    """JPMorgan Chase FY2023 10-K, 0000019617-24-000225: a bank has no cost of revenue."""
    fixture = Path(__file__).parents[2] / "fixtures" / "xbrl" / "jpm" / "10k_2024"
    statement = XBRL.from_directory(fixture).statements["IncomeStatement"]
    assert statement is not None
    frame = statement.render(standard=True).to_dataframe()
    compensation = frame[frame["concept"] == "us-gaap_LaborAndRelatedExpense"]
    assert len(compensation) == 1
    assert compensation["2023-12-31"].iloc[0] == 46_465_000_000
    assert compensation["standard_concept"].iloc[0] == "LaborExpenses"
    assert int((frame["standard_concept"] == "CostOfGoodsAndServicesSold").sum()) == 0

"""
Discontinued-operations elements were stored as "Extraordinary Items", a
category US GAAP eliminated in 2015 (ASU 2015-01). ``lookup()`` then labeled
discontinued-operations results, the tax on them and a disposal group's own
revenue as extraordinary items: IBM's FY2024 segment revenue reconciliation
showed $35 million of revenue from divested businesses that way.

This slice is the 28 rows of #1437. A null row is a deleted entry: no concept
fits, so ``lookup()`` returns ``None``. Later slices append rows to
``issue_1417_expected.json``.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1437
GitHub Issue: https://github.com/dgunning/edgartools/issues/1417
"""

import json
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import get_reverse_index

EXPECTED = json.loads((Path(__file__).parents[2] / "fixtures" / "standardization" / "issue_1417_expected.json").read_text(encoding="utf-8"))
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))

# These 4 rows repeated the old concept in every industry override.
HAD_OVERRIDES = [
    "DiscontinuedOperationGainLossOnDisposalOfDiscontinuedOperationNetOfTax",
    "DiscontinuedOperationTaxEffectOfDiscontinuedOperation",
    "DiscontinuedOperationTaxEffectOfIncomeLossFromDisposalOfDiscontinuedOperation",
    "IncomeLossFromDiscontinuedOperationsNetOfTaxAttributableToNoncontrollingInterest",
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
        (
            "DiscontinuedOperationGainLossOnDisposalOfDiscontinuedOperationNetOfTax",
            "DiscontinuedOperationsIncome",
            "Income from Discontinued Operations",
        ),
        (
            "DiscontinuedOperationIncomeLossFromDiscontinuedOperationBeforeIncomeTax",
            "DiscontinuedOperationsIncome",
            "Income from Discontinued Operations",
        ),
        (
            "DiscontinuedOperationIncomeLossFromDiscontinuedOperationDuringPhaseOutPeriodNetOfTax",
            "DiscontinuedOperationsIncome",
            "Income from Discontinued Operations",
        ),
        (
            "DiscontinuedOperationGainLossFromDisposalOfDiscontinuedOperationBeforeIncomeTax",
            "DiscontinuedOperationsIncome",
            "Income from Discontinued Operations",
        ),
        (
            "IncomeLossFromDiscontinuedOperationsNetOfTaxAttributableToNoncontrollingInterest",
            "MinorityInterestIncomeExpense",
            "Net Income Attributable to Noncontrolling Interest",
        ),
    ],
)
def test_concept_follows_the_element_definition(index, tag, concept, display):
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == [concept]
    assert result.display_names == [display]


def test_extraordinary_items_holds_only_extraordinary_items(index):
    """Twenty-seven discontinued-operations elements and a pre-2015 subtotal used to sit here."""
    assert _members(index, "ExtraordinaryItemsIncomeExpense(PostTax)") == {
        "ExtraordinaryItemGainOrLossNetOfTaxAttributableToNoncontrollingInterest",
        "ExtraordinaryItemGainOrLossNetOfTaxAttributableToReportingEntity",
        "ExtraordinaryItemNetOfTax",
        "ExtraordinaryItemsGross",
        "TaxEffectOfExtraordinaryItem",
    }


@pytest.fixture(scope="module")
def ibm_fy2024():
    return XBRL.from_directory(Path(__file__).parents[2] / "fixtures" / "xbrl" / "ibm" / "10k_2024")


@pytest.mark.parametrize(
    "role, concept, value_2024",
    [
        ("http://www.ibm.com/role/SegmentsRevenueReconciliationDetails", "us-gaap_DisposalGroupIncludingDiscontinuedOperationRevenue", 35_000_000),
        (
            "http://www.ibm.com/role/TaxesProvisionbyTaxingJurisdictionDetails",
            "us-gaap_DiscontinuedOperationTaxEffectOfDiscontinuedOperation",
            6_000_000,
        ),
    ],
)
def test_ibm_divested_revenue_and_discontinued_tax_are_not_extraordinary_items(ibm_fy2024, role, concept, value_2024):
    """IBM FY2024 10-K, 0000051143-25-000015: "Other—divested businesses" revenue and the tax on discontinued operations."""
    statement = ibm_fy2024.statements[role]
    assert statement is not None
    frame = statement.render(standard=True).to_dataframe()
    rows = frame[(frame["concept"] == concept) & ~frame["dimension"]]
    assert len(rows) == 1
    assert rows["2024-12-31"].iloc[0] == value_2024
    assert rows["standard_concept"].isna().all()
    assert int((frame["standard_concept"] == "ExtraordinaryItemsIncomeExpense(PostTax)").sum()) == 0

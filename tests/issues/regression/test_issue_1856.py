"""
Gross property and equipment, its accumulated depreciation and the net carrying amount all
standardized as ``PlantPropertyEquipmentNet`` when a filer used the property-plus-finance-lease
(or excluding-lessor-asset, or owned) elements, so a balance sheet showed three "Property, Plant
and Equipment" rows of which only one was net PP&E.

The PP&E family now follows the elements' definitions, like ``PropertyPlantAndEquipmentGross``
and ``AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment`` already did:

- accumulated depreciation of all PP&E (plus finance-lease ROU assets, excluding lessor assets,
  or owned) -> ``AccumulatedDepreciation``
- gross PP&E of the same scope ("before accumulated depreciation") -> ``GrossPropertyPlantEquipment``
- parts with no fitting concept (finance-lease ROU assets alone before amortization, the
  accumulated depreciation of "other" PP&E) -> no standard concept
- the net ``...AfterAccumulatedDepreciationAndAmortization`` element keeps ``PlantPropertyEquipmentNet``

Ground truth, both from fixtures captured from the filings:

- American Airlines Group FY2025 10-K, accession 0000006201-26-000014, consolidated balance
  sheet at 2025-12-31: total property and equipment, at cost $57,732M; less accumulated
  depreciation and amortization $(25,192)M; total property and equipment, net $32,540M.
- Coca-Cola FY2023 10-K, accession 0000021344-24-000009, property, plant and equipment note at
  2023-12-31: cost $18,469M, accumulated depreciation $9,233M, net $9,236M.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1856
"""

import json
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import ReverseIndex

FIXTURES = Path(__file__).parents[2] / "fixtures" / "xbrl"
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))

EXPECTED = {
    "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAccumulatedDepreciationAndAmortization": "AccumulatedDepreciation",
    "PropertyPlantAndEquipmentExcludingLessorAssetUnderOperatingLeaseAccumulatedDepreciation": "AccumulatedDepreciation",
    "PropertyPlantAndEquipmentOwnedAccumulatedDepreciation": "AccumulatedDepreciation",
    "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetBeforeAccumulatedDepreciationAndAmortization": "GrossPropertyPlantEquipment",
    "PropertyPlantAndEquipmentExcludingLessorAssetUnderOperatingLeaseBeforeAccumulatedDepreciation": "GrossPropertyPlantEquipment",
    "FinanceLeaseRightOfUseAssetBeforeAccumulatedAmortization": None,
    "PropertyPlantAndEquipmentOtherAccumulatedDepreciation": None,
    # Unchanged: the net elements and the existing gross/accumulated elements.
    "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization": "PlantPropertyEquipmentNet",
    "PropertyPlantAndEquipmentExcludingLessorAssetUnderOperatingLeaseAfterAccumulatedDepreciation": "PlantPropertyEquipmentNet",
    "PropertyPlantAndEquipmentNet": "PlantPropertyEquipmentNet",
    "PropertyPlantAndEquipmentGross": "GrossPropertyPlantEquipment",
    "AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment": "AccumulatedDepreciation",
}
DISPLAY = {
    "AccumulatedDepreciation": "Accumulated Depreciation",
    "GrossPropertyPlantEquipment": "Property, Plant & Equipment, Gross",
    "PlantPropertyEquipmentNet": "Property, Plant and Equipment",
}


@pytest.fixture(scope="module")
def index():
    return ReverseIndex()


@pytest.mark.fast
@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_ppe_family_follows_the_element_definition(index, tag):
    concept = EXPECTED[tag]
    for spelling in (tag, f"us-gaap:{tag}", f"us-gaap_{tag}"):
        result = index.lookup(spelling)
        if concept is None:
            assert tag not in GAAP_MAPPINGS
            assert result is None, spelling
        else:
            assert result is not None, spelling
            assert result.standard_concepts == [concept], spelling
            assert result.display_names == [DISPLAY[concept]], spelling


@pytest.mark.fast
@pytest.mark.parametrize("tag", sorted(t for t, c in EXPECTED.items() if c))
def test_retargeted_entry_display_name_matches_its_concept(tag):
    entry = GAAP_MAPPINGS[tag]
    assert entry["display_name"] == DISPLAY[EXPECTED[tag]]
    assert entry["statement"] == "BalanceSheet"
    assert "industry_overrides" not in entry


def _rows(directory, role_suffix):
    xbrl = XBRL.from_directory(FIXTURES / directory)
    role = next(s["role"] for s in xbrl.get_all_statements() if s["role"].endswith(role_suffix))
    frame = xbrl.statements[role].render(standard=True).to_dataframe()
    return frame[~frame["dimension"]]


def _by_concept(frame, column, prefix):
    ppe = frame[frame["concept"].str.startswith(prefix)]
    return {row["concept"]: (row["standard_concept"], row[column]) for _, row in ppe.iterrows()}


@pytest.mark.fast
def test_american_airlines_balance_sheet_has_one_net_ppe_row():
    """AAL FY2025 10-K, 0000006201-26-000014, balance sheet at 2025-12-31 ($M)."""
    frame = _rows("aal/10k_2025", "/ConsolidatedBalanceSheetsAmericanAirlinesGroupInc")
    stem = "us-gaap_PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAsset"
    assert _by_concept(frame, "2025-12-31", stem) == {
        f"{stem}BeforeAccumulatedDepreciationAndAmortization": ("GrossPropertyPlantEquipment", 57_732_000_000),
        f"{stem}AccumulatedDepreciationAndAmortization": ("AccumulatedDepreciation", -25_192_000_000),
        f"{stem}AfterAccumulatedDepreciationAndAmortization": ("PlantPropertyEquipmentNet", 32_540_000_000),
    }


@pytest.mark.fast
def test_coca_cola_owned_accumulated_depreciation_is_not_net_ppe():
    """KO FY2023 10-K, 0000021344-24-000009, PP&E note at 2023-12-31 ($M)."""
    frame = _rows("ko/10k_2024", "/BUSINESSANDSUMMARYOFSIGNIFICANTACCOUNTINGPOLICIESPROPERTYPLANTEQUIPMENTDetails")
    assert _by_concept(frame, "2023-12-31", "us-gaap_PropertyPlantAndEquipment") == {
        "us-gaap_PropertyPlantAndEquipmentGross": ("GrossPropertyPlantEquipment", 18_469_000_000),
        "us-gaap_PropertyPlantAndEquipmentOwnedAccumulatedDepreciation": ("AccumulatedDepreciation", 9_233_000_000),
        "us-gaap_PropertyPlantAndEquipmentNet": ("PlantPropertyEquipmentNet", 9_236_000_000),
    }

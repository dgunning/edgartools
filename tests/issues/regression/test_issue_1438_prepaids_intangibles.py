"""
Prepaid expenses, intangible assets and other disclosures were assigned
incorrect standard concepts. Corrected entries retain their filed labels and
values; entries without a fitting concept return no reverse-index mapping.
Coca-Cola's FY2023 trademarks and goodwill provide a filing regression.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1438
GitHub Issue: https://github.com/dgunning/edgartools/issues/1417
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
    (Path(__file__).parents[2] / "fixtures" / "standardization" / "issue_1438_prepaids_intangibles_expected.json").read_text(encoding="utf-8")
)
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))

# Pin the deletion decision independently of the expected-mapping fixture.
DELETED_TAGS = {
    "CustomerAdvancesAndProgressPaymentsForLongTermContractsOrPrograms",
    "DerivativeAssetsLiabilitiesAtFairValueNet",
    "EquitySecuritiesWithoutReadilyDeterminableFairValueUpwardPriceAdjustmentCumulativeAmount",
    "VariableInterestEntityConsolidatedCarryingAmountAssets",
}

INDUSTRIES = sorted({code for _, _, code in _FF48_SIC_RANGES})
STATEMENT_TYPES = [
    "BalanceSheet",
    "IncomeStatement",
    "CashFlowStatement",
    "http://example.com/role/BalanceSheet",
    "http://example.com/role/FinancialStatement",
    "",
]
SECTIONS = [
    None,
    "Current Assets",
    "Non-Current Assets",
    "Noncurrent Assets",
    "Non-current Assets",
    "Current Liabilities",
    "Non-Current Liabilities",
    "Noncurrent Liabilities",
    "Non-current Liabilities",
]
DERIVATIVE_SPELLINGS = [
    "DerivativeAssetsLiabilitiesAtFairValueNet",
    "us-gaap_DerivativeAssetsLiabilitiesAtFairValueNet",
    "us-gaap:DerivativeAssetsLiabilitiesAtFairValueNet",
]
BALANCE_SHEET_TYPES = ["BalanceSheet", "http://example.com/role/BalanceSheet", ""]


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


def _members(index, concept):
    return {tag for tag, entry in index._index.items() if isinstance(entry, dict) and concept in entry.get("standard_tags", [])}


@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_corrected_entries(index, tag):
    expected = EXPECTED[tag]
    if expected is None:
        assert tag not in GAAP_MAPPINGS
    else:
        assert GAAP_MAPPINGS[tag]["standard_tags"] == expected
    result = index.lookup(tag)
    if expected is None:
        assert result is None
        assert tag not in index._gaap_mappings
    else:
        assert result is not None and result.standard_concepts == expected
        assert result.display_names == [DISPLAY_NAMES[concept] for concept in expected]
        assert result.is_ambiguous is False


@pytest.mark.parametrize("tag", sorted(EXPECTED))
@pytest.mark.parametrize("industry", INDUSTRIES)
def test_no_industry_brings_the_old_concept_back(index, tag, industry):
    """Every industry uses the expected mapping, including the deletions."""
    expected = EXPECTED[tag]
    with_industry = index.lookup(tag, industry=industry)
    if expected is None:
        assert with_industry is None
    else:
        assert with_industry is not None
        assert with_industry.standard_concepts == expected
        assert with_industry.display_names == [DISPLAY_NAMES[concept] for concept in expected]
        assert with_industry.is_ambiguous is False
    assert with_industry == index.lookup(tag)


def test_no_corrected_entry_keeps_an_industry_override():
    """No corrected entry should retain a stale industry override."""
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
        ("PrepaidRent", "PrepaidExpenses", "Prepaid Expenses"),
        ("PrepaidInterest", "PrepaidExpenses", "Prepaid Expenses"),
        ("PrepaidRoyalties", "PrepaidExpenses", "Prepaid Expenses"),
        ("OtherPrepaidExpenseCurrent", "PrepaidExpenses", "Prepaid Expenses"),
        ("IndefiniteLivedTrademarks", "IntangibleAssets", "Intangible Assets"),
        ("IndefiniteLivedFranchiseRights", "IntangibleAssets", "Intangible Assets"),
        ("FiniteLivedCustomerRelationshipsGross", "IntangibleAssetsGross", "Intangible Assets, Gross"),
        ("FiniteLivedTradeNamesGross", "IntangibleAssetsGross", "Intangible Assets, Gross"),
        ("IntangibleAssetsCurrent", "OtherOperatingCurrentAssets", "Other Current Assets"),
        ("PropertySubjectToOrAvailableForOperatingLeaseNet", "PlantPropertyEquipmentNet", "Property, Plant and Equipment"),
        ("PropertySubjectToOrAvailableForOperatingLeaseAccumulatedDepreciation", "AccumulatedDepreciation", "Accumulated Depreciation"),
        ("LandAvailableForDevelopment", "RealEstateInvestments", "Real Estate Investments"),
    ],
)
def test_concept_follows_the_element_definition(index, tag, concept, display):
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == [concept]
    assert result.display_names == [display]


@pytest.mark.parametrize("tag", sorted(DELETED_TAGS))
def test_elements_with_no_fitting_concept_return_none(index, tag):
    """Net derivative fair value and the other deleted disclosures have no fitting concept."""
    assert tag not in GAAP_MAPPINGS
    assert index.lookup(tag) is None


def test_indefinite_lived_intangibles_are_not_goodwill(index):
    """The corrected indefinite-lived assets no longer belong to Goodwill."""
    goodwill = _members(index, "Goodwill")
    assert not {tag for tag in goodwill if tag.startswith(("IndefiniteLived", "OtherIndefiniteLived"))}
    assert {
        "IndefiniteLivedContractualRights",
        "IndefiniteLivedFranchiseRights",
        "IndefiniteLivedLicenseAgreements",
        "IndefiniteLivedTradeNames",
        "IndefiniteLivedTrademarks",
        "OtherIndefiniteLivedIntangibleAssets",
    } <= _members(index, "IntangibleAssets")


@pytest.fixture(scope="module")
def ko_fy2023():
    return XBRL.from_directory(Path(__file__).parents[2] / "fixtures" / "xbrl" / "ko" / "10k_2024")


def test_coca_cola_trademarks_are_not_goodwill(ko_fy2023):
    """Coca-Cola FY2023 10-K, 0000021344-24-000009: trademarks $14,349M beside goodwill $18,358M at Dec 31, 2023."""
    frame = ko_fy2023.statements["BalanceSheet"].render(standard=True).to_dataframe()
    frame = frame[~frame["dimension"]]
    trademarks = frame[frame["concept"] == "us-gaap_IndefiniteLivedTrademarks"]
    assert len(trademarks) == 1
    assert trademarks["2023-12-31"].iloc[0] == 14_349_000_000
    assert trademarks["standard_concept"].iloc[0] == "IntangibleAssets"
    goodwill = frame[frame["standard_concept"] == "Goodwill"]
    assert list(goodwill["concept"]) == ["us-gaap_Goodwill"]
    assert goodwill["2023-12-31"].iloc[0] == 18_358_000_000


@pytest.fixture(scope="module")
def mapper():
    return ConceptMapper(MappingStore(read_only=True))


def test_expected_entries_and_industry_domain_are_complete():
    assert len(EXPECTED) == 33
    assert {tag for tag, concepts in EXPECTED.items() if concepts is None} == DELETED_TAGS
    assert sum(concepts is not None for concepts in EXPECTED.values()) == 29
    assert len(INDUSTRIES) == 48
    assert set(EXPECTED).isdisjoint(EXCLUDED_TAGS)


@pytest.mark.parametrize("tag", sorted(tag for tag, concepts in EXPECTED.items() if concepts))
def test_corrected_entry_metadata_matches_its_concept(tag):
    concepts = EXPECTED[tag]
    assert concepts is not None and len(concepts) == 1
    entry = GAAP_MAPPINGS[tag]
    statement = get_statement_for_concept(concepts[0])
    assert entry["display_name"] == DISPLAY_NAMES[concepts[0]]
    assert entry["statement"] == statement
    assert entry["section"] == get_section_for_concept(concepts[0], statement)
    assert entry["is_total"] is False
    assert entry["confidence"] == 0.9
    assert "ambiguous" not in entry


@pytest.mark.parametrize("tag", sorted(EXPECTED))
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
@pytest.mark.parametrize("section", SECTIONS)
def test_public_context_paths_keep_the_corrected_concept(index, tag, statement_type, section):
    context = {"statement_type": statement_type, "section": section}
    expected = EXPECTED[tag]
    concept = index.get_standard_concept(tag, context)
    display = index.get_display_name(tag, context)
    if expected is None:
        assert concept is None
        assert display is None
    else:
        assert concept == expected[0]
        assert display == DISPLAY_NAMES[expected[0]]
        result = index.lookup(tag)
        assert result is not None
        assert result.is_ambiguous is False


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
    assert "standard_concept" not in item
    assert {key: value for key, value in result[0].items() if key != "standard_concept"} == item
    expected = EXPECTED[tag]
    if expected is None:
        assert "standard_concept" not in result[0]
    else:
        assert result[0]["standard_concept"] == expected[0]


@pytest.mark.parametrize("concept", DERIVATIVE_SPELLINGS)
@pytest.mark.parametrize("statement_type", BALANCE_SHEET_TYPES)
@pytest.mark.parametrize("section", SECTIONS)
def test_net_derivative_has_no_mapping_in_asset_or_liability_sections(index, concept, statement_type, section):
    """A net fair-value disclosure is neither an investment nor debt in these contexts."""
    context = {"statement_type": statement_type, "section": section}
    assert index.lookup(concept) is None
    assert index.get_standard_concept(concept, context) is None
    assert index.get_display_name(concept, context) is None


@pytest.mark.parametrize("concept", DERIVATIVE_SPELLINGS)
@pytest.mark.parametrize("statement_type", BALANCE_SHEET_TYPES)
@pytest.mark.parametrize("amount", [-123_456, 123_456])
@pytest.mark.parametrize("calculation_parent", [None, "AssetsCurrent", "AssetsNoncurrent", "LiabilitiesCurrent", "LiabilitiesNoncurrent"])
def test_net_derivative_statement_preserves_the_filed_disclosure(mapper, concept, statement_type, amount, calculation_parent):
    """Standardization keeps net derivative values without an investment or debt concept."""
    item = {
        "concept": concept,
        "label": "Filed net derivative fair value",
        "values": {"2023-12-31": amount},
        "statement_type": statement_type,
    }
    if calculation_parent is not None:
        item["calculation_parent"] = f"us-gaap_{calculation_parent}"
    result = standardize_statement([item], mapper)
    assert len(result) == 1
    assert "standard_concept" not in item
    assert result[0] == item

"""
Nineteen balance-sheet elements from the maintainer's 2026-10-13 status comment
still held their old mapping: warrant liabilities as warranty provisions,
restricted cash and deferred revenue in "Other", an allowance as accounts
receivable, and two line items (related-party payables, banks' other borrowings)
as "Total Liabilities". Seventeen now take the concepts the issue proposes, the
current and noncurrent sides resolved by section like their ...Current and
...Noncurrent siblings. The warrant liability lists its noncurrent side first:
a row with no section takes the first candidate, and a noncurrent block without
its own subtotal gets no section, which is where FreightCar, BuzzFeed, Token Cat
and MultiSensor AI file theirs.

Two have no standard concept instead. NotesReceivableGross is the gross loan
balance above the allowance: on Synchrony's and Greene County Bancorp's balance
sheets it sits two lines above NotesReceivableNet, which shares its concept, so
the group counted the loans twice. DerivativeLiabilityFairValueGrossAsset is a
debit, the asset side of a netting disclosure, so a liability concept would
reverse its sign, and #1467 removed the net element of the same table.

Before the fix FreightCar America's FY2025 warrant liability ($168,529K) was the
only "Warranty and Other Provisions" row, beside its real accrued warranty.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1438
"""

import json
from pathlib import Path

import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.core import ConceptMapper, MappingStore, standardize_statement
from edgar.xbrl.standardization.reverse_index import get_reverse_index
from edgar.xbrl.standardization.sections import get_section_for_concept
from edgar.xbrl.standardization.sic_industry import _FF48_SIC_RANGES

EXPECTED = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "standardization" / "issue_1438_followup_expected.json").read_text(encoding="utf-8")
)
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))

DELETED_TAGS = {"DerivativeLiabilityFairValueGrossAsset", "NotesReceivableGross"}
MAPPED_TAGS = sorted(tag for tag, concepts in EXPECTED.items() if concepts)
INDUSTRIES = sorted({code for _, _, code in _FF48_SIC_RANGES})
STATEMENT_TYPES = ["BalanceSheet", "http://example.com/role/ConsolidatedBalanceSheets", ""]
SECTIONS = [None, "Current Assets", "Non-Current Assets", "Current Liabilities", "Non-Current Liabilities"]


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


@pytest.fixture(scope="module")
def mapper():
    return ConceptMapper(MappingStore(read_only=True))


def test_expected_file_covers_the_comment():
    assert len(EXPECTED) == 19
    assert {tag for tag, concepts in EXPECTED.items() if concepts is None} == DELETED_TAGS
    assert all(len(EXPECTED[tag]) == 2 for tag in MAPPED_TAGS)
    assert len(INDUSTRIES) == 48


def test_lookups():
    """Each corrected entry, spelled out independently of the expected-mapping fixture."""
    index = get_reverse_index()

    def concepts(tag):
        result = index.lookup(f"us-gaap:{tag}")
        assert result is not None, tag
        assert result.is_ambiguous is True, tag
        return result.standard_concepts

    assert concepts("WarrantsAndRightsOutstanding") == ["OtherNonOperatingNonCurrentLiabilities", "OtherNonOperatingCurrentLiabilities"]
    assert concepts("RestrictedCashAndCashEquivalents") == ["RestrictedCashCurrent", "RestrictedCashNonCurrent"]
    assert concepts("AllowanceForDoubtfulAccountsReceivable") == ["AllowanceForDoubtfulAccounts", "OtherOperatingNonCurrentAssets"]
    assert concepts("DeferredRevenue") == ["DeferredRevenueCurrent", "DeferredRevenueNonCurrent"]
    assert concepts("DueToRelatedPartiesCurrentAndNoncurrent") == ["OtherNonOperatingCurrentLiabilities", "OtherNonOperatingNonCurrentLiabilities"]
    assert concepts("OtherBorrowings") == ["ShortTermDebt", "LongTermDebt"]
    assert concepts("PrepaidExpenseCurrentAndNoncurrent") == ["PrepaidExpenses", "OtherNonOperatingNonCurrentAssets"]
    assert concepts("CustomerFunds") == ["OtherOperatingNonCurrentAssets", "OtherOperatingCurrentAssets"]
    assert concepts("EmployeeRelatedLiabilitiesCurrentAndNoncurrent") == ["AccruedCompensation", "OtherOperatingNonCurrentLiabilities"]
    assert concepts("OtherEmployeeRelatedLiabilitiesCurrentAndNoncurrent") == ["OtherOperatingCurrentLiabilities", "OtherOperatingNonCurrentLiabilities"]
    assert concepts("AccountsReceivableRelatedParties") == ["TradeReceivables", "OtherOperatingNonCurrentAssets"]
    assert concepts("ContractWithCustomerReceivableBeforeAllowanceForCreditLoss") == ["AccountsReceivableGross", "OtherOperatingNonCurrentAssets"]
    assert concepts("SalesAndExciseTaxPayableCurrentAndNoncurrent") == ["TaxesPayable", "OtherOperatingNonCurrentLiabilities"]
    assert concepts("AccruedRoyaltiesCurrentAndNoncurrent") == ["OtherOperatingCurrentLiabilities", "OtherOperatingNonCurrentLiabilities"]
    assert concepts("ConstructionPayableCurrentAndNoncurrent") == ["TradePayables", "OtherOperatingNonCurrentLiabilities"]
    assert concepts("WorkersCompensationLiabilityCurrentAndNoncurrent") == ["SelfInsuranceReserve", "OtherOperatingNonCurrentLiabilities"]
    assert concepts("CostsInExcessOfBillingsOnUncompletedContractsOrPrograms") == ["ContractAssets", "OtherOperatingNonCurrentAssets"]
    for tag in ("NotesReceivableGross", "DerivativeLiabilityFairValueGrossAsset"):
        assert index.lookup(f"us-gaap:{tag}") is None, tag
        assert tag not in GAAP_MAPPINGS, tag
    # Left alone on purpose: #1467 removed it rather than mapping it to LongtermInvestments.
    assert index.lookup("us-gaap:DerivativeAssetsLiabilitiesAtFairValueNet") is None


@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_corrected_entries(index, tag):
    expected = EXPECTED[tag]
    result = index.lookup(tag)
    if expected is None:
        assert result is None
        assert tag not in index._gaap_mappings
    else:
        assert result is not None and result.standard_concepts == expected
        assert result.display_names == [DISPLAY_NAMES[concept] for concept in expected]


@pytest.mark.parametrize("tag", sorted(EXPECTED))
@pytest.mark.parametrize("industry", INDUSTRIES)
def test_no_industry_brings_the_old_concept_back(index, tag, industry):
    assert index.lookup(tag, industry=industry) == index.lookup(tag)


def test_no_corrected_entry_keeps_an_industry_override():
    assert [tag for tag in MAPPED_TAGS if "industry_overrides" in GAAP_MAPPINGS[tag]] == []


@pytest.mark.parametrize("tag", MAPPED_TAGS)
def test_corrected_entry_metadata_matches_its_primary_concept(tag):
    """The stored label, section and total flag describe the first candidate, as #1436's follow-up did."""
    concepts = EXPECTED[tag]
    entry = GAAP_MAPPINGS[tag]
    assert entry["display_name"] == DISPLAY_NAMES[concepts[0]]
    assert entry["statement"] == "BalanceSheet"
    assert entry["section"] == get_section_for_concept(concepts[0], "BalanceSheet")
    assert entry["is_total"] is False
    assert entry["confidence"] == 0.9
    assert entry["ambiguous"] is True


def test_no_line_item_is_total_liabilities_or_a_warranty_provision(index):
    for tag in MAPPED_TAGS:
        concepts = index.lookup(tag).standard_concepts
        assert "Liabilities" not in concepts, tag
        assert "OngoingOperatingProvisions(WarrantiesEtc)" not in concepts, tag
        assert "RetirementRelatedCurrentLiabilities" not in concepts, tag


@pytest.mark.parametrize("tag", MAPPED_TAGS)
@pytest.mark.parametrize("section", ["Current", "Non-Current"])
def test_balance_sheet_sections_pick_the_side(index, tag, section):
    """A ...CurrentAndNoncurrent element takes the candidate of the section it is filed in."""
    concepts = EXPECTED[tag]
    sides = {get_section_for_concept(concept, "BalanceSheet"): concept for concept in concepts}
    kind = "Assets" if any(side.endswith("Assets") for side in sides) else "Liabilities"
    wanted = f"{section} {kind}"
    context = {"statement_type": "BalanceSheet", "section": wanted}
    assert index.get_standard_concept(tag, context) == sides[wanted]
    assert index.get_display_name(tag, context) == DISPLAY_NAMES[sides[wanted]]


@pytest.mark.parametrize("tag", sorted(EXPECTED))
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
@pytest.mark.parametrize("section", SECTIONS)
def test_public_context_paths_keep_the_corrected_concept(index, tag, statement_type, section):
    context = {"statement_type": statement_type, "section": section}
    concept = index.get_standard_concept(tag, context)
    if EXPECTED[tag] is None:
        assert concept is None
        assert index.get_display_name(tag, context) is None
    else:
        assert concept in EXPECTED[tag]
        assert index.get_display_name(tag, context) == DISPLAY_NAMES[concept]


@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_standardization_preserves_filed_data(mapper, tag):
    item = {"concept": f"us-gaap_{tag}", "label": "Filed label", "values": {"2025-12-31": 123_456}, "statement_type": "BalanceSheet"}
    result = standardize_statement([item], mapper)
    assert len(result) == 1
    assert {key: value for key, value in result[0].items() if key != "standard_concept"} == item
    if EXPECTED[tag] is None:
        assert "standard_concept" not in result[0]
    else:
        assert result[0]["standard_concept"] in EXPECTED[tag]


def _rows(frame, standard_concept, column):
    selected = frame[frame["standard_concept"] == standard_concept]
    return dict(zip(selected["concept"], selected[column], strict=True))


# FreightCar America's FY2025 10-K. The schema (which embeds the presentation and label
# linkbases) and the instance render the balance sheet.
RAIL_10K_FOLDER = "https://www.sec.gov/Archives/edgar/data/1320854/000119312526098668/"
RAIL_10K_XBRL_FILES = ("rail-20251231.xsd", "rail-20251231_htm.xml")


@pytest.mark.vcr
def test_freightcar_warrant_liability_is_not_a_warranty_provision(tmp_path):
    """FreightCar America FY2025 10-K, 0001193125-26-098668, balance sheet at 2025-12-31.

    Filed: Warrant liability $168,529K (noncurrent; $136,319K a year earlier), Deferred revenue
    $539K and Accrued warranty $2,050K (both current). The warrant liability was the only
    "Warranty and Other Provisions" row and deferred revenue was "Other Current Liabilities".
    """
    for name in RAIL_10K_XBRL_FILES:
        (tmp_path / name).write_text(download_file(RAIL_10K_FOLDER + name), encoding="utf-8")
    statement = XBRL.from_directory(tmp_path).statements["BalanceSheet"]
    assert statement is not None
    frame = statement.render(standard=True).to_dataframe()
    frame = frame[~frame["dimension"]]

    assert _rows(frame, "OngoingOperatingProvisions(WarrantiesEtc)", "2025-12-31") == {}
    assert _rows(frame, "OtherNonOperatingNonCurrentLiabilities", "2025-12-31") == {
        "us-gaap_WarrantsAndRightsOutstanding": 168_529_000,
        "us-gaap_OtherLiabilitiesNoncurrent": 1_333_000,
    }
    assert _rows(frame, "OtherNonOperatingNonCurrentLiabilities", "2024-12-31")["us-gaap_WarrantsAndRightsOutstanding"] == 136_319_000
    assert _rows(frame, "DeferredRevenueCurrent", "2025-12-31") == {"us-gaap_DeferredRevenue": 539_000}
    assert _rows(frame, "OtherOperatingCurrentLiabilities", "2025-12-31") == {"us-gaap_ProductWarrantyAccrual": 2_050_000}

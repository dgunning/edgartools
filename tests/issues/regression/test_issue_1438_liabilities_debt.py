"""
Liability and debt disclosures were assigned incorrect standard concepts.
Corrected entries identify deferred revenue, liabilities and debt; entries
without a fitting concept return no reverse-index mapping. Apple and Microsoft
provide filing regressions for current and noncurrent deferred revenue.

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
    (Path(__file__).parents[2] / "fixtures" / "standardization" / "issue_1438_liabilities_debt_expected.json").read_text(encoding="utf-8")
)
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))

# These 12 rows repeated the old concept in every industry override.
HAD_OVERRIDES = [
    "AccruedRoyaltiesCurrent",
    "CommitmentsAndContingencies",
    "ContractWithCustomerLiabilityCurrent",
    "ContractWithCustomerLiabilityNoncurrent",
    "CustomerAdvancesCurrent",
    "DeferredIncomeCurrent",
    "DeferredIncomeNoncurrent",
    "DerivativeInstrumentsAndHedgesLiabilities",
    "OperatingLeaseLiability",
    "SecuredDebt",
    "SharesSubjectToMandatoryRedemptionSettlementTermsFairValueOfShares",
    "SubordinatedDebt",
]


# Pin deletion keys independently of the expected-mapping fixture.
DELETED_TAGS = {
    "CommitmentsAndContingencies",
    "DebtInstrumentFaceAmount",
    "DebtInstrumentIncreaseDecreaseForPeriodNet",
    "DebtLongtermAndShorttermCombinedAmount",
    "LiabilitiesOtherThanLongtermDebtNoncurrent",
    "OperatingLeaseLiability",
    "OperatingLeaseLiabilityStatementOfFinancialPositionExtensibleList",
    "SharesSubjectToMandatoryRedemptionSettlementTermsFairValueOfShares",
    "TemporaryEquityLiquidationPreference",
}

# These exclusions remain intentional even after their stored entries are removed.
EXCLUDED_ROWS = {
    "CommitmentsAndContingencies": None,
}

INDUSTRIES = sorted({code for _, _, code in _FF48_SIC_RANGES})
STATEMENT_TYPES = [
    "BalanceSheet",
    "IncomeStatement",
    "CashFlowStatement",
    "http://example.com/role/FinancialStatement",
    "",
]


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
    if expected is None or tag in EXCLUDED_ROWS:
        assert result is None
    else:
        assert result is not None and result.standard_concepts == expected


def test_only_the_decided_rows_remain_excluded():
    """Public behavior follows the explicit exclusion decision for this scope."""
    assert set(EXPECTED) & EXCLUDED_TAGS == set(EXCLUDED_ROWS)
    assert {tag: EXPECTED[tag] for tag in EXCLUDED_ROWS} == EXCLUDED_ROWS


@pytest.mark.parametrize("tag", sorted(EXPECTED))
@pytest.mark.parametrize("industry", INDUSTRIES)
def test_no_industry_brings_the_old_concept_back(index, tag, industry):
    """Each industry resolves to the independent expected mapping or exclusion."""
    expected = None if tag in EXCLUDED_ROWS else EXPECTED[tag]
    result = index.lookup(tag, industry=industry)
    if expected is None:
        assert result is None
    else:
        assert result is not None
        assert result.standard_concepts == expected
        assert result.display_names == [DISPLAY_NAMES[concept] for concept in expected]
        assert result.is_ambiguous is False


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
        ("ContractWithCustomerLiabilityCurrent", "DeferredRevenueCurrent", "Deferred Revenue, Current"),
        ("ContractWithCustomerLiabilityNoncurrent", "DeferredRevenueNonCurrent", "Deferred Revenue, Non-Current"),
        ("DeferredIncomeCurrent", "DeferredRevenueCurrent", "Deferred Revenue, Current"),
        ("DeferredRevenueAndCreditsNoncurrent", "DeferredRevenueNonCurrent", "Deferred Revenue, Non-Current"),
        ("CustomerDepositsCurrent", "CustomerAdvances", "Customer Advances and Deposits"),
        ("ConstructionPayableCurrent", "TradePayables", "Accounts Payable"),
        ("SecuredDebt", "LongTermDebt", "Long-Term Debt"),
        ("SubordinatedDebt", "LongTermDebt", "Long-Term Debt"),
        ("LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities", "LongTermDebt", "Long-Term Debt"),
        ("LiabilitiesNoncurrent", "NonCurrentLiabilitiesTotal", "Total Non-Current Liabilities"),
        ("AssetRetirementObligation", "AssetRetirementObligations", "Asset Retirement Obligations"),
        ("WorkersCompensationLiabilityCurrent", "SelfInsuranceReserve", "Self-Insurance Reserve"),
        (
            "DeferredCompensationCashbasedArrangementsLiabilityClassifiedNoncurrent",
            "DeferredCompensationNonCurrent",
            "Deferred Compensation, Non-Current",
        ),
    ],
)
def test_concept_follows_the_element_definition(index, tag, concept, display):
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == [concept]
    assert result.display_names == [display]


@pytest.mark.parametrize("tag", sorted(DELETED_TAGS))
def test_entries_without_a_fitting_standard_concept_return_none(index, tag):
    """A face amount, a net change in debt, a liquidation preference and a memo line used to be debt, current liabilities or totals."""
    assert index.lookup(tag) is None


def test_deferred_revenue_concepts_hold_only_deferred_revenue(index):
    assert {
        "ContractWithCustomerLiabilityCurrent",
        "DeferredIncomeCurrent",
    } <= _members(index, "DeferredRevenueCurrent")
    assert {
        "ContractWithCustomerLiabilityNoncurrent",
        "DeferredIncomeNoncurrent",
        "DeferredRevenueAndCreditsNoncurrent",
    } <= _members(index, "DeferredRevenueNonCurrent")
    assert "DeferredIncomeNoncurrent" not in _members(index, "OngoingOperatingProvisions(WarrantiesEtc)")


def _balance_sheet(directory):
    xbrl = XBRL.from_directory(Path(__file__).parents[2] / "fixtures" / "xbrl" / directory)
    statement = xbrl.statements["BalanceSheet"]
    assert statement is not None
    frame = statement.render(standard=True).to_dataframe()
    return frame[~frame["dimension"]]


def test_apple_deferred_revenue_is_deferred_revenue_current():
    """Apple FY2023 10-K: "Deferred revenue" $8,061M at Sep 30, 2023, was Other Operating Current Liabilities."""
    frame = _balance_sheet("aapl/10k_2023")
    rows = frame[frame["concept"] == "us-gaap_ContractWithCustomerLiabilityCurrent"]
    assert len(rows) == 1
    assert rows["2023-09-30"].iloc[0] == 8_061_000_000
    assert rows["standard_concept"].iloc[0] == "DeferredRevenueCurrent"


def test_microsoft_unearned_revenue_is_deferred_revenue_current_and_noncurrent():
    """Microsoft FY2024 10-K: short-term unearned revenue $57,582M and long-term $2,602M at Jun 30, 2024 (the long-term line was Contract Liabilities)."""
    frame = _balance_sheet("msft/10k_2024")
    current = frame[frame["concept"] == "us-gaap_ContractWithCustomerLiabilityCurrent"]
    noncurrent = frame[frame["concept"] == "us-gaap_ContractWithCustomerLiabilityNoncurrent"]
    assert len(current) == 1
    assert current["2024-06-30"].iloc[0] == 57_582_000_000
    assert current["standard_concept"].iloc[0] == "DeferredRevenueCurrent"
    assert len(noncurrent) == 1
    assert noncurrent["2024-06-30"].iloc[0] == 2_602_000_000
    assert noncurrent["standard_concept"].iloc[0] == "DeferredRevenueNonCurrent"


@pytest.fixture(scope="module")
def mapper():
    return ConceptMapper(MappingStore(read_only=True))


def test_expected_entries_and_industry_domain_are_complete():
    assert len(EXPECTED) == 34
    assert {tag for tag, concepts in EXPECTED.items() if concepts is None} == DELETED_TAGS
    assert sum(concepts is not None for concepts in EXPECTED.values()) == 25
    assert len(INDUSTRIES) == 48


@pytest.mark.parametrize("tag", sorted(tag for tag, concepts in EXPECTED.items() if concepts))
def test_corrected_entry_metadata_matches_its_concept(tag):
    concepts = EXPECTED[tag]
    assert concepts is not None and len(concepts) == 1
    entry = GAAP_MAPPINGS[tag]
    statement = get_statement_for_concept(concepts[0])
    assert entry["display_name"] == DISPLAY_NAMES[concepts[0]]
    assert entry["statement"] == statement
    assert entry["section"] == get_section_for_concept(concepts[0], statement)
    assert entry["is_total"] is (tag == "LiabilitiesNoncurrent")
    assert entry["confidence"] == 0.9
    assert "ambiguous" not in entry


@pytest.mark.parametrize("tag", sorted(EXPECTED))
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
@pytest.mark.parametrize("section", [None, "Current Assets", "Non-Current Assets", "Current Liabilities", "Non-Current Liabilities"])
def test_public_context_paths_keep_the_corrected_concept(index, tag, statement_type, section):
    context = {"statement_type": statement_type, "section": section}
    expected = None if tag in EXCLUDED_ROWS else EXPECTED[tag]
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
    expected = None if tag in EXCLUDED_ROWS else EXPECTED[tag]
    if expected is None:
        assert "standard_concept" not in result[0]
    else:
        assert result[0]["standard_concept"] == expected[0]

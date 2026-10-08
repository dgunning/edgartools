"""
Income, comprehensive income and related disclosures were assigned incorrect
standard concepts. The expected table covers every corrected entry, including
five excluded tags whose stored mappings still need to be correct. ExxonMobil
and Disney provide filing regressions for exploration expense and net interest.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1439
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

FIXTURES = Path(__file__).parents[2] / "fixtures"
EXPECTED = json.loads((FIXTURES / "standardization" / "issue_1439_income_statement_oci_expected.json").read_text(encoding="utf-8"))
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))

EXCLUDED_ROWS = {
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic": None,
    "NetIncomeLossAvailableToCommonStockholdersDiluted": ["NetIncomeToCommonShareholders"],
    "NetIncomeLossIncludingPortionAttributableToNonredeemableNoncontrollingInterest": ["ProfitLoss"],
    "OtherComprehensiveIncomeLossAvailableForSaleSecuritiesAdjustmentNetOfTax": ["UnrealizedGainsLossesSecurities"],
    "OtherComprehensiveIncomeLossTax": None,
}
ALL_ROWS = EXPECTED


# Pin deletion keys independently of the expected-mapping fixture.
DELETED_TAGS = {
    "ComprehensiveIncomeNetOfTaxAttributableToNoncontrollingInterest",
    "ConversionOfStockSharesConverted1",
    "DebtConversionConvertedInstrumentSharesIssued1",
    "EquitySecuritiesWithoutReadilyDeterminableFairValueDownwardPriceAdjustmentCumulativeAmount",
    "EquitySecuritiesWithoutReadilyDeterminableFairValueImpairmentLossCumulativeAmount",
    "FiniteLivedIntangibleAssetsAmortizationExpenseRemainderOfFiscalYear",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
    "InterestCostsCapitalized",
    "InterestCostsIncurredCapitalized",
    "LicenseMember",
    "MinorityInterestChangeInRedemptionValue",
    "MinorityInterestDecreaseFromRedemptions",
    "MinorityInterestPeriodIncreaseDecrease",
    "NoncontrollingInterestDecreaseFromDeconsolidation",
    "OtherComprehensiveIncomeLossBeforeTax",
    "OtherComprehensiveIncomeLossBeforeTaxPortionAttributableToParent",
    "OtherComprehensiveIncomeLossNetOfTaxPortionAttributableToNoncontrollingInterest",
    "OtherComprehensiveIncomeLossTax",
    "OtherComprehensiveIncomeLossTaxPortionAttributableToParent1",
    "PaymentsForOtherTaxes",
    "ProceedsFromLegalSettlements",
    "StockIssuedDuringPeriodSharesConversionOfConvertibleSecurities",
    "StockIssuedDuringPeriodSharesEmployeeBenefitPlan",
    "StockIssuedDuringPeriodSharesRestrictedStockAwardGross",
    "TemporaryEquityAccretionToRedemptionValue",
    "TemporaryEquityForeignCurrencyTranslationAdjustments",
}

INDUSTRIES = sorted({code for _, _, code in _FF48_SIC_RANGES})
STATEMENT_TYPES = [
    "BalanceSheet",
    "IncomeStatement",
    "CashFlowStatement",
    "ComprehensiveIncome",
    "http://example.com/role/IncomeStatement",
    "http://example.com/role/ComprehensiveIncome",
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
    "Equity",
    "Revenue",
    "Cost of Revenue",
    "Operating Expenses",
    "Non-Operating Items",
    "Net Income",
    "Banking Revenue",
    "Banking Expenses",
    "OCI Components",
    "Comprehensive Income Totals",
]
NAMESPACE_PREFIXES = ["", "us-gaap_", "us-gaap:"]
CALCULATION_PARENTS = [
    "us-gaap:AssetsCurrent",
    "us-gaap_AssetsNoncurrent",
    "us-gaap:LiabilitiesCurrent",
    "us-gaap_LiabilitiesNoncurrent",
    "us-gaap:StockholdersEquity",
    "us-gaap_OperatingCostsAndExpenses",
    "us-gaap:OtherComprehensiveIncomeLossCashFlowHedgeGainLossReclassificationTax",
]


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


def _members(index, concept):
    return {tag for tag, entry in index._index.items() if isinstance(entry, dict) and concept in entry.get("standard_tags", [])}


@pytest.mark.parametrize("tag", sorted(ALL_ROWS))
def test_corrected_entries(index, tag):
    expected = ALL_ROWS[tag]
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
    assert set(ALL_ROWS) & EXCLUDED_TAGS == set(EXCLUDED_ROWS)
    assert {tag: ALL_ROWS[tag] for tag in EXCLUDED_ROWS} == EXCLUDED_ROWS


@pytest.mark.parametrize("tag", sorted(ALL_ROWS))
@pytest.mark.parametrize("industry", INDUSTRIES)
def test_no_industry_brings_the_old_concept_back(index, tag, industry):
    """Each industry resolves to the independent expected mapping or exclusion."""
    expected = None if tag in EXCLUDED_ROWS else ALL_ROWS[tag]
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
    assert [tag for tag in ALL_ROWS if "industry_overrides" in GAAP_MAPPINGS.get(tag, {})] == []


def test_single_candidate_display_name_matches_the_catalog():
    """A stale display_name would still pass the concept check above."""
    for tag, concepts in ALL_ROWS.items():
        if not concepts or len(concepts) != 1:
            continue
        assert GAAP_MAPPINGS[tag]["display_name"] == DISPLAY_NAMES[concepts[0]], tag


@pytest.mark.parametrize(
    "tag, concept, display",
    [
        ("ExplorationExpense", "OtherOperatingExpense", "Other Operating Expense"),
        ("GainsLossesOnExtinguishmentOfDebt", "LossOnDebtExtinguishment", "Loss on Debt Extinguishment"),
        ("InterestIncomeExpenseNonoperatingNet", "NetInterestIncome", "Net Interest Income"),
        ("DefinedBenefitPlanInterestCost", "PensionExpense", "Net Periodic Pension Cost"),
        ("OtherComprehensiveIncomeLossCashFlowHedgeGainLossReclassificationAfterTax", "HedgingGainsLosses", "Hedging Gains/Losses"),
        (
            "OtherComprehensiveIncomeDefinedBenefitPlansNetUnamortizedGainLossArisingDuringPeriodNetOfTax",
            "PensionAndRetirementAdjustments",
            "Pension and Retirement Adjustments",
        ),
        (
            "IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest",
            "IncomeLossContinuingOperations",
            "Income from Continuing Operations",
        ),
    ],
)
def test_concept_follows_the_element_definition(index, tag, concept, display):
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == [concept]
    assert result.display_names == [display]


def test_share_counts_in_equity_notes_are_not_diluted_weighted_average_shares(index):
    """Four share-issuance and conversion elements used to sit beside the weighted-average share counts."""
    assert _members(index, "SharesFullyDilutedAverage") == {
        "AdjustedWeightedAverageShares",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
        "ifrs-full_AdjustedWeightedAverageShares",
    }


def test_comprehensive_income_holds_no_net_income_or_other_comprehensive_income_elements(index):
    members = _members(index, "ComprehensiveIncomeNet")
    assert {tag for tag in members if tag.startswith(("NetIncomeLoss", "OtherComprehensiveIncome"))} == set()


@pytest.fixture(scope="module")
def xom_fy2022():
    return XBRL.from_directory(FIXTURES / "xbrl" / "xom" / "10k_2023")


@pytest.fixture(scope="module")
def dis_fy2025():
    return XBRL.from_directory(FIXTURES / "xbrl" / "dis" / "10k_2025")


def _income_statement_row(xbrl, concept):
    frame = xbrl.statements["IncomeStatement"].render(standard=True).to_dataframe()
    rows = frame[(frame["concept"] == concept) & ~frame["dimension"]]
    assert len(rows) == 1
    return rows.iloc[0]


def test_exxon_exploration_expense_is_not_research_and_development(xom_fy2022):
    """ExxonMobil FY2022 10-K, 0000034088-23-000020: exploration expenses, including dry holes, were $1,025 million."""
    row = _income_statement_row(xom_fy2022, "us-gaap_ExplorationExpense")
    assert row["2022-12-31"] == 1_025_000_000
    assert row["standard_concept"] == "OtherOperatingExpense"


def test_disney_net_interest_is_not_plain_interest_expense(dis_fy2025):
    """Disney FY2025 10-K, 0001744489-25-000155: "Interest expense, net" was $1,305 million, and it nets interest income."""
    row = _income_statement_row(dis_fy2025, "us-gaap_InterestIncomeExpenseNonoperatingNet")
    assert row["2025-09-27"] == -1_305_000_000
    assert row["standard_concept"] == "NetInterestIncome"


def test_an_unknown_element_returns_none_not_a_guess(index):
    assert index.lookup("NoSuchElementInAnyTaxonomy") is None


@pytest.fixture(scope="module")
def mapper():
    return ConceptMapper(MappingStore(read_only=True))


def test_expected_entries_and_industry_domain_are_complete():
    assert len(ALL_ROWS) == 53
    assert {tag for tag, concepts in ALL_ROWS.items() if concepts is None} == DELETED_TAGS
    assert sum(concepts is not None for concepts in ALL_ROWS.values()) == 27
    assert DELETED_TAGS & EXCLUDED_ROWS.keys() == {
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
        "OtherComprehensiveIncomeLossTax",
    }
    assert EXCLUDED_ROWS.keys() - DELETED_TAGS == {
        "NetIncomeLossAvailableToCommonStockholdersDiluted",
        "NetIncomeLossIncludingPortionAttributableToNonredeemableNoncontrollingInterest",
        "OtherComprehensiveIncomeLossAvailableForSaleSecuritiesAdjustmentNetOfTax",
    }
    assert len(INDUSTRIES) == 48


@pytest.mark.parametrize("tag", sorted(tag for tag, concepts in ALL_ROWS.items() if concepts))
def test_corrected_entry_metadata_matches_its_concept(tag):
    concepts = ALL_ROWS[tag]
    assert concepts is not None and len(concepts) == 1
    entry = GAAP_MAPPINGS[tag]
    statement = get_statement_for_concept(concepts[0])
    assert entry["display_name"] == DISPLAY_NAMES[concepts[0]]
    assert entry["statement"] == statement
    assert entry["section"] == get_section_for_concept(concepts[0], statement)
    assert entry["is_total"] is False
    assert entry["confidence"] == 0.9
    assert "ambiguous" not in entry


@pytest.mark.parametrize("tag", sorted(ALL_ROWS))
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
@pytest.mark.parametrize("section", SECTIONS)
def test_public_context_paths_keep_the_corrected_concept(index, tag, statement_type, section):
    context = {"statement_type": statement_type, "section": section}
    expected = None if tag in EXCLUDED_ROWS else ALL_ROWS[tag]
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


@pytest.mark.parametrize("tag", sorted(ALL_ROWS))
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
@pytest.mark.parametrize("prefix", NAMESPACE_PREFIXES)
def test_standardization_preserves_filed_data(mapper, tag, statement_type, prefix):
    item = {
        "concept": f"{prefix}{tag}",
        "label": "Filed disclosure label",
        "values": {"2023-12-31": 123_456, "2022-12-31": -123_456},
        "statement_type": statement_type,
    }
    result = standardize_statement([item], mapper)
    assert len(result) == 1
    assert "standard_concept" not in item
    assert {key: value for key, value in result[0].items() if key != "standard_concept"} == item
    expected = None if tag in EXCLUDED_ROWS else ALL_ROWS[tag]
    if expected is None:
        assert "standard_concept" not in result[0]
    else:
        assert result[0]["standard_concept"] == expected[0]


@pytest.mark.parametrize("tag", sorted(DELETED_TAGS))
@pytest.mark.parametrize("prefix", NAMESPACE_PREFIXES)
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
def test_deleted_entries_have_no_legacy_mapping(mapper, tag, prefix, statement_type):
    """Deleting these entries exposes no fallback in the shipped legacy catalog."""
    concept = f"{prefix}{tag}"
    context = {"statement_type": statement_type}
    assert mapper.mapping_store.get_standard_concept(concept, context) is None
    assert mapper.mapping_store.get_display_name(concept, context) is None
    assert mapper.map_concept(concept, "Filed disclosure label", context) is None


@pytest.mark.parametrize("tag", sorted(DELETED_TAGS))
@pytest.mark.parametrize("prefix", NAMESPACE_PREFIXES)
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
@pytest.mark.parametrize("calculation_parent", CALCULATION_PARENTS)
def test_deleted_entries_stay_unmapped_under_calculation_parents(mapper, tag, prefix, statement_type, calculation_parent):
    """Real calculation parents supply asset, liability, equity, income and OCI sections."""
    item = {
        "concept": f"{prefix}{tag}",
        "label": "Filed disclosure label",
        "values": {"2023-12-31": 123_456, "2022-12-31": -123_456},
        "statement_type": statement_type,
        "calculation_parent": calculation_parent,
    }
    result = standardize_statement([item], mapper)
    assert result == [item]
    assert "standard_concept" not in item

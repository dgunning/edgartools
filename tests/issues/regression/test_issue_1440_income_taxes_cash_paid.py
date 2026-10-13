"""
Tax balances, tax components and cash-paid disclosures were assigned incorrect
standard concepts. Cash paid for income taxes and interest is disclosed under
ASC 230-10-50-2; deferred taxes are noncurrent on a classified balance sheet
under ASC 740-10-45-4. Apple, Coca-Cola and Microsoft provide filing regressions.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1440
GitHub Issue: https://github.com/dgunning/edgartools/issues/1417
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.core import ConceptMapper, MappingStore, standardize_statement
from edgar.xbrl.standardization.exclusions import EXCLUDED_TAGS
from edgar.xbrl.standardization.reverse_index import get_reverse_index
from edgar.xbrl.standardization.sections import get_section_for_concept, get_statement_for_concept
from edgar.xbrl.standardization.sic_industry import _FF48_SIC_RANGES

FIXTURES = Path(__file__).parents[2] / "fixtures"
EXPECTED = json.loads((FIXTURES / "standardization" / "issue_1440_income_taxes_cash_paid_expected.json").read_text(encoding="utf-8"))
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))
CONCEPT_MAPPINGS = json.loads((_STANDARDIZATION / "concept_mappings.json").read_text(encoding="utf-8"))

CASH_PAID = [
    "IncomeTaxesPaidNet",
    "IncomeTaxesPaid",
    "InterestPaidNet",
    "InterestPaid",
    "InterestPaidCapitalized",
    "ProceedsFromIncomeTaxRefunds",
]


# Pin deletion keys independently of the expected-mapping fixture.
DELETED_TAGS = {
    "AdjustmentsToAdditionalPaidInCapitalTaxEffectFromShareBasedCompensation",
    "EffectiveIncomeTaxRateReconciliationShareBasedCompensationExcessTaxBenefitAmount",
    "IncomeTaxEffectsAllocatedDirectlyToEquityEmployeeStockOptions",
    "IncomeTaxReconciliationNondeductibleExpenseCharitableContributions",
    "IncomeTaxesPaid",
    "IncomeTaxesPaidNet",
    "InterestPaid",
    "InterestPaidCapitalized",
    "InterestPaidNet",
    "ProceedsFromIncomeTaxRefunds",
}

# These exclusions remain intentional even after their stored entries are removed.
EXCLUDED_ROWS = {
    "IncomeTaxesPaid": None,
}

INDUSTRIES = sorted({code for _, _, code in _FF48_SIC_RANGES})
STATEMENT_TYPES = [
    "BalanceSheet",
    "IncomeStatement",
    "CashFlowStatement",
    "ComprehensiveIncome",
    "http://example.com/role/BalanceSheet",
    "http://example.com/role/IncomeStatement",
    "http://example.com/role/CashFlowStatement",
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
    "Income Tax",
    "Operating Expenses",
    "Operating Activities",
    "Supplemental Disclosures",
]
NAMESPACE_PREFIXES = ["", "us-gaap_", "us-gaap:"]
CALCULATION_PARENTS = [
    "us-gaap:AssetsCurrent",
    "us-gaap_AssetsNoncurrent",
    "us-gaap:LiabilitiesCurrent",
    "us-gaap_LiabilitiesNoncurrent",
    "us-gaap:StockholdersEquity",
    "us-gaap_IncomeTaxExpenseBenefit",
    "us-gaap:NetCashProvidedByUsedInOperatingActivities",
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
        ("DeferredIncomeTaxLiabilitiesNet", "DeferredTaxNonCurrentLiabilities", "Deferred Tax Liabilities, Non-Current"),
        ("DeferredTaxLiabilities", "DeferredTaxNonCurrentLiabilities", "Deferred Tax Liabilities, Non-Current"),
        ("DeferredTaxAssetsNet", "DeferredTaxNoncurrentAssets", "Deferred Tax Assets, Non-Current"),
        ("DeferredIncomeTaxExpenseBenefit", "DeferredIncomeTaxExpense", "Deferred Income Tax Expense"),
        ("TaxesPayableCurrent", "TaxesPayable", "Taxes Payable"),
        ("AccruedIncomeTaxesNoncurrent", "OtherNonOperatingNonCurrentLiabilities", "Other Non-Operating Non-Current Liabilities"),
        ("LiabilityForUncertainTaxPositionsNoncurrent", "OtherNonOperatingNonCurrentLiabilities", "Other Non-Operating Non-Current Liabilities"),
    ],
)
def test_concept_follows_the_element_definition(index, tag, concept, display):
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == [concept]
    assert result.display_names == [display]


@pytest.mark.parametrize("section", ["Current Assets", "Current Liabilities", "Non-Current Liabilities"])
def test_deferred_taxes_are_noncurrent_whatever_the_section(index, section):
    """ASU 2015-17: the section a company files them under cannot make a deferred tax current."""
    context = {"section": section, "statement_type": "BalanceSheet"}
    assert index.get_standard_concept("DeferredIncomeTaxLiabilitiesNet", context=context) == "DeferredTaxNonCurrentLiabilities"
    assert index.get_standard_concept("DeferredTaxAssetsNet", context=context) == "DeferredTaxNoncurrentAssets"


@pytest.mark.parametrize("tag", CASH_PAID)
def test_cash_paid_for_taxes_and_interest_claims_no_concept(index, tag):
    """Cash paid is a cash-flow disclosure; it is not the expense on the income statement."""
    assert index.lookup(tag) is None
    for concept in ("IncomeTaxes", "InterestExpense"):
        assert concept in DISPLAY_NAMES
        assert tag not in _members(index, concept)


def test_income_tax_expense_label_no_longer_lists_taxes_paid():
    """The legacy label hid the answer behind a cash-paid tag."""
    assert CONCEPT_MAPPINGS["Income Tax Expense"] == ["us-gaap_IncomeTaxExpenseBenefit"]
    store = MappingStore(read_only=True)
    assert store.get_standard_concept("us-gaap_IncomeTaxesPaidNet") is None
    assert store.get_standard_concept("us-gaap_IncomeTaxExpenseBenefit") == "Income Tax Expense"


def _row(xbrl, statement, concept):
    frame = xbrl.statements[statement].render(standard=True).to_dataframe()
    rows = frame[(frame["concept"] == concept) & ~frame["dimension"]]
    assert len(rows) == 1, concept
    return rows.iloc[0]


def _fixture(*parts):
    return XBRL.from_directory(FIXTURES / "xbrl" / Path(*parts))


def test_apple_cash_paid_for_taxes_and_interest_are_not_standardized():
    """Apple FY2023 10-K cash-flow statement: $18,679M of taxes and $3,803M of interest paid."""
    apple = _fixture("aapl", "10k_2023")
    taxes = _row(apple, "CashFlowStatement", "us-gaap_IncomeTaxesPaidNet")
    interest = _row(apple, "CashFlowStatement", "us-gaap_InterestPaidNet")
    assert taxes["2023-09-30"] == 18_679_000_000
    assert interest["2023-09-30"] == 3_803_000_000
    assert pd.isna(taxes["standard_concept"])
    assert pd.isna(interest["standard_concept"])


@pytest.mark.parametrize(
    "directory, column, value",
    [
        (("ko", "10k_2024"), "2023-12-31", 2_639_000_000),
        (("msft", "10k_2024"), "2024-06-30", 2_618_000_000),
    ],
)
def test_deferred_income_tax_liabilities_are_noncurrent(directory, column, value):
    """Coca-Cola's FY2023 and Microsoft's FY2024 deferred income tax liabilities (10-K balance sheets)."""
    row = _row(_fixture(*directory), "BalanceSheet", "us-gaap_DeferredIncomeTaxLiabilitiesNet")
    assert row[column] == value
    assert row["standard_concept"] == "DeferredTaxNonCurrentLiabilities"


@pytest.fixture(scope="module")
def mapper():
    return ConceptMapper(MappingStore(read_only=True))


def test_expected_entries_and_industry_domain_are_complete():
    assert len(EXPECTED) == 17
    assert {tag for tag, concepts in EXPECTED.items() if concepts is None} == DELETED_TAGS
    assert sum(concepts is not None for concepts in EXPECTED.values()) == 7
    assert DELETED_TAGS & EXCLUDED_ROWS.keys() == {"IncomeTaxesPaid"}
    assert EXCLUDED_ROWS.keys() - DELETED_TAGS == set()
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
    assert entry["is_total"] is False
    assert entry["confidence"] == 0.9
    assert "ambiguous" not in entry


@pytest.mark.parametrize("tag", sorted(EXPECTED))
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
@pytest.mark.parametrize("section", SECTIONS)
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
    expected = None if tag in EXCLUDED_ROWS else EXPECTED[tag]
    if expected is None:
        assert "standard_concept" not in result[0]
    else:
        assert result[0]["standard_concept"] == expected[0]


@pytest.mark.parametrize("tag", sorted(DELETED_TAGS))
@pytest.mark.parametrize("prefix", NAMESPACE_PREFIXES)
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
def test_deleted_entries_have_no_legacy_mapping(mapper, tag, prefix, statement_type):
    """The shipped legacy catalog must not restore a deleted expense mapping."""
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

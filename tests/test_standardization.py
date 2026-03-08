"""
Consolidated standardization unit tests (fast, no network).

Tests the standardization mapping infrastructure: StandardConcept enum, MappingStore,
ConceptMapper, standardize_statement(), default mappings, company-specific mappings,
and bottom-up section assignment.

Consolidated from: test_xbrl_standardization.py, test_enhanced_standardization.py,
test_sga_standardization.py, test_company_specific_standardization.py
"""

import os
import json
import shutil
import tempfile
from unittest.mock import MagicMock

import pytest

from edgar.xbrl.standardization import (
    StandardConcept, MappingStore, ConceptMapper,
    standardize_statement, initialize_default_mappings
)
from edgar.xbrl.standardization.core import _assign_sections_bottom_up


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_mapping_store():
    """Writable MappingStore backed by a temp file, cleaned up after test."""
    store = MappingStore(source="test_mapping.json", read_only=False)
    yield store
    if os.path.exists("test_mapping.json"):
        os.remove("test_mapping.json")


@pytest.fixture
def temp_standardization_dir():
    """Temp directory with core + Tesla company mappings for testing."""
    temp_dir = tempfile.mkdtemp()
    standardization_dir = os.path.join(temp_dir, "standardization")
    company_mappings_dir = os.path.join(standardization_dir, "company_mappings")
    os.makedirs(company_mappings_dir)

    core_mappings = {
        "Revenue": ["us-gaap_Revenue", "us-gaap_Revenues"],
        "Net Income": ["us-gaap_NetIncome", "us-gaap_NetIncomeLoss"]
    }
    with open(os.path.join(standardization_dir, "concept_mappings.json"), 'w') as f:
        json.dump(core_mappings, f)

    tesla_mappings = {
        "metadata": {"entity_identifier": "tsla", "company_name": "Tesla, Inc.", "priority": "high"},
        "concept_mappings": {
            "Automotive Revenue": ["tsla:AutomotiveRevenue"],
            "Automotive Leasing Revenue": ["tsla:AutomotiveLeasing"],
            "Energy Revenue": ["tsla:EnergyGenerationAndStorageRevenue"]
        },
        "hierarchy_rules": {"Revenue": {"children": ["Automotive Revenue", "Energy Revenue"]}}
    }
    with open(os.path.join(company_mappings_dir, "tsla_mappings.json"), 'w') as f:
        json.dump(tesla_mappings, f)

    yield standardization_dir
    shutil.rmtree(temp_dir)


# ── StandardConcept enum ─────────────────────────────────────────────────────

def test_standard_concepts():
    """Core enum values are defined correctly."""
    assert StandardConcept.REVENUE.value == "Revenue"
    assert StandardConcept.NET_INCOME.value == "Net Income"
    assert StandardConcept.TOTAL_ASSETS.value == "Total Assets"


def test_hierarchical_standard_concepts():
    """Hierarchical concepts (automotive, SG&A breakdown) are available."""
    assert StandardConcept.AUTOMOTIVE_REVENUE.value == "Automotive Revenue"
    assert StandardConcept.AUTOMOTIVE_LEASING_REVENUE.value == "Automotive Leasing Revenue"
    assert StandardConcept.ENERGY_REVENUE.value == "Energy Revenue"
    assert StandardConcept.SELLING_EXPENSE.value == "Selling Expense"
    assert StandardConcept.GENERAL_ADMIN_EXPENSE.value == "General and Administrative Expense"
    assert StandardConcept.MARKETING_EXPENSE.value == "Marketing Expense"


# ── MappingStore ──────────────────────────────────────────────────────────────

def test_mapping_store_add_get(temp_mapping_store):
    """Add and retrieve mappings, including reverse lookup."""
    store = temp_mapping_store
    store.add("us-gaap_Revenue", StandardConcept.REVENUE.value)
    store.add("us-gaap_NetIncome", StandardConcept.NET_INCOME.value)

    assert store.get_standard_concept("us-gaap_Revenue") == StandardConcept.REVENUE.value
    assert store.get_standard_concept("us-gaap_NetIncome") == StandardConcept.NET_INCOME.value
    assert "us-gaap_Revenue" in store.get_company_concepts(StandardConcept.REVENUE.value)


def test_initialize_default_mappings():
    """Default mapping file loads with specific concept-to-standard mappings."""
    store = initialize_default_mappings(read_only=True)
    assert store.get_standard_concept("us-gaap_Revenue") == "Revenue"
    assert store.get_standard_concept("us-gaap_NetIncome") == "Net Income"
    assert store.get_standard_concept("us-gaap_Assets") == "Total Assets"
    assert store.get_standard_concept(
        "us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect"
    ) == "Net Change in Cash"


def test_hierarchy_mappings_are_distinct():
    """Revenue, net income, and cost concepts map correctly.

    Consolidated from: test_revenue_hierarchy_fix.py, test_net_income_hierarchy_fix.py,
    test_tesla_net_income_fix.py, test_cost_of_revenue_fix.py
    """
    store = initialize_default_mappings(read_only=True)

    # Multiple revenue concepts all map to "Revenue"
    assert store.get_standard_concept("us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax") == "Revenue"
    assert store.get_standard_concept("us-gaap_SalesRevenueGoodsNet") == "Revenue"
    assert store.get_standard_concept("us-gaap_Revenue") == "Revenue"
    assert store.get_standard_concept("us-gaap_Revenues") == "Revenue"

    # Net income hierarchy: distinct labels for different concepts
    assert store.get_standard_concept("us-gaap_NetIncomeLoss") == "Net Income"
    assert store.get_standard_concept("us-gaap_NetIncomeLossAttributableToNoncontrollingInterest") == "Net Income Attributable to Noncontrolling Interest"
    assert store.get_standard_concept("us-gaap_ProfitLoss") == "Profit or Loss"

    # Cost concepts all map to "Cost of Revenue"
    assert store.get_standard_concept("us-gaap_CostOfRevenue") == "Cost of Revenue"
    assert store.get_standard_concept("us-gaap_CostOfGoodsSold") == "Cost of Revenue"
    assert store.get_standard_concept("us-gaap_CostOfGoodsAndServicesSold") == "Cost of Revenue"

    # Unmapped concepts return None
    assert store.get_standard_concept("us-gaap_SomeOtherRevenue") is None


# ── ConceptMapper ─────────────────────────────────────────────────────────────

def test_concept_mapper_direct_mapping(temp_mapping_store):
    """ConceptMapper returns correct standard concept for a known mapping."""
    store = temp_mapping_store
    store.add("us-gaap_Revenue", StandardConcept.REVENUE.value)
    mapper = ConceptMapper(store)
    result = mapper.map_concept("us-gaap_Revenue", "Revenue", {"statement_type": "IncomeStatement"})
    assert result == StandardConcept.REVENUE.value


# ── standardize_statement() ──────────────────────────────────────────────────

def test_standardize_statement():
    """Original labels preserved, standard_concept metadata added."""
    statement_data = [
        {"concept": "us-gaap_Revenues", "label": "Revenue",
         "statement_type": "IncomeStatement", "is_abstract": False},
        {"concept": "us-gaap_CostOfGoodsAndServicesSold", "label": "Cost of Sales",
         "statement_type": "IncomeStatement", "is_abstract": False}
    ]
    mapper = MagicMock()
    result = standardize_statement(statement_data, mapper)

    assert result[0]["label"] == "Revenue"
    assert result[1]["label"] == "Cost of Sales"
    assert result[0]["standard_concept"] == "Revenue"
    assert result[1]["standard_concept"] == "CostOfGoodsAndServicesSold"


# ── Company-specific mappings (Tesla) ─────────────────────────────────────────

def test_tesla_specific_mapping_priority(temp_standardization_dir):
    """Tesla-specific concept maps correctly; core US-GAAP still works."""
    path = os.path.join(temp_standardization_dir, "concept_mappings.json")
    store = MappingStore(source=path, read_only=True)
    assert store.get_standard_concept("tsla:AutomotiveLeasing") == "Automotive Leasing Revenue"
    assert store.get_standard_concept("us-gaap_Revenue") == "Revenue"


def test_company_detection_from_concept_prefix(temp_standardization_dir):
    """Entity detection from concept prefix returns correct company or None."""
    path = os.path.join(temp_standardization_dir, "concept_mappings.json")
    store = MappingStore(source=path, read_only=True)
    assert store._detect_entity_from_concept("tsla_AutomotiveRevenue") == "tsla"
    assert store._detect_entity_from_concept("us-gaap_Revenue") is None
    assert store._detect_entity_from_concept("unknown:Concept") is None


def test_hierarchy_rules_loading(temp_standardization_dir):
    """Hierarchy rules from company mapping JSON are loaded correctly."""
    path = os.path.join(temp_standardization_dir, "concept_mappings.json")
    store = MappingStore(source=path, read_only=True)
    assert "Revenue" in store.hierarchy_rules
    assert store.hierarchy_rules["Revenue"]["children"] == ["Automotive Revenue", "Energy Revenue"]


def test_error_handling_missing_company_mapping_file(temp_standardization_dir):
    """Invalid JSON in company_mappings dir doesn't crash store init."""
    invalid_file = os.path.join(temp_standardization_dir, "company_mappings", "invalid_mappings.json")
    with open(invalid_file, 'w') as f:
        f.write("{ invalid json")

    path = os.path.join(temp_standardization_dir, "concept_mappings.json")
    store = MappingStore(source=path, read_only=True)
    assert 'tsla' in store.company_mappings


# ── Bottom-up section assignment ──────────────────────────────────────────────

def test_bottom_up_section_assignment_balance_sheet():
    """Balance sheet items grouped into Current Assets, Non-Current Assets, Current Liabilities."""
    statement_data = [
        {"concept": "cash", "label": "Cash", "is_total": False, "level": 2},
        {"concept": "ar", "label": "Accounts Receivable", "is_total": False, "level": 2},
        {"concept": "total_ca", "label": "Total Current Assets", "is_total": True, "level": 1},
        {"concept": "ppe", "label": "Property, Plant and Equipment", "is_total": False, "level": 2},
        {"concept": "goodwill", "label": "Goodwill", "is_total": False, "level": 2},
        {"concept": "total_nca", "label": "Total Non-Current Assets", "is_total": True, "level": 1},
        {"concept": "ap", "label": "Accounts Payable", "is_total": False, "level": 2},
        {"concept": "total_cl", "label": "Total Current Liabilities", "is_total": True, "level": 1},
    ]
    items = [(i, d["concept"], d["label"], {"statement_type": "BalanceSheet"}) for i, d in enumerate(statement_data)]
    _assign_sections_bottom_up(items, statement_data)
    ctx = {item[1]: item[3] for item in items}

    assert ctx["cash"].get("section") == "Current Assets"
    assert ctx["ar"].get("section") == "Current Assets"
    assert ctx["ppe"].get("section") == "Non-Current Assets"
    assert ctx["goodwill"].get("section") == "Non-Current Assets"
    assert ctx["ap"].get("section") == "Current Liabilities"


def test_bottom_up_does_not_override_existing_sections():
    """Items with section already set (from calculation_parent) are not overwritten."""
    statement_data = [
        {"concept": "cash", "label": "Cash", "is_total": False, "level": 2},
        {"concept": "total_ca", "label": "Total Current Assets", "is_total": True, "level": 1},
    ]
    items = [
        (0, "cash", "Cash", {"statement_type": "BalanceSheet", "section": "Current Assets"}),
        (1, "total_ca", "Total Current Assets", {"statement_type": "BalanceSheet"}),
    ]
    _assign_sections_bottom_up(items, statement_data)
    assert items[0][3]["section"] == "Current Assets"


def test_bottom_up_income_statement_sections():
    """Income statement items grouped into Revenue, Cost of Revenue, Operating Expenses."""
    statement_data = [
        {"concept": "product_rev", "label": "Product Revenue", "is_total": False, "level": 2},
        {"concept": "service_rev", "label": "Service Revenue", "is_total": False, "level": 2},
        {"concept": "total_rev", "label": "Total Revenue", "is_total": True, "level": 1},
        {"concept": "cogs", "label": "Cost of Goods Sold", "is_total": False, "level": 2},
        {"concept": "total_cogs", "label": "Total Cost of Revenue", "is_total": True, "level": 1},
        {"concept": "sga", "label": "SG&A", "is_total": False, "level": 2},
        {"concept": "total_opex", "label": "Total Operating Expenses", "is_total": True, "level": 1},
    ]
    items = [(i, d["concept"], d["label"], {"statement_type": "IncomeStatement"}) for i, d in enumerate(statement_data)]
    _assign_sections_bottom_up(items, statement_data)
    ctx = {item[1]: item[3] for item in items}

    assert ctx["product_rev"].get("section") == "Revenue"
    assert ctx["service_rev"].get("section") == "Revenue"
    assert ctx["cogs"].get("section") == "Cost of Revenue"
    assert ctx["sga"].get("section") == "Operating Expenses"


def test_bottom_up_equity_section():
    """Equity items grouped into Equity section."""
    statement_data = [
        {"concept": "common_stock", "label": "Common Stock", "is_total": False, "level": 2},
        {"concept": "retained", "label": "Retained Earnings", "is_total": False, "level": 2},
        {"concept": "total_equity", "label": "Total Stockholders' Equity", "is_total": True, "level": 1},
    ]
    items = [(i, d["concept"], d["label"], {"statement_type": "BalanceSheet"}) for i, d in enumerate(statement_data)]
    _assign_sections_bottom_up(items, statement_data)
    ctx = {item[1]: item[3] for item in items}

    assert ctx["common_stock"].get("section") == "Equity"
    assert ctx["retained"].get("section") == "Equity"


def test_bottom_up_noncurrent_liabilities():
    """Current vs non-current liabilities assigned to separate sections."""
    statement_data = [
        {"concept": "short_debt", "label": "Short-term Debt", "is_total": False, "level": 2},
        {"concept": "total_cl", "label": "Total Current Liabilities", "is_total": True, "level": 1},
        {"concept": "long_debt", "label": "Long-term Debt", "is_total": False, "level": 2},
        {"concept": "deferred_tax", "label": "Deferred Tax Liabilities", "is_total": False, "level": 2},
        {"concept": "total_ncl", "label": "Total Non-Current Liabilities", "is_total": True, "level": 1},
    ]
    items = [(i, d["concept"], d["label"], {"statement_type": "BalanceSheet"}) for i, d in enumerate(statement_data)]
    _assign_sections_bottom_up(items, statement_data)
    ctx = {item[1]: item[3] for item in items}

    assert ctx["short_debt"].get("section") == "Current Liabilities"
    assert ctx["long_debt"].get("section") == "Non-Current Liabilities"
    assert ctx["deferred_tax"].get("section") == "Non-Current Liabilities"


def test_bottom_up_handles_empty_items():
    """Empty input does not raise."""
    _assign_sections_bottom_up([], [])


# ── Industry overrides ──────────────────────────────────────────────────────

def test_industry_override_resolves_ambiguous_tag():
    """Industry override narrows ambiguous tag to single concept."""
    from edgar.xbrl.standardization.reverse_index import get_reverse_index
    idx = get_reverse_index()

    # Without industry: ambiguous
    result = idx.lookup("DeferredIncomeTaxLiabilitiesNet")
    assert result.is_ambiguous
    assert len(result.standard_concepts) == 2

    # With Banks industry: resolved to single concept
    result_banks = idx.lookup("DeferredIncomeTaxLiabilitiesNet", industry="Banks")
    assert not result_banks.is_ambiguous
    assert len(result_banks.standard_concepts) == 1
    assert result_banks.standard_concepts[0] == "DeferredTaxCurrentLiabilities"


def test_industry_override_unknown_industry_returns_base():
    """Unknown industry code falls back to base entry."""
    from edgar.xbrl.standardization.reverse_index import get_reverse_index
    idx = get_reverse_index()

    result_base = idx.lookup("DeferredIncomeTaxLiabilitiesNet")
    result_unknown = idx.lookup("DeferredIncomeTaxLiabilitiesNet", industry="FakeIndustry")
    assert result_unknown.standard_concepts == result_base.standard_concepts
    assert result_unknown.is_ambiguous == result_base.is_ambiguous


def test_industry_override_via_get_standard_concept():
    """get_standard_concept passes industry through to lookup."""
    from edgar.xbrl.standardization.reverse_index import get_reverse_index
    idx = get_reverse_index()

    # AccountsPayableCurrentAndNoncurrent is ambiguous: TradePayables vs OtherOperatingNonCurrentLiabilities
    # Banks override resolves to TradePayables
    concept = idx.get_standard_concept("AccountsPayableCurrentAndNoncurrent", industry="Banks")
    assert concept == "TradePayables"


def test_sic_to_fama_french_mapping():
    """SIC codes map to correct FF48 industry codes."""
    from edgar.xbrl.standardization.sic_industry import sic_to_fama_french

    assert sic_to_fama_french(6020) == "Banks"
    assert sic_to_fama_french(3674) == "Chips"
    assert sic_to_fama_french(2834) == "Drugs"
    assert sic_to_fama_french(3711) == "Autos"
    assert sic_to_fama_french(9999) is None


def test_standardization_cache_set_industry():
    """StandardizationCache.set_industry_from_sic converts SIC to FF48."""
    from edgar.xbrl.standardization.cache import StandardizationCache
    from unittest.mock import MagicMock

    cache = StandardizationCache(MagicMock())
    assert cache.industry is None

    result = cache.set_industry_from_sic("6020")
    assert result == "Banks"
    assert cache.industry == "Banks"

    result = cache.set_industry_from_sic(None)
    assert result is None
    assert cache.industry is None


def test_ifrs_tag_standardization():
    """IFRS tags (ifrs-full_ prefix) resolve to standard concepts."""
    from edgar.xbrl.standardization.reverse_index import ReverseIndex

    idx = ReverseIndex()

    # Income statement
    assert idx.get_standard_concept("ifrs-full_Revenue") == "Revenue"
    assert idx.get_standard_concept("ifrs-full_CostOfSales") == "CostOfGoodsAndServicesSold"
    assert idx.get_standard_concept("ifrs-full_GrossProfit") == "GrossProfit"
    assert idx.get_standard_concept("ifrs-full_ProfitLossBeforeTax") == "PretaxIncomeLoss"
    assert idx.get_standard_concept("ifrs-full_ProfitLoss") == "ProfitLoss"
    assert idx.get_standard_concept("ifrs-full_ProfitLossFromOperatingActivities") == "OperatingIncomeLoss"
    assert idx.get_standard_concept("ifrs-full_ResearchAndDevelopmentExpense") == "ResearchAndDevelopementExpenses"

    # Balance sheet
    assert idx.get_standard_concept("ifrs-full_Assets") == "Assets"
    assert idx.get_standard_concept("ifrs-full_CurrentAssets") == "CurrentAssetsTotal"
    assert idx.get_standard_concept("ifrs-full_NoncurrentAssets") == "NonCurrentAssetsTotal"
    assert idx.get_standard_concept("ifrs-full_Liabilities") == "Liabilities"
    assert idx.get_standard_concept("ifrs-full_Equity") == "AllEquityBalanceIncludingMinorityInterest"
    assert idx.get_standard_concept("ifrs-full_RetainedEarnings") == "RetainedEarnings"
    assert idx.get_standard_concept("ifrs-full_Goodwill") == "Goodwill"
    assert idx.get_standard_concept("ifrs-full_PropertyPlantAndEquipment") == "PlantPropertyEquipmentNet"

    # Cash flow
    assert idx.get_standard_concept("ifrs-full_CashFlowsFromUsedInOperatingActivities") == "NetCashFromOperatingActivities"
    assert idx.get_standard_concept("ifrs-full_CashFlowsFromUsedInInvestingActivities") == "NetCashFromInvestingActivities"
    assert idx.get_standard_concept("ifrs-full_CashFlowsFromUsedInFinancingActivities") == "NetCashFromFinancingActivities"
    assert idx.get_standard_concept("ifrs-full_DividendsPaidClassifiedAsFinancingActivities") == "CommonDividendsPaid"

    # EPS
    assert idx.get_standard_concept("ifrs-full_BasicEarningsLossPerShare") == "EarningsPerShareBasic"
    assert idx.get_standard_concept("ifrs-full_DilutedEarningsLossPerShare") == "EarningsPerShareDiluted"

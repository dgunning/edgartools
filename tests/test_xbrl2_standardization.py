import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from edgar.xbrl2.standardization import (
    StandardConcept, MappingStore, ConceptMapper, 
    standardize_statement, initialize_default_mappings
)


@pytest.fixture
def temp_mapping_store():
    """Fixture for creating and cleaning up a temporary MappingStore."""
    store = MappingStore(source="test_mapping.json")
    yield store
    if os.path.exists("test_mapping.json"):
        os.remove("test_mapping.json")


def test_standard_concepts():
    """Test that standard concepts are defined properly."""
    assert StandardConcept.REVENUE.value == "Revenue"
    assert StandardConcept.NET_INCOME.value == "Net Income"
    assert StandardConcept.TOTAL_ASSETS.value == "Total Assets"


def test_mapping_store_add_get(temp_mapping_store):
    """Test adding and retrieving mappings."""
    store = temp_mapping_store
    
    # Add mappings
    store.add("us-gaap_Revenue", StandardConcept.REVENUE.value)
    store.add("us-gaap_NetIncome", StandardConcept.NET_INCOME.value)
    
    # Verify mappings
    assert store.get_standard_concept("us-gaap_Revenue") == StandardConcept.REVENUE.value
    assert store.get_standard_concept("us-gaap_NetIncome") == StandardConcept.NET_INCOME.value
    
    # Verify getting company concepts
    assert "us-gaap_Revenue" in store.get_company_concepts(StandardConcept.REVENUE.value)


def test_concept_mapper_direct_mapping(temp_mapping_store):
    """Test concept mapper with direct mappings."""
    store = temp_mapping_store
    store.add("us-gaap_Revenue", StandardConcept.REVENUE.value)
    
    # Create mapper
    mapper = ConceptMapper(store)
    
    # Test direct mapping
    result = mapper.map_concept("us-gaap_Revenue", "Revenue", {"statement_type": "IncomeStatement"})
    assert result == StandardConcept.REVENUE.value


def test_standardize_statement():
    """Test standardizing a statement."""
    # Create test statement data
    statement_data = [
        {
            "concept": "us-gaap_Revenue",
            "label": "Revenue",
            "statement_type": "IncomeStatement",
            "is_abstract": False
        },
        {
            "concept": "us-gaap_CostOfGoodsSold",
            "label": "Cost of Sales",
            "statement_type": "IncomeStatement",
            "is_abstract": False
        }
    ]
    
    # Create mapper with mock behavior
    mapper = MagicMock()
    mapper.map_concept.side_effect = [
        "Revenue", 
        "Cost of Revenue"
    ]
    
    # Standardize the statement
    result = standardize_statement(statement_data, mapper)
    
    # Verify labels are updated
    assert result[0]["label"] == "Revenue"
    assert result[1]["label"] == "Cost of Revenue"
    
    # Verify original labels are preserved
    assert result[0]["original_label"] == "Revenue"
    assert result[1]["original_label"] == "Cost of Sales"


def test_initialize_default_mappings():
    """Test initializing default mappings."""
    store = initialize_default_mappings()
    
    # Verify some default mappings
    assert store.get_standard_concept("us-gaap_Revenue") == "Revenue"
    assert store.get_standard_concept("us-gaap_NetIncome") == "Net Income"
    assert store.get_standard_concept("us-gaap_Assets") == "Total Assets"
    assert store.get_standard_concept("us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect") == "Net Change in Cash"
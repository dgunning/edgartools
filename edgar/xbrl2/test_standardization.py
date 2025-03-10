"""
Tests for the standardization module.

This module contains test cases for the XBRL concept standardization functionality.
"""

import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from edgar.xbrl2.standardization import (
    StandardConcept, MappingStore, ConceptMapper, 
    standardize_statement, initialize_default_mappings
)


class TestStandardization(unittest.TestCase):
    """Test cases for the standardization module."""
    
    def test_standard_concepts(self):
        """Test that standard concepts are defined properly."""
        # Verify revenue concept is defined
        self.assertEqual(StandardConcept.REVENUE.value, "Revenue")
        self.assertEqual(StandardConcept.NET_INCOME.value, "Net Income")
        self.assertEqual(StandardConcept.TOTAL_ASSETS.value, "Total Assets")
    
    def test_mapping_store_add_get(self):
        """Test adding and retrieving mappings."""
        # Create a temporary mapping store
        store = MappingStore(source="test_mapping.json")
        
        # Add mappings
        store.add("us-gaap_Revenue", StandardConcept.REVENUE.value)
        store.add("us-gaap_NetIncome", StandardConcept.NET_INCOME.value)
        
        # Verify mappings
        self.assertEqual(store.get_standard_concept("us-gaap_Revenue"), StandardConcept.REVENUE.value)
        self.assertEqual(store.get_standard_concept("us-gaap_NetIncome"), StandardConcept.NET_INCOME.value)
        
        # Verify getting company concepts
        self.assertIn("us-gaap_Revenue", store.get_company_concepts(StandardConcept.REVENUE.value))
        
        # Clean up
        os.remove("test_mapping.json")
    
    def test_concept_mapper_direct_mapping(self):
        """Test concept mapper with direct mappings."""
        # Create a store with known mappings
        store = MappingStore(source="test_mapping.json")
        store.add("us-gaap_Revenue", StandardConcept.REVENUE.value)
        
        # Create mapper
        mapper = ConceptMapper(store)
        
        # Test direct mapping
        result = mapper.map_concept("us-gaap_Revenue", "Revenue", {"statement_type": "IncomeStatement"})
        self.assertEqual(result, StandardConcept.REVENUE.value)
        
        # Clean up
        os.remove("test_mapping.json")
    
    def test_concept_mapper_inference(self):
        """Test concept mapper with inference."""
        # Create an empty store
        store = MappingStore(source="test_mapping.json")
        
        # Create mapper
        mapper = ConceptMapper(store)
        
        # Test label similarity inference with high confidence
        with patch.object(mapper, '_infer_mapping', return_value=(StandardConcept.REVENUE.value, 0.95)):
            result = mapper.map_concept("us-gaap_Revenues", "Total Revenues", {"statement_type": "IncomeStatement"})
            self.assertEqual(result, StandardConcept.REVENUE.value)
        
        # Test low confidence inference (should return None)
        with patch.object(mapper, '_infer_mapping', return_value=(StandardConcept.REVENUE.value, 0.5)):
            result = mapper.map_concept("us-gaap_Revenues", "Total Revenues", {"statement_type": "IncomeStatement"})
            self.assertIsNone(result)
        
        # Clean up
        if os.path.exists("test_mapping.json"):
            os.remove("test_mapping.json")
    
    def test_standardize_statement(self):
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
        self.assertEqual(result[0]["label"], "Revenue")
        self.assertEqual(result[1]["label"], "Cost of Revenue")
        
        # Verify original labels are preserved
        self.assertEqual(result[0]["original_label"], "Revenue")
        self.assertEqual(result[1]["original_label"], "Cost of Sales")
    
    def test_initialize_default_mappings(self):
        """Test initializing default mappings."""
        store = initialize_default_mappings()
        
        # Verify some default mappings
        self.assertEqual(store.get_standard_concept("us-gaap_Revenue"), "Revenue")
        self.assertEqual(store.get_standard_concept("us-gaap_NetIncome"), "Net Income")
        self.assertEqual(store.get_standard_concept("us-gaap_Assets"), "Total Assets")


if __name__ == "__main__":
    unittest.main()
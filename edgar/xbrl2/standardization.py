"""
Module for standardizing XBRL concepts across different company filings.

This module provides functionality to map company-specific XBRL concepts
to standardized concept names, enabling consistent presentation of financial
statements regardless of the filing entity.
"""

import json
import os
from enum import Enum
from json import JSONDecodeError
from typing import Dict, List, Optional, Set, Tuple, Any
from difflib import SequenceMatcher


class StandardConcept(str, Enum):
    """Standardized concept names for financial statements."""
    # Balance Sheet - Assets
    CASH_AND_EQUIVALENTS = "Cash and Cash Equivalents"
    ACCOUNTS_RECEIVABLE = "Accounts Receivable"
    INVENTORY = "Inventory"
    PREPAID_EXPENSES = "Prepaid Expenses"
    TOTAL_CURRENT_ASSETS = "Total Current Assets"
    PROPERTY_PLANT_EQUIPMENT = "Property, Plant and Equipment"
    GOODWILL = "Goodwill"
    INTANGIBLE_ASSETS = "Intangible Assets"
    TOTAL_ASSETS = "Total Assets"
    
    # Balance Sheet - Liabilities
    ACCOUNTS_PAYABLE = "Accounts Payable"
    ACCRUED_LIABILITIES = "Accrued Liabilities"
    SHORT_TERM_DEBT = "Short-Term Debt"
    TOTAL_CURRENT_LIABILITIES = "Total Current Liabilities"
    LONG_TERM_DEBT = "Long-Term Debt"
    DEFERRED_REVENUE = "Deferred Revenue"
    TOTAL_LIABILITIES = "Total Liabilities"
    
    # Balance Sheet - Equity
    COMMON_STOCK = "Common Stock"
    RETAINED_EARNINGS = "Retained Earnings"
    TOTAL_EQUITY = "Total Stockholders' Equity"
    
    # Income Statement
    REVENUE = "Revenue"
    COST_OF_REVENUE = "Cost of Revenue"
    GROSS_PROFIT = "Gross Profit"
    OPERATING_EXPENSES = "Operating Expenses"
    RESEARCH_AND_DEVELOPMENT = "Research and Development Expense"
    SELLING_GENERAL_ADMIN = "Selling, General and Administrative Expense"
    OPERATING_INCOME = "Operating Income"
    INTEREST_EXPENSE = "Interest Expense"
    INCOME_BEFORE_TAX = "Income Before Tax"
    INCOME_TAX_EXPENSE = "Income Tax Expense"
    NET_INCOME = "Net Income"
    
    # Cash Flow Statement
    CASH_FROM_OPERATIONS = "Net Cash from Operating Activities"
    CASH_FROM_INVESTING = "Net Cash from Investing Activities"
    CASH_FROM_FINANCING = "Net Cash from Financing Activities"
    NET_CHANGE_IN_CASH = "Net Change in Cash"


class MappingStore:
    """
    Storage for mappings between company-specific concepts and standard concepts.
    
    Attributes:
        source (str): Path to the JSON file storing the mappings
        mappings (Dict[str, Set[str]]): Dictionary mapping standard concepts to sets of company concepts
    """
    
    def __init__(self, source: Optional[str] = None):
        """
        Initialize the mapping store.
        
        Args:
            source: Path to the JSON file storing the mappings. If None, uses default location.
        """
        if source is None:
            # Default to a file in the same directory as this module
            module_dir = os.path.dirname(os.path.abspath(__file__))
            self.source = os.path.join(module_dir, "data", "concept_mappings.json")
        else:
            self.source = source
            
        self.mappings = self._load_mappings()

    def _load_mappings(self) -> Dict[str, Set[str]]:
        """
        Load mappings from the JSON file.
        
        Returns:
            Dictionary mapping standard concepts to sets of company concepts
        """
        try:
            with open(self.source, 'r') as f:
                data = json.load(f)
                
                # Check if the structure is flat or nested
                if any(isinstance(value, dict) for value in data.values()):
                    # Nested structure by statement type
                    flattened = {}
                    for statement_type, concepts in data.items():
                        for standard_concept, company_concepts in concepts.items():
                            flattened[standard_concept] = set(company_concepts)
                    return flattened
                else:
                    # Flat structure
                    return {k: set(v) for k, v in data.items()}

        except JSONDecodeError as e:
            raise
        except FileNotFoundError:
            # Return default mappings if file doesn't exist or is invalid
            return {
                "Revenue": {"us-gaap_SalesRevenueNet", "us-gaap_Revenue", "us-gaap_Revenues"},
                "Net Income": {"us-gaap_NetIncome", "us-gaap_NetIncomeLoss", "us-gaap_ProfitLoss"},
                "Total Assets": {"us-gaap_Assets", "us-gaap_AssetsTotal"}
            }
    
    def _save_mappings(self) -> None:
        """Save mappings to the JSON file."""
        # Ensure directory exists
        directory = os.path.dirname(self.source)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        # Convert sets to lists for JSON serialization
        serializable_mappings = {k: list(v) for k, v in self.mappings.items()}
        
        with open(self.source, 'w') as f:
            json.dump(serializable_mappings, f, indent=2)
    
    def add(self, company_concept: str, standard_concept: str) -> None:
        """
        Add a mapping from a company concept to a standard concept.
        
        Args:
            company_concept: The company-specific concept
            standard_concept: The standard concept
        """
        if standard_concept not in self.mappings:
            self.mappings[standard_concept] = set()
        
        self.mappings[standard_concept].add(company_concept)
        self._save_mappings()
    
    def get_standard_concept(self, company_concept: str) -> Optional[str]:
        """
        Get the standard concept for a given company concept.
        
        Args:
            company_concept: The company-specific concept
            
        Returns:
            The standard concept or None if not found
        """
        for standard_concept, company_concepts in self.mappings.items():
            if company_concept in company_concepts:
                return standard_concept
        return None
    
    def get_company_concepts(self, standard_concept: str) -> Set[str]:
        """
        Get all company concepts mapped to a standard concept.
        
        Args:
            standard_concept: The standard concept
            
        Returns:
            Set of company concepts mapped to the standard concept
        """
        return self.mappings.get(standard_concept, set())


class ConceptMapper:
    """
    Maps company-specific concepts to standard concepts using various techniques.
    
    Attributes:
        mapping_store (MappingStore): Storage for concept mappings
        pending_mappings (Dict): Low-confidence mappings pending review
    """
    
    def __init__(self, mapping_store: MappingStore):
        """
        Initialize the concept mapper.
        
        Args:
            mapping_store: Storage for concept mappings
        """
        self.mapping_store = mapping_store
        self.pending_mappings = {}
    
    def map_concept(self, company_concept: str, label: str, context: Dict[str, Any]) -> Optional[str]:
        """
        Map a company concept to a standard concept.
        
        Args:
            company_concept: The company-specific concept
            label: The label for the concept
            context: Additional context information (statement type, calculation relationships, etc.)
            
        Returns:
            The standard concept or None if no mapping found
        """
        # Check if we already have a mapping
        standard_concept = self.mapping_store.get_standard_concept(company_concept)
        if standard_concept:
            return standard_concept
        
        # Infer mapping and confidence
        inferred_concept, confidence = self._infer_mapping(company_concept, label, context)
        
        # Only use high-confidence mappings
        if confidence >= 0.9:
            return inferred_concept
            
        return None
    
    def _infer_mapping(self, company_concept: str, label: str, context: Dict[str, Any]) -> Tuple[Optional[str], float]:
        """
        Infer a mapping between a company concept and a standard concept.
        
        Args:
            company_concept: The company-specific concept
            label: The label for the concept
            context: Additional context information
            
        Returns:
            Tuple of (standard_concept, confidence)
        """
        # Direct label similarity
        best_match = None
        best_score = 0
        
        # Compare with all standard concepts
        for std_concept in StandardConcept:
            # Calculate similarity between labels
            similarity = SequenceMatcher(None, label.lower(), std_concept.value.lower()).ratio()
            
            # Check if this is the best match so far
            if similarity > best_score:
                best_score = similarity
                best_match = std_concept.value
        
        # Apply contextual rules to boost confidence
        statement_type = context.get("statement_type", "")
        
        # Adjust confidence based on statement type
        if statement_type == "BalanceSheet":
            if "assets" in label.lower() and "total" in label.lower():
                if best_match == StandardConcept.TOTAL_ASSETS.value:
                    best_score = min(1.0, best_score + 0.2)
        
        elif statement_type == "IncomeStatement":
            if any(term in label.lower() for term in ["revenue", "sales"]):
                if best_match == StandardConcept.REVENUE.value:
                    best_score = min(1.0, best_score + 0.2)
        
        # If confidence is too low, return None
        if best_score < 0.5:
            return None, 0.0
            
        return best_match, best_score
    
    def learn_mappings(self, filings: List[Dict[str, Any]]) -> None:
        """
        Learn mappings from a list of filings.
        
        Args:
            filings: List of dicts with XBRL data
        """
        for filing in filings:
            concept = filing["concept"]
            label = filing["label"]
            context = {
                "statement_type": filing.get("statement_type", ""),
                "calculation_parent": filing.get("calculation_parent", ""),
                "position": filing.get("position", "")
            }
            
            # Skip if already mapped
            if self.mapping_store.get_standard_concept(concept):
                continue
            
            # Infer mapping and confidence
            standard_concept, confidence = self._infer_mapping(concept, label, context)
            
            # Handle based on confidence
            if standard_concept and confidence >= 0.9:
                self.mapping_store.add(concept, standard_concept)
            elif standard_concept and confidence >= 0.5:
                if standard_concept not in self.pending_mappings:
                    self.pending_mappings[standard_concept] = []
                self.pending_mappings[standard_concept].append((concept, confidence, label))
    
    def save_pending_mappings(self, destination: str) -> None:
        """
        Save pending mappings to a file.
        
        Args:
            destination: Path to save the pending mappings
        """
        # Convert tuples to lists for JSON serialization
        serializable_mappings = {}
        for std_concept, mappings in self.pending_mappings.items():
            serializable_mappings[std_concept] = [
                {"concept": c, "confidence": conf, "label": lbl} 
                for c, conf, lbl in mappings
            ]
            
        with open(destination, 'w') as f:
            json.dump(serializable_mappings, f, indent=2)


def standardize_statement(statement_data: List[Dict[str, Any]], mapper: ConceptMapper) -> List[Dict[str, Any]]:
    """
    Standardize labels in a statement using the concept mapper.
    
    Args:
        statement_data: List of statement line items
        mapper: ConceptMapper instance
        
    Returns:
        Statement data with standardized labels where possible
    """
    standardized_data = []
    
    for item in statement_data:
        # Create a copy of the item to modify
        standardized_item = item.copy()
        
        # Skip standardization for abstract elements
        if item.get("is_abstract", False):
            standardized_data.append(standardized_item)
            continue
        
        concept = item.get("concept", "")
        label = item.get("label", "")
        context = {
            "statement_type": item.get("statement_type", ""),
            "level": item.get("level", 0),
            "is_total": "total" in label.lower() or item.get("is_total", False)
        }
        
        # Try to map the concept
        standard_label = mapper.map_concept(concept, label, context)
        
        # Update the label if we found a mapping
        if standard_label:
            standardized_item["label"] = standard_label
            standardized_item["original_label"] = label
        
        standardized_data.append(standardized_item)
    
    return standardized_data


# Initialize with default mappings for common concepts
def initialize_default_mappings() -> MappingStore:
    """
    Initialize a MappingStore with default mappings for common concepts.
    If a mappings file exists, it will be loaded; otherwise, these defaults are used.
    
    Returns:
        MappingStore initialized with default mappings
    """
    store = MappingStore()
    
    # Only add default mappings if the file doesn't exist
    if not os.path.exists(store.source):
        # Common US-GAAP mappings
        default_mappings = {
            # Income Statement
            StandardConcept.REVENUE.value: [
                "us-gaap_Revenue", 
                "us-gaap_SalesRevenueNet",
                "us-gaap_Revenues",
                "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                "us-gaap_SalesRevenueGoodsNet"
            ],
            StandardConcept.COST_OF_REVENUE.value: [
                "us-gaap_CostOfRevenue",
                "us-gaap_CostOfGoodsAndServicesSold",
                "us-gaap_CostOfGoodsSold"
            ],
            StandardConcept.GROSS_PROFIT.value: [
                "us-gaap_GrossProfit"
            ],
            StandardConcept.OPERATING_INCOME.value: [
                "us-gaap_OperatingIncome",
                "us-gaap_OperatingIncomeLoss"
            ],
            StandardConcept.NET_INCOME.value: [
                "us-gaap_NetIncome",
                "us-gaap_NetIncomeLoss",
                "us-gaap_ProfitLoss"
            ],
            
            # Balance Sheet
            StandardConcept.CASH_AND_EQUIVALENTS.value: [
                "us-gaap_CashAndCashEquivalentsAtCarryingValue",
                "us-gaap_Cash",
                "us-gaap_CashEquivalentsAtCarryingValue"
            ],
            StandardConcept.TOTAL_ASSETS.value: [
                "us-gaap_Assets",
                "us-gaap_AssetsTotal"
            ],
            StandardConcept.TOTAL_CURRENT_ASSETS.value: [
                "us-gaap_AssetsCurrent"
            ],
            StandardConcept.TOTAL_LIABILITIES.value: [
                "us-gaap_Liabilities",
                "us-gaap_LiabilitiesTotal"
            ],
            StandardConcept.TOTAL_CURRENT_LIABILITIES.value: [
                "us-gaap_LiabilitiesCurrent"
            ],
            StandardConcept.TOTAL_EQUITY.value: [
                "us-gaap_StockholdersEquity",
                "us-gaap_StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
            ],
            
            # Cash Flow
            StandardConcept.CASH_FROM_OPERATIONS.value: [
                "us-gaap_NetCashProvidedByUsedInOperatingActivities",
                "us-gaap_NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"
            ],
            StandardConcept.NET_CHANGE_IN_CASH.value: [
                "us-gaap_CashAndCashEquivalentsPeriodIncreaseDecrease",
                "us-gaap_IncreaseDecreaseInCashAndCashEquivalents"
            ]
        }
        
        # Add each mapping to the store
        for standard_concept, company_concepts in default_mappings.items():
            for company_concept in company_concepts:
                store.add(company_concept, standard_concept)
    
    return store
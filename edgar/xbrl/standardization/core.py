"""
Module for standardizing XBRL concepts across different company filings.

This module provides functionality to map company-specific XBRL concepts
to standardized concept names, enabling consistent presentation of financial
statements regardless of the filing entity.
"""

import json
import os
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd


class StandardConcept(str, Enum):
    """
    Standardized concept names for financial statements.
    
    The enum value (string) is the display label used for presentation.
    These labels should match keys in concept_mappings.json.
    """
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
    
    @classmethod
    def get_from_label(cls, label: str) -> Optional['StandardConcept']:
        """
        Get a StandardConcept enum by its label value.
        
        Args:
            label: The label string to look up
            
        Returns:
            The corresponding StandardConcept or None if not found
        """
        for concept in cls:
            if concept.value == label:
                return concept
        return None
    
    @classmethod
    def get_all_values(cls) -> Set[str]:
        """
        Get all label values defined in the enum.
        
        Returns:
            Set of all label strings
        """
        return {concept.value for concept in cls}


class MappingStore:
    """
    Storage for mappings between company-specific concepts and standard concepts.
    
    Attributes:
        source (str): Path to the JSON file storing the mappings
        mappings (Dict[str, Set[str]]): Dictionary mapping standard concepts to sets of company concepts
    """
    
    def __init__(self, source: Optional[str] = None, validate_with_enum: bool = False, read_only: bool = False):
        """
        Initialize the mapping store.
        
        Args:
            source: Path to the JSON file storing the mappings. If None, uses default location.
            validate_with_enum: Whether to validate JSON keys against StandardConcept enum
            read_only: If True, never save changes back to the file (used in testing)
        """
        self.read_only = read_only
        
        if source is None:
            # Try a few different ways to locate the file, handling both development
            # and installed package scenarios
            self.source = None
            
            # Default to a file in the same directory as this module (development mode)
            module_dir = os.path.dirname(os.path.abspath(__file__))
            potential_path = os.path.join(module_dir, "concept_mappings.json")
            if os.path.exists(potential_path):
                self.source = potential_path
            
            # If not found, try to load from package data (installed package)
            if self.source is None:
                try:
                    import importlib.resources as pkg_resources
                    try:
                        # For Python 3.9+
                        with pkg_resources.files('edgar.xbrl2.standardization').joinpath('concept_mappings.json').open('r') as f:
                            # Just read the file to see if it exists, we'll load it properly later
                            f.read(1)
                            self.source = potential_path  # Use the same path as before
                    except (ImportError, FileNotFoundError, AttributeError):
                        # Fallback for older Python versions
                        try:
                            import pkg_resources as legacy_resources
                            if legacy_resources.resource_exists('edgar.xbrl2.standardization', 'concept_mappings.json'):
                                self.source = potential_path  # Use the same path as before
                        except (ImportError, FileNotFoundError):
                            pass
                except ImportError:
                    pass
            
            # If we still haven't found the file, use the default path anyway
            # (it will fail gracefully in _load_mappings)
            if self.source is None:
                self.source = potential_path
        else:
            self.source = source
            
        self.mappings = self._load_mappings()
        
        # Validate the loaded mappings against StandardConcept enum
        if validate_with_enum:
            self.validate_against_enum()
    
    def validate_against_enum(self) -> Tuple[bool, List[str]]:
        """
        Validate that all keys in the mappings exist in StandardConcept enum.
        
        Returns:
            Tuple of (is_valid, list_of_missing_keys)
        """
        standard_values = StandardConcept.get_all_values()
        json_keys = set(self.mappings.keys())
        
        # Find keys in JSON that aren't in enum
        missing_in_enum = json_keys - standard_values
        
        # Find enum values not in JSON (just for information)
        missing_in_json = standard_values - json_keys
        
        import logging
        logger = logging.getLogger(__name__)
        
        if missing_in_enum:
            logger.warning(f"Found {len(missing_in_enum)} keys in concept_mappings.json that don't exist in StandardConcept enum: {sorted(missing_in_enum)}")
        
        if missing_in_json:
            logger.info(f"Found {len(missing_in_json)} StandardConcept values without mappings in concept_mappings.json: {sorted(missing_in_json)}")
        
        return len(missing_in_enum) == 0, list(missing_in_enum)
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert mappings to a pandas DataFrame for analysis and visualization.
        
        Returns:
            DataFrame with columns for standard_concept and company_concept
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for to_dataframe() but is not installed")
        
        rows = []
        for standard_concept, company_concepts in self.mappings.items():
            for company_concept in company_concepts:
                rows.append({
                    'standard_concept': standard_concept,
                    'company_concept': company_concept
                })
        
        return pd.DataFrame(rows)

    def _load_mappings(self) -> Dict[str, Set[str]]:
        """
        Load mappings from the JSON file.
        
        Returns:
            Dictionary mapping standard concepts to sets of company concepts
        """
        data = None
        
        # First try direct file access
        try:
            with open(self.source, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, IOError, PermissionError):
            # If direct file access fails, try package resources
            try:
                try:
                    # Modern importlib.resources approach (Python 3.9+)
                    import importlib.resources as pkg_resources
                    try:
                        # For Python 3.9+
                        with pkg_resources.files('edgar.xbrl2.standardization').joinpath('concept_mappings.json').open('r') as f:
                            data = json.load(f)
                    except (ImportError, FileNotFoundError, AttributeError):
                        # Fallback to legacy pkg_resources
                        import pkg_resources as legacy_resources
                        resource_string = legacy_resources.resource_string('edgar.xbrl2.standardization', 'concept_mappings.json')
                        data = json.loads(resource_string)
                except ImportError:
                    pass
            except Exception:
                # If all attempts fail, log a warning
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("Could not load concept_mappings.json. Standardization will be limited.")
        
        # If we have data, process it based on its structure
        if data:
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
        
        # If all methods fail, return empty mappings
        # The initialize_default_mappings function will create a file if needed
        return {}
    
    def _save_mappings(self) -> None:
        """Save mappings to the JSON file, unless in read_only mode."""
        # Skip saving if in read_only mode
        if self.read_only:
            return
            
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
        _cache (Dict): In-memory cache of mapped concepts
    """
    
    def __init__(self, mapping_store: MappingStore):
        """
        Initialize the concept mapper.
        
        Args:
            mapping_store: Storage for concept mappings
        """
        self.mapping_store = mapping_store
        self.pending_mappings = {}
        # Cache for faster lookups of previously mapped concepts
        self._cache = {}
        # Precompute lowercased standard concept values for faster comparison
        self._std_concept_values = [(concept, concept.value.lower()) for concept in StandardConcept]
        
        # Statement-specific keyword sets for faster contextual matching
        self._bs_keywords = {'assets', 'liabilities', 'equity', 'cash', 'debt', 'inventory', 'receivable', 'payable'}
        self._is_keywords = {'revenue', 'sales', 'income', 'expense', 'profit', 'loss', 'tax', 'earnings'}
        self._cf_keywords = {'cash', 'operating', 'investing', 'financing', 'activities'}
        
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
        # Use cache for faster lookups
        cache_key = (company_concept, context.get('statement_type', ''))
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Check if we already have a mapping in the store
        standard_concept = self.mapping_store.get_standard_concept(company_concept)
        if standard_concept:
            self._cache[cache_key] = standard_concept
            return standard_concept
        
        # Infer mapping and confidence
        inferred_concept, confidence = self._infer_mapping(company_concept, label, context)
        
        # Only use high-confidence mappings
        if confidence >= 0.9:
            # Cache the result for future lookups
            self._cache[cache_key] = inferred_concept
            return inferred_concept
            
        # Cache negative results too to avoid repeated inference
        self._cache[cache_key] = None
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
        # Fast path for common patterns
        label_lower = label.lower()
        
        # Quick matching for common concepts without full sequence matching
        if "total assets" in label_lower:
            return StandardConcept.TOTAL_ASSETS.value, 0.95
        elif "revenue" in label_lower and len(label_lower) < 30:  # Only match short labels to avoid false positives
            return StandardConcept.REVENUE.value, 0.9
        elif "net income" in label_lower and "parent" not in label_lower:
            return StandardConcept.NET_INCOME.value, 0.9
        
        # Faster direct match checking with precomputed lowercase values
        for std_concept, std_value_lower in self._std_concept_values:
            if std_value_lower == label_lower:
                return std_concept.value, 1.0  # Perfect match
        
        # Fall back to sequence matching for similarity
        best_match = None
        best_score = 0
        
        # Only compute similarity if some relevant keywords are present to reduce workload
        statement_type = context.get("statement_type", "")
        
        # Statement type based filtering to reduce unnecessary comparisons
        limited_concepts = []
        if statement_type == "BalanceSheet":
            if any(kw in label_lower for kw in self._bs_keywords):
                # Filter to balance sheet concepts only
                limited_concepts = [c for c, v in self._std_concept_values 
                                  if any(kw in v for kw in self._bs_keywords)]
        elif statement_type == "IncomeStatement":
            if any(kw in label_lower for kw in self._is_keywords):
                # Filter to income statement concepts only
                limited_concepts = [c for c, v in self._std_concept_values 
                                  if any(kw in v for kw in self._is_keywords)]
        elif statement_type == "CashFlowStatement":
            if any(kw in label_lower for kw in self._cf_keywords):
                # Filter to cash flow concepts only
                limited_concepts = [c for c, v in self._std_concept_values 
                                  if any(kw in v for kw in self._cf_keywords)]
        
        # Use limited concepts if available, otherwise use all
        concepts_to_check = limited_concepts if limited_concepts else [c for c, _ in self._std_concept_values]
        
        # Calculate similarities for candidate concepts
        for std_concept in concepts_to_check:
            # Calculate similarity between labels
            similarity = SequenceMatcher(None, label_lower, std_concept.value.lower()).ratio()
            
            # Check if this is the best match so far
            if similarity > best_score:
                best_score = similarity
                best_match = std_concept.value
        
        # Apply specific contextual rules based on statement type
        if statement_type == "BalanceSheet":
            if "assets" in label_lower and "total" in label_lower:
                if best_match == StandardConcept.TOTAL_ASSETS.value:
                    best_score = min(1.0, best_score + 0.2)
            elif "liabilities" in label_lower and "total" in label_lower:
                if best_match == StandardConcept.TOTAL_LIABILITIES.value:
                    best_score = min(1.0, best_score + 0.2)
            elif "equity" in label_lower and ("total" in label_lower or "stockholders" in label_lower):
                if best_match == StandardConcept.TOTAL_EQUITY.value:
                    best_score = min(1.0, best_score + 0.2)
        
        elif statement_type == "IncomeStatement":
            if any(term in label_lower for term in ["revenue", "sales"]):
                if best_match == StandardConcept.REVENUE.value:
                    best_score = min(1.0, best_score + 0.2)
            elif "net income" in label_lower:
                if best_match == StandardConcept.NET_INCOME.value:
                    best_score = min(1.0, best_score + 0.2)
        
        # Promote to 0.5 confidence if score close enough to help match
        # more items that are almost at threshold
        if 0.45 <= best_score < 0.5:
            best_score = 0.5
            
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
        # Pre-filter to only process unmapped concepts
        mapped_concepts = set()
        for std_concept, company_concepts in self.mapping_store.mappings.items():
            mapped_concepts.update(company_concepts)
        
        # Process only unmapped filings
        unmapped_filings = [f for f in filings if f.get("concept") not in mapped_concepts]
        
        # Create a batch of mappings to add
        mappings_to_add = {}
        
        for filing in unmapped_filings:
            concept = filing["concept"]
            label = filing["label"]
            context = {
                "statement_type": filing.get("statement_type", ""),
                "calculation_parent": filing.get("calculation_parent", ""),
                "position": filing.get("position", "")
            }
            
            # Infer mapping and confidence
            standard_concept, confidence = self._infer_mapping(concept, label, context)
            
            # Handle based on confidence
            if standard_concept and confidence >= 0.9:
                if standard_concept not in mappings_to_add:
                    mappings_to_add[standard_concept] = set()
                mappings_to_add[standard_concept].add(concept)
            elif standard_concept and confidence >= 0.5:
                if standard_concept not in self.pending_mappings:
                    self.pending_mappings[standard_concept] = []
                self.pending_mappings[standard_concept].append((concept, confidence, label))
        
        # Batch add all mappings at once
        for std_concept, concepts in mappings_to_add.items():
            for concept in concepts:
                self.mapping_store.add(concept, std_concept)
                # Update cache
                cache_key = (concept, filing.get("statement_type", ""))
                self._cache[cache_key] = std_concept
    
    def save_pending_mappings(self, destination: str) -> None:
        """
        Save pending mappings to a file.
        
        Args:
            destination: Path to save the pending mappings
        """
        # Convert to serializable format
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
    # Pre-filter to identify which items need standardization
    # This avoids unnecessary copying and processing
    items_to_standardize = []
    statement_type = statement_data[0].get("statement_type", "") if statement_data else ""
    
    # First pass - identify which items need standardization and prepare context
    for i, item in enumerate(statement_data):
        # Skip abstract elements and dimensions as they don't need standardization
        if item.get("is_abstract", False) or item.get("is_dimension", False):
            continue
            
        concept = item.get("concept", "")
        if not concept:
            continue
            
        label = item.get("label", "")
        if not label:
            continue
            
        # Build minimal context once, reuse for multiple calls
        context = {
            "statement_type": item.get("statement_type", "") or statement_type,
            "level": item.get("level", 0),
            "is_total": "total" in label.lower() or item.get("is_total", False)
        }
        
        items_to_standardize.append((i, concept, label, context))
    
    # If no items need standardization, return early with unchanged data
    if not items_to_standardize:
        return statement_data
        
    # Second pass - create result list with standardized items
    result = []
    
    # Track which indices need standardization for faster lookup
    standardize_indices = {i for i, _, _, _ in items_to_standardize}
    
    # Process all items
    for i, item in enumerate(statement_data):
        if i not in standardize_indices:
            # Items that don't need standardization are used as-is
            result.append(item)
            continue
            
        # Get the prepared data for this item
        _, concept, label, context = next((x for x in items_to_standardize if x[0] == i), (None, None, None, None))
        
        # Try to map the concept
        standard_label = mapper.map_concept(concept, label, context)
        
        # If we found a mapping, create a modified copy
        if standard_label:
            # Create a shallow copy only when needed
            standardized_item = item.copy()
            standardized_item["label"] = standard_label
            standardized_item["original_label"] = label
            result.append(standardized_item)
        else:
            # No mapping found, use original item
            result.append(item)
    
    return result


def create_default_mappings_file(file_path: str) -> None:
    """
    Create the initial concept_mappings.json file with default mappings.
    This can be called during package installation or initialization.
    
    Args:
        file_path: Path where to create the file
    """
    # Ensure directory exists
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    # The file already exists, don't overwrite it
    if os.path.exists(file_path):
        return
        
    # Create a minimal set of mappings to get started
    minimal_mappings = {
        StandardConcept.REVENUE.value: [
            "us-gaap_Revenue", 
            "us-gaap_SalesRevenueNet",
            "us-gaap_Revenues"
        ],
        StandardConcept.NET_INCOME.value: [
            "us-gaap_NetIncome",
            "us-gaap_NetIncomeLoss", 
            "us-gaap_ProfitLoss"
        ],
        StandardConcept.TOTAL_ASSETS.value: [
            "us-gaap_Assets",
            "us-gaap_AssetsTotal"
        ]
    }
    
    # Write the file
    with open(file_path, 'w') as f:
        json.dump(minimal_mappings, f, indent=2)

# Initialize MappingStore - only loads from JSON
def initialize_default_mappings(read_only: bool = False) -> MappingStore:
    """
    Initialize a MappingStore with mappings from the concept_mappings.json file.
    
    Args:
        read_only: If True, prevent writing changes back to the file (used in testing)
    
    Returns:
        MappingStore initialized with mappings from JSON file
    """
    store = MappingStore(read_only=read_only)
    
    # If JSON file doesn't exist, create it with minimal default mappings
    # Only do this in non-read_only mode to avoid test-initiated file creation
    if not read_only and not os.path.exists(store.source):
        create_default_mappings_file(store.source)
    
    return store
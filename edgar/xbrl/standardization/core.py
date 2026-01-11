"""
Module for standardizing XBRL concepts across different company filings.

This module provides functionality to map company-specific XBRL concepts
to standardized concept names, enabling consistent presentation of financial
statements regardless of the filing entity.
"""

import json
import logging
import os
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

# Module-level logger (avoid creating logger inside hot paths)
logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependencies
_reverse_index = None


def _get_reverse_index():
    """Lazy load the reverse index singleton."""
    global _reverse_index
    if _reverse_index is None:
        from .reverse_index import ReverseIndex
        _reverse_index = ReverseIndex()
    return _reverse_index


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
    SHORT_TERM_DEBT = "Short Term Debt"
    TOTAL_CURRENT_LIABILITIES = "Total Current Liabilities"
    LONG_TERM_DEBT = "Long Term Debt"
    DEFERRED_REVENUE = "Deferred Revenue"
    TOTAL_LIABILITIES = "Total Liabilities"

    # Balance Sheet - Equity
    COMMON_STOCK = "Common Stock"
    RETAINED_EARNINGS = "Retained Earnings"
    TOTAL_EQUITY = "Total Stockholders' Equity"

    # Income Statement - Revenue Hierarchy
    REVENUE = "Revenue"
    CONTRACT_REVENUE = "Contract Revenue"
    PRODUCT_REVENUE = "Product Revenue"
    SERVICE_REVENUE = "Service Revenue"
    SUBSCRIPTION_REVENUE = "Subscription Revenue"
    LEASING_REVENUE = "Leasing Revenue"

    # Industry-Specific Revenue Concepts
    AUTOMOTIVE_REVENUE = "Automotive Revenue"
    AUTOMOTIVE_LEASING_REVENUE = "Automotive Leasing Revenue"
    ENERGY_REVENUE = "Energy Revenue"
    SOFTWARE_REVENUE = "Software Revenue"
    HARDWARE_REVENUE = "Hardware Revenue"
    PLATFORM_REVENUE = "Platform Revenue"

    # Income Statement - Expenses
    COST_OF_REVENUE = "Cost of Revenue"
    COST_OF_GOODS_SOLD = "Cost of Goods Sold"
    COST_OF_GOODS_AND_SERVICES_SOLD = "Cost of Goods and Services Sold"
    COST_OF_SALES = "Cost of Sales"
    COSTS_AND_EXPENSES = "Costs and Expenses"
    DIRECT_OPERATING_COSTS = "Direct Operating Costs"
    GROSS_PROFIT = "Gross Profit"
    OPERATING_EXPENSES = "Operating Expenses"
    RESEARCH_AND_DEVELOPMENT = "Research and Development Expense"

    # Enhanced Expense Hierarchy
    SELLING_GENERAL_ADMIN = "Selling, General and Administrative Expense"
    SELLING_EXPENSE = "Selling Expense"
    GENERAL_ADMIN_EXPENSE = "General and Administrative Expense"
    MARKETING_EXPENSE = "Marketing Expense"
    SALES_EXPENSE = "Sales Expense"

    # Other Income Statement
    OPERATING_INCOME = "Operating Income"
    INTEREST_EXPENSE = "Interest Expense"
    INCOME_BEFORE_TAX = "Income Before Tax"
    INCOME_BEFORE_TAX_CONTINUING_OPS = "Income Before Tax from Continuing Operations"
    INCOME_TAX_EXPENSE = "Income Tax Expense"
    NET_INCOME = "Net Income"
    NET_INCOME_CONTINUING_OPS = "Net Income from Continuing Operations"
    NET_INCOME_NONCONTROLLING = "Net Income Attributable to Noncontrolling Interest"
    PROFIT_OR_LOSS = "Profit or Loss"

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
        company_mappings (Dict[str, Dict]): Company-specific mappings loaded from company_mappings/
        merged_mappings (Dict[str, List[Tuple]]): Merged mappings with priority scoring
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
                        with pkg_resources.files('edgar.xbrl.standardization').joinpath('concept_mappings.json').open('r') as f:
                            # Just read the file to see if it exists, we'll load it properly later
                            f.read(1)
                            self.source = potential_path  # Use the same path as before
                    except (ImportError, FileNotFoundError, AttributeError):
                        # Fallback for older Python versions
                        try:
                            import pkg_resources as legacy_resources
                            if legacy_resources.resource_exists('edgar.xbrl.standardization', 'concept_mappings.json'):
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

        # Load company-specific mappings (always enabled)
        self.company_mappings = self._load_all_company_mappings()
        self.merged_mappings = self._create_merged_mappings()
        self.hierarchy_rules = self._load_hierarchy_rules()

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

        if missing_in_enum:
            logger.warning("Found %d keys in concept_mappings.json that don't exist in StandardConcept enum: %s", len(missing_in_enum), sorted(missing_in_enum))

        if missing_in_json:
            logger.info("Found %d StandardConcept values without mappings in concept_mappings.json: %s", len(missing_in_json), sorted(missing_in_json))

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
            raise ImportError("pandas is required for to_dataframe() but is not installed") from None

        rows = []
        for standard_concept, company_concepts in self.mappings.items():
            for company_concept in company_concepts:
                rows.append({
                    'standard_concept': standard_concept,
                    'company_concept': company_concept
                })

        return pd.DataFrame(rows)


    def _load_all_company_mappings(self) -> Dict[str, Dict]:
        """Load all company-specific mapping files from company_mappings/ directory."""
        mappings = {}
        company_dir = os.path.join(os.path.dirname(self.source or __file__), "company_mappings")

        if os.path.exists(company_dir):
            for file in os.listdir(company_dir):
                if file.endswith("_mappings.json"):
                    entity_id = file.replace("_mappings.json", "")
                    try:
                        with open(os.path.join(company_dir, file), 'r') as f:
                            company_data = json.load(f)
                            mappings[entity_id] = company_data
                    except (FileNotFoundError, json.JSONDecodeError) as e:
                        logger.warning("Failed to load %s: %s", file, e)

        return mappings

    def _create_merged_mappings(self) -> Dict[str, List[Tuple[str, str, int]]]:
        """Create merged mappings with priority scoring.

        Priority levels:
        1. Core mappings (lowest)
        2. Company mappings (higher)
        3. Company-specific matches (highest when company detected)

        Returns:
            Dict mapping standard concepts to list of (company_concept, source, priority) tuples
        """
        merged = {}

        # Add core mappings (priority 1 - lowest)
        for std_concept, company_concepts in self.mappings.items():
            merged[std_concept] = []
            for concept in company_concepts:
                merged[std_concept].append((concept, "core", 1))

        # Add company mappings (priority 2 - higher)
        for entity_id, company_data in self.company_mappings.items():
            concept_mappings = company_data.get("concept_mappings", {})
            priority_level = 2

            for std_concept, company_concepts in concept_mappings.items():
                if std_concept not in merged:
                    merged[std_concept] = []
                for concept in company_concepts:
                    merged[std_concept].append((concept, entity_id, priority_level))

        return merged

    def _load_hierarchy_rules(self) -> Dict[str, Dict]:
        """Load hierarchy rules from company mappings."""
        all_rules = {}

        # Add company hierarchy rules
        for _entity_id, company_data in self.company_mappings.items():
            hierarchy_rules = company_data.get("hierarchy_rules", {})
            all_rules.update(hierarchy_rules)

        return all_rules

    def _detect_entity_from_concept(self, concept: str) -> Optional[str]:
        """Detect entity identifier from concept name prefix."""
        if '_' in concept:
            prefix = concept.split('_')[0].lower()
            # Check if this prefix corresponds to a known company
            if prefix in self.company_mappings:
                return prefix
        return None

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
                        with pkg_resources.files('edgar.xbrl.standardization').joinpath('concept_mappings.json').open('r') as f:
                            data = json.load(f)
                    except (ImportError, FileNotFoundError, AttributeError):
                        # Fallback to legacy pkg_resources
                        import pkg_resources as legacy_resources
                        resource_string = legacy_resources.resource_string('edgar.xbrl.standardization', 'concept_mappings.json')
                        data = json.loads(resource_string)
                except ImportError:
                    pass
            except Exception:
                # If all attempts fail, log a warning
                logger.warning("Could not load concept_mappings.json. Standardization will be limited.")

        # If we have data, process it based on its structure
        if data:
            # Check if the structure is flat or nested
            if any(isinstance(value, dict) for value in data.values()):
                # Nested structure by statement type
                flattened = {}
                for _statement_type, concepts in data.items():
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

    def get_standard_concept(self, company_concept: str, context: Optional[Dict] = None) -> Optional[str]:
        """
        Get the standard concept for a given company concept with priority-based resolution.

        Uses a multi-tier lookup strategy:
        1. Reverse index (O(1) lookup, 2,067 GAAP tags) - NEW
        2. Company-specific mappings (priority-based)
        3. Core mappings fallback

        Args:
            company_concept: The company-specific concept
            context: Optional context information (for future disambiguation)

        Returns:
            The standard concept or None if not found
        """
        # Tier 1: Try the reverse index first (O(1) lookup, covers 95% of tags)
        try:
            reverse_index = _get_reverse_index()
            display_name = reverse_index.get_display_name(company_concept, context)
            if display_name:
                logger.debug("Reverse index match: %s -> %s", company_concept, display_name)
                return display_name
        except (ImportError, FileNotFoundError, json.JSONDecodeError) as e:
            # Only catch expected errors - let other exceptions propagate
            logger.debug("Reverse index lookup failed for %s: %s", company_concept, e)

        # Tier 2: Use merged mappings with priority-based resolution
        if self.merged_mappings:
            # Detect company from concept prefix (e.g., 'tsla:Revenue' -> 'tsla')
            detected_entity = self._detect_entity_from_concept(company_concept)

            # Search through merged mappings with priority
            candidates = []

            for std_concept, mapping_list in self.merged_mappings.items():
                for concept, source, priority in mapping_list:
                    if concept == company_concept:
                        # Boost priority if it matches detected entity
                        effective_priority = priority
                        if detected_entity and source == detected_entity:
                            effective_priority = 4  # Highest priority for exact company match

                        candidates.append((std_concept, effective_priority, source))

            # Return highest priority match
            if candidates:
                best_match = max(candidates, key=lambda x: x[1])
                logger.debug("Merged mapping applied: %s -> %s (source: %s, priority: %s)", company_concept, best_match[0], best_match[2], best_match[1])
                return best_match[0]

        # Tier 3: Fallback to core mappings
        for standard_concept, company_concepts in self.mappings.items():
            if company_concept in company_concepts:
                logger.debug("Core mapping fallback: %s -> %s", company_concept, standard_concept)
                return standard_concept

        return None

    def get_display_name(self, company_concept: str, context: Optional[Dict] = None) -> Optional[str]:
        """
        Get the user-friendly display name for a company concept.

        This method returns the standardized display name (e.g., "Accounts Payable")
        rather than the internal concept name (e.g., "TradePayables").

        Args:
            company_concept: The company-specific XBRL concept
            context: Optional context information (for future disambiguation)

        Returns:
            The user-friendly display name, or None if not found
        """
        try:
            reverse_index = _get_reverse_index()
            return reverse_index.get_display_name(company_concept, context)
        except (ImportError, FileNotFoundError, json.JSONDecodeError):
            # Fallback to get_standard_concept for backwards compatibility
            return self.get_standard_concept(company_concept, context)

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
        # Use cache for faster lookups - include section for ambiguous tag disambiguation
        cache_key = (company_concept, context.get('statement_type', ''), context.get('section', ''))
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Check if we already have a mapping in the store
        # Pass context for context-aware disambiguation of ambiguous tags (Phase 3/4)
        standard_concept = self.mapping_store.get_standard_concept(company_concept, context)
        if standard_concept:
            self._cache[cache_key] = standard_concept
            return standard_concept

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
        for _std_concept, company_concepts in self.mapping_store.mappings.items():
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


def _should_preserve_label(original_label: str, standardized_label: str) -> bool:
    """
    Check if the original label should be preserved over the standardized version.

    Preserves original labels that contain important qualifiers that would be lost
    in standardization, such as "Other", "net", specific accounting distinctions.

    Args:
        original_label: The company's original label
        standardized_label: The proposed standardized label

    Returns:
        True if the original label should be kept (standardization would lose context)
    """
    if not original_label or not standardized_label:
        return False

    original_lower = original_label.lower()
    standardized_lower = standardized_label.lower()

    # Qualifiers that indicate important context that shouldn't be lost
    # These indicate the label is more specific than the standardized version
    important_qualifiers = [
        'other ',      # "Other intangible assets" vs "Intangible Assets"
        ', net',       # "Intangible assets, net" vs "Intangible Assets"
        ' net',        # "Property and equipment net" vs "Property and Equipment"
        'long-term',   # "Other long-term assets" vs "Other Assets"
        'short-term',  # Distinguishes from long-term
        'current',     # "Current assets" specificity
        'non-current', # "Non-current assets" specificity
        'noncurrent',  # Alternate spelling
    ]

    for qualifier in important_qualifiers:
        # If original has the qualifier but standardized doesn't, preserve original
        if qualifier in original_lower and qualifier not in standardized_lower:
            return True

    return False


def _derive_section_from_parent(calculation_parent: str, statement_type: str) -> Optional[str]:
    """
    Derive the balance sheet section from a calculation parent concept.

    Phase 3: Uses the calculation parent to determine which section an item
    belongs to, enabling disambiguation of ambiguous tags.

    The key insight is that if an item's calculation parent is "AssetsCurrent",
    then the item belongs to the "Current Assets" section.

    Args:
        calculation_parent: The calculation parent concept (e.g., "us-gaap:AssetsCurrent")
        statement_type: The statement type (e.g., "BalanceSheet")

    Returns:
        Section name (e.g., "Current Assets") or None if not determinable
    """
    if not calculation_parent:
        return None

    # Normalize the parent concept name
    parent_normalized = calculation_parent.lower()
    # Remove namespace prefix
    if ":" in parent_normalized:
        parent_normalized = parent_normalized.split(":")[-1]
    if "_" in parent_normalized:
        parent_normalized = parent_normalized.split("_")[-1]

    # Map parent totals to their sections
    # Items under AssetsCurrent belong to "Current Assets" section
    parent_to_section = {
        # Current Assets - items rolling up to AssetsCurrent
        "assetscurrent": "Current Assets",
        "currentassets": "Current Assets",

        # Non-Current Assets - items rolling up to AssetsNoncurrent
        "assetsnoncurrent": "Non-Current Assets",
        "noncurrentassets": "Non-Current Assets",

        # Current Liabilities - items rolling up to LiabilitiesCurrent
        "liabilitiescurrent": "Current Liabilities",
        "currentliabilities": "Current Liabilities",

        # Non-Current Liabilities - items rolling up to LiabilitiesNoncurrent
        "liabilitiesnoncurrent": "Non-Current Liabilities",
        "noncurrentliabilities": "Non-Current Liabilities",

        # Equity - items rolling up to StockholdersEquity
        "stockholdersequity": "Equity",
        "stockholdersequityincludingportionattributabletononcontrollinginterest": "Equity",
        "equity": "Equity",

        # Top-level totals (less specific)
        "assets": "Assets",
        "liabilities": "Liabilities",
        "liabilitiesandstockholdersequity": "Liabilities and Equity",
    }

    # Direct lookup
    if parent_normalized in parent_to_section:
        return parent_to_section[parent_normalized]

    # Partial match fallback
    for pattern, section in parent_to_section.items():
        if pattern in parent_normalized:
            return section

    # Try reverse index as last resort
    try:
        reverse_index = _get_reverse_index()
        parent_standard = reverse_index.get_standard_concept(calculation_parent)

        if parent_standard:
            from .sections import get_section_for_concept
            section = get_section_for_concept(parent_standard, statement_type)
            if section and section != "Totals":
                return section

    except Exception as e:
        logger.debug("Could not derive section from parent %s: %s", calculation_parent, e)

    return None


def _assign_sections_bottom_up(
    items_to_standardize: List[Tuple[int, str, str, Dict[str, Any]]],
    statement_data: List[Dict[str, Any]]
) -> None:
    """
    Assign sections to items using bottom-up scanning (mpreiss9's method).

    Process line items from bottom to top. When we encounter a subtotal,
    that defines the current section, and all items above it (until the
    next subtotal) belong to that section.

    This approach is more robust than calculation-parent-based section
    derivation because:
    1. Some filings have incomplete/missing calculation trees
    2. The statement's own structure (subtotals) is always present
    3. Subtotals naturally demarcate section boundaries

    Args:
        items_to_standardize: List of tuples (index, concept, label, context)
                             - modifies context dicts in-place
        statement_data: Original statement data for accessing item properties

    Note:
        This function modifies the context dicts in items_to_standardize in-place.
    """
    if not items_to_standardize:
        return

    # Map standard subtotal labels to section names
    subtotal_to_section = {
        # Current Assets subtotals
        "total current assets": "Current Assets",
        "current assets, total": "Current Assets",

        # Non-Current Assets subtotals
        "total non-current assets": "Non-Current Assets",
        "total noncurrent assets": "Non-Current Assets",
        "non-current assets, total": "Non-Current Assets",
        "total other assets": "Non-Current Assets",

        # Current Liabilities subtotals
        "total current liabilities": "Current Liabilities",
        "current liabilities, total": "Current Liabilities",

        # Non-Current Liabilities subtotals
        "total non-current liabilities": "Non-Current Liabilities",
        "total noncurrent liabilities": "Non-Current Liabilities",
        "non-current liabilities, total": "Non-Current Liabilities",
        "total long-term debt": "Non-Current Liabilities",

        # Equity subtotals
        "total stockholders' equity": "Equity",
        "total stockholders equity": "Equity",
        "total shareholders' equity": "Equity",
        "total shareholders equity": "Equity",
        "total equity": "Equity",
        "stockholders' equity, total": "Equity",

        # Income Statement sections
        "total revenue": "Revenue",
        "total revenues": "Revenue",
        "total operating expenses": "Operating Expenses",
        "operating expenses, total": "Operating Expenses",
        "total cost of revenue": "Cost of Revenue",
        "total cost of sales": "Cost of Revenue",
    }

    # Build index map for quick lookup: original_index -> items_to_standardize index
    idx_map = {item[0]: i for i, item in enumerate(items_to_standardize)}

    # Get all indices in original order
    all_indices = sorted([item[0] for item in items_to_standardize])

    # Process bottom-to-top
    current_section = None

    for orig_idx in reversed(all_indices):
        item_idx = idx_map[orig_idx]
        _, _, label, context = items_to_standardize[item_idx]

        # Get item properties from original data
        original_item = statement_data[orig_idx]
        is_total = original_item.get("is_total", False) or "total" in label.lower()
        level = original_item.get("level", 0)

        # Check if this is a section subtotal (level 0 or 1 total)
        if is_total and level <= 1:
            # Try to derive section from the subtotal label
            label_lower = label.lower()

            # Direct lookup
            section_from_subtotal = subtotal_to_section.get(label_lower)

            # Partial match fallback
            if not section_from_subtotal:
                for pattern, section in subtotal_to_section.items():
                    if pattern in label_lower or label_lower in pattern:
                        section_from_subtotal = section
                        break

            # Infer from label patterns if still not found
            if not section_from_subtotal:
                if "current asset" in label_lower:
                    section_from_subtotal = "Current Assets"
                elif "current liabilit" in label_lower:
                    section_from_subtotal = "Current Liabilities"
                elif "noncurrent asset" in label_lower or "non-current asset" in label_lower:
                    section_from_subtotal = "Non-Current Assets"
                elif "noncurrent liabilit" in label_lower or "non-current liabilit" in label_lower:
                    section_from_subtotal = "Non-Current Liabilities"
                elif "equity" in label_lower:
                    section_from_subtotal = "Equity"
                elif "revenue" in label_lower:
                    section_from_subtotal = "Revenue"
                elif "operating expense" in label_lower:
                    section_from_subtotal = "Operating Expenses"

            if section_from_subtotal:
                current_section = section_from_subtotal
                logger.debug("Bottom-up: Found section boundary '%s' at '%s'", current_section, label)

        # Assign section to this item if it doesn't have one
        if current_section and not context.get("section"):
            context["section"] = current_section
            logger.debug("Bottom-up: Assigned section '%s' to '%s'", current_section, label)


def standardize_statement(statement_data: List[Dict[str, Any]], mapper: ConceptMapper) -> List[Dict[str, Any]]:
    """
    Add standard concept metadata to statement items without replacing labels.

    This function preserves the original company labels (fidelity to the filing)
    while adding standard_concept metadata for cross-company analysis and filtering.

    The standard_concept field contains the concept identifier (e.g., "CommonEquity")
    which can be used for programmatic grouping and comparison across companies.

    Args:
        statement_data: List of statement line items
        mapper: ConceptMapper instance (used for context building)

    Returns:
        Statement data with standard_concept metadata added where mappings exist
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

        # Build enhanced context for disambiguation (Phase 3)
        calculation_parent = item.get("calculation_parent")
        context = {
            "statement_type": item.get("statement_type", "") or statement_type,
            "level": item.get("level", 0),
            "is_total": "total" in label.lower() or item.get("is_total", False),
            "calculation_parent": calculation_parent,  # Phase 3: for section determination
            "balance": item.get("balance"),  # debit/credit for sign-based disambiguation
            "weight": item.get("weight", 1.0),  # calculation weight
        }

        # Phase 3: Derive section from calculation parent if available
        if calculation_parent:
            context["section"] = _derive_section_from_parent(calculation_parent, statement_type)

        items_to_standardize.append((i, concept, label, context))

    # If no items need standardization, return early with unchanged data
    if not items_to_standardize:
        return statement_data

    # Bottom-up section assignment (mpreiss9's method)
    # This fills in sections for items that didn't get one from calculation_parent
    # by scanning from bottom to top and using subtotals as section boundaries
    _assign_sections_bottom_up(items_to_standardize, statement_data)

    # Get the reverse index for standard concept lookups
    reverse_index = _get_reverse_index()

    # Second pass - add standard_concept metadata without changing labels
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

        # Get the standard concept identifier (e.g., "CommonEquity", not "Total Stockholders' Equity")
        standard_concept = reverse_index.get_standard_concept(concept, context)

        if standard_concept:
            # Add standard_concept as metadata, preserve original label
            item_with_metadata = item.copy()
            item_with_metadata["standard_concept"] = standard_concept
            result.append(item_with_metadata)
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

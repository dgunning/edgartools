"""
Statement Resolution for XBRL data.

This module provides a robust system for identifying and matching XBRL financial statements,
notes, and disclosures regardless of taxonomy variations and company-specific customizations.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from edgar.xbrl.statements import statement_to_concepts


class StatementCategory(Enum):
    """Categories of XBRL presentation sections."""
    FINANCIAL_STATEMENT = "statement"
    NOTE = "note"
    DISCLOSURE = "disclosure"
    DOCUMENT = "document"  # For cover page, signatures, etc.
    OTHER = "other"


@dataclass
class ConceptPattern:
    """Pattern for matching statement concepts across different taxonomies."""
    pattern: str
    weight: float = 1.0


@dataclass
class StatementType:
    """Detailed information about a statement type for matching."""
    name: str
    primary_concepts: List[str]
    category: StatementCategory = StatementCategory.FINANCIAL_STATEMENT  # Default to financial statement
    alternative_concepts: List[str] = field(default_factory=list)
    concept_patterns: List[str] = field(default_factory=list)
    key_concepts: List[str] = field(default_factory=list)
    role_patterns: List[str] = field(default_factory=list)
    title: str = ""
    supports_parenthetical: bool = False
    weight_map: Dict[str, float] = field(default_factory=dict)
    
    def match_concept(self, concept_name: str) -> bool:
        """Check if a concept name matches this statement type's concepts."""
        # Try exact primary concept match
        if concept_name in self.primary_concepts:
            return True
            
        # Try alternate concepts
        if concept_name in self.alternative_concepts:
            return True
            
        # Try matching against patterns
        for pattern in self.concept_patterns:
            if re.match(pattern, concept_name):
                return True
                
        return False
        
    def match_role(self, role_uri: str, role_name: str = "", role_def: str = "") -> bool:
        """Check if role information matches this statement type."""
        name_lower = self.name.lower()
        
        # Check exact match in role parts
        if name_lower in role_uri.lower():
            return True
            
        if role_name and name_lower in role_name.lower():
            return True
            
        if role_def and name_lower in role_def.lower():
            return True
            
        # Try pattern matching
        for pattern in self.role_patterns:
            if re.match(pattern, role_uri) or (role_name and re.match(pattern, role_name)):
                return True
                
        return False


# Registry of statement types with matching information
statement_registry = {
    "BalanceSheet": StatementType(
        name="BalanceSheet",
        category=StatementCategory.FINANCIAL_STATEMENT,
        primary_concepts=["us-gaap_StatementOfFinancialPositionAbstract"],
        alternative_concepts=["us-gaap_BalanceSheetAbstract"],
        concept_patterns=[
            r".*_StatementOfFinancialPositionAbstract$",
            r".*_BalanceSheetAbstract$",
            r".*_ConsolidatedBalanceSheetsAbstract$",
            r".*_CondensedConsolidatedBalanceSheetsUnauditedAbstract$"
        ],
        key_concepts=["us-gaap_Assets", "us-gaap_Liabilities", "us-gaap_StockholdersEquity"],
        role_patterns=[
            r".*[Bb]alance[Ss]heet.*",
            r".*[Ss]tatement[Oo]f[Ff]inancial[Pp]osition.*",
            r".*StatementConsolidatedBalanceSheets.*"
        ],
        title="Consolidated Balance Sheets",
        supports_parenthetical=True,
        weight_map={"assets": 0.3, "liabilities": 0.3, "equity": 0.4}
    ),
    
    "IncomeStatement": StatementType(
        name="IncomeStatement",
        category=StatementCategory.FINANCIAL_STATEMENT,
        primary_concepts=["us-gaap_IncomeStatementAbstract"],
        alternative_concepts=["us-gaap_StatementOfIncomeAbstract"],
        concept_patterns=[
            r".*_IncomeStatementAbstract$",
            r".*_StatementOfIncomeAbstract$",
            r".*_ConsolidatedStatementsOfIncomeAbstract$", 
            r".*_CondensedConsolidatedStatementsOfIncomeUnauditedAbstract$"
        ],
        key_concepts=["us-gaap_Revenues", "us-gaap_NetIncomeLoss"],
        role_patterns=[
            r".*[Ii]ncome[Ss]tatement.*",
            r".*[Ss]tatement[Oo]f[Ii]ncome.*",
            r".*[Oo]perations.*",
            r".*StatementConsolidatedStatementsOfIncome.*"
        ],
        title="Consolidated Statement of Income",
        supports_parenthetical=True,
        weight_map={"revenues": 0.4, "netIncomeLoss": 0.6}
    ),
    
    "CashFlowStatement": StatementType(
        name="CashFlowStatement",
        category=StatementCategory.FINANCIAL_STATEMENT,
        primary_concepts=["us-gaap_StatementOfCashFlowsAbstract"],
        concept_patterns=[
            r".*_StatementOfCashFlowsAbstract$",
            r".*_CashFlowsAbstract$",
            r".*_ConsolidatedStatementsOfCashFlowsAbstract$",
            r".*_CondensedConsolidatedStatementsOfCashFlowsUnauditedAbstract$"
        ],
        key_concepts=[
            "us-gaap_NetCashProvidedByUsedInOperatingActivities",
            "us-gaap_CashAndCashEquivalentsPeriodIncreaseDecrease"
        ],
        role_patterns=[
            r".*[Cc]ash[Ff]low.*",
            r".*[Ss]tatement[Oo]f[Cc]ash[Ff]lows.*",
            r".*StatementConsolidatedStatementsOfCashFlows.*"
        ],
        title="Consolidated Statement of Cash Flows",
        supports_parenthetical=False
    ),
    
    "StatementOfEquity": StatementType(
        name="StatementOfEquity",
        category=StatementCategory.FINANCIAL_STATEMENT,
        primary_concepts=["us-gaap_StatementOfStockholdersEquityAbstract"],
        alternative_concepts=[
            "us-gaap_StatementOfShareholdersEquityAbstract",
            "us-gaap_StatementOfPartnersCapitalAbstract"
        ],
        concept_patterns=[
            r".*_StatementOfStockholdersEquityAbstract$",
            r".*_StatementOfShareholdersEquityAbstract$",
            r".*_StatementOfChangesInEquityAbstract$",
            r".*_ConsolidatedStatementsOfShareholdersEquityAbstract$"
        ],
        key_concepts=["us-gaap_StockholdersEquity", "us-gaap_CommonStock", "us-gaap_RetainedEarnings"],
        role_patterns=[
            r".*[Ee]quity.*",
            r".*[Ss]tockholders.*",
            r".*[Ss]hareholders.*",
            r".*[Cc]hanges[Ii]n[Ee]quity.*",
            r".*StatementConsolidatedStatementsOfStockholdersEquity.*"
        ],
        title="Consolidated Statement of Equity",
        supports_parenthetical=False
    ),
    
    "ComprehensiveIncome": StatementType(
        name="ComprehensiveIncome",
        category=StatementCategory.FINANCIAL_STATEMENT,
        primary_concepts=["us-gaap_StatementOfIncomeAndComprehensiveIncomeAbstract"],
        alternative_concepts=["us-gaap_StatementOfComprehensiveIncomeAbstract"],
        concept_patterns=[
            r".*_ComprehensiveIncomeAbstract$",
            r".*_StatementOfComprehensiveIncomeAbstract$",
            r".*_ConsolidatedStatementsOfComprehensiveIncomeAbstract$"
        ],
        key_concepts=["us-gaap_ComprehensiveIncomeNetOfTax"],
        role_patterns=[
            r".*[Cc]omprehensive[Ii]ncome.*",
            r".*[Oo]ther[Cc]omprehensive.*",
            r".*StatementConsolidatedStatementsOfComprehensiveIncome.*"
        ],
        title="Consolidated Statement of Comprehensive Income",
        supports_parenthetical=True
    ),
    
    "Notes": StatementType(
        name="Notes",
        category=StatementCategory.NOTE,
        primary_concepts=["us-gaap_NotesToFinancialStatementsAbstract"],
        alternative_concepts=[],
        concept_patterns=[
            r".*_NotesToFinancialStatementsAbstract$",
            r".*_NotesAbstract$"
        ],
        key_concepts=[],
        role_patterns=[
            r".*[Nn]otes[Tt]o[Ff]inancial[Ss]tatements.*",
            r".*[Nn]ote\s+\d+.*",
            r".*[Nn]otes.*"
        ],
        title="Notes to Financial Statements",
        supports_parenthetical=False
    ),
    
    "AccountingPolicies": StatementType(
        name="AccountingPolicies",
        category=StatementCategory.NOTE,
        primary_concepts=["us-gaap_AccountingPoliciesAbstract"],
        alternative_concepts=[],
        concept_patterns=[
            r".*_AccountingPoliciesAbstract$",
            r".*_SignificantAccountingPoliciesAbstract$"
        ],
        key_concepts=["us-gaap_SignificantAccountingPoliciesTextBlock"],
        role_patterns=[
            r".*[Aa]ccounting[Pp]olicies.*",
            r".*[Ss]ignificant[Aa]ccounting[Pp]olicies.*"
        ],
        title="Significant Accounting Policies",
        supports_parenthetical=False
    ),
    
    "Disclosures": StatementType(
        name="Disclosures",
        category=StatementCategory.DISCLOSURE,
        primary_concepts=["us-gaap_DisclosuresAbstract"],
        alternative_concepts=[],
        concept_patterns=[
            r".*_DisclosuresAbstract$",
            r".*_DisclosureAbstract$"
        ],
        key_concepts=[],
        role_patterns=[
            r".*[Dd]isclosure.*"
        ],
        title="Disclosures",
        supports_parenthetical=False
    ),
    
    "SegmentDisclosure": StatementType(
        name="SegmentDisclosure",
        category=StatementCategory.DISCLOSURE,
        primary_concepts=["us-gaap_SegmentDisclosureAbstract"],
        alternative_concepts=[],
        concept_patterns=[
            r".*_SegmentDisclosureAbstract$",
            r".*_SegmentReportingDisclosureAbstract$"
        ],
        key_concepts=["us-gaap_SegmentReportingDisclosureTextBlock"],
        role_patterns=[
            r".*[Ss]egment.*",
            r".*[Ss]egment[Rr]eporting.*",
            r".*[Ss]egment[Ii]nformation.*"
        ],
        title="Segment Information",
        supports_parenthetical=False
    ),
    
    "CoverPage": StatementType(
        name="CoverPage", 
        category=StatementCategory.DOCUMENT,
        primary_concepts=["dei_CoverAbstract"],
        concept_patterns=[r".*_CoverAbstract$"],
        key_concepts=["dei_EntityRegistrantName", "dei_DocumentType"],
        role_patterns=[r".*[Cc]over.*"],
        title="Cover Page",
        supports_parenthetical=False
    )
}


class StatementResolver:
    """
    Resolves statement identifiers to actual XBRL statement roles.
    
    This class provides a multi-layered approach to statement matching,
    handling taxonomy variations and company-specific customizations.
    """
    
    def __init__(self, xbrl):
        """
        Initialize with an XBRL object.
        
        Args:
            xbrl: XBRL object containing parsed data
        """
        self.xbrl = xbrl
        self._cache = {}
        
        # Build indices for faster lookups
        self._statement_by_role_uri = {}
        self._statement_by_role_name = {}
        self._statement_by_primary_concept = {}
        self._statement_by_type = {}
        self._statement_by_role_def = {}
        
        # Map legacy statement types to new registry
        self._legacy_to_registry = {}
        for legacy_type, info in statement_to_concepts.items():
            if legacy_type in statement_registry:
                self._legacy_to_registry[legacy_type] = legacy_type
                continue
                
            # Try to find a match in the registry
            for reg_type, reg_info in statement_registry.items():
                if info.concept in reg_info.primary_concepts or info.concept in reg_info.alternative_concepts:
                    self._legacy_to_registry[legacy_type] = reg_type
                    break
        
        # Initialize indices when instantiated
        self._initialize_indices()
    
    def _initialize_indices(self):
        """Build lookup indices for fast statement retrieval."""
        # Get all statements
        statements = self.xbrl.get_all_statements()
        
        # Reset indices
        self._statement_by_role_uri = {}
        self._statement_by_role_name = {}
        self._statement_by_primary_concept = {}
        self._statement_by_type = {}
        self._statement_by_role_def = {}
        
        # Build indices
        for stmt in statements:
            role = stmt.get('role', '')
            role_name = stmt.get('role_name', '').lower() if stmt.get('role_name') else ''
            primary_concept = stmt.get('primary_concept', '')
            stmt_type = stmt.get('type', '')
            role_def = stmt.get('definition', '').lower() if stmt.get('definition') else ''
            
            # By role URI
            self._statement_by_role_uri[role] = stmt
            
            # By role name
            if role_name:
                if role_name not in self._statement_by_role_name:
                    self._statement_by_role_name[role_name] = []
                self._statement_by_role_name[role_name].append(stmt)
            
            # By primary concept
            if primary_concept:
                if primary_concept not in self._statement_by_primary_concept:
                    self._statement_by_primary_concept[primary_concept] = []
                self._statement_by_primary_concept[primary_concept].append(stmt)
            
            # By statement type
            if stmt_type:
                if stmt_type not in self._statement_by_type:
                    self._statement_by_type[stmt_type] = []
                self._statement_by_type[stmt_type].append(stmt)
                
            # By role definition (without spaces, lowercase)
            if role_def:
                def_key = role_def.replace(' ', '')
                if def_key not in self._statement_by_role_def:
                    self._statement_by_role_def[def_key] = []
                self._statement_by_role_def[def_key].append(stmt)
                
    def _match_by_primary_concept(self, statement_type: str, is_parenthetical: bool = False) -> Tuple[List[Dict[str, Any]], Optional[str], float]:
        """
        Match statements using primary concept names.
        
        Args:
            statement_type: Statement type to match
            is_parenthetical: Whether to look for a parenthetical statement
            
        Returns:
            Tuple of (matching statements, found role, confidence score)
        """
        # Convert legacy types to registry types if needed
        if statement_type in self._legacy_to_registry:
            registry_type = self._legacy_to_registry[statement_type]
        else:
            registry_type = statement_type
            
        # Check if this is a known statement type
        if registry_type not in statement_registry:
            return [], None, 0.0
            
        # Get registry information
        registry_entry = statement_registry[registry_type]
        
        # Try to match by primary concepts
        matched_statements = []
        
        for concept in registry_entry.primary_concepts + registry_entry.alternative_concepts:
            if concept in self._statement_by_primary_concept:
                for stmt in self._statement_by_primary_concept[concept]:
                    # Handle parenthetical check
                    if registry_entry.supports_parenthetical:
                        role_def = stmt.get('definition', '').lower()
                        is_role_parenthetical = 'parenthetical' in role_def
                        
                        # Skip if parenthetical status doesn't match
                        if is_parenthetical != is_role_parenthetical:
                            continue
                    
                    matched_statements.append(stmt)
        
        # If we found matching statements, return with high confidence
        if matched_statements:
            return matched_statements, matched_statements[0]['role'], 0.9
            
        return [], None, 0.0
        
    def _match_by_concept_pattern(self, statement_type: str, is_parenthetical: bool = False) -> Tuple[List[Dict[str, Any]], Optional[str], float]:
        """
        Match statements using regex patterns on concept names to handle custom company namespaces.
        
        Args:
            statement_type: Statement type to match
            is_parenthetical: Whether to look for a parenthetical statement
            
        Returns:
            Tuple of (matching statements, found role, confidence score)
        """
        # Convert legacy types to registry types if needed
        if statement_type in self._legacy_to_registry:
            registry_type = self._legacy_to_registry[statement_type]
        else:
            registry_type = statement_type
            
        # Check if this is a known statement type
        if registry_type not in statement_registry:
            return [], None, 0.0
            
        # Get registry information
        registry_entry = statement_registry[registry_type]
        concept_patterns = registry_entry.concept_patterns
        
        if not concept_patterns:
            return [], None, 0.0
            
        # Get all statements to check against patterns
        all_statements = self.xbrl.get_all_statements()
        
        # Check each statement's primary concept against our patterns
        matched_statements = []
        for stmt in all_statements:
            primary_concept = stmt.get('primary_concept', '')
            
            # Skip if no primary concept
            if not primary_concept:
                continue
                
            # Check if this concept matches any of our patterns
            for pattern in concept_patterns:
                if re.match(pattern, primary_concept):
                    # For parenthetical statements, check the role definition
                    if registry_entry.supports_parenthetical:
                        role_def = stmt.get('definition', '').lower()
                        is_role_parenthetical = 'parenthetical' in role_def
                        
                        # Skip if parenthetical status doesn't match
                        if is_parenthetical != is_role_parenthetical:
                            continue
                            
                    matched_statements.append(stmt)
                    break  # Found a match, no need to check other patterns
                    
        # If we found matching statements, return with high confidence
        if matched_statements:
            return matched_statements, matched_statements[0]['role'], 0.85
            
        return [], None, 0.0
        
    def _match_by_role_pattern(self, statement_type: str, is_parenthetical: bool = False) -> Tuple[List[Dict[str, Any]], Optional[str], float]:
        """
        Match statements using role URI or role name patterns.
        
        Args:
            statement_type: Statement type to match
            is_parenthetical: Whether to look for a parenthetical statement
            
        Returns:
            Tuple of (matching statements, found role, confidence score)
        """
        # Convert legacy types to registry types if needed
        if statement_type in self._legacy_to_registry:
            registry_type = self._legacy_to_registry[statement_type]
        else:
            registry_type = statement_type
            
        # Check if this is a known statement type
        if registry_type not in statement_registry:
            return [], None, 0.0
            
        # Get registry information
        registry_entry = statement_registry[registry_type]
        role_patterns = registry_entry.role_patterns
        
        if not role_patterns:
            return [], None, 0.0
            
        # Get all statements
        all_statements = self.xbrl.get_all_statements()
        
        # Check each statement's role and role name against our patterns
        matched_statements = []
        for stmt in all_statements:
            role = stmt.get('role', '')
            role_name = stmt.get('role_name', '')
            
            # Check if role matches any pattern
            for pattern in role_patterns:
                if (re.search(pattern, role, re.IGNORECASE) or 
                   (role_name and re.search(pattern, role_name, re.IGNORECASE))):
                    # For parenthetical statements, check the role definition
                    if registry_entry.supports_parenthetical:
                        role_def = stmt.get('definition', '').lower()
                        is_role_parenthetical = 'parenthetical' in role_def
                        
                        # Skip if parenthetical status doesn't match
                        if is_parenthetical != is_role_parenthetical:
                            continue
                            
                    matched_statements.append(stmt)
                    break  # Found a match, no need to check other patterns
                    
        # If we found matching statements, return with good confidence
        if matched_statements:
            return matched_statements, matched_statements[0]['role'], 0.75
            
        return [], None, 0.0
        
    def _match_by_content(self, statement_type: str) -> Tuple[List[Dict[str, Any]], Optional[str], float]:
        """
        Match statements by analyzing their content against key concepts.
        
        Args:
            statement_type: Statement type to match
            
        Returns:
            Tuple of (matching statements, found role, confidence score)
        """
        # Convert legacy types to registry types if needed
        if statement_type in self._legacy_to_registry:
            registry_type = self._legacy_to_registry[statement_type]
        else:
            registry_type = statement_type
            
        # Check if this is a known statement type
        if registry_type not in statement_registry:
            return [], None, 0.0
            
        # Get registry information
        registry_entry = statement_registry[registry_type]
        key_concepts = registry_entry.key_concepts
        
        if not key_concepts:
            return [], None, 0.0
            
        # Get all statements
        all_statements = self.xbrl.get_all_statements()
        
        # Score each statement based on presence of key concepts
        statement_scores = []
        
        for stmt in all_statements:
            role = stmt.get('role', '')
            if role not in self.xbrl.presentation_trees:
                continue
                
            # Get concept nodes for this role
            tree = self.xbrl.presentation_trees[role]
            all_nodes = set(tree.all_nodes.keys())
            
            # Count matching key concepts
            matches = 0
            total_weight = 0.0
            
            for concept in key_concepts:
                # Normalize concept name
                normalized = concept.replace(':', '_')
                
                if concept in all_nodes or normalized in all_nodes:
                    matches += 1
                    # Add weighting if available
                    concept_key = concept.split('_')[-1].lower()
                    weight = registry_entry.weight_map.get(concept_key, 1.0)
                    total_weight += weight
            
            # Calculate confidence score (weighted by presence of key concepts)
            if key_concepts:
                # Base confidence on percentage of key concepts found
                confidence = matches / len(key_concepts)
                
                # Apply weighting if available
                if total_weight > 0:
                    confidence = min(total_weight / sum(registry_entry.weight_map.values()), 1.0)
            else:
                confidence = 0.0
                
            if confidence > 0:
                statement_scores.append((stmt, confidence))
        
        # Sort by confidence score
        statement_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return best match if above threshold
        if statement_scores and statement_scores[0][1] >= 0.4:
            best_match, confidence = statement_scores[0]
            return [best_match], best_match['role'], min(confidence + 0.2, 0.85)  # Boost confidence but cap at 0.85
            
        return [], None, 0.0
        
    def _match_by_standard_name(self, statement_type: str) -> Tuple[List[Dict[str, Any]], Optional[str], float]:
        """
        Match statements by standard statement type name.
        
        Args:
            statement_type: Statement type to match
            
        Returns:
            Tuple of (matching statements, found role, confidence score)
        """
        # Check if we have statements of this type
        if statement_type in self._statement_by_type:
            statements = self._statement_by_type[statement_type]
            if statements:
                return statements, statements[0]['role'], 0.95
                
        return [], None, 0.0
        
    def _match_by_role_definition(self, statement_type: str) -> Tuple[List[Dict[str, Any]], Optional[str], float]:
        """
        Match statements by role definition text.
        
        Args:
            statement_type: Statement type or definition text to match
            
        Returns:
            Tuple of (matching statements, found role, confidence score)
        """
        # Clean statement type for matching
        clean_type = statement_type.lower().replace(' ', '')
        
        # Try exact match
        if clean_type in self._statement_by_role_def:
            statements = self._statement_by_role_def[clean_type]
            if statements:
                return statements, statements[0]['role'], 0.85
        
        # Try partial match
        for def_key, statements in self._statement_by_role_def.items():
            if clean_type in def_key:
                return statements, statements[0]['role'], 0.65
                
            if def_key in clean_type:
                return statements, statements[0]['role'], 0.55
                
        return [], None, 0.0
        
    def _get_best_guess(self, statement_type: str) -> Tuple[List[Dict[str, Any]], Optional[str], float]:
        """
        Make a best guess when all other methods fail.
        
        Args:
            statement_type: Statement type to guess
            
        Returns:
            Tuple of (matching statements, found role, confidence score)
        """
        # Try partial matching on role names
        clean_type = statement_type.lower()
        
        for role_name, statements in self._statement_by_role_name.items():
            if clean_type in role_name or role_name in clean_type:
                return statements, statements[0]['role'], 0.4
        
        # If we have statements of any type, return the first one with very low confidence
        all_statements = self.xbrl.get_all_statements()
        if all_statements:
            # Try to find a primary financial statement
            for stmt_type in ['BalanceSheet', 'IncomeStatement', 'CashFlowStatement']:
                if stmt_type in self._statement_by_type:
                    statements = self._statement_by_type[stmt_type]
                    if statements:
                        return statements, statements[0]['role'], 0.2
            
            # Last resort: return first statement
            return [all_statements[0]], all_statements[0]['role'], 0.1
                
        return [], None, 0.0
        
    def find_statement(self, statement_type: str, is_parenthetical: bool = False, 
                      category_filter: Optional[StatementCategory] = None) -> Tuple[List[Dict[str, Any]], Optional[str], str, float]:
        """
        Find a statement by type, with multi-layered fallback approach.
        
        Args:
            statement_type: Statement type or identifier
            is_parenthetical: Whether to look for parenthetical version
            category_filter: Optional filter to only match statements of a specific category
            
        Returns:
            Tuple of (matching_statements, found_role, canonical_statement_type, confidence_score)
            
        Note:
            For standard statement types like "BalanceSheet", "IncomeStatement", etc., the
            canonical_statement_type will be the input statement_type, allowing downstream
            code to still recognize and apply type-specific logic.
        """
        # Check cache first
        category_key = str(category_filter.value) if category_filter else "None"
        cache_key = f"{statement_type}_{is_parenthetical}_{category_key}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        # If this is a role URI we already know, return immediately
        if statement_type in self._statement_by_role_uri:
            stmt = self._statement_by_role_uri[statement_type]
            
            # Apply category filter if specified
            if category_filter:
                # Get category from statement or determine based on type
                stmt_category = None
                if 'category' in stmt and stmt['category']:
                    stmt_category = stmt['category']
                elif stmt['type'] in statement_registry:
                    stmt_category = statement_registry[stmt['type']].category.value
                
                # Skip if category doesn't match
                if stmt_category != category_filter.value:
                    result = ([], None, statement_type, 0.0)
                    self._cache[cache_key] = result
                    return result
            
            result = ([stmt], statement_type, stmt.get('type', statement_type), 1.0)
            self._cache[cache_key] = result
            return result
        
        # Check if this is a canonical statement type from the registry
        is_canonical_type = statement_type in statement_registry
            
        # Try standard name matching first (exact type match)
        match = self._match_by_standard_name(statement_type)
        if match[0] and match[2] > 0.9:  # Very high confidence
            statements, role, conf = match
            # For canonical types, preserve the original statement_type
            canonical_type = statement_type if is_canonical_type else statements[0].get('type', statement_type)
            result = (statements, role, canonical_type, conf)
            self._cache[cache_key] = result
            return result
            
        # Try primary concept matching
        match = self._match_by_primary_concept(statement_type, is_parenthetical)
        if match[0] and match[2] > 0.8:  # High confidence
            statements, role, conf = match
            # For canonical types, preserve the original statement_type
            canonical_type = statement_type if is_canonical_type else statements[0].get('type', statement_type)
            result = (statements, role, canonical_type, conf)
            self._cache[cache_key] = result
            return result
        
        # Try custom namespace matching
        match = self._match_by_concept_pattern(statement_type, is_parenthetical)
        if match[0] and match[2] > 0.8:  # High confidence
            statements, role, conf = match
            # For canonical types, preserve the original statement_type
            canonical_type = statement_type if is_canonical_type else statements[0].get('type', statement_type)
            result = (statements, role, canonical_type, conf)
            self._cache[cache_key] = result
            return result
            
        # Try role pattern matching
        match = self._match_by_role_pattern(statement_type, is_parenthetical)
        if match[0] and match[2] > 0.7:  # Good confidence
            statements, role, conf = match
            # For canonical types, preserve the original statement_type
            canonical_type = statement_type if is_canonical_type else statements[0].get('type', statement_type)
            result = (statements, role, canonical_type, conf)
            self._cache[cache_key] = result
            return result
            
        # Try content-based analysis
        match = self._match_by_content(statement_type)
        if match[0] and match[2] > 0.6:  # Moderate confidence
            statements, role, conf = match
            # For canonical types, preserve the original statement_type
            canonical_type = statement_type if is_canonical_type else statements[0].get('type', statement_type)
            result = (statements, role, canonical_type, conf)
            self._cache[cache_key] = result
            return result
            
        # Try role definition matching
        match = self._match_by_role_definition(statement_type)
        if match[0] and match[2] > 0.5:  # Lower confidence but still useful
            statements, role, conf = match
            # For canonical types, preserve the original statement_type
            canonical_type = statement_type if is_canonical_type else statements[0].get('type', statement_type)
            result = (statements, role, canonical_type, conf)
            self._cache[cache_key] = result
            return result
            
        # No good match found, return best guess with low confidence
        statements, role, conf = self._get_best_guess(statement_type)
        if statements:
            # For canonical types, preserve the original statement_type
            canonical_type = statement_type if is_canonical_type else statements[0].get('type', statement_type)
            result = (statements, role, canonical_type, conf)
        else:
            result = ([], None, statement_type, 0.0)
            
        self._cache[cache_key] = result
        return result
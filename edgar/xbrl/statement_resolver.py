"""
Statement Resolution for XBRL data.

This module provides a robust system for identifying and matching XBRL financial statements,
notes, and disclosures regardless of taxonomy variations and company-specific customizations.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from edgar.config import VERBOSE_EXCEPTIONS
from edgar.core import log
from edgar.xbrl.exceptions import StatementNotFound
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
        alternative_concepts=[
            "us-gaap_BalanceSheetAbstract",
            "ifrs-full_StatementOfFinancialPositionAbstract"  # IFRS equivalent
        ],
        concept_patterns=[
            r".*_StatementOfFinancialPositionAbstract$",
            r".*_BalanceSheetAbstract$",
            r".*_ConsolidatedBalanceSheetsAbstract$",
            r".*_CondensedConsolidatedBalanceSheetsUnauditedAbstract$"
        ],
        key_concepts=[
            "us-gaap_Assets", "us-gaap_Liabilities", "us-gaap_StockholdersEquity",
            "ifrs-full_Assets", "ifrs-full_Liabilities", "ifrs-full_Equity"  # IFRS equivalents
        ],
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
        alternative_concepts=[
            "us-gaap_StatementOfIncomeAbstract",
            "ifrs-full_IncomeStatementAbstract",  # IFRS equivalent
            # IFRS often combines income + comprehensive income into one statement
            "ifrs-full_StatementOfComprehensiveIncomeAbstract",
            "ifrs-full_StatementOfProfitOrLossAbstract"
        ],
        concept_patterns=[
            r".*_IncomeStatementAbstract$",
            r".*_StatementOfIncomeAbstract$",
            r".*_ConsolidatedStatementsOfIncomeAbstract$",
            r".*_CondensedConsolidatedStatementsOfIncomeUnauditedAbstract$"
        ],
        key_concepts=[
            "us-gaap_Revenues", "us-gaap_NetIncomeLoss",
            "ifrs-full_Revenue", "ifrs-full_ProfitLoss"  # IFRS equivalents
        ],
        role_patterns=[
            r".*[Ii]ncome[Ss]tatements?.*",
            # Issue #581: Match both singular and plural (Statement/Statements)
            r".*[Ss]tatements?[Oo]f[Ii]ncome.*",
            # Issue #581: Make Operations pattern more specific to avoid matching tax disclosures
            # Match "StatementOfOperations" or "StatementsOfOperations" but NOT "ContinuingOperationsDetails"
            r".*[Ss]tatements?[Oo]f[Oo]perations.*",
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
        alternative_concepts=["ifrs-full_StatementOfCashFlowsAbstract"],  # IFRS equivalent
        concept_patterns=[
            r".*_StatementOfCashFlowsAbstract$",
            r".*_CashFlowsAbstract$",
            r".*_ConsolidatedStatementsOfCashFlowsAbstract$",
            r".*_CondensedConsolidatedStatementsOfCashFlowsUnauditedAbstract$"
        ],
        key_concepts=[
            "us-gaap_NetCashProvidedByUsedInOperatingActivities",
            "us-gaap_CashAndCashEquivalentsPeriodIncreaseDecrease",
            "ifrs-full_CashFlowsFromUsedInOperatingActivities",  # IFRS equivalents
            "ifrs-full_IncreaseDecreaseInCashAndCashEquivalents"
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
            "us-gaap_StatementOfPartnersCapitalAbstract",
            # Issue edgartools-8ad8: ORCL uses roll-forward concept for main equity statement
            "us-gaap_IncreaseDecreaseInStockholdersEquityRollForward",
            # IFRS equivalents
            "ifrs-full_StatementOfChangesInEquityAbstract"
        ],
        concept_patterns=[
            r".*_StatementOfStockholdersEquityAbstract$",
            r".*_StatementOfShareholdersEquityAbstract$",
            r".*_StatementOfChangesInEquityAbstract$",
            r".*_ConsolidatedStatementsOfShareholdersEquityAbstract$",
            # Issue edgartools-8ad8: Match roll-forward patterns for equity statements
            r".*_IncreaseDecreaseInStockholdersEquityRollForward$"
        ],
        key_concepts=[
            "us-gaap_StockholdersEquity", "us-gaap_CommonStock", "us-gaap_RetainedEarnings",
            # IFRS equivalents
            "ifrs-full_Equity", "ifrs-full_IssuedCapital", "ifrs-full_RetainedEarnings"
        ],
        role_patterns=[
            r".*[Ee]quity.*",
            r".*[Ss]tockholders.*",
            r".*[Ss]hareholders.*",
            r".*[Cc]hanges[Ii]n[Ee]quity.*",
            r".*StatementConsolidatedStatementsOfStockholdersEquity.*"
        ],
        title="Consolidated Statement of Equity",
        supports_parenthetical=True  # Issue edgartools-8ad8: Enable parenthetical filtering
    ),

    "ComprehensiveIncome": StatementType(
        name="ComprehensiveIncome",
        category=StatementCategory.FINANCIAL_STATEMENT,
        primary_concepts=["us-gaap_StatementOfIncomeAndComprehensiveIncomeAbstract"],
        alternative_concepts=[
            "us-gaap_StatementOfComprehensiveIncomeAbstract",
            # IFRS equivalents
            "ifrs-full_StatementOfComprehensiveIncomeAbstract",
            "ifrs-full_StatementOfProfitOrLossAndOtherComprehensiveIncomeAbstract"
        ],
        concept_patterns=[
            r".*_ComprehensiveIncomeAbstract$",
            r".*_StatementOfComprehensiveIncomeAbstract$",
            r".*_ConsolidatedStatementsOfComprehensiveIncomeAbstract$"
        ],
        key_concepts=[
            "us-gaap_ComprehensiveIncomeNetOfTax",
            # IFRS equivalents
            "ifrs-full_ComprehensiveIncome",
            "ifrs-full_OtherComprehensiveIncome"
        ],
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
    ),

    # Fund-specific statements (for BDCs, closed-end funds, investment companies)
    "ScheduleOfInvestments": StatementType(
        name="ScheduleOfInvestments",
        category=StatementCategory.FINANCIAL_STATEMENT,
        primary_concepts=["us-gaap_ScheduleOfInvestmentsAbstract"],
        alternative_concepts=[
            "us-gaap_InvestmentsDebtAndEquitySecuritiesAbstract",
            "us-gaap_InvestmentHoldingsAbstract"
        ],
        concept_patterns=[
            r".*_ScheduleOfInvestmentsAbstract$",
            r".*_ConsolidatedScheduleofInvestmentsAbstract$",
            r".*_InvestmentHoldingsAbstract$"
        ],
        key_concepts=[
            "us-gaap_InvestmentOwnedAtFairValue",
            "us-gaap_InvestmentOwnedAtCost",
            "us-gaap_InvestmentOwnedBalancePrincipalAmount",
            "us-gaap_InvestmentOwnedBalanceShares",
            "us-gaap_InvestmentOwnedPercentOfNetAssets",
            "us-gaap_ScheduleOfInvestmentsLineItems"
        ],
        role_patterns=[
            r".*[Ss]chedule[Oo]f[Ii]nvestments.*",
            r".*[Cc]onsolidated[Ss]chedule[Oo]f[Ii]nvestments.*",
            r".*[Ii]nvestment[Hh]oldings.*",
            r".*[Pp]ortfolio[Ii]nvestments.*"
        ],
        title="Consolidated Schedule of Investments",
        supports_parenthetical=True
    ),

    "FinancialHighlights": StatementType(
        name="FinancialHighlights",
        category=StatementCategory.FINANCIAL_STATEMENT,
        primary_concepts=["us-gaap_InvestmentCompanyFinancialHighlightsAbstract"],
        alternative_concepts=[
            "us-gaap_InvestmentCompanyAbstract"
        ],
        concept_patterns=[
            r".*_FinancialHighlightsAbstract$",
            r".*_InvestmentCompanyFinancialHighlightsAbstract$"
        ],
        key_concepts=[
            "us-gaap_NetAssetValuePerShare",
            "us-gaap_InvestmentCompanyNetAssets",
            "us-gaap_InvestmentCompanyTotalReturn",
            "us-gaap_InvestmentCompanyExpenseRatio"
        ],
        role_patterns=[
            r".*[Ff]inancial[Hh]ighlights.*",
            r".*[Ii]nvestment[Cc]ompany[Ff]inancial[Hh]ighlights.*"
        ],
        title="Financial Highlights",
        supports_parenthetical=False
    )
}

# Mapping from StatementType enum snake_case values to PascalCase registry keys
# This allows xbrl.get_statement(StatementType.INCOME_STATEMENT) to work
_ENUM_TO_REGISTRY: Dict[str, str] = {
    "income_statement": "IncomeStatement",
    "balance_sheet": "BalanceSheet",
    "cash_flow_statement": "CashFlowStatement",
    "changes_in_equity": "StatementOfEquity",
    "comprehensive_income": "ComprehensiveIncome",
    "segment_reporting": "SegmentDisclosure",
    "footnotes": "Notes",
    "accounting_policies": "AccountingPolicies",
}


# Essential concepts that should be present in each statement type for validation
# These are used to verify that the resolved statement is actually the correct type
# At least one concept from each group should be present for a valid statement
ESSENTIAL_CONCEPTS = {
    "IncomeStatement": {
        "revenue": [
            "us-gaap_Revenues", "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
            "us-gaap_SalesRevenueNet", "us-gaap_NetSales", "us-gaap_TotalRevenuesAndOtherIncome",
            "ifrs-full_Revenue"
        ],
        "net_income": [
            "us-gaap_NetIncomeLoss", "us-gaap_ProfitLoss", "us-gaap_NetIncomeLossAvailableToCommonStockholdersBasic",
            "ifrs-full_ProfitLoss", "ifrs-full_ProfitLossAttributableToOwnersOfParent"
        ]
    },
    "BalanceSheet": {
        "assets": [
            "us-gaap_Assets", "us-gaap_AssetsCurrent", "us-gaap_AssetsNoncurrent",
            "ifrs-full_Assets", "ifrs-full_CurrentAssets", "ifrs-full_NoncurrentAssets"
        ],
        "liabilities_or_equity": [
            "us-gaap_Liabilities", "us-gaap_StockholdersEquity", "us-gaap_LiabilitiesAndStockholdersEquity",
            "ifrs-full_Liabilities", "ifrs-full_Equity", "ifrs-full_EquityAndLiabilities"
        ]
    },
    "CashFlowStatement": {
        "operating": [
            "us-gaap_NetCashProvidedByUsedInOperatingActivities",
            "us-gaap_NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
            "ifrs-full_CashFlowsFromUsedInOperatingActivities"
        ],
        "cash_change": [
            "us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
            "us-gaap_CashAndCashEquivalentsPeriodIncreaseDecrease",
            "ifrs-full_IncreaseDecreaseInCashAndCashEquivalents"
        ]
    },
    "ComprehensiveIncome": {
        "comprehensive_income": [
            "us-gaap_ComprehensiveIncomeNetOfTax",
            "us-gaap_ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest",
            "ifrs-full_ComprehensiveIncome"
        ]
    },
    "StatementOfEquity": {
        "equity": [
            "us-gaap_StockholdersEquity", "us-gaap_StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            "ifrs-full_Equity"
        ]
    }
}

# Minimum threshold for validation - at least this percentage of concept groups must be satisfied
VALIDATION_THRESHOLD = 0.5


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

    def _validate_statement(self, stmt: Dict[str, Any], statement_type: str) -> Tuple[bool, float, str]:
        """
        Validate that a resolved statement contains expected essential concepts.

        This helps catch misclassifications where a statement is incorrectly identified
        (e.g., a tax disclosure being selected as an income statement).

        Args:
            stmt: Statement dictionary with role information
            statement_type: The type of statement being validated

        Returns:
            Tuple of (is_valid, confidence_score, reason)
            - is_valid: True if statement passes validation
            - confidence_score: 0.0 to 1.0 based on concept coverage
            - reason: Human-readable explanation of validation result
        """
        # Get essential concepts for this statement type
        if statement_type not in ESSENTIAL_CONCEPTS:
            # No validation defined for this type - assume valid
            return True, 1.0, "No validation rules defined"

        essential_groups = ESSENTIAL_CONCEPTS[statement_type]
        role = stmt.get('role', '')

        # Check if role exists in presentation trees
        if role not in self.xbrl.presentation_trees:
            return False, 0.0, f"Role {role} not found in presentation trees"

        # Get all concept nodes for this role
        tree = self.xbrl.presentation_trees[role]
        all_nodes = set(tree.all_nodes.keys())

        # Check each group of essential concepts
        groups_satisfied = 0
        total_groups = len(essential_groups)
        missing_groups = []

        for group_name, concepts in essential_groups.items():
            # Check if any concept from this group is present
            group_found = False
            for concept in concepts:
                # Normalize concept name (handle : vs _ separator)
                normalized = concept.replace(':', '_')
                if concept in all_nodes or normalized in all_nodes:
                    group_found = True
                    break

            if group_found:
                groups_satisfied += 1
            else:
                missing_groups.append(group_name)

        # Calculate confidence score
        confidence = groups_satisfied / total_groups if total_groups > 0 else 1.0

        # Determine validity based on threshold
        is_valid = confidence >= VALIDATION_THRESHOLD

        if is_valid:
            if confidence == 1.0:
                reason = "All essential concept groups present"
            else:
                reason = f"Validation passed ({groups_satisfied}/{total_groups} groups): missing {missing_groups}"
        else:
            reason = f"Validation failed ({groups_satisfied}/{total_groups} groups): missing {missing_groups}"

        return is_valid, confidence, reason

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

        # If we found matching statements, sort by quality and return with high confidence
        if matched_statements:
            # Issue #506: Sort by statement quality to prefer correct statement type
            matched_statements.sort(key=lambda s: self._score_statement_quality(s, statement_type), reverse=True)
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

        # If we found matching statements, sort by quality and return with high confidence
        if matched_statements:
            # Issue #506: Sort by statement quality to prefer correct statement type
            matched_statements.sort(key=lambda s: self._score_statement_quality(s, statement_type), reverse=True)
            return matched_statements, matched_statements[0]['role'], 0.85

        return [], None, 0.0

    def _score_statement_quality(self, stmt: Dict[str, Any], statement_type: str = "") -> int:
        """
        Score a statement to prefer complete financial statements over fragments/details.

        Higher scores = more likely to be a complete statement.
        Lower scores = more likely to be a fragment/detail/disclosure.

        Args:
            stmt: Statement dictionary with role, definition, etc.
            statement_type: The type of statement being searched for (e.g., "IncomeStatement")

        Returns:
            Quality score (higher is better)
        """
        score = 100  # Start with base score

        role_def = stmt.get('definition', '').lower()
        role_uri = stmt.get('role', '').lower()

        # Fragment indicators (decrease score significantly)
        fragment_keywords = [
            'details', 'detail', 'tables', 'table', 'schedule', 'schedules',
            'textual', 'narrative', 'policy', 'policies', 'disclosure',
            'supplemental', 'additional', 'breakdown', 'summary'
        ]

        for keyword in fragment_keywords:
            if keyword in role_def or keyword in role_uri:
                score -= 50
                break  # One hit is enough

        # Issue #506/#584: When looking for IncomeStatement, deprioritize PURE ComprehensiveIncome
        # But allow combined "Statement of Operations and Comprehensive Income" which is valid
        if statement_type == "IncomeStatement":
            clean_def = role_def.replace(' ', '').replace('-', '').replace('_', '')
            clean_uri = role_uri.replace(' ', '').replace('-', '').replace('_', '')

            # Check if this is a combined Operations + Comprehensive Income statement
            # These are VALID income statements and should NOT be penalized
            operations_indicators = ['operations', 'statementsofincome', 'statementsofearnings',
                                     'incomestatement', 'operationsand']
            is_combined_statement = any(ind in clean_def or ind in clean_uri for ind in operations_indicators)

            # Only penalize PURE comprehensive income statements (not combined ones)
            # Issue #584: REGN uses "CONSOLIDATEDSTATEMENTSOFOPERATIONSANDCOMPREHENSIVEINCOME"
            # which is a valid income statement that should not be penalized
            if not is_combined_statement:
                comprehensive_indicators = ['comprehensiveincome', 'othercomprehensive']
                for indicator in comprehensive_indicators:
                    if indicator in clean_def or indicator in clean_uri:
                        score -= 100  # Strong penalty only for pure comprehensive income
                        break

            # Issue #581: Penalize tax-related disclosures that may accidentally match
            # e.g., IncomeTaxBenefitProvisionFromContinuingOperationsDetails
            tax_indicators = ['incometax', 'taxbenefit', 'taxprovision', 'taxexpense', 'deferredtax']
            for indicator in tax_indicators:
                if indicator in clean_def or indicator in clean_uri:
                    score -= 100  # Strong penalty to avoid selecting tax disclosure
                    break

        # Issue edgartools-8ad8: Penalize parenthetical statements to prefer main statements
        # Parenthetical statements contain supplementary details (e.g., share counts)
        # and should not be selected when the main statement is available
        if 'parenthetical' in role_def or 'parenthetical' in role_uri:
            score -= 80  # Strong penalty to avoid selecting parenthetical over main statement

        # Prefer "Consolidated" statements (primary statements)
        if 'consolidated' in role_def or 'consolidated' in role_uri:
            score += 30

        # Prefer "Condensed" statements (legitimate abbreviated statements)
        if 'condensed' in role_def or 'condensed' in role_uri:
            score += 20

        # Exact matches for primary statement names get highest priority
        primary_names = [
            'consolidatedbalancesheets',
            'consolidatedstatementsofoperations',
            'consolidatedstatementsofincome',
            'consolidatedstatementsofcashflows',
            'consolidatedstatementsofequity',
            'consolidatedstatementsofstockholdersequity'
        ]

        clean_def = role_def.replace(' ', '').replace('-', '').replace('_', '')
        if clean_def in primary_names:
            score += 50

        # Post-resolution validation: boost/penalize based on essential concept presence
        # This helps catch misclassifications (e.g., tax disclosure selected as income statement)
        if statement_type in ESSENTIAL_CONCEPTS:
            is_valid, validation_conf, reason = self._validate_statement(stmt, statement_type)
            if is_valid:
                # Boost score based on validation confidence
                score += int(validation_conf * 30)  # Up to +30 for fully validated
            else:
                # Penalize statements that fail validation
                score -= 50
                if VERBOSE_EXCEPTIONS:
                    log.debug(f"Statement validation failed for {statement_type}: {reason}")

        return score

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

        # If we found matching statements, sort by quality and return the best
        if matched_statements:
            # Issue #503: Sort by statement quality to prefer complete statements over fragments
            # Issue #506: Pass statement_type to deprioritize ComprehensiveIncome for IncomeStatement
            matched_statements.sort(key=lambda s: self._score_statement_quality(s, statement_type), reverse=True)
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
                    weight_sum = sum(registry_entry.weight_map.values())
                    if weight_sum > 0:
                        confidence = min(total_weight / weight_sum, 1.0)
                    # If weight_sum is 0, keep the base confidence (matches / len(key_concepts))
            else:
                confidence = 0.0

            if confidence > 0:
                statement_scores.append((stmt, confidence))

        # Sort by confidence score
        statement_scores.sort(key=lambda x: x[1], reverse=True)

        # Return best match if above threshold
        if statement_scores and statement_scores[0][1] >= 0.4:
            best_match, confidence = statement_scores[0]

            # Issue #518: Verify the statement type matches (don't return CashFlow for Income)
            matched_type = best_match.get('type', '')
            if matched_type and matched_type != statement_type:
                # Statement type mismatch - the concepts overlap but it's the wrong statement
                log.debug(f"Content match found {matched_type} when looking for {statement_type}, rejecting due to type mismatch")
                return [], None, 0.0

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
                # Issue #506: Sort by statement quality to prefer correct statement type
                statements = sorted(statements, key=lambda s: self._score_statement_quality(s, statement_type), reverse=True)
                # Note: essential-concept validation is applied in the cascade in
                # find_statement(), so we return all candidates here and let the
                # cascade filter out mislabeled roles (Issue #659).
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

        # Issue #518: Don't return completely wrong statement types
        # If looking for a specific financial statement type and it's not found,
        # return empty rather than returning a different statement type
        financial_statement_types = ['BalanceSheet', 'IncomeStatement', 'CashFlowStatement',
                                     'ComprehensiveIncome', 'StatementOfEquity']

        if statement_type in financial_statement_types:
            # For financial statements, don't guess - return empty if not found
            # This prevents returning CashFlowStatement when IncomeStatement is requested
            log.debug(f"Financial statement '{statement_type}' not found, returning empty (no fallback to wrong type)")
            return [], None, 0.0

        # For non-financial statement types (notes, disclosures, etc.), we can be more lenient
        all_statements = self.xbrl.get_all_statements()
        if all_statements:
            # Return first statement with very low confidence
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
        # Normalize snake_case enum values to PascalCase registry keys
        statement_type = _ENUM_TO_REGISTRY.get(statement_type, statement_type)

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

        # Issue #659: Essential-concept validation applies across ALL cascade steps.
        # A role may have the right name/concept but wrong content (e.g., MTD has
        # StatementOfFinancialPositionAbstract as root but only contains Schedule II).
        needs_validation = statement_type in ESSENTIAL_CONCEPTS

        # Cascade through matching strategies in order of confidence
        cascade = [
            (self._match_by_standard_name(statement_type), 0.9),
            (self._match_by_primary_concept(statement_type, is_parenthetical), 0.8),
            (self._match_by_concept_pattern(statement_type, is_parenthetical), 0.8),
            (self._match_by_role_pattern(statement_type, is_parenthetical), 0.7),
            (self._match_by_content(statement_type), 0.6),
            (self._match_by_role_definition(statement_type), 0.5),
        ]

        for match, min_conf in cascade:
            statements, role, conf = match
            if not statements or conf < min_conf:
                continue

            # Issue #659: Validate that the top candidate actually contains the
            # essential concepts for this statement type. Filter out mislabeled roles.
            if needs_validation:
                valid = [s for s in statements
                         if self._validate_statement(s, statement_type)[0]]
                if not valid:
                    continue
                statements = valid
                role = valid[0]['role']

            canonical_type = statement_type if is_canonical_type else statements[0].get('type', statement_type)
            result = (statements, role, canonical_type, conf)
            self._cache[cache_key] = result
            return result

        # Issue #518: Special fallback for IncomeStatement -> ComprehensiveIncome
        # Many filings have ComprehensiveIncome instead of separate IncomeStatement
        # Issue #608: Must validate that ComprehensiveIncome contains actual P&L data (Revenue)
        # Some filings have two roles: one with P&L, one with pure OCI items
        if statement_type == 'IncomeStatement':
            # Get ALL ComprehensiveIncome candidates from the type index directly.
            # We bypass _match_by_standard_name here because its essential-concept
            # filter (Issue #659) validates against ComprehensiveIncome criteria,
            # which discards the P&L-containing statement we actually want.
            # Instead, we validate against IncomeStatement criteria below.
            all_comp_statements = list(self._statement_by_type.get('ComprehensiveIncome', []))

            if all_comp_statements:
                # Issue #608: Sort candidates by IncomeStatement criteria to prefer
                # statements with P&L data (Revenue, Operating Income) over pure OCI statements
                all_comp_statements = sorted(
                    all_comp_statements,
                    key=lambda s: self._score_statement_quality(s, 'IncomeStatement'),
                    reverse=True
                )

                # Issue #608: Find the first candidate that passes IncomeStatement validation
                for candidate in all_comp_statements:
                    is_valid, validation_conf, reason = self._validate_statement(candidate, 'IncomeStatement')
                    if is_valid:
                        role = candidate['role']
                        if VERBOSE_EXCEPTIONS:
                            log.info(f"IncomeStatement not found, using ComprehensiveIncome as fallback (role: {role})")
                        result = ([candidate], role, 'ComprehensiveIncome', 0.90)
                        self._cache[cache_key] = result
                        return result

                if VERBOSE_EXCEPTIONS:
                    log.debug("ComprehensiveIncome fallback rejected: no candidates contain P&L data")

        # No good match found, return best guess with low confidence
        statements, role, conf = self._get_best_guess(statement_type)
        if conf < 0.4:
            # Get entity context for detailed error reporting
            entity_name = getattr(self.xbrl, 'entity_name', 'Unknown')
            cik = getattr(self.xbrl, 'cik', 'Unknown')
            period_of_report = getattr(self.xbrl, 'period_of_report', 'Unknown')

            if len(statements) == 0:
                raise StatementNotFound(
                    statement_type=statement_type,
                    confidence=conf,
                    found_statements=[],
                    entity_name=entity_name,
                    cik=cik,
                    period_of_report=period_of_report,
                    reason="No statements available in XBRL data"
                )
            elif conf < 0.3:
                found_statements = [s['definition'] for s in statements]
                raise StatementNotFound(
                    statement_type=statement_type,
                    confidence=conf,
                    found_statements=found_statements,
                    entity_name=entity_name,
                    cik=cik,
                    period_of_report=period_of_report,
                    reason="Confidence threshold not met"
                )
            else:
                if VERBOSE_EXCEPTIONS:
                    log.warn(
                        f"No good match found for statement type '{statement_type}'. The best guess has low confidence: {conf:.2f}")
        if statements:
            # For canonical types, preserve the original statement_type
            canonical_type = statement_type if is_canonical_type else statements[0].get('type', statement_type)
            result = (statements, role, canonical_type, conf)
        else:
            result = ([], None, statement_type, 0.0)

        self._cache[cache_key] = result
        return result

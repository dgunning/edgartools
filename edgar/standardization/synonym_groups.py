"""
Unified Synonym Management System for EdgarTools.

This module provides centralized synonym group management for XBRL tags,
enabling consistent cross-company financial analysis. It serves as the
foundation for both XBRL and EntityFacts APIs.

The SynonymGroups system allows users to query financial concepts without
needing to know the specific XBRL tag variants used by each company.

Example:
    >>> from edgar.standardization import SynonymGroups
    >>> synonyms = SynonymGroups()
    >>>
    >>> # Get all synonyms for a concept
    >>> revenue_tags = synonyms.get_group('revenue')
    >>> print(revenue_tags.synonyms)
    ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', ...]
    >>>
    >>> # Identify what concept a tag represents
    >>> info = synonyms.identify_concept('us-gaap:Revenues')
    >>> print(info.name)
    'revenue'
    >>>
    >>> # Register custom synonym group
    >>> synonyms.register_group(
    ...     name='custom_capex',
    ...     synonyms=['PaymentsToAcquirePropertyPlantAndEquipment', 'CapitalExpenditures'],
    ...     description='Custom capital expenditure definition'
    ... )

Architecture:
    This module implements Priority 1A (Unified Synonym Management) from the
    EntityFacts/XBRL Standardization sequencing plan. It provides:

    1. Pre-built synonym groups for 40+ common financial concepts
    2. User-extensible groups via JSON import/export
    3. Reverse lookup (tag → concept identification)
    4. Foundation for future StandardizationProfile support

See Also:
    - docs-internal/planning/features/comprehensive-synonym-analysis-solutions.md
    - docs-internal/research/codebase/2025-12-06-entityfacts-xbrl-standardization-sequencing.md
    - Discussion #495 for user requirements
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Union

log = logging.getLogger(__name__)

# Module-level caches
_default_instance: Optional['SynonymGroups'] = None
_builtin_groups_cache: Optional[List['SynonymGroup']] = None


def _normalize_name(name: str) -> str:
    """Normalize a concept name to lowercase with underscores."""
    return name.strip().lower().replace(' ', '_').replace('-', '_')


@dataclass
class SynonymGroup:
    """
    A group of XBRL tags that represent the same financial concept.

    Attributes:
        name: Canonical name for the concept (e.g., 'revenue', 'net_income')
        synonyms: List of XBRL tag names that represent this concept
        description: Human-readable description of the concept
        namespace: Default namespace for tags (default: 'us-gaap')
        priority_order: How to order synonyms when resolving
            - 'listed': Use order as specified in synonyms list
            - 'frequency': Order by usage frequency (most common first)
            - 'specificity': Order by tag specificity (most specific first)
        category: Financial statement category (e.g., 'income_statement', 'balance_sheet')
    """
    name: str
    synonyms: List[str]
    description: str = ""
    namespace: str = "us-gaap"
    priority_order: str = "listed"
    category: str = ""
    # Internal set for O(1) tag membership lookup (not serialized)
    _synonym_set: Set[str] = field(default_factory=set, repr=False, compare=False)

    def __post_init__(self):
        """Normalize the synonym group after initialization."""
        # Ensure name is lowercase with underscores
        self.name = _normalize_name(self.name)
        # Remove namespace prefixes and deduplicate while preserving order
        seen: Set[str] = set()
        deduped: List[str] = []
        for s in self.synonyms:
            stripped = self._strip_namespace(s)
            key = stripped.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(stripped)
        self.synonyms = deduped
        # Reuse the set we already built for O(1) lookup
        self._synonym_set = seen

    @staticmethod
    def _strip_namespace(tag: str) -> str:
        """Remove namespace prefix from tag (e.g., 'us-gaap:Revenue' -> 'Revenue')."""
        if ':' in tag:
            return tag.split(':', 1)[1]
        # Handle underscore format (us-gaap_Revenue)
        if '_' in tag:
            parts = tag.split('_', 1)
            if parts[0].replace('-', '') in ('usgaap', 'dei', 'srt', 'ifrs'):
                return parts[1]
        return tag

    def get_tags_with_namespace(self, namespace: Optional[str] = None) -> List[str]:
        """
        Get synonyms with namespace prefix.

        Args:
            namespace: Namespace to use (default: self.namespace)

        Returns:
            List of tags with namespace prefix
        """
        ns = namespace or self.namespace
        return [f"{ns}:{tag}" for tag in self.synonyms]

    def contains_tag(self, tag: str) -> bool:
        """
        Check if this group contains the given tag.

        Args:
            tag: XBRL tag to check (with or without namespace)

        Returns:
            True if tag is in this group's synonyms
        """
        normalized = self._strip_namespace(tag).lower()
        return normalized in self._synonym_set  # O(1) lookup

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'synonyms': self.synonyms,
            'description': self.description,
            'namespace': self.namespace,
            'priority_order': self.priority_order,
            'category': self.category
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SynonymGroup':
        """Create SynonymGroup from dictionary."""
        return cls(
            name=data['name'],
            synonyms=data['synonyms'],
            description=data.get('description', ''),
            namespace=data.get('namespace', 'us-gaap'),
            priority_order=data.get('priority_order', 'listed'),
            category=data.get('category', '')
        )


@dataclass
class ConceptInfo:
    """
    Information about an identified concept from a tag lookup.

    Attributes:
        name: Canonical concept name
        tag: The original tag that was looked up
        group: The full SynonymGroup containing this concept
        match_type: How the match was found ('exact', 'normalized', 'fuzzy')
    """
    name: str
    tag: str
    group: SynonymGroup
    match_type: str = "exact"

    @property
    def synonyms(self) -> List[str]:
        """Get all synonyms for this concept."""
        return self.group.synonyms

    @property
    def description(self) -> str:
        """Get concept description."""
        return self.group.description

    @property
    def category(self) -> str:
        """Get concept category."""
        return self.group.category


def _get_builtin_groups_cached() -> List[SynonymGroup]:
    """
    Get the pre-built synonym groups (cached at module level).

    These groups are based on:
    - Existing concept_mappings.json from XBRL standardization
    - EntityFacts standardized methods (get_revenue, get_net_income, etc.)
    - User requests from Discussion #495 (Phil Oakley framework)

    The synonyms are ordered by priority (most common/specific first).
    """
    global _builtin_groups_cache
    if _builtin_groups_cache is not None:
        return _builtin_groups_cache

    _builtin_groups_cache = [
        # ═══════════════════════════════════════════════════════════════════
        # INCOME STATEMENT CONCEPTS
        # ═══════════════════════════════════════════════════════════════════
        SynonymGroup(
            name='revenue',
            synonyms=[
                'RevenueFromContractWithCustomerExcludingAssessedTax',
                'RevenueFromContractWithCustomerIncludingAssessedTax',
                'Revenues',
                'Revenue',
                'SalesRevenueNet',
                'SalesRevenueGoodsNet',
                'TotalRevenues',
                'NetSales',
                'OperatingRevenue',
            ],
            description='Total revenue/sales from operations',
            category='income_statement'
        ),
        SynonymGroup(
            name='cost_of_revenue',
            synonyms=[
                'CostOfRevenue',
                'CostOfGoodsAndServicesSold',
                'CostOfGoodsSold',
                'CostOfSales',
                'CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization',
                'DirectOperatingCosts',
            ],
            description='Cost of revenue/goods sold',
            category='income_statement'
        ),
        SynonymGroup(
            name='gross_profit',
            synonyms=[
                'GrossProfit',
            ],
            description='Revenue minus cost of revenue',
            category='income_statement'
        ),
        SynonymGroup(
            name='operating_expenses',
            synonyms=[
                'OperatingExpenses',
                'OperatingCostsAndExpenses',
                'NoninterestExpense',
                'CostsAndExpenses',
            ],
            description='Total operating expenses',
            category='income_statement'
        ),
        SynonymGroup(
            name='research_and_development',
            synonyms=[
                'ResearchAndDevelopmentExpense',
                'ResearchAndDevelopmentCosts',
            ],
            description='Research and development expenses',
            category='income_statement'
        ),
        SynonymGroup(
            name='sga_expense',
            synonyms=[
                'SellingGeneralAndAdministrativeExpense',
                'GeneralAndAdministrativeExpense',
                'SellingAndMarketingExpense',
                'SellingExpense',
                'AdministrativeExpense',
            ],
            description='Selling, general and administrative expenses',
            category='income_statement'
        ),
        SynonymGroup(
            name='operating_income',
            synonyms=[
                'OperatingIncomeLoss',
                'OperatingIncome',
                'IncomeLossFromContinuingOperationsBeforeInterestAndTaxes',
            ],
            description='Operating income/loss',
            category='income_statement'
        ),
        SynonymGroup(
            name='interest_expense',
            synonyms=[
                'InterestExpense',
                'InterestAndDebtExpense',
                'InterestIncomeExpenseNet',
                'InterestExpenseOperating',
                'InterestExpenseNonoperating',
            ],
            description='Interest expense',
            category='income_statement'
        ),
        SynonymGroup(
            name='interest_income',
            synonyms=[
                'InterestIncome',
                'InterestIncomeOperating',
                'InvestmentIncomeInterest',
            ],
            description='Interest income',
            category='income_statement'
        ),
        SynonymGroup(
            name='income_before_tax',
            synonyms=[
                'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
                'IncomeLossFromContinuingOperationsBeforeIncomeTaxes',
                'IncomeLossBeforeIncomeTaxes',
            ],
            description='Income before income taxes',
            category='income_statement'
        ),
        SynonymGroup(
            name='income_tax_expense',
            synonyms=[
                'IncomeTaxExpenseBenefit',
                'IncomeTaxesPaidNet',
            ],
            description='Income tax expense/benefit',
            category='income_statement'
        ),
        SynonymGroup(
            name='net_income',
            synonyms=[
                'NetIncomeLoss',
                'ProfitLoss',
                'NetIncome',
                'NetEarnings',
                'NetIncomeLossAttributableToParent',
                'IncomeLossFromContinuingOperations',
            ],
            description='Net income/loss',
            category='income_statement'
        ),
        SynonymGroup(
            name='earnings_per_share_basic',
            synonyms=[
                'EarningsPerShareBasic',
            ],
            description='Basic earnings per share',
            category='income_statement'
        ),
        SynonymGroup(
            name='earnings_per_share_diluted',
            synonyms=[
                'EarningsPerShareDiluted',
            ],
            description='Diluted earnings per share',
            category='income_statement'
        ),
        SynonymGroup(
            name='depreciation_and_amortization',
            synonyms=[
                'DepreciationAndAmortization',
                'DepreciationDepletionAndAmortization',
                'Depreciation',
                'AmortizationOfIntangibleAssets',
            ],
            description='Depreciation and amortization expense',
            category='income_statement'
        ),
        SynonymGroup(
            name='ebitda',
            synonyms=[
                'EBITDA',
                'EarningsBeforeInterestTaxesDepreciationAndAmortization',
            ],
            description='Earnings before interest, taxes, depreciation and amortization',
            category='income_statement'
        ),

        # ═══════════════════════════════════════════════════════════════════
        # BALANCE SHEET - ASSETS
        # ═══════════════════════════════════════════════════════════════════
        SynonymGroup(
            name='cash_and_equivalents',
            synonyms=[
                'CashAndCashEquivalentsAtCarryingValue',
                'CashCashEquivalentsAndShortTermInvestments',
                'CashEquivalentsAtCarryingValue',
                'Cash',
            ],
            description='Cash and cash equivalents',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='short_term_investments',
            synonyms=[
                'ShortTermInvestments',
                'MarketableSecuritiesCurrent',
                'AvailableForSaleSecuritiesDebtSecuritiesCurrent',
            ],
            description='Short-term investments and marketable securities',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='accounts_receivable',
            synonyms=[
                'AccountsReceivableNetCurrent',
                'AccountsReceivableNet',
                'ReceivablesNetCurrent',
                'AccountsReceivableGross',
            ],
            description='Accounts receivable',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='inventory',
            synonyms=[
                'InventoryNet',
                'InventoryGross',
                'InventoryFinishedGoods',
            ],
            description='Inventory',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='prepaid_expenses',
            synonyms=[
                'PrepaidExpenseAndOtherAssetsCurrent',
                'PrepaidExpenseCurrent',
                'PrepaidExpense',
            ],
            description='Prepaid expenses',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='total_current_assets',
            synonyms=[
                'AssetsCurrent',
            ],
            description='Total current assets',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='property_plant_equipment',
            synonyms=[
                'PropertyPlantAndEquipmentNet',
                'PropertyPlantAndEquipmentGross',
                'FixedAssets',
            ],
            description='Property, plant and equipment',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='goodwill',
            synonyms=[
                'Goodwill',
            ],
            description='Goodwill',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='intangible_assets',
            synonyms=[
                'IntangibleAssetsNetExcludingGoodwill',
                'IntangibleAssetsNetIncludingGoodwill',
                'FiniteLivedIntangibleAssetsNet',
            ],
            description='Intangible assets',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='long_term_investments',
            synonyms=[
                'LongTermInvestments',
                'MarketableSecuritiesNoncurrent',
                'AvailableForSaleSecuritiesDebtSecuritiesNoncurrent',
            ],
            description='Long-term investments',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='deferred_tax_assets',
            synonyms=[
                'DeferredIncomeTaxAssetsNet',
                'DeferredTaxAssetsNet',
                'DeferredTaxAssetsNetCurrent',
                'DeferredTaxAssetsNetNoncurrent',
            ],
            description='Deferred tax assets',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='total_assets',
            synonyms=[
                'Assets',
                'AssetsTotal',
            ],
            description='Total assets',
            category='balance_sheet'
        ),

        # ═══════════════════════════════════════════════════════════════════
        # BALANCE SHEET - LIABILITIES
        # ═══════════════════════════════════════════════════════════════════
        SynonymGroup(
            name='accounts_payable',
            synonyms=[
                'AccountsPayableCurrent',
                'AccountsPayableTradeCurrent',
                'AccountsPayable',
            ],
            description='Accounts payable',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='accrued_liabilities',
            synonyms=[
                'AccruedLiabilitiesCurrent',
                'OtherAccruedLiabilitiesCurrent',
                'EmployeeRelatedLiabilitiesCurrent',
            ],
            description='Accrued liabilities',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='short_term_debt',
            synonyms=[
                'DebtCurrent',
                'ShortTermBorrowings',
                'LongTermDebtCurrent',
                'NotesPayableCurrent',
            ],
            description='Short-term debt',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='deferred_revenue',
            synonyms=[
                'DeferredRevenue',
                'DeferredRevenueCurrent',
                'DeferredRevenueNoncurrent',
                'ContractWithCustomerLiability',
                'ContractWithCustomerLiabilityCurrent',
            ],
            description='Deferred revenue / contract liabilities',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='total_current_liabilities',
            synonyms=[
                'LiabilitiesCurrent',
            ],
            description='Total current liabilities',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='long_term_debt',
            synonyms=[
                'LongTermDebtNoncurrent',
                'LongTermDebt',
                'LongTermDebtAndCapitalLeaseObligations',
                'LongTermBorrowings',
                'LongTermNotesAndLoans',
            ],
            description='Long-term debt',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='deferred_tax_liabilities',
            synonyms=[
                'DeferredIncomeTaxLiabilitiesNet',
                'DeferredTaxLiabilitiesNoncurrent',
            ],
            description='Deferred tax liabilities',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='total_liabilities',
            synonyms=[
                'Liabilities',
                'LiabilitiesTotal',
            ],
            description='Total liabilities',
            category='balance_sheet'
        ),

        # ═══════════════════════════════════════════════════════════════════
        # BALANCE SHEET - EQUITY
        # ═══════════════════════════════════════════════════════════════════
        SynonymGroup(
            name='common_stock',
            synonyms=[
                'CommonStockValue',
                'CommonStocksIncludingAdditionalPaidInCapital',
                'StockholdersEquityCommonStock',
            ],
            description='Common stock value',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='additional_paid_in_capital',
            synonyms=[
                'AdditionalPaidInCapital',
                'AdditionalPaidInCapitalCommonStock',
            ],
            description='Additional paid-in capital',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='retained_earnings',
            synonyms=[
                'RetainedEarningsAccumulatedDeficit',
                'RetainedEarnings',
            ],
            description='Retained earnings',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='treasury_stock',
            synonyms=[
                'TreasuryStockValue',
                'TreasuryStockCommonValue',
            ],
            description='Treasury stock',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='accumulated_other_comprehensive_income',
            synonyms=[
                'AccumulatedOtherComprehensiveIncomeLossNetOfTax',
                'AccumulatedOtherComprehensiveIncomeLoss',
            ],
            description='Accumulated other comprehensive income/loss',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='stockholders_equity',
            synonyms=[
                'StockholdersEquity',
                'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
                'StockholdersEquityAttributableToParent',
                'EquityAttributableToParent',
                'ShareholdersEquity',
                'TotalEquity',
                'PartnersCapital',
                'MembersEquity',
            ],
            description='Total stockholders equity',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='common_shares_outstanding',
            synonyms=[
                'CommonStockSharesOutstanding',
                'WeightedAverageNumberOfSharesOutstandingBasic',
            ],
            description='Common shares outstanding',
            category='balance_sheet'
        ),

        # ═══════════════════════════════════════════════════════════════════
        # CASH FLOW STATEMENT
        # ═══════════════════════════════════════════════════════════════════
        SynonymGroup(
            name='operating_cash_flow',
            synonyms=[
                'NetCashProvidedByUsedInOperatingActivities',
                'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
            ],
            description='Net cash from operating activities',
            category='cash_flow'
        ),
        SynonymGroup(
            name='investing_cash_flow',
            synonyms=[
                'NetCashProvidedByUsedInInvestingActivities',
                'NetCashProvidedByUsedInInvestingActivitiesContinuingOperations',
            ],
            description='Net cash from investing activities',
            category='cash_flow'
        ),
        SynonymGroup(
            name='financing_cash_flow',
            synonyms=[
                'NetCashProvidedByUsedInFinancingActivities',
                'NetCashProvidedByUsedInFinancingActivitiesContinuingOperations',
            ],
            description='Net cash from financing activities',
            category='cash_flow'
        ),
        SynonymGroup(
            name='capex',
            synonyms=[
                'PaymentsToAcquirePropertyPlantAndEquipment',
                'CapitalExpenditures',
                'PurchaseOfPropertyPlantAndEquipment',
                'PaymentsToAcquireProductiveAssets',
            ],
            description='Capital expenditures',
            category='cash_flow'
        ),
        SynonymGroup(
            name='dividends_paid',
            synonyms=[
                'PaymentsOfDividends',
                'PaymentsOfDividendsCommonStock',
                'DividendsPaid',
            ],
            description='Dividends paid',
            category='cash_flow'
        ),
        SynonymGroup(
            name='share_repurchases',
            synonyms=[
                'PaymentsForRepurchaseOfCommonStock',
                'StockRepurchasedDuringPeriodValue',
                'PaymentsForRepurchaseOfEquity',
            ],
            description='Share repurchases/buybacks',
            category='cash_flow'
        ),
        SynonymGroup(
            name='debt_repayment',
            synonyms=[
                'RepaymentsOfLongTermDebt',
                'RepaymentsOfDebt',
                'RepaymentsOfShortTermDebt',
            ],
            description='Debt repayments',
            category='cash_flow'
        ),
        SynonymGroup(
            name='debt_proceeds',
            synonyms=[
                'ProceedsFromIssuanceOfLongTermDebt',
                'ProceedsFromDebtNetOfIssuanceCosts',
                'ProceedsFromIssuanceOfDebt',
            ],
            description='Proceeds from debt issuance',
            category='cash_flow'
        ),
        SynonymGroup(
            name='free_cash_flow',
            synonyms=[
                'FreeCashFlow',
            ],
            description='Free cash flow (operating cash flow minus capex)',
            category='cash_flow'
        ),

        # ═══════════════════════════════════════════════════════════════════
        # LEASE-RELATED (Discussion #495 - Phil Oakley Framework)
        # ═══════════════════════════════════════════════════════════════════
        SynonymGroup(
            name='operating_lease_payments',
            synonyms=[
                'OperatingLeasePayments',
                'PaymentsForOperatingLeases',
                'LesseeOperatingLeaseLiabilityPaymentsDue',
                'OperatingLeasesFutureMinimumPaymentsDue',
            ],
            description='Operating lease payments (Phil Oakley framework)',
            category='cash_flow'
        ),
        SynonymGroup(
            name='operating_lease_liability',
            synonyms=[
                'OperatingLeaseLiability',
                'OperatingLeaseLiabilityCurrent',
                'OperatingLeaseLiabilityNoncurrent',
            ],
            description='Operating lease liability',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='operating_lease_right_of_use_asset',
            synonyms=[
                'OperatingLeaseRightOfUseAsset',
                'RightOfUseAssetObtainedInExchangeForOperatingLeaseLiability',
            ],
            description='Operating lease right-of-use asset',
            category='balance_sheet'
        ),
        SynonymGroup(
            name='finance_lease_liability',
            synonyms=[
                'FinanceLeaseLiability',
                'FinanceLeaseLiabilityCurrent',
                'FinanceLeaseLiabilityNoncurrent',
                'CapitalLeaseObligations',
            ],
            description='Finance/capital lease liability',
            category='balance_sheet'
        ),

        # ═══════════════════════════════════════════════════════════════════
        # FINANCIAL RATIOS / METRICS
        # ═══════════════════════════════════════════════════════════════════
        SynonymGroup(
            name='book_value_per_share',
            synonyms=[
                'BookValuePerShare',
                'BookValuePerShareCommon',
            ],
            description='Book value per share',
            category='metrics'
        ),
        SynonymGroup(
            name='return_on_equity',
            synonyms=[
                'ReturnOnEquity',
                'ROE',
            ],
            description='Return on equity',
            category='metrics'
        ),
        SynonymGroup(
            name='return_on_assets',
            synonyms=[
                'ReturnOnAssets',
                'ROA',
            ],
            description='Return on assets',
            category='metrics'
        ),
    ]
    return _builtin_groups_cache


class SynonymGroups:
    """
    Centralized manager for XBRL tag synonym groups.

    Provides a unified interface for managing synonym groups that can be used
    across both XBRL and EntityFacts APIs. This is the foundation for the
    shared standardization infrastructure.

    The manager comes pre-loaded with 40+ common financial concept groups
    (revenue, net_income, capex, operating_lease_payments, etc.) and supports
    user-defined custom groups.

    Example:
        >>> synonyms = SynonymGroups()
        >>>
        >>> # Get pre-built group
        >>> revenue = synonyms.get_group('revenue')
        >>> print(revenue.synonyms[:3])
        ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'Revenue']
        >>>
        >>> # Identify concept from tag
        >>> info = synonyms.identify_concept('NetIncomeLoss')
        >>> print(info.name)
        'net_income'
        >>>
        >>> # Register custom group
        >>> synonyms.register_group(
        ...     name='my_revenue',
        ...     synonyms=['CustomRevenue1', 'CustomRevenue2']
        ... )
        >>>
        >>> # Export for sharing
        >>> synonyms.export_to_json('my_groups.json')

    Attributes:
        _groups: Dictionary of name -> SynonymGroup
        _tag_index: Reverse index of tag -> group name for fast lookups
    """

    def __init__(self, load_builtin: bool = True):
        """
        Initialize SynonymGroups manager.

        Args:
            load_builtin: Whether to load pre-built synonym groups (default: True)
        """
        self._groups: Dict[str, SynonymGroup] = {}
        self._tag_index: Dict[str, List[str]] = {}  # tag -> [group_name1, group_name2, ...]
        self._user_groups: Dict[str, SynonymGroup] = {}  # Track user-defined groups

        if load_builtin:
            self._load_builtin_groups()

    def _load_builtin_groups(self) -> None:
        """Load pre-built synonym groups for common financial concepts."""
        builtin_groups = _get_builtin_groups_cached()
        for group in builtin_groups:
            self._register_group_internal(group, is_user_defined=False)

    def _register_group_internal(self, group: SynonymGroup, is_user_defined: bool = False) -> None:
        """
        Internal method to register a group and update indices.

        Tags can belong to multiple groups (multi-group membership). This allows
        concepts like DepreciationAndAmortization to appear in both income_statement
        and cash_flow contexts.

        Args:
            group: The SynonymGroup to register
            is_user_defined: Whether this is a user-defined group
        """
        self._groups[group.name] = group

        if is_user_defined:
            self._user_groups[group.name] = group

        # Update reverse index - append to list to support multi-group membership
        for tag in group.synonyms:
            tag_lower = tag.lower()
            if tag_lower not in self._tag_index:
                self._tag_index[tag_lower] = []
            # Avoid duplicates if same group is re-registered
            if group.name not in self._tag_index[tag_lower]:
                self._tag_index[tag_lower].append(group.name)

    def get_group(self, name: str) -> Optional[SynonymGroup]:
        """
        Get a synonym group by name.

        Args:
            name: The canonical name of the concept (e.g., 'revenue', 'net_income')

        Returns:
            SynonymGroup if found, None otherwise

        Example:
            >>> synonyms = SynonymGroups()
            >>> revenue = synonyms.get_group('revenue')
            >>> print(revenue.synonyms[:2])
            ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues']
        """
        normalized = _normalize_name(name)
        return self._groups.get(normalized)

    def get_synonyms(self, name: str) -> List[str]:
        """
        Get the list of synonyms for a concept.

        Convenience method that returns just the synonym list.

        Args:
            name: The canonical name of the concept

        Returns:
            List of synonym tags, or empty list if not found

        Example:
            >>> synonyms = SynonymGroups()
            >>> tags = synonyms.get_synonyms('capex')
            >>> print(tags[:2])
            ['PaymentsToAcquirePropertyPlantAndEquipment', 'CapitalExpenditures']
        """
        group = self.get_group(name)
        return group.synonyms if group else []

    def identify_concept(self, tag: str) -> Optional[ConceptInfo]:
        """
        Identify which concept a tag belongs to (returns first match).

        Performs reverse lookup to find the canonical concept name
        for a given XBRL tag. If the tag belongs to multiple groups,
        returns the first one (order of registration).

        For tags that may belong to multiple concepts, use identify_concepts()
        to get all matches.

        Args:
            tag: XBRL tag to identify (with or without namespace prefix)

        Returns:
            ConceptInfo if tag is recognized, None otherwise

        Example:
            >>> synonyms = SynonymGroups()
            >>> info = synonyms.identify_concept('us-gaap:NetIncomeLoss')
            >>> print(info.name)
            'net_income'
            >>> print(info.description)
            'Net income/loss'
        """
        # Normalize tag
        normalized = SynonymGroup._strip_namespace(tag).lower()

        # Look up in index - returns list of group names
        group_names = self._tag_index.get(normalized, [])
        if group_names:
            group_name = group_names[0]  # Return first match
            group = self._groups[group_name]
            return ConceptInfo(
                name=group_name,
                tag=tag,
                group=group,
                match_type='exact'
            )

        return None

    def identify_concepts(self, tag: str) -> List[ConceptInfo]:
        """
        Identify all concepts a tag belongs to.

        Performs reverse lookup to find all canonical concept names
        for a given XBRL tag. Tags can belong to multiple groups
        (multi-group membership) when they have different meanings
        in different contexts.

        For example, DepreciationAndAmortization could belong to both
        an income_statement concept (as an expense) and a cash_flow
        concept (as an adjustment).

        Args:
            tag: XBRL tag to identify (with or without namespace prefix)

        Returns:
            List of ConceptInfo for all matching groups (empty if not recognized)

        Example:
            >>> synonyms = SynonymGroups()
            >>> # If a tag belongs to multiple groups:
            >>> infos = synonyms.identify_concepts('DepreciationAndAmortization')
            >>> for info in infos:
            ...     print(f"{info.name} ({info.category})")
            depreciation_and_amortization (income_statement)
            >>>
            >>> # Filter by category for context-aware selection:
            >>> cash_flow_concepts = [i for i in infos if i.category == 'cash_flow']
        """
        # Normalize tag
        normalized = SynonymGroup._strip_namespace(tag).lower()

        # Look up in index - returns list of group names
        group_names = self._tag_index.get(normalized, [])

        results = []
        for group_name in group_names:
            group = self._groups[group_name]
            results.append(ConceptInfo(
                name=group_name,
                tag=tag,
                group=group,
                match_type='exact'
            ))

        return results

    def register_group(
        self,
        name: str,
        synonyms: List[str],
        description: str = "",
        namespace: str = "us-gaap",
        priority_order: str = "listed",
        category: str = ""
    ) -> SynonymGroup:
        """
        Register a custom synonym group.

        User-defined groups take precedence over built-in groups
        if there are naming conflicts.

        Args:
            name: Canonical name for the concept
            synonyms: List of XBRL tags that represent this concept
            description: Human-readable description
            namespace: Default namespace for tags
            priority_order: How to order synonyms ('listed', 'frequency', 'specificity')
            category: Financial statement category

        Returns:
            The registered SynonymGroup

        Example:
            >>> synonyms = SynonymGroups()
            >>> group = synonyms.register_group(
            ...     name='custom_capex',
            ...     synonyms=['PaymentsToAcquirePropertyPlantAndEquipment', 'CapitalExpenditures'],
            ...     description='Custom CAPEX for FCFF calculation'
            ... )
        """
        group = SynonymGroup(
            name=name,
            synonyms=synonyms,
            description=description,
            namespace=namespace,
            priority_order=priority_order,
            category=category
        )
        self._register_group_internal(group, is_user_defined=True)
        log.info(f"Registered custom synonym group: {group.name}")
        return group

    def unregister_group(self, name: str) -> bool:
        """
        Remove a user-defined synonym group.

        Only user-defined groups can be removed. Built-in groups
        cannot be unregistered.

        Args:
            name: Name of the group to remove

        Returns:
            True if group was removed, False if not found or is built-in
        """
        normalized = _normalize_name(name)

        if normalized not in self._user_groups:
            log.warning(f"Cannot unregister group '{name}': not a user-defined group")
            return False

        group = self._groups.pop(normalized, None)
        self._user_groups.pop(normalized, None)

        if group:
            # Remove from index - handle list-based index
            for tag in group.synonyms:
                tag_lower = tag.lower()
                if tag_lower in self._tag_index:
                    group_list = self._tag_index[tag_lower]
                    if normalized in group_list:
                        group_list.remove(normalized)
                    # Clean up empty lists
                    if not group_list:
                        del self._tag_index[tag_lower]
            return True

        return False

    def list_groups(self, category: Optional[str] = None) -> List[str]:
        """
        List all available synonym group names.

        Args:
            category: Optional filter by category (e.g., 'income_statement', 'balance_sheet')

        Returns:
            List of group names, sorted alphabetically

        Example:
            >>> synonyms = SynonymGroups()
            >>> groups = synonyms.list_groups(category='cash_flow')
            >>> print(groups)
            ['capex', 'dividends_paid', 'financing_cash_flow', ...]
        """
        if category:
            return sorted([
                name for name, group in self._groups.items()
                if group.category == category
            ])
        return sorted(self._groups.keys())

    def list_categories(self) -> List[str]:
        """
        List all available categories.

        Returns:
            List of unique categories
        """
        categories = set(group.category for group in self._groups.values() if group.category)
        return sorted(categories)

    def export_to_json(self, path: Union[str, Path], include_builtin: bool = False) -> None:
        """
        Export synonym groups to a JSON file.

        By default, exports only user-defined groups. Use include_builtin=True
        to include all groups.

        Args:
            path: Path to write JSON file
            include_builtin: Include built-in groups in export (default: False)

        Example:
            >>> synonyms = SynonymGroups()
            >>> synonyms.register_group('custom_revenue', ['MyRevenue1', 'MyRevenue2'])
            >>> synonyms.export_to_json('my_groups.json')
        """
        path = Path(path)

        if include_builtin:
            groups_to_export = self._groups.values()
        else:
            groups_to_export = self._user_groups.values()

        data = {
            'version': '1.0',
            'groups': [group.to_dict() for group in groups_to_export]
        }

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

        log.info(f"Exported {len(data['groups'])} groups to {path}")

    def import_from_json(self, path: Union[str, Path]) -> int:
        """
        Import synonym groups from a JSON file.

        Imported groups are treated as user-defined and can override
        built-in groups.

        Args:
            path: Path to JSON file

        Returns:
            Number of groups imported

        Example:
            >>> synonyms = SynonymGroups()
            >>> count = synonyms.import_from_json('team_groups.json')
            >>> print(f"Imported {count} groups")
        """
        path = Path(path)

        with open(path, 'r') as f:
            data = json.load(f)

        groups = data.get('groups', [])
        count = 0

        for group_data in groups:
            group = SynonymGroup.from_dict(group_data)
            self._register_group_internal(group, is_user_defined=True)
            count += 1

        log.info(f"Imported {count} groups from {path}")
        return count

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> 'SynonymGroups':
        """
        Create a SynonymGroups instance from a JSON file.

        Loads built-in groups first, then overlays groups from file.

        Args:
            path: Path to JSON file

        Returns:
            New SynonymGroups instance

        Example:
            >>> synonyms = SynonymGroups.from_file('/shared/config/company_synonyms.json')
        """
        instance = cls(load_builtin=True)
        instance.import_from_json(path)
        return instance

    def __len__(self) -> int:
        """Return number of registered groups."""
        return len(self._groups)

    def __contains__(self, name: str) -> bool:
        """Check if a group name exists."""
        normalized = _normalize_name(name)
        return normalized in self._groups

    def __iter__(self) -> Iterator[str]:
        """Iterate over group names."""
        return iter(self._groups.keys())

    def __repr__(self) -> str:
        return f"SynonymGroups(groups={len(self._groups)}, user_defined={len(self._user_groups)})"


def get_synonym_groups() -> SynonymGroups:
    """
    Get the default SynonymGroups instance (singleton).

    This function returns a cached singleton instance for efficiency.
    Use SynonymGroups() directly if you need a fresh instance.

    Returns:
        Default SynonymGroups instance

    Example:
        >>> from edgar.standardization import get_synonym_groups
        >>> synonyms = get_synonym_groups()
        >>> tags = synonyms.get_synonyms('revenue')
    """
    global _default_instance
    if _default_instance is None:
        _default_instance = SynonymGroups()
    return _default_instance


def reset_synonym_groups() -> None:
    """
    Reset the singleton instance (primarily for testing).

    This clears the cached singleton so the next call to
    get_synonym_groups() creates a fresh instance.
    """
    global _default_instance
    _default_instance = None

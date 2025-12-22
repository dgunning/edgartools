"""
Shared XBRL concept definitions for balance types and deprecated normalization lists.

This module contains balance type mappings for common US-GAAP concepts to support
the balance column in DataFrame exports without parsing full taxonomy schemas.

DEPRECATED: Static normalization concept lists (CONSISTENT_POSITIVE_CONCEPTS,
LEGITIMATE_NEGATIVE_CONCEPTS) are kept for historical reference but no longer used.
Testing confirmed that SEC XBRL instance data is already consistent across companies.
See Issue #463 analysis for details.
"""

# =============================================================================
# DEPRECATED CONCEPT LISTS (No longer used as of Issue #463)
# =============================================================================
# These lists were created to work around perceived inconsistencies in XBRL data.
# Testing revealed that raw SEC instance data is ALREADY consistent across companies.
#
# Historical context:
# - Issues #290, #334, #451 reported negative values for expenses
# - Root cause: EdgarTools was misusing calculation weights for display logic
# - These lists fixed symptoms but not the actual problem
# - Issue #463 removed calculation weight application during parsing
# - Result: Raw values preserved as-is (matching SEC CompanyFacts API)
#
# Kept for historical reference and potential future use cases.
# =============================================================================

CONSISTENT_POSITIVE_CONCEPTS = {
    # Research and Development Expenses
    'us-gaap_ResearchAndDevelopmentExpense',
    'us_gaap_ResearchAndDevelopmentExpense',
    'ResearchAndDevelopmentExpense',

    # Selling, General & Administrative Expenses
    'us-gaap_SellingGeneralAndAdministrativeExpense',
    'us_gaap_SellingGeneralAndAdministrativeExpense',
    'SellingGeneralAndAdministrativeExpense',

    # General and Administrative Expenses (separate from SG&A)
    'us-gaap_GeneralAndAdministrativeExpense',
    'us_gaap_GeneralAndAdministrativeExpense',
    'GeneralAndAdministrativeExpense',

    # Selling Expenses
    'us-gaap_SellingExpense',
    'us_gaap_SellingExpense',
    'SellingExpense',

    # Marketing and Advertising Expenses
    'us-gaap_SellingAndMarketingExpense',
    'us_gaap_SellingAndMarketingExpense',
    'SellingAndMarketingExpense',
    'us-gaap_MarketingExpense',
    'us_gaap_MarketingExpense',
    'MarketingExpense',
    'us-gaap_AdvertisingExpense',
    'us_gaap_AdvertisingExpense',
    'AdvertisingExpense',

    # Share-based Compensation Expenses
    'us-gaap_AllocatedShareBasedCompensationExpense',
    'us_gaap_AllocatedShareBasedCompensationExpense',
    'AllocatedShareBasedCompensationExpense',
    'us-gaap_ShareBasedCompensationArrangementByShareBasedPaymentAwardExpenseRecognized',
    'us_gaap_ShareBasedCompensationArrangementByShareBasedPaymentAwardExpenseRecognized',
    'ShareBasedCompensationArrangementByShareBasedPaymentAwardExpenseRecognized',

    # Operating Expenses (general)
    'us-gaap_OperatingExpenses',
    'us_gaap_OperatingExpenses',
    'OperatingExpenses',

    # Professional Services Expenses
    'us-gaap_ProfessionalServiceFees',
    'us_gaap_ProfessionalServiceFees',
    'ProfessionalServiceFees',

    # Compensation and Benefits
    'us-gaap_LaborAndRelatedExpense',
    'us_gaap_LaborAndRelatedExpense',
    'LaborAndRelatedExpense',
    'us-gaap_EmployeeBenefitsExpense',
    'us_gaap_EmployeeBenefitsExpense',
    'EmployeeBenefitsExpense',

    # Cost of Revenue and Cost of Goods/Services Sold (Issue #290, #451)
    'us-gaap_CostOfRevenue',
    'us_gaap_CostOfRevenue',
    'CostOfRevenue',
    'us-gaap_CostOfGoodsAndServicesSold',
    'us_gaap_CostOfGoodsAndServicesSold',
    'CostOfGoodsAndServicesSold',
    'us-gaap_CostOfGoodsSold',
    'us_gaap_CostOfGoodsSold',
    'CostOfGoodsSold',
    'us-gaap_CostOfServices',
    'us_gaap_CostOfServices',
    'CostOfServices',

    # Income Tax Expense (Issue #451)
    'us-gaap_IncomeTaxExpenseBenefit',
    'us_gaap_IncomeTaxExpenseBenefit',
    'IncomeTaxExpenseBenefit',
    'us-gaap_IncomeTaxRecoveryExpense',
    'us_gaap_IncomeTaxRecoveryExpense',
    'IncomeTaxRecoveryExpense',

    # Cash Flow Statement - Financing Activities (cash outflows)
    # These represent uses of cash that should always be positive
    'us-gaap_PaymentsForRepurchaseOfCommonStock',
    'us_gaap_PaymentsForRepurchaseOfCommonStock',
    'PaymentsForRepurchaseOfCommonStock',
    'us-gaap_PaymentsOfDividends',
    'us_gaap_PaymentsOfDividends',
    'PaymentsOfDividends',
    'us-gaap_PaymentsOfDividendsCommonStock',
    'us_gaap_PaymentsOfDividendsCommonStock',
    'PaymentsOfDividendsCommonStock',
    'us-gaap_PaymentsOfDividendsPreferredStockAndPreferenceStock',
    'us_gaap_PaymentsOfDividendsPreferredStockAndPreferenceStock',
    'PaymentsOfDividendsPreferredStockAndPreferenceStock'
}

# DEPRECATED: Concepts that can legitimately be negative
# This list is no longer used but kept for historical reference.
LEGITIMATE_NEGATIVE_CONCEPTS = {
    # Interest expense/income that can be net negative
    'us-gaap_InterestIncomeExpenseNet',
    'us_gaap_InterestIncomeExpenseNet',
    'InterestIncomeExpenseNet',

    # Foreign exchange gains/losses
    'us-gaap_ForeignCurrencyTransactionGainLossBeforeTax',
    'us_gaap_ForeignCurrencyTransactionGainLossBeforeTax',
    'ForeignCurrencyTransactionGainLossBeforeTax',

    # Restructuring reversals/credits
    'us-gaap_RestructuringChargesAndReversals',
    'us_gaap_RestructuringChargesAndReversals',
    'RestructuringChargesAndReversals'
}

# US-GAAP Balance Type Mappings (Issue #463)
#
# This mapping provides balance types for common US-GAAP concepts to support
# the balance column in DataFrame exports without requiring full taxonomy parsing.
#
# Balance types:
#   - "debit": Assets, Expenses (increase with debits, decrease with credits)
#   - "credit": Liabilities, Equity, Revenue (increase with credits, decrease with debits)
#
# TODO: Eventually replace with full US-GAAP taxonomy parser that follows schema imports
#
US_GAAP_BALANCE_TYPES = {
    # ============================================================================
    # ASSETS (Balance: debit)
    # ============================================================================

    # Current Assets
    'us-gaap:Cash': 'debit',
    'Cash': 'debit',  # Short form
    'us-gaap:CashAndCashEquivalentsAtCarryingValue': 'debit',
    'CashAndCashEquivalentsAtCarryingValue': 'debit',  # Short form
    'us-gaap:CashEquivalentsAtCarryingValue': 'debit',
    'us-gaap:RestrictedCashAndCashEquivalents': 'debit',
    'us-gaap:MarketableSecurities': 'debit',
    'us-gaap:AvailableForSaleSecuritiesDebtSecurities': 'debit',
    'us-gaap:ShortTermInvestments': 'debit',
    'us-gaap:AccountsReceivableNetCurrent': 'debit',
    'us-gaap:AccountsReceivableGrossCurrent': 'debit',
    'us-gaap:Inventory': 'debit',
    'us-gaap:InventoryNet': 'debit',
    'us-gaap:PrepaidExpenseAndOtherAssetsCurrent': 'debit',
    'us-gaap:DeferredTaxAssetsNetCurrent': 'debit',
    'us-gaap:OtherAssetsCurrent': 'debit',
    'us-gaap:AssetsCurrent': 'debit',

    # Non-Current Assets
    'us-gaap:PropertyPlantAndEquipmentNet': 'debit',
    'us-gaap:PropertyPlantAndEquipmentGross': 'debit',
    'us-gaap:Land': 'debit',
    'us-gaap:BuildingsAndImprovementsGross': 'debit',
    'us-gaap:MachineryAndEquipmentGross': 'debit',
    'us-gaap:Goodwill': 'debit',
    'us-gaap:IntangibleAssetsNetExcludingGoodwill': 'debit',
    'us-gaap:IntangibleAssetsGrossExcludingGoodwill': 'debit',
    'us-gaap:LongTermInvestments': 'debit',
    'us-gaap:DeferredTaxAssetsNetNoncurrent': 'debit',
    'us-gaap:OtherAssetsNoncurrent': 'debit',
    'us-gaap:AssetsNoncurrent': 'debit',
    'us-gaap:Assets': 'debit',
    'Assets': 'debit',  # Short form

    # ============================================================================
    # LIABILITIES (Balance: credit)
    # ============================================================================

    # Current Liabilities
    'us-gaap:AccountsPayableCurrent': 'credit',
    'us-gaap:AccruedLiabilitiesCurrent': 'credit',
    'us-gaap:DeferredRevenueCurrent': 'credit',
    'us-gaap:ContractWithCustomerLiabilityCurrent': 'credit',
    'us-gaap:ShortTermBorrowings': 'credit',
    'us-gaap:LongTermDebtCurrent': 'credit',
    'us-gaap:CommercialPaper': 'credit',
    'us-gaap:AccruedIncomeTaxesCurrent': 'credit',
    'us-gaap:DividendsPayableCurrent': 'credit',
    'us-gaap:OtherLiabilitiesCurrent': 'credit',
    'us-gaap:LiabilitiesCurrent': 'credit',

    # Non-Current Liabilities
    'us-gaap:LongTermDebtNoncurrent': 'credit',
    'us-gaap:LongTermDebtAndCapitalLeaseObligations': 'credit',
    'us-gaap:DeferredRevenueNoncurrent': 'credit',
    'us-gaap:DeferredTaxLiabilitiesNoncurrent': 'credit',
    'us-gaap:PensionAndOtherPostretirementDefinedBenefitPlansLiabilitiesNoncurrent': 'credit',
    'us-gaap:OtherLiabilitiesNoncurrent': 'credit',
    'us-gaap:LiabilitiesNoncurrent': 'credit',
    'us-gaap:Liabilities': 'credit',

    # ============================================================================
    # EQUITY (Balance: credit)
    # ============================================================================

    'us-gaap:CommonStockValue': 'credit',
    'us-gaap:CommonStockSharesIssued': 'credit',
    'us-gaap:CommonStockSharesOutstanding': 'credit',
    'us-gaap:PreferredStockValue': 'credit',
    'us-gaap:AdditionalPaidInCapital': 'credit',
    'us-gaap:AdditionalPaidInCapitalCommonStock': 'credit',
    'us-gaap:RetainedEarningsAccumulatedDeficit': 'credit',
    'us-gaap:TreasuryStockValue': 'debit',  # Contra-equity (debit balance)
    'us-gaap:AccumulatedOtherComprehensiveIncomeLossNetOfTax': 'credit',
    'us-gaap:StockholdersEquity': 'credit',
    'us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest': 'credit',
    'us-gaap:LiabilitiesAndStockholdersEquity': 'credit',

    # ============================================================================
    # REVENUE (Balance: credit)
    # ============================================================================

    'us-gaap:Revenues': 'credit',
    'Revenues': 'credit',  # Short form
    'Revenue': 'credit',  # Short form (singular)
    'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax': 'credit',
    'RevenueFromContractWithCustomerExcludingAssessedTax': 'credit',  # Short form
    'us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax': 'credit',
    'RevenueFromContractWithCustomerIncludingAssessedTax': 'credit',  # Short form
    'us-gaap:SalesRevenueNet': 'credit',
    'us-gaap:SalesRevenueGoodsNet': 'credit',
    'us-gaap:SalesRevenueServicesNet': 'credit',
    'us-gaap:InterestAndDividendIncomeOperating': 'credit',
    'us-gaap:InterestIncomeOther': 'credit',
    'us-gaap:InvestmentIncomeInterest': 'credit',
    'us-gaap:GainLossOnSaleOfPropertyPlantEquipment': 'credit',
    'us-gaap:GainLossOnInvestments': 'credit',
    'us-gaap:OtherNonoperatingIncomeExpense': 'credit',

    # ============================================================================
    # EXPENSES & COSTS (Balance: debit)
    # ============================================================================

    # Cost of Revenue
    'us-gaap:CostOfRevenue': 'debit',
    'us-gaap:CostOfGoodsAndServicesSold': 'debit',
    'us-gaap:CostOfGoodsSold': 'debit',
    'us-gaap:CostOfServices': 'debit',

    # Operating Expenses
    'us-gaap:ResearchAndDevelopmentExpense': 'debit',
    'us-gaap:SellingGeneralAndAdministrativeExpense': 'debit',
    'us-gaap:GeneralAndAdministrativeExpense': 'debit',
    'us-gaap:SellingExpense': 'debit',
    'us-gaap:SellingAndMarketingExpense': 'debit',
    'us-gaap:MarketingExpense': 'debit',
    'us-gaap:AdvertisingExpense': 'debit',
    'us-gaap:DepreciationDepletionAndAmortization': 'debit',
    'us-gaap:Depreciation': 'debit',
    'us-gaap:AmortizationOfIntangibleAssets': 'debit',
    'us-gaap:RestructuringCharges': 'debit',
    'us-gaap:AssetImpairmentCharges': 'debit',
    'us-gaap:ShareBasedCompensation': 'debit',

    # Other Expenses
    'us-gaap:InterestExpense': 'debit',
    'us-gaap:InterestExpenseDebt': 'debit',
    'us-gaap:IncomeTaxExpenseBenefit': 'debit',
    'us-gaap:ProvisionForDoubtfulAccounts': 'debit',

    # ============================================================================
    # INCOME & TOTALS (Balance: credit)
    # ============================================================================

    'us-gaap:GrossProfit': 'credit',
    'us-gaap:OperatingIncomeLoss': 'credit',
    'us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest': 'credit',
    'us-gaap:IncomeLossFromContinuingOperations': 'credit',
    'us-gaap:NetIncomeLoss': 'credit',
    'us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic': 'credit',
    'us-gaap:NetIncomeLossAvailableToCommonStockholdersDiluted': 'credit',
    'us-gaap:ComprehensiveIncomeNetOfTax': 'credit',

    # ============================================================================
    # CASH FLOW STATEMENT
    # ============================================================================

    # Operating Activities
    'us-gaap:NetCashProvidedByUsedInOperatingActivities': 'debit',
    'us-gaap:DepreciationAndAmortization': 'debit',
    'us-gaap:ShareBasedCompensationArrangementByShareBasedPaymentAwardExpenseRecognized': 'debit',
    'us-gaap:DeferredIncomeTaxExpenseBenefit': 'debit',

    # Investing Activities
    'us-gaap:NetCashProvidedByUsedInInvestingActivities': 'debit',
    'us-gaap:PaymentsToAcquirePropertyPlantAndEquipment': 'credit',  # Cash outflow
    'us-gaap:PaymentsToAcquireBusinessesNetOfCashAcquired': 'credit',  # Cash outflow
    'us-gaap:PaymentsToAcquireMarketableSecurities': 'credit',  # Cash outflow
    'us-gaap:ProceedsFromSaleOfPropertyPlantAndEquipment': 'debit',  # Cash inflow
    'us-gaap:ProceedsFromSaleOfAvailableForSaleSecuritiesDebt': 'debit',  # Cash inflow

    # Financing Activities
    'us-gaap:NetCashProvidedByUsedInFinancingActivities': 'debit',
    'us-gaap:ProceedsFromIssuanceOfCommonStock': 'debit',  # Cash inflow
    'us-gaap:ProceedsFromIssuanceOfLongTermDebt': 'debit',  # Cash inflow
    'us-gaap:RepaymentsOfLongTermDebt': 'credit',  # Cash outflow
    'us-gaap:PaymentsOfDividends': 'credit',  # Cash outflow
    'us-gaap:PaymentsOfDividendsCommonStock': 'credit',  # Cash outflow
    'us-gaap:PaymentsForRepurchaseOfCommonStock': 'credit',  # Cash outflow
}


def get_balance_type(concept: str) -> str:
    """
    Get the balance type for a concept.

    Looks up the balance type from the static US-GAAP mapping, handling
    both colon and underscore namespace separators.

    Args:
        concept: The concept name (e.g., 'us-gaap:Revenue' or 'us-gaap_Revenue' or 'us_gaap_Revenue')

    Returns:
        Balance type ('debit', 'credit', or None if not found)

    Example:
        >>> get_balance_type('us-gaap:Cash')
        'debit'
        >>> get_balance_type('us-gaap_Revenue')
        'credit'
        >>> get_balance_type('us_gaap_Revenue')
        'credit'
        >>> get_balance_type('UnknownConcept')
        None
    """
    # Try direct lookup first (standard form)
    if concept in US_GAAP_BALANCE_TYPES:
        return US_GAAP_BALANCE_TYPES[concept]

    # Normalize to standard form: us-gaap:LocalName
    # Handle common namespace prefix variations
    normalized = concept

    # Replace known namespace patterns
    # us_gaap_Cash -> us-gaap:Cash
    # us-gaap_Cash -> us-gaap:Cash
    if 'us_gaap' in normalized:
        normalized = normalized.replace('us_gaap_', 'us-gaap:')
        normalized = normalized.replace('us_gaap:', 'us-gaap:')
    elif 'us-gaap' in normalized:
        normalized = normalized.replace('us-gaap_', 'us-gaap:')

    # Try normalized form
    if normalized in US_GAAP_BALANCE_TYPES:
        return US_GAAP_BALANCE_TYPES[normalized]

    # Try converting all underscores to colons (simple fallback)
    concept_all_colons = concept.replace('_', ':')
    if concept_all_colons in US_GAAP_BALANCE_TYPES:
        return US_GAAP_BALANCE_TYPES[concept_all_colons]

    return None

"""
Shared XBRL concept definitions for sign normalization.

This module contains sets of XBRL concepts used across multiple parsers
to ensure consistent handling of sign normalization when applying calculation weights.
"""

# Concepts that should always be positive (expenses, costs)
# These concepts represent actual expenses/costs that companies incur.
# Even if they have negative calculation weights in the taxonomy, we force them positive
# because a negative value would mean a credit/benefit, not an expense.
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

# Concepts that can legitimately be negative (benefits, credits, reversals)
# These should NOT be forced positive even if they have negative calculation weights
# Note: Income tax concepts moved to consistent_positive_concepts for issue #451
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

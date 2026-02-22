"""
Loader for learned statement mappings and canonical structures.

This module handles loading and caching of learned mappings from the
structural learning process.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_learned_mappings() -> Dict[str, Dict[str, Any]]:
    """
    Load learned statement mappings from package data.

    Returns:
        Dictionary of concept -> mapping info
    """
    try:
        # Get the data file path
        data_dir = Path(__file__).parent / 'data'
        mappings_file = data_dir / 'statement_mappings_v1.json'

        if not mappings_file.exists():
            log.warning("Learned mappings file not found: %s", mappings_file)
            return {}

        with open(mappings_file, 'r') as f:
            data = json.load(f)

        mappings = data.get('mappings', {})
        metadata = data.get('metadata', {})

        log.info("Loaded %d learned concept mappings (version: %s)", len(mappings), metadata.get('version', 'unknown'))

        return mappings

    except Exception as e:
        log.error("Error loading learned mappings: %s", e)
        return {}


@lru_cache(maxsize=1)
def load_canonical_structures() -> Dict[str, Any]:
    """
    Load canonical statement structures.

    Returns:
        Dictionary of statement_type -> canonical structure
    """
    try:
        data_dir = Path(__file__).parent / 'data'
        structures_file = data_dir / 'learned_mappings.json'

        if not structures_file.exists():
            log.warning("Canonical structures file not found: %s", structures_file)
            return {}

        with open(structures_file, 'r') as f:
            structures = json.load(f)

        log.info("Loaded canonical structures for %d statement types", len(structures))
        return structures

    except Exception as e:
        log.error("Error loading canonical structures: %s", e)
        return {}


@lru_cache(maxsize=1)
def load_virtual_trees() -> Dict[str, Any]:
    """
    Load virtual presentation trees.

    Returns:
        Dictionary of statement_type -> virtual tree
    """
    try:
        data_dir = Path(__file__).parent / 'data'
        trees_file = data_dir / 'virtual_trees.json'

        if not trees_file.exists():
            log.warning("Virtual trees file not found: %s", trees_file)
            return {}

        with open(trees_file, 'r') as f:
            trees = json.load(f)

        log.info("Loaded virtual trees for %d statement types", len(trees))
        return trees

    except Exception as e:
        log.error("Error loading virtual trees: %s", e)
        return {}


def get_concept_mapping(concept: str) -> Optional[Dict[str, Any]]:
    """
    Get mapping information for a specific concept.

    Args:
        concept: Concept name (without namespace)

    Returns:
        Mapping info dict or None if not found
    """
    mappings = load_learned_mappings()
    return mappings.get(concept)


def get_statement_concepts(statement_type: str,
                         min_confidence: float = 0.5) -> Dict[str, Dict[str, Any]]:
    """
    Get all concepts for a specific statement type.

    Args:
        statement_type: Type of statement (BalanceSheet, IncomeStatement, etc.)
        min_confidence: Minimum confidence threshold

    Returns:
        Dictionary of concept -> mapping info
    """
    mappings = load_learned_mappings()

    result = {}
    for concept, info in mappings.items():
        if (info.get('statement_type') == statement_type and
            info.get('confidence', 0) >= min_confidence):
            result[concept] = info

    return result


# =============================================================================
# Industry-Specific Virtual Tree Extensions
# =============================================================================

@lru_cache(maxsize=1)
def load_industry_mappings() -> Dict[str, Any]:
    """
    Load SIC-to-industry mapping configuration.

    Returns:
        Dictionary with industry definitions and SIC ranges
    """
    try:
        data_dir = Path(__file__).parent / 'data'
        mappings_file = data_dir / 'industry_mappings.json'

        if not mappings_file.exists():
            log.debug("Industry mappings file not found: %s", mappings_file)
            return {}

        with open(mappings_file, 'r') as f:
            data = json.load(f)

        industries = data.get('industries', {})
        log.debug("Loaded industry mappings for %d industries", len(industries))
        return data

    except Exception as e:
        log.error("Error loading industry mappings: %s", e)
        return {}


def get_industry_for_sic(sic_code: str) -> Optional[str]:
    """
    Determine industry category from SIC code.

    Args:
        sic_code: SIC code as string (e.g., "6021")

    Returns:
        Industry name (e.g., "banking") or None if no match
    """
    if not sic_code:
        return None

    try:
        sic_int = int(sic_code)
    except (ValueError, TypeError):
        return None

    mappings = load_industry_mappings()
    industries = mappings.get('industries', {})

    for industry_key, industry_info in industries.items():
        for sic_range in industry_info.get('sic_ranges', []):
            if len(sic_range) == 2:
                start, end = sic_range
                if start <= sic_int <= end:
                    return industry_key

    return None


def get_industry_for_ticker(ticker: str) -> Optional[str]:
    """
    Determine industry category from ticker symbol.

    This is used for industries with curated ticker lists (like payment_networks)
    where SIC codes don't map cleanly to the industry.

    Args:
        ticker: Stock ticker symbol (e.g., "V", "MA", "PYPL")

    Returns:
        Industry name (e.g., "payment_networks") or None if no match
    """
    if not ticker:
        return None

    ticker_upper = ticker.upper()
    mappings = load_industry_mappings()
    industries = mappings.get('industries', {})

    for industry_key, industry_info in industries.items():
        curated_tickers = industry_info.get('curated_tickers')
        if isinstance(curated_tickers, list) and ticker_upper in curated_tickers:
            return industry_key

    return None


def get_industry(sic_code: Optional[str] = None, ticker: Optional[str] = None) -> Optional[str]:
    """
    Determine industry category from SIC code or ticker symbol.

    Tries ticker-based lookup first (for curated industries like payment_networks),
    then falls back to SIC-based lookup.

    Args:
        sic_code: SIC code as string (e.g., "6021")
        ticker: Stock ticker symbol (e.g., "V", "MA")

    Returns:
        Industry name or None if no match
    """
    # Try ticker-based lookup first (for curated industries)
    if ticker:
        industry = get_industry_for_ticker(ticker)
        if industry:
            return industry

    # Fall back to SIC-based lookup
    if sic_code:
        return get_industry_for_sic(sic_code)

    return None


@lru_cache(maxsize=10)
def load_industry_extension(industry: str) -> Dict[str, Any]:
    """
    Load industry-specific virtual tree extension.

    Args:
        industry: Industry key (e.g., "banking", "tech")

    Returns:
        Dictionary with statement type -> extension nodes
    """
    try:
        data_dir = Path(__file__).parent / 'data' / 'industry_extensions'

        # Get extension filename from mappings
        mappings = load_industry_mappings()
        industries = mappings.get('industries', {})

        if industry not in industries:
            log.debug("Unknown industry: %s", industry)
            return {}

        extension_file = industries[industry].get('extension_file')
        if not extension_file:
            return {}

        extension_path = data_dir / extension_file

        if not extension_path.exists():
            log.debug("Industry extension file not found: %s", extension_path)
            return {}

        with open(extension_path, 'r') as f:
            extension = json.load(f)

        log.debug("Loaded %s industry extension", industry)
        return extension

    except Exception as e:
        log.error("Error loading industry extension for %s: %s", industry, e)
        return {}


def get_available_industries() -> Dict[str, str]:
    """
    Get list of available industry categories.

    Returns:
        Dictionary of industry_key -> industry_name
    """
    mappings = load_industry_mappings()
    industries = mappings.get('industries', {})

    return {
        key: info.get('name', key)
        for key, info in industries.items()
    }


# =============================================================================
# Unified Concept-to-Statement Mapping
# =============================================================================

@lru_cache(maxsize=1)
def load_concept_linkages() -> Dict[str, Any]:
    """
    Load concept linkage data for multi-statement concept handling.

    Returns:
        Dictionary with multi_statement_concepts and category linkages
    """
    try:
        data_dir = Path(__file__).parent / 'data'
        linkages_file = data_dir / 'concept_linkages.json'

        if not linkages_file.exists():
            log.debug("Concept linkages file not found: %s", linkages_file)
            return {}

        with open(linkages_file, 'r') as f:
            linkages = json.load(f)

        log.debug(
            "Loaded concept linkages: %d multi-statement concepts",
            len(linkages.get('multi_statement_concepts', []))
        )
        return linkages

    except Exception as e:
        log.error("Error loading concept linkages: %s", e)
        return {}


# Common concept mappings not covered by learned data
# These are standard US-GAAP concepts with well-known statement assignments


_FALLBACK_CONCEPT_MAPPINGS = {
    # Income Statement
    'Revenue': 'IncomeStatement',
    'SalesRevenueNet': 'IncomeStatement',
    'SalesRevenueGoodsNet': 'IncomeStatement',
    'SalesRevenueServicesNet': 'IncomeStatement',
    'CostOfGoodsSold': 'IncomeStatement',
    'InterestIncome': 'IncomeStatement',
    # Balance Sheet - Assets
    'CurrentAssets': 'BalanceSheet',
    'AssetsNoncurrent': 'BalanceSheet',
    'ShortTermInvestments': 'BalanceSheet',
    'MarketableSecuritiesCurrent': 'BalanceSheet',
    'AccountsReceivableNet': 'BalanceSheet',
    'Inventory': 'BalanceSheet',
    # Balance Sheet - Liabilities
    'CurrentLiabilities': 'BalanceSheet',
    'LiabilitiesNoncurrent': 'BalanceSheet',
    'AccountsPayable': 'BalanceSheet',
    'AccruedLiabilitiesCurrent': 'BalanceSheet',
    'DeferredRevenueCurrent': 'BalanceSheet',
    'DeferredRevenueNoncurrent': 'BalanceSheet',
    'LongTermDebt': 'BalanceSheet',
    'LongTermDebtCurrent': 'BalanceSheet',
    'LongTermDebtNoncurrent': 'BalanceSheet',
    # Cash Flow
    'CashAndCashEquivalentsPeriodIncreaseDecrease': 'CashFlowStatement',
    'PaymentsToAcquireInvestments': 'CashFlowStatement',
    'ProceedsFromSaleOfInvestments': 'CashFlowStatement',
    'ProceedsFromIssuanceOfLongTermDebt': 'CashFlowStatement',
    'ProceedsFromMaturitiesPrepaymentsAndCallsOfAvailableForSaleSecurities': 'CashFlowStatement',
}


# =============================================================================
# IFRS Concept Mappings for Foreign Private Issuers
# =============================================================================
# These are standard IFRS concepts used by Foreign Private Issuers (FPIs)
# who file 20-F instead of 10-K (e.g., Novo Nordisk, ASML, Toyota, SAP)

_IFRS_FALLBACK_MAPPINGS = {
    # =========================================================================
    # Income Statement (Statement of Profit or Loss)
    # =========================================================================
    'Revenue': 'IncomeStatement',
    'CostOfSales': 'IncomeStatement',
    'GrossProfit': 'IncomeStatement',
    'AdministrativeExpense': 'IncomeStatement',
    'SellingGeneralAndAdministrativeExpense': 'IncomeStatement',
    'ResearchAndDevelopmentExpense': 'IncomeStatement',
    'OtherOperatingIncomeExpense': 'IncomeStatement',
    'OtherOperatingIncome': 'IncomeStatement',
    'OtherOperatingExpense': 'IncomeStatement',
    'ProfitLossFromOperatingActivities': 'IncomeStatement',
    'FinanceIncome': 'IncomeStatement',
    'FinanceCosts': 'IncomeStatement',
    'FinanceIncomeExpense': 'IncomeStatement',
    'InterestExpense': 'IncomeStatement',
    'InterestIncome': 'IncomeStatement',
    'ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod': 'IncomeStatement',
    'ProfitLossBeforeTax': 'IncomeStatement',
    'IncomeTaxExpenseContinuingOperations': 'IncomeStatement',
    'ProfitLoss': 'IncomeStatement',
    'ProfitLossAttributableToOwnersOfParent': 'IncomeStatement',
    'ProfitLossAttributableToNoncontrollingInterests': 'IncomeStatement',
    'BasicEarningsLossPerShare': 'IncomeStatement',
    'DilutedEarningsLossPerShare': 'IncomeStatement',
    'EmployeeBenefitsExpense': 'IncomeStatement',
    'DepreciationAndAmortisationExpense': 'IncomeStatement',
    'DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss': 'IncomeStatement',
    'ImpairmentLossRecognisedInProfitOrLossGoodwill': 'IncomeStatement',
    'ImpairmentLossRecognisedInProfitOrLossIntangibleAssetsOtherThanGoodwill': 'IncomeStatement',
    'NetForeignExchangeLoss': 'IncomeStatement',
    'NetForeignExchangeGain': 'IncomeStatement',
    'PostemploymentBenefitExpenseDefinedBenefitPlans': 'IncomeStatement',
    'PostemploymentBenefitExpenseDefinedContributionPlans': 'IncomeStatement',

    # =========================================================================
    # Balance Sheet (Statement of Financial Position)
    # =========================================================================
    # Assets
    'Assets': 'BalanceSheet',
    'CurrentAssets': 'BalanceSheet',
    'NoncurrentAssets': 'BalanceSheet',
    'CashAndCashEquivalents': 'BalanceSheet',
    'TradeAndOtherCurrentReceivables': 'BalanceSheet',
    'TradeAndOtherReceivables': 'BalanceSheet',
    'Inventories': 'BalanceSheet',
    'OtherCurrentFinancialAssets': 'BalanceSheet',
    'OtherCurrentAssets': 'BalanceSheet',
    'PropertyPlantAndEquipment': 'BalanceSheet',
    'IntangibleAssetsOtherThanGoodwill': 'BalanceSheet',
    'Goodwill': 'BalanceSheet',
    'InvestmentProperty': 'BalanceSheet',
    'InvestmentsAccountedForUsingEquityMethod': 'BalanceSheet',
    'DeferredTaxAssets': 'BalanceSheet',
    'OtherNoncurrentFinancialAssets': 'BalanceSheet',
    'OtherNoncurrentAssets': 'BalanceSheet',
    'RightofuseAssets': 'BalanceSheet',

    # Liabilities
    'Liabilities': 'BalanceSheet',
    'CurrentLiabilities': 'BalanceSheet',
    'NoncurrentLiabilities': 'BalanceSheet',
    'TradeAndOtherCurrentPayables': 'BalanceSheet',
    'TradeAndOtherPayables': 'BalanceSheet',
    'CurrentBorrowings': 'BalanceSheet',
    'NoncurrentBorrowings': 'BalanceSheet',
    'CurrentProvisions': 'BalanceSheet',
    'NoncurrentProvisions': 'BalanceSheet',
    'DeferredTaxLiabilities': 'BalanceSheet',
    'CurrentTaxLiabilitiesCurrent': 'BalanceSheet',
    'CurrentTaxAssetsCurrent': 'BalanceSheet',
    'LeaseLiabilities': 'BalanceSheet',
    'CurrentLeaseLiabilities': 'BalanceSheet',
    'NoncurrentLeaseLiabilities': 'BalanceSheet',
    'EmployeeBenefitsLiabilities': 'BalanceSheet',
    'OtherCurrentLiabilities': 'BalanceSheet',
    'OtherNoncurrentLiabilities': 'BalanceSheet',

    # Equity
    'Equity': 'BalanceSheet',
    'EquityAttributableToOwnersOfParent': 'BalanceSheet',
    'NoncontrollingInterests': 'BalanceSheet',
    'IssuedCapital': 'BalanceSheet',
    'SharePremium': 'BalanceSheet',
    'RetainedEarnings': 'BalanceSheet',
    'TreasuryShares': 'BalanceSheet',
    'OtherReserves': 'BalanceSheet',
    'ReserveOfExchangeDifferencesOnTranslation': 'BalanceSheet',
    'ReserveOfCashFlowHedges': 'BalanceSheet',

    # =========================================================================
    # Cash Flow Statement
    # =========================================================================
    # Operating Activities
    'CashFlowsFromUsedInOperatingActivities': 'CashFlowStatement',
    'AdjustmentsForDepreciationAndAmortisationExpenseAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss': 'CashFlowStatement',
    'AdjustmentsForIncomeTaxExpense': 'CashFlowStatement',
    'AdjustmentsForFinanceCosts': 'CashFlowStatement',
    'AdjustmentsForFinanceIncome': 'CashFlowStatement',
    'AdjustmentsForUndistributedProfitsOfAssociates': 'CashFlowStatement',
    'AdjustmentsForUnrealisedForeignExchangeLossesGains': 'CashFlowStatement',
    'AdjustmentsForGainLossOnDisposalOfInvestmentsInSubsidiariesJointVenturesAndAssociates': 'CashFlowStatement',
    'OtherAdjustmentsToReconcileProfitLoss': 'CashFlowStatement',
    'IncreaseDecreaseInTradeAndOtherReceivables': 'CashFlowStatement',
    'IncreaseDecreaseInInventories': 'CashFlowStatement',
    'IncreaseDecreaseInTradeAndOtherPayables': 'CashFlowStatement',
    'IncreaseDecreaseInOtherOperatingLiabilities': 'CashFlowStatement',
    'IncreaseDecreaseInOtherOperatingAssets': 'CashFlowStatement',
    'InterestPaidClassifiedAsOperatingActivities': 'CashFlowStatement',
    'InterestReceivedClassifiedAsOperatingActivities': 'CashFlowStatement',
    'IncomeTaxesPaidRefundClassifiedAsOperatingActivities': 'CashFlowStatement',

    # Investing Activities
    'CashFlowsFromUsedInInvestingActivities': 'CashFlowStatement',
    'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities': 'CashFlowStatement',
    'ProceedsFromSalesOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities': 'CashFlowStatement',
    'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities': 'CashFlowStatement',
    'CashFlowsUsedInObtainingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities': 'CashFlowStatement',
    'CashFlowsFromLosingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities': 'CashFlowStatement',
    'PurchaseOfInterestsInAssociates': 'CashFlowStatement',
    'DividendsReceivedFromAssociatesClassifiedAsInvestingActivities': 'CashFlowStatement',
    'ProceedsFromSalesOfInvestmentsOtherThanInvestmentsAccountedForUsingEquityMethod': 'CashFlowStatement',
    'PurchaseOfFinancialAssetsMeasuredAtFairValueThroughProfitOrLossClassifiedAsInvestingActivities': 'CashFlowStatement',
    'ProceedsFromDisposalOrMaturityOfAvailableforsaleFinancialAssets': 'CashFlowStatement',

    # Financing Activities
    'CashFlowsFromUsedInFinancingActivities': 'CashFlowStatement',
    'ProceedsFromBorrowingsClassifiedAsFinancingActivities': 'CashFlowStatement',
    'RepaymentsOfBorrowingsClassifiedAsFinancingActivities': 'CashFlowStatement',
    'PaymentsOfLeaseLiabilitiesClassifiedAsFinancingActivities': 'CashFlowStatement',
    'DividendsPaidClassifiedAsFinancingActivities': 'CashFlowStatement',
    'DividendsPaid': 'CashFlowStatement',
    'PaymentsToAcquireOrRedeemEntitysShares': 'CashFlowStatement',
    'ProceedsFromIssuingShares': 'CashFlowStatement',
    'InterestPaidClassifiedAsFinancingActivities': 'CashFlowStatement',

    # Net Change in Cash
    'IncreaseDecreaseInCashAndCashEquivalents': 'CashFlowStatement',
    'EffectOfExchangeRateChangesOnCashAndCashEquivalents': 'CashFlowStatement',
    'CashAndCashEquivalentsAtBeginningOfPeriod': 'CashFlowStatement',
    'CashAndCashEquivalentsAtEndOfPeriod': 'CashFlowStatement',

    # Additional Cash Flow Adjustments
    'AdjustmentsForCurrentTaxOfPriorPeriod': 'CashFlowStatement',
    'AdjustmentsForDeferredTaxOfPriorPeriods': 'CashFlowStatement',
    'AdjustmentsForDecreaseIncreaseInInventories': 'CashFlowStatement',
    'AdjustmentsForDecreaseIncreaseInTradeAccountReceivable': 'CashFlowStatement',
    'AdjustmentsForIncreaseDecreaseInOtherLiabilities': 'CashFlowStatement',
    'AdjustmentsForIncreaseDecreaseInTradeAccountPayable': 'CashFlowStatement',
    'AdjustmentsForProvisions': 'CashFlowStatement',
    'AdjustmentsForSharebasedPayments': 'CashFlowStatement',

    # =========================================================================
    # Comprehensive Income
    # =========================================================================
    'ComprehensiveIncome': 'ComprehensiveIncome',
    'OtherComprehensiveIncome': 'ComprehensiveIncome',
    'OtherComprehensiveIncomeNetOfTaxExchangeDifferencesOnTranslation': 'ComprehensiveIncome',
    'OtherComprehensiveIncomeNetOfTaxGainsLossesOnRemeasurementsOfDefinedBenefitPlans': 'ComprehensiveIncome',
    'OtherComprehensiveIncomeThatWillBeReclassifiedToProfitOrLossNetOfTax': 'ComprehensiveIncome',
    'OtherComprehensiveIncomeThatWillNotBeReclassifiedToProfitOrLossBeforeTax': 'ComprehensiveIncome',
    'GainsLossesOnCashFlowHedgesNetOfTax': 'ComprehensiveIncome',
    'GainsLossesOnCashFlowHedgesBeforeTax': 'ComprehensiveIncome',
    'ReclassificationAdjustmentsOnCashFlowHedgesNetOfTax': 'ComprehensiveIncome',

    # =========================================================================
    # Tax-Related Concepts (Income Statement)
    # =========================================================================
    'CurrentTaxExpenseIncome': 'IncomeStatement',
    'DeferredTaxExpenseIncome': 'IncomeStatement',
    'DeferredTaxExpenseIncomeRecognisedInProfitOrLoss': 'IncomeStatement',
    'ApplicableTaxRate': 'IncomeStatement',
    'AverageEffectiveTaxRate': 'IncomeStatement',
    'TaxRateEffectOfForeignTaxRates': 'IncomeStatement',

    # =========================================================================
    # Additional Income Statement Items
    # =========================================================================
    'DonationsAndSubsidiesExpense': 'IncomeStatement',
    'ProfessionalFeesExpense': 'IncomeStatement',
    'OtherEmployeeExpense': 'IncomeStatement',
    'OtherFinanceCost': 'IncomeStatement',
    'ExpenseFromSharebasedPaymentTransactionsWithEmployees': 'IncomeStatement',
    'ExpenseRelatingToLeasesOfLowvalueAssetsForWhichRecognitionExemptionHasBeenUsed': 'IncomeStatement',
    'ExpenseRelatingToShorttermLeasesForWhichRecognitionExemptionHasBeenUsed': 'IncomeStatement',
    'ExpenseRelatingToVariableLeasePaymentsNotIncludedInMeasurementOfLeaseLiabilities': 'IncomeStatement',
    'InterestExpenseOnLeaseLiabilities': 'IncomeStatement',
    'OperatingLeaseIncome': 'IncomeStatement',
    'DepreciationPropertyPlantAndEquipmentIncludingRightofuseAssets': 'IncomeStatement',
    'DepreciationRightofuseAssets': 'IncomeStatement',
    'ImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss': 'IncomeStatement',
    'ImpairmentLossRecognisedInProfitOrLossPropertyPlantAndEquipmentIncludingRightofuseAssets': 'IncomeStatement',
    'GainsLossesRecognisedWhenControlInSubsidiaryIsLost': 'IncomeStatement',
    'RevenueFromInterest': 'IncomeStatement',

    # =========================================================================
    # Additional Balance Sheet Items
    # =========================================================================
    'AllowanceAccountForCreditLossesOfFinancialAssets': 'BalanceSheet',
    'CurrentFinancialAssetsAtFairValueThroughProfitOrLoss': 'BalanceSheet',
    'CurrentValueAddedTaxPayables': 'BalanceSheet',
    'DeferredTaxLiabilityAsset': 'BalanceSheet',
    'NetDefinedBenefitLiabilityAsset': 'BalanceSheet',
    'OtherProvisions': 'BalanceSheet',
    'RentDeferredIncomeClassifiedAsCurrent': 'BalanceSheet',

    # =========================================================================
    # Metadata/Disclosure Items (often not mapped to specific statements)
    # =========================================================================
    'AverageNumberOfEmployees': 'IncomeStatement',
    'AuditorsRemuneration': 'IncomeStatement',
    'AuditorsRemunerationForAuditServices': 'IncomeStatement',
    'AuditorsRemunerationForOtherServices': 'IncomeStatement',
    'AuditorsRemunerationForTaxServices': 'IncomeStatement',
    'DividendsPaidOrdinarySharesPerShare': 'CashFlowStatement',
    'DividendsProposedOrDeclaredBeforeFinancialStatementsAuthorisedForIssueButNotRecognisedAsDistributionToOwners': 'CashFlowStatement',
    'DividendsRecognisedAsDistributionsToOwnersOfParentRelatingToCurrentYear': 'CashFlowStatement',
    'DividendsRecognisedAsDistributionsToOwnersOfParentRelatingToPriorYears': 'CashFlowStatement',

    # Share-based payment concepts
    'NumberOfOtherEquityInstrumentsOutstandingInSharebasedPaymentArrangement': 'BalanceSheet',
    'AdjustedWeightedAverageShares': 'IncomeStatement',

    # Additional Cash Flow Adjustments
    'IncreaseDecreaseInCashAndCashEquivalentsBeforeEffectOfExchangeRateChanges': 'CashFlowStatement',
    'IncreaseDecreaseInWorkingCapital': 'CashFlowStatement',
    'OtherAdjustmentsForNoncashItems': 'CashFlowStatement',
    'PurchaseOfTreasuryShares': 'CashFlowStatement',
    'IncreaseDecreaseThroughSharebasedPaymentTransactions': 'BalanceSheet',
    'DecreaseIncreaseThroughTaxOnSharebasedPaymentTransactions': 'BalanceSheet',
    'IncreaseDecreaseThroughBusinessCombinationsDeferredTaxLiabilityAsset': 'BalanceSheet',
    'IncreaseDecreaseThroughNetExchangeDifferencesDeferredTaxLiabilityAsset': 'BalanceSheet',

    # Additional Comprehensive Income
    'IncomeTaxRelatingToComponentsOfOtherComprehensiveIncome': 'ComprehensiveIncome',
    'CurrentTaxRelatingToItemsChargedOrCreditedDirectlyToEquity': 'ComprehensiveIncome',
    'DeferredTaxRelatingToItemsChargedOrCreditedDirectlyToEquity': 'ComprehensiveIncome',
    'CurrentAndDeferredTaxRelatingToItemsChargedOrCreditedDirectlyToEquity': 'ComprehensiveIncome',
    'GainsLossesOnChangeInValueOfForeignCurrencyBasisSpreadsNetOfTax': 'ComprehensiveIncome',
    'GainsLossesOnChangeInValueOfForwardElementsOfForwardContractsNetOfTax': 'ComprehensiveIncome',
    'GainsLossesRecognisedInOtherComprehensiveIncomeFairValueMeasurementAssets': 'ComprehensiveIncome',
    'GainsLossesOnAvailableforsaleFinancialAssets': 'ComprehensiveIncome',
    'ReclassificationAdjustmentsOnCashFlowHedgesBeforeTax': 'ComprehensiveIncome',
    'AmountRemovedFromReserveOfCashFlowHedgesAndIncludedInInitialCostOrOtherCarryingAmountOfNonfinancialAssetLiabilityOrFirmCommitmentForWhichFairValueHedgeAccountingIsApplied': 'ComprehensiveIncome',
    'ActuarialGainsLossesArisingFromChangesInFinancialAssumptionsNetDefinedBenefitLiabilityAsset': 'ComprehensiveIncome',

    # Disclosure/Metadata
    'KeyManagementPersonnelCompensation': 'IncomeStatement',
    'NumberOfEmployees': 'IncomeStatement',
    'SocialSecurityContributions': 'IncomeStatement',
    'UnusedTaxLossesForWhichNoDeferredTaxAssetRecognised': 'BalanceSheet',
    'IncreaseDecreaseInCurrentTaxExpenseIncomeDueToRateRegulation': 'IncomeStatement',
}


@lru_cache(maxsize=1)
def _build_concept_statement_index() -> Dict[str, Dict[str, Any]]:
    """
    Build a unified index of concept -> statement info from all sources.

    Combines (in priority order):
    1. multi_statement_concepts from concept_linkages.json
    2. learned_mappings.json
    3. Fallback mappings for common concepts

    Returns:
        Dictionary of concept -> {
            'primary_statement': str,
            'statements': List[str],
            'statement_details': Dict[str, Any]  # optional
        }
    """
    index = {}

    # 1. Load multi-statement concepts (highest priority - has full details)
    linkages = load_concept_linkages()
    for item in linkages.get('multi_statement_concepts', []):
        concept = item.get('concept')
        if concept:
            index[concept] = {
                'primary_statement': item.get('primary_statement'),
                'statements': item.get('statements', []),
                'statement_details': item.get('statement_details', {})
            }

    # 2. Load learned mappings (fill in gaps)
    learned = load_canonical_structures()  # This loads learned_mappings.json
    for concept, info in learned.items():
        if concept not in index:
            stmt_type = info.get('statement_type')
            if stmt_type:
                index[concept] = {
                    'primary_statement': stmt_type,
                    'statements': [stmt_type],
                    'statement_details': {
                        stmt_type: {
                            'occurrence_rate': info.get('occurrence_rate', info.get('confidence', 0)),
                            'label': info.get('label'),
                            'parent': info.get('parent'),
                            'is_abstract': info.get('is_abstract', False),
                            'is_total': info.get('is_total', False)
                        }
                    }
                }

    # 3. Add fallback mappings for common concepts not in JSON files
    for concept, stmt_type in _FALLBACK_CONCEPT_MAPPINGS.items():
        if concept not in index:
            index[concept] = {
                'primary_statement': stmt_type,
                'statements': [stmt_type],
                'statement_details': {}
            }

    # 4. Add IFRS fallback mappings for Foreign Private Issuers
    for concept, stmt_type in _IFRS_FALLBACK_MAPPINGS.items():
        if concept not in index:
            index[concept] = {
                'primary_statement': stmt_type,
                'statements': [stmt_type],
                'statement_details': {}
            }

    log.debug("Built concept-statement index with %d concepts", len(index))
    return index


def get_concept_statements(concept: str) -> Optional[Dict[str, Any]]:
    """
    Get statement information for a concept.

    Args:
        concept: Concept name (without namespace prefix)

    Returns:
        Dict with 'primary_statement', 'statements' list, and optional 'statement_details',
        or None if concept not found in mappings
    """
    # Remove namespace if present
    if ':' in concept:
        concept = concept.split(':')[-1]

    index = _build_concept_statement_index()
    return index.get(concept)


def get_primary_statement(concept: str) -> Optional[str]:
    """
    Get the primary statement type for a concept.

    Args:
        concept: Concept name (without namespace prefix)

    Returns:
        Statement type string (e.g., 'IncomeStatement', 'BalanceSheet'),
        or None if not found
    """
    info = get_concept_statements(concept)
    return info.get('primary_statement') if info else None


def get_all_statements_for_concept(concept: str) -> list:
    """
    Get all statement types a concept can appear in.

    Args:
        concept: Concept name (without namespace prefix)

    Returns:
        List of statement types, or empty list if not found
    """
    info = get_concept_statements(concept)
    return info.get('statements', []) if info else []


def get_concepts_for_statement(statement_type: str,
                               include_linked: bool = True) -> Dict[str, Dict[str, Any]]:
    """
    Get all concepts that belong to a statement type.

    Args:
        statement_type: Statement type (e.g., 'IncomeStatement')
        include_linked: If True, include concepts where this is a secondary statement

    Returns:
        Dictionary of concept -> statement info
    """
    index = _build_concept_statement_index()
    result = {}

    for concept, info in index.items():
        if info.get('primary_statement') == statement_type:
            result[concept] = info
        elif include_linked and statement_type in info.get('statements', []):
            result[concept] = info

    return result


def get_linkage_category(concept: str) -> Optional[str]:
    """
    Get the linkage category for a multi-statement concept.

    Args:
        concept: Concept name

    Returns:
        Category name (e.g., 'income_to_cashflow') or None
    """
    if ':' in concept:
        concept = concept.split(':')[-1]

    linkages = load_concept_linkages()
    categories = linkages.get('categories', {})

    for category, concepts in categories.items():
        if concept in concepts:
            return category

    return None

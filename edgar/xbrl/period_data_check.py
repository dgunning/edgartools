"""
Enhanced period selection with data availability checking.

This module provides functions to verify that selected periods have sufficient
data before displaying them to investors.
"""

from typing import Dict, List, Optional, Set, Tuple


def count_facts_for_period(xbrl_instance, period_key: str, statement_type: Optional[str] = None) -> int:
    """
    Count the number of facts available for a specific period.

    Args:
        xbrl_instance: XBRL instance with facts
        period_key: Period key to check (e.g., 'instant_2024-09-28')
        statement_type: Optional statement type to filter facts

    Returns:
        Number of facts found for this period
    """
    fact_count = 0

    # Parse period key to get context criteria
    if period_key.startswith('instant_'):
        period_type = 'instant'
        period_date = period_key.replace('instant_', '')
    elif 'duration_' in period_key:
        period_type = 'duration'
        parts = period_key.split('_')
        if len(parts) >= 3:
            start_date = parts[1]
            end_date = parts[2]
        else:
            return 0
    else:
        return 0

    # Count facts matching this period
    for _fact_key, fact in xbrl_instance._facts.items():
        # Get context for this fact
        context = xbrl_instance.contexts.get(fact.context_ref)
        if not context:
            continue

        # Check if period matches
        period_data = context.model_dump().get('period', {})
        if period_type == 'instant':
            if period_data.get('type') == 'instant' and period_data.get('instant') == period_date:
                fact_count += 1
        elif period_type == 'duration':
            if (period_data.get('type') == 'duration' and 
                period_data.get('startDate') == start_date and
                period_data.get('endDate') == end_date):
                fact_count += 1

    return fact_count


def get_essential_concepts_for_statement(statement_type: str) -> Set[str]:
    """
    Get the essential concepts that should be present for a statement type.

    These are the minimum concepts investors expect to see.
    """
    essential_concepts = {
        'BalanceSheet': {
            # Core balance sheet items
            'Assets', 'AssetsCurrent', 
            'Liabilities', 'LiabilitiesCurrent',
            'StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
            # Common important items
            'CashAndCashEquivalentsAtCarryingValue', 'Cash',
            'AccountsReceivableNetCurrent', 'AccountsReceivable',
            'Inventory', 'InventoryNet',
            'PropertyPlantAndEquipmentNet',
            'AccountsPayableCurrent', 'AccountsPayable',
            'LongTermDebt', 'LongTermDebtNoncurrent'
        },
        'IncomeStatement': {
            # Core income items
            'Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet',
            'CostOfRevenue', 'CostOfGoodsAndServicesSold', 'CostOfGoodsSold',
            'GrossProfit',
            'OperatingExpenses', 'OperatingCostsAndExpenses',
            'OperatingIncomeLoss', 'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'NetIncomeLoss', 'ProfitLoss',
            # Common important items
            'ResearchAndDevelopmentExpense',
            'SellingGeneralAndAdministrativeExpense',
            'EarningsPerShareBasic', 'EarningsPerShareDiluted'
        },
        'CashFlowStatement': {
            # Core cash flow items
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInInvestingActivities', 
            'NetCashProvidedByUsedInFinancingActivities',
            'CashAndCashEquivalentsPeriodIncreaseDecrease',
            # Common important items
            'NetIncomeLoss',
            'DepreciationDepletionAndAmortization', 'DepreciationAndAmortization',
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsOfDividends', 'PaymentsOfDividendsCommonStock'
        }
    }

    return essential_concepts.get(statement_type, set())


def check_period_data_quality(xbrl_instance, period_key: str, statement_type: str) -> Dict[str, any]:
    """
    Check the data quality for a specific period.

    Returns:
        Dictionary with quality metrics:
        - fact_count: Total number of facts
        - meaningful_fact_count: Number of facts with meaningful (non-empty) values
        - essential_coverage: Percentage of essential concepts found
        - has_sufficient_data: Boolean indicating if period should be displayed
        - missing_essentials: List of missing essential concepts
        - has_meaningful_data: Boolean indicating if period has meaningful values (fixes Issue #408)
    """
    # Count total facts
    fact_count = count_facts_for_period(xbrl_instance, period_key, statement_type)

    # Count meaningful facts (non-empty values) - Fix for Issue #408
    meaningful_fact_count = 0

    # Get essential concepts
    essential_concepts = get_essential_concepts_for_statement(statement_type)

    # Check which essential concepts are present
    found_essentials = set()
    missing_essentials = set()

    # Parse period for context matching
    if period_key.startswith('instant_'):
        period_type = 'instant'
        period_date = period_key.replace('instant_', '')
    else:
        period_type = 'duration'
        parts = period_key.split('_')
        if len(parts) >= 3:
            start_date = parts[1]
            end_date = parts[2]
        else:
            return {
                'fact_count': fact_count,
                'essential_coverage': 0.0,
                'has_sufficient_data': False,
                'missing_essentials': list(essential_concepts)
            }

    # Check each essential concept
    for concept in essential_concepts:
        concept_found = False

        # Look for this concept in facts
        for _fact_key, fact in xbrl_instance._facts.items():
            if concept_found:
                break

            # Check if this fact matches the concept
            element = xbrl_instance.element_catalog.get(fact.element_id)
            if element and concept in element.name:
                # Check if it's for our period
                context = xbrl_instance.contexts.get(fact.context_ref)
                if context:
                    period_data = context.model_dump().get('period', {})
                    if period_type == 'instant':
                        if period_data.get('type') == 'instant' and period_data.get('instant') == period_date:
                            found_essentials.add(concept)
                            concept_found = True
                    else:
                        if (period_data.get('type') == 'duration' and 
                            period_data.get('startDate') == start_date and
                            period_data.get('endDate') == end_date):
                            found_essentials.add(concept)
                            concept_found = True

        if not concept_found:
            missing_essentials.add(concept)

    # Count meaningful facts (non-empty values) - Fix for Issue #408
    for _fact_key, fact in xbrl_instance._facts.items():
        # Check if it's for our period
        context = xbrl_instance.contexts.get(fact.context_ref)
        if context:
            period_data = context.model_dump().get('period', {})
            period_matches = False

            if period_type == 'instant':
                if period_data.get('type') == 'instant' and period_data.get('instant') == period_date:
                    period_matches = True
            else:
                if (period_data.get('type') == 'duration' and
                    period_data.get('startDate') == start_date and
                    period_data.get('endDate') == end_date):
                    period_matches = True

            if period_matches:
                # Check if fact has meaningful value
                fact_value = getattr(fact, 'value', None)
                if fact_value is not None:
                    str_value = str(fact_value).strip()
                    if str_value and str_value.lower() not in ['', 'nan', 'none']:
                        try:
                            import pandas as pd
                            numeric_value = pd.to_numeric(str_value, errors='coerce')
                            if not pd.isna(numeric_value):
                                meaningful_fact_count += 1
                        except:
                            # If not numeric but not empty, might still be meaningful
                            if len(str_value) > 0:
                                meaningful_fact_count += 1

    # Calculate coverage
    essential_coverage = len(found_essentials) / len(essential_concepts) if essential_concepts else 0.0

    # Determine if sufficient data
    # Require at least 50% essential coverage or 20+ facts
    has_sufficient_data = essential_coverage >= 0.5 or fact_count >= 20

    # Determine if has meaningful data (fixes Issue #408)
    # A period has meaningful data if it has at least some facts with non-empty values
    has_meaningful_data = meaningful_fact_count > 0

    return {
        'fact_count': fact_count,
        'meaningful_fact_count': meaningful_fact_count,
        'essential_coverage': essential_coverage,
        'has_sufficient_data': has_sufficient_data,
        'has_meaningful_data': has_meaningful_data,
        'missing_essentials': list(missing_essentials),
        'found_essentials': list(found_essentials)
    }


def filter_periods_with_data(xbrl_instance, periods: List[Tuple[str, str]], 
                            statement_type: str, 
                            min_fact_count: int = 10) -> List[Tuple[str, str]]:
    """
    Filter periods to only include those with sufficient data.

    Args:
        xbrl_instance: XBRL instance
        periods: List of (period_key, label) tuples
        statement_type: Type of statement
        min_fact_count: Minimum number of facts required

    Returns:
        Filtered list of periods with sufficient data
    """
    filtered_periods = []

    for period_key, label in periods:
        quality = check_period_data_quality(xbrl_instance, period_key, statement_type)

        # Include period if it has sufficient data AND meaningful data (fixes Issue #408)
        if (quality['has_sufficient_data'] and
            quality['fact_count'] >= min_fact_count and
            quality['has_meaningful_data']):
            filtered_periods.append((period_key, label))
        else:
            # Log why period was excluded
            pass

    return filtered_periods


def determine_investor_preferred_periods(xbrl_instance, statement_type: str) -> List[Tuple[str, str]]:
    """
    Enhanced period selection that prioritizes what investors want to see.

    For Annual Reports:
    1. Current fiscal year
    2. Prior fiscal year (YoY comparison) 
    3. Two years ago (3-year trend)

    For Quarterly Reports:
    1. Current quarter
    2. Same quarter prior year (YoY)
    3. Current YTD
    4. Prior year YTD

    Only includes periods with sufficient data.
    """
    from edgar.xbrl.period_selector import select_periods

    # Start with the unified period selection
    base_periods = select_periods(xbrl_instance, statement_type)

    # Filter for data availability
    periods_with_data = filter_periods_with_data(
        xbrl_instance, 
        base_periods, 
        statement_type,
        min_fact_count=10
    )

    # If we lost too many periods, be less strict
    if len(periods_with_data) < 2 and len(base_periods) >= 2:
        # Try again with lower threshold
        periods_with_data = filter_periods_with_data(
            xbrl_instance,
            base_periods,
            statement_type,
            min_fact_count=5
        )

    return periods_with_data

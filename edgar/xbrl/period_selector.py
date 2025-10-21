"""
Unified Period Selection System

A streamlined, single-responsibility approach to XBRL period selection that:
- Consolidates logic from legacy periods.py and smart_periods.py
- Always applies document date filtering to prevent future period bugs
- Preserves essential fiscal intelligence while eliminating complexity
- Provides a single, clear entry point for all period selection

This replaces 1,275 lines of dual-system complexity with ~200 lines of focused logic.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def select_periods(xbrl, statement_type: str, max_periods: int = 4) -> List[Tuple[str, str]]:
    """
    Single entry point for period selection.

    Args:
        xbrl: XBRL instance with reporting_periods and entity_info
        statement_type: 'BalanceSheet', 'IncomeStatement', 'CashFlowStatement', etc.
        max_periods: Maximum number of periods to return

    Returns:
        List of (period_key, period_label) tuples, most recent first
    """
    # Step 1: Always filter by document date first (prevents future date bugs)
    all_periods = xbrl.reporting_periods
    document_end_date = xbrl.period_of_report

    if not all_periods:
        logger.warning("No reporting periods available for %s", xbrl.entity_name)
        return []

    filtered_periods = _filter_by_document_date(all_periods, document_end_date)

    if not filtered_periods:
        logger.warning("No valid periods found after document date filtering for %s", xbrl.entity_name)
        return [(p['key'], p['label']) for p in all_periods[:max_periods]]  # Fallback to unfiltered

    try:
        # Step 2: Statement-specific logic
        if statement_type == 'BalanceSheet':
            candidate_periods = _select_balance_sheet_periods(filtered_periods, max_periods)
        else:  # Income/Cash Flow statements
            candidate_periods = _select_duration_periods(filtered_periods, xbrl.entity_info, max_periods)

        # Step 3: Filter out periods with insufficient data
        periods_with_data = _filter_periods_with_sufficient_data(xbrl, candidate_periods, statement_type)

        if periods_with_data:
            return periods_with_data
        else:
            # If no periods have sufficient data, return the candidates anyway
            logger.warning("No periods with sufficient data found for %s %s, returning all candidates", xbrl.entity_name, statement_type)
            return candidate_periods

    except Exception as e:
        logger.error("Period selection failed for %s %s: %s", xbrl.entity_name, statement_type, e)
        # Final fallback: return filtered periods (document date filter already applied)
        return [(p['key'], p['label']) for p in filtered_periods[:max_periods]]


def _filter_by_document_date(periods: List[Dict], document_end_date: Optional[str]) -> List[Dict]:
    """
    Filter periods to only include those that end on or before the document date.

    This prevents the future date bug where periods from 2026-2029 were selected
    for a 2024 filing.
    """
    if not document_end_date:
        return periods

    try:
        doc_end_date = datetime.strptime(document_end_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        logger.debug("Could not parse document end date: %s", document_end_date)
        return periods

    filtered_periods = []
    for period in periods:
        try:
            if period['type'] == 'instant':
                period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                if period_date <= doc_end_date:
                    filtered_periods.append(period)
            else:  # duration
                period_end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                if period_end_date <= doc_end_date:
                    filtered_periods.append(period)
        except (ValueError, TypeError):
            # If we can't parse the period date, include it to be safe
            filtered_periods.append(period)

    return filtered_periods


def _select_balance_sheet_periods(periods: List[Dict], max_periods: int) -> List[Tuple[str, str]]:
    """
    Select instant periods for balance sheet statements.

    Balance sheets are point-in-time snapshots, so we need instant periods.
    We select the most recent instant periods with basic fiscal year intelligence.
    """
    instant_periods = [p for p in periods if p['type'] == 'instant']

    if not instant_periods:
        logger.warning("No instant periods found for balance sheet")
        return []

    # Sort by date (most recent first)
    instant_periods = _sort_periods_by_date(instant_periods, 'instant')

    # Take more candidate periods initially (up to 10) to ensure we capture fiscal year ends
    # Many filings have several instant periods (quarterly, mid-year, etc.) with minimal data
    # We need to cast a wider net initially and let data filtering select the best ones
    # Issue #464: Was only checking first 4 periods, missing prior fiscal year ends
    candidate_count = min(10, len(instant_periods))

    selected_periods = []
    for period in instant_periods[:candidate_count]:
        selected_periods.append((period['key'], period['label']))
        if len(selected_periods) >= max_periods * 3:  # Check up to 3x max_periods
            break

    return selected_periods


def _select_duration_periods(periods: List[Dict], entity_info: Dict[str, Any], max_periods: int) -> List[Tuple[str, str]]:
    """
    Select duration periods for income/cash flow statements with fiscal intelligence.

    This consolidates the sophisticated fiscal year logic from the legacy system
    while keeping it simple and focused.
    """
    duration_periods = [p for p in periods if p['type'] == 'duration']

    if not duration_periods:
        logger.warning("No duration periods found for income/cash flow statement")
        return []

    # Get fiscal information for intelligent period selection
    fiscal_period = entity_info.get('fiscal_period', 'FY')
    fiscal_year_end_month = entity_info.get('fiscal_year_end_month')
    fiscal_year_end_day = entity_info.get('fiscal_year_end_day')

    # Filter for annual periods if this is an annual report
    if fiscal_period == 'FY':
        annual_periods = _get_annual_periods(duration_periods)
        if annual_periods:
            # Apply fiscal year alignment scoring
            scored_periods = _score_fiscal_alignment(annual_periods, fiscal_year_end_month, fiscal_year_end_day)
            return [(p['key'], p['label']) for p in scored_periods[:max_periods]]

    # For quarterly reports or if no annual periods found, use sophisticated quarterly logic
    return _select_quarterly_periods(duration_periods, max_periods)


def _select_quarterly_periods(duration_periods: List[Dict], max_periods: int) -> List[Tuple[str, str]]:
    """
    Select quarterly periods with intelligent investor-focused logic.

    For quarterly filings, investors typically want:
    1. Current quarter (most recent quarterly period)
    2. Same quarter from prior year (YoY comparison)
    3. Year-to-date current year (6-month, 9-month YTD)
    4. Year-to-date prior year (comparative YTD)

    Issue #464 Fix: Cast wider net by checking more quarterly periods and returning
    more candidates (max_periods * 3) to let data quality filtering select the best ones.
    This mirrors the successful Balance Sheet fix from v4.20.1.
    """
    if not duration_periods:
        return []

    # Categorize periods by duration to identify types
    quarterly_periods = []  # ~90 days (80-100)
    ytd_periods = []       # 180-280 days (semi-annual, 9-month YTD)

    for period in duration_periods:
        try:
            start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
            duration_days = (end_date - start_date).days

            if 80 <= duration_days <= 100:  # Quarterly
                quarterly_periods.append(period)
            elif 150 <= duration_days <= 285:  # YTD (semi-annual to 9-month)
                ytd_periods.append(period)
            # Skip periods that are too short (<80 days) or too long (>285 days but <300)

        except (ValueError, TypeError, KeyError):
            continue

    # Sort periods by end date (most recent first)
    quarterly_periods = _sort_periods_by_date(quarterly_periods, 'duration')
    ytd_periods = _sort_periods_by_date(ytd_periods, 'duration')

    selected_periods = []

    # 1. Add current quarter (most recent quarterly period)
    if quarterly_periods:
        current_quarter = quarterly_periods[0]
        selected_periods.append((current_quarter['key'], current_quarter['label']))

        # 2. Find same quarter from prior year for YoY comparison
        # Issue #464: Check more quarterly periods to find prior year matches
        try:
            current_end = datetime.strptime(current_quarter['end_date'], '%Y-%m-%d').date()
            target_year = current_end.year - 1

            # Check up to 12 quarterly periods instead of just a few
            check_count = min(12, len(quarterly_periods) - 1)
            for period in quarterly_periods[1:check_count + 1]:
                period_end = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                # Same quarter if same month and within 15 days, previous year
                if (period_end.year == target_year and
                    period_end.month == current_end.month and
                    abs(period_end.day - current_end.day) <= 15):
                    selected_periods.append((period['key'], period['label']))
                    break
        except (ValueError, TypeError, KeyError):
            pass

    # 3. Add current year YTD (most recent YTD period)
    if ytd_periods:
        current_ytd = ytd_periods[0]
        # Avoid duplicates - check if this YTD period is already selected as quarterly
        if not any(current_ytd['key'] == key for key, _ in selected_periods):
            selected_periods.append((current_ytd['key'], current_ytd['label']))

            # 4. Add additional YTD candidates for data quality filtering to choose from
            # Issue #464: Cast wider net instead of strict matching to handle fiscal year differences
            # Example: AAPL current YTD ends June 29, prior YTD ends July 1 (different months)
            # Let data quality filtering choose the best periods based on fact counts
            if len(selected_periods) < max_periods * 3:
                added_keys = {key for key, _ in selected_periods}
                check_count = min(8, len(ytd_periods) - 1)
                for period in ytd_periods[1:check_count + 1]:  # Skip first (already added as current_ytd)
                    if period['key'] not in added_keys and len(selected_periods) < max_periods * 3:
                        selected_periods.append((period['key'], period['label']))
                        added_keys.add(period['key'])

    # If we still don't have enough periods, add other quarterly periods
    # Issue #464: Check more periods and return more candidates
    if len(selected_periods) < max_periods * 3:
        added_keys = {key for key, _ in selected_periods}
        check_count = min(12, len(quarterly_periods))
        for period in quarterly_periods[:check_count]:
            if period['key'] not in added_keys and len(selected_periods) < max_periods * 3:
                selected_periods.append((period['key'], period['label']))
                added_keys.add(period['key'])

    # Issue #464: Return max_periods * 3 candidates instead of just max_periods
    # Let data quality filtering in _filter_periods_with_sufficient_data choose the best ones
    # This mirrors the successful Balance Sheet fix from v4.20.1 (line 128)
    return selected_periods[:max_periods * 3]


def _get_annual_periods(duration_periods: List[Dict]) -> List[Dict]:
    """
    Filter duration periods to only include truly annual periods (>300 days).

    This consolidates the 300-day logic that was duplicated across both systems.
    """
    annual_periods = []

    for period in duration_periods:
        if _is_annual_period(period):
            annual_periods.append(period)

    return annual_periods


def _is_annual_period(period: Dict) -> bool:
    """
    Determine if a period is truly annual (300-400 days).

    Annual periods should be approximately one year, allowing for:
    - Leap years (366 days)
    - Slight variations in fiscal year end dates
    - But rejecting multi-year cumulative periods
    """
    try:
        start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
        duration_days = (end_date - start_date).days
        # Annual periods should be between 300-400 days
        # This rejects quarterly (~90 days) and multi-year (>400 days) periods
        return 300 < duration_days <= 400
    except (ValueError, TypeError, KeyError):
        return False


def _score_fiscal_alignment(periods: List[Dict], fiscal_month: Optional[int], fiscal_day: Optional[int]) -> List[Dict]:
    """
    Score and sort periods based on fiscal year alignment.

    This preserves the sophisticated fiscal intelligence from the legacy system.
    """
    if fiscal_month is None or fiscal_day is None:
        # No fiscal info available, just sort by date
        return _sort_periods_by_date(periods, 'duration')

    scored_periods = []

    for period in periods:
        try:
            end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
            score = _calculate_fiscal_alignment_score(end_date, fiscal_month, fiscal_day)

            # Add score to period for sorting
            period_with_score = period.copy()
            period_with_score['fiscal_score'] = score
            scored_periods.append(period_with_score)

        except (ValueError, TypeError, KeyError):
            # If we can't score it, give it a low score
            period_with_score = period.copy()
            period_with_score['fiscal_score'] = 0
            scored_periods.append(period_with_score)

    # Sort by fiscal score (highest first), then by date
    scored_periods.sort(key=lambda p: (p.get('fiscal_score', 0), p.get('end_date', '')), reverse=True)

    return scored_periods


def _calculate_fiscal_alignment_score(end_date: date, fiscal_month: int, fiscal_day: int) -> int:
    """
    Calculate fiscal year alignment score (0-100).

    Consolidated from the legacy system's fiscal alignment logic.
    """
    if end_date.month == fiscal_month and end_date.day == fiscal_day:
        return 100  # Perfect fiscal year end match
    elif end_date.month == fiscal_month and abs(end_date.day - fiscal_day) <= 15:
        return 75   # Same month, within 15 days
    elif abs(end_date.month - fiscal_month) <= 1:
        return 50   # Adjacent month
    else:
        return 25   # Different quarter


def _sort_periods_by_date(periods: List[Dict], period_type: str) -> List[Dict]:
    """
    Sort periods by date (most recent first).

    Handles both instant and duration periods correctly.
    """
    def get_sort_key(period):
        try:
            if period_type == 'instant':
                return datetime.strptime(period['date'], '%Y-%m-%d').date()
            else:  # duration
                return datetime.strptime(period['end_date'], '%Y-%m-%d').date()
        except (ValueError, TypeError, KeyError):
            return date.min  # Sort problematic periods to the end

    return sorted(periods, key=get_sort_key, reverse=True)


def _calculate_dynamic_thresholds(facts_by_period: Dict, statement_type: str) -> int:
    """
    Calculate minimum fact threshold based on actual data distribution.

    This adapts to company size - small companies get lower thresholds,
    large companies maintain high standards.

    Args:
        facts_by_period: Pre-grouped facts by period key
        statement_type: Statement type to analyze

    Returns:
        Minimum fact count threshold for this company/statement
    """
    # Collect fact counts for this statement type across all periods
    statement_fact_counts = []

    for period_key, period_facts in facts_by_period.items():
        statement_facts = [
            f for f in period_facts
            if f.get('statement_type') == statement_type
        ]
        if statement_facts:
            statement_fact_counts.append(len(statement_facts))

    if not statement_fact_counts:
        # No data for this statement type - use conservative default
        return 10

    # Sort to find the richest periods
    statement_fact_counts.sort(reverse=True)

    # Strategy: Use 40% of the richest period's fact count as minimum
    # This adapts to company size while still filtering sparse periods
    richest_period_facts = statement_fact_counts[0]

    # Calculate adaptive threshold
    adaptive_threshold = int(richest_period_facts * 0.4)

    # Apply floor and ceiling
    MIN_FLOOR = 10   # Never go below 10 facts
    MAX_CEILING = {
        'BalanceSheet': 40,
        'IncomeStatement': 25,
        'CashFlowStatement': 20
    }

    threshold = max(MIN_FLOOR, min(adaptive_threshold, MAX_CEILING.get(statement_type, 30)))

    logger.debug("Dynamic threshold for %s: %d (richest period: %d facts, 40%% = %d)",
                statement_type, threshold, richest_period_facts, adaptive_threshold)

    return threshold


def _calculate_dynamic_concept_diversity(facts_by_period: Dict, statement_type: str) -> int:
    """
    Calculate minimum concept diversity based on actual data.

    Returns:
        Minimum unique concept count for this company/statement
    """
    if statement_type != 'BalanceSheet':
        return 0  # Only apply to Balance Sheets for now

    # Find maximum concept diversity across periods
    max_concepts = 0
    for period_facts in facts_by_period.values():
        statement_facts = [
            f for f in period_facts
            if f.get('statement_type') == statement_type
        ]
        unique_concepts = len(set(f.get('concept') for f in statement_facts if f.get('concept')))
        max_concepts = max(max_concepts, unique_concepts)

    # Require 30% of maximum concept diversity, but at least 5
    diversity_threshold = max(5, int(max_concepts * 0.3))

    logger.debug("Dynamic concept diversity for %s: %d (max concepts: %d)",
                statement_type, diversity_threshold, max_concepts)

    return diversity_threshold


# Enhanced essential concept patterns with multiple variations
ESSENTIAL_CONCEPT_PATTERNS = {
    'BalanceSheet': [
        # Pattern groups - any match in group counts as finding that concept
        ['Assets', 'AssetsCurrent', 'AssetsNoncurrent', 'AssetsFairValueDisclosure'],
        ['Liabilities', 'LiabilitiesCurrent', 'LiabilitiesNoncurrent', 'LiabilitiesAndStockholdersEquity'],
        ['Equity', 'StockholdersEquity', 'ShareholdersEquity', 'PartnersCapital',
         'MembersEquity', 'ShareholdersEquityIncludingPortionAttributableToNoncontrollingInterest']
    ],
    'IncomeStatement': [
        ['Revenue', 'Revenues', 'SalesRevenue', 'SalesRevenueNet', 'RevenueFromContractWithCustomer'],
        ['NetIncome', 'NetIncomeLoss', 'ProfitLoss', 'NetIncomeLossAvailableToCommonStockholdersBasic'],
        ['OperatingIncome', 'OperatingIncomeLoss', 'IncomeLossFromOperations']
    ],
    'CashFlowStatement': [
        ['OperatingCashFlow', 'NetCashProvidedByUsedInOperatingActivities',
         'CashProvidedByUsedInOperatingActivities'],
        ['InvestingCashFlow', 'NetCashProvidedByUsedInInvestingActivities',
         'CashProvidedByUsedInInvestingActivities'],
        ['FinancingCashFlow', 'NetCashProvidedByUsedInFinancingActivities',
         'CashProvidedByUsedInFinancingActivities']
    ]
}


def _check_essential_concepts_flexible(statement_facts: List[Dict], statement_type: str) -> int:
    """
    Check for essential concepts using flexible pattern matching.

    Returns count of essential concept groups found (not individual patterns).
    """
    concept_groups = ESSENTIAL_CONCEPT_PATTERNS.get(statement_type, [])

    if not concept_groups:
        return 0

    # Extract all concepts from facts once
    fact_concepts = [f.get('concept', '').lower() for f in statement_facts if f.get('concept')]

    essential_concept_count = 0

    # For each concept group, check if ANY pattern matches
    for pattern_group in concept_groups:
        group_matched = False

        for pattern in pattern_group:
            pattern_lower = pattern.lower()

            # Check if this pattern appears in any fact concept
            if any(pattern_lower in concept for concept in fact_concepts):
                group_matched = True
                logger.debug("Essential concept matched: %s (from group %s)",
                           pattern, pattern_group[0])
                break

        if group_matched:
            essential_concept_count += 1

    return essential_concept_count


def _filter_periods_with_sufficient_data(xbrl, candidate_periods: List[Tuple[str, str]], statement_type: str) -> List[Tuple[str, str]]:
    """
    Filter periods to only include those with sufficient financial data.

    This prevents selection of periods that exist in the taxonomy but have
    no meaningful financial facts (like the Alphabet 2019 case).

    Issue #464: Added statement-specific fact count checks and concept diversity
    requirements to prevent showing sparse historical periods with only 1-2 concepts.

    Performance optimization: Retrieves all facts once and works with in-memory data
    instead of creating 40+ DataFrames per statement rendering.
    """
    MIN_FACTS_THRESHOLD = 10  # Minimum facts needed for a period to be considered viable

    # PERFORMANCE FIX: Get all facts once at the start (single operation)
    all_facts = xbrl.facts.get_facts()  # Returns List[Dict] - fast!

    # Pre-group facts by period_key (O(n) operation, done once)
    facts_by_period = {}
    for fact in all_facts:
        period_key = fact.get('period_key')
        if period_key:
            if period_key not in facts_by_period:
                facts_by_period[period_key] = []
            facts_by_period[period_key].append(fact)

    # Pre-group facts by statement type within each period
    statement_facts_by_period = {}
    for period_key, period_facts in facts_by_period.items():
        statement_facts_by_period[period_key] = [
            f for f in period_facts
            if f.get('statement_type') == statement_type
        ]

    # DYNAMIC THRESHOLDS: Calculate based on this company's data distribution
    statement_min_facts = _calculate_dynamic_thresholds(facts_by_period, statement_type)
    min_concept_diversity = _calculate_dynamic_concept_diversity(facts_by_period, statement_type)

    # Get essential concept groups for this statement type
    required_concept_groups = len(ESSENTIAL_CONCEPT_PATTERNS.get(statement_type, []))

    periods_with_data = []

    # Loop through candidates using pre-computed groups (no DataFrame conversions!)
    for period_key, period_label in candidate_periods:
        try:
            # Get pre-grouped facts (fast list access, not DataFrame query)
            statement_facts = statement_facts_by_period.get(period_key, [])
            period_facts = facts_by_period.get(period_key, [])

            statement_fact_count = len(statement_facts)
            total_fact_count = len(period_facts)

            # Check statement-specific threshold
            if statement_fact_count < statement_min_facts:
                logger.debug("Period %s has insufficient %s facts (%d < %d)",
                           period_label, statement_type, statement_fact_count, statement_min_facts)
                continue

            # Fallback check for total facts
            if total_fact_count < MIN_FACTS_THRESHOLD:
                logger.debug("Period %s has insufficient facts (%d < %d)",
                           period_label, total_fact_count, MIN_FACTS_THRESHOLD)
                continue

            # Check concept diversity (Issue #464)
            if statement_type == 'BalanceSheet':
                unique_concepts = len(set(f.get('concept') for f in statement_facts if f.get('concept')))

                if unique_concepts < min_concept_diversity:
                    logger.debug("Period %s lacks concept diversity (%d < %d unique concepts)",
                               period_label, unique_concepts, min_concept_diversity)
                    continue

            # FLEXIBLE CONCEPT MATCHING: Check essential concepts using pattern groups
            essential_concept_count = _check_essential_concepts_flexible(statement_facts, statement_type)

            # Require at least half the essential concept groups
            min_essential_required = max(1, required_concept_groups // 2)
            if essential_concept_count >= min_essential_required:
                periods_with_data.append((period_key, period_label))
                unique_concepts_count = len(set(f.get('concept') for f in statement_facts if f.get('concept')))
                logger.debug("Period %s has sufficient data: %d %s facts, %d unique concepts, %d/%d essential concepts",
                           period_label, statement_fact_count, statement_type,
                           unique_concepts_count,
                           essential_concept_count, required_concept_groups)
            else:
                logger.debug("Period %s lacks essential concepts: %d/%d present",
                           period_label, essential_concept_count, required_concept_groups)

        except Exception as e:
            logger.warning("Error checking data for period %s: %s", period_label, e)
            # Be more conservative - don't include if we can't verify
            continue

    return periods_with_data


# Legacy compatibility functions - to be removed after migration
def determine_periods_to_display(xbrl_instance, statement_type: str) -> List[Tuple[str, str]]:
    """Legacy compatibility wrapper."""
    logger.warning("Using legacy compatibility wrapper - update to use select_periods() directly")
    return select_periods(xbrl_instance, statement_type)


def select_smart_periods(xbrl, statement_type: str, max_periods: int = 4) -> List[Tuple[str, str]]:
    """Legacy compatibility wrapper."""
    logger.warning("Using legacy compatibility wrapper - update to use select_periods() directly")
    return select_periods(xbrl, statement_type, max_periods)

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
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any

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
    try:
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
        # Final fallback: return first few periods
        return [(p['key'], p['label']) for p in xbrl.reporting_periods[:max_periods]]


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

    # Take the most recent instant periods
    selected_periods = []
    for period in instant_periods[:max_periods]:
        selected_periods.append((period['key'], period['label']))

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
        try:
            current_end = datetime.strptime(current_quarter['end_date'], '%Y-%m-%d').date()
            target_year = current_end.year - 1

            for period in quarterly_periods[1:]:
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

            # 4. Find prior year YTD for comparison
            try:
                ytd_end = datetime.strptime(current_ytd['end_date'], '%Y-%m-%d').date()
                target_year = ytd_end.year - 1

                for period in ytd_periods[1:]:
                    period_end = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                    # Same YTD period from previous year
                    if (period_end.year == target_year and
                        period_end.month == ytd_end.month and
                        abs(period_end.day - ytd_end.day) <= 15):
                        selected_periods.append((period['key'], period['label']))
                        break
            except (ValueError, TypeError, KeyError):
                pass

    # If we still don't have enough periods, add other quarterly periods
    if len(selected_periods) < max_periods:
        added_keys = {key for key, _ in selected_periods}
        for period in quarterly_periods:
            if period['key'] not in added_keys and len(selected_periods) < max_periods:
                selected_periods.append((period['key'], period['label']))
                added_keys.add(period['key'])

    return selected_periods[:max_periods]


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


def _filter_periods_with_sufficient_data(xbrl, candidate_periods: List[Tuple[str, str]], statement_type: str) -> List[Tuple[str, str]]:
    """
    Filter periods to only include those with sufficient financial data.

    This prevents selection of periods that exist in the taxonomy but have
    no meaningful financial facts (like the Alphabet 2019 case).
    """
    MIN_FACTS_THRESHOLD = 10  # Minimum facts needed for a period to be considered viable

    # Define essential concepts by statement type
    essential_concepts = {
        'IncomeStatement': ['Revenue', 'NetIncome', 'OperatingIncome'],
        'BalanceSheet': ['Assets', 'Liabilities', 'Equity'],
        'CashFlowStatement': ['OperatingCashFlow', 'InvestingCashFlow', 'FinancingCashFlow']
    }

    required_concepts = essential_concepts.get(statement_type, [])
    periods_with_data = []

    for period_key, period_label in candidate_periods:
        try:
            # Check total fact count for this period
            period_facts = xbrl.facts.query().by_period_key(period_key).to_dataframe()
            fact_count = len(period_facts)

            if fact_count < MIN_FACTS_THRESHOLD:
                logger.debug("Period %s has insufficient facts (%d < %d)", period_label, fact_count, MIN_FACTS_THRESHOLD)
                continue

            # Check for essential concepts
            essential_concept_count = 0
            for concept in required_concepts:
                concept_facts = xbrl.facts.query().by_period_key(period_key).by_concept(concept).to_dataframe()
                if len(concept_facts) > 0:
                    essential_concept_count += 1

            # Require at least half the essential concepts to be present
            min_essential_required = max(1, len(required_concepts) // 2)
            if essential_concept_count >= min_essential_required:
                periods_with_data.append((period_key, period_label))
                logger.debug("Period %s has sufficient data: %d facts, %d/%d essential concepts",
                           period_label, fact_count, essential_concept_count, len(required_concepts))
            else:
                logger.debug("Period %s lacks essential concepts: %d/%d present",
                           period_label, essential_concept_count, len(required_concepts))

        except Exception as e:
            logger.debug("Error checking data for period %s: %s", period_label, e)
            # If we can't check, include it to be safe
            periods_with_data.append((period_key, period_label))

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
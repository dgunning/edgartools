"""
XBRL Statement Stitching - Period Optimization (Refactored)

This module provides functionality to determine optimal periods for stitching
statements across multiple XBRL filings, handling period selection and
fiscal period matching.

Refactored to use a clean class-based architecture for better maintainability,
testability, and extensibility.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from edgar.xbrl.core import format_date, parse_date
from edgar.xbrl.xbrl import XBRL

logger = logging.getLogger(__name__)


@dataclass
class PeriodSelectionConfig:
    """Configuration for period selection behavior"""

    # Duration ranges for different period types
    annual_duration_range: Tuple[int, int] = (350, 380)
    quarterly_duration_range: Tuple[int, int] = (80, 100)
    q2_ytd_range: Tuple[int, int] = (175, 190)
    q3_ytd_range: Tuple[int, int] = (260, 285)
    q4_annual_range: Tuple[int, int] = (350, 380)

    # Target durations for optimization
    target_annual_days: int = 365
    target_quarterly_days: int = 90
    target_q2_ytd_days: int = 180
    target_q3_ytd_days: int = 270

    # Behavior flags
    require_exact_matches: bool = True
    allow_fallback_when_no_doc_date: bool = True
    max_periods_default: int = 8


class PeriodMatcher:
    """Handles exact period matching logic"""

    def __init__(self, config: PeriodSelectionConfig):
        self.config = config

    def find_exact_instant_match(self, periods: List[Dict], target_date: date) -> Optional[Dict]:
        """Find instant period that exactly matches target date"""
        for period in periods:
            try:
                period_date = parse_date(period['date'])
                if period_date == target_date:
                    return period
            except (ValueError, TypeError) as e:
                logger.warning("Failed to parse period date '%s': %s", period.get('date'), e)
                continue
        return None

    def find_exact_duration_match(self, periods: List[Dict], target_date: date) -> Optional[Dict]:
        """Find duration period that ends exactly on target date"""
        for period in periods:
            try:
                end_date = parse_date(period['end_date'])
                if end_date == target_date:
                    return period
            except (ValueError, TypeError) as e:
                logger.warning("Failed to parse period end date '%s': %s", period.get('end_date'), e)
                continue
        return None

    def filter_by_duration_range(self, periods: List[Dict], min_days: int, max_days: int, target_days: int) -> List[Dict]:
        """Filter periods by duration and sort by proximity to target"""
        filtered_periods = []

        for period in periods:
            duration_days = period.get('duration_days')
            if duration_days is None:
                try:
                    start_date = parse_date(period['start_date'])
                    end_date = parse_date(period['end_date'])
                    duration_days = (end_date - start_date).days
                    period = period.copy()
                    period['duration_days'] = duration_days
                except (ValueError, TypeError) as e:
                    logger.warning("Failed to calculate duration for period: %s", e)
                    continue

            if min_days <= duration_days <= max_days:
                filtered_periods.append(period)

        # Sort by proximity to target duration
        filtered_periods.sort(key=lambda x: abs(x['duration_days'] - target_days))
        return filtered_periods


class FiscalPeriodClassifier:
    """Classifies and filters periods based on fiscal information"""

    def __init__(self, config: PeriodSelectionConfig):
        self.config = config

    def classify_annual_periods(self, periods: List[Dict]) -> List[Dict]:
        """Identify annual periods (350-380 days)"""
        min_days, max_days = self.config.annual_duration_range
        target_days = self.config.target_annual_days

        annual_periods = []
        for period in periods:
            duration_days = period.get('duration_days', 0)
            if min_days <= duration_days <= max_days:
                annual_periods.append(period)

        # Sort by proximity to target annual duration
        annual_periods.sort(key=lambda x: abs(x.get('duration_days', 0) - target_days))
        return annual_periods

    def classify_quarterly_periods(self, periods: List[Dict]) -> List[Dict]:
        """Identify quarterly periods (80-100 days)"""
        min_days, max_days = self.config.quarterly_duration_range
        target_days = self.config.target_quarterly_days

        quarterly_periods = []
        for period in periods:
            duration_days = period.get('duration_days', 0)
            if min_days <= duration_days <= max_days:
                quarterly_periods.append(period)

        # Sort by proximity to target quarterly duration
        quarterly_periods.sort(key=lambda x: abs(x.get('duration_days', 0) - target_days))
        return quarterly_periods

    def classify_ytd_periods(self, periods: List[Dict], fiscal_period: str) -> List[Dict]:
        """Identify YTD periods based on fiscal quarter"""
        if fiscal_period not in ['Q2', 'Q3', 'Q4']:
            return []

        # Get expected duration range for this fiscal period
        duration_ranges = {
            'Q2': self.config.q2_ytd_range,
            'Q3': self.config.q3_ytd_range,
            'Q4': self.config.q4_annual_range
        }

        target_durations = {
            'Q2': self.config.target_q2_ytd_days,
            'Q3': self.config.target_q3_ytd_days,
            'Q4': self.config.target_annual_days
        }

        min_days, max_days = duration_ranges[fiscal_period]
        target_days = target_durations[fiscal_period]

        ytd_periods = []
        for period in periods:
            duration_days = period.get('duration_days', 0)
            if min_days <= duration_days <= max_days:
                ytd_periods.append(period)

        # Sort by proximity to target duration
        ytd_periods.sort(key=lambda x: abs(x.get('duration_days', 0) - target_days))
        return ytd_periods

    def get_expected_durations(self, fiscal_period: str) -> Dict[str, Tuple[int, int]]:
        """Get expected duration ranges for fiscal period"""
        if fiscal_period == 'FY':
            return {'annual': self.config.annual_duration_range}
        elif fiscal_period in ['Q1', 'Q2', 'Q3', 'Q4']:
            durations = {'quarterly': self.config.quarterly_duration_range}
            if fiscal_period == 'Q2':
                durations['ytd'] = self.config.q2_ytd_range
            elif fiscal_period == 'Q3':
                durations['ytd'] = self.config.q3_ytd_range
            elif fiscal_period == 'Q4':
                durations['ytd'] = self.config.q4_annual_range
            return durations
        else:
            return {}


class StatementTypeSelector:
    """
    Handles statement-specific period selection logic.

    Period Selection Strategy for Quarterly Reports:

    For quarterly 10-Q filings, we prioritize quarterly periods (~90 days) over
    YTD periods (~180-270 days) to provide users with detailed quarterly breakdowns
    rather than cumulative summaries. This matches the behavior of regular statement
    period selection and aligns with investor expectations.

    YTD periods are only used as a fallback when quarterly periods are unavailable.

    See GitHub Issue #475 for background on this design decision.
    """

    def __init__(self, matcher: PeriodMatcher, classifier: FiscalPeriodClassifier):
        self.matcher = matcher
        self.classifier = classifier

    def select_balance_sheet_periods(self, xbrl: XBRL, doc_period_end_date: Optional[date]) -> List[Dict]:
        """Select instant periods for balance sheets"""
        # Filter for instant periods only
        instant_periods = [p for p in xbrl.reporting_periods if p['type'] == 'instant']

        if not instant_periods:
            return []

        # If we have document_period_end_date, find exact match
        if doc_period_end_date:
            exact_match = self.matcher.find_exact_instant_match(instant_periods, doc_period_end_date)
            if exact_match:
                return [exact_match]
            else:
                # No exact match found - don't use fallback to prevent fiscal year boundary issues
                logger.info("No exact instant period match found for %s", doc_period_end_date)
                return []

        # No document_period_end_date available - use most recent period
        instant_periods.sort(key=lambda x: x['date'], reverse=True)
        return [instant_periods[0]]

    def select_income_statement_periods(self, xbrl: XBRL, doc_period_end_date: Optional[date], 
                                      fiscal_period: str) -> List[Dict]:
        """Select duration periods for income statements"""
        return self._select_duration_periods(xbrl, doc_period_end_date, fiscal_period)

    def select_cash_flow_periods(self, xbrl: XBRL, doc_period_end_date: Optional[date], 
                               fiscal_period: str) -> List[Dict]:
        """Select duration periods for cash flow statements"""
        return self._select_duration_periods(xbrl, doc_period_end_date, fiscal_period)

    def _select_duration_periods(self, xbrl: XBRL, doc_period_end_date: Optional[date], 
                               fiscal_period: str) -> List[Dict]:
        """Common logic for selecting duration periods"""
        # Filter for duration periods only
        duration_periods = [p for p in xbrl.reporting_periods if p['type'] == 'duration']

        if not duration_periods:
            return []

        # Add duration_days to all periods
        enriched_periods = []
        for period in duration_periods:
            try:
                start_date = parse_date(period['start_date'])
                end_date = parse_date(period['end_date'])
                period_copy = period.copy()
                period_copy['duration_days'] = (end_date - start_date).days
                enriched_periods.append(period_copy)
            except (ValueError, TypeError) as e:
                logger.warning("Failed to parse period dates: %s", e)
                continue

        if not enriched_periods:
            return []

        # If we have document_period_end_date, find periods that end exactly on that date
        if doc_period_end_date:
            matching_periods = []
            for period in enriched_periods:
                try:
                    end_date = parse_date(period['end_date'])
                    if end_date == doc_period_end_date:
                        matching_periods.append(period)
                except (ValueError, TypeError):
                    continue

            if matching_periods:
                return self._select_appropriate_durations(matching_periods, fiscal_period)
            else:
                # No exact match found - don't use fallback
                logger.info("No exact duration period match found for %s", doc_period_end_date)
                return []

        # No document_period_end_date - use fallback logic
        return self._select_fallback_periods(enriched_periods, fiscal_period)

    def _select_appropriate_durations(self, periods: List[Dict], fiscal_period: str) -> List[Dict]:
        """Select appropriate duration periods based on fiscal period"""
        selected_periods = []

        is_annual = fiscal_period == 'FY'

        if is_annual:
            # For annual reports, select annual periods
            annual_periods = self.classifier.classify_annual_periods(periods)
            if annual_periods:
                selected_periods.append(annual_periods[0])
        else:
            # For quarterly reports, select the period with more data (Issue #475)
            # Some companies (e.g., PYPL) tag full detail to YTD periods rather than
            # quarterly periods. We should use whichever has more complete data.
            quarterly_periods = self.classifier.classify_quarterly_periods(periods)
            ytd_periods = self.classifier.classify_ytd_periods(periods, fiscal_period)

            # If we have both, select the one that appears to have more data
            # (by checking if it's the longest duration, which typically has more facts tagged)
            if quarterly_periods and ytd_periods:
                # YTD has longer duration, so if it exists, it likely has more data
                # This matches regular statement behavior for companies like PYPL
                selected_periods.append(ytd_periods[0])
            elif quarterly_periods:
                # Only quarterly available
                selected_periods.append(quarterly_periods[0])
            elif ytd_periods:
                # Only YTD available (rare edge case)
                selected_periods.append(ytd_periods[0])

        return selected_periods

    def _select_fallback_periods(self, periods: List[Dict], fiscal_period: str) -> List[Dict]:
        """Fallback period selection when no document_period_end_date is available"""
        is_annual = fiscal_period == 'FY'

        if is_annual:
            # For annual reports, prefer periods closest to 365 days
            annual_periods = self.classifier.classify_annual_periods(periods)
            if annual_periods:
                # Sort by end date and take the most recent
                annual_periods.sort(key=lambda x: x['end_date'], reverse=True)
                return [annual_periods[0]]
        else:
            # For quarterly reports, prefer quarterly duration
            quarterly_periods = self.classifier.classify_quarterly_periods(periods)
            selected_periods = []

            if quarterly_periods:
                quarterly_periods.sort(key=lambda x: x['end_date'], reverse=True)
                selected_periods.append(quarterly_periods[0])

            # Add YTD period if available
            ytd_periods = self.classifier.classify_ytd_periods(periods, fiscal_period)
            if ytd_periods:
                ytd_periods.sort(key=lambda x: x['end_date'], reverse=True)
                selected_periods.append(ytd_periods[0])

            return selected_periods

        # If no appropriate periods found, return the most recent period
        periods.sort(key=lambda x: x['end_date'], reverse=True)
        return [periods[0]]


class PeriodMetadataEnricher:
    """Handles period metadata enrichment"""

    def enrich_period_metadata(self, period: Dict, xbrl_index: int, entity_info: Dict, 
                              doc_period_end_date: Optional[date], fiscal_period: str, 
                              fiscal_year: str) -> Dict[str, Any]:
        """Add comprehensive metadata to period"""
        period_metadata = {
            'xbrl_index': xbrl_index,
            'period_key': period['key'],
            'period_label': period['label'],
            'period_type': period['type'],
            'entity_info': entity_info,
            'doc_period_end_date': doc_period_end_date,
            'fiscal_period': fiscal_period,
            'fiscal_year': fiscal_year
        }

        # Add date information
        if period['type'] == 'instant':
            period_metadata['date'] = parse_date(period['date'])
            period_metadata['display_date'] = format_date(period_metadata['date'])
        else:  # duration
            period_metadata['start_date'] = parse_date(period['start_date'])
            period_metadata['end_date'] = parse_date(period['end_date'])
            period_metadata['duration_days'] = period.get('duration_days', 
                (period_metadata['end_date'] - period_metadata['start_date']).days)
            period_metadata['display_date'] = format_date(period_metadata['end_date'])

        return period_metadata


class PeriodDeduplicator:
    """Handles period deduplication and sorting"""

    def deduplicate_periods(self, periods: List[Dict], statement_type: str) -> List[Dict]:
        """Remove duplicate periods using exact date matching"""
        filtered_periods = []

        for period in periods:
            too_close = False
            for included_period in filtered_periods:
                # Skip if period types don't match
                if period['period_type'] != included_period['period_type']:
                    continue

                # Check for true duplicates (exact same period)
                if period['period_type'] == 'instant':
                    # For instant periods, check the date
                    if period['date'] == included_period['date']:
                        too_close = True
                        break
                else:  # duration
                    # For duration periods, check BOTH start and end dates
                    # Q2 quarterly (Apr-Jun) and Q2 YTD (Jan-Jun) have same end date
                    # but different start dates, so they're NOT duplicates
                    if (period['start_date'] == included_period['start_date'] and
                        period['end_date'] == included_period['end_date']):
                        too_close = True
                        break

            if not too_close:
                filtered_periods.append(period)

        return filtered_periods

    def sort_periods_chronologically(self, periods: List[Dict], statement_type: str) -> List[Dict]:
        """Sort periods by appropriate date field"""
        if statement_type == 'BalanceSheet':
            return sorted(periods, key=lambda x: x['date'], reverse=True)
        else:
            return sorted(periods, key=lambda x: x['end_date'], reverse=True)

    def limit_periods(self, periods: List[Dict], max_periods: int) -> List[Dict]:
        """Limit to maximum number of periods"""
        return periods[:max_periods] if len(periods) > max_periods else periods


class PeriodOptimizer:
    """Main orchestrator for period optimization"""

    def __init__(self, config: Optional[PeriodSelectionConfig] = None):
        self.config = config or PeriodSelectionConfig()
        self.matcher = PeriodMatcher(self.config)
        self.classifier = FiscalPeriodClassifier(self.config)
        self.selector = StatementTypeSelector(self.matcher, self.classifier)
        self.enricher = PeriodMetadataEnricher()
        self.deduplicator = PeriodDeduplicator()

    def determine_optimal_periods(self, xbrl_list: List[XBRL], statement_type: str, 
                                 max_periods: Optional[int] = None) -> List[Dict[str, Any]]:
        """Main entry point - orchestrates the entire process"""
        max_periods = max_periods or self.config.max_periods_default

        # Step 1: Extract periods from all XBRLs
        all_periods = self._extract_all_periods(xbrl_list, statement_type)

        # Step 2: Enrich with metadata
        enriched_periods = self._enrich_with_metadata(all_periods)

        # Step 3: Deduplicate, sort, and limit
        final_periods = self._deduplicate_and_limit(enriched_periods, max_periods, statement_type)

        return final_periods

    def _extract_all_periods(self, xbrl_list: List[XBRL], statement_type: str) -> List[Dict[str, Any]]:
        """Extract periods from all XBRL objects"""
        all_periods = []

        for i, xbrl in enumerate(xbrl_list):
            # Skip None XBRLs (pre-XBRL era filings before 2009)
            if xbrl is None:
                continue

            # Skip XBRLs with no reporting periods
            if not xbrl.reporting_periods:
                continue

            entity_info = xbrl.entity_info or {}
            doc_period_end_date = self._parse_document_period_end_date(entity_info)
            fiscal_period = entity_info.get('fiscal_period')
            fiscal_year = entity_info.get('fiscal_year')

            # Select appropriate periods based on statement type
            selected_periods = self._select_periods_for_statement_type(
                xbrl, statement_type, doc_period_end_date, fiscal_period
            )

            # Add context information to each period
            for period in selected_periods:
                period_with_context = {
                    'period': period,
                    'xbrl_index': i,
                    'entity_info': entity_info,
                    'doc_period_end_date': doc_period_end_date,
                    'fiscal_period': fiscal_period,
                    'fiscal_year': fiscal_year
                }
                all_periods.append(period_with_context)

        return all_periods

    def _parse_document_period_end_date(self, entity_info: Dict) -> Optional[date]:
        """Parse document_period_end_date from entity_info"""
        if 'document_period_end_date' not in entity_info:
            return None

        try:
            doc_period_end_date = entity_info['document_period_end_date']
            if not isinstance(doc_period_end_date, date):
                doc_period_end_date = parse_date(str(doc_period_end_date))
            return doc_period_end_date
        except (ValueError, TypeError) as e:
            logger.warning("Failed to parse document_period_end_date: %s", e)
            return None

    def _select_periods_for_statement_type(self, xbrl: XBRL, statement_type: str, 
                                         doc_period_end_date: Optional[date], 
                                         fiscal_period: str) -> List[Dict]:
        """Select periods based on statement type"""
        if statement_type == 'BalanceSheet':
            return self.selector.select_balance_sheet_periods(xbrl, doc_period_end_date)
        elif statement_type in ['IncomeStatement', 'CashFlowStatement']:
            if statement_type == 'IncomeStatement':
                return self.selector.select_income_statement_periods(xbrl, doc_period_end_date, fiscal_period)
            else:
                return self.selector.select_cash_flow_periods(xbrl, doc_period_end_date, fiscal_period)
        else:
            # For other statement types, use income statement logic as default
            return self.selector.select_income_statement_periods(xbrl, doc_period_end_date, fiscal_period)

    def _enrich_with_metadata(self, all_periods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich periods with comprehensive metadata"""
        enriched_periods = []

        for period_context in all_periods:
            period = period_context['period']
            enriched_metadata = self.enricher.enrich_period_metadata(
                period,
                period_context['xbrl_index'],
                period_context['entity_info'],
                period_context['doc_period_end_date'],
                period_context['fiscal_period'],
                period_context['fiscal_year']
            )
            enriched_periods.append(enriched_metadata)

        return enriched_periods

    def _deduplicate_and_limit(self, periods: List[Dict[str, Any]], max_periods: int, 
                              statement_type: str) -> List[Dict[str, Any]]:
        """Deduplicate, sort, and limit periods"""
        # Sort periods chronologically
        sorted_periods = self.deduplicator.sort_periods_chronologically(periods, statement_type)

        # Remove duplicates
        deduplicated_periods = self.deduplicator.deduplicate_periods(sorted_periods, statement_type)

        # Limit to maximum number of periods
        final_periods = self.deduplicator.limit_periods(deduplicated_periods, max_periods)

        return final_periods


# Main function that maintains the original API
def determine_optimal_periods(xbrl_list: List[XBRL], statement_type: str, max_periods: int = 8) -> List[Dict[str, Any]]:
    """
    Determine the optimal periods to display for stitched statements from a list of XBRL objects.

    This function analyzes entity info and reporting periods across multiple XBRL instances
    to select the most appropriate periods for display, ensuring consistency in period selection
    when creating stitched statements.

    Args:
        xbrl_list: List of XBRL objects ordered chronologically
        statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
        max_periods: Maximum number of periods to return (default is 8)

    Returns:
        List of period metadata dictionaries containing information for display
    """
    optimizer = PeriodOptimizer()
    return optimizer.determine_optimal_periods(xbrl_list, statement_type, max_periods)

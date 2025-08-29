"""
Smart Period Selection: Investor Needs ∩ Company Data Availability

This module implements efficient period selection that balances what investors
want to see with what data is actually available in the filing.
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Set
import pandas as pd

logger = logging.getLogger(__name__)


class InvestorPeriodRanker:
    """Ranks periods by investor decision value, independent of data availability."""
    
    def rank_periods(self, available_periods: List[Dict], fiscal_period: str, statement_type: str = None) -> List[Tuple[str, int]]:
        """Return periods ranked by investor priority (period_key, priority_score)."""
        
        # Balance Sheet needs instant periods (point-in-time), not duration periods
        if statement_type == 'BalanceSheet':
            return self._rank_balance_sheet_periods(available_periods)
        elif fiscal_period == 'FY':
            return self._rank_annual_periods(available_periods)
        else:
            return self._rank_quarterly_periods(available_periods, fiscal_period)
    
    def _rank_annual_periods(self, periods: List[Dict]) -> List[Tuple[str, int]]:
        """Rank annual reporting periods by investor priority."""
        ranked = []
        
        # Find true annual periods (duration > 300 days)
        annual_periods = []
        for period in periods:
            if self._is_annual_period(period):
                annual_periods.append(period)
        
        # Sort by end date (most recent first)
        annual_periods.sort(key=lambda x: self._get_period_end_date(x), reverse=True)
        
        # Assign priority scores: Current FY=100, Prior FY=90, 2 years ago=80
        for i, period in enumerate(annual_periods[:3]):
            priority = 100 - (i * 10)
            ranked.append((period['key'], priority))
        
        return ranked
    
    def _rank_quarterly_periods(self, periods: List[Dict], fiscal_period: str) -> List[Tuple[str, int]]:
        """Rank quarterly reporting periods by investor priority."""
        ranked = []
        
        # Find different period types
        current_q = self._find_current_quarter(periods)
        same_q_last_year = self._find_yoy_quarter(periods, current_q) if current_q else None
        current_ytd = self._find_current_ytd(periods)
        prev_quarter = self._find_previous_quarter(periods, current_q) if current_q else None
        
        # Assign priorities based on investment decision value
        # Use dict to avoid duplicates - highest priority wins
        priority_map = {}
        
        if current_q:
            priority_map[current_q['key']] = (100, "Current Quarter")
        
        if same_q_last_year and same_q_last_year['key'] not in priority_map:
            priority_map[same_q_last_year['key']] = (95, "Same Quarter Last Year")
        
        if current_ytd and current_ytd['key'] not in priority_map:
            priority_map[current_ytd['key']] = (85, "Year-to-Date")
        
        if prev_quarter and prev_quarter['key'] not in priority_map:
            # Check if this is already the YoY quarter (avoid duplicate)
            if same_q_last_year and prev_quarter['key'] == same_q_last_year['key']:
                # It's already added as YoY with higher priority, skip
                pass
            else:
                priority_map[prev_quarter['key']] = (75, "Previous Quarter")
        
        # Add any other quarterly periods with lower priority
        other_periods = self._find_other_relevant_periods(periods, set(priority_map.keys()))
        for period_key in other_periods:
            if period_key not in priority_map:
                priority_map[period_key] = (60, "Other Period")
        
        # Convert to list sorted by priority
        result = [(pk, priority) for pk, (priority, desc) in priority_map.items()]
        result.sort(key=lambda x: x[1], reverse=True)  # Sort by priority descending
        
        return result
    
    def _is_annual_period(self, period: Dict) -> bool:
        """Check if period represents annual data (>300 days)."""
        if period['type'] != 'duration':
            return False
        
        try:
            start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
            duration = (end_date - start_date).days
            return duration > 300
        except (ValueError, KeyError, TypeError):
            return False
    
    def _get_period_end_date(self, period: Dict) -> date:
        """Get period end date for sorting."""
        try:
            if period['type'] == 'instant':
                return datetime.strptime(period['date'], '%Y-%m-%d').date()
            else:
                return datetime.strptime(period['end_date'], '%Y-%m-%d').date()
        except (ValueError, KeyError, TypeError):
            return date.min
    
    def _find_current_quarter(self, periods: List[Dict]) -> Optional[Dict]:
        """Find the most recent quarterly period (~90 days)."""
        quarterly_periods = []
        
        for period in periods:
            if period['type'] == 'duration' and self._is_quarterly_duration(period):
                quarterly_periods.append(period)
        
        if not quarterly_periods:
            return None
        
        # Return most recent
        quarterly_periods.sort(key=lambda x: self._get_period_end_date(x), reverse=True)
        return quarterly_periods[0]
    
    def _is_quarterly_duration(self, period: Dict) -> bool:
        """Check if period is quarterly duration (80-100 days)."""
        try:
            start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
            duration = (end_date - start_date).days
            return 80 <= duration <= 100
        except (ValueError, KeyError, TypeError):
            return False
    
    def _find_yoy_quarter(self, periods: List[Dict], current_q: Optional[Dict]) -> Optional[Dict]:
        """Find same quarter from previous year."""
        if not current_q:
            return None
        
        try:
            current_end = datetime.strptime(current_q['end_date'], '%Y-%m-%d').date()
            target_year = current_end.year - 1
            
            for period in periods:
                if period['type'] == 'duration' and self._is_quarterly_duration(period):
                    period_end = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                    
                    # Same quarter if same month and within 15 days, previous year
                    if (period_end.year == target_year and 
                        period_end.month == current_end.month and
                        abs(period_end.day - current_end.day) <= 15):
                        return period
        except (ValueError, KeyError, TypeError):
            pass
        
        return None
    
    def _find_current_ytd(self, periods: List[Dict]) -> Optional[Dict]:
        """Find current year-to-date period (180-280 days)."""
        ytd_periods = []
        
        for period in periods:
            if period['type'] == 'duration':
                try:
                    start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                    end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                    duration = (end_date - start_date).days
                    
                    # YTD periods are typically 6-9 months
                    if 170 <= duration <= 285:
                        ytd_periods.append(period)
                except (ValueError, KeyError, TypeError):
                    continue
        
        if not ytd_periods:
            return None
        
        # Return most recent YTD period
        ytd_periods.sort(key=lambda x: self._get_period_end_date(x), reverse=True)
        return ytd_periods[0]
    
    def _find_previous_quarter(self, periods: List[Dict], current_q: Optional[Dict]) -> Optional[Dict]:
        """Find the quarter immediately before current quarter."""
        if not current_q:
            return None
        
        quarterly_periods = [p for p in periods if p['type'] == 'duration' and self._is_quarterly_duration(p)]
        quarterly_periods.sort(key=lambda x: self._get_period_end_date(x), reverse=True)
        
        # Find current quarter in list and return the next one
        for i, period in enumerate(quarterly_periods):
            if period['key'] == current_q['key'] and i + 1 < len(quarterly_periods):
                return quarterly_periods[i + 1]
        
        return None
    
    def _find_other_relevant_periods(self, periods: List[Dict], exclude_keys: Set[str]) -> List[str]:
        """Find other periods that might be relevant but lower priority."""
        other_keys = []
        
        for period in periods:
            if period['key'] not in exclude_keys and period['type'] == 'duration':
                # Include if it's a reasonable duration period
                try:
                    start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                    end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                    duration = (end_date - start_date).days
                    
                    # Include periods between 30 days and 1 year
                    if 30 <= duration <= 400:
                        other_keys.append(period['key'])
                except (ValueError, KeyError, TypeError):
                    continue
        
        return other_keys
    
    def _rank_balance_sheet_periods(self, periods: List[Dict]) -> List[Tuple[str, int]]:
        """Rank Balance Sheet periods - focuses on instant periods (snapshots)."""
        ranked = []
        
        # Balance Sheets use instant periods (point-in-time asset/liability positions)
        instant_periods = [p for p in periods if p['type'] == 'instant']
        
        # Sort by date (most recent first)
        instant_periods.sort(key=lambda x: self._get_period_end_date(x), reverse=True)
        
        # Prioritize key comparison dates
        priority_map = []
        
        # Most recent period (highest priority)
        if len(instant_periods) > 0:
            priority_map.append((instant_periods[0]['key'], 100, "Current Period"))
        
        # Find fiscal/calendar year end dates (high priority for comparison)
        for i, period in enumerate(instant_periods[1:], 1):
            period_date = self._get_period_end_date(period)
            
            # Prioritize fiscal year ends (typically Sept 30, Dec 31, etc.)
            if period_date.month in [9, 12]:  # Common fiscal year ends
                priority_map.append((period['key'], 90 - (i * 5), f"Fiscal Year End"))
            # Quarter ends are also valuable
            elif period_date.month in [3, 6]:  # Quarter ends
                priority_map.append((period['key'], 80 - (i * 5), f"Quarter End"))
            else:
                # Other dates get lower priority
                priority_map.append((period['key'], 70 - (i * 5), f"Other Date"))
        
        # Return top periods sorted by priority
        priority_map.sort(key=lambda x: x[1], reverse=True)
        return [(pk, priority) for pk, priority, desc in priority_map[:4]]  # Max 4 periods


class DataAvailabilityScorer:
    """Efficiently scores periods based on data richness."""
    
    def __init__(self, xbrl):
        self.xbrl = xbrl
        self._fact_cache = {}
        
        # Pre-compute essential concepts for efficiency
        self.essential_concepts = {
            'IncomeStatement': ['revenue', 'netincome', 'operatingincome'],
            'BalanceSheet': ['assets', 'liabilities', 'equity', 'stockholdersequity'],
            'CashFlowStatement': ['operatingcashflow', 'netcash', 'cashflow']
        }
    
    def score_period_data(self, period_key: str, statement_type: str) -> float:
        """Score 0.0-1.0 based on data availability and quality."""
        
        cache_key = (period_key, statement_type)
        if cache_key in self._fact_cache:
            return self._fact_cache[cache_key]
        
        try:
            # Get facts for this period and statement type
            period_facts = self.xbrl.facts.query().by_period_key(period_key).by_statement_type(statement_type).to_dataframe()
            fact_count = len(period_facts)
            
            # Apply different scoring based on statement type
            if statement_type == 'BalanceSheet':
                # Balance Sheet needs many facts for complete picture (Assets, Liabilities, Equity)
                if fact_count == 0:
                    score = 0.0
                elif fact_count < 20:  # Much stricter for Balance Sheet
                    score = 0.1  # Too sparse for meaningful comparison
                elif fact_count < 40:
                    score = 0.5  # Moderate coverage
                elif fact_count < 60:
                    score = 0.8  # Good coverage
                else:
                    score = 1.0  # Rich data
            elif statement_type == 'CashFlowStatement':
                # Cash Flow Statement - stricter than Income Statement due to YTD-only reporting patterns
                if fact_count == 0:
                    score = 0.0
                elif fact_count < 5:
                    score = 0.1  # Too sparse - many companies only report YTD
                elif fact_count < 10:
                    score = 0.3  # Minimal but usable
                elif fact_count < 20:
                    score = 0.6  # Good coverage
                elif fact_count < 35:
                    score = 0.8  # Very good coverage
                else:
                    score = 1.0  # Rich data
            else:
                # Income Statement and other statements
                if fact_count == 0:
                    score = 0.0
                elif fact_count < 5:
                    score = 0.2  # Very sparse
                elif fact_count < 15:
                    score = 0.5  # Moderate
                elif fact_count < 30:
                    score = 0.8  # Good coverage
                else:
                    score = 1.0  # Rich data
            
            # Bonus for essential concepts
            if fact_count > 0:
                essential_bonus = self._check_essential_concepts(period_facts, statement_type)
                score = min(score + essential_bonus, 1.0)
            
        except Exception as e:
            logger.debug(f"Error scoring period {period_key}: {e}")
            score = 0.1  # Small fallback score if query fails
        
        self._fact_cache[cache_key] = score
        return score
    
    def _check_essential_concepts(self, period_facts: pd.DataFrame, statement_type: str) -> float:
        """Quick essential concept check - returns 0.0-0.3 bonus."""
        if len(period_facts) == 0:
            return 0.0
        
        essential_list = self.essential_concepts.get(statement_type, [])
        if not essential_list:
            return 0.1
        
        # Check concept names (case-insensitive)
        available_concepts = set(period_facts['concept'].str.lower()) if 'concept' in period_facts.columns else set()
        
        concepts_found = 0
        for essential in essential_list:
            if any(essential in concept for concept in available_concepts):
                concepts_found += 1
        
        coverage_ratio = concepts_found / len(essential_list)
        return coverage_ratio * 0.3  # Max 0.3 bonus


class SmartPeriodSelector:
    """Efficiently selects optimal intersection of investor needs and data availability."""
    
    def __init__(self, xbrl):
        self.xbrl = xbrl
        self.ranker = InvestorPeriodRanker()
        self.scorer = DataAvailabilityScorer(xbrl)
    
    def select_optimal_periods(self, statement_type: str, max_periods: int = 4) -> List[Tuple[str, str]]:
        """Select periods balancing investor needs and data availability."""
        
        try:
            # Step 1: Get investor-ranked periods
            fiscal_period = self.xbrl.entity_info.get('fiscal_period', 'FY')
            ranked_periods = self.ranker.rank_periods(self.xbrl.reporting_periods, fiscal_period, statement_type)
            
            if not ranked_periods:
                return self._fallback_selection(statement_type, max_periods)
            
            # Step 2: Score top candidates for data availability
            candidates_to_check = min(len(ranked_periods), max_periods * 2)
            scored_periods = []
            
            for period_key, investor_priority in ranked_periods[:candidates_to_check]:
                data_score = self.scorer.score_period_data(period_key, statement_type)
                
                # Combined scoring: adjust weights based on statement type
                if data_score == 0.0:
                    combined_score = 0  # No data = unusable
                else:
                    # Adjust weights based on statement type
                    if statement_type == 'CashFlowStatement':
                        # Give more weight to data availability for Cash Flow (YTD-only pattern common)
                        investor_weight = 0.60
                        data_weight = 0.40
                    else:
                        # Use default weights for other statements
                        investor_weight = 0.75
                        data_weight = 0.25
                    
                    # Scale data score to match investor priority range
                    scaled_data_score = data_score * 40  # 0-40 range
                    combined_score = (investor_priority * investor_weight) + (scaled_data_score * data_weight)
                
                period_label = self._get_period_label(period_key)
                scored_periods.append((period_key, period_label, combined_score, data_score))
            
            # Step 3: Select top periods with minimum data quality
            scored_periods.sort(key=lambda x: x[2], reverse=True)
            
            selected_periods = []
            for period_key, period_label, combined_score, data_score in scored_periods:
                # Apply different minimum thresholds based on statement type
                if statement_type == 'BalanceSheet':
                    min_threshold = 0.4  # Much stricter for Balance Sheet (needs complete data)
                elif statement_type == 'CashFlowStatement':
                    min_threshold = 0.3  # Stricter for Cash Flow to filter out quarterly periods with 1-2 facts
                else:
                    min_threshold = 0.1  # More lenient for Income Statement
                
                if data_score < min_threshold:
                    continue
                
                selected_periods.append((period_key, period_label))
                
                if len(selected_periods) >= max_periods:
                    break
            
            # Step 4: Ensure we have at least 2 periods if possible
            if len(selected_periods) < 2 and len(scored_periods) >= 2:
                # Add the best remaining period even if data is sparse
                for period_key, period_label, combined_score, data_score in scored_periods:
                    if (period_key, period_label) not in selected_periods and data_score > 0:
                        selected_periods.append((period_key, period_label))
                        if len(selected_periods) >= 2:
                            break
            
            # Step 5: Final sparsity filter - remove periods with very few facts
            if selected_periods:
                filtered_periods = self._apply_sparsity_filter(selected_periods, statement_type)
                if filtered_periods:
                    return filtered_periods
                else:
                    # If all periods were filtered out, return the best ones anyway
                    return selected_periods
            
        except Exception as e:
            logger.warning(f"Smart period selection failed: {e}")
        
        # Fallback to existing logic
        return self._fallback_selection(statement_type, max_periods)
    
    def _fallback_selection(self, statement_type: str, max_periods: int) -> List[Tuple[str, str]]:
        """Simple fallback selection using basic period logic."""
        try:
            # Simple fallback: return most recent periods up to max_periods
            periods = []
            reporting_periods = self.xbrl.reporting_periods
            
            # Filter by statement type
            if statement_type == 'BalanceSheet':
                # Balance Sheet uses instant periods
                instant_periods = [p for p in reporting_periods if 'instant' in p['key']]
                periods = instant_periods[:max_periods]
            else:
                # Income/Cash Flow use duration periods
                duration_periods = [p for p in reporting_periods if 'duration' in p['key']]
                periods = duration_periods[:max_periods]
            
            return [(p['key'], p['label']) for p in periods]
        except Exception as e:
            logger.error(f"Fallback period selection failed: {e}")
            # Last resort: return any available periods
            return [(p['key'], p['label']) for p in self.xbrl.reporting_periods[:max_periods]]
    
    def _get_period_label(self, period_key: str) -> str:
        """Get display label for period key."""
        for period in self.xbrl.reporting_periods:
            if period['key'] == period_key:
                return period['label']
        return period_key
    
    def _apply_sparsity_filter(self, selected_periods: List[Tuple[str, str]], statement_type: str) -> List[Tuple[str, str]]:
        """Remove periods with very few facts as final quality check."""
        if len(selected_periods) <= 2:
            # Don't filter if we only have 2 or fewer periods
            return selected_periods
        
        # Set minimum fact thresholds by statement type
        if statement_type == 'CashFlowStatement':
            min_facts = 5  # Cash flow needs at least 5 facts to be meaningful
        elif statement_type == 'BalanceSheet':
            min_facts = 15  # Balance sheet needs many facts
        else:
            min_facts = 3  # Income statement can be useful with fewer facts
        
        filtered_periods = []
        for period_key, period_label in selected_periods:
            try:
                facts = self.xbrl.facts.query().by_period_key(period_key).by_statement_type(statement_type).to_dataframe()
                fact_count = len(facts)
                
                if fact_count >= min_facts:
                    filtered_periods.append((period_key, period_label))
                else:
                    logger.debug(f"Filtering out sparse period {period_label} with only {fact_count} facts")
                    
            except Exception as e:
                logger.debug(f"Error checking facts for period {period_key}: {e}")
                # Keep the period if we can't check it
                filtered_periods.append((period_key, period_label))
        
        # Ensure we keep at least 2 periods for comparison
        if len(filtered_periods) < 2 and len(selected_periods) >= 2:
            return selected_periods[:2]  # Return the top 2 regardless of sparsity
        
        return filtered_periods
    
    def get_selection_explanation(self, statement_type: str, max_periods: int = 4) -> Dict[str, any]:
        """Get detailed explanation of period selection for debugging/transparency."""
        
        fiscal_period = self.xbrl.entity_info.get('fiscal_period', 'FY')
        ranked_periods = self.ranker.rank_periods(self.xbrl.reporting_periods, fiscal_period, statement_type)
        
        explanation = {
            'fiscal_period': fiscal_period,
            'total_periods_available': len(self.xbrl.reporting_periods),
            'investor_ranked_periods': [],
            'selected_periods': [],
            'excluded_periods': []
        }
        
        # Score all ranked periods for explanation
        for period_key, investor_priority in ranked_periods[:max_periods * 2]:
            data_score = self.scorer.score_period_data(period_key, statement_type)
            period_label = self._get_period_label(period_key)
            
            period_info = {
                'period_key': period_key,
                'label': period_label,
                'investor_priority': investor_priority,
                'data_score': round(data_score, 2),
                'combined_score': round((investor_priority * 0.75) + (data_score * 40 * 0.25), 1) if data_score > 0 else 0
            }
            
            explanation['investor_ranked_periods'].append(period_info)
            
            if data_score >= 0.1 and len(explanation['selected_periods']) < max_periods:
                explanation['selected_periods'].append(period_info)
            else:
                period_info['exclusion_reason'] = 'Insufficient data' if data_score < 0.1 else 'Max periods reached'
                explanation['excluded_periods'].append(period_info)
        
        return explanation


# Convenience function for easy integration
def select_smart_periods(xbrl, statement_type: str, max_periods: int = 4) -> List[Tuple[str, str]]:
    """Easy-to-use function for smart period selection."""
    selector = SmartPeriodSelector(xbrl)
    return selector.select_optimal_periods(statement_type, max_periods)
"""TTM (Trailing Twelve Months) calculation module.

Provides core logic for aggregating 4 consecutive quarters into trailing
twelve month metrics. TTM calculations smooth seasonal variations and
provide a current view of annual performance.

Example:
    >>> from edgar import Company
    >>> company = Company('AAPL')
    >>> ttm = company.get_ttm_revenue()
    >>> print(f"TTM Revenue: ${ttm.value / 1e9:.1f}B")
    TTM Revenue: $391.0B

"""
from dataclasses import dataclass
from datetime import date
from typing import Callable, List, Optional, Tuple

import pandas as pd

from edgar.entity.models import FinancialFact

# =============================================================================
# Duration Classification Constants
# =============================================================================
# These ranges define how we classify SEC filing periods by their duration.
# Ranges are non-overlapping to ensure deterministic classification.

# Quarter: ~90 days (shortest valid quarter to longest, accounting for calendar variations)
QUARTER_MIN_DAYS = 70
QUARTER_MAX_DAYS = 120

# YTD 6-Month: ~180 days (Jan-Jun or equivalent fiscal periods)
YTD_6M_MIN_DAYS = 140
YTD_6M_MAX_DAYS = 229  # Non-overlapping with YTD_9M

# YTD 9-Month: ~270 days (Jan-Sep or equivalent fiscal periods)
YTD_9M_MIN_DAYS = 230
YTD_9M_MAX_DAYS = 329  # Non-overlapping with Annual

# Annual: ~365 days (full fiscal year)
ANNUAL_MIN_DAYS = 330
ANNUAL_MAX_DAYS = 420

# Calculation limits
MAX_TTM_PERIODS = 100  # Maximum periods for TTM trend calculation
MIN_QUARTERS_FOR_TTM = 4  # Minimum quarters needed for a single TTM value

# Split detection
MAX_SPLIT_LAG_DAYS = 280  # Maximum days between period_end and filing_date for valid split
MAX_SPLIT_DURATION_DAYS = 31  # Maximum duration for a valid split fact (instant or short)


class DurationBucket:
    """Duration classification buckets for period facts."""

    QUARTER = "QUARTER"     # 70-120 days
    YTD_6M = "YTD_6M"       # 140-240 days
    YTD_9M = "YTD_9M"       # 230-330 days
    ANNUAL = "ANNUAL"       # 330-420 days
    OTHER = "OTHER"         # Outside normal ranges


@dataclass
class TTMMetric:
    """Result of a TTM calculation.

    Attributes:
        concept: XBRL concept identifier (e.g., 'us-gaap:Revenue')
        label: Human-readable label (e.g., 'Revenue')
        value: TTM value (sum of 4 quarters)
        unit: Unit of measurement (e.g., 'USD', 'shares')
        as_of_date: Date of most recent quarter in TTM window
        periods: List of fiscal periods included [(2023, 'Q3'), (2023, 'Q4'), ...]
        period_facts: List of FinancialFact objects used in calculation
        has_gaps: True if quarters are not consecutive
        has_calculated_q4: True if Q4 was calculated from FY - (Q1+Q2+Q3)
        warning: Optional warning message about data quality

    """

    concept: str
    label: str
    value: float
    unit: str
    as_of_date: date
    periods: List[Tuple[int, str]]  # [(fiscal_year, fiscal_period), ...]
    period_facts: List[FinancialFact]
    has_gaps: bool
    has_calculated_q4: bool = False
    warning: Optional[str] = None

    def __repr__(self):
        """String representation."""
        periods_str = ", ".join(f"{fp} {fy}" for fy, fp in self.periods)
        return (
            f"TTMMetric(concept='{self.concept}', "
            f"value={self.value:,.0f}, "
            f"periods=[{periods_str}])"
        )


class TTMCalculator:
    """Calculates TTM metrics from quarterly financial facts.

    TTM (Trailing Twelve Months) aggregates 4 consecutive quarters into a
    rolling 12-month metric. This provides a smoothed view of financial
    performance that eliminates seasonal variations.

    Example:
        >>> calculator = TTMCalculator(revenue_facts)
        >>> ttm = calculator.calculate_ttm()
        >>> print(f"TTM: ${ttm.value:,.0f}")
        TTM: $391,035,000,000

    """

    def __init__(self, facts: List[FinancialFact]):
        """Initialize with list of facts for a single concept.

        Args:
            facts: List of FinancialFact objects for one concept

        """
        self.facts = facts

    def calculate_ttm(self, as_of: Optional[date] = None) -> TTMMetric:
        """Calculate TTM value as of a specific date.

        Selects the 4 most recent consecutive quarters ending on or before
        the as_of date and sums their values. Quarters are obtained via
        quarterization, which derives Q2, Q3, and Q4 from YTD and annual facts
        when discrete quarterly filings are not available.

        Args:
            as_of: Date to calculate TTM as of (uses most recent if None)

        Returns:
            TTMMetric with value and metadata

        Raises:
            ValueError: If insufficient data (<4 quarters available after quarterization)

        Example:
            >>> ttm = calculator.calculate_ttm(as_of=date(2024, 3, 30))
            >>> print(ttm.periods)
            [(2023, 'Q3'), (2023, 'Q4'), (2024, 'Q1'), (2024, 'Q2')]

        """

        # 1. Get quarterized facts (includes derived Q2, Q3, Q4 from YTD/annual)
        quarterly = self._filter_quarterly_facts()

        # 2. Select 4 consecutive quarters ending on/before as_of
        ttm_quarters = self._select_ttm_window(quarterly, as_of)

        # 3. Validate minimum 4 quarters
        if len(ttm_quarters) < 4:
            raise ValueError(
                f"Insufficient quarterly data: found {len(ttm_quarters)} quarters, "
                f"need at least 4 for TTM calculation. "
                f"Quarterization requires Q1, YTD_6M, YTD_9M, and FY facts to derive all quarters."
            )

        # 4. Check for gaps in quarterly data
        has_gaps = self._check_for_gaps(ttm_quarters)

        # 5. Sum quarterly values to get TTM
        ttm_value = sum(q.numeric_value for q in ttm_quarters)

        # 6. Check if any quarters were derived (vs. reported)
        has_calculated_q4 = any(
            q.calculation_context and 'derived' in q.calculation_context
            for q in ttm_quarters
        )

        # 7. Generate warning if data quality issues exist
        warning = self._generate_warning(quarterly, ttm_quarters, has_calculated_q4)

        # 8. Build and return result
        return TTMMetric(
            concept=ttm_quarters[0].concept,
            label=ttm_quarters[0].label,
            value=ttm_value,
            unit=ttm_quarters[0].unit,
            as_of_date=ttm_quarters[-1].period_end,  # Most recent quarter
            periods=[(q.fiscal_year, q.fiscal_period) for q in ttm_quarters],
            period_facts=ttm_quarters,
            has_gaps=has_gaps,
            has_calculated_q4=has_calculated_q4,
            warning=warning
        )

    def calculate_ttm_trend(self, periods: int = 8) -> pd.DataFrame:
        """Calculate rolling TTM values for multiple periods.

        Creates a time series of TTM values, with each row representing
        a different "as of" quarter. Useful for analyzing TTM trends
        and growth patterns over time.

        Args:
            periods: Number of TTM values to calculate (default: 8, max: 100)

        Returns:
            DataFrame with columns:
            - as_of_quarter: e.g., 'Q2 2024'
            - ttm_value: TTM value for that quarter
            - fiscal_year: e.g., 2024
            - fiscal_period: e.g., 'Q2'
            - yoy_growth: % change vs 4 quarters ago (None if insufficient data)
            - periods_included: List of quarters in this TTM window

        Raises:
            ValueError: If periods < 1 or > 100, or insufficient data

        Example:
            >>> trend = calculator.calculate_ttm_trend(periods=8)
            >>> print(trend[['as_of_quarter', 'ttm_value', 'yoy_growth']])
            as_of_quarter    ttm_value  yoy_growth
            Q2 2024          391.0B     0.042
            Q1 2024          390.0B     0.031
            ...

        """
        # Validate periods parameter
        if periods < 1 or periods > MAX_TTM_PERIODS:
            raise ValueError(f"periods must be between 1 and {MAX_TTM_PERIODS}, got {periods}")

        # 1. Filter to quarterly facts
        quarterly = self._filter_quarterly_facts()

        # 2. Sort chronologically (oldest to newest)
        sorted_facts = sorted(quarterly, key=lambda f: f.period_end)

        # 3. Check minimum quarters needed
        if len(sorted_facts) < MIN_QUARTERS_FOR_TTM:
            raise ValueError(
                f"Insufficient data for TTM trend: need at least {MIN_QUARTERS_FOR_TTM} quarters, "
                f"found {len(sorted_facts)} quarters"
            )

        # 4. Calculate only the requested number of TTM windows (from most recent)
        # For YoY growth, we need 4 extra quarters, so calculate a few more if available
        results = []
        total_available = len(sorted_facts) - 3  # Number of possible TTM windows
        num_to_calculate = min(periods, total_available)

        # Calculate from most recent backwards
        for offset in range(num_to_calculate):
            i = len(sorted_facts) - 1 - offset
            # TTM window: quarters [i-3, i-2, i-1, i] (4 quarters)
            ttm_window = sorted_facts[i-3:i+1]
            ttm_value = sum(q.numeric_value for q in ttm_window)

            # Calculate YoY growth (compare to TTM from 4 quarters ago)
            yoy_growth = None
            if i >= 7:  # Need 8 total quarters for YoY comparison
                prior_ttm_window = sorted_facts[i-7:i-3]
                prior_ttm = sum(q.numeric_value for q in prior_ttm_window)
                # Only calculate YoY for positive prior values (negative = losses)
                if prior_ttm > 0:
                    yoy_growth = (ttm_value - prior_ttm) / prior_ttm

            # Build result row
            as_of_fact = sorted_facts[i]
            results.append({
                'as_of_quarter': f"{as_of_fact.fiscal_period} {as_of_fact.fiscal_year}",
                'ttm_value': ttm_value,
                'fiscal_year': as_of_fact.fiscal_year,
                'fiscal_period': as_of_fact.fiscal_period,
                'as_of_date': as_of_fact.period_end,  # Add period_end for statement builder
                'yoy_growth': yoy_growth,
                'periods_included': [
                    (q.fiscal_year, q.fiscal_period) for q in ttm_window
                ]
            })

        # 5. Convert to DataFrame (already in most-recent-first order)
        return pd.DataFrame(results)

    def _filter_quarterly_facts(self) -> List[FinancialFact]:
        """Get discrete quarterly facts.

        Returns both reported quarters (80-120 day periods) and quarters derived
        from YTD/annual facts. This handles the common filing pattern where Q2
        and Q3 are reported as YTD cumulative values rather than discrete quarters.

        The quarterization process:
        - Q1: Reported discrete quarter (70-120 days)
        - Q2: Derived from YTD_6M - Q1
        - Q3: Derived from YTD_9M - YTD_6M
        - Q4: Derived from FY - YTD_9M

        Returns:
            List of discrete quarterly facts (reported + derived)

        Example:
            >>> # Company files: Q1 ($100B), YTD_6M ($220B), YTD_9M ($350B), FY ($480B)
            >>> quarters = calculator._filter_quarterly_facts()
            >>> # Returns: Q1 ($100B), Q2 ($120B), Q3 ($130B), Q4 ($130B)

        """
        return self._quarterize_facts()

    def _filter_annual_facts(self) -> List[FinancialFact]:
        """Filter to annual duration facts (~365 days).

        Returns:
            List of facts with duration between 350-380 days

        """
        annual = []

        for fact in self.facts:
            # Skip non-duration facts (instant/point-in-time)
            if fact.period_type != 'duration':
                continue

            # Skip facts without start/end dates
            if not fact.period_start or not fact.period_end:
                continue

            # Calculate duration in days
            duration_days = (fact.period_end - fact.period_start).days

            # Annual periods are typically 350-380 days
            # (allows for calendar variations: 363-365 days common, leap years 366)
            if 350 <= duration_days <= 380:
                annual.append(fact)

        return annual

    def _classify_duration(self, fact: FinancialFact) -> str:
        """Classify fact by duration bucket.

        Uses period_start and period_end to determine if fact represents
        a discrete quarter, YTD (year-to-date), or annual period.

        Args:
            fact: FinancialFact to classify

        Returns:
            DurationBucket classification (QUARTER, YTD_6M, YTD_9M, ANNUAL, or OTHER)

        Example:
            >>> fact = FinancialFact(..., period_start=date(2023,1,1), period_end=date(2023,6,30))
            >>> bucket = calculator._classify_duration(fact)
            >>> print(bucket)
            'YTD_6M'  # 180 days

        """
        if not fact.period_start or not fact.period_end:
            return DurationBucket.OTHER

        days = (fact.period_end - fact.period_start).days

        # Use module constants for non-overlapping ranges
        if QUARTER_MIN_DAYS <= days <= QUARTER_MAX_DAYS:
            return DurationBucket.QUARTER
        if YTD_6M_MIN_DAYS <= days <= YTD_6M_MAX_DAYS:
            return DurationBucket.YTD_6M
        if YTD_9M_MIN_DAYS <= days <= YTD_9M_MAX_DAYS:
            return DurationBucket.YTD_9M
        if ANNUAL_MIN_DAYS <= days <= ANNUAL_MAX_DAYS:
            return DurationBucket.ANNUAL
        return DurationBucket.OTHER

    def _filter_by_duration(
        self,
        bucket: str,
        require_duration: bool = True
    ) -> List[FinancialFact]:
        """Filter facts to specific duration bucket.

        Args:
            bucket: DurationBucket constant (QUARTER, YTD_6M, YTD_9M, or ANNUAL)
            require_duration: If True, only include duration-type facts (default: True)

        Returns:
            List of facts matching the duration bucket

        Example:
            >>> quarters = calculator._filter_by_duration(DurationBucket.QUARTER)
            >>> ytd_6m = calculator._filter_by_duration(DurationBucket.YTD_6M)

        """
        filtered = []
        for fact in self.facts:
            # Skip non-duration facts if required
            if require_duration and fact.period_type != 'duration':
                continue

            # Check if fact matches bucket
            if self._classify_duration(fact) == bucket:
                filtered.append(fact)

        return filtered

    def _is_additive_concept(self, fact: FinancialFact) -> bool:
        """Check if a fact represents an additive concept (safe for derivation).
        
        Derivation (e.g., Q4 = FY - YTD_9M) relies on the concept being additive over time.
        Non-additive concepts cannot be subtracted to find a period-specific value.
        
        Returns False for:
        - Instant facts (Assets, Equity) - point-in-time, not flows
        - Share counts (UnitType.SHARES) - not additive
        - Ratios/Rates (UnitType.RATIO) - averages, not sums
        - Per-share metrics (EPS) - derived from Income/Shares, shares change
        
        Returns True for:
        - Duration monetary flows (Revenue, Net Income) - truly additive
        """
        from edgar.core import log

        # 1. Period Type Check - instant facts are never additive
        if fact.period_type == 'instant':
            log.debug(f"Skipping derivation for {fact.concept}: instant period type")
            return False

        # 2. Unit Type Check
        if not fact.unit:
            return True  # Assume additive if no unit (rare)

        from edgar.entity.unit_handling import UnitNormalizer, UnitType
        norm_unit = UnitNormalizer.normalize_unit(fact.unit)
        unit_type = UnitNormalizer.get_unit_type(norm_unit)

        # Exclude Shares and Ratios
        if unit_type in (UnitType.SHARES, UnitType.RATIO):
            log.debug(f"Skipping derivation for {fact.concept}: unit type {unit_type}")
            return False

        # Exclude Per Share metrics (EPS)
        # Note: get_unit_type maps per-share to CURRENCY, so check mappings directly
        if norm_unit in UnitNormalizer.PER_SHARE_MAPPINGS:
            log.debug(f"Skipping derivation for {fact.concept}: per-share unit")
            return False

        # Additional keyword safety
        unit_lower = norm_unit.lower()
        if 'shares' in unit_lower or 'pure' in unit_lower or 'ratio' in unit_lower:
            log.debug(f"Skipping derivation for {fact.concept}: unit contains keyword")
            return False

        return True

    def _is_positive_concept(self, concept: str) -> bool:
        """Check if a concept should always be positive (e.g., revenue, assets).

        For these concepts, a negative derived value indicates data quality issues
        rather than legitimate negative values (like losses).

        Args:
            concept: XBRL concept name (may include namespace prefix)

        Returns:
            True if concept should be positive, False if negatives are valid
        """
        # Normalize concept name (remove namespace prefix)
        name = concept.split(':')[-1].lower() if ':' in concept else concept.lower()

        # Concepts that should always be positive
        positive_keywords = [
            'revenue', 'sales', 'asset', 'cash', 'inventory',
            'receivable', 'property', 'equipment', 'goodwill',
            'grossprofit',  # Gross profit should be positive
        ]

        # Concepts that can legitimately be negative
        negative_ok_keywords = [
            'income', 'loss', 'expense', 'cost', 'liability',
            'deficit', 'impairment', 'depreciation', 'amortization',
            'interest', 'tax', 'earnings', 'profit',  # Can be loss
        ]

        # Check for negative-OK keywords first (more specific)
        for keyword in negative_ok_keywords:
            if keyword in name:
                return False

        # Check for positive-required keywords
        for keyword in positive_keywords:
            if keyword in name:
                return True

        # Default: allow negatives (conservative)
        return False

    def _quarterize_facts(self) -> List[FinancialFact]:
        """Convert YTD and annual facts into discrete quarters.

        This method handles the common SEC filing pattern where companies report:
        - Q1 as discrete quarter (70-120 days)
        - Q2 as YTD (Jan-Jun, 140-240 days)
        - Q3 as YTD (Jan-Sep, 230-330 days)
        - FY as annual (Jan-Dec, 330-420 days)

        Derives:
        - Q2 from YTD_6M - Q1
        - Q3 from YTD_9M - YTD_6M
        - Q4 from FY - YTD_9M

        Returns:
            List of discrete quarterly facts (reported + derived), deduplicated
            and sorted by period_end

        """
        from edgar.core import log

        # 1. Separate by duration bucket
        quarters = self._filter_by_duration(DurationBucket.QUARTER)
        ytd_6m = self._filter_by_duration(DurationBucket.YTD_6M)
        ytd_9m = self._filter_by_duration(DurationBucket.YTD_9M)
        annual = self._filter_by_duration(DurationBucket.ANNUAL)

        discrete_quarters = []

        # 2. Keep all reported discrete quarters
        discrete_quarters.extend(quarters)
        log.debug(f"Found {len(quarters)} reported discrete quarters")

        # 3. Derive quarters using helper methods
        discrete_quarters.extend(self._derive_q2_from_ytd6(quarters, ytd_6m))
        discrete_quarters.extend(self._derive_q3_from_ytd9(ytd_6m, ytd_9m))
        discrete_quarters.extend(self._derive_q4_from_fy(quarters, ytd_9m, annual))

        # 4. Deduplicate by period_end (keep latest filing)
        dedup_quarters = self._deduplicate_by_period_end(discrete_quarters)
        log.debug(f"Quarterization complete: {len(dedup_quarters)} discrete quarters "
                  f"({len(quarters)} reported + {len(dedup_quarters) - len(quarters)} derived)")

        return dedup_quarters

    def _derive_q2_from_ytd6(
        self,
        quarters: List[FinancialFact],
        ytd_6m: List[FinancialFact]
    ) -> List[FinancialFact]:
        from edgar.core import log
        derived = []
        for ytd6 in ytd_6m:
            if not self._is_additive_concept(ytd6):
                continue
            q1 = self._find_prior_quarter(quarters, before=ytd6.period_end)
            if q1:
                q2_value = ytd6.numeric_value - q1.numeric_value

                # Skip if negative and concept should be positive (revenue-like)
                if q2_value < 0 and self._is_positive_concept(ytd6.concept):
                    log.warning(f"Data quality issue: Q1 ({q1.numeric_value/1e9:.2f}B) > "
                                f"YTD_6M ({ytd6.numeric_value/1e9:.2f}B) for {ytd6.concept}, skipping Q2 derivation")
                    continue

                from datetime import timedelta
                q2_start = q1.period_end + timedelta(days=1)
                q2_fact = self._create_derived_quarter(
                    ytd6, q2_value, "derived_q2_ytd6_minus_q1", target_period="Q2",
                    period_start=q2_start
                )
                derived.append(q2_fact)
                log.debug(f"Derived Q2 from YTD_6M: ${q2_value/1e9:.2f}B "
                          f"(YTD_6M ${ytd6.numeric_value/1e9:.2f}B - Q1 ${q1.numeric_value/1e9:.2f}B)")
        return derived

    def _derive_q3_from_ytd9(
        self,
        ytd_6m: List[FinancialFact],
        ytd_9m: List[FinancialFact]
    ) -> List[FinancialFact]:
        from edgar.core import log
        derived = []
        for ytd9 in ytd_9m:
            if not self._is_additive_concept(ytd9):
                continue
            ytd6 = self._find_prior_ytd6(ytd_6m, before=ytd9.period_end)
            if ytd6:
                q3_value = ytd9.numeric_value - ytd6.numeric_value

                # Skip if negative and concept should be positive (revenue-like)
                if q3_value < 0 and self._is_positive_concept(ytd9.concept):
                    log.warning(f"Data quality issue: YTD_6M ({ytd6.numeric_value/1e9:.2f}B) > "
                                f"YTD_9M ({ytd9.numeric_value/1e9:.2f}B) for {ytd9.concept}, skipping Q3 derivation")
                    continue

                from datetime import timedelta
                q3_start = ytd6.period_end + timedelta(days=1)
                q3_fact = self._create_derived_quarter(
                    ytd9, q3_value, "derived_q3_ytd9_minus_ytd6", target_period="Q3",
                    period_start=q3_start
                )
                derived.append(q3_fact)
                log.debug(f"Derived Q3 from YTD_9M: ${q3_value/1e9:.2f}B "
                          f"(YTD_9M ${ytd9.numeric_value/1e9:.2f}B - YTD_6M ${ytd6.numeric_value/1e9:.2f}B)")
        return derived

    def _derive_q4_from_fy(
        self,
        quarters: List[FinancialFact],
        ytd_9m: List[FinancialFact],
        annual: List[FinancialFact]
    ) -> List[FinancialFact]:
        from dataclasses import replace

        from edgar.core import log
        from edgar.entity.enhanced_statement import (
            calculate_fiscal_year_for_label,
            detect_fiscal_year_end,
        )
        derived = []
        fiscal_year_end_month = detect_fiscal_year_end(self.facts)
        for fy in annual:
            if not self._is_additive_concept(fy):
                continue
            ytd9 = self._find_matching_ytd9(
                ytd_9m, period_start=fy.period_start, before=fy.period_end
            )
            if ytd9:
                q4_value = fy.numeric_value - ytd9.numeric_value

                # Skip if negative and concept should be positive (revenue-like)
                if q4_value < 0 and self._is_positive_concept(fy.concept):
                    log.warning(f"Data quality issue: YTD_9M ({ytd9.numeric_value/1e9:.2f}B) > "
                                f"FY ({fy.numeric_value/1e9:.2f}B) for {fy.concept}, skipping Q4 derivation")
                    continue

                from datetime import timedelta
                q4_start = ytd9.period_end + timedelta(days=1)
                q4_fact = self._create_derived_quarter(
                    fy, q4_value, "derived_q4_fy_minus_ytd9", target_period="Q4",
                    period_start=q4_start
                )
                if q4_fact.period_end:
                    calculated_fy = calculate_fiscal_year_for_label(
                        q4_fact.period_end, fiscal_year_end_month
                    )
                    q4_fact = replace(q4_fact, fiscal_year=calculated_fy)
                derived.append(q4_fact)
                log.debug(f"Derived Q4 from FY: ${q4_value/1e9:.2f}B "
                          f"(FY ${fy.numeric_value/1e9:.2f}B - YTD_9M ${ytd9.numeric_value/1e9:.2f}B)")
                continue

            # Fallback: derive Q4 from FY - (Q1 + Q2 + Q3) when YTD_9M is absent
            q1_q3_candidates = []
            for q in quarters:
                if q.fiscal_period not in ("Q1", "Q2", "Q3"):
                    continue
                if q.numeric_value is None or q.period_start is None or q.period_end is None:
                    continue
                if fy.period_start and fy.period_end:
                    if not (fy.period_start <= q.period_start <= fy.period_end):
                        continue
                    if not (fy.period_start <= q.period_end <= fy.period_end):
                        continue
                q1_q3_candidates.append(q)

            if not q1_q3_candidates:
                log.debug(f"No Q1-Q3 quarters found for FY {fy.fiscal_year} - cannot derive Q4")
                continue

            # Prefer the latest filing per quarter
            quarter_by_period = {}
            for q in q1_q3_candidates:
                existing = quarter_by_period.get(q.fiscal_period)
                if not existing or (q.filing_date and existing.filing_date and q.filing_date > existing.filing_date):
                    quarter_by_period[q.fiscal_period] = q

            ordered_quarters = [quarter_by_period.get(p) for p in ("Q1", "Q2", "Q3")]
            if any(q is None for q in ordered_quarters):
                log.debug(f"Incomplete Q1-Q3 set for FY {fy.fiscal_year} - cannot derive Q4")
                continue

            q1, q2, q3 = ordered_quarters
            if any(q.numeric_value is None for q in (q1, q2, q3)):
                log.debug(f"Missing numeric values for Q1-Q3 FY {fy.fiscal_year} - cannot derive Q4")
                continue

            q4_value = fy.numeric_value - (q1.numeric_value + q2.numeric_value + q3.numeric_value)

            # Skip if negative and concept should be positive (revenue-like)
            if q4_value < 0 and self._is_positive_concept(fy.concept):
                q1_q3_sum = q1.numeric_value + q2.numeric_value + q3.numeric_value
                log.warning(f"Data quality issue: Q1+Q2+Q3 ({q1_q3_sum/1e9:.2f}B) > "
                            f"FY ({fy.numeric_value/1e9:.2f}B) for {fy.concept}, skipping Q4 derivation")
                continue

            from datetime import timedelta
            q4_start = q3.period_end + timedelta(days=1)
            q4_fact = self._create_derived_quarter(
                fy, q4_value, "derived_q4_fy_minus_q1q2q3", target_period="Q4",
                period_start=q4_start
            )
            if q4_fact.period_end:
                calculated_fy = calculate_fiscal_year_for_label(
                    q4_fact.period_end, fiscal_year_end_month
                )
                q4_fact = replace(q4_fact, fiscal_year=calculated_fy)
            derived.append(q4_fact)
            log.debug(
                f"Derived Q4 from FY: ${q4_value/1e9:.2f}B "
                f"(FY ${fy.numeric_value/1e9:.2f}B - Q1-3 ${((q1.numeric_value + q2.numeric_value + q3.numeric_value)/1e9):.2f}B)"
            )
        return derived

    def derive_eps_for_quarter(
        self,
        net_income_facts: List[FinancialFact],
        shares_facts: List[FinancialFact],
        eps_concept: str = 'us-gaap:EarningsPerShareBasic'
    ) -> List[FinancialFact]:
        """Calculate EPS for derived quarters using Net Income / Weighted Avg Shares.
        
        This method provides accurate Q4 EPS calculation by:
        1. Deriving Q4 Net Income (additive, safe to derive)
        2. Using FY Weighted Average Shares for Q4 (best available)
        3. Computing Q4 EPS = Q4 Net Income / FY Shares
        
        Args:
            net_income_facts: Facts for NetIncomeLoss concept
            shares_facts: Facts for WeightedAverageNumberOfSharesOutstandingBasic
            eps_concept: XBRL concept for the EPS (default: basic)
        
        Returns:
            List of derived EPS FinancialFact objects for Q4 periods

        """
        from edgar.core import log

        derived_eps = []

        # Step 1: Get Q4 Net Income facts (derived or reported)
        ni_calculator = TTMCalculator(net_income_facts)
        ni_quarters = ni_calculator._quarterize_facts()
        q4_net_income = [q for q in ni_quarters if q.fiscal_period == 'Q4']

        if not q4_net_income:
            log.debug("No derived Q4 Net Income found - cannot calculate Q4 EPS")
            return derived_eps

        # Step 2: Get shares by period (FY and YTD9)
        shares_calculator = TTMCalculator(shares_facts)
        fy_shares_list = shares_calculator._filter_by_duration(DurationBucket.ANNUAL)
        ytd9_shares_list = shares_calculator._filter_by_duration(DurationBucket.YTD_9M)

        # Build lookup by fiscal year
        fy_shares_by_year = {s.fiscal_year: s.numeric_value for s in fy_shares_list}
        ytd9_shares_by_year = {s.fiscal_year: s.numeric_value for s in ytd9_shares_list}

        # Step 3: Calculate Q4 EPS
        for q4_ni in q4_net_income:
            eps_fact = self._calculate_single_q4_eps(
                q4_ni, fy_shares_by_year, ytd9_shares_by_year, eps_concept
            )
            if eps_fact:
                derived_eps.append(eps_fact)

        return derived_eps

    def _calculate_single_q4_eps(
        self,
        q4_ni: FinancialFact,
        fy_shares_map: dict,
        ytd9_shares_map: dict,
        eps_concept: str
    ) -> Optional[FinancialFact]:
        from edgar.core import log
        from edgar.entity.mappings_loader import get_primary_statement
        fy = q4_ni.fiscal_year

        if fy not in fy_shares_map or fy_shares_map[fy] <= 0:
            log.debug(f"No FY shares found for {fy} - cannot calculate Q4 EPS")
            return None

        fy_shares = fy_shares_map[fy]
        ytd9_shares = ytd9_shares_map.get(fy)
        q4_shares = fy_shares # Default fallback

        # Precise Q4 shares formula: Q4_WAS = 4 * FY_WAS - 3 * YTD9_WAS
        if ytd9_shares and ytd9_shares > 0:
            calculated_q4_shares = 4 * fy_shares - 3 * ytd9_shares

            if calculated_q4_shares > 0:
                q4_shares = calculated_q4_shares
                share_change_pct = ((q4_shares - fy_shares) / fy_shares) * 100
                log.debug(f"FY{fy}: Q4 WAS = {q4_shares/1e6:.2f}M "
                            f"(FY: {fy_shares/1e6:.2f}M, change: {share_change_pct:.1f}%)")
            else:
                log.debug(f"FY{fy}: Derived Q4 shares invalid ({calculated_q4_shares}), using FY shares")
        else:
            log.debug(f"FY{fy}: No YTD9 shares, using FY shares")

        # Guard against division by zero
        if q4_shares <= 0:
            log.warning(f"FY{fy}: Invalid Q4 shares ({q4_shares}) - cannot calculate EPS")
            return None

        q4_eps_value = q4_ni.numeric_value / q4_shares

        log.debug(f"Derived Q4 EPS for FY{fy}: ${q4_eps_value:.2f} "
                    f"(NI ${q4_ni.numeric_value/1e9:.2f}B / {q4_shares/1e9:.2f}B shares)")

        clean_concept = eps_concept.split(':')[-1] if ':' in eps_concept else eps_concept
        statement_type = get_primary_statement(clean_concept)

        return FinancialFact(
            concept=eps_concept,
            taxonomy='us-gaap',
            label='Earnings Per Share (Derived)',
            value=q4_eps_value,
            numeric_value=q4_eps_value,
            unit='USD/share',
            fiscal_year=fy,
            fiscal_period='Q4',
            period_type='duration',
            period_start=q4_ni.period_start,
            period_end=q4_ni.period_end,
            filing_date=q4_ni.filing_date,
            form_type=q4_ni.form_type,
            accession=q4_ni.accession,
            statement_type=statement_type,
            calculation_context='derived_eps_from_ni_shares'
        )

    def _find_prior_quarter(
        self,
        quarters: List[FinancialFact],
        before: date
    ) -> Optional[FinancialFact]:
        """Find the most recent quarter ending before a date.

        Args:
            quarters: List of quarterly facts
            before: Date to search before

        Returns:
            Most recent quarter ending before the date, or None if not found

        Example:
            >>> q1 = calculator._find_prior_quarter(quarters, before=date(2023, 6, 30))
            >>> # Returns Q1 ending 2023-03-31

        """
        candidates = [q for q in quarters if q.period_end < before]
        return max(candidates, key=lambda q: q.period_end) if candidates else None

    def _find_prior_ytd6(
        self,
        ytd_6m: List[FinancialFact],
        before: date
    ) -> Optional[FinancialFact]:
        """Find the most recent YTD_6M ending before a date.

        Args:
            ytd_6m: List of YTD_6M facts
            before: Date to search before

        Returns:
            Most recent YTD_6M ending before the date, or None if not found

        Example:
            >>> ytd6 = calculator._find_prior_ytd6(ytd_6m, before=date(2023, 9, 30))
            >>> # Returns YTD_6M ending 2023-06-30

        """
        candidates = [y for y in ytd_6m if y.period_end < before]
        return max(candidates, key=lambda y: y.period_end) if candidates else None

    def _find_matching_ytd9(
        self,
        ytd_9m: List[FinancialFact],
        period_start: date,
        before: date
    ) -> Optional[FinancialFact]:
        """Find YTD_9M with matching period_start (same fiscal year).

        Attempts to match period_start exactly to ensure Q4 derivation uses
        YTD_9M from the same fiscal year as the annual fact. Falls back to
        latest YTD_9M before the date if exact match not found.

        Args:
            ytd_9m: List of YTD_9M facts
            period_start: Fiscal year start date to match
            before: Date to search before

        Returns:
            YTD_9M fact with matching period_start, or latest before date

        Example:
            >>> ytd9 = calculator._find_matching_ytd9(
            ...     ytd_9m,
            ...     period_start=date(2023, 1, 1),
            ...     before=date(2023, 12, 31)
            ... )
            >>> # Returns YTD_9M with period_start=2023-01-01

        """
        # First try exact period_start match (same fiscal year)
        candidates = [
            y for y in ytd_9m
            if y.period_start == period_start and y.period_end < before
        ]
        if candidates:
            return max(candidates, key=lambda y: y.period_end)

        # Fallback: latest YTD_9M before the date
        candidates = [y for y in ytd_9m if y.period_end < before]
        return max(candidates, key=lambda y: y.period_end) if candidates else None

    def _create_derived_quarter(
        self,
        source_fact: FinancialFact,
        derived_value: float,
        derivation_method: str,
        target_period: Optional[str] = None,
        period_start: Optional[date] = None
    ) -> FinancialFact:
        """Create a synthetic quarter fact from derivation.

        Args:
            source_fact: Source YTD or annual fact
            derived_value: Calculated discrete quarter value
            derivation_method: Description of how value was derived
            target_period: Fiscal period label (e.g., 'Q2', 'Q4'). Defaults to source's.
            period_start: Optional start date for the derived period

        Returns:
            New FinancialFact with derived value and metadata

        Example:
            >>> q2_fact = calculator._create_derived_quarter(
            ...     ytd6_fact,
            ...     120e9,
            ...     "derived_q2_ytd6_minus_q1",
            ...     target_period="Q2"
            ... )

        """
        # Ensure statement_type is set (if None, builder rejects in _fact_belongs_to_statement fallback due to linkage rules)
        stmt_type = source_fact.statement_type
        if not stmt_type:
            from edgar.entity.mappings_loader import get_primary_statement
            clean_concept = source_fact.concept.split(':')[-1] if ':' in source_fact.concept else source_fact.concept
            stmt_type = get_primary_statement(clean_concept)

        return FinancialFact(
            concept=source_fact.concept,
            taxonomy=source_fact.taxonomy,
            label=source_fact.label,
            value=derived_value,
            numeric_value=derived_value,
            unit=source_fact.unit,
            fiscal_year=source_fact.fiscal_year,
            fiscal_period=target_period or source_fact.fiscal_period,
            period_type='duration',
            period_start=period_start or source_fact.period_start,
            period_end=source_fact.period_end,
            filing_date=source_fact.filing_date,
            form_type=source_fact.form_type,
            accession=source_fact.accession,
            statement_type=stmt_type,
            calculation_context=derivation_method  # Mark as derived
        )

    def _deduplicate_by_period_end(
        self,
        facts: List[FinancialFact]
    ) -> List[FinancialFact]:
        """Keep latest fact per period_end (handles re-filings).

        When multiple facts exist for the same period_end (due to amended
        filings or derivation), keeps the most recently filed version.

        Args:
            facts: List of facts potentially containing duplicates

        Returns:
            Deduplicated list sorted by period_end

        Example:
            >>> dedup = calculator._deduplicate_by_period_end(all_quarters)
            >>> # Returns one fact per unique period_end date

        """
        by_end = {}
        for fact in facts:
            key = fact.period_end
            if key not in by_end:
                by_end[key] = fact
            elif fact.filing_date and by_end[key].filing_date and fact.filing_date > by_end[key].filing_date:
                # Keep the more recently filed version
                by_end[key] = fact
            elif fact.filing_date and not by_end[key].filing_date:
                # Prefer fact with filing_date over one without
                by_end[key] = fact
        return sorted(by_end.values(), key=lambda f: f.period_end)


    def _select_ttm_window(
        self,
        quarterly: List[FinancialFact],
        as_of: Optional[date]
    ) -> List[FinancialFact]:
        """Select 4 consecutive quarters ending on/before as_of date.

        Args:
            quarterly: List of quarterly facts
            as_of: Date to calculate TTM as of (None = most recent)

        Returns:
            List of 4 quarters in chronological order (oldest to newest)

        """
        # Sort by period_end descending (newest first)
        sorted_facts = sorted(quarterly, key=lambda f: f.period_end, reverse=True)

        # If as_of specified, filter to quarters ending on/before that date
        if as_of:
            sorted_facts = [f for f in sorted_facts if f.period_end <= as_of]

        # Take first 4 quarters (most recent)
        ttm_window = sorted_facts[:4]

        # Reverse to chronological order (oldest to newest)
        return list(reversed(ttm_window))

    def _check_for_gaps(self, quarters: List[FinancialFact]) -> bool:
        """Check if quarters are consecutive (~90 days apart).

        Args:
            quarters: List of quarters in chronological order

        Returns:
            True if gaps detected, False if quarters are consecutive

        """
        if len(quarters) < 2:
            return False

        for i in range(len(quarters) - 1):
            # Calculate gap between consecutive quarters
            gap = (quarters[i+1].period_end - quarters[i].period_end).days

            # Expect ~90 days between consecutive quarters
            # Allow 70-110 day range for calendar variations
            if not (70 <= gap <= 110):
                return True

        return False

    def _generate_warning(
        self,
        all_quarterly: List[FinancialFact],
        ttm_quarters: List[FinancialFact],
        has_calculated_q4: bool = False
    ) -> Optional[str]:
        """Generate warning message if data quality issues exist.

        Args:
            all_quarterly: All available quarterly facts
            ttm_quarters: 4 quarters used in TTM calculation
            has_calculated_q4: True if any quarters were derived from YTD/annual data

        Returns:
            Warning message string, or None if no issues

        """
        warnings = []

        # Info message if quarters were derived (not a warning, just informational)
        if has_calculated_q4:
            warnings.append(
                "Some quarters were derived from YTD or annual facts. "
                "These are calculated values, not directly reported quarterly data."
            )

        # Check total quarters available
        if len(all_quarterly) < 8:
            warnings.append(
                f"Only {len(all_quarterly)} quarters available. "
                "Minimum 8 quarters recommended for year-over-year TTM comparison."
            )

        # Check for gaps in TTM window
        if self._check_for_gaps(ttm_quarters):
            warnings.append(
                "Gaps detected in quarterly data. "
                "TTM calculation may not be accurate."
            )

        return " ".join(warnings) if warnings else None


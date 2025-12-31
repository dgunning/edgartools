"""
TTM (Trailing Twelve Months) calculation module.

Provides core logic for aggregating 4 consecutive quarters into trailing
twelve month metrics. TTM calculations smooth seasonal variations and
provide a current view of annual performance.

Example:
    >>> from edgar import Company
    >>> company = Company('AAPL')
    >>> facts = company.get_facts()
    >>> ttm = facts.get_ttm_revenue()
    >>> print(f"TTM Revenue: ${ttm.value / 1e9:.1f}B")
    TTM Revenue: $391.0B
"""
from dataclasses import dataclass
from datetime import date
from typing import Callable, List, Optional, Tuple

import pandas as pd

from edgar.entity.models import FinancialFact


class DurationBucket:
    """Duration classification buckets for period facts."""
    QUARTER = "QUARTER"     # 70-120 days
    YTD_6M = "YTD_6M"       # 140-240 days
    YTD_9M = "YTD_9M"       # 230-330 days
    ANNUAL = "ANNUAL"       # 330-420 days
    OTHER = "OTHER"         # Outside normal ranges


@dataclass
class TTMMetric:
    """
    Result of a TTM calculation.

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
    """
    Calculates TTM metrics from quarterly financial facts.

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
        """
        Initialize with list of facts for a single concept.

        Args:
            facts: List of FinancialFact objects for one concept
        """
        self.facts = facts

    def calculate_ttm(self, as_of: Optional[date] = None) -> TTMMetric:
        """
        Calculate TTM value as of a specific date.

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
        from edgar.core import log

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
        """
        Calculate rolling TTM values for multiple periods.

        Creates a time series of TTM values, with each row representing
        a different "as of" quarter. Useful for analyzing TTM trends
        and growth patterns over time.

        Args:
            periods: Number of TTM values to calculate (default: 8)

        Returns:
            DataFrame with columns:
            - as_of_quarter: e.g., 'Q2 2024'
            - ttm_value: TTM value for that quarter
            - fiscal_year: e.g., 2024
            - fiscal_period: e.g., 'Q2'
            - yoy_growth: % change vs 4 quarters ago (None if insufficient data)
            - periods_included: List of quarters in this TTM window

        Raises:
            ValueError: If insufficient data (need periods + 3 quarters)

        Example:
            >>> trend = calculator.calculate_ttm_trend(periods=8)
            >>> print(trend[['as_of_quarter', 'ttm_value', 'yoy_growth']])
            as_of_quarter    ttm_value  yoy_growth
            Q2 2024          391.0B     0.042
            Q1 2024          390.0B     0.031
            ...
        """
        # 1. Filter to quarterly facts
        quarterly = self._filter_quarterly_facts()

        # 2. Sort chronologically (oldest to newest)
        sorted_facts = sorted(quarterly, key=lambda f: f.period_end)

        # 3. Check minimum quarters needed
        # Need at least 4 quarters for a single TTM calculation
        if len(sorted_facts) < 4:
            raise ValueError(
                f"Insufficient data for TTM trend: need at least 4 quarters, "
                f"found {len(sorted_facts)} quarters"
            )

        # 4. Calculate TTM for ALL rolling windows
        results = []

        for i in range(3, len(sorted_facts)):
            # TTM window: quarters [i-3, i-2, i-1, i] (4 quarters)
            ttm_window = sorted_facts[i-3:i+1]
            ttm_value = sum(q.numeric_value for q in ttm_window)

            # Calculate YoY growth (compare to TTM from 4 quarters ago)
            yoy_growth = None
            if i >= 7:  # Need 8 total quarters for YoY comparison
                prior_ttm_window = sorted_facts[i-7:i-3]
                prior_ttm = sum(q.numeric_value for q in prior_ttm_window)
                if prior_ttm != 0:
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

        # 5. Convert to DataFrame
        df = pd.DataFrame(results)

        # Reverse so most recent quarter is first
        df = df.iloc[::-1].reset_index(drop=True)

        # 6. Return only the requested number of periods (most recent)
        if len(df) > periods:
            df = df.head(periods)

        return df

    def _filter_quarterly_facts(self) -> List[FinancialFact]:
        """
        Get discrete quarterly facts.

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
        """
        Filter to annual duration facts (~365 days).

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
        """
        Classify fact by duration bucket.

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

        if 70 <= days <= 120:   return DurationBucket.QUARTER
        if 140 <= days <= 240:  return DurationBucket.YTD_6M
        if 230 <= days <= 330:  return DurationBucket.YTD_9M
        if 330 <= days <= 420:  return DurationBucket.ANNUAL
        return DurationBucket.OTHER

    def _filter_by_duration(
        self,
        bucket: str,
        require_duration: bool = True
    ) -> List[FinancialFact]:
        """
        Filter facts to specific duration bucket.

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
        """
        Check if a fact represents an additive concept (safe for derivation).
        
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

    def _quarterize_facts(self) -> List[FinancialFact]:
        """
        Convert YTD and annual facts into discrete quarters.

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
        discrete_quarters.extend(self._derive_q4_from_fy(ytd_9m, annual))

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
                if q2_value < 0:
                    log.debug(f"Negative Q2 value detected: ${q2_value/1e9:.2f}B for {ytd6.concept}.")

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
                if q3_value < 0:
                    log.debug(f"Negative Q3 value detected: ${q3_value/1e9:.2f}B for {ytd9.concept}.")

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
        ytd_9m: List[FinancialFact],
        annual: List[FinancialFact]
    ) -> List[FinancialFact]:
        from edgar.core import log
        derived = []
        for fy in annual:
            if not self._is_additive_concept(fy):
                continue
            ytd9 = self._find_matching_ytd9(
                ytd_9m, period_start=fy.period_start, before=fy.period_end
            )
            if ytd9:
                q4_value = fy.numeric_value - ytd9.numeric_value
                if q4_value < 0:
                    log.debug(f"Negative Q4 value detected: ${q4_value/1e9:.2f}B for {fy.concept}.")

                from datetime import timedelta
                q4_start = ytd9.period_end + timedelta(days=1)
                q4_fact = self._create_derived_quarter(
                    fy, q4_value, "derived_q4_fy_minus_ytd9", target_period="Q4",
                    period_start=q4_start
                )
                derived.append(q4_fact)
                log.debug(f"Derived Q4 from FY: ${q4_value/1e9:.2f}B "
                          f"(FY ${fy.numeric_value/1e9:.2f}B - YTD_9M ${ytd9.numeric_value/1e9:.2f}B)")
        return derived

    def derive_eps_for_quarter(
        self,
        net_income_facts: List[FinancialFact],
        shares_facts: List[FinancialFact],
        eps_concept: str = 'us-gaap:EarningsPerShareBasic'
    ) -> List[FinancialFact]:
        """
        Calculate EPS for derived quarters using Net Income / Weighted Avg Shares.
        
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
        
        # Step 1: Get derived Q4 Net Income facts
        ni_calculator = TTMCalculator(net_income_facts)
        ni_quarters = ni_calculator._quarterize_facts()
        q4_net_income = [
            q for q in ni_quarters 
            if q.calculation_context and 'q4' in str(q.calculation_context).lower()
        ]
        
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
        
        q4_eps_value = q4_ni.numeric_value / q4_shares
        
        log.debug(f"Derived Q4 EPS for FY{fy}: ${q4_eps_value:.2f} "
                    f"(NI ${q4_ni.numeric_value/1e9:.2f}B / {q4_shares/1e9:.2f}B shares)")

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
            calculation_context='derived_eps_from_ni_shares'
        )

    def _find_prior_quarter(
        self,
        quarters: List[FinancialFact],
        before: date
    ) -> Optional[FinancialFact]:
        """
        Find the most recent quarter ending before a date.

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
        """
        Find the most recent YTD_6M ending before a date.

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
        """
        Find YTD_9M with matching period_start (same fiscal year).

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
        """
        Create a synthetic quarter fact from derivation.

        Args:
            source_fact: Source YTD or annual fact
            derived_value: Calculated discrete quarter value
            derivation_method: Description of how value was derived
            target_period: Fiscal period label (e.g., 'Q2', 'Q4'). Defaults to source's.

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
        """
        Keep latest fact per period_end (handles re-filings).

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
            if key not in by_end or fact.filing_date > by_end[key].filing_date:
                by_end[key] = fact
        return sorted(by_end.values(), key=lambda f: f.period_end)


    def _select_ttm_window(
        self,
        quarterly: List[FinancialFact],
        as_of: Optional[date]
    ) -> List[FinancialFact]:
        """
        Select 4 consecutive quarters ending on/before as_of date.

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
        """
        Check if quarters are consecutive (~90 days apart).

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
        """
        Generate warning message if data quality issues exist.

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


@dataclass
class TTMStatement:
    """
    TTM financial statement with multiple line items.

    Represents a full financial statement (Income Statement or Cash Flow
    Statement) calculated using TTM values for each line item.

    Attributes:
        statement_type: 'IncomeStatement' or 'CashFlowStatement'
        as_of_date: Date of most recent quarter
        items: List of line items with TTM values
        company_name: Company name
        cik: CIK number as string
    """
    statement_type: str
    as_of_date: date
    items: List[dict]  # [{label, values, concept, depth, is_total}, ...]
    company_name: str
    cik: str
    periods: Optional[List[Tuple[int, str]]] = None

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert statement to pandas DataFrame.

        Returns:
            DataFrame with columns: label, periods..., depth, is_total
        """
        rows = []
        period_labels = [f"{fp} {fy}" for fy, fp in self.periods] if self.periods else ["TTM"]
        for item in self.items:
            row = {
                'label': item.get('label', ''),
                'depth': item.get('depth', 0),
                'is_total': item.get('is_total', False)
            }
            values = item.get('values', {})
            if not values and 'value' in item:
                values = {"TTM": item.get('value')}
            for period in period_labels:
                row[period] = values.get(period)
            rows.append(row)
        return pd.DataFrame(rows)

    def __rich__(self):
        """Rich console representation styled like core statements."""
        import shutil
        from rich import box
        from rich.console import Group
        from rich.padding import Padding
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        from edgar.display import SYMBOLS, get_statement_styles
        from edgar.entity.enhanced_statement import _calculate_label_width

        styles = get_statement_styles()

        statement_names = {
            'IncomeStatement': 'Income Statement',
            'BalanceSheet': 'Balance Sheet',
            'CashFlowStatement': 'Cash Flow Statement',
        }
        statement_display = statement_names.get(self.statement_type, self.statement_type)

        ttm_periods = []
        source_periods = self.periods or []
        if source_periods:
            ttm_periods = [f"{fp} {fy}" for fy, fp in source_periods]
        period_range = ""
        if ttm_periods:
            period_range = f"{ttm_periods[-1]} to {ttm_periods[0]}"
        elif self.as_of_date:
            period_range = f"TTM as of {self.as_of_date:%Y-%m-%d}"

        title_lines = [
            Text(statement_display, style=styles["header"]["statement_title"]),
            Text(period_range, style=styles["metadata"]["period_range"]),
            Text("Amounts in USD", style=styles["metadata"]["units"]),
        ]
        title = Text("\n").join(title_lines)

        footer_parts = []
        if self.company_name:
            footer_parts.append((self.company_name, styles["header"]["company_name"]))
            footer_parts.append(("  ", ""))
            footer_parts.append((SYMBOLS["bullet"], styles["structure"]["separator"]))
            footer_parts.append(("  ", ""))
        footer_parts.append(("Source: ", styles["metadata"]["source"]))
        footer_parts.append(("EntityFacts", styles["metadata"]["source_entity_facts"]))
        footer = Text.assemble(*footer_parts)

        stmt_table = Table(
            box=box.SIMPLE,
            show_header=True,
            padding=(0, 1),
        )

        terminal_width = shutil.get_terminal_size().columns
        label_width = _calculate_label_width(max(len(ttm_periods), 1), terminal_width)
        stmt_table.add_column("", style="", width=label_width, no_wrap=False)
        if ttm_periods:
            for period in ttm_periods:
                stmt_table.add_column(period, justify="right", style="bold", min_width=10)
        else:
            stmt_table.add_column("TTM", justify="right", style="bold", min_width=10)

        for item in self.items:
            indent = "  " * item.get('depth', 0)
            label = item.get('label', '')
            is_total = item.get('is_total', False)

            if is_total:
                label_cell = Text(f"{indent}{label}", style=styles["row"]["total"])
            else:
                label_cell = Text(f"{indent}{label}", style=styles["row"]["item"])

            values = item.get('values', {})
            if not ttm_periods:
                value = item.get('value')
                values = {"TTM": value}
                period_keys = ["TTM"]
            else:
                period_keys = ttm_periods

            row = [label_cell]
            for period in period_keys:
                value = values.get(period)
                if value is None:
                    row.append(Text("", style=styles["value"]["empty"]))
                    continue

                abs_value = abs(value)
                if abs_value >= 1e9:
                    value_str = f"${value / 1e9:,.1f}B"
                elif abs_value >= 1e6:
                    value_str = f"${value / 1e6:,.1f}M"
                else:
                    value_str = f"${value:,.0f}"

                value_style = styles["value"]["negative"] if value < 0 else styles["value"]["positive"]
                if is_total:
                    total_style = styles["value"]["total"]
                    value_style = f"{total_style} {value_style}"
                row.append(Text(value_str, style=value_style))

            stmt_table.add_row(*row)

        content = Group(Padding("", (1, 0, 0, 0)), stmt_table)

        return Panel(
            content,
            title=title,
            title_align="left",
            subtitle=footer,
            subtitle_align="left",
            border_style=styles["structure"]["border"],
            box=box.SIMPLE,
            padding=(0, 1),
            expand=False,
        )

    def __repr__(self):
        """String representation."""
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())


class TTMStatementBuilder:
    """
    Builds TTM statements from EntityFacts.

    Creates full financial statements (Income Statement, Cash Flow Statement)
    with TTM values calculated for each line item.
    """

    def __init__(self, entity_facts):
        """
        Initialize with EntityFacts instance.

        Args:
            entity_facts: EntityFacts object containing company financial data
        """
        self.facts = entity_facts

    def _build_statement(
        self,
        statement_method: Callable,
        statement_type: str,
        as_of: Optional[date] = None
    ) -> TTMStatement:
        """
        Internal helper to build shared TTM statement logic.
        
        Args:
            statement_method: Bound method to get multi-period statement (e.g. self.facts.income_statement)
            statement_type: Type label for the TTM statement
            as_of: TTM calculation date
            
        Returns:
            Constructed TTMStatement
        """
        # Get multi-period statement to get structure
        multi_period = statement_method(periods=8, annual=False)

        # Calculate rolling TTM for each concept
        ttm_items = []
        base_periods = None
        base_period_labels = None

        def _is_quarterly_periods(periods: List[Tuple[int, str]]) -> bool:
            return periods and all(p in {"Q1", "Q2", "Q3", "Q4"} for _, p in periods)

        def _get_concept_facts(concept: str) -> Optional[List[FinancialFact]]:
            fact_index = getattr(self.facts, "_fact_index", {}).get("by_concept", {})
            concept_facts = fact_index.get(concept)
            if not concept_facts:
                if ":" in concept:
                    local_name = concept.split(":", 1)[1]
                    concept_facts = fact_index.get(local_name)
                else:
                    concept_facts = fact_index.get(f"us-gaap:{concept}")
            return concept_facts

        def _is_eps_concept(concept: str) -> bool:
            return "earningspershare" in concept.lower()

        def _trend_for_eps(eps_concept: str, max_periods: int = 8) -> Optional[pd.DataFrame]:
            net_income_concepts = [
                "NetIncomeLoss",
                "NetIncomeLossAvailableToCommonStockholdersBasic",
            ]
            shares_basic_concepts = [
                "WeightedAverageNumberOfSharesOutstandingBasic",
                "WeightedAverageNumberOfSharesOutstandingBasicAndDiluted",
            ]
            shares_diluted_concepts = [
                "WeightedAverageNumberOfDilutedSharesOutstanding",
                "WeightedAverageNumberOfSharesOutstandingDiluted",
            ]

            net_income_facts = None
            for concept in net_income_concepts:
                net_income_facts = _get_concept_facts(concept)
                if net_income_facts:
                    break

            if not net_income_facts:
                return None

            is_diluted = "diluted" in eps_concept.lower()
            shares_facts = None
            share_candidates = shares_diluted_concepts if is_diluted else shares_basic_concepts
            for concept in share_candidates:
                shares_facts = _get_concept_facts(concept)
                if shares_facts:
                    break

            if not shares_facts:
                return None

            ni_calc = TTMCalculator(net_income_facts)
            ni_quarters = sorted(ni_calc._filter_quarterly_facts(), key=lambda f: f.period_end)
            if len(ni_quarters) < 4:
                return None

            shares_calc = TTMCalculator(shares_facts)
            share_quarters = shares_calc._filter_by_duration(DurationBucket.QUARTER)
            if not share_quarters:
                return None

            shares_by_end = {}
            for fact in share_quarters:
                key = fact.period_end
                if key not in shares_by_end or (
                    fact.filing_date and shares_by_end[key].filing_date and fact.filing_date > shares_by_end[key].filing_date
                ):
                    shares_by_end[key] = fact

            share_annual = shares_calc._filter_by_duration(DurationBucket.ANNUAL)
            shares_by_end_annual = {}
            for fact in share_annual:
                key = fact.period_end
                if key not in shares_by_end_annual or (
                    fact.filing_date and shares_by_end_annual[key].filing_date and fact.filing_date > shares_by_end_annual[key].filing_date
                ):
                    shares_by_end_annual[key] = fact

            rows = []
            for i in range(3, len(ni_quarters)):
                window = ni_quarters[i - 3:i + 1]
                window_ends = [q.period_end for q in window]
                window_shares = []
                for end in window_ends:
                    share_fact = shares_by_end.get(end) or shares_by_end_annual.get(end)
                    if not share_fact or share_fact.numeric_value is None:
                        window_shares = []
                        break
                    window_shares.append(share_fact.numeric_value)

                if not window_shares:
                    continue

                ttm_income = sum(q.numeric_value for q in window if q.numeric_value is not None)
                avg_shares = sum(window_shares) / len(window_shares)
                if avg_shares == 0:
                    continue

                as_of_fact = window[-1]
                rows.append({
                    "as_of_quarter": f"{as_of_fact.fiscal_period} {as_of_fact.fiscal_year}",
                    "ttm_value": ttm_income / avg_shares,
                    "fiscal_year": as_of_fact.fiscal_year,
                    "fiscal_period": as_of_fact.fiscal_period,
                    "as_of_date": as_of_fact.period_end,
                })

            if not rows:
                return None

            trend = pd.DataFrame(rows)
            trend = trend.iloc[::-1].reset_index(drop=True)
            if as_of:
                trend = trend[trend["as_of_date"] <= as_of].reset_index(drop=True)
            if trend.empty:
                return None
            trend["display_quarter"] = trend.apply(
                lambda row: f"{row['fiscal_period']} {row['as_of_date'].year}", axis=1
            )
            return trend.head(max_periods)

        def _trend_for_concept(concept: str, max_periods: int = 8) -> Optional[pd.DataFrame]:
            if _is_eps_concept(concept):
                return _trend_for_eps(concept, max_periods=max_periods)
            concept_facts = _get_concept_facts(concept)
            if not concept_facts:
                return None
            calc = TTMCalculator(concept_facts)
            trend = calc.calculate_ttm_trend(periods=max_periods)
            if as_of:
                trend = trend[trend["as_of_date"] <= as_of].reset_index(drop=True)
            if trend.empty:
                return None
            trend["display_quarter"] = trend.apply(
                lambda row: f"{row['fiscal_period']} {row['as_of_date'].year}", axis=1
            )
            return trend.head(max_periods)

        preferred_concepts = [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "NetIncomeLoss",
        ]

        base_trend = None
        for concept in preferred_concepts:
            trend = _trend_for_concept(concept)
            if trend is None:
                continue
            candidate_periods = [
                (int(row["fiscal_year"]), str(row["fiscal_period"])) for _, row in trend.iterrows()
            ]
            if not _is_quarterly_periods(candidate_periods):
                continue
            if base_trend is None or trend["as_of_date"].iloc[0] > base_trend["as_of_date"].iloc[0]:
                base_trend = trend

        if base_trend is None:
            for item, _, _ in multi_period.iter_hierarchy():
                trend = _trend_for_concept(item.concept)
                if trend is None:
                    continue
                candidate_periods = [
                    (int(row["fiscal_year"]), str(row["fiscal_period"])) for _, row in trend.iterrows()
                ]
                if not _is_quarterly_periods(candidate_periods):
                    continue
                if base_trend is None or trend["as_of_date"].iloc[0] > base_trend["as_of_date"].iloc[0]:
                    base_trend = trend

        if base_trend is not None:
            base_period_labels = base_trend["display_quarter"].tolist()
            base_periods = [
                (int(row["as_of_date"].year), str(row["fiscal_period"])) for _, row in base_trend.iterrows()
            ]

        # Use iter_hierarchy to traverse all nested items, not just the root level
        for item, depth, _ in multi_period.iter_hierarchy():
            concept = item.concept
            label = item.label

            try:
                trend = _trend_for_concept(concept)
                if trend is None:
                    continue

                period_values = {
                    row["display_quarter"]: row["ttm_value"] for _, row in trend.iterrows()
                }

                if base_period_labels:
                    values = {p: period_values.get(p) for p in base_period_labels}
                else:
                    values = period_values
                    base_period_labels = list(period_values.keys())

                if not any(v is not None for v in values.values()):
                    continue

                ttm_items.append({
                    'label': label,
                    'values': values,
                    'concept': concept,
                    'depth': depth,
                    'is_total': getattr(item, 'is_total', False)
                })
            except (ValueError, KeyError, AttributeError, IndexError, TypeError):
                # Concept doesn't have quarterly data or TTM calculation failed
                # Skip this line item
                continue

        return TTMStatement(
            statement_type=statement_type,
            as_of_date=as_of or date.today(),
            items=ttm_items,
            company_name=self.facts.name,
            cik=str(self.facts.cik),
            periods=base_periods
        )

    def build_income_statement(
        self,
        as_of: Optional[date] = None
    ) -> TTMStatement:
        """
        Build TTM income statement.

        Creates a complete income statement using TTM values for each
        line item. Useful for comparing to annual 10-K statements.

        Args:
            as_of: Calculate TTM as of this date (None = most recent)

        Returns:
            TTMStatement with all income statement line items
        """
        return self._build_statement(
            self.facts.income_statement,
            'IncomeStatement',
            as_of
        )

    def build_cashflow_statement(
        self,
        as_of: Optional[date] = None
    ) -> TTMStatement:
        """
        Build TTM cash flow statement.

        Args:
            as_of: Calculate TTM as of this date (None = most recent)

        Returns:
            TTMStatement with all cash flow statement line items
        """
        return self._build_statement(
            self.facts.cash_flow,
            'CashFlowStatement',
            as_of
        )

# -----------------------------------------------------------------------------
# Stock Split Adjustment Utilities
# -----------------------------------------------------------------------------

from typing import Any, Dict
from dataclasses import replace

def detect_splits(facts: List[FinancialFact]) -> List[Dict[str, Any]]:
    """
    Detect stock splits from facts.
    
    Identifies 'StockSplitConversionRatio' facts and filters for valid
    split events (rejecting filing lags and long-duration aggregations).
    """
    split_facts = [f for f in facts if 'StockSplitConversionRatio' in f.concept]
    splits = []
    seen_splits = set()
    
    for f in split_facts:
        # Normalize: Ratio > 1 implies forward split (e.g. 10). Adjust by dividing older values.
        if f.numeric_value is not None and f.numeric_value > 0 and f.period_end:
            # Deduplicate based on Year and Ratio to avoid applying the same split multiple times
            split_key = (f.period_end.year, f.numeric_value)

            # Filter out "historical echo" facts (e.g. 2023 10-K reporting a 2020 split)
            if f.filing_date:
                lag = (f.filing_date - f.period_end).days
                if lag > 280:
                    continue

            # Accept Instant facts OR short-duration facts (<=31 days)
            # Instant: period_start is None (true event date)
            # Short duration: Split event reported for the month (e.g., NVDA May 2024 = 30 days)
            # Reject long durations: Comparative quarters/years (90+ days)
            if f.period_start is not None:
                duration_days = (f.period_end - f.period_start).days
                if duration_days > 31:  # Reject quarterly/annual comparative periods
                    continue

            if split_key in seen_splits:
                continue
            seen_splits.add(split_key)

            splits.append({
                'date': f.period_end,
                'ratio': f.numeric_value
            })
    splits.sort(key=lambda s: s['date'])
    return splits

def apply_split_adjustments(facts: List[FinancialFact], splits: List[Dict[str, Any]]) -> List[FinancialFact]:
    """
    Apply retrospective split adjustments to per-share and share-count facts.
    
    Adjusts:
    - Per-share metrics (EPS, Dividend/Share): Divided by cumulative ratio
    - Share counts (Shares Outstanding): Multiplied by cumulative ratio
    """
    adjusted_facts = []
    for f in facts:
        if not f.unit or f.numeric_value is None:
            adjusted_facts.append(f)
            continue

        unit_lower = str(f.unit).lower()
        concept_lower = f.concept.lower()

        # Identify adjustables
        is_per_share = '/share' in unit_lower or 'earningspershare' in concept_lower
        is_shares = 'shares' in unit_lower and not is_per_share

        if not (is_per_share or is_shares):
            adjusted_facts.append(f)
            continue

        # Calculate cumulative ratio
        # Apply all splits that occurred AFTER this fact's period_end
        cum_ratio = 1.0
        for s in splits:
            if s['date'] > f.period_end:
                # Check if finding is NOT restated (filing date < split)
                if not f.filing_date or f.filing_date <= s['date']:
                    cum_ratio *= s['ratio']

        if cum_ratio == 1.0:
            adjusted_facts.append(f)
            continue

        # Apply adjustment
        if is_per_share:
            new_val = f.numeric_value / cum_ratio
        else: # is_shares
            new_val = f.numeric_value * cum_ratio

        # Clone and replace
        # Note: We depend on FinancialFact being a dataclass or having replace method
        try:
            new_f = replace(f, 
                            value=new_val, 
                            numeric_value=new_val, 
                            calculation_context=f"split_adj_ratio_{cum_ratio:.2f}")
            adjusted_facts.append(new_f)
        except Exception:
            # Fallback if replace doesn't work (though it should for dataclass)
            adjusted_facts.append(f)

    return adjusted_facts

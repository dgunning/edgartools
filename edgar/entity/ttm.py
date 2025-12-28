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
from typing import List, Optional, Tuple

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

        Example:
            >>> # Company files: Q1 ($100B), YTD_6M ($220B), YTD_9M ($350B), FY ($480B)
            >>> quarters = calculator._quarterize_facts()
            >>> # Returns: Q1 ($100B), Q2 ($120B), Q3 ($130B), Q4 ($130B)
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

        # 3. Derive Q2 from YTD_6M - Q1
        for ytd6 in ytd_6m:
            # Find Q1 that ended before this YTD_6M
            q1 = self._find_prior_quarter(quarters, before=ytd6.period_end)
            if q1:
                q2_value = ytd6.numeric_value - q1.numeric_value
                if q2_value < 0:
                    log.debug(f"Negative Q2 value detected: ${q2_value/1e9:.2f}B for {ytd6.concept}. "
                               f"Passing value (data quality/adjustment issue)")
                
                q2_fact = self._create_derived_quarter(
                    ytd6, q2_value, "derived_q2_ytd6_minus_q1", target_period="Q2"
                )
                discrete_quarters.append(q2_fact)
                log.debug(f"Derived Q2 from YTD_6M: ${q2_value/1e9:.2f}B "
                         f"(YTD_6M ${ytd6.numeric_value/1e9:.2f}B - Q1 ${q1.numeric_value/1e9:.2f}B)")

        # 4. Derive Q3 from YTD_9M - YTD_6M
        for ytd9 in ytd_9m:
            ytd6 = self._find_prior_ytd6(ytd_6m, before=ytd9.period_end)
            if ytd6:
                q3_value = ytd9.numeric_value - ytd6.numeric_value
                if q3_value < 0:
                    log.debug(f"Negative Q3 value detected: ${q3_value/1e9:.2f}B for {ytd9.concept}. "
                               f"Passing value (data quality/adjustment issue)")
                
                q3_fact = self._create_derived_quarter(
                    ytd9, q3_value, "derived_q3_ytd9_minus_ytd6", target_period="Q3"
                )
                discrete_quarters.append(q3_fact)
                log.debug(f"Derived Q3 from YTD_9M: ${q3_value/1e9:.2f}B "
                         f"(YTD_9M ${ytd9.numeric_value/1e9:.2f}B - YTD_6M ${ytd6.numeric_value/1e9:.2f}B)")

        # 5. Derive Q4 from FY - YTD_9M
        for fy in annual:
            # Match YTD_9M with same period_start (same fiscal year)
            ytd9 = self._find_matching_ytd9(
                ytd_9m,
                period_start=fy.period_start,
                before=fy.period_end
            )
            if ytd9:
                q4_value = fy.numeric_value - ytd9.numeric_value
                if q4_value < 0:
                    log.debug(f"Negative Q4 value detected: ${q4_value/1e9:.2f}B for {fy.concept}. "
                               f"Passing value (data quality/adjustment issue)")
                
                q4_fact = self._create_derived_quarter(
                    fy, q4_value, "derived_q4_fy_minus_ytd9", target_period="Q4"
                )
                discrete_quarters.append(q4_fact)
                log.debug(f"Derived Q4 from FY: ${q4_value/1e9:.2f}B "
                         f"(FY ${fy.numeric_value/1e9:.2f}B - YTD_9M ${ytd9.numeric_value/1e9:.2f}B)")

        # 6. Deduplicate by period_end (keep latest filing)
        dedup_quarters = self._deduplicate_by_period_end(discrete_quarters)
        log.debug(f"Quarterization complete: {len(dedup_quarters)} discrete quarters "
                 f"({len(quarters)} reported + {len(dedup_quarters) - len(quarters)} derived)")

        return dedup_quarters

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
        target_period: Optional[str] = None
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
            period_start=source_fact.period_start,
            period_end=source_fact.period_end,
            filing_date=source_fact.filing_date,
            form_type=source_fact.form_type,
            accession=source_fact.accession,
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

    def _find_matching_annual_fact(
        self,
        fiscal_year: int,
        annual_facts: Optional[List[FinancialFact]] = None
    ) -> Optional[FinancialFact]:
        """
        Find annual (FY) fact for a specific fiscal year.

        Args:
            fiscal_year: The fiscal year to find
            annual_facts: Pre-filtered annual facts (optional, will filter if not provided)

        Returns:
            FinancialFact with fiscal_period='FY' for the year, or None if not found
        """
        if annual_facts is None:
            annual_facts = self._filter_annual_facts()

        # Find FY fact for this fiscal year
        for fact in annual_facts:
            if fact.fiscal_year == fiscal_year and fact.fiscal_period == 'FY':
                return fact

        return None

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
    items: List[dict]  # [{label, value, periods, concept, depth, is_total}, ...]
    company_name: str
    cik: str

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert statement to pandas DataFrame.

        Returns:
            DataFrame with columns: label, ttm_value, depth, is_total
        """
        return pd.DataFrame([
            {
                'label': item['label'],
                'ttm_value': item['value'],
                'depth': item.get('depth', 0),
                'is_total': item.get('is_total', False)
            }
            for item in self.items
        ])

    def __rich__(self):
        """Rich console representation."""
        from rich.table import Table
        from rich import box

        table = Table(
            title=f"{self.statement_type} (TTM) - {self.company_name}",
            box=box.ROUNDED,
            show_header=True,
            title_style="bold cyan"
        )

        table.add_column("Item", style="cyan", no_wrap=False)
        table.add_column("TTM Value", justify="right", style="green")
        table.add_column("Periods", style="dim")

        for item in self.items:
            # Format periods string
            periods_str = ", ".join(
                f"{fp} {fy}" for fy, fp in item['periods']
            )

            # Format value with appropriate scaling
            value = item['value']
            if abs(value) >= 1e9:
                value_str = f"${value / 1e9:,.1f}B"
            elif abs(value) >= 1e6:
                value_str = f"${value / 1e6:,.1f}M"
            else:
                value_str = f"${value:,.0f}"

            # Add indentation based on depth
            indent = "  " * item.get('depth', 0)
            label = indent + item['label']

            table.add_row(label, value_str, periods_str)

        return table

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

        Example:
            >>> builder = TTMStatementBuilder(facts)
            >>> stmt = builder.build_income_statement()
            >>> print(stmt)
            # Rich formatted table output
        """
        # Get multi-period income statement to get structure
        multi_period = self.facts.income_statement(periods=8, annual=False)

        # Calculate TTM for each concept
        ttm_items = []

        for item in multi_period.items:
            concept = item.concept
            label = item.label

            try:
                # Calculate TTM for this concept
                ttm = self.facts.get_ttm(concept, as_of=as_of)

                ttm_items.append({
                    'label': label,
                    'value': ttm.value,
                    'periods': ttm.periods,
                    'concept': concept,
                    'depth': getattr(item, 'depth', 0),
                    'is_total': getattr(item, 'is_total', False)
                })
            except (ValueError, KeyError, AttributeError):
                # Concept doesn't have quarterly data or TTM calculation failed
                # Skip this line item
                continue

        return TTMStatement(
            statement_type='IncomeStatement',
            as_of_date=as_of or date.today(),
            items=ttm_items,
            company_name=self.facts.name,
            cik=str(self.facts.cik)
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
        # Get multi-period cash flow statement
        multi_period = self.facts.cash_flow(periods=8, annual=False)

        # Calculate TTM for each concept
        ttm_items = []

        for item in multi_period.items:
            concept = item.concept
            label = item.label

            try:
                ttm = self.facts.get_ttm(concept, as_of=as_of)

                ttm_items.append({
                    'label': label,
                    'value': ttm.value,
                    'periods': ttm.periods,
                    'concept': concept,
                    'depth': getattr(item, 'depth', 0),
                    'is_total': getattr(item, 'is_total', False)
                })
            except (ValueError, KeyError, AttributeError):
                continue

        return TTMStatement(
            statement_type='CashFlowStatement',
            as_of_date=as_of or date.today(),
            items=ttm_items,
            company_name=self.facts.name,
            cik=str(self.facts.cik)
        )

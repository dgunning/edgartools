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
        the as_of date and sums their values.

        Args:
            as_of: Date to calculate TTM as of (uses most recent if None)

        Returns:
            TTMMetric with value and metadata

        Raises:
            ValueError: If insufficient data (<4 quarters available)

        Example:
            >>> ttm = calculator.calculate_ttm(as_of=date(2024, 3, 30))
            >>> print(ttm.periods)
            [(2023, 'Q3'), (2023, 'Q4'), (2024, 'Q1'), (2024, 'Q2')]
        """
        # 1. Filter to quarterly facts (duration ~90 days)
        quarterly = self._filter_quarterly_facts()

        # 2. Select 4 consecutive quarters ending on/before as_of
        ttm_quarters = self._select_ttm_window(quarterly, as_of)

        # 3. Validate (minimum 4 quarters required)
        if len(ttm_quarters) < 4:
            raise ValueError(
                f"Insufficient quarterly data: found {len(ttm_quarters)} quarters, "
                f"need at least 4 for TTM calculation. "
                f"Consider using annual data instead."
            )

        # 4. Check for gaps in quarterly data
        has_gaps = self._check_for_gaps(ttm_quarters)

        # 5. Sum quarterly values to get TTM
        ttm_value = sum(q.numeric_value for q in ttm_quarters)

        # 6. Generate warning if data quality issues exist
        warning = self._generate_warning(quarterly, ttm_quarters)

        # 7. Build and return result
        return TTMMetric(
            concept=ttm_quarters[0].concept,
            label=ttm_quarters[0].label,
            value=ttm_value,
            unit=ttm_quarters[0].unit,
            as_of_date=ttm_quarters[-1].period_end,  # Most recent quarter
            periods=[(q.fiscal_year, q.fiscal_period) for q in ttm_quarters],
            period_facts=ttm_quarters,
            has_gaps=has_gaps,
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

        # 3. Calculate minimum quarters needed
        # To get 'periods' TTM values, need periods + 3 quarters
        # (first TTM uses quarters 0-3, last TTM uses quarters n-3 to n)
        min_quarters = periods + 3

        if len(sorted_facts) < min_quarters:
            raise ValueError(
                f"Insufficient data for TTM trend: need {min_quarters} quarters "
                f"to calculate {periods} TTM values, found {len(sorted_facts)} quarters"
            )

        # 4. Calculate TTM for each rolling window
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
                'yoy_growth': yoy_growth,
                'periods_included': [
                    (q.fiscal_year, q.fiscal_period) for q in ttm_window
                ]
            })

            # Stop when we have enough periods
            if len(results) >= periods:
                break

        # 5. Convert to DataFrame
        df = pd.DataFrame(results)

        # Reverse so most recent quarter is first
        df = df.iloc[::-1].reset_index(drop=True)

        return df

    def _filter_quarterly_facts(self) -> List[FinancialFact]:
        """
        Filter to quarterly duration facts (~90 days).

        Returns:
            List of facts with duration between 80-100 days
        """
        quarterly = []

        for fact in self.facts:
            # Skip non-duration facts (instant/point-in-time)
            if fact.period_type != 'duration':
                continue

            # Skip facts without start/end dates
            if not fact.period_start or not fact.period_end:
                continue

            # Calculate duration in days
            duration_days = (fact.period_end - fact.period_start).days

            # Quarterly periods are typically 80-100 days
            # (allows for calendar variations: 89-92 days common)
            if 80 <= duration_days <= 100:
                quarterly.append(fact)

        return quarterly

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
        ttm_quarters: List[FinancialFact]
    ) -> Optional[str]:
        """
        Generate warning message if data quality issues exist.

        Args:
            all_quarterly: All available quarterly facts
            ttm_quarters: 4 quarters used in TTM calculation

        Returns:
            Warning message string, or None if no issues
        """
        warnings = []

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

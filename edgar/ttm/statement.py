"""TTM financial statement classes.

Provides TTMStatement and TTMStatementBuilder for creating
trailing twelve month financial statements.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, List, Optional, Tuple

import pandas as pd

from edgar.entity.models import FinancialFact

# Matches the per-share detection used by the entity statement renderer
# (enhanced_statement.py), so both surfaces agree on what is a per-share amount.
from edgar.entity.unit_handling import (
    format_share_count,
    is_per_share_label,
    is_share_count_label,
)
from edgar.ttm.calculator import (
    EPS_NUMERATOR_CONCEPTS,
    DurationBucket,
    TTMCalculator,
    numerator_agrees_within,
)


def _is_per_share_item(item: dict) -> bool:
    """True when a statement line item holds a per-share amount."""
    return is_per_share_label(item.get('concept', ''), item.get('label', ''))


def _is_share_count_item(item: dict) -> bool:
    """True when a statement line item holds a number of shares."""
    return is_share_count_label(item.get('concept', ''), item.get('label', ''))


def _period_days(start: date, end: date) -> int:
    """Length of a duration period in days, both ends included."""
    return (end - start).days + 1


def _quarter_share_count(quarter: FinancialFact, quarter_counts: dict, annual_counts: dict,
                         cumulative_counts: Optional[dict] = None) -> Optional[float]:
    """Weighted-average share count for one quarter of a TTM window.

    A filed three-month count is used as is. A fiscal-year count is never put in
    a quarter's place: when the quarter closes a fiscal year and has no
    three-month count (10-Ks rarely tag one), its count is solved from the
    fiscal-year count and the year's other three quarters, weighting each period
    by its days, which is how the year's weighted average is built (ASC
    260-10-45-10). Failing that, it is solved the same way from the filer's
    cumulative counts: the period through the quarter's end less the period
    through the day before it starts (Q4 = FY - 9M, Q3 = 9M - 6M). Returns None
    when neither is possible (GH #1691).
    """
    filed = quarter_counts.get(quarter.period_end)
    if filed is not None:
        return filed.numeric_value
    if quarter.period_start is None:
        return None

    year = annual_counts.get(quarter.period_end)
    if year is not None and year.period_start is not None:
        others = [f for end, f in quarter_counts.items()
                  if year.period_start < end < quarter.period_start and f.period_start
                  and f.period_start >= year.period_start]
        year_days = _period_days(year.period_start, year.period_end)
        quarter_days = _period_days(quarter.period_start, quarter.period_end)
        other_days = sum(_period_days(f.period_start, f.period_end) for f in others)
        if len(others) == 3 and abs(other_days + quarter_days - year_days) <= 3:
            solved = (year.numeric_value * year_days
                      - sum(f.numeric_value * _period_days(f.period_start, f.period_end) for f in others)) / quarter_days
            if solved > 0:
                return solved

    return _solve_from_cumulative(quarter, cumulative_counts or {})


def _solve_from_cumulative(quarter: FinancialFact, cumulative_counts: dict) -> Optional[float]:
    """A quarter's count from two cumulative counts sharing a start (GH #1691).

    ``cumulative_counts`` maps (period_start, period_end) to a share fact. The
    weighted average through the quarter's end, times its days, less the one
    through the day before the quarter starts, is the quarter's share-days.
    """
    prior_end = quarter.period_start - timedelta(days=1)
    quarter_days = _period_days(quarter.period_start, quarter.period_end)
    for (start, end), through in cumulative_counts.items():
        if end != quarter.period_end or start >= quarter.period_start:
            continue
        before = cumulative_counts.get((start, prior_end))
        if before is None:
            continue
        solved = (through.numeric_value * _period_days(start, end)
                  - before.numeric_value * _period_days(start, prior_end)) / quarter_days
        if solved > 0:
            return solved
    return None


def _window_share_count(window: List[FinancialFact], quarter_counts: dict, annual_counts: dict,
                        cumulative_counts: Optional[dict] = None) -> Optional[float]:
    """Weighted-average share count over a four-quarter TTM window (GH #1691).

    A window that is a fiscal year uses that year's filed count, so its EPS is
    the filed annual EPS. Any other window weights its quarters' counts by their
    days. ``quarter_counts`` and ``annual_counts`` map period_end to a three-month
    and a fiscal-year share fact; ``cumulative_counts`` (see _share_count_maps)
    lets a quarter with no count of its own be solved. Returns None when a
    quarter has no count.
    """
    start, end = window[0].period_start, window[-1].period_end
    year = annual_counts.get(end)
    if year is not None and year.period_start and start and abs((year.period_start - start).days) <= 7:
        return year.numeric_value

    weighted = 0.0
    total_days = 0
    for quarter in window:
        if quarter.period_start is None:
            return None
        count = _quarter_share_count(quarter, quarter_counts, annual_counts, cumulative_counts)
        if count is None:
            return None
        days = _period_days(quarter.period_start, quarter.period_end)
        weighted += count * days
        total_days += days
    return weighted / total_days if total_days else None


def _numerator_series(facts: List[FinancialFact]) -> dict:
    """One EPS numerator concept's facts, indexed for TTM windows."""
    calc = TTMCalculator(facts)
    annual = {}
    for fact in calc._filter_by_duration(DurationBucket.ANNUAL):
        if fact.numeric_value is None:
            continue
        held = annual.get(fact.period_end)
        if held is None or (fact.filing_date or date.min) > (held.filing_date or date.min):
            annual[fact.period_end] = fact
    return {
        "facts": facts,
        "quarters": {q.period_end: q for q in calc._filter_quarterly_facts() if q.numeric_value is not None},
        "annual": annual,
    }


def _window_numerator(window: List[FinancialFact], series: List[dict]) -> Optional[float]:
    """TTM EPS numerator for one window, from the best numerator concept (GH #1692).

    ``series`` is ordered best first (income available to common stockholders
    before net income). A window that is a fiscal year uses the year's filed
    value, otherwise the four quarters are summed; all from ONE concept. A
    lesser concept stands in only where the filer's facts do not show it
    differing from the better one in this window; otherwise there is no EPS.
    """
    start, end = window[0].period_start, window[-1].period_end
    for rank, candidate in enumerate(series):
        year = candidate["annual"].get(end)
        if year is not None and year.period_start and start and abs((year.period_start - start).days) <= 7:
            value = year.numeric_value
        elif all(q.period_end in candidate["quarters"] for q in window):
            value = sum(candidate["quarters"][q.period_end].numeric_value for q in window)
        else:
            continue
        span_start = start or end
        if all(numerator_agrees_within(better["facts"], candidate["facts"], span_start, end)
               for better in series[:rank]):
            return value
        return None
    return None


@dataclass
class TTMStatement:
    """TTM financial statement with multiple line items.

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
        """Convert statement to pandas DataFrame.

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

    def to_dict(self) -> list[dict]:
        """Convert statement to a list of row dictionaries."""
        return self.to_dataframe().to_dict(orient='records')

    def to_llm_string(self) -> str:
        """Convert statement to a markdown string for LLMs."""
        df = self.to_dataframe()
        return df.to_markdown(index=False) if not df.empty else ""

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
                if _is_per_share_item(item):
                    # Per-share amounts are dollars-and-cents, not magnitudes:
                    # the whole-dollar format below rendered EPS of 20.16 as
                    # "$20" while to_dataframe() kept the precision (GH #910).
                    value_str = f"{value:,.2f}"
                elif _is_share_count_item(item):
                    # A count of shares is not an amount of money; the currency
                    # path below rendered 12.1 billion shares as "$12.1B".
                    value_str = format_share_count(value)
                elif abs_value >= 1e9:
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
    """Builds TTM statements from EntityFacts.

    Creates full financial statements (Income Statement, Cash Flow Statement)
    with TTM values calculated for each line item.
    """

    def __init__(self, entity_facts):
        """Initialize with EntityFacts instance.

        Args:
            entity_facts: EntityFacts object containing company financial data

        """
        self.facts = entity_facts

    def _build_statement(
        self,
        statement_method: Callable,
        statement_type: str,
        as_of: Optional[date] = None,
        max_periods: int = 8
    ) -> TTMStatement:
        """Internal helper to build shared TTM statement logic.

        Args:
            statement_method: Bound method to get multi-period statement (e.g. self.facts.income_statement)
            statement_type: Type label for the TTM statement
            as_of: TTM calculation date

        Returns:
            Constructed TTMStatement

        """
        # Get multi-period statement to get structure
        # We always fetch at least 8 periods to ensure enough quarters are available
        # to calculate a trailing 4-quarter rolling sum for TTM calculation.
        multi_period = statement_method(periods=max(max_periods, 8), annual=False)

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

        def _label_year(row) -> int:
            fy = row.get("fiscal_year")
            return int(fy) if pd.notna(fy) else int(row["as_of_date"].year)

        def _trend_for_eps(eps_concept: str, max_periods: int) -> Optional[pd.DataFrame]:
            shares_basic_concepts = [
                "WeightedAverageNumberOfSharesOutstandingBasic",
                "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
            ]
            shares_diluted_concepts = [
                "WeightedAverageNumberOfDilutedSharesOutstanding",
                "WeightedAverageNumberOfSharesOutstandingDiluted",
                "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
            ]

            is_diluted = "diluted" in eps_concept.lower()
            # Basic EPS divides income available to common stockholders, not net
            # income; the diluted numerator starts from it (GH #1692).
            numerators = []
            for concept in EPS_NUMERATOR_CONCEPTS["diluted" if is_diluted else "basic"]:
                concept_facts = _get_concept_facts(concept)
                if concept_facts:
                    numerators.append((concept, concept_facts))
            if not numerators:
                return None
            # Windows are laid out on net income's quarters (the widest series);
            # each window's numerator is then chosen by _window_numerator.
            net_income_facts = dict(numerators).get("NetIncomeLoss") or numerators[0][1]
            numerator_series = [_numerator_series(f) for _, f in numerators]

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

            # Derive each window's label fiscal year from its period_end rather
            # than the as_of fact's tagged fiscal_year. The SEC tags a quarter
            # re-filed as a comparative with the FILING's fiscal year, so GOOGL's
            # Q2 2025 (period_end 2025-06-30) carries fy=2026 and would be
            # labelled "Q2 2026" — colliding with the real Q2 2026 window and
            # overwriting it in the caller's period dict. calculate_ttm_trend()
            # already does this for every other concept (GH #793); the EPS path
            # did not, which is why only EPS rows were wrong (GH #910).
            from edgar.entity.enhanced_statement import (
                calculate_fiscal_year_for_label,
                detect_fiscal_year_end,
            )
            # Detect FYE from the same fact list the windows are built from;
            # detect_fiscal_year_end takes a list of facts, not an EntityFacts.
            fiscal_year_end_month = detect_fiscal_year_end(net_income_facts)

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
            shares_by_end = {k: f for k, f in shares_by_end.items() if f.numeric_value is not None}
            shares_by_end_annual = {k: f for k, f in shares_by_end_annual.items() if f.numeric_value is not None}
            # Every cumulative count by (start, end), so a quarter with no count
            # of its own can be solved from two of them (GH #1691).
            shares_cumulative = {}
            for bucket in (DurationBucket.QUARTER, DurationBucket.YTD_6M, DurationBucket.YTD_9M, DurationBucket.ANNUAL):
                for fact in shares_calc._filter_by_duration(bucket):
                    if fact.numeric_value is None or fact.period_start is None:
                        continue
                    key = (fact.period_start, fact.period_end)
                    held = shares_cumulative.get(key)
                    if held is None or (fact.filing_date and held.filing_date and fact.filing_date > held.filing_date):
                        shares_cumulative[key] = fact

            rows = []
            for i in range(3, len(ni_quarters)):
                window = ni_quarters[i - 3:i + 1]
                # A fiscal-year count never fills a quarter's slot (GH #1691)
                avg_shares = _window_share_count(window, shares_by_end, shares_by_end_annual, shares_cumulative)
                if not avg_shares:
                    continue

                ttm_income = _window_numerator(window, numerator_series)
                if ttm_income is None:
                    continue

                as_of_fact = window[-1]
                label_fy = calculate_fiscal_year_for_label(
                    as_of_fact.period_end, fiscal_year_end_month
                )
                rows.append({
                    "as_of_quarter": f"{as_of_fact.fiscal_period} {label_fy}",
                    "ttm_value": ttm_income / avg_shares,
                    "fiscal_year": label_fy,
                    "fiscal_period": as_of_fact.fiscal_period,
                    "as_of_date": as_of_fact.period_end,
                    "has_gaps": ni_calc._check_for_gaps(window),
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
                lambda row: f"{row['fiscal_period']} {_label_year(row)}", axis=1
            )
            return trend.head(max_periods)

        def _trend_for_concept(concept: str, max_periods: int) -> Optional[pd.DataFrame]:
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
                lambda row: f"{row['fiscal_period']} {_label_year(row)}", axis=1
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
            trend = _trend_for_concept(concept, max_periods=max_periods)
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
                trend = _trend_for_concept(item.concept, max_periods=max_periods)
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
                (
                    int(row["fiscal_year"]) if pd.notna(row.get("fiscal_year")) else int(row["as_of_date"].year),
                    str(row["fiscal_period"])
                )
                for _, row in base_trend.iterrows()
            ]

        # Use iter_hierarchy to traverse all nested items, not just the root level
        for item, depth, _ in multi_period.iter_hierarchy():
            concept = item.concept
            label = item.label

            try:
                trend = _trend_for_concept(concept, max_periods=max_periods)
                if trend is None:
                    continue

                # trend is ordered most-recent-first. Keep the first window seen
                # for a label: if two windows ever collide on one label again,
                # the current period's value wins rather than being silently
                # overwritten by an older one, which is how GH #910 turned a
                # labelling bug into a plausible-looking wrong number.
                period_values = {}
                for _, row in trend.iterrows():
                    period_label = row["display_quarter"]
                    if period_label in period_values:
                        from edgar.core import log
                        log.debug(
                            "%s: duplicate TTM period label %s (window ending %s ignored)",
                            concept, period_label, row["as_of_date"],
                        )
                        continue
                    # A window whose quarters are not consecutive does not
                    # cover twelve months (a skipped quarter makes it ~15), so
                    # its sum is not a TTM value: leave the cell empty rather
                    # than print it under a TTM column (GH #1694).
                    period_values[period_label] = None if row.get("has_gaps") else row["ttm_value"]

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
            except (ValueError, KeyError) as e:
                # Expected: Concept doesn't have sufficient quarterly data
                from edgar.core import log
                log.debug(f"Skipping {concept}: insufficient data - {e}")
                continue
            except (AttributeError, IndexError, TypeError) as e:
                # Unexpected: May indicate a bug, log at higher level
                from edgar.core import log
                log.warning(f"Unexpected error processing {concept}: {type(e).__name__}: {e}")
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
        as_of: Optional[date] = None,
        max_periods: int = 8
    ) -> TTMStatement:
        """Build TTM income statement.

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
            as_of,
            max_periods=max_periods
        )

    def build_cashflow_statement(
        self,
        as_of: Optional[date] = None,
        max_periods: int = 8
    ) -> TTMStatement:
        """Build TTM cash flow statement.

        Args:
            as_of: Calculate TTM as of this date (None = most recent)

        Returns:
            TTMStatement with all cash flow statement line items

        """
        return self._build_statement(
            self.facts.cash_flow_statement,
            'CashFlowStatement',
            as_of,
            max_periods=max_periods
        )

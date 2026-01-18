"""TTM financial statement classes.

Provides TTMStatement and TTMStatementBuilder for creating
trailing twelve month financial statements.
"""
from dataclasses import dataclass
from datetime import date
from typing import Callable, List, Optional, Tuple

import pandas as pd

from edgar.entity.models import FinancialFact
from edgar.ttm.calculator import DurationBucket, TTMCalculator


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
        as_of: Optional[date] = None
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
            shares_by_year_annual = {}
            for fact in share_annual:
                key = fact.period_end
                if key not in shares_by_end_annual or (
                    fact.filing_date and shares_by_end_annual[key].filing_date and fact.filing_date > shares_by_end_annual[key].filing_date
                ):
                    shares_by_end_annual[key] = fact
                if fact.fiscal_year:
                    existing = shares_by_year_annual.get(fact.fiscal_year)
                    if not existing or (
                        fact.filing_date and existing.filing_date and fact.filing_date > existing.filing_date
                    ):
                        shares_by_year_annual[fact.fiscal_year] = fact

            rows = []
            for i in range(3, len(ni_quarters)):
                window = ni_quarters[i - 3:i + 1]
                window_ends = [q.period_end for q in window]
                window_shares = []
                for quarter in window:
                    end = quarter.period_end
                    share_fact = shares_by_end.get(end) or shares_by_end_annual.get(end)
                    if not share_fact and quarter.fiscal_period == "Q4":
                        share_fact = shares_by_year_annual.get(quarter.fiscal_year)
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
        as_of: Optional[date] = None
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
            as_of
        )

    def build_cashflow_statement(
        self,
        as_of: Optional[date] = None
    ) -> TTMStatement:
        """Build TTM cash flow statement.

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

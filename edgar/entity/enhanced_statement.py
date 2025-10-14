"""
Enhanced financial statement that combines hierarchical structure with multi-period display.

This module provides an enhanced statement class that uses learned mappings
to show multiple periods with proper hierarchical organization.

Note: PD011 violations in this file are false positives - .values refers to
Dict[str, Optional[float]] on MultiPeriodItem objects, not pandas DataFrames.
"""
# ruff: noqa: PD011

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
from rich import box
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.core import log
from edgar.entity.mappings_loader import load_learned_mappings, load_virtual_trees
from edgar.entity.models import FinancialFact

try:
    from edgar.entity.terminal_styles import get_current_scheme
except ImportError:
    # Fallback if terminal_styles not available - use professional scheme
    def get_current_scheme():
        return {
            "abstract_item": "bold blue",
            "total_item": "bold bright_white",
            "regular_item": "",
            "low_confidence_item": "italic",
            "positive_value": "green",
            "negative_value": "red",
            "total_value_prefix": "bold",
            "separator": "blue",
            "company_name": "bold bright_white",
            "statement_type": "bold blue",
            "panel_border": "white",
            "empty_value": "bright_black",
        }
from edgar.richtools import repr_rich


@dataclass
class MultiPeriodStatement:
    """
    A financial statement showing multiple periods with hierarchical structure.

    Combines the best of both worlds:
    - Multiple periods side-by-side (like current pivot tables)
    - Hierarchical organization (from StructuredStatement)
    - Learned concept mappings for better coverage
    """

    statement_type: str
    periods: List[str]  # Period labels like ["Q1 2024", "Q2 2024"]

    # Hierarchical items with multi-period values
    items: List['MultiPeriodItem']

    # Metadata
    company_name: Optional[str] = None
    cik: Optional[str] = None
    canonical_coverage: float = 0.0

    # Display format control
    concise_format: bool = False  # If True, display as $1.0B, if False display as $1,000,000,000

    def __rich__(self):
        """Create a rich representation with multiple periods."""
        # Get color scheme at the start
        colors = get_current_scheme()

        # Statement type mapping
        statement_names = {
            'IncomeStatement': 'Income Statement',
            'BalanceSheet': 'Balance Sheet',
            'CashFlow': 'Cash Flow Statement'
        }

        # Title
        title_parts = []
        if self.company_name:
            title_parts.append((self.company_name, colors["company_name"]))
        else:
            title_parts.append(("Financial Statement", colors["total_item"]))

        title = Text.assemble(*title_parts)

        # Subtitle
        statement_display = statement_names.get(self.statement_type, self.statement_type)
        period_range = f"{self.periods[-1]} to {self.periods[0]}" if len(self.periods) > 1 else self.periods[0] if self.periods else ""
        subtitle = f"{statement_display} • {period_range}"

        # Main table with multiple period columns
        stmt_table = Table(
            box=box.SIMPLE,
            show_header=True,
            padding=(0, 1),
            expand=True
        )

        # Add concept column
        stmt_table.add_column("", style="", ratio=2)

        # Add period columns
        for period in self.periods:
            stmt_table.add_column(period, justify="right", style="bold", ratio=1)

        def add_item_to_table(item: 'MultiPeriodItem', depth: int = 0):
            """Add an item row to the table."""
            indent = "  " * depth

            # Prepare row values
            row = []

            # Concept label
            if item.is_abstract:
                row.append(Text(f"{indent}{item.label}", style=colors["abstract_item"]))
            elif item.is_total:
                row.append(Text(f"{indent}{item.label}", style=colors["total_item"]))
            else:
                # Check if this is a key financial item that should always be prominent
                important_labels = [
                    'Total Revenue', 'Revenue', 'Net Sales', 'Total Net Sales',
                    'Operating Income', 'Operating Income (Loss)', 'Operating Profit',
                    'Net Income', 'Net Income (Loss)', 'Net Earnings',
                    'Gross Profit', 'Gross Margin',
                    'Cost of Revenue', 'Cost of Goods Sold',
                    'Operating Expenses', 'Total Operating Expenses',
                    'Earnings Per Share', 'EPS'
                ]

                is_important = any(label in item.label for label in important_labels)

                # Don't mark important items as low confidence even if score is low
                if is_important:
                    style = colors["total_item"]  # Use bold styling for important items
                    confidence_marker = ""
                else:
                    style = colors["low_confidence_item"] if item.confidence < 0.8 else colors["regular_item"]
                    confidence_marker = " ◦" if item.confidence < 0.8 else ""

                row.append(Text(f"{indent}{item.label}{confidence_marker}", style=style))

            # Period values
            for period in self.periods:
                value_str = item.get_display_value(period, concise_format=self.concise_format)
                if value_str and value_str != "-":
                    # Color code values
                    value = item.values.get(period)
                    if value and isinstance(value, (int, float)):
                        value_style = colors["negative_value"] if value < 0 else colors["positive_value"]
                    else:
                        value_style = ""

                    if item.is_total:
                        # Combine total style with value color if present
                        total_style = colors["total_value_prefix"]
                        if value_style:
                            total_style = f"{total_style} {value_style}"
                        row.append(Text(value_str, style=total_style))
                    else:
                        row.append(Text(value_str, style=value_style))
                else:
                    row.append("")

            stmt_table.add_row(*row)

            # Add separator line after totals
            if item.is_total and depth == 0:
                separator_row = [Text("─" * 40, style=colors["separator"])]
                for _ in self.periods:
                    separator_row.append(Text("─" * 15, style=colors["separator"]))
                stmt_table.add_row(*separator_row)

            # Add children
            for child in item.children:
                if depth < 3:
                    add_item_to_table(child, depth + 1)

        # Add all items
        for item in self.items:
            add_item_to_table(item)


        # Combine content
        content_parts = [
            Padding("", (1, 0, 0, 0)),
            stmt_table
        ]

        content = Group(*content_parts)

        return Panel(
            content,
            title=title,
            subtitle=subtitle,
            border_style=colors["panel_border"],
            expand=True
        )

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the multi-period statement to a DataFrame.

        Returns:
            DataFrame with concepts as rows and periods as columns
        """
        data = []

        def collect_items(item: 'MultiPeriodItem', depth: int = 0):
            """Recursively collect items into flat structure."""
            # Create row data
            row = {
                'concept': item.concept,
                'label': item.label,
                'depth': depth,
                'is_abstract': item.is_abstract,
                'is_total': item.is_total,
                'section': item.section,
                'confidence': item.confidence
            }

            # Add period values
            for period in self.periods:
                row[period] = item.values.get(period)

            data.append(row)

            # Process children
            for child in item.children:
                collect_items(child, depth + 1)

        # Collect all items
        for item in self.items:
            collect_items(item)

        # Create DataFrame
        df = pd.DataFrame(data)

        # Set concept as index
        if not df.empty:
            df = df.set_index('concept')

        return df

    def to_llm_context(self, 
                       include_metadata: bool = True,
                       include_hierarchy: bool = False,
                       flatten_values: bool = True) -> Dict[str, Any]:
        """
        Generate structured context optimized for LLM consumption.

        This method creates a clean, structured representation of financial data
        that LLMs can easily parse and reason about, avoiding complex hierarchies
        and focusing on key-value pairs with clear semantics.

        Args:
            include_metadata: Include metadata about data quality and coverage
            include_hierarchy: Include parent-child relationships (default False for simplicity)
            flatten_values: Flatten multi-period values into period-prefixed keys (default True)

        Returns:
            Dictionary with structured financial data for LLM analysis

        Example Output:
            {
                "company": "Apple Inc.",
                "statement_type": "income_statement",
                "periods": ["FY 2024", "FY 2023"],
                "currency": "USD",
                "scale": "actual",
                "data": {
                    "revenue_fy2024": 391035000000,
                    "revenue_fy2023": 383285000000,
                    "net_income_fy2024": 93736000000,
                    ...
                },
                "key_metrics": {
                    "revenue_growth": 0.02,
                    "profit_margin_fy2024": 0.24,
                    ...
                },
                "metadata": {
                    "total_concepts": 173,
                    "coverage_ratio": 0.85,
                    ...
                }
            }
        """
        from datetime import datetime

        context = {
            "company": self.company_name or "Unknown",
            "cik": self.cik or "Unknown",
            "statement_type": self._get_statement_type_name(),
            "periods": self.periods,
            "currency": "USD",  # Default, could be enhanced
            "scale": "actual",  # Values are in actual amounts
            "generated_at": datetime.now().isoformat()
        }

        # Prepare main data section
        data = {}
        hierarchical_data = [] if include_hierarchy else None

        def process_item(item: 'MultiPeriodItem', parent_path: str = ""):
            """Process an item and its children."""
            # Skip abstract items unless they have values
            if item.is_abstract and not any(v is not None for v in item.values.values()):
                # Still process children
                for child in item.children:
                    process_item(child, parent_path)
                return

            # Create a clean concept key (lowercase, underscored)
            concept_key = self._create_llm_key(item.concept)

            if flatten_values:
                # Create period-specific keys
                for period in self.periods:
                    value = item.values.get(period)
                    if value is not None:
                        # Create period suffix
                        period_key = period.lower().replace(' ', '_').replace('-', '_')
                        full_key = f"{concept_key}_{period_key}"
                        data[full_key] = value

                        # Also store with label for better readability
                        label_key = f"{self._create_llm_key(item.label)}_{period_key}"
                        if label_key != full_key and label_key not in data:
                            data[label_key] = value
            else:
                # Store as nested structure
                if any(v is not None for v in item.values.values()):
                    data[concept_key] = {
                        "label": item.label,
                        "values": {p: v for p, v in item.values.items() if v is not None},
                        "is_total": item.is_total
                    }

            # Add to hierarchical data if requested
            if include_hierarchy and hierarchical_data is not None:
                hierarchical_data.append({
                    "concept": item.concept,
                    "label": item.label,
                    "parent": parent_path or None,
                    "depth": item.depth,
                    "is_total": item.is_total,
                    "values": {p: v for p, v in item.values.items() if v is not None}
                })

            # Process children
            current_path = f"{parent_path}/{item.concept}" if parent_path else item.concept
            for child in item.children:
                process_item(child, current_path)

        # Process all top-level items
        for item in self.items:
            process_item(item)

        context["data"] = data

        if include_hierarchy and hierarchical_data:
            context["hierarchy"] = hierarchical_data

        # Calculate key metrics and ratios
        key_metrics = self._calculate_key_metrics(data)
        if key_metrics:
            context["key_metrics"] = key_metrics

        # Add metadata if requested
        if include_metadata:
            metadata = {
                "total_concepts": len([i for i in self._flatten_items() if not i.is_abstract]),
                "total_values": sum(1 for v in data.values() if v is not None),
                "periods_count": len(self.periods),
                "has_comparisons": len(self.periods) > 1,
                "coverage_ratio": self.coverage if hasattr(self, 'coverage') else None
            }

            # Add data quality indicators
            quality_indicators = []
            if metadata["total_concepts"] > 100:
                quality_indicators.append("comprehensive")
            elif metadata["total_concepts"] > 50:
                quality_indicators.append("detailed")
            else:
                quality_indicators.append("basic")

            if metadata["has_comparisons"]:
                quality_indicators.append("comparable")

            metadata["quality_indicators"] = quality_indicators
            context["metadata"] = metadata

        return context

    def _get_statement_type_name(self) -> str:
        """Get clean statement type name for LLM context."""
        type_map = {
            "IncomeStatement": "income_statement",
            "BalanceSheet": "balance_sheet", 
            "CashFlow": "cash_flow",
            "CashFlowStatement": "cash_flow"
        }
        return type_map.get(self.statement_type, self.statement_type.lower())

    def _create_llm_key(self, text: str) -> str:
        """Create a clean key from concept or label text."""
        import re
        # Remove special characters and convert to snake_case
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', '_', text.strip())
        return text.lower()

    def _flatten_items(self) -> List['MultiPeriodItem']:
        """Flatten all items into a single list."""
        result = []

        def collect(item: 'MultiPeriodItem'):
            result.append(item)
            for child in item.children:
                collect(child)

        for item in self.items:
            collect(item)

        return result

    def _calculate_key_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate important financial metrics from the data."""
        metrics = {}

        # Try to calculate based on statement type
        if "income" in self.statement_type.lower():
            metrics.update(self._calculate_income_metrics(data))
        elif "balance" in self.statement_type.lower():
            metrics.update(self._calculate_balance_metrics(data))
        elif "cash" in self.statement_type.lower():
            metrics.update(self._calculate_cashflow_metrics(data))

        return metrics

    def _calculate_income_metrics(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate income statement metrics."""
        metrics = {}

        # Find revenue and net income for each period
        for period in self.periods:
            period_key = period.lower().replace(' ', '_').replace('-', '_')

            # Find revenue
            revenue_keys = [k for k in data.keys() if 'revenue' in k.lower() and period_key in k and 'total' in k.lower()]
            if not revenue_keys:
                revenue_keys = [k for k in data.keys() if 'revenue' in k.lower() and period_key in k]

            if revenue_keys:
                revenue = data[revenue_keys[0]]

                # Find net income
                income_keys = [k for k in data.keys() if 'net_income' in k.lower() and period_key in k]
                if income_keys:
                    net_income = data[income_keys[0]]
                    # Calculate profit margin
                    if revenue and revenue != 0:
                        metrics[f"profit_margin_{period_key}"] = round(net_income / revenue, 4)

                # Find operating income
                op_income_keys = [k for k in data.keys() if 'operating_income' in k.lower() and period_key in k]
                if op_income_keys:
                    op_income = data[op_income_keys[0]]
                    if revenue and revenue != 0:
                        metrics[f"operating_margin_{period_key}"] = round(op_income / revenue, 4)

        # Calculate growth rates if we have multiple periods
        if len(self.periods) >= 2:
            # Get the two most recent periods
            recent_period = self.periods[0].lower().replace(' ', '_').replace('-', '_')
            prior_period = self.periods[1].lower().replace(' ', '_').replace('-', '_')

            # Revenue growth
            recent_rev_keys = [k for k in data.keys() if 'revenue' in k.lower() and recent_period in k and 'total' in k.lower()]
            prior_rev_keys = [k for k in data.keys() if 'revenue' in k.lower() and prior_period in k and 'total' in k.lower()]

            if recent_rev_keys and prior_rev_keys:
                recent_rev = data[recent_rev_keys[0]]
                prior_rev = data[prior_rev_keys[0]]
                if prior_rev and prior_rev != 0:
                    metrics["revenue_growth_rate"] = round((recent_rev - prior_rev) / prior_rev, 4)

        return metrics

    def _calculate_balance_metrics(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate balance sheet metrics."""
        metrics = {}

        for period in self.periods:
            period_key = period.lower().replace(' ', '_').replace('-', '_')

            # Find key balance sheet items
            assets_keys = [k for k in data.keys() if 'total_assets' in k.lower() and period_key in k]
            liabilities_keys = [k for k in data.keys() if 'total_liabilities' in k.lower() and period_key in k]
            equity_keys = [k for k in data.keys() if 'stockholders_equity' in k.lower() and period_key in k]

            if assets_keys and liabilities_keys:
                assets = data[assets_keys[0]]
                liabilities = data[liabilities_keys[0]]

                # Debt to assets ratio
                if assets and assets != 0:
                    metrics[f"debt_to_assets_{period_key}"] = round(liabilities / assets, 4)

                # Equity ratio
                if equity_keys:
                    equity = data[equity_keys[0]]
                    if assets and assets != 0:
                        metrics[f"equity_ratio_{period_key}"] = round(equity / assets, 4)

        return metrics

    def _calculate_cashflow_metrics(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate cash flow metrics."""
        metrics = {}

        for period in self.periods:
            period_key = period.lower().replace(' ', '_').replace('-', '_')

            # Find operating cash flow
            ocf_keys = [k for k in data.keys() if 'operating_activities' in k.lower() and 'net_cash' in k.lower() and period_key in k]
            if ocf_keys:
                ocf = data[ocf_keys[0]]

                # Find capital expenditures
                capex_keys = [k for k in data.keys() if 'capital_expenditure' in k.lower() and period_key in k]
                if not capex_keys:
                    capex_keys = [k for k in data.keys() if 'property_plant_equipment' in k.lower() and 'acquire' in k.lower() and period_key in k]

                if capex_keys:
                    capex = abs(data[capex_keys[0]])  # Capex is usually negative
                    # Calculate free cash flow
                    metrics[f"free_cash_flow_{period_key}"] = ocf - capex

        return metrics

    def __iter__(self):
        """
        Iterate over all items in the statement (flat iteration).

        Yields items in display order (depth-first traversal).

        Example:
            for item in statement:
                print(f"{item.label}: {item.values}")
        """
        def traverse(item: 'MultiPeriodItem'):
            yield item
            for child in item.children:
                yield from traverse(child)

        for item in self.items:
            yield from traverse(item)

    def iter_hierarchy(self):
        """
        Iterate over items with hierarchy information.

        Yields tuples of (item, depth, parent) for each item.

        Example:
            for item, depth, parent in statement.iter_hierarchy():
                indent = "  " * depth
                print(f"{indent}{item.label}")
        """
        def traverse(item: 'MultiPeriodItem', depth: int = 0, parent: Optional['MultiPeriodItem'] = None):
            yield (item, depth, parent)
            for child in item.children:
                yield from traverse(child, depth + 1, item)

        for item in self.items:
            yield from traverse(item)

    def iter_with_values(self):
        """
        Iterate over items that have actual values (skip abstract/empty items).

        Yields only items with at least one non-None value.

        Example:
            for item in statement.iter_with_values():
                for period in statement.periods:
                    value = item.values.get(period)
                    if value:
                        print(f"{item.label} ({period}): ${value:,.0f}")
        """
        for item in self:
            if any(v is not None for v in item.values.values()):
                yield item

    def get_items_by_depth(self, max_depth: int = None) -> List['MultiPeriodItem']:
        """
        Get all items up to a specified depth level.

        Args:
            max_depth: Maximum depth to include (None for all depths)

        Returns:
            List of items up to the specified depth

        Example:
            # Get only top-level and first-level items
            top_items = statement.get_items_by_depth(1)
        """
        result = []
        for item, depth, _ in self.iter_hierarchy():
            if max_depth is None or depth <= max_depth:
                result.append(item)
        return result

    def find_item(self, concept: str = None, label: str = None) -> Optional['MultiPeriodItem']:
        """
        Find a specific item by concept name or label.

        Args:
            concept: Concept name to search for (case-insensitive)
            label: Label text to search for (case-insensitive)

        Returns:
            First matching item or None if not found

        Example:
            revenue = statement.find_item(label="Total Revenue")
            if revenue:
                print(revenue.values)
        """
        if not concept and not label:
            return None

        for item in self:
            if concept and item.concept.lower() == concept.lower():
                return item
            if label and item.label.lower() == label.lower():
                return item
        return None

    def to_dict(self, include_empty: bool = False) -> Dict[str, Any]:
        """
        Convert statement to a simple dictionary structure for JSON serialization.

        Args:
            include_empty: Include items with no values

        Returns:
            Dictionary representation suitable for web APIs

        Example:
            data = statement.to_dict()
            json.dumps(data)  # Ready for web API response
        """
        def item_to_dict(item: 'MultiPeriodItem') -> Dict[str, Any]:
            # Skip items with no values unless requested
            if not include_empty and not any(v is not None for v in item.values.values()):
                return None

            result = {
                'concept': item.concept,
                'label': item.label,
                'values': item.values,
                'is_abstract': item.is_abstract,
                'is_total': item.is_total,
                'depth': item.depth,
                'confidence': item.confidence
            }

            # Add children if they exist
            if item.children:
                children = []
                for child in item.children:
                    child_dict = item_to_dict(child)
                    if child_dict:
                        children.append(child_dict)
                if children:
                    result['children'] = children

            return result

        items_data = []
        for item in self.items:
            item_dict = item_to_dict(item)
            if item_dict:
                items_data.append(item_dict)

        return {
            'company': self.company_name,
            'cik': self.cik,
            'statement_type': self._get_statement_type_name(),
            'periods': self.periods,
            'items': items_data,
            'metadata': {
                'canonical_coverage': self.canonical_coverage,
                'total_items': len(list(self.iter_with_values())),
                'concise_format': self.concise_format
            }
        }

    def to_flat_list(self) -> List[Dict[str, Any]]:
        """
        Convert statement to a flat list of items for table rendering.

        Returns:
            List of dictionaries, each representing one row

        Example:
            rows = statement.to_flat_list()
            # Perfect for rendering in HTML tables or data grids
            for row in rows:
                print(f"{row['label']}: {row['values']}")
        """
        result = []

        for item, depth, parent in self.iter_hierarchy():
            # Skip empty abstract items
            if item.is_abstract and not any(v is not None for v in item.values.values()):
                continue

            row = {
                'concept': item.concept,
                'label': item.label,
                'depth': depth,
                'parent': parent.concept if parent else None,
                'is_abstract': item.is_abstract,
                'is_total': item.is_total,
                'confidence': item.confidence
            }

            # Add period values
            for period in self.periods:
                row[period] = item.values.get(period)
                # Also add formatted version
                row[f"{period}_formatted"] = item.get_display_value(period, self.concise_format)

            result.append(row)

        return result

    def get_period_comparison(self, period1: str, period2: str) -> List[Dict[str, Any]]:
        """
        Get comparison data between two periods.

        Args:
            period1: First period to compare
            period2: Second period to compare

        Returns:
            List of items with values, changes, and percentages

        Example:
            comparison = statement.get_period_comparison("FY 2024", "FY 2023")
            for item in comparison:
                if item['change_percent']:
                    print(f"{item['label']}: {item['change_percent']:.1%} change")
        """
        if period1 not in self.periods or period2 not in self.periods:
            raise ValueError(f"Periods must be in {self.periods}")

        result = []

        for item in self.iter_with_values():
            val1 = item.values.get(period1)
            val2 = item.values.get(period2)

            comparison = {
                'concept': item.concept,
                'label': item.label,
                'is_total': item.is_total,
                period1: val1,
                period2: val2,
                f"{period1}_formatted": item.get_display_value(period1, self.concise_format),
                f"{period2}_formatted": item.get_display_value(period2, self.concise_format)
            }

            # Calculate change if both values exist
            if val1 is not None and val2 is not None and val2 != 0:
                change = val1 - val2
                change_percent = change / abs(val2)
                comparison['change'] = change
                comparison['change_percent'] = change_percent
                comparison['change_formatted'] = f"${change:,.0f}" if abs(change) >= 1 else f"{change:.2f}"
            else:
                comparison['change'] = None
                comparison['change_percent'] = None
                comparison['change_formatted'] = None

            result.append(comparison)

        return result

    def _create_table(self, for_llm: bool = False) -> Table:
        """
        Create the statement table without Panel wrapper.

        Args:
            for_llm: If True, use minimal formatting for LLM consumption

        Returns:
            Rich Table object
        """
        # Get color scheme
        colors = get_current_scheme()

        # Choose box style based on context
        box_style = box.MINIMAL if for_llm else box.SIMPLE

        # Main table with multiple period columns
        stmt_table = Table(
            box=box_style,
            show_header=True,
            padding=(0, 1),
            expand=True
        )

        # Add concept column
        stmt_table.add_column("", style="", ratio=2)

        # Add period columns
        for period in self.periods:
            stmt_table.add_column(period, justify="right", style="bold", ratio=1)

        def add_item_to_table(item: 'MultiPeriodItem', depth: int = 0):
            """Add an item row to the table."""
            indent = "  " * depth

            # Prepare row values
            row = []

            # Concept label
            if item.is_abstract:
                row.append(Text(f"{indent}{item.label}", style=colors["abstract_item"]))
            elif item.is_total:
                row.append(Text(f"{indent}{item.label}", style=colors["total_item"]))
            else:
                # Check if this is a key financial item that should always be prominent
                important_labels = [
                    'Total Revenue', 'Revenue', 'Net Sales', 'Total Net Sales',
                    'Operating Income', 'Operating Income (Loss)', 'Operating Profit',
                    'Net Income', 'Net Income (Loss)', 'Net Earnings',
                    'Gross Profit', 'Gross Margin',
                    'Cost of Revenue', 'Cost of Goods Sold',
                    'Operating Expenses', 'Total Operating Expenses',
                    'Earnings Per Share', 'EPS'
                ]

                is_important = any(label in item.label for label in important_labels)

                # Don't mark important items as low confidence even if score is low
                if is_important:
                    style = colors["total_item"]  # Use bold styling for important items
                    confidence_marker = ""
                else:
                    style = colors["low_confidence_item"] if item.confidence < 0.8 else colors["regular_item"]
                    confidence_marker = " ◦" if item.confidence < 0.8 else ""

                row.append(Text(f"{indent}{item.label}{confidence_marker}", style=style))

            # Period values
            for period in self.periods:
                value_str = item.get_display_value(period, concise_format=self.concise_format)
                if value_str and value_str != "-":
                    # Color code values
                    value = item.values.get(period)
                    if value and isinstance(value, (int, float)):
                        value_style = colors["negative_value"] if value < 0 else colors["positive_value"]
                    else:
                        value_style = ""

                    if item.is_total:
                        # Combine total style with value color if present
                        total_style = colors["total_value_prefix"]
                        if value_style:
                            total_style = f"{total_style} {value_style}"
                        row.append(Text(value_str, style=total_style))
                    else:
                        row.append(Text(value_str, style=value_style))
                else:
                    row.append("")

            stmt_table.add_row(*row)

            # Add separator line after totals (skip for LLM to save characters)
            if item.is_total and depth == 0 and not for_llm:
                separator_row = [Text("─" * 40, style=colors["separator"])]
                for _ in self.periods:
                    separator_row.append(Text("─" * 15, style=colors["separator"]))
                stmt_table.add_row(*separator_row)

            # Add children
            for child in item.children:
                if depth < 3:
                    add_item_to_table(child, depth + 1)

        # Add all items
        for item in self.items:
            add_item_to_table(item)

        return stmt_table

    def to_llm_string(self) -> str:
        """
        Generate LLM-optimized string representation.

        Uses minimal formatting optimized for LLM consumption:
        - No Panel borders (saves ~200 characters)
        - Minimal table box style (saves ~100 characters per row)
        - No ANSI color codes (plain text)
        - Assumes concise_format is already set for number formatting
        - Omits separator lines after totals

        Returns:
            String representation optimized for LLM token usage
        """
        from io import StringIO
        from rich.console import Console

        buffer = StringIO()
        # Disable color/formatting codes for plain text output
        console = Console(
            file=buffer,
            force_terminal=False,  # No ANSI codes
            no_color=True,         # Plain text only
            width=120,
            legacy_windows=False
        )

        # Create table without Panel wrapper
        table = self._create_table(for_llm=True)
        console.print(table)

        output = buffer.getvalue()
        return output

    def __repr__(self) -> str:
        """String representation using rich formatting."""
        return repr_rich(self.__rich__())


@dataclass
class MultiPeriodItem:
    """An item in a multi-period statement with values for each period."""
    concept: str
    label: str
    values: Dict[str, Optional[float]]  # Period -> Value mapping

    # Hierarchy
    depth: int
    parent_concept: Optional[str]
    children: List['MultiPeriodItem'] = field(default_factory=list)

    # Metadata
    is_abstract: bool = False
    is_total: bool = False
    section: Optional[str] = None
    confidence: float = 1.0

    def get_display_value(self, period: str, concise_format: bool = False) -> str:
        """
        Get formatted value for a specific period.

        Args:
            period: The period to get value for
            concise_format: If True, use concise format ($1.0B), if False use full numbers with commas

        Returns:
            Formatted value string
        """
        value = self.values.get(period)

        if value is not None:
            # Check if this is a per-share amount
            is_per_share = any(indicator in self.concept.lower() or indicator in self.label.lower() 
                             for indicator in ['pershare', 'per share', 'earnings per', 'eps'])

            if is_per_share:
                # Format per-share amounts with 2 decimal places, no dollar sign
                return f"{value:.2f}"
            elif concise_format:
                # Use concise format ($1.0B, $1.0M, etc.)
                if abs(value) >= 1_000_000_000:
                    return f"${value/1_000_000_000:.1f}B"
                elif abs(value) >= 1_000_000:
                    return f"${value/1_000_000:.1f}M"
                elif abs(value) >= 1_000:
                    return f"${value/1_000:.0f}K"
                else:
                    return f"${value:.0f}"
            else:
                # Use full number format with commas
                # Format as integer if whole number, otherwise with appropriate decimals
                if value == int(value):
                    return f"${int(value):,}"
                else:
                    # Use appropriate decimal places based on magnitude
                    if abs(value) >= 1:
                        return f"${value:,.0f}"
                    else:
                        return f"${value:.2f}"
        elif self.is_abstract:
            return ""
        else:
            return "-"


def validate_fiscal_year_period_end(fiscal_year: int, period_end: date) -> bool:
    """
    Validate that fiscal_year is reasonable given period_end.

    This handles SEC Facts API data quality issues where comparative periods
    are mislabeled with incorrect fiscal_year values (Issue #452).

    Args:
        fiscal_year: The fiscal year from the fact
        period_end: The period end date

    Returns:
        True if the fiscal_year/period_end combination is valid, False otherwise

    Examples:
        >>> # Early January period (52/53-week calendar)
        >>> validate_fiscal_year_period_end(2022, date(2023, 1, 1))
        True
        >>> validate_fiscal_year_period_end(2023, date(2023, 1, 1))
        True
        >>> validate_fiscal_year_period_end(2024, date(2023, 1, 1))
        False

        >>> # Late December period
        >>> validate_fiscal_year_period_end(2023, date(2023, 12, 31))
        True
        >>> validate_fiscal_year_period_end(2024, date(2023, 12, 31))
        True

        >>> # Normal period
        >>> validate_fiscal_year_period_end(2023, date(2023, 6, 30))
        True
        >>> validate_fiscal_year_period_end(2025, date(2023, 6, 30))
        False
    """
    year_diff = fiscal_year - period_end.year

    # Early January (Jan 1-7): fiscal_year should be year-1 (52/53-week calendar) or year
    # Example: Period ending Jan 1, 2023 → FY 2022 (most common) or FY 2023 (edge case)
    if period_end.month == 1 and period_end.day <= 7:
        return year_diff in (-1, 0)

    # Late December (Dec 25-31): fiscal_year should be year or year+1
    # Example: Period ending Dec 31, 2023 → FY 2023 (most common) or FY 2024 (year-end shifts)
    elif period_end.month == 12 and period_end.day >= 25:
        return year_diff in (0, 1)

    # All other dates: fiscal_year should match period_end.year exactly
    else:
        return year_diff == 0


def validate_quarterly_period_end(fiscal_period: str,
                                  period_end: date,
                                  fiscal_year_end_month: int = 12) -> bool:
    """
    Validate that period_end matches the expected month for the fiscal_period.

    This filters out comparative period data that's mislabeled with incorrect
    fiscal_period values in the SEC Facts API.

    Args:
        fiscal_period: The fiscal period (Q1, Q2, Q3, Q4, FY)
        period_end: The period end date
        fiscal_year_end_month: Company's fiscal year end month (default: 12)

    Returns:
        True if period_end matches expected month for fiscal_period

    Examples:
        >>> # Apple (fiscal year ends in September, month 9)
        >>> validate_quarterly_period_end('Q3', date(2025, 6, 28), 9)
        True  # Q3 should end in June (3 months before Sept)

        >>> validate_quarterly_period_end('Q3', date(2024, 9, 28), 9)
        False  # This is Q4, not Q3
    """
    if fiscal_period == 'FY':
        # FY should match fiscal year end month
        return period_end.month == fiscal_year_end_month

    # Calculate expected month for each quarter based on fiscal year end
    # Q4 ends in fiscal year end month
    # Q3 ends 3 months before that
    # Q2 ends 6 months before that
    # Q1 ends 9 months before that

    quarter_offsets = {
        'Q1': -9,  # 9 months before fiscal year end
        'Q2': -6,  # 6 months before fiscal year end
        'Q3': -3,  # 3 months before fiscal year end
        'Q4': 0    # Fiscal year end month
    }

    if fiscal_period not in quarter_offsets:
        return False

    # Calculate expected month
    offset = quarter_offsets[fiscal_period]
    expected_month = fiscal_year_end_month + offset

    # Handle month wrapping
    if expected_month <= 0:
        expected_month += 12
    elif expected_month > 12:
        expected_month -= 12

    # Allow ±1 month flexibility for 52/53-week calendars
    month_diff = abs(period_end.month - expected_month)

    # Handle wrap-around (e.g., month 12 vs month 1 is only 1 month apart)
    if month_diff > 6:
        month_diff = 12 - month_diff

    return month_diff <= 1


def detect_fiscal_year_end(facts: List[FinancialFact]) -> int:
    """
    Detect company's fiscal year end month from FY period_end dates.

    Returns:
        Most common month from FY period_end dates (default: 12)
    """
    from collections import Counter

    # Get all FY facts with period_end
    fy_facts = [f for f in facts if f.fiscal_period == 'FY' and f.period_end]

    if not fy_facts:
        return 12  # Default to December

    # Find most common period_end month
    months = [f.period_end.month for f in fy_facts]
    most_common = Counter(months).most_common(1)

    return most_common[0][0] if most_common else 12


def calculate_fiscal_year_for_label(period_end: date, fiscal_year_end_month: int) -> int:
    """
    Calculate the fiscal year for period labels based on period_end date.

    This function addresses Issue #460 where quarterly labels showed incorrect fiscal years
    because the SEC Facts API provides forward-looking fiscal_year values (the year the
    quarter contributes to), not the year for labeling purposes.

    For quarterly periods, the fiscal year label should reflect when the period occurred,
    not which fiscal year it contributes to. This mirrors the logic from
    validate_fiscal_year_period_end() but calculates the appropriate fiscal year for labels.

    Args:
        period_end: The period end date
        fiscal_year_end_month: Company's fiscal year end month (1-12)

    Returns:
        The fiscal year to use for labeling this period

    Examples:
        >>> # Apple (fiscal year ends in September)
        >>> # Q3 ending June 28, 2024
        >>> calculate_fiscal_year_for_label(date(2024, 6, 28), 9)
        2024  # Q3 2024, not Q3 2025

        >>> # Q4 ending September 28, 2024
        >>> calculate_fiscal_year_for_label(date(2024, 9, 28), 9)
        2024  # Q4 2024 (fiscal year end)

        >>> # Q1 ending December 30, 2023
        >>> calculate_fiscal_year_for_label(date(2023, 12, 30), 9)
        2024  # Q1 2024 (first quarter of FY 2024)

        >>> # Early January period (52/53-week calendar edge case)
        >>> calculate_fiscal_year_for_label(date(2023, 1, 1), 12)
        2022  # FY 2022 (52/53-week calendar convention)
    """
    # Early January (Jan 1-7): Use prior year (52/53-week calendar convention)
    if period_end.month == 1 and period_end.day <= 7:
        return period_end.year - 1

    # If period_end is in a month AFTER fiscal year end, it's the NEXT fiscal year
    # Example: Apple FY ends Sept (month 9)
    #   - Period ending Oct 2023 (month 10) → FY 2024 (first quarter of new fiscal year)
    #   - Period ending Sept 2023 (month 9) → FY 2023 (end of fiscal year)
    #   - Period ending June 2024 (month 6) → FY 2024 (third quarter)

    if period_end.month > fiscal_year_end_month:
        # Period is after fiscal year end, so it's in the next fiscal year
        # Example: Sept FY end, period ends in Oct/Nov/Dec → next year
        return period_end.year + 1
    else:
        # Period is at or before fiscal year end, use calendar year
        return period_end.year


class EnhancedStatementBuilder:
    """
    Builds multi-period statements with hierarchical structure using learned mappings.
    """

    # Essential concepts that should always be shown if they have data
    ESSENTIAL_CONCEPTS = {
        'BalanceSheet': {
            # Working Capital
            'AccountsReceivable', 'AccountsReceivableNetCurrent', 
            'Inventory', 'InventoryNet',
            'AccountsPayable', 'AccountsPayableCurrent',
            # Debt
            'LongTermDebt', 'LongTermDebtNoncurrent', 'LongTermDebtCurrent',
            'ShortTermDebt', 'ShortTermBorrowings',
            # Equity
            'CommonStockSharesOutstanding', 'CommonStockValue',
            'RetainedEarningsAccumulatedDeficit',
            # Other important
            'IntangibleAssetsNetExcludingGoodwill', 'Goodwill',
            'DeferredRevenueCurrent', 'DeferredRevenueNoncurrent',
            'PropertyPlantAndEquipmentNet'
        },
        'IncomeStatement': {
            'CostOfRevenue', 'CostOfGoodsAndServicesSold', 'GrossProfit',
            'ResearchAndDevelopmentExpense', 'SellingGeneralAndAdministrativeExpense',
            'InterestExpense', 'InterestIncome', 'OtherNonoperatingIncomeExpense'
        },
        'CashFlowStatement': {
            # Key adjustments
            'DepreciationDepletionAndAmortization', 'DepreciationAndAmortization',
            # Investment activities
            'CapitalExpendituresIncurredButNotYetPaid', 'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsToAcquireBusinessesNetOfCashAcquired', 'BusinessAcquisitionsNetOfCashAcquired',
            # Financing activities
            'DividendsPaid', 'PaymentsOfDividends', 'PaymentsOfDividendsCommonStock',
            'PaymentsForRepurchaseOfCommonStock', 'PaymentsForRepurchaseOfEquity',
            'ProceedsFromIssuanceOfLongTermDebt', 'RepaymentsOfLongTermDebt',
            # Working capital changes
            'IncreaseDecreaseInAccountsReceivable', 'IncreaseDecreaseInInventories',
            'IncreaseDecreaseInAccountsPayable'
        }
    }

    # Common concept name variations that should be normalized
    CONCEPT_NORMALIZATIONS = {
        # Cost concepts
        'CostOfGoodsAndServicesSold': 'CostOfRevenue',
        'CostOfGoodsSold': 'CostOfRevenue',
        'CostOfSales': 'CostOfRevenue',
        # Receivables
        'AccountsReceivableNetCurrent': 'AccountsReceivable',
        'AccountsReceivableNet': 'AccountsReceivable',
        # Payables
        'AccountsPayableCurrent': 'AccountsPayable',
        # Inventory
        'InventoryNet': 'Inventory',
        # Debt concepts
        'LongTermDebtNoncurrent': 'LongTermDebt',
        'LongTermDebtAndCapitalLeaseObligations': 'LongTermDebt',
        'ShortTermBorrowings': 'ShortTermDebt',
        # Depreciation concepts
        'DepreciationDepletionAndAmortization': 'DepreciationAndAmortization',
        # Capital expenditure concepts  
        'PaymentsToAcquirePropertyPlantAndEquipment': 'CapitalExpenditures',
        'CapitalExpendituresIncurredButNotYetPaid': 'CapitalExpenditures',
        # Dividend concepts
        'PaymentsOfDividends': 'DividendsPaid',
        'PaymentsForDividends': 'DividendsPaid',
        'PaymentsOfDividendsCommonStock': 'DividendsPaid',
        # Share repurchase
        'PaymentsForRepurchaseOfEquity': 'PaymentsForRepurchaseOfCommonStock'
    }

    def __init__(self):
        self.learned_mappings = load_learned_mappings()
        self.virtual_trees = load_virtual_trees()

    def _normalize_concept(self, concept: str) -> str:
        """Normalize concept names for matching."""
        # Remove namespace prefix
        if ':' in concept:
            concept = concept.split(':')[-1]

        # Apply normalization mappings
        return self.CONCEPT_NORMALIZATIONS.get(concept, concept)

    def _is_essential_concept(self, concept: str, statement_type: str) -> bool:
        """Check if concept is essential for this statement type."""
        essential = self.ESSENTIAL_CONCEPTS.get(statement_type, set())
        normalized = self._normalize_concept(concept)
        return normalized in essential or concept in essential

    def build_multi_period_statement(self,
                                    facts: List[FinancialFact],
                                    statement_type: str,
                                    periods: int = 4,
                                    annual: bool = True) -> MultiPeriodStatement:
        """
        Build a multi-period statement with hierarchical structure.

        Args:
            facts: List of all facts
            statement_type: Type of statement
            periods: Number of periods to include
            annual: Prefer annual periods over quarterly

        Returns:
            MultiPeriodStatement with hierarchical structure and multiple periods
        """

        # Filter facts by statement type
        # Handle both 'CashFlow' and 'CashFlowStatement' for compatibility
        if statement_type == 'CashFlow':
            stmt_facts = [f for f in facts if f.statement_type in ['CashFlow', 'CashFlowStatement']]
        else:
            stmt_facts = [f for f in facts if f.statement_type == statement_type]

        # Use the same logic as FactQuery.latest_periods for consistency
        # Group facts by unique periods and calculate period info
        # FIX: Use period_end as part of the key to keep all variations
        period_info = {}
        period_facts = defaultdict(list)

        for fact in stmt_facts:
            # Include period_end in the key to avoid losing different period_end variations
            period_key = (fact.fiscal_year, fact.fiscal_period, fact.period_end)
            # Make period label unique by including period_end when there are duplicates
            period_label = f"{fact.fiscal_period} {fact.fiscal_year}"

            # Store period metadata for each unique combination
            if period_key not in period_info:
                period_info[period_key] = {
                    'label': period_label,
                    'end_date': fact.period_end or date.max,
                    'is_annual': fact.fiscal_period == 'FY',
                    'filing_date': fact.filing_date or date.min,
                    'fiscal_year': fact.fiscal_year,
                    'fiscal_period': fact.fiscal_period
                }

            # Store facts by the unique period key instead of label
            period_facts[period_key].append(fact)

        # Create list of periods with their metadata
        period_list = []
        for period_key, info in period_info.items():
            period_list.append((period_key, info))

        # Detect fiscal year end month for label calculation (Issue #460)
        # This needs to be calculated before the annual/quarterly split so it's available for both paths
        fiscal_year_end_month = detect_fiscal_year_end(stmt_facts)

        if annual:
            # When annual=True, filter for TRUE annual periods using duration
            # Some facts are marked as FY but are actually quarterly (90 days vs 363+ days)
            true_annual_periods = []

            for pk, info in period_list:
                if not info['is_annual']:
                    continue

                # pk is now (fiscal_year, fiscal_period, period_end)
                fiscal_year = pk[0]
                period_end_date = pk[2]

                # Validate fiscal_year against period_end to filter out mislabeled comparative data
                # Issue #452: SEC Facts API has inconsistent fiscal_year values for comparatives
                if not period_end_date:
                    continue

                # Use strict validation to reject invalid fiscal_year/period_end combinations
                if not validate_fiscal_year_period_end(fiscal_year, period_end_date):
                    log.debug(
                        f"Skipping invalid fiscal_year={fiscal_year} for period_end={period_end_date} "
                        f"(likely mislabeled comparative data - Issue #452)"
                    )
                    continue  # Skip mislabeled comparative data

                # Get a fact from this period to check duration
                period_fact_list = period_facts.get(pk, [])
                if period_fact_list:
                    # Check if this is truly annual by looking at period duration
                    sample_fact = period_fact_list[0]
                    if sample_fact.period_start and sample_fact.period_end:
                        duration = (sample_fact.period_end - sample_fact.period_start).days
                        # Annual periods are typically 360-370 days, quarterly are ~90 days
                        if duration > 300:  # This is truly annual
                            true_annual_periods.append((pk, info))
                    elif not sample_fact.period_start:
                        # If no period_start, assume it's annual if marked as FY
                        # (this handles instant facts like balance sheet items)
                        true_annual_periods.append((pk, info))

            # Group by period year and select most recent comprehensive filing
            # This approach combines availability (comprehensive data) with recency (latest corrections)
            # Issue #452: When multiple periods exist for same year (e.g., Jan 1 and Dec 31 both in 2023),
            # prefer the period where fiscal_year best matches expected value
            annual_by_period_year = {}
            for pk, info in true_annual_periods:
                fiscal_year = pk[0]
                period_end_date = pk[2]
                period_year = period_end_date.year if period_end_date else None

                if period_year:
                    facts_for_period = period_facts.get(pk, [])
                    filing_date = info.get('filing_date')

                    # Only consider periods with substantial data (≥5 facts) to avoid sparse comparative data
                    if len(facts_for_period) >= 5:
                        should_replace = False

                        if period_year not in annual_by_period_year:
                            should_replace = True
                        else:
                            existing_pk, existing_info = annual_by_period_year[period_year]
                            existing_fiscal_year = existing_pk[0]
                            existing_period_end = existing_pk[2]
                            existing_filing_date = existing_info.get('filing_date')

                            # Prefer period where fiscal_year matches expected value
                            # For early January: expect fiscal_year = year - 1
                            # For normal dates: expect fiscal_year = year
                            is_early_jan = period_end_date.month == 1 and period_end_date.day <= 7
                            existing_is_early_jan = existing_period_end.month == 1 and existing_period_end.day <= 7

                            expected_fy = period_year - 1 if is_early_jan else period_year
                            existing_expected_fy = period_year - 1 if existing_is_early_jan else period_year

                            # Score: 0 = matches expected, 1 = doesn't match
                            score = 0 if fiscal_year == expected_fy else 1
                            existing_score = 0 if existing_fiscal_year == existing_expected_fy else 1

                            # Replace if current period has better score, or same score but newer filing
                            if score < existing_score:
                                should_replace = True
                            elif score == existing_score and filing_date and existing_filing_date and filing_date > existing_filing_date:
                                should_replace = True

                        if should_replace:
                            annual_by_period_year[period_year] = (pk, info)

            # Sort by period year (descending) and select
            sorted_periods = sorted(annual_by_period_year.items(), key=lambda x: x[0], reverse=True)
            selected_period_info = [period_info for year, period_info in sorted_periods[:periods]]
        else:
            # Quarterly mode: Filter out comparative data by validating period_end
            # fiscal_year_end_month was already calculated at line 1223 and is in scope here

            valid_quarterly_periods = []

            for pk, info in period_list:
                fiscal_period = info['fiscal_period']
                period_end_date = pk[2]  # pk is (fiscal_year, fiscal_period, period_end)

                # Skip if no period_end
                if not period_end_date:
                    continue

                # Skip FY periods - we only want Q1/Q2/Q3/Q4 for quarterly mode
                if fiscal_period == 'FY':
                    continue

                # Validate period_end matches expected month for fiscal_period
                if validate_quarterly_period_end(fiscal_period, period_end_date, fiscal_year_end_month):
                    valid_quarterly_periods.append((pk, info))
                else:
                    log.debug(
                        f"Skipping invalid period_end={period_end_date} for fiscal_period={fiscal_period} "
                        f"(likely comparative data)"
                    )

            # Group by fiscal period label and keep most recent
            # FIX for Issue #460: Calculate fiscal_year from period_end for quarterly labels
            quarterly_by_period = {}
            for pk, info in valid_quarterly_periods:
                fiscal_period = pk[1]
                period_end_date = pk[2]

                # Calculate correct fiscal year for label based on period_end
                # This fixes Issue #460 where SEC's forward-looking fiscal_year caused
                # quarterly labels to show 1 year ahead (Q3 2025 instead of Q3 2024)
                calculated_fiscal_year = calculate_fiscal_year_for_label(
                    period_end_date,
                    fiscal_year_end_month
                )
                period_label = f"{fiscal_period} {calculated_fiscal_year}"

                # Store the calculated fiscal year in info for later use
                info_with_calculated_fy = info.copy()
                info_with_calculated_fy['calculated_fiscal_year'] = calculated_fiscal_year

                if period_label not in quarterly_by_period:
                    quarterly_by_period[period_label] = (pk, info_with_calculated_fy)
                else:
                    # If duplicate valid periods exist, prefer most recent filing_date
                    existing_pk, existing_info = quarterly_by_period[period_label]
                    if info['filing_date'] > existing_info['filing_date']:
                        quarterly_by_period[period_label] = (pk, info_with_calculated_fy)

            # Sort by period end date (newest first) and select requested number
            sorted_periods = sorted(
                quarterly_by_period.values(),
                key=lambda x: x[1]['end_date'],
                reverse=True
            )
            selected_period_info = sorted_periods[:periods]

        # Extract period labels and build a mapping for the selected periods
        # For annual periods, use the fiscal year from facts (most reliable)
        # For quarterly periods, calculate fiscal year from period_end (Issue #460)
        selected_periods = []
        for pk, info in selected_period_info:
            if annual and info.get('is_annual') and pk[2]:  # pk[2] is period_end
                # Use fiscal_year from facts if available (handles 52/53-week calendars correctly)
                # Falls back to period_end.year with early January adjustment for edge cases
                if 'fiscal_year' in info and info['fiscal_year']:
                    label = f"FY {info['fiscal_year']}"
                else:
                    period_end = pk[2]
                    # For periods ending Jan 1-7, use prior year (52/53-week calendar convention)
                    # This handles cases like fiscal year ending Jan 1, 2023 being FY 2022
                    if period_end.month == 1 and period_end.day <= 7:
                        label = f"FY {period_end.year - 1}"
                    else:
                        label = f"FY {period_end.year}"
            elif not annual and pk[2]:
                # FIX for Issue #460: For quarterly periods, use the calculated fiscal year
                # that was stored during grouping (avoids recalculation)
                fiscal_period = pk[1]
                period_end = pk[2]
                calculated_fiscal_year = info.get('calculated_fiscal_year')
                if calculated_fiscal_year is not None:
                    label = f"{fiscal_period} {calculated_fiscal_year}"
                else:
                    # Fallback: calculate if not found (shouldn't happen for quarterly)
                    calculated_fiscal_year = calculate_fiscal_year_for_label(
                        period_end,
                        fiscal_year_end_month
                    )
                    label = f"{fiscal_period} {calculated_fiscal_year}"
            else:
                label = info['label']
            selected_periods.append(label)

        # Create a new period_facts dict with labels as keys for the selected periods
        # CRITICAL: For annual periods, filter facts to only include those with duration > 300 days
        period_facts_by_label = defaultdict(list)
        for i, (period_key, info) in enumerate(selected_period_info):
            label = selected_periods[i]  # Use the corrected label
            facts_for_period = period_facts.get(period_key, [])

            # If this is an annual period, filter to only include annual facts
            if annual and info.get('is_annual'):
                filtered_facts = []
                for fact in facts_for_period:
                    # Keep facts with annual duration (>300 days) or instant facts (no period_start)
                    if fact.period_start and fact.period_end:
                        duration = (fact.period_end - fact.period_start).days
                        if duration > 300:
                            filtered_facts.append(fact)
                    else:
                        # Instant facts (balance sheet items) don't have duration
                        filtered_facts.append(fact)
                period_facts_by_label[label] = filtered_facts
            else:
                period_facts_by_label[label] = facts_for_period

        # Build hierarchical structure using canonical template
        # Handle statement type naming inconsistencies
        # Map fact statement types to virtual tree keys
        statement_type_mapping = {
            'CashFlow': 'CashFlowStatement',
            'IncomeStatement': 'IncomeStatement',
            'BalanceSheet': 'BalanceSheet',
            'ComprehensiveIncome': 'ComprehensiveIncome',
            'StatementOfEquity': 'StatementOfEquity'
        }

        virtual_tree_key = statement_type_mapping.get(statement_type, statement_type)

        # Also try the exact statement type if mapping doesn't exist
        if virtual_tree_key not in self.virtual_trees and statement_type in self.virtual_trees:
            virtual_tree_key = statement_type

        if virtual_tree_key in self.virtual_trees:
            items = self._build_with_canonical(period_facts_by_label, selected_periods, virtual_tree_key)
            canonical_coverage = self._calculate_coverage(stmt_facts, virtual_tree_key)
        else:
            items = self._build_from_facts(period_facts_by_label, selected_periods)
            canonical_coverage = 0.0

        return MultiPeriodStatement(
            statement_type=statement_type,
            periods=selected_periods,
            items=items,
            canonical_coverage=canonical_coverage
        )


    def _build_with_canonical(self, 
                             period_facts: Dict[str, List[FinancialFact]],
                             periods: List[str],
                             virtual_tree_key: str) -> List[MultiPeriodItem]:
        """Build items using canonical structure."""
        virtual_tree = self.virtual_trees[virtual_tree_key]
        items = []

        # Create fact maps for each period
        period_maps = {}
        for period in periods:
            period_maps[period] = self._create_fact_map(period_facts.get(period, []))

        # For Income Statement, promote essential concepts to top level for visibility
        if virtual_tree_key == 'IncomeStatement':
            items = self._build_with_promoted_concepts(
                virtual_tree, period_maps, periods, virtual_tree_key
            )
        else:
            # Process root nodes normally for other statements
            for root_concept in virtual_tree.get('roots', []):
                item = self._build_canonical_item(
                    root_concept,
                    virtual_tree['nodes'],
                    period_maps,
                    periods,
                    depth=0,
                    statement_type=virtual_tree_key
                )
                if item:
                    items.append(item)

        # Add orphan facts that have values but aren't in the virtual tree
        orphan_section = self._add_orphan_facts(
            period_maps, 
            virtual_tree.get('nodes', {}), 
            periods, 
            virtual_tree_key
        )
        if orphan_section:
            items.append(orphan_section)

        # Add calculated metrics for Income Statement
        if virtual_tree_key == 'IncomeStatement':
            calculated_items = self._add_calculated_metrics(period_maps, periods, items)
            if calculated_items:
                items.extend(calculated_items)

        # Apply smart aggregation to parent nodes
        for item in items:
            self._apply_smart_aggregation(item)

        # Remove redundant table duplicates for cleaner presentation
        items = self._deduplicate_table_items(items)

        return items

    def _build_with_promoted_concepts(self,
                                     virtual_tree: Dict,
                                     period_maps: Dict[str, Dict[str, FinancialFact]],
                                     periods: List[str],
                                     statement_type: str) -> List[MultiPeriodItem]:
        """Build Income Statement with essential concepts promoted to top level."""
        items = []
        nodes = virtual_tree['nodes']

        # Essential revenue/income concepts to promote
        ESSENTIAL_CONCEPTS = [
            # Revenue concepts (in priority order)
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'SalesRevenueNet',
            'Revenues',
            # Cost concepts
            'CostOfGoodsAndServicesSold',
            'CostOfRevenue',
            # Profit concepts
            'GrossProfit',
            'OperatingIncomeLoss',
            'NetIncomeLoss',
            # Earnings per share
            'EarningsPerShareBasic',
            'EarningsPerShareDiluted'
        ]

        # Revenue concepts for deduplication (in priority order)
        REVENUE_CONCEPTS = [
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'SalesRevenueNet',
            'Revenues'
        ]

        # First, add the abstract root for structure
        for root_concept in virtual_tree.get('roots', []):
            if 'Abstract' in root_concept:
                item = self._build_canonical_item(
                    root_concept,
                    nodes,
                    period_maps,
                    periods,
                    depth=0,
                    statement_type=statement_type
                )
                if item:
                    # Clear children to rebuild with promoted concepts
                    item.children = []

                    # Handle revenue deduplication first
                    promoted_added = set()
                    revenue_item = self._create_deduplicated_revenue_item(
                        REVENUE_CONCEPTS, nodes, period_maps, periods, statement_type
                    )
                    if revenue_item:
                        item.children.append(revenue_item)
                        # Mark all revenue concepts as processed
                        promoted_added.update(REVENUE_CONCEPTS)

                    # Add other promoted concepts that have values
                    for concept in ESSENTIAL_CONCEPTS:
                        if concept not in promoted_added and concept in nodes:
                            # Check if it has values in any period
                            has_values = any(
                                concept in period_maps[p] for p in periods
                            )
                            if has_values:
                                promoted_item = self._build_canonical_item(
                                    concept,
                                    nodes,
                                    period_maps,
                                    periods,
                                    depth=1,
                                    statement_type=statement_type
                                )
                                if promoted_item:
                                    # Override label for better display
                                    if concept == 'CostOfGoodsAndServicesSold':
                                        promoted_item.label = 'Cost of Revenue'

                                    promoted_item.children = []  # Don't show deep hierarchy
                                    item.children.append(promoted_item)
                                    promoted_added.add(concept)

                    # Then add other important concepts not in essential list
                    for child_concept in nodes.get(root_concept, {}).get('children', []):
                        if child_concept not in promoted_added:
                            child_item = self._build_canonical_item(
                                child_concept,
                                nodes,
                                period_maps,
                                periods,
                                depth=1,
                                statement_type=statement_type
                            )
                            if child_item:
                                item.children.append(child_item)

                    items.append(item)
                    break

        # If no abstract root, just build normally
        if not items:
            for root_concept in virtual_tree.get('roots', []):
                item = self._build_canonical_item(
                    root_concept,
                    nodes,
                    period_maps,
                    periods,
                    depth=0,
                    statement_type=statement_type
                )
                if item:
                    items.append(item)

        return items

    def _create_deduplicated_revenue_item(self,
                                        revenue_concepts: List[str],
                                        nodes: Dict[str, Any],
                                        period_maps: Dict[str, Dict[str, FinancialFact]],
                                        periods: List[str],
                                        statement_type: str) -> Optional[MultiPeriodItem]:
        """
        Create a single deduplicated revenue item by combining multiple revenue concepts.

        This method implements revenue deduplication for the Facts API path, similar to 
        what was done for XBRL processing. It combines revenue from different concepts
        across periods to show comprehensive revenue data. When no explicit revenue
        concepts exist, it attempts to calculate revenue from GrossProfit + CostOfRevenue.

        Args:
            revenue_concepts: List of revenue concepts in priority order
            nodes: Virtual tree nodes
            period_maps: Period-mapped fact data
            periods: List of periods
            statement_type: Statement type

        Returns:
            Single MultiPeriodItem with deduplicated revenue data or None if no revenue found
        """
        # Collect all revenue values across all concepts and periods
        consolidated_values = {}
        best_label = "Total Revenue"  # Default label
        has_any_revenue = False

        # Track which concept provides data for each period (for debugging/transparency)
        source_tracking = {}

        for period in periods:
            period_value = None
            source_concept = None

            # Try explicit revenue concepts in priority order for this period
            for concept in revenue_concepts:
                if concept in period_maps[period]:
                    fact = period_maps[period][concept]
                    if fact.numeric_value is not None:
                        period_value = fact.numeric_value
                        source_concept = concept
                        has_any_revenue = True

                        # Use the label from the first concept we find
                        if period_value is not None and not source_tracking:
                            best_label = fact.label if fact.label else "Total Revenue"

                        break  # Found value for this period, use highest priority

            # If no explicit revenue found, try to calculate from GrossProfit + CostOfRevenue
            if period_value is None:
                gross_profit = None
                cost_of_revenue = None

                # Look for GrossProfit
                if 'GrossProfit' in period_maps[period]:
                    gross_profit_fact = period_maps[period]['GrossProfit']
                    gross_profit = gross_profit_fact.numeric_value

                # Look for CostOfRevenue
                if 'CostOfRevenue' in period_maps[period]:
                    cost_fact = period_maps[period]['CostOfRevenue']
                    cost_of_revenue = cost_fact.numeric_value

                # Calculate revenue if both components are available
                if gross_profit is not None and cost_of_revenue is not None:
                    period_value = gross_profit + cost_of_revenue
                    source_concept = 'Calculated_Revenue'
                    has_any_revenue = True
                    # Debug output (disabled)
                    # print(f"DEBUG: Calculated revenue for {period}: ${period_value:,} (GP: ${gross_profit:,} + CoR: ${cost_of_revenue:,})")

            consolidated_values[period] = period_value
            if source_concept:
                source_tracking[period] = source_concept

        if not has_any_revenue:
            return None

        # Override label to be more descriptive
        best_label = "Total Revenue"

        # Find the highest priority concept that has data to determine other properties
        primary_concept = None
        for concept in revenue_concepts:
            if any(concept in period_maps[p] for p in periods):
                primary_concept = concept
                break

        # If no explicit revenue concepts, use a calculated concept identifier
        if not primary_concept:
            primary_concept = 'TotalRevenue_Consolidated'

        # Create the deduplicated revenue item
        revenue_item = MultiPeriodItem(
            concept=primary_concept,  # Use the highest priority concept as the base
            label=best_label,
            values=consolidated_values,
            depth=1,
            parent_concept=None,
            is_abstract=False,
            is_total=True,  # Revenue is typically a total
            section=None,
            confidence=0.95,  # High confidence for deduplicated revenue
            children=[]
        )

        return revenue_item

    def _build_canonical_item(self,
                             concept: str,
                             nodes: Dict[str, Any],
                             period_maps: Dict[str, Dict[str, FinancialFact]],
                             periods: List[str],
                             depth: int = 0,
                             statement_type: str = None) -> Optional[MultiPeriodItem]:
        """Build a single canonical item with multi-period values."""
        node = nodes.get(concept, {})

        # Get values for each period
        # Check both original concept and normalized version
        values = {}
        has_any_value = False
        for period in periods:
            # Try original concept first
            fact = period_maps[period].get(concept)
            # If not found, try normalized version
            if not fact:
                normalized = self._normalize_concept(concept)
                fact = period_maps[period].get(normalized)

            if fact:
                values[period] = fact.numeric_value
                has_any_value = True
            else:
                values[period] = None

        # Get label from first fact or node
        label = None
        for period in periods:
            fact = period_maps[period].get(concept)
            if fact:
                label = fact.label
                break
        if not label:
            label = node.get('label', concept)

        # Process children first to see if any have values
        children_items = []
        for child_concept in node.get('children', []):
            child_item = self._build_canonical_item(
                child_concept,
                nodes,
                period_maps,
                periods,
                depth + 1,
                statement_type=statement_type
            )
            if child_item:
                children_items.append(child_item)

        # Determine if we should include this node
        # Include if ANY of these are true:
        # 1. It has values
        # 2. It's abstract (structural node)
        # 3. It has children with values
        # 4. It's an essential concept for investors
        # 5. It has reasonable occurrence rate (>= 0.3)

        is_essential = statement_type and self._is_essential_concept(concept, statement_type)

        if not has_any_value and not node.get('is_abstract'):
            # Skip only if ALL of these are true:
            # - Not essential
            # - Low occurrence rate
            # - No children with values
            if not is_essential and node.get('occurrence_rate', 0) < 0.3 and not children_items:
                return None

        item = MultiPeriodItem(
            concept=concept,
            label=label,
            values=values,
            depth=depth,
            parent_concept=None,
            is_abstract=node.get('is_abstract', False),
            is_total=node.get('is_total', False),
            section=node.get('section'),
            confidence=node.get('occurrence_rate', 1.0),
            children=children_items
        )

        return item

    def _add_orphan_facts(self,
                         period_maps: Dict[str, Dict[str, FinancialFact]],
                         virtual_tree_nodes: Dict[str, Any],
                         periods: List[str],
                         statement_type: str) -> Optional[MultiPeriodItem]:
        """Add valuable facts not in virtual tree as 'Additional Items' section."""

        # Find all concepts that have values but aren't in the virtual tree
        orphan_concepts = set()
        for period_map in period_maps.values():
            for concept in period_map.keys():
                # Skip if already in virtual tree
                if concept not in virtual_tree_nodes:
                    # Check if this is an essential or important concept
                    if self._is_important_orphan(concept, statement_type):
                        orphan_concepts.add(concept)

        if not orphan_concepts:
            return None

        # Create orphan section
        orphan_section = MultiPeriodItem(
            concept='AdditionalItems',
            label='Additional Financial Items',
            values={},
            depth=0,
            parent_concept=None,
            is_abstract=True,
            is_total=False,
            section='Additional',
            confidence=1.0
        )

        # Add each orphan concept as a child
        for concept in sorted(orphan_concepts):
            # Get values for each period
            values = {}
            label = None
            has_values = False

            for period in periods:
                fact = period_maps[period].get(concept)
                if fact:
                    values[period] = fact.numeric_value
                    has_values = True
                    if not label:
                        label = fact.label
                else:
                    values[period] = None

            if has_values:
                orphan_item = MultiPeriodItem(
                    concept=concept,
                    label=label or concept,
                    values=values,
                    depth=1,
                    parent_concept='AdditionalItems',
                    is_abstract=False,
                    is_total=self._is_total_concept(concept, label),
                    section='Additional',
                    confidence=0.5  # Lower confidence for orphan facts
                )
                orphan_section.children.append(orphan_item)

        # Only return if we have actual orphan items
        return orphan_section if orphan_section.children else None

    def _is_important_orphan(self, concept: str, statement_type: str) -> bool:
        """Determine if an orphan concept is important enough to display."""

        # Check if it's an essential concept
        if self._is_essential_concept(concept, statement_type):
            return True

        # Check if it's a normalized version of an essential concept
        normalized = self._normalize_concept(concept)
        if normalized != concept and self._is_essential_concept(normalized, statement_type):
            return True

        # Additional important concepts not in essential list but valuable
        important_keywords = [
            # Balance Sheet
            'Debt', 'Receivable', 'Payable', 'Inventory', 'Investment',
            'Deferred', 'Accrued', 'Prepaid', 'Goodwill', 'Intangible',
            # Income Statement  
            'Revenue', 'Sales', 'Cost', 'Expense', 'Income', 'Profit', 'Loss',
            'Research', 'Marketing', 'Administrative', 'Interest', 'Tax',
            # Cash Flow
            'Depreciation', 'Amortization', 'Capital', 'Dividend', 'Acquisition',
            'Repurchase', 'Proceeds', 'Payments', 'Working'
        ]

        concept_lower = concept.lower()
        return any(keyword.lower() in concept_lower for keyword in important_keywords)

    def _is_total_concept(self, concept: str, label: str = None) -> bool:
        """Determine if a concept represents a total."""
        indicators = ['total', 'net', 'gross', 'subtotal', 'aggregate']
        concept_lower = concept.lower()
        label_lower = (label or '').lower()
        return any(ind in concept_lower or ind in label_lower for ind in indicators)

    def _add_calculated_metrics(self, 
                               period_maps: Dict[str, Dict[str, FinancialFact]],
                               periods: List[str],
                               existing_items: List[MultiPeriodItem]) -> List[MultiPeriodItem]:
        """Add calculated metrics like Gross Profit if not already present."""
        calculated_items = []

        # Check if GrossProfit exists in items
        has_gross_profit = any(
            self._find_item_by_concept(item, 'GrossProfit') 
            for item in existing_items
        )

        if not has_gross_profit:
            # Try to calculate Gross Profit = Revenue - Cost of Revenue
            gross_profit_values = {}
            has_values = False

            for period in periods:
                period_map = period_maps[period]

                # Find revenue (try various concepts)
                revenue = None
                revenue_concepts = [
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'Revenues', 'Revenue', 'SalesRevenueNet', 'TotalRevenues'
                ]
                for concept in revenue_concepts:
                    if concept in period_map:
                        revenue = period_map[concept].numeric_value
                        break

                # Find cost of revenue
                cost = None
                cost_concepts = [
                    'CostOfRevenue', 'CostOfGoodsAndServicesSold',
                    'CostOfGoodsSold', 'CostOfSales'
                ]
                for concept in cost_concepts:
                    if concept in period_map:
                        cost = period_map[concept].numeric_value
                        break

                # Calculate if both available
                if revenue is not None and cost is not None:
                    gross_profit_values[period] = revenue - cost
                    has_values = True
                else:
                    gross_profit_values[period] = None

            if has_values:
                gross_profit_item = MultiPeriodItem(
                    concept='GrossProfit_Calculated',
                    label='Gross Profit (Calculated)',
                    values=gross_profit_values,
                    depth=0,
                    parent_concept=None,
                    is_abstract=False,
                    is_total=True,
                    section='Calculated',
                    confidence=0.8
                )
                calculated_items.append(gross_profit_item)

        return calculated_items

    def _find_item_by_concept(self, item: MultiPeriodItem, concept: str) -> Optional[MultiPeriodItem]:
        """Recursively find an item by concept name."""
        if item.concept == concept:
            return item
        for child in item.children:
            found = self._find_item_by_concept(child, concept)
            if found:
                return found
        return None

    def _apply_smart_aggregation(self, item: MultiPeriodItem):
        """Apply smart aggregation to calculate parent values from children."""
        # Recursively process children first
        for child in item.children:
            self._apply_smart_aggregation(child)

        # Only aggregate if:
        # 1. Parent has no values
        # 2. Parent is not abstract (or is a total)
        # 3. Has children with values

        has_any_value = any(v is not None for v in item.values.values())

        if not has_any_value and item.children:
            # Check if this should be aggregated
            should_aggregate = (
                item.is_total or 
                'total' in item.label.lower() or
                (not item.is_abstract and self._should_aggregate_children(item))
            )

            if should_aggregate:
                # Aggregate values from children
                for period in item.values.keys():
                    child_sum = 0
                    has_child_values = False

                    for child in item.children:
                        child_value = child.values.get(period)
                        if child_value is not None:
                            # Skip if child is also abstract (unless it's a calculated total)
                            if not child.is_abstract or child.is_total:
                                child_sum += child_value
                                has_child_values = True

                    if has_child_values:
                        item.values[period] = child_sum
                        # Mark as aggregated
                        if not item.label.endswith(' (Aggregated)'):
                            item.label = item.label + ' (Aggregated)'

    def _deduplicate_table_items(self, items: List[MultiPeriodItem]) -> List[MultiPeriodItem]:
        """
        Remove redundant items from Statement [Table] structures when they duplicate primary items.

        This handles the XBRL quirk where the same concepts appear both:
        1. At the top level (primary context)
        2. Under Statement [Table] -> Statement [Line Items] (dimensional context)

        When there are no actual dimensions, these are pure duplicates.
        """
        # First, collect all concepts and their values from non-table contexts
        primary_concepts = {}

        def collect_primary_concepts(item: MultiPeriodItem, in_table: bool = False):
            """Collect concepts that are not in table structures."""
            # Check if we're entering a table
            if 'Table' in item.label and 'Statement' in item.label:
                in_table = True

            if not in_table and item.concept and item.values:
                # Store the concept and its values
                if any(v is not None for v in item.values.values()):
                    primary_concepts[item.concept] = item.values

            # Recurse through children
            for child in item.children:
                collect_primary_concepts(child, in_table)

        # Collect all primary (non-table) concepts
        for item in items:
            collect_primary_concepts(item)

        def remove_duplicate_table_items(item: MultiPeriodItem, in_table: bool = False) -> Optional[MultiPeriodItem]:
            """Remove items from table structures that duplicate primary items."""
            # Check if we're entering a table
            if 'Table' in item.label and 'Statement' in item.label:
                in_table = True

                # For table structures, check if ALL children are duplicates
                # If so, we might want to skip the entire table
                cleaned_children = []
                total_children = 0
                duplicate_children = 0

                for child in item.children:
                    total_children += 1
                    cleaned_child = remove_duplicate_table_items(child, in_table)
                    if cleaned_child:
                        cleaned_children.append(cleaned_child)
                    else:
                        duplicate_children += 1

                # If most children are duplicates and we have few remaining items,
                # consider removing the table entirely
                if cleaned_children and len(cleaned_children) > 2:
                    # Keep the table if it has meaningful content
                    item.children = cleaned_children
                    return item
                elif not cleaned_children:
                    # Table is entirely duplicates, remove it
                    return None
                else:
                    # Table has very little unique content, remove it
                    return None

            # For items within tables, check if they're duplicates
            if in_table and item.concept in primary_concepts:
                # Check if values match
                if item.values == primary_concepts[item.concept]:
                    # This is a duplicate, remove it (but keep exploring children
                    # in case they have unique dimensional breakdowns)
                    has_unique_children = False
                    cleaned_children = []

                    for child in item.children:
                        cleaned_child = remove_duplicate_table_items(child, in_table)
                        if cleaned_child:
                            cleaned_children.append(cleaned_child)
                            # Check if child has different values
                            if cleaned_child.concept not in primary_concepts or \
                               cleaned_child.values != primary_concepts.get(cleaned_child.concept):
                                has_unique_children = True

                    if has_unique_children:
                        # Keep this item as a container for unique children
                        item.children = cleaned_children
                        return item
                    else:
                        # Pure duplicate with no unique children
                        return None

            # For non-duplicate items, clean their children
            cleaned_children = []
            for child in item.children:
                cleaned_child = remove_duplicate_table_items(child, in_table)
                if cleaned_child:
                    cleaned_children.append(cleaned_child)

            item.children = cleaned_children
            return item

        # Process all top-level items
        cleaned_items = []
        for item in items:
            cleaned_item = remove_duplicate_table_items(item)
            if cleaned_item:
                cleaned_items.append(cleaned_item)

        return cleaned_items

    def _should_aggregate_children(self, item: MultiPeriodItem) -> bool:
        """Determine if children should be aggregated for this parent."""
        # Don't aggregate if children are heterogeneous (mix of assets/liabilities etc)
        # This is a simplified check - could be more sophisticated

        aggregatable_parents = [
            'CurrentAssets', 'NonCurrentAssets', 'TotalAssets',
            'CurrentLiabilities', 'NonCurrentLiabilities', 'TotalLiabilities',
            'OperatingExpenses', 'TotalExpenses', 'TotalRevenue'
        ]

        return any(parent in item.concept for parent in aggregatable_parents)

    def _build_from_facts(self,
                         period_facts: Dict[str, List[FinancialFact]],
                         periods: List[str]) -> List[MultiPeriodItem]:
        """Build items directly from facts without canonical structure."""
        # Simple approach - just list all unique concepts
        all_concepts = set()
        concept_labels = {}

        for period_facts_list in period_facts.values():
            for fact in period_facts_list:
                concept = fact.concept.split(':', 1)[-1] if ':' in fact.concept else fact.concept
                all_concepts.add(concept)
                concept_labels[concept] = fact.label

        items = []
        for concept in sorted(all_concepts):
            values = {}
            for period in periods:
                # Find fact for this concept in this period
                for fact in period_facts.get(period, []):
                    fact_concept = fact.concept.split(':', 1)[-1] if ':' in fact.concept else fact.concept
                    if fact_concept == concept:
                        values[period] = fact.numeric_value
                        break
                else:
                    values[period] = None

            item = MultiPeriodItem(
                concept=concept,
                label=concept_labels.get(concept, concept),
                values=values,
                depth=0,
                parent_concept=None
            )
            items.append(item)

        return items

    def _create_fact_map(self, facts: List[FinancialFact]) -> Dict[str, FinancialFact]:
        """Create concept -> fact mapping with normalization."""
        fact_map = {}
        for fact in facts:
            # Get clean concept name without namespace
            concept = fact.concept.split(':', 1)[-1] if ':' in fact.concept else fact.concept

            # Store under both original and normalized names
            # This allows matching both variants
            fact_map[concept] = fact

            normalized = self._normalize_concept(concept)
            if normalized != concept:
                # Also store under normalized name if different
                # Prefer normalized if not already present
                if normalized not in fact_map:
                    fact_map[normalized] = fact

            # Use most recent fact for duplicates
            if concept not in fact_map or fact.filing_date > fact_map[concept].filing_date:
                fact_map[concept] = fact
        return fact_map

    def _calculate_coverage(self, facts: List[FinancialFact], virtual_tree_key: str) -> float:
        """Calculate canonical coverage."""
        if virtual_tree_key not in self.virtual_trees:
            return 0.0

        canonical_concepts = set(self.virtual_trees[virtual_tree_key].get('nodes', {}).keys())
        if not canonical_concepts:
            return 0.0

        fact_concepts = set()
        for fact in facts:
            concept = fact.concept.split(':', 1)[-1] if ':' in fact.concept else fact.concept
            fact_concepts.add(concept)

        matched = len(fact_concepts & canonical_concepts)
        return matched / len(canonical_concepts)

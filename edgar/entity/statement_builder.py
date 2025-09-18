"""
Statement Builder for reconstructing financial statements using canonical structures.

This module provides intelligent statement reconstruction using learned canonical
structures and virtual presentation trees.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Set

from rich import box
from rich.columns import Columns
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.entity.mappings_loader import load_canonical_structures, load_virtual_trees
from edgar.entity.models import FinancialFact
from edgar.richtools import repr_rich

log = logging.getLogger(__name__)


@dataclass
class StatementItem:
    """A single item in a reconstructed financial statement."""
    concept: str
    label: str
    value: Optional[float]
    depth: int
    parent_concept: Optional[str]
    children: List['StatementItem'] = field(default_factory=list)

    # Metadata
    is_abstract: bool = False
    is_total: bool = False
    section: Optional[str] = None
    confidence: float = 1.0
    source: str = 'fact'  # 'fact', 'calculated', 'canonical', 'placeholder'

    # Original fact if available
    fact: Optional[FinancialFact] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'concept': self.concept,
            'label': self.label,
            'value': self.value,
            'depth': self.depth,
            'is_abstract': self.is_abstract,
            'is_total': self.is_total,
            'section': self.section,
            'confidence': self.confidence,
            'source': self.source,
            'children': [child.to_dict() for child in self.children]
        }

    def get_display_value(self) -> str:
        """Get formatted value for display."""
        if self.value is not None:
            if abs(self.value) >= 1_000_000_000:
                return f"${self.value/1_000_000_000:.1f}B"
            elif abs(self.value) >= 1_000_000:
                return f"${self.value/1_000_000:.1f}M"
            elif abs(self.value) >= 1_000:
                return f"${self.value/1_000:.0f}K"
            else:
                return f"${self.value:.0f}"
        elif self.is_abstract:
            return ""
        elif self.source == 'placeholder':
            return "[Missing]"
        else:
            return "-"

    def __rich__(self):
        """Create a rich representation of the statement item."""
        from rich.tree import Tree

        # Create the node label
        if self.is_abstract:
            label = Text(self.label, style="bold cyan")
        elif self.is_total:
            label = Text(self.label, style="bold yellow")
        else:
            style = "dim" if self.confidence < 0.8 else ""
            confidence_marker = " ◦" if self.confidence < 0.8 else ""
            label = Text(f"{self.label}{confidence_marker}", style=style)

        # Add value if present
        value_str = self.get_display_value()
        if value_str and value_str != "-":
            # Color code values
            if value_str.startswith("$") and self.value and isinstance(self.value, (int, float)):
                value_style = "red" if self.value < 0 else "green"
            else:
                value_style = ""

            label_with_value = Text.assemble(
                label,
                " ",
                (value_str, value_style)
            )
        else:
            label_with_value = label

        # Create tree with this item as root
        tree = Tree(label_with_value)

        # Add children
        for child in self.children:
            tree.add(child.__rich__())

        return tree

    def __repr__(self) -> str:
        """String representation using rich formatting."""
        return repr_rich(self.__rich__())


@dataclass
class StructuredStatement:
    """A complete structured financial statement."""
    statement_type: str
    fiscal_year: Optional[int]
    fiscal_period: Optional[str]
    period_end: Optional[date]

    items: List[StatementItem]

    # Metadata
    company_name: Optional[str] = None
    cik: Optional[str] = None
    canonical_coverage: float = 0.0
    facts_used: int = 0
    facts_total: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'statement_type': self.statement_type,
            'fiscal_year': self.fiscal_year,
            'fiscal_period': self.fiscal_period,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'company_name': self.company_name,
            'cik': self.cik,
            'canonical_coverage': self.canonical_coverage,
            'facts_used': self.facts_used,
            'facts_total': self.facts_total,
            'items': [item.to_dict() for item in self.items]
        }

    def get_hierarchical_display(self, max_depth: int = 3) -> str:
        """Get hierarchical text representation."""
        lines = []

        def add_item(item: StatementItem, indent: int = 0):
            if indent > max_depth:
                return

            indent_str = "  " * indent
            value_str = item.get_display_value()

            if item.is_abstract:
                lines.append(f"{indent_str}{item.label}")
            elif item.is_total:
                lines.append(f"{indent_str}{item.label:<40} {value_str:>15}")
                lines.append(f"{indent_str}{'-' * 55}")
            else:
                confidence_marker = "" if item.confidence > 0.8 else " *"
                lines.append(f"{indent_str}{item.label:<40} {value_str:>15}{confidence_marker}")

            for child in item.children:
                add_item(child, indent + 1)

        for item in self.items:
            add_item(item)

        return "\n".join(lines)

    def __rich__(self):
        """Create a rich representation of the structured statement."""
        # Statement type mapping for better display
        statement_names = {
            'IncomeStatement': 'Income Statement',
            'BalanceSheet': 'Balance Sheet', 
            'CashFlow': 'Cash Flow Statement',
            'StatementsOfComprehensiveIncome': 'Comprehensive Income',
            'StatementsOfShareholdersEquity': 'Shareholders Equity'
        }

        # Title with company name and period
        title_parts = []
        if self.company_name:
            title_parts.append((self.company_name, "bold green"))
        else:
            title_parts.append(("Financial Statement", "bold"))

        title = Text.assemble(*title_parts)

        # Subtitle with statement type and period
        statement_display = statement_names.get(self.statement_type, self.statement_type)
        if self.fiscal_period and self.fiscal_year:
            subtitle = f"{statement_display} • {self.fiscal_period} {self.fiscal_year}"
        elif self.period_end:
            subtitle = f"{statement_display} • As of {self.period_end}"
        else:
            subtitle = statement_display

        # Main statement table
        stmt_table = Table(
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 1),
            expand=True
        )
        stmt_table.add_column("Item", style="", ratio=3)
        stmt_table.add_column("Value", justify="right", style="bold", ratio=1)

        def add_item_to_table(item: StatementItem, depth: int = 0):
            """Add an item to the table with proper indentation."""
            indent = "  " * depth

            if item.is_abstract:
                # Abstract items are headers
                stmt_table.add_row(
                    Text(f"{indent}{item.label}", style="bold cyan"),
                    ""
                )
            elif item.is_total:
                # Total items with underline
                value_text = Text(item.get_display_value(), style="bold yellow")
                stmt_table.add_row(
                    Text(f"{indent}{item.label}", style="bold"),
                    value_text
                )
                # Add a separator line after totals
                if depth == 0:
                    stmt_table.add_row("", "")
                    stmt_table.add_row(
                        Text("─" * 40, style="dim"),
                        Text("─" * 15, style="dim")
                    )
            else:
                # Regular items
                style = "dim" if item.confidence < 0.8 else ""
                confidence_marker = " ◦" if item.confidence < 0.8 else ""
                label_text = f"{indent}{item.label}{confidence_marker}"

                # Color code positive/negative values
                value_str = item.get_display_value()
                if value_str and value_str.startswith("$"):
                    try:
                        # Extract numeric value for coloring
                        if item.value and isinstance(item.value, (int, float)):
                            if item.value < 0:
                                value_style = "red"
                            else:
                                value_style = "green"
                        else:
                            value_style = ""
                    except:
                        value_style = ""
                else:
                    value_style = ""

                stmt_table.add_row(
                    Text(label_text, style=style),
                    Text(value_str, style=value_style) if value_str else ""
                )

            # Add children recursively
            for child in item.children:
                if depth < 3:  # Limit depth for display
                    add_item_to_table(child, depth + 1)

        # Add all items to the table
        for item in self.items:
            add_item_to_table(item)

        # Metadata summary
        metadata = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        metadata.add_column("Metric", style="dim")
        metadata.add_column("Value", style="bold")

        metadata.add_row("Facts Used", f"{self.facts_used:,}")
        if self.facts_total > 0:
            metadata.add_row("Total Facts", f"{self.facts_total:,}")

        if self.canonical_coverage > 0:
            coverage_pct = self.canonical_coverage * 100
            coverage_style = "green" if coverage_pct >= 50 else "yellow" if coverage_pct >= 25 else "red"
            metadata.add_row(
                "Canonical Coverage",
                Text(f"{coverage_pct:.1f}%", style=coverage_style)
            )

        if self.cik:
            metadata.add_row("CIK", self.cik)

        # Data quality indicators
        quality_notes = []

        # Count items by confidence
        low_confidence_count = sum(
            1 for item in self._flatten_items()
            if not item.is_abstract and item.confidence < 0.8
        )

        if low_confidence_count > 0:
            quality_notes.append(
                Text(f"◦ {low_confidence_count} items with lower confidence", style="dim yellow")
            )

        # Count calculated vs actual values
        calculated_count = sum(
            1 for item in self._flatten_items()
            if item.source == 'calculated'
        )

        if calculated_count > 0:
            quality_notes.append(
                Text(f"◦ {calculated_count} calculated values", style="dim cyan")
            )

        # Combine metadata and quality notes
        metadata_panel = Panel(
            metadata,
            title="📊 Statement Metadata",
            border_style="bright_black"
        )

        # Create the main content group
        content_parts = [
            Padding("", (1, 0, 0, 0)),
            stmt_table
        ]

        # Add metadata in a column layout
        if self.facts_used > 0:
            bottom_content = [metadata_panel]

            if quality_notes:
                quality_panel = Panel(
                    Group(*quality_notes),
                    title="📝 Data Quality Notes",
                    border_style="bright_black"
                )
                bottom_content.append(quality_panel)

            content_parts.append(Padding("", (1, 0)))
            content_parts.append(Columns(bottom_content, equal=True, expand=True))

        content = Group(*content_parts)

        # Create the main panel
        return Panel(
            content,
            title=title,
            subtitle=subtitle,
            border_style="blue",
            expand=True
        )

    def _flatten_items(self) -> List[StatementItem]:
        """Flatten the hierarchical items into a flat list."""
        flat_items = []

        def flatten(item: StatementItem):
            flat_items.append(item)
            for child in item.children:
                flatten(child)

        for item in self.items:
            flatten(item)

        return flat_items

    def __repr__(self) -> str:
        """String representation using rich formatting."""
        return repr_rich(self.__rich__())


class StatementBuilder:
    """
    Builds structured financial statements using canonical templates.

    This class reconstructs complete financial statements by combining
    actual facts with canonical structures, filling in missing concepts
    and maintaining proper hierarchy.
    """

    def __init__(self, cik: Optional[str] = None):
        """
        Initialize the statement builder.

        Args:
            cik: Company CIK for context
        """
        self.cik = cik
        self.canonical_structures = load_canonical_structures()
        self.virtual_trees = load_virtual_trees()

    def build_statement(self, 
                       facts: List[FinancialFact],
                       statement_type: str,
                       fiscal_year: Optional[int] = None,
                       fiscal_period: Optional[str] = None,
                       use_canonical: bool = True,
                       include_missing: bool = False) -> StructuredStatement:
        """
        Build a structured financial statement from facts.

        Args:
            facts: List of financial facts
            statement_type: Type of statement (BalanceSheet, IncomeStatement, etc.)
            fiscal_year: Fiscal year to filter for
            fiscal_period: Fiscal period (FY, Q1, Q2, Q3, Q4)
            use_canonical: Whether to use canonical structure for organization
            include_missing: Whether to include placeholder for missing concepts

        Returns:
            StructuredStatement with hierarchical organization
        """
        # Filter facts for this statement and period
        filtered_facts = self._filter_facts(facts, statement_type, fiscal_year, fiscal_period)

        # Create fact lookup
        fact_map = self._create_fact_map(filtered_facts)

        # Get period end date
        period_end = self._get_period_end(filtered_facts)

        if use_canonical and statement_type in self.virtual_trees:
            # Build using canonical structure
            items = self._build_with_canonical(
                fact_map, 
                self.virtual_trees[statement_type],
                include_missing
            )

            # Add unmatched facts
            unmatched = self._find_unmatched_facts(fact_map, self.virtual_trees[statement_type])
            items.extend(self._create_items_from_facts(unmatched))
        else:
            # Build from facts only
            items = self._build_from_facts(fact_map)

        # Calculate metadata
        facts_used = len(fact_map)
        canonical_coverage = self._calculate_coverage(fact_map, statement_type) if use_canonical else 0.0

        return StructuredStatement(
            statement_type=statement_type,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            period_end=period_end,
            items=items,
            cik=self.cik,
            canonical_coverage=canonical_coverage,
            facts_used=facts_used,
            facts_total=len(facts)
        )

    def _filter_facts(self, facts: List[FinancialFact], 
                     statement_type: str,
                     fiscal_year: Optional[int],
                     fiscal_period: Optional[str]) -> List[FinancialFact]:
        """Filter facts for the requested statement and period."""
        filtered = []

        for fact in facts:
            # Check statement type
            if fact.statement_type != statement_type:
                continue

            # Check fiscal year
            if fiscal_year and fact.fiscal_year != fiscal_year:
                continue

            # Check fiscal period
            if fiscal_period and fact.fiscal_period != fiscal_period:
                continue

            filtered.append(fact)

        return filtered

    def _create_fact_map(self, facts: List[FinancialFact]) -> Dict[str, FinancialFact]:
        """Create a map of concept to fact."""
        fact_map = {}

        for fact in facts:
            # Extract clean concept name
            concept = fact.concept
            if ':' in concept:
                concept = concept.split(':', 1)[1]

            # Use most recent fact for duplicates
            if concept not in fact_map or fact.filing_date > fact_map[concept].filing_date:
                fact_map[concept] = fact

        return fact_map

    def _get_period_end(self, facts: List[FinancialFact]) -> Optional[date]:
        """Get the period end date from facts."""
        for fact in facts:
            if fact.period_end:
                return fact.period_end
        return None

    def _build_with_canonical(self, fact_map: Dict[str, FinancialFact],
                             virtual_tree: Dict[str, Any],
                             include_missing: bool) -> List[StatementItem]:
        """Build statement using canonical structure."""
        items = []
        processed = set()

        # Process root nodes
        for root_concept in virtual_tree.get('roots', []):
            item = self._build_canonical_item(
                root_concept, 
                virtual_tree['nodes'],
                fact_map,
                processed,
                include_missing,
                depth=0
            )
            if item:
                items.append(item)

        return items

    def _build_canonical_item(self, concept: str,
                             nodes: Dict[str, Any],
                             fact_map: Dict[str, FinancialFact],
                             processed: Set[str],
                             include_missing: bool,
                             depth: int = 0,
                             parent: Optional[str] = None) -> Optional[StatementItem]:
        """Build a single canonical item with children."""
        if concept in processed:
            return None

        processed.add(concept)

        # Get node info
        node = nodes.get(concept, {})

        # Check if we have a fact for this concept
        fact = fact_map.get(concept)

        # Determine if we should include this item
        if not fact and not include_missing and not node.get('is_abstract'):
            # Skip missing concrete concepts unless required
            if node.get('occurrence_rate', 0) < 0.8:  # Not a core concept
                return None

        # Create the item
        item = StatementItem(
            concept=concept,
            label=fact.label if fact else node.get('label', concept),
            value=fact.numeric_value if fact else None,
            depth=depth,
            parent_concept=parent,
            is_abstract=node.get('is_abstract', False),
            is_total=node.get('is_total', False),
            section=node.get('section'),
            confidence=node.get('occurrence_rate', 1.0) if not fact else 1.0,
            source='fact' if fact else ('canonical' if not include_missing else 'placeholder'),
            fact=fact
        )

        # Process children
        for child_concept in node.get('children', []):
            child_item = self._build_canonical_item(
                child_concept,
                nodes,
                fact_map,
                processed,
                include_missing,
                depth + 1,
                concept
            )
            if child_item:
                item.children.append(child_item)

        # Try to calculate total if missing
        if item.is_total and item.value is None and item.children:
            calculated_value = self._calculate_total(item.children)
            if calculated_value is not None:
                item.value = calculated_value
                item.source = 'calculated'

        return item

    def _calculate_total(self, children: List[StatementItem]) -> Optional[float]:
        """Calculate total from children values."""
        total = 0
        has_values = False

        for child in children:
            if not child.is_abstract and child.value is not None:
                total += child.value
                has_values = True

        return total if has_values else None

    def _find_unmatched_facts(self, fact_map: Dict[str, FinancialFact],
                             virtual_tree: Dict[str, Any]) -> Dict[str, FinancialFact]:
        """Find facts that don't match canonical concepts."""
        canonical_concepts = set(virtual_tree.get('nodes', {}).keys())
        unmatched = {}

        for concept, fact in fact_map.items():
            if concept not in canonical_concepts:
                unmatched[concept] = fact

        return unmatched

    def _create_items_from_facts(self, facts: Dict[str, FinancialFact]) -> List[StatementItem]:
        """Create statement items from unmatched facts."""
        items = []

        for concept, fact in facts.items():
            item = StatementItem(
                concept=concept,
                label=fact.label,
                value=fact.numeric_value,
                depth=1,  # Default depth
                parent_concept=None,
                is_abstract=fact.is_abstract,
                is_total=fact.is_total,
                section=fact.section,
                confidence=0.7,  # Lower confidence for unmatched
                source='fact',
                fact=fact
            )
            items.append(item)

        return items

    def _build_from_facts(self, fact_map: Dict[str, FinancialFact]) -> List[StatementItem]:
        """Build statement directly from facts without canonical structure."""
        # Group facts by parent
        hierarchy = defaultdict(list)
        roots = []

        for concept, fact in fact_map.items():
            if fact.parent_concept:
                hierarchy[fact.parent_concept].append(concept)
            else:
                roots.append(concept)

        # Build items recursively
        items = []
        for root_concept in roots:
            item = self._build_fact_item(root_concept, fact_map, hierarchy)
            if item:
                items.append(item)

        # Add orphaned facts
        for concept, fact in fact_map.items():
            if concept not in roots and not fact.parent_concept:
                item = StatementItem(
                    concept=concept,
                    label=fact.label,
                    value=fact.numeric_value,
                    depth=0,
                    parent_concept=None,
                    is_abstract=fact.is_abstract,
                    is_total=fact.is_total,
                    section=fact.section,
                    confidence=1.0,
                    source='fact',
                    fact=fact
                )
                items.append(item)

        return items

    def _build_fact_item(self, concept: str, 
                        fact_map: Dict[str, FinancialFact],
                        hierarchy: Dict[str, List[str]],
                        depth: int = 0) -> Optional[StatementItem]:
        """Build item from fact with children."""
        if concept not in fact_map:
            return None

        fact = fact_map[concept]

        item = StatementItem(
            concept=concept,
            label=fact.label,
            value=fact.numeric_value,
            depth=depth,
            parent_concept=fact.parent_concept,
            is_abstract=fact.is_abstract,
            is_total=fact.is_total,
            section=fact.section,
            confidence=1.0,
            source='fact',
            fact=fact
        )

        # Add children
        for child_concept in hierarchy.get(concept, []):
            child_item = self._build_fact_item(child_concept, fact_map, hierarchy, depth + 1)
            if child_item:
                item.children.append(child_item)

        return item

    def _calculate_coverage(self, fact_map: Dict[str, FinancialFact],
                          statement_type: str) -> float:
        """Calculate canonical coverage percentage."""
        if statement_type not in self.virtual_trees:
            return 0.0

        canonical_concepts = set(self.virtual_trees[statement_type].get('nodes', {}).keys())
        if not canonical_concepts:
            return 0.0

        matched = len(set(fact_map.keys()) & canonical_concepts)
        return matched / len(canonical_concepts)

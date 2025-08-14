"""
Enhanced financial statement that combines hierarchical structure with multi-period display.

This module provides an enhanced statement class that uses learned mappings
to show multiple periods with proper hierarchical organization.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from datetime import date
import pandas as pd
from collections import defaultdict

from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.console import Group
from rich import box
from rich.padding import Padding

from edgar.entity.models import FinancialFact
from edgar.entity.mappings_loader import load_learned_mappings, load_virtual_trees
from edgar.entity.statement_builder import StatementItem
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
        # Statement type mapping
        statement_names = {
            'IncomeStatement': 'Income Statement',
            'BalanceSheet': 'Balance Sheet',
            'CashFlow': 'Cash Flow Statement'
        }
        
        # Title
        title_parts = []
        if self.company_name:
            title_parts.append((self.company_name, "bold green"))
        else:
            title_parts.append(("Financial Statement", "bold"))
        
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
                row.append(Text(f"{indent}{item.label}", style="bold cyan"))
            elif item.is_total:
                row.append(Text(f"{indent}{item.label}", style="bold"))
            else:
                style = "dim" if item.confidence < 0.8 else ""
                confidence_marker = " ◦" if item.confidence < 0.8 else ""
                row.append(Text(f"{indent}{item.label}{confidence_marker}", style=style))
            
            # Period values
            for period in self.periods:
                value_str = item.get_display_value(period, concise_format=self.concise_format)
                if value_str and value_str != "-":
                    # Color code values
                    value = item.values.get(period)
                    if value and isinstance(value, (int, float)):
                        value_style = "red" if value < 0 else "green"
                    else:
                        value_style = ""
                    
                    if item.is_total:
                        row.append(Text(value_str, style=f"bold yellow {value_style}"))
                    else:
                        row.append(Text(value_str, style=value_style))
                else:
                    row.append("")
            
            stmt_table.add_row(*row)
            
            # Add separator line after totals
            if item.is_total and depth == 0:
                separator_row = [Text("─" * 40, style="dim")]
                for _ in self.periods:
                    separator_row.append(Text("─" * 15, style="dim"))
                stmt_table.add_row(*separator_row)
            
            # Add children
            for child in item.children:
                if depth < 3:
                    add_item_to_table(child, depth + 1)
        
        # Add all items
        for item in self.items:
            add_item_to_table(item)
        
        # Metadata
        metadata_text = []
        if self.canonical_coverage > 0:
            coverage_pct = self.canonical_coverage * 100
            coverage_style = "green" if coverage_pct >= 50 else "yellow" if coverage_pct >= 25 else "red"
            metadata_text.append(
                Text.assemble(
                    "Canonical Coverage: ",
                    (f"{coverage_pct:.1f}%", coverage_style)
                )
            )
        
        metadata_text.append(Text(f"Periods: {len(self.periods)}", style="dim"))
        
        # Combine content
        content_parts = [
            Padding("", (1, 0, 0, 0)),
            stmt_table
        ]
        
        if metadata_text:
            metadata_panel = Panel(
                Group(*metadata_text),
                title="📊 Metadata",
                border_style="bright_black"
            )
            content_parts.append(Padding("", (1, 0)))
            content_parts.append(metadata_panel)
        
        content = Group(*content_parts)
        
        return Panel(
            content,
            title=title,
            subtitle=subtitle,
            border_style="blue",
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
        from datetime import date
        
        # Filter facts by statement type
        # Handle both 'CashFlow' and 'CashFlowStatement' for compatibility
        if statement_type == 'CashFlow':
            stmt_facts = [f for f in facts if f.statement_type in ['CashFlow', 'CashFlowStatement']]
        else:
            stmt_facts = [f for f in facts if f.statement_type == statement_type]
        
        # Use the same logic as FactQuery.latest_periods for consistency
        # Group facts by unique periods and calculate period info
        period_info = {}
        period_facts = defaultdict(list)
        
        for fact in stmt_facts:
            period_key = (fact.fiscal_year, fact.fiscal_period)
            period_label = f"{fact.fiscal_period} {fact.fiscal_year}"
            
            # Store facts by period label
            period_facts[period_label].append(fact)
            
            # Store period metadata
            if period_key not in period_info:
                period_info[period_key] = {
                    'label': period_label,
                    'end_date': fact.period_end or date.max,
                    'is_annual': fact.fiscal_period == 'FY',
                    'filing_date': fact.filing_date or date.min,
                    'fiscal_year': fact.fiscal_year,
                    'fiscal_period': fact.fiscal_period
                }
        
        # Create list of periods with their metadata
        period_list = []
        for period_key, info in period_info.items():
            period_list.append((period_key, info))
        
        if annual:
            # When annual=True, only use annual periods - no backfilling with interim periods
            annual_periods = [(pk, info) for pk, info in period_list if info['is_annual']]
            
            # Sort annual periods by fiscal year (newest first)
            annual_periods.sort(key=lambda x: x[0][0] if x[0][0] else 0, reverse=True)
            
            # Select only annual periods, up to n
            selected_period_info = annual_periods[:periods]
        else:
            # Sort all periods by end date (newest first)
            period_list.sort(key=lambda x: x[1]['end_date'], reverse=True)
            selected_period_info = period_list[:periods]
        
        # Extract period labels for selected periods
        selected_periods = [info['label'] for _, info in selected_period_info]
        
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
            items = self._build_with_canonical(period_facts, selected_periods, virtual_tree_key)
            canonical_coverage = self._calculate_coverage(stmt_facts, virtual_tree_key)
        else:
            items = self._build_from_facts(period_facts, selected_periods)
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
                    
                    # Add promoted concepts that have values
                    promoted_added = set()
                    for concept in ESSENTIAL_CONCEPTS:
                        if concept in nodes:
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
                                    if concept == 'RevenueFromContractWithCustomerExcludingAssessedTax':
                                        promoted_item.label = 'Total Revenue'
                                    elif concept == 'CostOfGoodsAndServicesSold':
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
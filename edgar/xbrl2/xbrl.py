"""
XBRL Parser - Top-level integration module for XBRL parsing.

This module provides the XBRL class, which integrates all components of the XBRL parsing system:
- Instance Document Parser
- Presentation Linkbase Parser
- Calculation Linkbase Parser
- Definition Linkbase Parser

The XBRL class provides a unified interface for working with XBRL data,
organizing facts according to presentation hierarchies, validating calculations,
and handling dimensional qualifiers.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

import pandas as pd
from rich.table import Table as RichTable

# Import legacy XBRL data for compatibility
from edgar.xbrl.instance import XBRLInstance as LegacyXbrlInstance
from edgar.xbrl2.core import STANDARD_LABEL
# Import refactored components
from edgar.xbrl2.models import (
    Fact, PresentationNode, XBRLProcessingError
)
from edgar.xbrl2.parser import XBRLParser
from edgar.xbrl2.rendering import render_statement, generate_rich_representation


class XBRL:
    """
    Integrated XBRL parser that combines all linkbase parsers.
    
    This is the top-level object that integrates all components of the XBRL parsing system,
    providing access to facts organized according to presentation hierarchies and
    allowing for dimensional analysis and calculation validation.
    """
    
    def __init__(self):
        # Use the parser component
        self.parser = XBRLParser()
        
        # Reference to legacy XBRLInstance for compatibility
        self.legacy_instance: Optional[LegacyXbrlInstance] = None
        
    @property
    def element_catalog(self):
        return self.parser.element_catalog
        
    @property
    def contexts(self):
        return self.parser.contexts
        
    @property
    def facts(self):
        return self.parser.facts
        
    @property
    def units(self):
        return self.parser.units
        
    @property
    def presentation_roles(self):
        return self.parser.presentation_roles
        
    @property
    def presentation_trees(self):
        return self.parser.presentation_trees
        
    @property
    def calculation_roles(self):
        return self.parser.calculation_roles
        
    @property
    def calculation_trees(self):
        return self.parser.calculation_trees
        
    @property
    def definition_roles(self):
        return self.parser.definition_roles
        
    @property
    def tables(self):
        return self.parser.tables
        
    @property
    def axes(self):
        return self.parser.axes
        
    @property
    def domains(self):
        return self.parser.domains
        
    @property
    def entity_info(self):
        return self.parser.entity_info
        
    @property
    def reporting_periods(self):
        return self.parser.reporting_periods
        
    @property
    def context_period_map(self):
        return self.parser.context_period_map
    
    @classmethod
    def parse_directory(cls, directory_path: Union[str, Path]) -> 'XBRL':
        """
        Parse all XBRL files in a directory.
        
        Args:
            directory_path: Path to directory containing XBRL files
            
        Returns:
            XBRL object with parsed data
        """
        xbrl = cls()
        xbrl.parser.parse_directory(directory_path)
        
        # Try to create legacy instance as well for compatibility
        directory = Path(directory_path)
        instance_file = None
        for file_path in directory.glob("*"):
            if file_path.is_file() and file_path.name.lower().endswith('.xml') and '<xbrl' in file_path.read_text()[:2000]:
                instance_file = file_path
                break
                
        try:
            if instance_file:
                xbrl.legacy_instance = LegacyXbrlInstance.parse(instance_file.read_text())
        except Exception:
            xbrl.legacy_instance = None
        
        return xbrl
    
    @classmethod
    def from_files(cls, instance_file: Optional[Union[str, Path]] = None,
                  schema_file: Optional[Union[str, Path]] = None,
                  presentation_file: Optional[Union[str, Path]] = None,
                  calculation_file: Optional[Union[str, Path]] = None,
                  definition_file: Optional[Union[str, Path]] = None,
                  label_file: Optional[Union[str, Path]] = None) -> 'XBRL':
        """
        Create an XBRL object from individual files.
        
        Args:
            instance_file: Path to instance document file
            schema_file: Path to schema file
            presentation_file: Path to presentation linkbase file
            calculation_file: Path to calculation linkbase file
            definition_file: Path to definition linkbase file
            label_file: Path to label linkbase file
            
        Returns:
            XBRL object with parsed data
        """
        xbrl = cls()
        
        # Parse schema first
        if schema_file:
            xbrl.parser.parse_schema(schema_file)
        
        # Parse linkbase files
        if label_file:
            xbrl.parser.parse_labels(label_file)
        
        if presentation_file:
            xbrl.parser.parse_presentation(presentation_file)
        
        if calculation_file:
            xbrl.parser.parse_calculation(calculation_file)
        
        if definition_file:
            xbrl.parser.parse_definition(definition_file)
        
        # Parse instance last
        if instance_file:
            xbrl.parser.parse_instance(instance_file)
        
        # Try to create legacy instance for compatibility
        try:
            if instance_file:
                instance_content = Path(instance_file).read_text() if isinstance(instance_file, (str, Path)) else instance_file
                xbrl.legacy_instance = LegacyXbrlInstance.parse(instance_content)
        except Exception:
            xbrl.legacy_instance = None
        
        return xbrl
    
    @classmethod
    def from_filing(cls, filing) -> 'XBRL':
        """
        Create an XBRL object from a Filing object.
        
        Args:
            filing: Filing object with attachments containing XBRL files
            
        Returns:
            XBRL object with parsed data
        """
        from edgar.xbrl.xbrldata import XBRLAttachments
        
        xbrl = cls()
        
        # Get XBRL attachments from filing
        xbrl_attachments = XBRLAttachments(filing.attachments)
        
        if xbrl_attachments.empty:
            raise XBRLProcessingError("No XBRL attachments found in filing")
        
        # Get content and parse
        if xbrl_attachments.get('schema'):
            xbrl.parser.parse_schema_content(xbrl_attachments.get('schema').content)
        
        if xbrl_attachments.get('label'):
            xbrl.parser.parse_labels_content(xbrl_attachments.get('label').content)
        
        if xbrl_attachments.get('presentation'):
            xbrl.parser.parse_presentation_content(xbrl_attachments.get('presentation').content)
        
        if xbrl_attachments.get('calculation'):
            xbrl.parser.parse_calculation_content(xbrl_attachments.get('calculation').content)
        
        if xbrl_attachments.get('definition'):
            xbrl.parser.parse_definition_content(xbrl_attachments.get('definition').content)
        
        if xbrl_attachments.get('instance'):
            xbrl.parser.parse_instance_content(xbrl_attachments.get('instance').content)
        
        # Try to create legacy instance for compatibility
        try:
            if xbrl_attachments.get('instance'):
                xbrl.legacy_instance = LegacyXbrlInstance.parse(xbrl_attachments.get('instance').content)
        except Exception:
            xbrl.legacy_instance = None
        
        return xbrl

    @property
    def statements(self):
        from edgar.xbrl2.statements import Statements
        return Statements(self)
    
    def get_all_statements(self) -> List[Dict[str, Any]]:
        """
        Get all available financial statements.
        
        Returns:
            List of statement metadata (role, definition, element count)
        """
        statements = []
        
        # Standard taxonomy concepts for statement identification
        standard_statement_concepts = {
            'BalanceSheet': ['us-gaap_StatementOfFinancialPositionAbstract', 
                             'us-gaap_StatementOfFinancialPositionClassifiedAbstract'],
            'IncomeStatement': ['us-gaap_IncomeStatementAbstract', 
                                'us-gaap_StatementOfIncomeAbstract'],
            'CashFlowStatement': ['us-gaap_StatementOfCashFlowsAbstract'],
            'StatementOfEquity': ['us-gaap_StatementOfStockholdersEquityAbstract',
                                  'us-gaap_StatementOfShareholdersEquityAbstract'],
            'ComprehensiveIncome': ['us-gaap_StatementOfComprehensiveIncomeAbstract',
                                    'us-gaap_StatementOfIncome'],
        }
        
        for role, tree in self.presentation_trees.items():
            # Check if this role appears to be a financial statement
            role_def = tree.definition.lower()
            statement_type = None
            
            # First try to identify by standard taxonomy concepts
            for stmt_type, concepts in standard_statement_concepts.items():
                for element_id in tree.all_nodes:
                    if any(element_id.endswith(concept) for concept in concepts):
                        statement_type = stmt_type
                        break
                if statement_type:
                    break
            
            # Fallback to keyword matching in role definition if no concept match
            if not statement_type:
                if any(term in role_def for term in ['balance sheet', 'financial position']):
                    statement_type = 'BalanceSheet'
                elif any(term in role_def for term in ['income', 'profit and loss', 'operations']):
                    statement_type = 'IncomeStatement'
                elif any(term in role_def for term in ['cash flow']):
                    statement_type = 'CashFlowStatement'
                elif any(term in role_def for term in ['equity', 'stockholder', 'shareholder']):
                    statement_type = 'StatementOfEquity'
                elif any(term in role_def for term in ['comprehensive income']):
                    statement_type = 'ComprehensiveIncome'
            
            statements.append({
                'role': role,
                'definition': tree.definition,
                'element_count': len(tree.all_nodes),
                'type': statement_type
            })
        
        return statements
        
    def get_statement_by_type(self, statement_type: str) -> Optional[Dict[str, Any]]:
        """
        Get the first statement matching the given type.
        
        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            
        Returns:
            Statement data if found, None otherwise
        """
        # Get all statements
        statements = self.get_all_statements()
        
        # Find the first matching statement
        for statement in statements:
            if statement['type'] == statement_type:
                # Get statement data
                role = statement['role']
                statement_data = self.get_statement_data(role)
                
                if statement_data:
                    return {
                        'role': role,
                        'definition': statement['definition'],
                        'statement_type': statement_type,
                        'periods': statement_data['periods'],
                        'data': statement_data['statement_data']
                    }
        
        return None

    @classmethod
    def stitch_statements(cls, xbrl_list: List['XBRL'], 
                        statement_type: str = 'IncomeStatement',
                        period_type: str = 'RECENT_PERIODS',
                        max_periods: int = 3,
                        standard: bool = True) -> Dict[str, Any]:
        """
        Stitch together statements from multiple XBRL objects.
        
        Args:
            xbrl_list: List of XBRL objects, should be from the same company and ordered by date
            statement_type: Type of statement to stitch ('IncomeStatement', 'BalanceSheet', etc.)
            period_type: Type of period view to generate
            max_periods: Maximum number of periods to include (default: 3)
            standard: Whether to use standardized concept labels (default: True)
            
        Returns:
            Stitched statement data
        """
        from edgar.xbrl2.stitching import stitch_statements as _stitch_statements
        return _stitch_statements(xbrl_list, statement_type, period_type, max_periods, standard)

    def render_stitched_statement(self, stitched_data: Dict[str, Any],
                                statement_title: str,
                                statement_type: str) -> 'RichTable':
        """
        Render a stitched statement.
        
        Args:
            stitched_data: Stitched statement data
            statement_title: Title of the statement
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            
        Returns:
            RichTable: A formatted table representation of the stitched statement
        """
        from edgar.xbrl2.stitching import render_stitched_statement as _render_stitched_statement
        return _render_stitched_statement(stitched_data, statement_title, statement_type, self.entity_info)
    
    def get_statement(self, role_or_type: str, period_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get a financial statement by role URI, statement type, or statement short name.
        
        Args:
            role_or_type: Can be one of:
                - Extended link role URI (e.g. "http://apple.com/role/ConsolidatedStatementOfIncome")
                - Statement type name (e.g. "BalanceSheet")
                - Statement short name (e.g. "ConsolidatedStatementOfIncome")
            period_filter: Optional period key to filter facts
            
        Returns:
            List of line items with values
        """
        # If requesting by full role URI, use as is
        if role_or_type.startswith('http'):
            role_uri = role_or_type
        else:
            # Check if it's a statement type
            all_statements = self.get_all_statements()
            
            # First try to match by type (e.g., "BalanceSheet")
            matching_statements = [stmt for stmt in all_statements if stmt['type'] == role_or_type]
            
            # If not found by type, try to match by the last part of the role URI (short name)
            if not matching_statements:
                for stmt in all_statements:
                    # Extract the short name from the role (last part after / or #)
                    role = stmt['role']
                    short_name = role.split('/')[-1] if '/' in role else role.split('#')[-1] if '#' in role else ''
                    
                    # Also try to extract from the definition if available
                    definition_short_name = ''
                    if 'definition' in stmt and stmt['definition']:
                        # Remove spaces and standardize
                        definition_words = ''.join(stmt['definition'].split())
                        if definition_words:
                            definition_short_name = definition_words
                    
                    # Check if either short name matches
                    if (short_name and short_name.lower() == role_or_type.lower()) or \
                       (definition_short_name and definition_short_name.lower() == role_or_type.lower()):
                        matching_statements.append(stmt)
            
            # If found, use the role
            if matching_statements:
                role_uri = matching_statements[0]['role']
            else:
                return []  # No matching statement found
        
        if role_uri not in self.presentation_trees:
            return []
        
        tree = self.presentation_trees[role_uri]
        
        # Find the root element
        root_id = tree.root_element_id
        
        # Generate line items recursively
        line_items = []
        self._generate_line_items(root_id, tree.all_nodes, line_items, period_filter)
        
        return line_items
    
    def _generate_line_items(self, element_id: str, nodes: Dict[str, PresentationNode], 
                            result: List[Dict[str, Any]], period_filter: Optional[str] = None, 
                            path: List[str] = None) -> None:
        """
        Recursively generate line items for a statement.
        
        Args:
            element_id: Current element ID
            nodes: Dictionary of presentation nodes
            result: List to append line items to
            period_filter: Optional period key to filter facts
            path: Current path in hierarchy
        """
        if element_id not in nodes:
            return
        
        # Update path
        if path is None:
            path = []
        
        current_path = path + [element_id]
        
        # Get node information
        node = nodes[element_id]
        
        # Get label
        label = node.display_label
        
        # Get values and decimals across periods
        values = {}
        decimals = {}  # Store decimals info for each period
        
        # Try to determine the actual concept name used in facts
        # First, get the element name from node or catalog
        element_name = None
        concept_names = []
        
        # Try node's element_name
        if node.element_name:
            concept_names.append(node.element_name)
            
        # Try element catalog name
        if element_id in self.element_catalog:
            catalog_name = self.element_catalog[element_id].name
            if catalog_name:
                concept_names.append(catalog_name)
        
        # Try element ID itself (often used in facts)
        concept_names.append(element_id)

        # Try additional variations of element names
        additional_names = []
        for name in concept_names:
            # Try with common variations
            if ":" not in name and "_" not in name:
                additional_names.extend([
                    f"us-gaap:{name}",
                    f"ifrs:{name}"
                ])
            # Convert underscore to colon (us-gaap_Cash -> us-gaap:Cash)
            elif "_" in name and ":" not in name:
                # Handle us-gaap_ElementName pattern
                parts = name.split("_", 1)
                if len(parts) == 2 and parts[0] in ['us-gaap', 'ifrs', 'dei']:
                    additional_names.append(f"{parts[0]}:{parts[1]}")
        
        concept_names.extend(additional_names)
        
        # Remove duplicates
        concept_names = list(set(concept_names))
            
        # Find facts for any of these concept names
        all_relevant_facts = {}
        for concept_name in concept_names:
            relevant_facts = self._find_facts_for_element(concept_name, period_filter)
            all_relevant_facts.update(relevant_facts)
            
        # Group facts by period for better selection
        facts_by_period = {}
        
        # Process all found facts and group by period
        for context_id, fact in all_relevant_facts.items():
            # Get period key for this context
            period_key = self.context_period_map.get(context_id)
            if not period_key:
                continue  # Skip if no period key found
                
            # Initialize period entry if not exists
            if period_key not in facts_by_period:
                facts_by_period[period_key] = []
                
            # Add this fact to the period
            facts_by_period[period_key].append((context_id, fact))
        
        # Process facts by period, selecting the most appropriate fact for each period
        for period_key, period_facts in facts_by_period.items():
            # If only one fact, use it
            if len(period_facts) == 1:
                context_id, fact = period_facts[0]
            else:
                # Multiple facts for same period - prioritize based on dimensions
                # Sort facts by preference: no dimensions first, then by dimension count (fewer dimensions preferred)
                sorted_facts = []
                for ctx_id, f in period_facts:
                    context = self.contexts.get(ctx_id)
                    dimension_count = len(context.dimensions) if context and hasattr(context, 'dimensions') else 999
                    sorted_facts.append((dimension_count, ctx_id, f))
                
                # Sort by dimension count (no dimensions or fewer dimensions first)
                sorted_facts.sort()
                
                # Use the first fact (with fewest dimensions)
                _, context_id, fact = sorted_facts[0]
            
            # Store the value
            values[period_key] = fact.numeric_value if fact.numeric_value is not None else fact.value
            
            # Store the decimals info for proper scaling
            if fact.decimals is not None:
                try:
                    if fact.decimals == 'INF':
                        decimals[period_key] = 0  # Infinite precision, no scaling
                    else:
                        decimals[period_key] = int(fact.decimals)
                except (ValueError, TypeError):
                    decimals[period_key] = 0  # Default if decimals can't be converted
        
        # Create line item
        line_item = {
            'concept': element_id,
            'name': concept_names[0] if concept_names else None,
            'all_names': concept_names,
            'label': label,
            'values': values,
            'decimals': decimals,  # Add decimals info for formatting
            'level': node.depth,
            'preferred_label': node.preferred_label,
            'is_abstract': node.is_abstract,
            'children': node.children,
            'has_values': len(values) > 0  # Flag to indicate if we found values
        }
        
        # Add to result
        result.append(line_item)
        
        # Process children
        for child_id in node.children:
            self._generate_line_items(child_id, nodes, result, period_filter, current_path)
    
    def _find_facts_for_element(self, element_name: str, period_filter: Optional[str] = None) -> Dict[str, Fact]:
        """
        Find facts for a specific element, optionally filtered by period.
        
        Args:
            element_name: Element name to find facts for
            period_filter: Optional period key to filter contexts
            
        Returns:
            Dictionary of facts by context ID
        """
        if not element_name:
            return {}  # No element name provided
            
        relevant_facts = {}
        
        # Exact match - check if the element name is a direct key in the facts dictionary
        for context_id in self.contexts:
            # Try original key
            exact_match_key = f"{element_name}_{context_id}"
            
            # Also try colon/underscore substitution variations
            alternative_keys = [exact_match_key]
            
            # If element name has colon, also try with underscore
            if ':' in element_name:
                parts = element_name.split(':', 1)
                if len(parts) == 2 and parts[0] in ['us-gaap', 'ifrs', 'dei']:
                    alternative_keys.append(f"{parts[0]}_{parts[1]}_{context_id}")
            # If element name has underscore, also try with colon
            elif '_' in element_name:
                parts = element_name.split('_', 1)
                if len(parts) == 2 and parts[0] in ['us-gaap', 'ifrs', 'dei']:
                    alternative_keys.append(f"{parts[0]}:{parts[1]}_{context_id}")
            
            # Try all key variations
            for key in alternative_keys:
                if key in self.facts:
                    fact = self.facts[key]
                    # If period filter is specified, check if context matches period
                    if period_filter:
                        period_key = self.context_period_map.get(context_id)
                        if period_key == period_filter:
                            relevant_facts[context_id] = fact
                    else:
                        relevant_facts[context_id] = fact
        
        # If we found exact matches, return them
        return relevant_facts

    
    def get_period_views(self, statement_type: str) -> List[Dict[str, Any]]:
        """
        Get available period views for a statement type.
        
        Args:
            statement_type: Type of statement to get period views for
            
        Returns:
            List of period view options with name, description, and period keys
        """
        period_views = []
        
        # Sort periods by their end dates for easier matching
        instant_periods = sorted(
            [p for p in self.reporting_periods if p['type'] == 'instant'],
            key=lambda x: x['date'],
            reverse=True  # Latest first
        )
        
        duration_periods = sorted(
            [p for p in self.reporting_periods if p['type'] == 'duration'],
            key=lambda x: (x['end_date'], x['start_date']),
            reverse=True  # Latest first
        )
        
        # Group duration periods by length (year-to-date, quarter, etc.)
        duration_groups = {}
        for period in duration_periods:
            try:
                start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                days = (end_date - start_date).days
                if days not in duration_groups:
                    duration_groups[days] = []
                duration_groups[days].append(period)
            except (ValueError, TypeError):
                # Skip if dates can't be parsed
                pass
        
        # Get relevant entity info
        entity_info = self.entity_info
        fiscal_year = entity_info.get('fiscal_year')
        annual_report = entity_info.get('annual_report', False)
        quarterly_report = entity_info.get('quarterly_report', False)
        document_type = entity_info.get('document_type', '')
        
        # Create different views based on statement type
        if statement_type in ['BalanceSheet']:
            # For Balance Sheet, we can show different years/quarters as columns
            if len(instant_periods) >= 2:
                # Create views with multiple periods
                if len(instant_periods) >= 3:
                    # Three-year view
                    period_views.append({
                        'name': 'Three-Year Comparison',
                        'description': 'Shows the most recent three periods',
                        'period_keys': [instant_periods[0]['key'], instant_periods[1]['key'], instant_periods[2]['key']]
                    })
                
                # Current period vs. Previous period (always included)
                period_views.append({
                    'name': 'Current vs. Previous Period',
                    'description': 'Shows the current period and the previous period',
                    'period_keys': [instant_periods[0]['key'], instant_periods[1]['key']]
                })
            
            # If we have more periods, show annual comparisons
            annual_periods = []
            for period in instant_periods:
                if annual_report and ('fiscal_year_end_month' in entity_info and 
                                    'fiscal_year_end_day' in entity_info):
                    # Check if this is an annual period (close to fiscal year end)
                    try:
                        period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                        fiscal_month = entity_info.get('fiscal_year_end_month')
                        fiscal_day = entity_info.get('fiscal_year_end_day')
                        
                        # Check if this date is close to fiscal year end
                        if (abs(period_date.month - fiscal_month) <= 1 and 
                            abs(period_date.day - fiscal_day) <= 15):
                            annual_periods.append(period)
                    except (ValueError, TypeError):
                        pass
                else:
                    # Without fiscal info, just use the period
                    annual_periods.append(period)
            
            if len(annual_periods) >= 2:
                if len(annual_periods) >= 3:
                    period_views.append({
                        'name': 'Three-Year Annual Comparison',
                        'description': 'Shows three fiscal years for comparison',
                        'period_keys': [p['key'] for p in annual_periods[:3]]
                    })
                
                period_views.append({
                    'name': 'Annual Comparison',
                    'description': 'Shows two fiscal years for comparison',
                    'period_keys': [p['key'] for p in annual_periods[:min(2, len(annual_periods))]]
                })
            
        elif statement_type in ['IncomeStatement', 'CashFlowStatement']:
            # For Income Statement and Cash Flow, we need to consider duration periods
            
            # First, identify different types of periods (annual, quarterly, etc.)
            annual_periods = []
            quarterly_periods = []
            ytd_periods = []
            
            for period in duration_periods:
                try:
                    start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                    end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                    days = (end_date - start_date).days
                    
                    # Determine period type by duration
                    if 350 <= days <= 380:  # Annual: 350-380 days
                        annual_periods.append(period)
                    elif 85 <= days <= 95:  # Quarterly: 85-95 days
                        quarterly_periods.append(period)
                    elif 175 <= days <= 190:  # Year-to-date (6 months): 175-190 days
                        ytd_periods.append(period)
                    elif 265 <= days <= 285:  # Year-to-date (9 months): 265-285 days
                        ytd_periods.append(period)
                except (ValueError, TypeError):
                    # Skip periods with invalid dates
                    pass
            
            # Generate views based on available periods
            
            # Annual comparisons
            if len(annual_periods) >= 2:
                # Three-year view if available
                if len(annual_periods) >= 3:
                    period_views.append({
                        'name': 'Three-Year Comparison',
                        'description': 'Compares three fiscal years',
                        'period_keys': [p['key'] for p in annual_periods[:3]]
                    })
                
                # Default two-year view
                period_views.append({
                    'name': 'Annual Comparison',
                    'description': 'Compares recent fiscal years',
                    'period_keys': [p['key'] for p in annual_periods[:min(2, len(annual_periods))]]
                })
            
            # Quarterly comparisons
            if len(quarterly_periods) >= 2:
                # Current quarter vs. same quarter previous year
                if len(quarterly_periods) >= 4:
                    current_q = quarterly_periods[0]
                    # Try to find same quarter from previous year
                    prev_year_q = None
                    for q in quarterly_periods[1:]:
                        try:
                            current_end = datetime.strptime(current_q['end_date'], '%Y-%m-%d').date()
                            q_end = datetime.strptime(q['end_date'], '%Y-%m-%d').date()
                            
                            # Check if the quarters are approximately 1 year apart
                            days_diff = abs((current_end - q_end).days - 365)
                            if days_diff <= 15:  # Within 15 days of being exactly 1 year apart
                                prev_year_q = q
                                break
                        except (ValueError, TypeError):
                            continue
                    
                    if prev_year_q:
                        period_views.append({
                            'name': 'Current Quarter vs. Prior Year Quarter',
                            'description': 'Compares the current quarter with the same quarter last year',
                            'period_keys': [current_q['key'], prev_year_q['key']]
                        })
                
                # Sequential quarters
                period_views.append({
                    'name': 'Three Recent Quarters',
                    'description': 'Shows three most recent quarters in sequence',
                    'period_keys': [p['key'] for p in quarterly_periods[:min(3, len(quarterly_periods))]]
                })
            
            # YTD comparisons
            if len(ytd_periods) >= 2:
                if len(ytd_periods) >= 3:
                    period_views.append({
                        'name': 'Three-Year YTD Comparison',
                        'description': 'Compares year-to-date figures across three years',
                        'period_keys': [p['key'] for p in ytd_periods[:3]]
                    })
                
                period_views.append({
                    'name': 'Year-to-Date Comparison',
                    'description': 'Compares year-to-date figures across years',
                    'period_keys': [p['key'] for p in ytd_periods[:min(2, len(ytd_periods))]]
                })
            
            # Mixed view - current YTD + quarterly breakdown
            if quarterly_periods and ytd_periods:
                mixed_keys = []
                if ytd_periods:
                    mixed_keys.append(ytd_periods[0]['key'])  # Current YTD
                    
                # Add recent quarters
                for q in quarterly_periods[:min(4, len(quarterly_periods))]:
                    if q['key'] not in mixed_keys:
                        mixed_keys.append(q['key'])
                
                if len(mixed_keys) >= 2:
                    period_views.append({
                        'name': 'YTD and Quarterly Breakdown',
                        'description': 'Shows YTD figures and quarterly breakdown',
                        'period_keys': mixed_keys[:5]  # Limit to 5 columns
                    })
                
        # For all statement types, if specific views haven't been created yet, add generic ones
        
        # If no views have been created, add a basic one with the most recent periods
        if not period_views:
            if statement_type in ['BalanceSheet'] and instant_periods:
                # Use most recent instant periods for balance sheet
                period_keys = [p['key'] for p in instant_periods[:min(3, len(instant_periods))]]
                period_views.append({
                    'name': 'Most Recent Periods',
                    'description': 'Shows the most recent reporting periods',
                    'period_keys': period_keys
                })
            elif statement_type in ['IncomeStatement', 'CashFlowStatement'] and duration_periods:
                # Use most recent duration periods for income/cash flow
                period_keys = [p['key'] for p in duration_periods[:min(3, len(duration_periods))]]
                period_views.append({
                    'name': 'Most Recent Periods',
                    'description': 'Shows the most recent reporting periods',
                    'period_keys': period_keys
                })
        
        return period_views
    
    def render_statement(self, statement_type: str = "BalanceSheet", 
                         period_filter: Optional[str] = None, 
                         period_view: Optional[str] = None,
                         standard: bool = False) -> RichTable:
        """
        Render a statement in a rich table format similar to how it would appear in an actual filing.
        
        Args:
            statement_type: Type of statement to render (e.g., "BalanceSheet", "IncomeStatement")
            period_filter: Optional period key to filter by specific reporting period
            period_view: Optional name of a predefined period view (e.g., "Quarterly: Current vs Previous")
            standard: Whether to use standardized concept labels (default: False)
            
        Returns:
            RichTable: A formatted table representation of the statement
        """
        # Get the statement data
        statement_data = self.get_statement(statement_type, period_filter)
        if not statement_data:
            return RichTable(title=f"No {statement_type} found")
        
        # Get the statement definition
        all_statements = self.get_all_statements()
        matching_statements = [stmt for stmt in all_statements if stmt['type'] == statement_type]
        statement_title = f"{matching_statements[0]['definition']}" if matching_statements else statement_type
        
        # Determine the periods to display
        periods_to_display = []
        
        # Get useful entity info for period selection
        entity_info = self.entity_info
        doc_period_end_date = entity_info.get('document_period_end_date')
        fiscal_year_focus = entity_info.get('fiscal_year')
        fiscal_period_focus = entity_info.get('fiscal_period')
        
        # Filter out periods that are later than document_period_end_date
        all_periods = self.reporting_periods
        
        if doc_period_end_date:
            # Filter for periods not later than document_period_end_date
            all_periods = []
            for period in self.reporting_periods:
                if period['type'] == 'instant':
                    try:
                        period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                        if period_date <= doc_period_end_date:
                            all_periods.append(period)
                    except (ValueError, TypeError):
                        # Keep periods we can't parse
                        all_periods.append(period)
                else:  # duration
                    try:
                        end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                        if end_date <= doc_period_end_date:
                            all_periods.append(period)
                    except (ValueError, TypeError):
                        # Keep periods we can't parse
                        all_periods.append(period)
            
            if not all_periods:
                print(f"Warning: No valid periods found for document_period_end_date {doc_period_end_date}")
        
        # Sort the filtered periods
        instant_periods = sorted(
            [p for p in all_periods if p['type'] == 'instant'],
            key=lambda x: x['date'],
            reverse=True  # Latest first
        )
        
        duration_periods = sorted(
            [p for p in all_periods if p['type'] == 'duration'],
            key=lambda x: (x['end_date'], x['start_date']),
            reverse=True  # Latest first
        )
        
        # If a period view is specified, use that
        if period_view:
            available_views = self.get_period_views(statement_type)
            matching_view = next((view for view in available_views if view['name'] == period_view), None)
            
            if matching_view:
                for period_key in matching_view['period_keys']:
                    period_match = None
                    # Find the period in our reporting periods
                    for period in all_periods:
                        p_key = period['key']
                        if p_key == period_key:
                            period_match = period
                            break
                    
                    if period_match:
                        periods_to_display.append((period_key, period_match['label']))
        
        # If no period view specified or it didn't find any periods
        if not periods_to_display:
            # For Balance Sheets - use instant periods
            if statement_type == 'BalanceSheet':
                # Take latest instant period that is not later than document_period_end_date
                if instant_periods:
                    current_period = instant_periods[0]  # Most recent
                    period_key = f"instant_{current_period['date']}"
                    periods_to_display.append((period_key, current_period['label']))
                    
                    # Try to find appropriate comparison period
                    try:
                        current_date = datetime.strptime(current_period['date'], '%Y-%m-%d').date()
                        
                        # Use fiscal information if available for better matching
                        if 'fiscal_year_end_month' in self.entity_info and 'fiscal_year_end_day' in self.entity_info:
                            fiscal_month = self.entity_info.get('fiscal_year_end_month')
                            fiscal_day = self.entity_info.get('fiscal_year_end_day')
                            
                            # If this is a fiscal year end report (or close to it), find previous fiscal year end
                            is_fiscal_year_end = False
                            if fiscal_period_focus == 'FY' or (
                                    current_date.month == fiscal_month and 
                                    abs(current_date.day - fiscal_day) <= 7):
                                is_fiscal_year_end = True
                            
                            if is_fiscal_year_end and fiscal_year_focus:
                                # For fiscal year end, find the previous fiscal year end period
                                prev_fiscal_year = int(fiscal_year_focus) - 1 if isinstance(fiscal_year_focus, (int, str)) and str(fiscal_year_focus).isdigit() else current_date.year - 1
                                
                                # Look for a comparable period from previous fiscal year
                                for period in instant_periods[1:]:  # Skip the current one
                                    try:
                                        period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                                        # Check if this period is from the previous fiscal year and around fiscal year end
                                        if (period_date.year == prev_fiscal_year and
                                            period_date.month == fiscal_month and 
                                            abs(period_date.day - fiscal_day) <= 15):
                                            period_key = f"instant_{period['date']}"
                                            periods_to_display.append((period_key, period['label']))
                                            break
                                    except (ValueError, TypeError):
                                        continue
                        
                        # If no appropriate period found yet, try generic date-based comparison
                        if len(periods_to_display) == 1:
                            # Look for a period from previous year with similar date pattern
                            prev_year = current_date.year - 1
                            
                            for period in instant_periods[1:]:  # Skip the current one
                                try:
                                    period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                                    # If from previous year with similar month/day
                                    if period_date.year == prev_year:
                                        period_key = f"instant_{period['date']}"
                                        periods_to_display.append((period_key, period['label']))
                                        break
                                except (ValueError, TypeError):
                                    continue
                        
                        # If still no match found, take up to two more recent periods (3 total)
                        if len(periods_to_display) == 1 and len(instant_periods) > 1:
                            # Add second period
                            period = instant_periods[1]
                            period_key = f"instant_{period['date']}"
                            periods_to_display.append((period_key, period['label']))
                            
                            # Add third period if available
                            if len(instant_periods) > 2:
                                period = instant_periods[2]
                                period_key = f"instant_{period['date']}"
                                periods_to_display.append((period_key, period['label']))
                    except (ValueError, TypeError):
                        # If date parsing failed, take up to three most recent periods
                        if len(instant_periods) > 1:
                            # Add second period
                            period = instant_periods[1]
                            period_key = f"instant_{period['date']}"
                            periods_to_display.append((period_key, period['label']))
                            
                            # Add third period if available
                            if len(instant_periods) > 2:
                                period = instant_periods[2]
                                period_key = f"instant_{period['date']}"
                                periods_to_display.append((period_key, period['label']))
            
            # For Income Statement or Cash Flow - use duration periods
            elif statement_type in ['IncomeStatement', 'CashFlowStatement']:
                # First identify annual periods
                annual_periods = []
                for period in duration_periods:
                    try:
                        start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                        end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                        days = (end_date - start_date).days
                        
                        # Typical annual report is about 365 days
                        if 350 <= days <= 380:
                            annual_periods.append(period)
                    except (ValueError, TypeError):
                        pass
                
                # For annual reports, show current and previous annual periods
                if fiscal_period_focus == 'FY' and annual_periods:
                    # Current annual period
                    current_period = annual_periods[0]
                    period_key = current_period['key']
                    periods_to_display.append((period_key, current_period['label']))
                    
                    # Previous annual periods (up to 2) if available
                    if len(annual_periods) > 1:
                        # Add second period (previous year)
                        prev_period = annual_periods[1]
                        period_key = prev_period['key']
                        periods_to_display.append((period_key, prev_period['label']))
                        
                        # Add third period (2 years ago) if available
                        if len(annual_periods) > 2:
                            prev_prev_period = annual_periods[2]
                            period_key = prev_prev_period['key']
                            periods_to_display.append((period_key, prev_prev_period['label']))
                
                # For quarterly reports, show current quarter and same quarter last year
                elif fiscal_period_focus in ['Q1', 'Q2', 'Q3', 'Q4'] and duration_periods:
                    # Current quarter
                    current_period = duration_periods[0]
                    period_key = current_period['key']
                    periods_to_display.append((period_key, current_period['label']))
                    
                    # Try to find same quarter from previous years (up to 2 years back)
                    try:
                        current_start = datetime.strptime(current_period['start_date'], '%Y-%m-%d').date()
                        current_end = datetime.strptime(current_period['end_date'], '%Y-%m-%d').date()
                        current_days = (current_end - current_start).days
                        
                        # Periods from previous years to add (up to 2)
                        prev_year_periods = []
                        
                        # Compare with other periods
                        for period in duration_periods[1:]:
                            try:
                                period_start = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                                period_end = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                                period_days = (period_end - period_start).days
                                
                                # Similar length periods from approximately a year apart
                                days_apart = abs((current_end - period_end).days)
                                # Check for 1 year ago period
                                if (abs(period_days - current_days) <= 10 and  # Similar duration
                                    350 <= days_apart <= 380):  # About a year apart
                                    prev_year_periods.append((days_apart, period))
                                
                                # Check for 2 years ago period
                                if (abs(period_days - current_days) <= 10 and  # Similar duration
                                    730 - 30 <= days_apart <= 730 + 30):  # About two years apart
                                    prev_year_periods.append((days_apart, period))
                            except (ValueError, TypeError):
                                continue
                        
                        # Sort by how closely they match the expected timeframes
                        prev_year_periods.sort()
                        
                        # Add up to 2 periods from previous years
                        for i, (_, period) in enumerate(prev_year_periods[:2]):
                            period_key = period['key']
                            periods_to_display.append((period_key, period['label']))
                    except (ValueError, TypeError):
                        pass
                
                # If no periods selected yet, use generic approach 
                if not periods_to_display:
                    # Try to use annual periods if available
                    if annual_periods:
                        for period in annual_periods[:min(3, len(annual_periods))]:
                            period_key = period['key']
                            periods_to_display.append((period_key, period['label']))
                    else:
                        # Fall back to any available duration periods
                        for period in duration_periods[:min(3, len(duration_periods))]:
                            period_key = period['key']
                            periods_to_display.append((period_key, period['label']))
            
            # If we still don't have any periods, use whatever is available
            if not periods_to_display and all_periods:
                # Use first period available
                period = all_periods[0]
                period_key = period['key']
                periods_to_display.append((period_key, period['label']))
                
                # Add a second period if available
                if len(all_periods) > 1:
                    period = all_periods[1]
                    period_key = period['key']
                    periods_to_display.append((period_key, period['label']))
                
                # Add a third period if available
                if len(all_periods) > 2:
                    period = all_periods[2]
                    period_key = period['key']
                    periods_to_display.append((period_key, period['label']))
        
        # Use the rendering module to render the statement
        return render_statement(
            statement_data,
            periods_to_display,
            statement_title,
            statement_type,
            self.entity_info,
            standard
        )
    
    def to_pandas(self, statement_role: Optional[str] = None, standard: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Convert XBRL data to pandas DataFrames.
        
        Args:
            statement_role: Optional role URI to convert only a specific statement
            standard: Whether to use standardized concept labels (default: True)
            
        Returns:
            Dictionary of DataFrames for different aspects of the XBRL data
        """
        import pandas as pd
        
        dataframes = {}
        
        # Convert contexts to DataFrame
        context_data = []
        for context_id, context in self.contexts.items():
            ctx_dict = context.dict()
            ctx_dict['context_id'] = context_id
            
            # Extract entity info
            if 'entity' in ctx_dict and ctx_dict['entity']:
                ctx_dict['entity_identifier'] = ctx_dict['entity'].get('identifier')
                ctx_dict['entity_scheme'] = ctx_dict['entity'].get('scheme')
            
            # Extract period info
            if 'period' in ctx_dict and ctx_dict['period']:
                ctx_dict['period_type'] = ctx_dict['period'].get('type')
                if ctx_dict['period_type'] == 'instant':
                    ctx_dict['period_instant'] = ctx_dict['period'].get('instant')
                elif ctx_dict['period_type'] == 'duration':
                    ctx_dict['period_start'] = ctx_dict['period'].get('startDate')
                    ctx_dict['period_end'] = ctx_dict['period'].get('endDate')
            
            # Extract dimensions
            if 'dimensions' in ctx_dict and ctx_dict['dimensions']:
                for dim_name, dim_value in ctx_dict['dimensions'].items():
                    dim_key = f"dim_{dim_name.replace(':', '_')}"
                    ctx_dict[dim_key] = dim_value
            
            context_data.append(ctx_dict)
        
        if context_data:
            dataframes['contexts'] = pd.DataFrame(context_data)
        
        # Convert facts to DataFrame
        fact_data = []
        for fact_key, fact in self.facts.items():
            fact_dict = fact.dict()
            fact_dict['fact_key'] = fact_key
            
            # Try to get additional information
            if fact.context_ref in self.contexts:
                context = self.contexts[fact.context_ref]
                
                # Add period information
                if 'period' in context.dict() and context.period:
                    fact_dict['period_type'] = context.period.get('type')
                    if fact_dict['period_type'] == 'instant':
                        fact_dict['period_instant'] = context.period.get('instant')
                    elif fact_dict['period_type'] == 'duration':
                        fact_dict['period_start'] = context.period.get('startDate')
                        fact_dict['period_end'] = context.period.get('endDate')
                
                # Add entity information
                if 'entity' in context.dict() and context.entity:
                    fact_dict['entity_identifier'] = context.entity.get('identifier')
                
                # Add dimensions
                if 'dimensions' in context.dict() and context.dimensions:
                    for dim_name, dim_value in context.dimensions.items():
                        dim_key = f"dim_{dim_name.replace(':', '_')}"
                        fact_dict[dim_key] = dim_value
            
            # Try to get element information
            element_id = fact.element_id
            if element_id in self.element_catalog:
                element = self.element_catalog[element_id]
                fact_dict['element_name'] = element.name
                fact_dict['element_type'] = element.data_type
                fact_dict['element_period_type'] = element.period_type
                fact_dict['element_balance'] = element.balance
                
                # Add label
                label = None
                if element.labels:
                    # Try standard label first
                    label = element.labels.get(STANDARD_LABEL)
                    if not label:
                        # Take first available label
                        label = next(iter(element.labels.values()), None)
                fact_dict['element_label'] = label
            
            fact_data.append(fact_dict)
        
        if fact_data:
            dataframes['facts'] = pd.DataFrame(fact_data)
        
        # Convert entity info to DataFrame
        if self.entity_info:
            dataframes['entity_info'] = pd.DataFrame([self.entity_info])
        
        # Convert specific statement if requested
        if statement_role:
            # Try direct role URI
            statement_data = self.get_statement(statement_role)
            
            # If not found, try by statement type
            if not statement_data and not statement_role.startswith('http'):
                # Find the role for this statement type
                all_statements = self.get_all_statements()
                matching_statements = [stmt for stmt in all_statements if stmt['type'] == statement_role]
                
                if matching_statements:
                    role = matching_statements[0]['role']
                    statement_data = self.get_statement(role)
            
            # Convert statement data to DataFrame if found
            if statement_data:
                # Apply standardization if requested
                if standard:
                    # Get statement type for context
                    stmt_type = statement_role
                    if not stmt_type.startswith('http'):
                        stmt_type = statement_role
                    else:
                        # Try to determine statement type from role
                        all_statements = self.get_all_statements()
                        for stmt in all_statements:
                            if stmt['role'] == statement_role:
                                stmt_type = stmt['type']
                                break
                    
                    # Add statement type to each item
                    for item in statement_data:
                        item['statement_type'] = stmt_type
                    
                    # Apply standardization
                    from edgar.xbrl2 import standardization
                    mapper = standardization.ConceptMapper(standardization.initialize_default_mappings())
                    statement_data = standardization.standardize_statement(statement_data, mapper)
                
                # Create rows for the DataFrame
                rows = []
                
                # Add columns for all found periods
                all_periods = set()
                for item in statement_data:
                    for period in item.get('values', {}).keys():
                        all_periods.add(period)
                
                # Sort periods (typically instant or duration_start_end format)
                sorted_periods = sorted(all_periods)
                
                for item in statement_data:
                    row = {
                        'concept': item['concept'],
                        'name': item.get('name'),
                        'label': item['label'],
                        'level': item['level'],
                        'is_abstract': item['is_abstract'],
                        'has_values': item.get('has_values', False),
                    }
                    
                    # Add original label if standardized
                    if 'original_label' in item:
                        row['original_label'] = item['original_label']
                    
                    # Add period values
                    for period in sorted_periods:
                        value = item.get('values', {}).get(period)
                        row[period] = value
                    
                    rows.append(row)
                
                if rows:
                    dataframes['statement'] = pd.DataFrame(rows)
            
        return dataframes
    
    def __rich__(self):
        """Rich representation for pretty printing in console."""
        return generate_rich_representation(self)
    
    def __str__(self):
        """String representation."""
        return f"XBRL Document with {len(self.facts)} facts, {len(self.contexts)} contexts, and {len(self.presentation_trees)} statements"
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

from pathlib import Path
from typing import Dict, List, Any, Optional, Union

import pandas as pd
from rich.table import Table as RichTable

from edgar.richtools import repr_rich
from edgar.xbrl2 import transformers
from edgar.xbrl2.core import STANDARD_LABEL
from edgar.xbrl2.facts import FactQuery
from edgar.xbrl2.models import (
    PresentationNode, XBRLProcessingError
)
from edgar.xbrl2.parser import XBRLParser
from edgar.xbrl2.periods import get_period_views, determine_periods_to_display
from edgar.xbrl2.rendering import render_statement, generate_rich_representation, RenderedStatement
from edgar.xbrl2.statements import statement_to_concepts


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
        
        # Cached indices for fast statement lookup
        self._statement_indices = {}
        self._statement_by_standard_name = {}
        self._statement_by_primary_concept = {}
        self._statement_by_role_uri = {}
        self._statement_by_role_name = {}
        self._all_statements_cached = None
    
    def _is_dimension_display_statement(self, statement_type: str, role_definition: str) -> bool:
        """
        Determine if a statement should display dimensioned line items.
        
        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            role_definition: The definition of the statement role
            
        Returns:
            bool: True if dimensions should be displayed, False otherwise
        """
        # Skip financial statements where dimensions would mess up the display
        if statement_type in ['BalanceSheet', 'IncomeStatement', 'CashFlowStatement', 
                             'StatementOfEquity', 'ComprehensiveIncome']:
            return False
            
        # Look for keywords in role definition that suggest dimensional breakdowns
        dimension_keywords = [
            'segment', 'geography', 'geographic', 'region', 'product', 'business',
            'by country', 'by region', 'by product', 'by segment', 'revenues by'
        ]
        
        role_def_lower = role_definition.lower() if role_definition else ""
        return any(keyword in role_def_lower for keyword in dimension_keywords)
        
    @property
    def element_catalog(self):
        return self.parser.element_catalog
        
    @property
    def contexts(self):
        return self.parser.contexts
        
    @property
    def _facts(self):
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

        return xbrl

    @property
    def statements(self):
        from edgar.xbrl2.statements import Statements
        return Statements(self)
        
    @property
    def facts(self):
        from edgar.xbrl2.facts import FactsView
        if not hasattr(self, '_facts_view'):
            self._facts_view = FactsView(self)
        return self._facts_view

    def query(self,
              include_dimensions: bool = True,
              include_contexts: bool = False,
              include_element_info:bool = False) -> 'FactQuery':
        """
        Start a new query for XBRL facts.
        """
        fact_query = self.facts.query()
        if not include_dimensions:
            fact_query = fact_query.exclude_dimensions()
        if not include_contexts:
            fact_query = fact_query.exclude_contexts()
        if not include_element_info:
            fact_query = fact_query.exclude_element_info()
        return fact_query
    
    def get_all_statements(self) -> List[Dict[str, Any]]:
        """
        Get all available financial statements.
        
        Returns:
            List of statement metadata (role, definition, element count)
        """
        # Return cached result if available
        if self._all_statements_cached is not None:
            return self._all_statements_cached
            
        statements = []

        # Reset indices
        self._statement_indices = {}
        self._statement_by_standard_name = {}
        self._statement_by_primary_concept = {}
        self._statement_by_role_uri = {}
        self._statement_by_role_name = {}
        
        for role, tree in self.presentation_trees.items():
            # Check if this role appears to be a financial statement
            role_def = tree.definition.lower()
            statement_type = None
            primary_concept = next(iter(tree.all_nodes))

            for statement_alias, statement_info in statement_to_concepts.items():
                if primary_concept == statement_info.concept:
                    if 'parenthetical' in role_def:
                        statement_type = f"{statement_alias}Parenthetical"
                    else:
                        statement_type = statement_alias
                    if not 'BalanceSheet' in statement_type:
                        break
            # Try to extract role name from URI
            role_name = role.split('/')[-1] if '/' in role else role.split('#')[-1] if '#' in role else ''
            
            # Create the statement metadata
            statement = {
                'role': role,
                'definition': tree.definition,
                'element_count': len(tree.all_nodes),
                'type': statement_type,
                'primary_concept': primary_concept,
                'role_name': role_name
            }
            
            statements.append(statement)
            
            # Build lookup indices
            # By role URI
            self._statement_by_role_uri[role] = statement
            
            # By role name (short name)
            if role_name:
                role_name_lower = role_name.lower()
                if role_name_lower not in self._statement_by_role_name:
                    self._statement_by_role_name[role_name_lower] = []
                self._statement_by_role_name[role_name_lower].append(statement)
            
            # By standard name
            if statement_type:
                if statement_type not in self._statement_by_standard_name:
                    self._statement_by_standard_name[statement_type] = []
                self._statement_by_standard_name[statement_type].append(statement)
            
            # By primary concept
            if primary_concept:
                if primary_concept not in self._statement_by_primary_concept:
                    self._statement_by_primary_concept[primary_concept] = []
                self._statement_by_primary_concept[primary_concept].append(statement)
                
            # Also index by definition (without spaces, lowercase)
            if statement['definition']:
                def_key = statement['definition'].lower().replace(' ', '')
                if def_key not in self._statement_indices:
                    self._statement_indices[def_key] = []
                self._statement_indices[def_key].append(statement)
        
        # Cache the result
        self._all_statements_cached = statements
        return statements
        
    def get_statement_by_type(self, statement_type: str) -> Optional[Dict[str, Any]]:
        """
        Get the first statement matching the given type.
        
        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            
        Returns:
            Statement data if found, None otherwise
        """
        # Ensure indices are built
        if not self._all_statements_cached:
            self.get_all_statements()
            
        # Use indexed lookup by standard name
        if statement_type in self._statement_by_standard_name:
            statements = self._statement_by_standard_name[statement_type]
            if statements:
                statement = statements[0]
                # Get statement data
                role = statement['role']
                statement_data = self.get_statement(role)
                
                if statement_data:
                    # Extract periods from the statement data
                    periods = {}
                    for item in statement_data:
                        for period_id, value in item.get('values', {}).items():
                            if period_id not in periods:
                                # Get period label from reporting_periods
                                period_label = period_id
                                for period in self.reporting_periods:
                                    if period['key'] == period_id:
                                        period_label = period['label']
                                        break
                                periods[period_id] = {'label': period_label}
                    
                    return {
                        'role': role,
                        'definition': statement['definition'],
                        'statement_type': statement_type,
                        'periods': periods,
                        'data': statement_data
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
    
    def get_statement(self, role_or_type: str,
                      period_filter: Optional[str] = None,
                      should_display_dimensions: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        Get a financial statement by role URI, statement type, or statement short name.
        
        Args:
            role_or_type: Can be one of:
                - Extended link role URI (e.g. "http://apple.com/role/ConsolidatedStatementOfIncome")
                - Statement type name (e.g. "BalanceSheet")
                - Statement short name (e.g. "ConsolidatedStatementOfIncome") 
            period_filter: Optional period key to filter facts
            should_display_dimensions: Whether to display dimensions for this statement.
                If None, the method will determine based on statement type and role.
            
        Returns:
            List of line items with values
        """
        # Ensure indices are built
        if not self._all_statements_cached:
            self.get_all_statements()
            
        # If requesting by full role URI, use as is
        role_uri = None
        
        if role_or_type.startswith('http'):
            # Direct role URI lookup
            role_uri = role_or_type
        else:
            # Try to find by standard name (e.g., "BalanceSheet")
            if role_or_type in self._statement_by_standard_name:
                statements = self._statement_by_standard_name[role_or_type]
                if statements:
                    role_uri = statements[0]['role']
            
            # If not found, try by role name (case-insensitive)
            if not role_uri:
                role_or_type_lower = role_or_type.lower()
                if role_or_type_lower in self._statement_by_role_name:
                    statements = self._statement_by_role_name[role_or_type_lower]
                    if statements:
                        role_uri = statements[0]['role']
            
            # If still not found, try by definition
            if not role_uri:
                def_key = role_or_type.lower().replace(' ', '')
                if def_key in self._statement_indices:
                    statements = self._statement_indices[def_key]
                    if statements:
                        role_uri = statements[0]['role']
                        
            # If still not found, try partial matching on role name
            if not role_uri:
                for role_name, statements in self._statement_by_role_name.items():
                    if role_or_type.lower() in role_name:
                        role_uri = statements[0]['role']
                        break
        
        # If no matching statement found, return empty list
        if not role_uri or role_uri not in self.presentation_trees:
            return []
        
        tree = self.presentation_trees[role_uri]
        
        # Find the root element
        root_id = tree.root_element_id
        
        # If should_display_dimensions wasn't provided, determine it from the statement type and role
        if should_display_dimensions is None:
            statement_type = None
            role_definition = ""
            # Find statement info to get type and definition
            for stmt in self.get_all_statements():
                if stmt['role'] == role_or_type:
                    statement_type = stmt['type']
                    role_definition = stmt['definition']
                    break
            # Determine whether to display dimensions
            should_display_dimensions = self._is_dimension_display_statement(statement_type, role_definition)
            
        # Generate line items recursively
        line_items = []
        self._generate_line_items(root_id, tree.all_nodes, line_items, period_filter, None, should_display_dimensions)
        
        return line_items
    
    def _generate_line_items(self, element_id: str, nodes: Dict[str, PresentationNode], 
                            result: List[Dict[str, Any]], period_filter: Optional[str] = None, 
                            path: List[str] = None, should_display_dimensions: bool = False) -> None:
        """
        Recursively generate line items for a statement.
        
        Args:
            element_id: Current element ID
            nodes: Dictionary of presentation nodes
            result: List to append line items to
            period_filter: Optional period key to filter facts
            path: Current path in hierarchy
            should_display_dimensions: Whether to display dimensions for this statement
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
            
        # Find facts for any of these concept names
        all_relevant_facts =  self._find_facts_for_element(node.element_name, period_filter)
            
        # Group facts by period for better selection
        facts_by_period = {}
        
        # Process all found facts and group by period
        for context_id, wrapped_fact in all_relevant_facts.items():
            # Get period key for this context
            period_key = self.context_period_map.get(context_id)
            if not period_key:
                continue  # Skip if no period key found
                
            # Initialize period entry if not exists
            if period_key not in facts_by_period:
                facts_by_period[period_key] = []
                
            # Add this fact to the period
            facts_by_period[period_key].append((context_id, wrapped_fact))
            
        # should_display_dimensions is now passed as a parameter from the calling method
        
        # Process facts by period, with different handling based on statement type
        from collections import defaultdict
        dimensioned_facts = defaultdict(list)  # For dimensioned statement types
        
        for period_key, period_facts in facts_by_period.items():
            if should_display_dimensions:
                # For statements that should display dimensions, group facts by dimension
                for context_id, wrapped_fact in period_facts:
                    fact = wrapped_fact['fact']
                    dimension_info = wrapped_fact['dimension_info']
                    dimension_key = wrapped_fact['dimension_key']
                    
                    if dimension_info:
                        # Use the dimension_key we already generated
                        dim_key_str = dimension_key
                        
                        # Store dimensioned fact with the full dimension metadata
                        dimensioned_facts[dim_key_str].append((period_key, fact, dimension_info))
                    else:
                        # This is a non-dimensioned fact for this concept, use in the main item
                        if not values.get(period_key):
                            values[period_key] = fact.numeric_value if fact.numeric_value is not None else fact.value
                            
                            # Store the decimals info for proper scaling
                            if fact.decimals is not None:
                                try:
                                    if fact.decimals == 'INF':
                                        decimals[period_key] = 0  # Infinite precision, no scaling
                                    else:
                                        decimals[period_key] = int(fact.decimals)
                                except (ValueError, TypeError):
                                    decimals[period_key] = 0  # Default
            else:
                # For standard financial statements, prefer non-dimensioned facts
                # If only one fact, use it
                if len(period_facts) == 1:
                    context_id, wrapped_fact = period_facts[0]
                    fact = wrapped_fact['fact']
                else:
                    # Multiple facts for same period - prioritize based on dimensions
                    # Sort facts by preference: no dimensions first, then by dimension count (fewer dimensions preferred)
                    sorted_facts = []
                    for ctx_id, wrapped_fact in period_facts:
                        dimension_count = len(wrapped_fact['dimension_info'])
                        sorted_facts.append((dimension_count, ctx_id, wrapped_fact))
                    
                    # Sort by dimension count (no dimensions or fewer dimensions first)
                    sorted_facts.sort()
                    
                    # Use the first fact (with fewest dimensions)
                    _, context_id, wrapped_fact = sorted_facts[0]
                    fact = wrapped_fact['fact']
                
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
        
        # For dimensional statements with dimension data, handle the parent item specially
        if should_display_dimensions and dimensioned_facts:
            # Create parent line item as an abstract header for dimensions
            line_item = {
                'concept': element_id,
                'name': node.element_name,
                'all_names': [node.element_name],
                'label': f"{label}:", # Add colon to indicate it's a header with dimension children
                'values': {},  # No values for the parent header
                'decimals': {},
                'level': node.depth,
                'preferred_label': node.preferred_label,
                'is_abstract': True,  # Mark as abstract since it's just a header
                'children': node.children,
                'has_values': False,
                'has_dimension_children': True  # Mark as having dimension children
            }
        else:
            # Non-dimensional case: Create normal line item with values
            line_item = {
                'concept': element_id,
                'name': node.element_name,
                'all_names': [node.element_name],
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
        
        # For dimensional statements, add dimensioned facts as child line items
        if should_display_dimensions and dimensioned_facts:
            # Add each dimension as a child line item with increased depth
            for dim_key, facts_list in dimensioned_facts.items():
                dim_values = {}
                dim_decimals = {}
                dim_metadata = None  # Store metadata from the first fact
                
                # Collect values for each period
                for fact_data in facts_list:
                    try:
                        # Unpack with consistent 3-part tuples from our updated code
                        period_key, fact, dimensions_info = fact_data
                        
                        # Store the dimension metadata from the first fact
                        if dim_metadata is None:
                            dim_metadata = dimensions_info
                            
                        # Extract value from fact
                        dim_values[period_key] = fact.numeric_value if fact.numeric_value is not None else fact.value
                    except (ValueError, TypeError, IndexError) as e:
                        # Try to handle older format (period_key, fact) tuple for backward compatibility
                        try:
                            if isinstance(fact_data, tuple) and len(fact_data) == 2:
                                period_key, fact = fact_data
                                dim_values[period_key] = fact.numeric_value if fact.numeric_value is not None else fact.value
                        except Exception:
                            # Log the error and continue
                            print(f"Error processing dimension fact data: {e}")
                            continue
                    
                    # Store decimals
                    if fact.decimals is not None:
                        try:
                            if fact.decimals == 'INF':
                                dim_decimals[period_key] = 0
                            else:
                                dim_decimals[period_key] = int(fact.decimals)
                        except (ValueError, TypeError):
                            dim_decimals[period_key] = 0
                
                # For better display, use the member label for dimension items,
                # but make sure we don't add the parent concept name as well
                
                # Default to the full dimension key (e.g., "Region: Americas")
                display_label = dim_key
                
                # Try various member label formats based on dimension structure
                if dim_metadata:
                    if len(dim_metadata) == 1:
                        # For single dimensions, just use the member label (e.g., "Americas")
                        display_label = dim_metadata[0]['member_label']
                    else:
                        # For multiple dimensions, create a combined label with all member names
                        # (e.g., "Americas - iPhone")
                        member_labels = [info['member_label'] for info in dim_metadata if 'member_label' in info]
                        if member_labels:
                            display_label = " - ".join(member_labels)
                
                # Create dimension line item
                dim_line_item = {
                    'concept': element_id,  # Use same concept
                    'name': node.element_name,
                    'all_names': [node.element_name],
                    'label': display_label,  # Use optimized dimension label
                    'full_dimension_label': dim_key,  # Keep full dimension notation for reference
                    'values': dim_values,
                    'decimals': dim_decimals,
                    'level': node.depth + 1,  # Increase depth by 1
                    'preferred_label': node.preferred_label,
                    'is_abstract': False,
                    'children': [],
                    'has_values': len(dim_values) > 0,
                    'is_dimension': True,  # Mark as a dimension item
                    'dimension_metadata': dim_metadata  # Store full dimension information
                }
                
                # Add to result
                result.append(dim_line_item)
        
        # Process children
        for child_id in node.children:
            self._generate_line_items(child_id, nodes, result, period_filter, current_path, should_display_dimensions)
    
    def _find_facts_for_element(self, element_name: str, period_filter: Optional[str] = None, 
                                 dimensions: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Find facts for a specific element, optionally filtered by period and dimensions.
        
        Args:
            element_name: Element name to find facts for
            period_filter: Optional period key to filter contexts
            dimensions: Optional dictionary of dimension names to dimension values to filter by
            
        Returns:
            Dictionary of facts by context ID with dimension information attached
        """
        if not element_name:
            return {}  # No element name provided
            
        relevant_facts = {}
        
        # Check each context
        for context_id in self.contexts:
            # Use parser's get_fact method which handles normalization internally
            fact = self.parser.get_fact(element_name, context_id)
            
            if fact:
                # If period filter is specified, check if context matches period
                if period_filter:
                    period_key = self.context_period_map.get(context_id)
                    if period_key != period_filter:
                        continue  # Skip if period doesn't match
                
                # If dimensions are specified, check if context has matching dimensions
                if dimensions:
                    context = self.contexts.get(context_id)
                    if not context or not hasattr(context, 'dimensions'):
                        continue  # Skip if context doesn't have dimensions
                    
                    # Check if all specified dimensions match
                    matches_all_dimensions = True
                    for dim_name, dim_value in dimensions.items():
                        # Normalize dimension name if it contains a colon
                        normalized_dim_name = dim_name.replace(':', '_')
                        
                        # Check if this dimension exists and matches the expected value
                        if normalized_dim_name not in context.dimensions or context.dimensions[normalized_dim_name] != dim_value:
                            matches_all_dimensions = False
                            break
                    
                    if not matches_all_dimensions:
                        continue  # Skip if dimensions don't match
                
                # Get the context and extract dimension information
                context = self.contexts.get(context_id)
                
                # Create a wrapper around the fact with dimension information
                wrapped_fact = {
                    'fact': fact,
                    'dimension_info': [],
                    'dimension_key': ""
                }
                
                if context and hasattr(context, 'dimensions') and context.dimensions:
                    # Build rich dimension information with formatted labels
                    dimension_info = []
                    dim_keys = []
                    
                    for dim_name, dim_value in sorted(context.dimensions.items()):
                        dim_value = dim_value.replace(":", "_")
                        # Initialize with technical names
                        dim_label = dim_name
                        mem_label = dim_value
                        
                        # Get richer label information from element catalog
                        dim_element = None
                        mem_element = None
                        
                        # Try to get human-readable dimension name
                        if dim_name in self.element_catalog:
                            dim_element = self.element_catalog[dim_name]
                            # Try different label roles in order of preference
                            for role in ['http://www.xbrl.org/2003/role/terseLabel',
                                        'http://www.xbrl.org/2003/role/label',
                                        'http://www.xbrl.org/2003/role/verboseLabel']:
                                if role in dim_element.labels:
                                    dim_label = dim_element.labels[role]
                                    break
                        
                        # Try to get human-readable member name
                        if dim_value in self.element_catalog:
                            mem_element = self.element_catalog[dim_value]
                            # Try different label roles in order of preference
                            for role in ['http://www.xbrl.org/2003/role/terseLabel',
                                        'http://www.xbrl.org/2003/role/label',
                                        'http://www.xbrl.org/2003/role/verboseLabel']:
                                if role in mem_element.labels:
                                    mem_label = mem_element.labels[role]
                                    break
                        
                        # Clean up labels (remove [Axis], [Member], etc.)
                        dim_label = dim_label.replace('[Axis]', '').replace('[Domain]', '').strip()
                        mem_label = mem_label.replace('[Member]', '').strip()
                        
                        # Format key for display
                        format_key = f"{dim_label}: {mem_label}"
                        dim_keys.append(format_key)
                        
                        # Store rich dimension information
                        dimension_info.append({
                            'dimension': dim_name,
                            'member': dim_value,
                            'dimension_label': dim_label,
                            'member_label': mem_label,
                            'format_key': format_key,
                            'dimension_element': dim_element,
                            'member_element': mem_element
                        })
                    
                    # Store dimension information in the wrapper
                    wrapped_fact['dimension_info'] = dimension_info
                    wrapped_fact['dimension_key'] = ", ".join(sorted(dim_keys))
                
                # If we get here, all filters passed
                relevant_facts[context_id] = wrapped_fact
        
        return relevant_facts

    
    def get_period_views(self, statement_type: str) -> List[Dict[str, Any]]:
        """
        Get available period views for a statement type.
        
        Args:
            statement_type: Type of statement to get period views for
            
        Returns:
            List of period view options with name, description, and period keys
        """
        return get_period_views(self, statement_type)
    
    def render_statement(self, statement_type: str = "BalanceSheet", 
                          period_filter: Optional[str] = None, 
                          period_view: Optional[str] = None,
                          standard: bool = True,
                          show_date_range: bool = False) -> Optional[RenderedStatement]:
        """
        Render a statement in a rich table format similar to how it would appear in an actual filing.
        
        Args:
            statement_type: Type of statement to render (e.g., "BalanceSheet", "IncomeStatement")
                           or a specific statement role/name (e.g., "CONSOLIDATEDBALANCESHEETS")
            period_filter: Optional period key to filter by specific reporting period
            period_view: Optional name of a predefined period view (e.g., "Quarterly: Current vs Previous")
            standard: Whether to use standardized concept labels (default: False)
            show_date_range: Whether to show full date ranges for duration periods (default: False)
            
        Returns:
            RichTable: A formatted table representation of the statement
        """
        # First, determine the actual statement type and role from the input
        matching_statements = []
        found_role = None
        actual_statement_type = statement_type
        
        # Try to find the statement by standard name first
        if statement_type in self._statement_by_standard_name:
            matching_statements = self._statement_by_standard_name[statement_type]
            if matching_statements:
                found_role = matching_statements[0]['role']
                
        # If not found by standard name, try by role URI
        if not matching_statements and statement_type.startswith('http') and statement_type in self._statement_by_role_uri:
            matching_statements = [self._statement_by_role_uri[statement_type]]
            found_role = statement_type
            
        # If not found, try by role name (case-insensitive)
        if not matching_statements:
            role_or_type_lower = statement_type.lower()
            if role_or_type_lower in self._statement_by_role_name:
                matching_statements = self._statement_by_role_name[role_or_type_lower]
                if matching_statements:
                    found_role = matching_statements[0]['role']
                    
        # If still not found, try by definition
        if not matching_statements:
            def_key = statement_type.lower().replace(' ', '')
            if def_key in self._statement_indices:
                matching_statements = self._statement_indices[def_key]
                if matching_statements:
                    found_role = matching_statements[0]['role']
        
        # Get statement definition and update actual statement type if we found a match
        role_definition = ""
        if matching_statements:
            role_definition = matching_statements[0]['definition']
            if matching_statements[0]['type']:
                actual_statement_type = matching_statements[0]['type']
        
        # Determine if this statement should display dimensions
        should_display_dimensions = self._is_dimension_display_statement(actual_statement_type, role_definition)
        
        # Get the statement data with dimension display flag
        statement_data = self.get_statement(statement_type, period_filter, should_display_dimensions)
        if not statement_data:
            return None
        
        # Get the statement title
        statement_info = statement_to_concepts.get(actual_statement_type)
        if statement_info:
            statement_title = statement_info.title
        else:
            # Try to get a nice title from the role definition
            if role_definition:
                statement_title = role_definition.split(' - ')[-1].strip()
            else:
                statement_title = statement_type
        
        # Get periods to display using the new periods module
        periods_to_display = determine_periods_to_display(
            self, actual_statement_type, period_filter, period_view
        )
        
        # Render the statement
        return render_statement(
            statement_data,
            periods_to_display,
            statement_title,
            actual_statement_type,
            self.entity_info,
            standard,
            show_date_range
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
        for fact_key, fact in self._facts.items():
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
                    # Rename columns to remove duration/instant prefixes
                    dataframes['statement'].columns = [
                        col.replace('duration_', '').replace('instant_', '')
                        for col in dataframes['statement'].columns
                    ]
            
        return dataframes
    
    def __rich__(self):
        """Rich representation for pretty printing in console."""
        return generate_rich_representation(self)

    def __repr__(self):
        return repr_rich(self)
    
    def calculate_ratios(self, statement_type: Optional[str] = None) -> Dict[str, Dict[str, float]]:
        """
        Calculate common financial ratios.
        
        Args:
            statement_type: Optional statement type to use (e.g., 'BalanceSheet')
            
        Returns:
            Dict[str, Dict[str, float]]: Dictionary of ratio names to period values
        """
        # Get statement data
        if statement_type:
            statement_data = self.get_statement_by_type(statement_type)
            if statement_data is None:
                return {}
            if isinstance(statement_data, dict):
                statement_data = [statement_data]
        else:
            all_statements = self.get_all_statements()
            if all_statements is None:
                return {}
            # Convert to list of statements
            statement_data = []
            for stmt in all_statements.values():
                if isinstance(stmt, dict):
                    statement_data.append(stmt)
                elif isinstance(stmt, list):
                    statement_data.extend(stmt)
        
        # Get periods to display
        periods_to_display = None
        if statement_type:
            period_views = self.get_period_views(statement_type)
            if period_views:
                periods_to_display = period_views[0].get('periods', [])
        
        return transformers.calculate_ratios(statement_data, periods_to_display)
    
    def calculate_growth_rates(self, statement_type: Optional[str] = None,
                             concepts: Optional[List[str]] = None) -> Dict[str, Dict[str, float]]:
        """
        Calculate period-over-period growth rates.
        
        Args:
            statement_type: Optional statement type to use
            concepts: Optional list of concepts to calculate growth rates for
            
        Returns:
            Dict[str, Dict[str, float]]: Dictionary of concept names to period growth rates
        """
        # Get statement data
        if statement_type:
            statement_data = self.get_statement_by_type(statement_type)
            if statement_data is None:
                return {}
            if isinstance(statement_data, dict):
                statement_data = [statement_data]
        else:
            all_statements = self.get_all_statements()
            if all_statements is None:
                return {}
            # Convert to list of statements
            statement_data = []
            for stmt in all_statements.values():
                if isinstance(stmt, dict):
                    statement_data.append(stmt)
                elif isinstance(stmt, list):
                    statement_data.extend(stmt)
        
        # Get periods to display
        periods_to_display = None
        if statement_type:
            period_views = self.get_period_views(statement_type)
            if period_views:
                periods_to_display = period_views[0].get('periods', [])
        
        return transformers.calculate_growth_rates(
            statement_data,
            periods_to_display=periods_to_display,
            concepts=concepts
        )
    
    def aggregate_by_dimension(self, statement_type: str, dimension_name: str,
                             aggregation: str = 'sum') -> Dict[str, Dict[str, Any]]:
        """
        Aggregate values by a specific dimension.
        
        Args:
            statement_type: Statement type to aggregate
            dimension_name: Name of the dimension to aggregate by
            aggregation: Aggregation function ('sum' or 'average')
            
        Returns:
            Dict[str, Dict[str, Any]]: Aggregated values by dimension member
        """
        statement_data = self.get_statement_by_type(statement_type)
        if not statement_data:
            return {}
            
        # Ensure statement_data is a list
        if isinstance(statement_data, dict):
            statement_data = [statement_data]
        
        return transformers.aggregate_by_dimension(
            statement_data,
            dimension_name=dimension_name,
            aggregation=aggregation
        )

        
    def __str__(self):
        """String representation."""
        return f"XBRL Document with {len(self._facts)} facts, {len(self.contexts)} contexts, and {len(self.presentation_trees)} statements"
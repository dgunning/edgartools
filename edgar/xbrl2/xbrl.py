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

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

import pandas as pd
from rich.table import Table as RichTable

from edgar.richtools import repr_rich
# Import legacy XBRL data for compatibility
from edgar.xbrl.instance import XBRLInstance as LegacyXbrlInstance
from edgar.xbrl2.core import STANDARD_LABEL, format_date, parse_date
# Import refactored components
from edgar.xbrl2.models import (
    Fact, PresentationNode, XBRLProcessingError
)
from edgar.xbrl2.parser import XBRLParser
from edgar.xbrl2.rendering import render_statement, generate_rich_representation
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
        
        # Reference to legacy XBRLInstance for compatibility
        self.legacy_instance: Optional[LegacyXbrlInstance] = None
        
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
        
    @property
    def facts_view(self):
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
        fact_query = self.facts_view.query()
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
            'CoverPage': ['dei_CoverAbstract'],
        }
        
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
                    statement_type = statement_alias
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
    
    def get_statement(self, role_or_type: str, period_filter: Optional[str] = None,
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
                                 dimensions: Optional[Dict[str, str]] = None) -> Dict[str, Fact]:
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
                
                # Current period vs. Previous periods (always included)
                # If we have 3 or more periods, show all three for balance sheets
                if len(instant_periods) >= 3:
                    period_views.append({
                        'name': 'Current vs. Previous Periods',
                        'description': 'Shows the current period and two previous periods',
                        'period_keys': [instant_periods[0]['key'], instant_periods[1]['key'], instant_periods[2]['key']]
                    })
                else:
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
                         standard: bool = True,
                         show_date_range: bool = False) -> RichTable:
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
        # Determine if this statement should display dimensions
        matching_statements = []
        found_role = None
        actual_statement_type = statement_type
        
        # First, try to find the statement by standard name
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
        
        # Get statement definition if we found a match
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
            return RichTable(title=f"No {statement_type} found")
        
        # Use our optimized indices to find the statement
        matching_statements = []
        actual_statement_type = statement_type
        
        # Ensure indices are built
        if not self._all_statements_cached:
            self.get_all_statements()
        
        # Try to find by standard name
        if statement_type in self._statement_by_standard_name:
            matching_statements = self._statement_by_standard_name[statement_type]
            
        # If not found by standard name, try by role (exact match)
        if not matching_statements and statement_type.startswith('http') and statement_type in self._statement_by_role_uri:
            matching_statements = [self._statement_by_role_uri[statement_type]]
            actual_statement_type = matching_statements[0]['type'] or statement_type
            
        # If not found, try by role name (case-insensitive)
        if not matching_statements:
            role_or_type_lower = statement_type.lower()
            if role_or_type_lower in self._statement_by_role_name:
                matching_statements = self._statement_by_role_name[role_or_type_lower]
                if matching_statements:
                    actual_statement_type = matching_statements[0]['type'] or statement_type
        
        # If still not found, try by definition
        if not matching_statements:
            def_key = statement_type.lower().replace(' ', '')
            if def_key in self._statement_indices:
                matching_statements = self._statement_indices[def_key]
                if matching_statements:
                    actual_statement_type = matching_statements[0]['type'] or statement_type

        statement_info = statement_to_concepts.get(actual_statement_type)
        if statement_info:
            statement_title = statement_info.title
        else:
            statement_title = f"{matching_statements[0]['definition']}" if matching_statements else statement_type
        
        # Use the actual statement type for period selection logic to ensure consistent formatting
        statement_type = actual_statement_type
        
        # Determine the periods to display
        periods_to_display = []
        
        # Get useful entity info for period selection
        entity_info = self.entity_info.copy()  # Make a copy to avoid modifying original
        # Add a reference to the XBRL instance
        entity_info['xbrl_instance'] = self
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
                        
                        # For balance sheets, show appropriate comparison periods
                        # For annual reports, only show other annual periods (fiscal year ends)
                        # For quarterly reports, only show the same quarter from previous years
                        
                        # First determine if this is an annual report or a quarterly report
                        is_annual_report = (fiscal_period_focus == 'FY')
                        
                        # Find the fiscal year end month/day from the current period
                        current_fiscal_month = None
                        current_fiscal_day = None
                        
                        if 'fiscal_year_end_month' in self.entity_info and 'fiscal_year_end_day' in self.entity_info:
                            # Use fiscal year end month/day from entity info
                            current_fiscal_month = self.entity_info.get('fiscal_year_end_month')
                            current_fiscal_day = self.entity_info.get('fiscal_year_end_day')
                        else:
                            # Try to infer from current date for annual reports
                            if is_annual_report:
                                current_fiscal_month = current_date.month
                                current_fiscal_day = current_date.day
                        
                        # Only add comparable periods (up to a total of 3)
                        added_period_keys = [key for key, _ in periods_to_display]
                        for period in instant_periods[1:]:  # Skip current period which should be first
                            if len(periods_to_display) >= 3:
                                break  # Stop when we have 3 periods
                                
                            # For annual reports, only add periods that are also fiscal year ends
                            if is_annual_report and current_fiscal_month is not None:
                                try:
                                    # Check if this period is close to the fiscal year end
                                    period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                                    is_fiscal_year_end = (
                                        period_date.month == current_fiscal_month and
                                        abs(period_date.day - current_fiscal_day) <= 15  # Allow some flexibility
                                    )
                                    
                                    # Only include this period if it's a fiscal year end
                                    if not is_fiscal_year_end:
                                        continue  # Skip non-fiscal-year-end periods
                                except (ValueError, TypeError):
                                    continue  # Skip periods with invalid dates
                            
                            period_key = f"instant_{period['date']}"
                            if period_key not in added_period_keys:
                                try:
                                    # Format consistently
                                    period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                                    simple_label = format_date(period_date)
                                    periods_to_display.append((period_key, simple_label))
                                except (ValueError, TypeError):
                                    # Skip periods with invalid dates
                                    continue
                    except (ValueError, TypeError):
                        # If date parsing failed, still try to select appropriate periods
                        # For annual reports, we should only show fiscal year end periods
                        is_annual_report = (fiscal_period_focus == 'FY')
                        
                        # Get fiscal year end month/day if available
                        current_fiscal_month = self.entity_info.get('fiscal_year_end_month')
                        current_fiscal_day = self.entity_info.get('fiscal_year_end_day')
                        
                        added_count = 0
                        for i, period in enumerate(instant_periods):
                            if i == 0:
                                continue  # Skip first period which should already be added
                                
                            if added_count >= 2:  # Already added 2 more (for a total of 3)
                                break
                            
                            # For annual reports, only add periods that are close to fiscal year end
                            if is_annual_report and current_fiscal_month is not None and current_fiscal_day is not None:
                                try:
                                    period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                                    # Only add periods close to fiscal year end
                                    if period_date.month != current_fiscal_month or abs(period_date.day - current_fiscal_day) > 15:
                                        continue  # Skip periods that aren't fiscal year ends
                                except (ValueError, TypeError):
                                    continue  # Skip periods with invalid dates
                            
                            try:
                                period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                                simple_label = format_date(period_date)
                                period_key = f"instant_{period['date']}"
                                periods_to_display.append((period_key, simple_label))
                                added_count += 1
                            except (ValueError, TypeError):
                                # Skip periods with invalid dates
                                continue
            
            # For Income Statement or Cash Flow - use duration periods
            elif statement_type in ['IncomeStatement', 'CashFlowStatement']:
                # First identify annual periods
                annual_periods = []
                
                # Use fiscal_year_end information if available to better identify annual periods
                fiscal_year_end_month = self.entity_info.get('fiscal_year_end_month')
                fiscal_year_end_day = self.entity_info.get('fiscal_year_end_day')
                
                for period in duration_periods:
                    try:
                        start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                        end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                        days = (end_date - start_date).days
                        
                        # Check if this is likely an annual period
                        is_annual = False
                        
                        # First check fiscal period info (most reliable)
                        if period.get('fiscal_period') == 'FY':
                            is_annual = True
                        # Then check duration (typical annual report is about 365 days)
                        elif 350 <= days <= 380:
                            is_annual = True
                        # Also consider fiscal year end date if available
                        elif (fiscal_year_end_month and fiscal_year_end_day and 
                              abs(days - 365) <= 30 and 
                              end_date.month == fiscal_year_end_month and
                              abs(end_date.day - fiscal_year_end_day) <= 15):
                            is_annual = True
                            
                        if is_annual:
                            annual_periods.append(period)
                    except (ValueError, TypeError):
                        pass
                
                # Sort annual periods by end date to ensure chronological order
                annual_periods.sort(key=lambda p: p['end_date'], reverse=True)
                
                # For annual reports, show FY to FY comparisons (current and previous annual periods)
                if fiscal_period_focus == 'FY' and annual_periods:
                    # Get up to 3 most recent fiscal year periods for comparison
                    for i, period in enumerate(annual_periods[:3]):
                        try:
                            # Use end date to determine fiscal year
                            end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                            # Format using the consistent date formatter
                            simple_label = format_date(end_date)
                            periods_to_display.append((period['key'], simple_label))
                        except (ValueError, TypeError):
                            # Fall back to original label if date parsing fails
                            periods_to_display.append((period['key'], period.get('label', '')))
                
                # For quarterly reports, show current quarter and same quarter previous year
                elif fiscal_period_focus in ['Q1', 'Q2', 'Q3', 'Q4'] and duration_periods:
                    # Filter duration periods to find quarterly periods (typically 80-100 days)
                    quarterly_periods = []
                    for period in duration_periods:
                        try:
                            start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                            end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                            duration_days = (end_date - start_date).days
                            
                            # Check if this is a quarterly period (between 80-100 days)
                            if 80 <= duration_days <= 100:
                                quarterly_periods.append(period)
                        except (ValueError, TypeError):
                            continue  # Skip periods with invalid dates
                    
                    # If no quarterly periods found, log a warning and use the most recent period
                    if not quarterly_periods and duration_periods:
                        print(f"Warning: No quarterly periods (80-100 days) found for {fiscal_period_focus} report. Using most recent period.")
                        quarterly_periods = [duration_periods[0]]
                    
                    # Use the most recent quarterly period as current quarter
                    if quarterly_periods:
                        current_period = quarterly_periods[0]
                        
                        try:
                            current_end = datetime.strptime(current_period['end_date'], '%Y-%m-%d').date()
                            simple_label = format_date(current_end)
                            periods_to_display.append((current_period['key'], simple_label))
                        except (ValueError, TypeError):
                            # Fall back to original label if date parsing fails
                            periods_to_display.append((current_period['key'], current_period['label']))
                    
                    # Try to find same quarter from previous years (up to 2 years back)
                    if quarterly_periods:  # Only proceed if we found a valid current period
                        try:
                            current_start = datetime.strptime(current_period['start_date'], '%Y-%m-%d').date()
                            current_end = datetime.strptime(current_period['end_date'], '%Y-%m-%d').date()
                            current_days = (current_end - current_start).days
                            
                            # Periods from previous years to add (up to 2)
                            prev_year_periods = []
                            
                            # First look in quarterly periods for best matches
                            candidate_periods = []
                            # Start with other quarterly periods
                            for period in quarterly_periods[1:]:
                                candidate_periods.append(period)
                            # Then add other duration periods for broader search if needed
                            for period in duration_periods:
                                if period not in quarterly_periods:
                                    candidate_periods.append(period)
                            
                            # Compare with other periods
                            for period in candidate_periods:
                                try:
                                    period_start = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                                    period_end = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                                    period_days = (period_end - period_start).days
                                    
                                    # Similar length periods from approximately a year apart
                                    days_apart = abs((current_end - period_end).days)
                                    # Check for 1 year ago period
                                    if (abs(period_days - current_days) <= 15 and  # Similar duration (slightly more flexible)
                                        350 <= days_apart <= 380):  # About a year apart
                                        prev_year_periods.append((days_apart, period))
                                    
                                    # Check for 2 years ago period
                                    if (abs(period_days - current_days) <= 15 and  # Similar duration (slightly more flexible)
                                        730 - 30 <= days_apart <= 730 + 30):  # About two years apart
                                        prev_year_periods.append((days_apart, period))
                                except (ValueError, TypeError):
                                    continue
                            
                            # Sort by how closely they match the expected timeframes
                            prev_year_periods.sort()
                            
                            # Add up to 2 periods from previous years
                            for i, (_, period) in enumerate(prev_year_periods[:2]):
                                # Create a more consistent label for comparison periods
                                try:
                                    end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                                    simple_label = format_date(end_date)
                                    periods_to_display.append((period['key'], simple_label))
                                except (ValueError, TypeError):
                                    # Fall back to original label if date parsing fails
                                    periods_to_display.append((period['key'], period.get('label', '')))
                        except (ValueError, TypeError):
                            pass
                
                # If no periods selected yet, or we have less than 3 periods for a balance sheet,
                # use generic approach to select periods. For balance sheets, we want to show 3 columns when available
                needs_more_periods = (statement_type == 'BalanceSheet' and len(periods_to_display) < 3)
                
                if not periods_to_display or needs_more_periods:
                    # For balance sheets, if we already have some periods selected but not enough,
                    # figure out which periods we already have
                    existing_period_keys = [key for key, _ in periods_to_display]
                    
                    # Try to use annual periods if available
                    if annual_periods:
                        for i, period in enumerate(annual_periods[:min(3, len(annual_periods))]):
                            # Check if this period is already selected
                            if period['key'] in existing_period_keys:
                                continue
                                
                            # If we have enough periods, stop
                            if len(periods_to_display) >= 3 and statement_type == 'BalanceSheet':
                                break
                                
                            try:
                                # Use end date to determine fiscal year for consistent labeling
                                end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                                simple_label = format_date(end_date)
                                periods_to_display.append((period['key'], simple_label))
                            except (ValueError, TypeError):
                                # Fall back to original label if date parsing fails
                                periods_to_display.append((period['key'], period.get('label', '')))
                    else:
                        # Fall back to any available duration periods with consistent labeling
                        filtered_periods = duration_periods
                        
                        # For quarterly reports, prioritize proper quarterly periods (80-100 days)
                        if fiscal_period_focus in ['Q1', 'Q2', 'Q3', 'Q4']:
                            quarterly_candidates = []
                            non_quarterly_candidates = []
                            
                            for period in duration_periods:
                                try:
                                    start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                                    end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                                    duration_days = (end_date - start_date).days
                                    
                                    # Check if this is a quarterly period
                                    if 80 <= duration_days <= 100:
                                        quarterly_candidates.append(period)
                                    else:
                                        non_quarterly_candidates.append(period)
                                except (ValueError, TypeError):
                                    non_quarterly_candidates.append(period)
                            
                            # Use quarterly periods first, then fall back to non-quarterly if needed
                            if quarterly_candidates:
                                filtered_periods = quarterly_candidates + non_quarterly_candidates
                        
                        for period in filtered_periods[:min(3, len(filtered_periods))]:
                            # Check if this period is already selected
                            if period['key'] in existing_period_keys:
                                continue
                                
                            # If we have enough periods, stop
                            if len(periods_to_display) >= 3 and statement_type == 'BalanceSheet':
                                break
                                
                            try:
                                end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                                simple_label = format_date(end_date)
                                periods_to_display.append((period['key'], simple_label))
                            except (ValueError, TypeError):
                                # Fall back to original label if date parsing fails
                                periods_to_display.append((period['key'], period.get('label', '')))
            
            # If we still don't have any periods, use period selection logic consistent with known statement types
            if not periods_to_display and all_periods:
                # For balance-sheet-like statements (instant data points)
                if statement_type in ['BalanceSheet']:
                    # Use instant periods
                    if instant_periods:
                        # Take up to 3 most recent instant periods
                        for i, period in enumerate(instant_periods[:3]):
                            period_key = period['key']
                            periods_to_display.append((period_key, period['label']))
                # For income-statement-like statements and other financials (duration data points)
                elif statement_type in ['IncomeStatement', 'CashFlowStatement', 'StatementOfEquity', 'ComprehensiveIncome'] or 'statement' in statement_type.lower():
                    # Check if this is an annual or quarterly report
                    is_annual = fiscal_period_focus == 'FY'
                    
                    if is_annual and duration_periods:
                        # For annual reports, prioritize annual periods (~365 days)
                        annual_periods = []
                        for period in duration_periods:
                            try:
                                start_date = parse_date(period['start_date'])
                                end_date = parse_date(period['end_date'])
                                days = (end_date - start_date).days
                                if 350 <= days <= 380:  # ~365 days
                                    annual_periods.append(period)
                            except (ValueError, TypeError):
                                continue
                                
                        if annual_periods:
                            # Use up to 3 most recent annual periods
                            for i, period in enumerate(annual_periods[:3]):
                                period_key = period['key']
                                periods_to_display.append((period_key, period['label']))
                        else:
                            # Fall back to most recent duration periods
                            for i, period in enumerate(duration_periods[:3]):
                                period_key = period['key']
                                periods_to_display.append((period_key, period['label']))
                    else:
                        # For quarterly reports or unknown, prioritize quarterly periods
                        quarterly_periods = []
                        for period in duration_periods:
                            try:
                                start_date = parse_date(period['start_date'])
                                end_date = parse_date(period['end_date'])
                                days = (end_date - start_date).days
                                if 80 <= days <= 100:  # ~90 days (quarterly)
                                    quarterly_periods.append(period)
                            except (ValueError, TypeError):
                                continue
                                
                        if quarterly_periods:
                            # Use up to 3 most recent quarterly periods
                            for i, period in enumerate(quarterly_periods[:3]):
                                period_key = period['key']
                                periods_to_display.append((period_key, period['label']))
                        else:
                            # Fall back to most recent duration periods
                            for i, period in enumerate(duration_periods[:3]):
                                period_key = period['key']
                                periods_to_display.append((period_key, period['label']))
                # For any other unknown statement types
                else:
                    # Try to find periods closest to document_period_end_date
                    if doc_period_end_date:
                        # Sort periods by how close they are to the document period end date
                        periods_with_distance = []
                        for period in all_periods:
                            try:
                                # For instant periods
                                if period['type'] == 'instant':
                                    period_date = parse_date(period['date'])
                                    distance = abs((period_date - doc_period_end_date).days)
                                    periods_with_distance.append((period, distance))
                                # For duration periods
                                else:
                                    end_date = parse_date(period['end_date'])
                                    distance = abs((end_date - doc_period_end_date).days)
                                    periods_with_distance.append((period, distance))
                            except (ValueError, TypeError):
                                continue
                        
                        # Sort by distance to document_period_end_date
                        periods_with_distance.sort(key=lambda x: x[1])
                        
                        # Add up to 3 closest periods
                        for i, (period, _) in enumerate(periods_with_distance[:3]):
                            period_key = period['key']
                            periods_to_display.append((period_key, period['label']))
                    else:
                        # If no document_period_end_date, use up to 3 periods
                        for i, period in enumerate(all_periods[:3]):
                            period_key = period['key']
                            periods_to_display.append((period_key, period['label']))
        
        # Use the rendering module to render the statement
        return render_statement(
            statement_data,
            periods_to_display,
            statement_title,
            statement_type,
            entity_info,
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
    
    def __str__(self):
        """String representation."""
        return f"XBRL Document with {len(self.facts)} facts, {len(self.contexts)} contexts, and {len(self.presentation_trees)} statements"
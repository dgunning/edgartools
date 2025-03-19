"""
XBRL file parsing functionality.

This module provides functions for parsing XBRL files and extracting data.
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from edgar.core import log

from edgar.xbrl2.models import (
    ElementCatalog, Context, Fact, PresentationNode, PresentationTree,
    CalculationNode, CalculationTree, Axis, Domain, Table, XBRLProcessingError
)
from edgar.xbrl2.core import NAMESPACES, STANDARD_LABEL, extract_element_id, classify_duration


class XBRLParser:
    """Parser for XBRL files."""
    
    def __init__(self):
        # Core data structures
        self.element_catalog: Dict[str, ElementCatalog] = {}
        self.contexts: Dict[str, Context] = {}
        self.facts: Dict[str, Fact] = {}
        self.units: Dict[str, Any] = {}
        
        # Presentation structures
        self.presentation_roles: Dict[str, Dict[str, Any]] = {}
        self.presentation_trees: Dict[str, PresentationTree] = {}
        
        # Calculation structures
        self.calculation_roles: Dict[str, Dict[str, Any]] = {}
        self.calculation_trees: Dict[str, CalculationTree] = {}
        
        # Definition (dimensional) structures
        self.definition_roles: Dict[str, Dict[str, Any]] = {}
        self.tables: Dict[str, List[Table]] = {}
        self.axes: Dict[str, Axis] = {}
        self.domains: Dict[str, Domain] = {}
        
        # Entity information
        self.entity_info: Dict[str, Any] = {}
        
        # Reporting periods
        self.reporting_periods: List[Dict[str, Any]] = []
        
        # Mapping of context IDs to period identifiers for easy lookup
        self.context_period_map: Dict[str, str] = {}
        
    def _create_normalized_fact_key(self, element_id: str, context_ref: str) -> str:
        """
        Create a normalized fact key using underscore format.
        
        Args:
            element_id: Element ID (with either colon or underscore)
            context_ref: Context reference
            
        Returns:
            Normalized fact key
        """
        # Normalize element ID to use underscore format consistently
        normalized_element_id = element_id
        if ':' in element_id:
            prefix, name = element_id.split(':', 1)
            normalized_element_id = f"{prefix}_{name}"
        
        # Create and return the key
        return f"{normalized_element_id}_{context_ref}"
    
    def get_fact(self, element_id: str, context_ref: str) -> Optional[Fact]:
        """
        Get a fact by element ID and context reference.
        Handles both colon and underscore formats transparently.
        
        Args:
            element_id: Element ID (can use either colon or underscore format)
            context_ref: Context reference
            
        Returns:
            Fact if found, None otherwise
        """
        # Create a normalized key and look up the fact
        normalized_key = self._create_normalized_fact_key(element_id, context_ref)
        return self.facts.get(normalized_key)
    
    def parse_directory(self, directory_path: Union[str, Path]) -> None:
        """
        Parse all XBRL files in a directory.
        
        Args:
            directory_path: Path to directory containing XBRL files
        """
        directory = Path(directory_path)
        if not directory.exists() or not directory.is_dir():
            raise ValueError(f"Directory {directory} does not exist or is not a directory")
        
        # Find and categorize files
        instance_file = None
        schema_file = None
        presentation_file = None
        calculation_file = None
        definition_file = None
        label_file = None
        
        for file_path in directory.glob("*"):
            if file_path.is_file():
                file_name = file_path.name.lower()
                
                if file_name.endswith('.xml') and '<xbrl' in file_path.read_text()[:2000]:
                    instance_file = file_path
                elif file_name.endswith('.xsd'):
                    schema_file = file_path
                elif '_pre.xml' in file_name:
                    presentation_file = file_path
                elif '_cal.xml' in file_name:
                    calculation_file = file_path
                elif '_def.xml' in file_name:
                    definition_file = file_path
                elif '_lab.xml' in file_name:
                    label_file = file_path
        
        # Parse schema first to handle embedded linkbases if standalone files aren't available
        if schema_file:
            self.parse_schema(schema_file)
            
            # Check if we have standalone linkbase files
            has_standalone_linkbases = bool(label_file or presentation_file or 
                                          calculation_file or definition_file)
            
            # If no standalone linkbase files, check for embedded linkbases in schema
            if not has_standalone_linkbases:
                # Get the schema content
                schema_content = schema_file.read_text()
                
                # Extract embedded linkbases
                embedded_linkbases = self._extract_embedded_linkbases(schema_content)
                
                # Use embedded linkbases if found
                if embedded_linkbases and 'linkbases' in embedded_linkbases:
                    if 'label' in embedded_linkbases['linkbases']:
                        self.parse_labels_content(embedded_linkbases['linkbases']['label'])
                    
                    if 'presentation' in embedded_linkbases['linkbases']:
                        self.parse_presentation_content(embedded_linkbases['linkbases']['presentation'])
                    
                    if 'calculation' in embedded_linkbases['linkbases']:
                        self.parse_calculation_content(embedded_linkbases['linkbases']['calculation'])
                    
                    if 'definition' in embedded_linkbases['linkbases']:
                        self.parse_definition_content(embedded_linkbases['linkbases']['definition'])
        
        # Parse standalone linkbase files if available
        if label_file:
            self.parse_labels(label_file)
        
        if presentation_file:
            self.parse_presentation(presentation_file)
        
        if calculation_file:
            self.parse_calculation(calculation_file)
        
        if definition_file:
            self.parse_definition(definition_file)
        
        # Parse instance last after all linkbases are processed
        if instance_file:
            self.parse_instance(instance_file)
    
    def parse_schema(self, file_path: Union[str, Path]) -> None:
        """Parse schema file and extract element information."""
        try:
            content = Path(file_path).read_text()
            self.parse_schema_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing schema file {file_path}: {str(e)}")
    
    def parse_schema_content(self, content: str) -> None:
        """Parse schema content and extract element information."""
        try:
            # Register namespaces
            root = ET.fromstring(content)
            
            # Extract element declarations
            for element in root.findall('.//{http://www.w3.org/2001/XMLSchema}element'):
                element_id = element.get('id') or element.get('name')
                if not element_id:
                    continue
                
                # Extract element properties
                name = element.get('name', '')
                data_type = element.get('type', '')
                
                # Check for balance and period type in child annotations
                balance_type = None
                period_type = None
                abstract = element.get('abstract', 'false').lower() == 'true'
                
                # Look for balance and period type
                annotation = element.find('.//{http://www.w3.org/2001/XMLSchema}annotation')
                if annotation is not None:
                    for appinfo in annotation.findall('.//{http://www.w3.org/2001/XMLSchema}appinfo'):
                        balance_element = appinfo.find('.//{http://www.xbrl.org/2003/instance}balance')
                        if balance_element is not None:
                            balance_type = balance_element.text
                        
                        period_element = appinfo.find('.//{http://www.xbrl.org/2003/instance}periodType')
                        if period_element is not None:
                            period_type = period_element.text
                
                # Create element catalog entry
                self.element_catalog[element_id] = ElementCatalog(
                    name=name,
                    data_type=data_type,
                    period_type=period_type or "duration",  # Default to duration
                    balance=balance_type,
                    abstract=abstract,
                    labels={}
                )
                
            # Extract embedded linkbases if present
            embedded_linkbases = self._extract_embedded_linkbases(content)
            
            # If embedded linkbases were found, parse them
            if embedded_linkbases and 'linkbases' in embedded_linkbases:
                if 'label' in embedded_linkbases['linkbases']:
                    self.parse_labels_content(embedded_linkbases['linkbases']['label'])
                
                if 'presentation' in embedded_linkbases['linkbases']:
                    self.parse_presentation_content(embedded_linkbases['linkbases']['presentation'])
                
                if 'calculation' in embedded_linkbases['linkbases']:
                    self.parse_calculation_content(embedded_linkbases['linkbases']['calculation'])
                
                if 'definition' in embedded_linkbases['linkbases']:
                    self.parse_definition_content(embedded_linkbases['linkbases']['definition'])
        
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing schema content: {str(e)}")
    
    def _extract_embedded_linkbases(self, schema_content: str) -> Dict[str, Dict[str, str]]:
        """
        Extract embedded linkbases and role types from the schema file.
        
        Args:
            schema_content: XML content of the schema file
            
        Returns:
            Dictionary containing embedded linkbases and role type information
        """
        embedded_data = {
            'linkbases': {},
            'role_types': {}
        }

        try:
            # Register namespaces
            for prefix, uri in NAMESPACES.items():
                ET.register_namespace(prefix, uri)

            # Parse the schema content
            root = ET.fromstring(schema_content)

            # Find all appinfo elements
            for appinfo in root.findall('.//xsd:appinfo', NAMESPACES):
                # Extract role types
                for role_type in appinfo.findall('link:roleType', NAMESPACES):
                    role_uri = role_type.get('roleURI')
                    role_id = role_type.get('id')
                    definition = role_type.find('link:definition', NAMESPACES)
                    definition_text = definition.text if definition is not None else ""
                    used_on = [elem.text for elem in role_type.findall('link:usedOn', NAMESPACES)]

                    embedded_data['role_types'][role_uri] = {
                        'id': role_id,
                        'definition': definition_text,
                        'used_on': used_on
                    }

                # Find the linkbase element
                linkbase = appinfo.find('link:linkbase', NAMESPACES)
                if linkbase is not None:
                    # Extract the entire linkbase element as a string
                    linkbase_string = ET.tostring(linkbase, encoding='unicode', method='xml')

                    # Extract each type of linkbase
                    for linkbase_type in ['presentation', 'label', 'calculation', 'definition']:
                        linkbase_elements = linkbase.findall(f'link:{linkbase_type}Link', NAMESPACES)

                        if linkbase_elements:
                            # Convert all linkbase elements of this type to strings
                            linkbase_strings = [ET.tostring(elem, encoding='unicode', method='xml') for elem in
                                              linkbase_elements]

                            # Join multiple linkbase elements if there are more than one, and wrap them in the linkbase tags
                            embedded_data['linkbases'][linkbase_type] = f"{linkbase_string.split('>', 1)[0]}>\n" + \
                                                                      '\n'.join(linkbase_strings) + \
                                                                      "\n</link:linkbase>"
            
            return embedded_data
        except Exception as e:
            # Log the error but don't fail - just return empty embedded data
            log.warning(f"Warning: Error extracting embedded linkbases: {str(e)}")
            return embedded_data
    
    def parse_labels(self, file_path: Union[str, Path]) -> None:
        """Parse label linkbase file and extract label information."""
        try:
            content = Path(file_path).read_text()
            self.parse_labels_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing label file {file_path}: {str(e)}")
    
    def parse_labels_content(self, content: str) -> None:
        """Parse label linkbase content and extract label information."""
        try:
            root = ET.fromstring(content)
            
            # Extract label arcs and labels
            label_arcs = root.findall('.//{http://www.xbrl.org/2003/linkbase}labelArc')
            labels = root.findall('.//{http://www.xbrl.org/2003/linkbase}label')
            
            # Create label lookup by id
            label_lookup = {}
            for label in labels:
                label_id = label.get('{http://www.w3.org/1999/xlink}label')
                if not label_id:
                    continue
                
                role = label.get('{http://www.w3.org/1999/xlink}role', 'http://www.xbrl.org/2003/role/label')
                lang = label.get('{http://www.w3.org/XML/1998/namespace}lang', 'en-US')
                
                if label.text is not None:
                    if label_id not in label_lookup:
                        label_lookup[label_id] = {}
                    
                    if lang not in label_lookup[label_id]:
                        label_lookup[label_id][lang] = {}
                    
                    label_lookup[label_id][lang][role] = label.text
            
            # Connect labels to elements using arcs
            for arc in label_arcs:
                from_ref = arc.get('{http://www.w3.org/1999/xlink}from')
                to_ref = arc.get('{http://www.w3.org/1999/xlink}to')
                
                if not from_ref or not to_ref:
                    continue
                
                # Find the element being connected to the label
                element_loc = root.find(f'.//*[@{{{NAMESPACES["xlink"]}}}label="{from_ref}"]')
                if element_loc is None:
                    continue
                
                href = element_loc.get('{http://www.w3.org/1999/xlink}href')
                if not href:
                    continue
                
                # Extract element ID from href
                element_id = extract_element_id(href)
                
                # Find labels for this element
                if to_ref in label_lookup and 'en-US' in label_lookup[to_ref]:
                    element_labels = label_lookup[to_ref]['en-US']
                    
                    # Add labels to element catalog
                    if element_id in self.element_catalog:
                        self.element_catalog[element_id].labels.update(element_labels)
                    else:
                        # Create placeholder in catalog
                        self.element_catalog[element_id] = ElementCatalog(
                            name=element_id,
                            data_type="",
                            period_type="duration",
                            labels=element_labels
                        )
        
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing label content: {str(e)}")
    
    def parse_presentation(self, file_path: Union[str, Path]) -> None:
        """Parse presentation linkbase file and build presentation trees."""
        try:
            content = Path(file_path).read_text()
            self.parse_presentation_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing presentation file {file_path}: {str(e)}")
    
    def parse_presentation_content(self, content: str) -> None:
        """Parse presentation linkbase content and build presentation trees."""
        try:
            root = ET.fromstring(content)
            
            # Extract presentation links
            presentation_links = root.findall('.//{http://www.xbrl.org/2003/linkbase}presentationLink')
            
            for link in presentation_links:
                role = link.get('{http://www.w3.org/1999/xlink}role')
                if not role:
                    continue
                
                # Store role information
                role_id = role.split('/')[-1] if '/' in role else role
                role_def = role_id.replace('_', ' ')
                
                self.presentation_roles[role] = {
                    'roleUri': role,
                    'definition': role_def,
                    'roleId': role_id
                }
                
                # Extract arcs
                arcs = link.findall('.//{http://www.xbrl.org/2003/linkbase}presentationArc')
                
                # Create relationships map
                relationships = []
                
                for arc in arcs:
                    from_ref = arc.get('{http://www.w3.org/1999/xlink}from')
                    to_ref = arc.get('{http://www.w3.org/1999/xlink}to')
                    order = float(arc.get('order', '1.0'))
                    preferred_label = arc.get('preferredLabel')
                    
                    if not from_ref or not to_ref:
                        continue
                    
                    # Find locators for from/to references
                    from_loc = link.find(f'.//*[@{{{NAMESPACES["xlink"]}}}label="{from_ref}"]')
                    to_loc = link.find(f'.//*[@{{{NAMESPACES["xlink"]}}}label="{to_ref}"]')
                    
                    if from_loc is None or to_loc is None:
                        continue
                    
                    from_href = from_loc.get('{http://www.w3.org/1999/xlink}href')
                    to_href = to_loc.get('{http://www.w3.org/1999/xlink}href')
                    
                    if not from_href or not to_href:
                        continue
                    
                    # Extract element IDs
                    from_element = extract_element_id(from_href)
                    to_element = extract_element_id(to_href)
                    
                    # Add relationship
                    relationships.append({
                        'from_element': from_element,
                        'to_element': to_element,
                        'order': order,
                        'preferred_label': preferred_label
                    })
                
                # Build presentation tree for this role
                if relationships:
                    self._build_presentation_tree(role, relationships)
        
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing presentation content: {str(e)}")
    
    def _build_presentation_tree(self, role: str, relationships: List[Dict[str, Any]]) -> None:
        """
        Build a presentation tree from relationships.
        
        Args:
            role: Extended link role URI
            relationships: List of relationships (from_element, to_element, order, preferred_label)
        """
        # Group relationships by source element
        from_map = {}
        to_map = {}
        
        for rel in relationships:
            from_element = rel['from_element']
            to_element = rel['to_element']
            
            if from_element not in from_map:
                from_map[from_element] = []
            from_map[from_element].append(rel)
            
            if to_element not in to_map:
                to_map[to_element] = []
            to_map[to_element].append(rel)
        
        # Find root elements (appear as 'from' but not as 'to')
        root_elements = set(from_map.keys()) - set(to_map.keys())
        
        if not root_elements:
            return  # No root elements found
        
        # Create presentation tree
        tree = PresentationTree(
            role_uri=role,
            definition=self.presentation_roles[role]['definition'],
            root_element_id=next(iter(root_elements)),
            all_nodes={}
        )
        
        # Build tree recursively
        for root_id in root_elements:
            self._build_presentation_subtree(root_id, None, 0, from_map, tree.all_nodes)
        
        # Add tree to collection
        self.presentation_trees[role] = tree
    
    def _build_presentation_subtree(self, element_id: str, parent_id: Optional[str], depth: int,
                                 from_map: Dict[str, List[Dict[str, Any]]], 
                                 all_nodes: Dict[str, PresentationNode]) -> None:
        """
        Recursively build a presentation subtree.
        
        Args:
            element_id: Current element ID
            parent_id: Parent element ID
            depth: Current depth in tree
            from_map: Map of relationships by source element
            all_nodes: Dictionary to store all nodes
        """
        # Create node
        node = PresentationNode(
            element_id=element_id,
            parent=parent_id,
            children=[],
            depth=depth
        )
        
        # Add element information if available
        if element_id in self.element_catalog:
            elem_info = self.element_catalog[element_id]
            node.element_name = elem_info.name
            node.standard_label = elem_info.labels.get('http://www.xbrl.org/2003/role/label', elem_info.name)
            node.is_abstract = elem_info.abstract
            node.labels = elem_info.labels
        
        # Add to collection
        all_nodes[element_id] = node
        
        # Process children
        if element_id in from_map:
            # Sort children by order
            children = sorted(from_map[element_id], key=lambda r: r['order'])
            
            for rel in children:
                child_id = rel['to_element']
                
                # Add child to parent's children list
                node.children.append(child_id)
                
                # Set preferred label
                preferred_label = rel['preferred_label']
                
                # Recursively build child subtree
                self._build_presentation_subtree(
                    child_id, element_id, depth + 1, from_map, all_nodes
                )
                
                # Update preferred label after child is built
                if preferred_label and child_id in all_nodes:
                    all_nodes[child_id].preferred_label = preferred_label
    
    def parse_calculation(self, file_path: Union[str, Path]) -> None:
        """Parse calculation linkbase file and build calculation trees."""
        try:
            content = Path(file_path).read_text()
            self.parse_calculation_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing calculation file {file_path}: {str(e)}")
    
    def parse_calculation_content(self, content: str) -> None:
        """Parse calculation linkbase content and build calculation trees."""
        try:
            root = ET.fromstring(content)
            
            # Extract calculation links
            calculation_links = root.findall('.//{http://www.xbrl.org/2003/linkbase}calculationLink')
            
            for link in calculation_links:
                role = link.get('{http://www.w3.org/1999/xlink}role')
                if not role:
                    continue
                
                # Store role information
                role_id = role.split('/')[-1] if '/' in role else role
                role_def = role_id.replace('_', ' ')
                
                self.calculation_roles[role] = {
                    'roleUri': role,
                    'definition': role_def,
                    'roleId': role_id
                }
                
                # Extract arcs
                arcs = link.findall('.//{http://www.xbrl.org/2003/linkbase}calculationArc')
                
                # Create relationships list
                relationships = []
                
                for arc in arcs:
                    from_ref = arc.get('{http://www.w3.org/1999/xlink}from')
                    to_ref = arc.get('{http://www.w3.org/1999/xlink}to')
                    order = float(arc.get('order', '1.0'))
                    weight = float(arc.get('weight', '1.0'))
                    
                    if not from_ref or not to_ref:
                        continue
                    
                    # Find locators for from/to references
                    from_loc = link.find(f'.//*[@{{{NAMESPACES["xlink"]}}}label="{from_ref}"]')
                    to_loc = link.find(f'.//*[@{{{NAMESPACES["xlink"]}}}label="{to_ref}"]')
                    
                    if from_loc is None or to_loc is None:
                        continue
                    
                    from_href = from_loc.get('{http://www.w3.org/1999/xlink}href')
                    to_href = to_loc.get('{http://www.w3.org/1999/xlink}href')
                    
                    if not from_href or not to_href:
                        continue
                    
                    # Extract element IDs
                    from_element = extract_element_id(from_href)
                    to_element = extract_element_id(to_href)
                    
                    # Add relationship
                    relationships.append({
                        'from_element': from_element,
                        'to_element': to_element,
                        'order': order,
                        'weight': weight
                    })
                
                # Build calculation tree for this role
                if relationships:
                    self._build_calculation_tree(role, relationships)
        
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing calculation content: {str(e)}")
    
    def _build_calculation_tree(self, role: str, relationships: List[Dict[str, Any]]) -> None:
        """
        Build a calculation tree from relationships.
        
        Args:
            role: Extended link role URI
            relationships: List of relationships (from_element, to_element, order, weight)
        """
        # Group relationships by source element
        from_map = {}
        to_map = {}
        
        for rel in relationships:
            from_element = rel['from_element']
            to_element = rel['to_element']
            
            if from_element not in from_map:
                from_map[from_element] = []
            from_map[from_element].append(rel)
            
            if to_element not in to_map:
                to_map[to_element] = []
            to_map[to_element].append(rel)
        
        # Find root elements (appear as 'from' but not as 'to')
        root_elements = set(from_map.keys()) - set(to_map.keys())
        
        if not root_elements:
            return  # No root elements found
        
        # Create calculation tree
        tree = CalculationTree(
            role_uri=role,
            definition=self.calculation_roles[role]['definition'],
            root_element_id=next(iter(root_elements)),
            all_nodes={}
        )
        
        # Build tree recursively
        for root_id in root_elements:
            self._build_calculation_subtree(root_id, None, from_map, tree.all_nodes)
        
        # Add tree to collection
        self.calculation_trees[role] = tree
    
    def _build_calculation_subtree(self, element_id: str, parent_id: Optional[str],
                               from_map: Dict[str, List[Dict[str, Any]]], 
                               all_nodes: Dict[str, CalculationNode]) -> None:
        """
        Recursively build a calculation subtree.
        
        Args:
            element_id: Current element ID
            parent_id: Parent element ID
            from_map: Map of relationships by source element
            all_nodes: Dictionary to store all nodes
        """
        # Create node
        node = CalculationNode(
            element_id=element_id,
            parent=parent_id,
            children=[]
        )
        
        # Add element information if available
        if element_id in self.element_catalog:
            elem_info = self.element_catalog[element_id]
            node.balance_type = elem_info.balance
            node.period_type = elem_info.period_type
        
        # Add to collection
        all_nodes[element_id] = node
        
        # Process children
        if element_id in from_map:
            # Sort children by order
            children = sorted(from_map[element_id], key=lambda r: r['order'])
            
            for rel in children:
                child_id = rel['to_element']
                
                # Add child to parent's children list
                node.children.append(child_id)
                
                # Set weight
                weight = rel['weight']
                
                # Recursively build child subtree
                self._build_calculation_subtree(
                    child_id, element_id, from_map, all_nodes
                )
                
                # Update weight after child is built
                if child_id in all_nodes:
                    all_nodes[child_id].weight = weight
    
    def parse_definition(self, file_path: Union[str, Path]) -> None:
        """Parse definition linkbase file and build dimensional structures."""
        try:
            content = Path(file_path).read_text()
            self.parse_definition_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing definition file {file_path}: {str(e)}")
    
    def parse_definition_content(self, content: str) -> None:
        """Parse definition linkbase content and build dimensional structures."""
        try:
            root = ET.fromstring(content)
            
            # Extract definition links
            definition_links = root.findall('.//{http://www.xbrl.org/2003/linkbase}definitionLink')
            
            for link in definition_links:
                role = link.get('{http://www.w3.org/1999/xlink}role')
                if not role:
                    continue
                
                # Store role information
                role_id = role.split('/')[-1] if '/' in role else role
                role_def = role_id.replace('_', ' ')
                
                self.definition_roles[role] = {
                    'roleUri': role,
                    'definition': role_def,
                    'roleId': role_id
                }
                
                # Extract arcs
                arcs = link.findall('.//{http://www.xbrl.org/2003/linkbase}definitionArc')
                
                # Create relationships list
                relationships = []
                
                for arc in arcs:
                    from_ref = arc.get('{http://www.w3.org/1999/xlink}from')
                    to_ref = arc.get('{http://www.w3.org/1999/xlink}to')
                    order = float(arc.get('order', '1.0'))
                    
                    # Get the arcrole - this is important for identifying dimensional relationships
                    arcrole = arc.get('{http://www.w3.org/1999/xlink}arcrole')
                    if not from_ref or not to_ref or not arcrole:
                        continue
                    
                    # Find locators for from/to references
                    from_loc = link.find(f'.//*[@{{{NAMESPACES["xlink"]}}}label="{from_ref}"]')
                    to_loc = link.find(f'.//*[@{{{NAMESPACES["xlink"]}}}label="{to_ref}"]')
                    
                    if from_loc is None or to_loc is None:
                        continue
                    
                    from_href = from_loc.get('{http://www.w3.org/1999/xlink}href')
                    to_href = to_loc.get('{http://www.w3.org/1999/xlink}href')
                    
                    if not from_href or not to_href:
                        continue
                    
                    # Extract element IDs
                    from_element = extract_element_id(from_href)
                    to_element = extract_element_id(to_href)
                    
                    # Add relationship with arcrole
                    relationships.append({
                        'from_element': from_element,
                        'to_element': to_element,
                        'order': order,
                        'arcrole': arcrole
                    })
                
                # Process dimensional structures from relationships
                self._process_dimensional_relationships(role, relationships)
        
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing definition content: {str(e)}")
    
    def _process_dimensional_relationships(self, role: str, relationships: List[Dict[str, Any]]) -> None:
        """
        Process dimensional relationships to build tables, axes, and domains.
        
        Args:
            role: Extended link role URI
            relationships: List of dimensional relationships
        """
        # XBRL Dimensions arcrole URIs
        HYPERCUBE_DIMENSION = "http://xbrl.org/int/dim/arcrole/hypercube-dimension"
        DIMENSION_DOMAIN = "http://xbrl.org/int/dim/arcrole/dimension-domain"
        DOMAIN_MEMBER = "http://xbrl.org/int/dim/arcrole/domain-member"
        ALL = "http://xbrl.org/int/dim/arcrole/all"
        
        # Group relationships by arcrole
        grouped_rels = {}
        for rel in relationships:
            arcrole = rel['arcrole']
            if arcrole not in grouped_rels:
                grouped_rels[arcrole] = []
            grouped_rels[arcrole].append(rel)
        
        # Process hypercube-dimension relationships to identify tables and axes
        hypercube_axes = {}  # Map of hypercubes to their axes
        if HYPERCUBE_DIMENSION in grouped_rels:
            for rel in grouped_rels[HYPERCUBE_DIMENSION]:
                table_id = rel['from_element']
                axis_id = rel['to_element']
                
                if table_id not in hypercube_axes:
                    hypercube_axes[table_id] = []
                
                hypercube_axes[table_id].append(axis_id)
                
                # Create or update axis
                if axis_id not in self.axes:
                    self.axes[axis_id] = Axis(
                        element_id=axis_id,
                        label=self._get_element_label(axis_id)
                    )
        
        # Process dimension-domain relationships to link axes to domains
        if DIMENSION_DOMAIN in grouped_rels:
            for rel in grouped_rels[DIMENSION_DOMAIN]:
                axis_id = rel['from_element']
                domain_id = rel['to_element']
                
                # Link domain to axis
                if axis_id in self.axes:
                    self.axes[axis_id].domain_id = domain_id
                
                # Create or update domain
                if domain_id not in self.domains:
                    self.domains[domain_id] = Domain(
                        element_id=domain_id,
                        label=self._get_element_label(domain_id)
                    )
        
        # Process domain-member relationships to build domain hierarchies
        if DOMAIN_MEMBER in grouped_rels:
            # Group by parent (domain) element
            domain_members = {}
            for rel in grouped_rels[DOMAIN_MEMBER]:
                domain_id = rel['from_element']
                member_id = rel['to_element']
                
                if domain_id not in domain_members:
                    domain_members[domain_id] = []
                
                domain_members[domain_id].append(member_id)
                
                # Also create the domain if it doesn't exist
                if domain_id not in self.domains:
                    self.domains[domain_id] = Domain(
                        element_id=domain_id,
                        label=self._get_element_label(domain_id)
                    )
            
            # Update domains with their members
            for domain_id, members in domain_members.items():
                if domain_id in self.domains:
                    self.domains[domain_id].members = members
        
        # Process 'all' relationships to identify line items and build hypercubes (tables)
        if ALL in grouped_rels:
            tables_by_role = []
            for rel in grouped_rels[ALL]:
                line_items_id = rel['to_element']
                table_id = rel['from_element']
                
                # Only process if this table has axes defined
                if table_id in hypercube_axes:
                    table = Table(
                        element_id=table_id,
                        label=self._get_element_label(table_id),
                        role_uri=role,
                        axes=hypercube_axes[table_id],
                        line_items=[line_items_id],
                        closed=False  # Default
                    )
                    tables_by_role.append(table)
            
            # Add tables to collection
            if tables_by_role:
                self.tables[role] = tables_by_role
    
    def _get_element_label(self, element_id: str) -> str:
        """Get the label for an element, falling back to the element ID if not found."""
        if element_id in self.element_catalog and self.element_catalog[element_id].labels:
            # Use standard label if available
            standard_label = self.element_catalog[element_id].labels.get(STANDARD_LABEL)
            if standard_label:
                return standard_label
        return element_id  # Fallback to element ID
    
    def parse_instance(self, file_path: Union[str, Path]) -> None:
        """Parse instance document file and extract contexts, facts, and units."""
        try:
            content = Path(file_path).read_text()
            self.parse_instance_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing instance file {file_path}: {str(e)}")
    
    def parse_instance_content(self, content: str) -> None:
        """Parse instance document content and extract contexts, facts, and units."""
        try:
            root = ET.fromstring(content)
            
            # Extract contexts
            self._extract_contexts(root)
            
            # Extract units
            self._extract_units(root)
            
            # Extract facts
            self._extract_facts(root)
            
            # Extract entity information
            self._extract_entity_info()
            
            # Build reporting periods
            self._build_reporting_periods()
        
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing instance content: {str(e)}")
    
    def _extract_contexts(self, root: ET.Element) -> None:
        """Extract contexts from instance document."""
        try:
            # Find all context elements
            for context_elem in root.findall('.//{http://www.xbrl.org/2003/instance}context'):
                context_id = context_elem.get('id')
                if not context_id:
                    continue
                
                # Create context object
                context = Context(context_id=context_id)
                
                # Extract entity information
                entity_elem = context_elem.find('.//{http://www.xbrl.org/2003/instance}entity')
                if entity_elem is not None:
                    # Get identifier
                    identifier_elem = entity_elem.find('.//{http://www.xbrl.org/2003/instance}identifier')
                    if identifier_elem is not None:
                        scheme = identifier_elem.get('scheme', '')
                        identifier = identifier_elem.text
                        context.entity = {
                            'scheme': scheme,
                            'identifier': identifier
                        }
                    
                    # Get segment dimensions if present
                    segment_elem = entity_elem.find('.//{http://www.xbrl.org/2003/instance}segment')
                    if segment_elem is not None:
                        # Extract explicit dimensions
                        for dim_elem in segment_elem.findall('.//{http://xbrl.org/2006/xbrldi}explicitMember'):
                            dimension = dim_elem.get('dimension')
                            value = dim_elem.text
                            if dimension and value:
                                context.dimensions[dimension] = value
                        
                        # Extract typed dimensions
                        for dim_elem in segment_elem.findall('.//{http://xbrl.org/2006/xbrldi}typedMember'):
                            dimension = dim_elem.get('dimension')
                            if dimension:
                                # The typed dimension value is the first child element
                                for child in dim_elem:
                                    context.dimensions[dimension] = child.tag
                                    break
                
                # Extract period information
                period_elem = context_elem.find('.//{http://www.xbrl.org/2003/instance}period')
                if period_elem is not None:
                    # Check for instant period
                    instant_elem = period_elem.find('.//{http://www.xbrl.org/2003/instance}instant')
                    if instant_elem is not None and instant_elem.text:
                        context.period = {
                            'type': 'instant',
                            'instant': instant_elem.text
                        }
                    
                    # Check for duration period
                    start_elem = period_elem.find('.//{http://www.xbrl.org/2003/instance}startDate')
                    end_elem = period_elem.find('.//{http://www.xbrl.org/2003/instance}endDate')
                    if start_elem is not None and end_elem is not None and start_elem.text and end_elem.text:
                        context.period = {
                            'type': 'duration',
                            'startDate': start_elem.text,
                            'endDate': end_elem.text
                        }
                    
                    # Check for forever period
                    forever_elem = period_elem.find('.//{http://www.xbrl.org/2003/instance}forever')
                    if forever_elem is not None:
                        context.period = {
                            'type': 'forever'
                        }
                
                # Add context to registry
                self.contexts[context_id] = context
        
        except Exception as e:
            raise XBRLProcessingError(f"Error extracting contexts: {str(e)}")
    
    def _extract_units(self, root: ET.Element) -> None:
        """Extract units from instance document."""
        try:
            # Find all unit elements
            for unit_elem in root.findall('.//{http://www.xbrl.org/2003/instance}unit'):
                unit_id = unit_elem.get('id')
                if not unit_id:
                    continue
                
                # Check for measure
                measure_elem = unit_elem.find('.//{http://www.xbrl.org/2003/instance}measure')
                if measure_elem is not None and measure_elem.text:
                    self.units[unit_id] = {
                        'type': 'simple',
                        'measure': measure_elem.text
                    }
                    continue
                
                # Check for divide
                divide_elem = unit_elem.find('.//{http://www.xbrl.org/2003/instance}divide')
                if divide_elem is not None:
                    # Get numerator
                    numerator_elem = divide_elem.find('.//{http://www.xbrl.org/2003/instance}unitNumerator')
                    denominator_elem = divide_elem.find('.//{http://www.xbrl.org/2003/instance}unitDenominator')
                    
                    if numerator_elem is not None and denominator_elem is not None:
                        # Get measures
                        numerator_measures = [elem.text for elem in numerator_elem.findall('.//{http://www.xbrl.org/2003/instance}measure') if elem.text]
                        denominator_measures = [elem.text for elem in denominator_elem.findall('.//{http://www.xbrl.org/2003/instance}measure') if elem.text]
                        
                        self.units[unit_id] = {
                            'type': 'divide',
                            'numerator': numerator_measures,
                            'denominator': denominator_measures
                        }
        
        except Exception as e:
            raise XBRLProcessingError(f"Error extracting units: {str(e)}")
    
    def _extract_facts(self, root: ET.Element) -> None:
        """Extract facts from instance document."""
        try:
            # Namespace mappings to help with element identification
            namespaces = {
                'xbrli': 'http://www.xbrl.org/2003/instance',
                'us-gaap': 'http://fasb.org/us-gaap/2023',  # More generic pattern
                'ifrs': 'http://xbrl.ifrs.org/taxonomy/2023',  # More generic pattern
                'dei': 'http://xbrl.sec.gov/dei/2023',  # More generic pattern
            }
            
            # Track prefixes found in the document
            prefix_map = {}
            
            # First, detect any namespace declarations in the root element
            for attr_name, attr_value in root.attrib.items():
                if attr_name.startswith('{http://www.w3.org/2000/xmlns/}') or attr_name.startswith('xmlns:'):
                    # Extract the prefix 
                    if attr_name.startswith('{http://www.w3.org/2000/xmlns/}'):
                        prefix = attr_name.split('}', 1)[1]
                    else:
                        prefix = attr_name.split(':', 1)[1]
                    
                    # Map URI to prefix
                    prefix_map[attr_value] = prefix
                    
                    # If this is one of our standard namespaces, update it
                    for std_prefix, std_uri in namespaces.items():
                        if attr_value.startswith(std_uri.split('/20')[0]):
                            namespaces[std_prefix] = attr_value
            
            fact_count = 0
            nonstandard_facts = []
            
            # Find all elements that might be facts (both top-level and nested)
            all_elements = []
            for child in root:
                if child.tag.endswith('}context') or child.tag.endswith('}unit') or child.tag.endswith('}schemaRef'):
                    continue
                all_elements.append(child)
                # Also check for nested elements that might be facts
                for descendant in child.findall('.//*'):
                    all_elements.append(descendant)
            
            for child in all_elements:
                # Extract fact information
                element_name = None
                namespace = None
                
                # Get element namespace and name
                if '}' in child.tag:
                    namespace, element_name = child.tag.split('}', 1)
                    namespace = namespace.strip('{')
                else:
                    element_name = child.tag
                
                # Get context and unit references
                context_ref = child.get('contextRef')
                
                # Skip if no context reference (not a fact)
                if not context_ref:
                    continue
                
                # Get namespace prefix
                prefix = prefix_map.get(namespace)
                if not prefix:
                    # Try to match with known namespaces
                    for std_prefix, std_uri in namespaces.items():
                        if namespace.startswith(std_uri.split('/20')[0]):
                            prefix = std_prefix
                            break
                
                # Construct element ID with prefix if available
                if prefix:
                    element_id = f"{prefix}:{element_name}"
                else:
                    # For non-standard namespaces, create a placeholder
                    element_id = element_name
                    # Track these to help with debugging
                    if namespace not in nonstandard_facts:
                        nonstandard_facts.append(namespace)
                
                # Get unit reference
                unit_ref = child.get('unitRef')
                
                # Get value
                value = child.text
                if value is None or value.strip() == "":
                    # Check if there's a nested value element
                    for sub_elem in child:
                        if sub_elem.text and sub_elem.text.strip() != "":
                            value = sub_elem.text
                            break
                
                if value is None:
                    value = ""
                
                # Get decimals attribute
                decimals = child.get('decimals')
                
                # Create numeric value if possible
                numeric_value = None
                try:
                    # Clean and parse the value
                    clean_value = value.strip().replace(',', '')
                    if clean_value:
                        numeric_value = float(clean_value)
                except (ValueError, TypeError):
                    pass
                
                # Create fact object
                fact = Fact(
                    element_id=element_id,
                    context_ref=context_ref,
                    value=value.strip() if value else "",
                    unit_ref=unit_ref,
                    decimals=decimals,
                    numeric_value=numeric_value
                )
                
                # Create a normalized key using underscore format for consistency
                normalized_key = self._create_normalized_fact_key(element_id, context_ref)
                
                # Store the fact once with the normalized key
                self.facts[normalized_key] = fact
                
                fact_count += 1
            
            # Debug information
            log.debug(f"Extracted {fact_count} facts")
            if nonstandard_facts:
                log.debug(f"Found {len(nonstandard_facts)} non-standard namespaces: {nonstandard_facts[:5]}...")
            
            # Double check that we found facts
            if fact_count == 0:
                log.warning("WARNING: No facts were extracted from the instance document!")
            
            # Apply calculation weights after all facts are extracted
            self._apply_calculation_weights()
                
        except Exception as e:
            raise XBRLProcessingError(f"Error extracting facts: {str(e)}")
            
    def _apply_calculation_weights(self) -> None:
        """
        Apply calculation weights to facts based on calculation linkbase information.
        
        This method handles the application of negative weights from calculation arcs.
        Per XBRL specification, a negative weight should flip the sign of a fact value
        when used in calculations. This is particularly common with elements like
        "IncreaseDecreaseInInventories" which should be negated when contributing
        to cash flow calculations.
        """
        try:
            # Create a mapping of normalized element IDs to their calculation nodes
            element_to_calc_node = {}
            
            # Populate the mapping from all calculation trees
            for role_uri, calc_tree in self.calculation_trees.items():
                for element_id, node in calc_tree.all_nodes.items():
                    # Always store with normalized element ID (underscore format)
                    normalized_element_id = element_id.replace(':', '_') if ':' in element_id else element_id
                    element_to_calc_node[normalized_element_id] = node
            
            # Apply calculation weights to facts
            adjusted_count = 0
            
            # Find and adjust facts with negative weights
            for fact_key, fact in list(self.facts.items()):
                # Normalize the element ID for lookup
                element_id = fact.element_id
                normalized_element_id = element_id.replace(':', '_') if ':' in element_id else element_id
                
                # Look up the calculation node using the normalized element ID
                calc_node = element_to_calc_node.get(normalized_element_id)
                
                # Apply negative weights if found
                if calc_node and calc_node.weight < 0:
                    if fact.numeric_value is not None:
                        # Store original for logging
                        original_value = fact.numeric_value
                        
                        # Apply the weight (negate the value)
                        fact.numeric_value = -fact.numeric_value
                        
                        # Also update the string value if present
                        if fact.value:
                            # Handle positive values
                            if not fact.value.startswith('-'):
                                fact.value = f"-{fact.value}"
                            # Handle negative values
                            else:
                                fact.value = fact.value[1:]
                        
                        # Update fact in the dictionary
                        self.facts[fact_key] = fact
                        adjusted_count += 1
                        
                        log.debug(f"Adjusted fact {fact.element_id}: {original_value} -> {fact.numeric_value}")
            
            log.debug(f"Applied calculation weights to {adjusted_count} facts")
            
        except Exception as e:
            # Log the error but don't fail the entire parsing process
            log.warning(f"Warning: Error applying calculation weights: {str(e)}")
            # Include stack trace for debugging
            import traceback
            log.debug(traceback.format_exc())
    
    def _extract_entity_info(self) -> None:
        """Extract entity information from contexts and DEI facts."""
        try:
            # Initialize entity info
            self.entity_info = {
                'entity_name': None,
                'ticker': None,
                'identifier': None,
                'document_type': None,
                'reporting_end_date': None,
                'document_period_end_date': None,
                'fiscal_year': None,
                'fiscal_period': None,
                'fiscal_year_end_month': None,
                'fiscal_year_end_day': None,
                'annual_report': False,
                'quarterly_report': False,
                'amendment': False
            }
            
            # Get CIK from first context
            if self.contexts:
                first_context = next(iter(self.contexts.values()))
                if 'identifier' in first_context.entity:
                    identifier = first_context.entity['identifier']
                    # Clean up CIK (remove leading zeros)
                    if identifier and identifier.isdigit():
                        self.entity_info['identifier'] = identifier.lstrip('0')
            
            # Define DEI fact names we're looking for based on xbrl.py.bak
            dei_fact_names = {
                'fiscal_year': ['DocumentFiscalYearFocus', 'FiscalYearFocus', 'FiscalYear'],
                'fiscal_period': ['DocumentFiscalPeriodFocus', 'FiscalPeriodFocus'],
                'current_fiscal_year_end_date': ['CurrentFiscalYearEndDate'],
                'fiscal_year_end': ['FiscalYearEnd', 'CurrentFiscalYearEndDate'],
                'document_type': ['DocumentType'],
                'document_period_end_date': ['DocumentPeriodEndDate'],
                'entity_name': ['EntityRegistrantName'],
                'ticker': ['TradingSymbol'],
                'quarterly_report': ['DocumentQuarterlyReport'],
                'annual_report': ['DocumentAnnualReport'],
            }
            
            # Search for DEI facts
            dei_facts = {}
            
            # Look for DEI facts with different namespace patterns
            dei_prefixes = ['dei:', 'dei_']
            
            for key, fact in self.facts.items():
                is_dei_fact = False
                
                # Check if the fact has a DEI prefix
                if any(fact.element_id.startswith(prefix) for prefix in dei_prefixes) or any(prefix in key.lower() for prefix in dei_prefixes):
                    is_dei_fact = True
                
                if is_dei_fact:
                    # Extract the concept name without the prefix
                    concept = fact.element_id
                    if ':' in concept:
                        concept = concept.split(':', 1)[1]
                    elif '_' in concept:
                        parts = concept.split('_', 1)
                        if parts[0].lower() == 'dei':
                            concept = parts[1]
                    
                    # Store the fact by its concept name (case-insensitive)
                    dei_facts[concept.lower()] = fact
                    
                    # Also check if the fact matches any of our specific target names
                    for info_key, possible_names in dei_fact_names.items():
                        for name in possible_names:
                            if concept.lower() == name.lower():
                                dei_facts[info_key] = fact
            
            # Debug output
            log.debug(f"Found {len(dei_facts)} DEI facts")
            
            # Extract entity name
            if 'entity_name' in dei_facts:
                self.entity_info['entity_name'] = dei_facts['entity_name'].value
            elif 'entityregistrantname' in dei_facts:
                self.entity_info['entity_name'] = dei_facts['entityregistrantname'].value
            
            # Extract ticker
            if 'ticker' in dei_facts:
                self.entity_info['ticker'] = dei_facts['ticker'].value
            elif 'tradingsymbol' in dei_facts:
                self.entity_info['ticker'] = dei_facts['tradingsymbol'].value
            
            # Extract document type
            if 'document_type' in dei_facts:
                doc_type = dei_facts['document_type'].value
                self.entity_info['document_type'] = doc_type
            elif 'documenttype' in dei_facts:
                doc_type = dei_facts['documenttype'].value
                self.entity_info['document_type'] = doc_type
                
            # Set flags based on document type if available
            if self.entity_info['document_type']:
                doc_type = self.entity_info['document_type']
                if doc_type == '10-K':
                    self.entity_info['annual_report'] = True
                elif doc_type == '10-Q':
                    self.entity_info['quarterly_report'] = True
                
                # Check for amendment
                if '/A' in doc_type:
                    self.entity_info['amendment'] = True
            else:
                # Also check explicit annual/quarterly flags
                if 'annual_report' in dei_facts:
                    try:
                        # Handle boolean values in text form
                        annual_report_value = dei_facts['annual_report'].value.lower()
                        self.entity_info['annual_report'] = (annual_report_value == 'true' or annual_report_value == '1')
                    except (AttributeError, ValueError):
                        pass
                
                if 'quarterly_report' in dei_facts:
                    try:
                        quarterly_report_value = dei_facts['quarterly_report'].value.lower()
                        self.entity_info['quarterly_report'] = (quarterly_report_value == 'true' or quarterly_report_value == '1')
                    except (AttributeError, ValueError):
                        pass
            
            # Extract document period end date
            if 'document_period_end_date' in dei_facts:
                date_str = dei_facts['document_period_end_date'].value
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    self.entity_info['document_period_end_date'] = date_obj
                except (ValueError, TypeError):
                    pass
            elif 'documentperiodenddate' in dei_facts:
                date_str = dei_facts['documentperiodenddate'].value
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    self.entity_info['document_period_end_date'] = date_obj
                except (ValueError, TypeError):
                    pass
            
            # Extract fiscal year
            if 'fiscal_year' in dei_facts:
                try:
                    self.entity_info['fiscal_year'] = int(dei_facts['fiscal_year'].value)
                except (ValueError, TypeError):
                    pass
            elif 'fiscalyear' in dei_facts:
                try:
                    self.entity_info['fiscal_year'] = int(dei_facts['fiscalyear'].value)
                except (ValueError, TypeError):
                    pass
            
            # Extract fiscal period
            if 'fiscal_period' in dei_facts:
                self.entity_info['fiscal_period'] = dei_facts['fiscal_period'].value
            elif 'fiscalperiod' in dei_facts:
                self.entity_info['fiscal_period'] = dei_facts['fiscalperiod'].value
            
            # Extract fiscal year end date
            if 'fiscal_year_end' in dei_facts:
                fiscal_end = dei_facts['fiscal_year_end'].value
                try:
                    # Format is typically --MM-DD
                    if fiscal_end.startswith('--'):
                        fiscal_end = fiscal_end[2:]  # Remove --
                    if fiscal_end.count('-') == 1:
                        month_str, day_str = fiscal_end.split('-')
                        if month_str.isdigit() and day_str.isdigit():
                            self.entity_info['fiscal_year_end_month'] = int(month_str)
                            self.entity_info['fiscal_year_end_day'] = int(day_str)
                except (ValueError, TypeError, IndexError):
                    pass
            elif 'fiscalyearend' in dei_facts:
                fiscal_end = dei_facts['fiscalyearend'].value
                try:
                    # Format is typically --MM-DD
                    if fiscal_end.startswith('--'):
                        fiscal_end = fiscal_end[2:]  # Remove --
                    if fiscal_end.count('-') == 1:
                        month_str, day_str = fiscal_end.split('-')
                        if month_str.isdigit() and day_str.isdigit():
                            self.entity_info['fiscal_year_end_month'] = int(month_str)
                            self.entity_info['fiscal_year_end_day'] = int(day_str)
                except (ValueError, TypeError, IndexError):
                    pass
            
            # Extract reporting end date from context end dates
            for context in self.contexts.values():
                if 'period' in context.dict() and context.period.get('type') == 'instant':
                    date_str = context.period.get('instant')
                    if date_str:
                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                            # Update if this is later than current value
                            current_date = self.entity_info.get('reporting_end_date')
                            if current_date is None or date_obj > current_date:
                                self.entity_info['reporting_end_date'] = date_obj
                        except (ValueError, TypeError):
                            pass
            
            # Debug output
            log.debug(f"Entity info: {self.entity_info}")
            
        except Exception as e:
            # Log error but don't fail
            log.warning(f"Warning: Error extracting entity info: {str(e)}")
    
    def _build_reporting_periods(self) -> None:
        """Build reporting periods from contexts."""
        try:
            # Clear existing periods
            self.reporting_periods = []
            self.context_period_map = {}
            
            # Collect unique periods from contexts
            instant_periods = {}
            duration_periods = {}
            
            for context_id, context in self.contexts.items():
                if 'period' in context.dict() and 'type' in context.period:
                    period_type = context.period.get('type')
                    
                    if period_type == 'instant':
                        date_str = context.period.get('instant')
                        if date_str:
                            if date_str not in instant_periods:
                                instant_periods[date_str] = []
                            
                            # Add context ID to this period
                            instant_periods[date_str].append(context_id)
                            
                            # Map context to period key
                            period_key = f"instant_{date_str}"
                            self.context_period_map[context_id] = period_key
                    
                    elif period_type == 'duration':
                        start_date = context.period.get('startDate')
                        end_date = context.period.get('endDate')
                        if start_date and end_date:
                            duration_key = f"{start_date}_{end_date}"
                            if duration_key not in duration_periods:
                                duration_periods[duration_key] = []
                            
                            # Add context ID to this period
                            duration_periods[duration_key].append(context_id)
                            
                            # Map context to period key
                            period_key = f"duration_{start_date}_{end_date}"
                            self.context_period_map[context_id] = period_key
            
            # Process instant periods
            for date_str, context_ids in instant_periods.items():
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    formatted_date = date_obj.strftime('%B %d, %Y')
                    
                    period = {
                        'type': 'instant',
                        'date': date_str,
                        'date_obj': date_obj,
                        'label': formatted_date,
                        'context_ids': context_ids,
                        'key': f"instant_{date_str}"
                    }
                    self.reporting_periods.append(period)
                except (ValueError, TypeError):
                    # Skip invalid dates
                    continue
            
            # Process duration periods
            for period_key, context_ids in duration_periods.items():
                start_date, end_date = period_key.split('_')
                try:
                    start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                    formatted_start = start_obj.strftime('%B %d, %Y')
                    formatted_end = end_obj.strftime('%B %d, %Y')
                    
                    # Calculate duration in days
                    days = (end_obj - start_obj).days
                    
                    # Determine period type based on duration
                    period_description = classify_duration(days)
                    
                    period = {
                        'type': 'duration',
                        'start_date': start_date,
                        'end_date': end_date,
                        'start_obj': start_obj,
                        'end_obj': end_obj,
                        'days': days,
                        'period_type': period_description,
                        'label': f"{period_description}: {formatted_start} to {formatted_end}",
                        'context_ids': context_ids,
                        'key': f"duration_{start_date}_{end_date}"
                    }
                    self.reporting_periods.append(period)
                except (ValueError, TypeError):
                    # Skip invalid dates
                    continue
            
            # Sort periods by date (most recent first)
            self.reporting_periods.sort(key=lambda p: p['date_obj'] if p['type'] == 'instant' else p['end_obj'], reverse=True)
            
            # Debug printout to verify periods are extracted
            if len(self.reporting_periods) > 0:
                log.debug(f"Found {len(self.reporting_periods)} reporting periods.")
                log.debug(f"First period: {self.reporting_periods[0]['label']}")
            else:
                log.debug("Warning: No reporting periods found!")
                
            # Debug context period map
            log.debug(f"Context period map has {len(self.context_period_map)} entries.")
            
        except Exception as e:
            # Log error but don't fail
            log.debug(f"Warning: Error building reporting periods: {str(e)}")
            self.reporting_periods = []
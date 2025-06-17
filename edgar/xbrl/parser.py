"""
XBRL file parsing functionality.

This module provides functions for parsing XBRL files and extracting data.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from lxml import etree as ET

from edgar.core import log
from edgar.xbrl.core import NAMESPACES, STANDARD_LABEL, classify_duration, extract_element_id
from edgar.xbrl.models import (
    Axis,
    CalculationNode,
    CalculationTree,
    Context,
    Domain,
    ElementCatalog,
    Fact,
    PresentationNode,
    PresentationTree,
    Table,
    XBRLProcessingError,
)


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
        self.dei_facts: Dict[str, Fact] = {}
        
        # Reporting periods
        self.reporting_periods: List[Dict[str, Any]] = []
        
        # Mapping of context IDs to period identifiers for easy lookup
        self.context_period_map: Dict[str, str] = {}
        
    def _create_normalized_fact_key(self, element_id: str, context_ref: str, instance_id: Optional[int] = None) -> str:
        """
        Create a normalized fact key using underscore format.
        
        Args:
            element_id: The element ID
            context_ref: The context reference
            instance_id: Optional instance ID for duplicate facts
        
        Returns:
            Normalized key in format: element_id_context_ref[_instance_id]
        """
        normalized_element_id = element_id
        if ':' in element_id:
            prefix, name = element_id.split(':', 1)
            normalized_element_id = f"{prefix}_{name}"
        if instance_id is not None:
            return f"{normalized_element_id}_{context_ref}_{instance_id}"
        return f"{normalized_element_id}_{context_ref}"

    def get_facts_by_key(self, element_id: str, context_ref: str) -> List[Fact]:
        """Get all facts matching the given element ID and context reference.
        
        This method handles both single facts and duplicate facts using the hybrid storage approach.
        For single facts, it returns a list with one fact. For duplicates, it returns all instances.
        
        Args:
            element_id: The element ID to look up
            context_ref: The context reference
        
        Returns:
            List of matching facts
        """
        base_key = self._create_normalized_fact_key(element_id, context_ref)
        
        # First try direct lookup for single fact
        if base_key in self.facts:
            return [self.facts[base_key]]
        
        # Look for facts with instance IDs
        facts = []
        i = 0
        while True:
            key = self._create_normalized_fact_key(element_id, context_ref, i)
            if key not in self.facts:
                break
            facts.append(self.facts[key])
            i += 1
        
        return facts
    
    def get_fact(self, element_id: str, context_ref: str) -> Optional[Fact]:
        """
        Get a fact by element ID and context reference.
        Handles both colon and underscore formats transparently.
        If there are duplicate facts, returns the first instance.
        Use get_facts_by_key to get all instances.
        
        Args:
            element_id: Element ID (can use either colon or underscore format)
            context_ref: Context reference
            
        Returns:
            First matching fact if found, None otherwise
        """
        facts = self.get_facts_by_key(element_id, context_ref)
        return facts[0] if facts else None
    
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
            # Use the safe XML parsing helper
            root = self._safe_parse_xml(content)
            
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
            # Use the safe XML parsing helper
            root = self._safe_parse_xml(schema_content)
            
            # Create namespace map for use with XPath
            nsmap = {
                'xsd': 'http://www.w3.org/2001/XMLSchema',
                'link': 'http://www.xbrl.org/2003/linkbase'
            }

            # Find all appinfo elements using optimized XPath
            for appinfo in root.xpath('.//xsd:appinfo', namespaces=nsmap):
                # Extract role types
                for role_type in appinfo.xpath('./link:roleType', namespaces=nsmap):
                    role_uri = role_type.get('roleURI')
                    role_id = role_type.get('id')
                    
                    # Use optimized XPath to find definition
                    definition = role_type.find('./link:definition', nsmap)
                    definition_text = definition.text if definition is not None else ""
                    
                    # Use optimized XPath to find usedOn elements
                    used_on = [elem.text for elem in role_type.xpath('./link:usedOn', namespaces=nsmap) if elem.text]

                    if role_uri:
                        embedded_data['role_types'][role_uri] = {
                            'id': role_id,
                            'definition': definition_text,
                            'used_on': used_on
                        }

                # Find the linkbase element with optimized XPath
                linkbase = appinfo.find('./link:linkbase', nsmap)
                if linkbase is not None:
                    # Extract the entire linkbase element as a string - with proper encoding
                    linkbase_string = ET.tostring(linkbase, encoding='unicode', method='xml')

                    # Extract each type of linkbase with optimized XPath
                    for linkbase_type in ['presentation', 'label', 'calculation', 'definition']:
                        # Use direct child XPath for better performance
                        xpath_expr = f'./link:{linkbase_type}Link'
                        linkbase_elements = linkbase.xpath(xpath_expr, namespaces=nsmap)

                        if linkbase_elements:
                            # Convert all linkbase elements of this type to strings
                            linkbase_strings = [
                                ET.tostring(elem, encoding='unicode', method='xml') 
                                for elem in linkbase_elements
                            ]

                            # Join multiple linkbase elements efficiently
                            linkbase_header = linkbase_string.split('>', 1)[0] + '>'
                            embedded_data['linkbases'][linkbase_type] = (
                                f"{linkbase_header}\n" + 
                                '\n'.join(linkbase_strings) + 
                                "\n</link:linkbase>"
                            )
            
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
            # Optimize: Register namespaces for faster XPath lookups
            nsmap = {
                'link': 'http://www.xbrl.org/2003/linkbase',
                'xlink': 'http://www.w3.org/1999/xlink',
                'xml': 'http://www.w3.org/XML/1998/namespace'
            }
            
            # Optimize: Use lxml parser with smart string handling
            parser = ET.XMLParser(remove_blank_text=True, recover=True)
            root = ET.XML(content.encode('utf-8'), parser)
            
            # Optimize: Use specific XPath expressions with namespaces for faster lookups
            # This is much faster than using findall with '//' in element tree
            label_arcs = root.xpath('//link:labelArc', namespaces=nsmap)
            labels = root.xpath('//link:label', namespaces=nsmap)
            
            # Optimize: Pre-allocate dictionary with expected size
            label_lookup = {}
            
            # Optimize: Cache attribute lookups
            xlink_label = '{http://www.w3.org/1999/xlink}label'
            xlink_role = '{http://www.w3.org/1999/xlink}role'
            xml_lang = '{http://www.w3.org/XML/1998/namespace}lang'
            default_role = 'http://www.xbrl.org/2003/role/label'
            
            # Optimize: Process labels in a single pass with direct attribute access
            for label in labels:
                label_id = label.get(xlink_label)
                if not label_id:
                    continue
                
                # Get text first - if empty, skip further processing
                text = label.text
                if text is None:
                    continue
                
                # Get attributes - direct lookup is faster than method calls
                role = label.get(xlink_role, default_role)
                lang = label.get(xml_lang, 'en-US')
                
                # Create nested dictionaries only when needed
                if label_id not in label_lookup:
                    label_lookup[label_id] = {}
                
                if lang not in label_lookup[label_id]:
                    label_lookup[label_id][lang] = {}
                
                label_lookup[label_id][lang][role] = text
            
            # Optimize: Cache attribute lookups for arcs
            xlink_from = '{http://www.w3.org/1999/xlink}from'
            xlink_to = '{http://www.w3.org/1999/xlink}to'
            xlink_href = '{http://www.w3.org/1999/xlink}href'
            
            # Optimize: Create a lookup table for locators by label for faster access
            loc_by_label = {}
            for loc in root.xpath('//link:loc', namespaces=nsmap):
                loc_label = loc.get(xlink_label)
                if loc_label:
                    loc_by_label[loc_label] = loc.get(xlink_href)
            
            # Connect labels to elements using arcs - with optimized lookups
            for arc in label_arcs:
                from_ref = arc.get(xlink_from)
                to_ref = arc.get(xlink_to)
                
                if not from_ref or not to_ref or to_ref not in label_lookup:
                    continue
                
                # Use cached locator lookup instead of expensive XPath
                href = loc_by_label.get(from_ref)
                if not href:
                    continue
                
                # Extract element ID from href
                element_id = extract_element_id(href)
                
                # Find labels for this element - check most likely case first
                if 'en-US' in label_lookup[to_ref]:
                    element_labels = label_lookup[to_ref]['en-US']
                    
                    # Optimize: Update catalog with minimal overhead
                    catalog_entry = self.element_catalog.get(element_id)
                    if catalog_entry:
                        catalog_entry.labels.update(element_labels)
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
            # Optimize: Register namespaces for faster XPath lookups
            nsmap = {
                'link': 'http://www.xbrl.org/2003/linkbase',
                'xlink': 'http://www.w3.org/1999/xlink'
            }
            
            # Optimize: Use lxml parser with smart string handling
            parser = ET.XMLParser(remove_blank_text=True, recover=True)
            root = ET.XML(content.encode('utf-8'), parser)
            
            # Optimize: Use XPath with namespaces for faster extraction
            presentation_links = root.xpath('//link:presentationLink', namespaces=nsmap)
            
            # Optimize: Cache attribute paths
            xlink_role = '{http://www.w3.org/1999/xlink}role'
            xlink_from = '{http://www.w3.org/1999/xlink}from'
            xlink_to = '{http://www.w3.org/1999/xlink}to'
            xlink_label = '{http://www.w3.org/1999/xlink}label'
            xlink_href = '{http://www.w3.org/1999/xlink}href'
            
            for link in presentation_links:
                role = link.get(xlink_role)
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
                
                # Optimize: Pre-build locator map to avoid repeated XPath lookups
                loc_map = {}
                for loc in link.xpath('.//link:loc', namespaces=nsmap):
                    label = loc.get(xlink_label)
                    if label:
                        loc_map[label] = loc.get(xlink_href)
                
                # Optimize: Extract arcs using direct xpath with context
                arcs = link.xpath('.//link:presentationArc', namespaces=nsmap)
                
                # Create relationships map - pre-allocate with known size
                relationships = []
                relationships_append = relationships.append  # Local function reference for speed
                
                # Process arcs with optimized locator lookups
                for arc in arcs:
                    from_ref = arc.get(xlink_from)
                    to_ref = arc.get(xlink_to)
                    
                    if not from_ref or not to_ref:
                        continue
                    
                    # Optimize: Use cached locator references instead of expensive XPath lookups
                    from_href = loc_map.get(from_ref)
                    to_href = loc_map.get(to_ref)
                    
                    if not from_href or not to_href:
                        continue
                    
                    # Optimize order extraction with direct try/except
                    try:
                        order = float(arc.get('order', '1.0'))
                    except (ValueError, TypeError):
                        order = 1.0
                    
                    preferred_label = arc.get('preferredLabel')
                    
                    # Extract element IDs from hrefs
                    from_element = extract_element_id(from_href)
                    to_element = extract_element_id(to_href)
                    
                    # Add relationship using local function reference
                    relationships_append({
                        'from_element': from_element,
                        'to_element': to_element,
                        'order': order,
                        'preferred_label': preferred_label
                    })
                
                # Build presentation tree for this role if we have relationships
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
    
    def _safe_parse_xml(self, content: str) -> ET.Element:
        """
        Safely parse XML content with lxml, handling encoding declarations properly.
        
        Args:
            content: XML content as string or bytes
            
        Returns:
            parsed XML root element
        """
        parser = ET.XMLParser(remove_blank_text=True, recover=True)
        
        # Convert to bytes for safer parsing if needed
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content
            
        # Parse with lxml
        return ET.XML(content_bytes, parser)

    def parse_calculation_content(self, content: str) -> None:
        """Parse calculation linkbase content and build calculation trees."""
        try:
            # Use safe XML parsing method
            root = self._safe_parse_xml(content)
            
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
            root = self._safe_parse_xml(content)
            
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
            # Use lxml's optimized parser with smart string handling and recovery mode
            parser = ET.XMLParser(remove_blank_text=True, recover=True, huge_tree=True)
            
            # Convert to bytes for faster parsing if not already
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
            else:
                content_bytes = content
                
            # Parse content with optimized settings
            root = ET.XML(content_bytes, parser)
            
            # Extract data in optimal order (contexts first, then units, then facts)
            # This ensures dependencies are resolved before they're needed
            self._extract_contexts(root)
            self._extract_units(root)
            self._extract_facts(root)
            
            # Post-processing steps after all raw data is extracted
            self._extract_entity_info()
            self._build_reporting_periods()
        
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing instance content: {str(e)}")

    def count_facts(self, content:str) -> tuple:
        """Count the number of facts in the instance document
        This function counts both unique facts and total fact instances in the XBRL document.
        
        Returns:
            tuple: (unique_facts_count, total_fact_instances)
        """

        # Use lxml's optimized parser with smart string handling and recovery mode
        parser = ET.XMLParser(remove_blank_text=True, recover=True, huge_tree=True)

        # Convert to bytes for faster parsing if not already
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content

        # Parse content with optimized settings
        root = ET.XML(content_bytes, parser)
        
        # Fast path to identify non-fact elements to skip
        skip_tag_endings = {'}context', '}unit', '}schemaRef'}
        
        # Track both total instances and unique facts
        total_fact_instances = 0  # Total number of fact references in the document
        unique_facts = set()      # Set of unique element_id + context_ref combinations
        create_key = self._create_normalized_fact_key
        
        # Define counting function
        def count_element(element):
            """Process a single element as a potential fact."""
            nonlocal total_fact_instances
            
            # Skip known non-fact elements
            tag = element.tag
            for ending in skip_tag_endings:
                if tag.endswith(ending):
                    return
            
            # Get context reference - key check to identify facts
            context_ref = element.get('contextRef')
            if context_ref is None:
                return
                
            # Extract element namespace and name - optimized split
            if '}' in tag:
                namespace, element_name = tag.split('}', 1)
                namespace = namespace[1:]  # Faster than strip('{')
            else:
                element_name = tag
                namespace = None
            
            # Get namespace prefix - cached for performance
            prefix = None
            for std_prefix, std_uri_base in NAMESPACES.items():
                if namespace.startswith(std_uri_base):
                    prefix = std_prefix
                    break
                        
            if not prefix and namespace:
                # Try to extract prefix from the namespace
                parts = namespace.split('/')
                prefix = parts[-1] if parts else ''
                    
            # Construct element ID with optimized string concatenation
            if prefix:
                element_id = f"{prefix}:{element_name}" if prefix else element_name
            else:
                element_id = element_name
            
            # Create a normalized key using underscore format for consistency
            normalized_key = create_key(element_id, context_ref)
            
            # Track unique facts
            unique_facts.add(normalized_key)
                
            # Increment total instances count
            total_fact_instances += 1
        
        # Optimize traversal using lxml's iterchildren and iterdescendants if available
        if hasattr(root, 'iterchildren'):
            # Use lxml's optimized traversal methods
            for child in root.iterchildren():
                count_element(child)
                # Process nested elements with optimized iteration
                for descendant in child.iterdescendants():
                    count_element(descendant)
        else:
            # Fallback for ElementTree
            for child in root:
                count_element(child)
                for descendant in child.findall('.//*'):
                    count_element(descendant)
        
        # Return tuple of counts (unique_facts_count, total_fact_instances)
        return len(unique_facts), total_fact_instances

    
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
            # Get direct access to nsmap if using lxml (much faster than regex extraction)
            if hasattr(root, 'nsmap'):
                # Leverage lxml's native nsmap functionality
                prefix_map = {uri: prefix for prefix, uri in root.nsmap.items() if prefix is not None}
            else:
                # Fallback for ElementTree - precompile regex patterns for namespace extraction
                xmlns_pattern = '{http://www.w3.org/2000/xmlns/}'
                prefix_map = {}

                # Extract namespace declarations from root
                for attr_name, attr_value in root.attrib.items():
                    if attr_name.startswith(xmlns_pattern) or attr_name.startswith('xmlns:'):
                        # Extract the prefix more efficiently
                        if attr_name.startswith(xmlns_pattern):
                            prefix = attr_name[len(xmlns_pattern):]
                        else:
                            prefix = attr_name.split(':', 1)[1]
                        prefix_map[attr_value] = prefix

            # Initialize counters and tracking
            fact_count = 0
            facts_dict = {}
            base_keys = {}

            # Fast path to identify non-fact elements to skip - compile as set for O(1) lookup
            skip_tag_endings = {
                'schemaRef',
                'roleRef',
                'arcroleRef',
                'linkbaseRef',
                'context',
                'unit'
            }

            def process_element(element):
                """Process a single element as a potential fact."""
                nonlocal fact_count

                # Skip annotation nodes and other non element nodes
                if not ET.iselement(element):
                    # logger('Skipping non-element: %s', element)
                    return
                # Skip known non-fact elements - faster check with set membership
                # If the tag is not a string, try calling () to get the string value (in rare cases)
                if callable(element.tag):
                    if isinstance(element, ET._Comment):
                        # logger ('Skipping Comment: %s', element)
                        return
                    if not element.values():
                        # logger ('Skipping non-values: %s', element)
                        return
                tag = element.tag
                for ending in skip_tag_endings:
                    if tag.endswith(ending):
                        return

                # Get context reference - key check to identify facts
                context_ref = element.get('contextRef')
                if not context_ref:
                    return

                # Extract element namespace and name - optimized split
                if '}' in tag:
                    namespace, element_name = tag.split('}', 1)
                    namespace = namespace[1:]  # Faster than strip('{')

                    # Try to extract prefix from the namespace
                    prefix = prefix_map.get(namespace)
                    if not prefix:
                        parts = namespace.split('/')
                        prefix = parts[-1] if parts else ''
                else:
                    element_name = tag
                    prefix = ''

                # Construct element ID with optimized string concatenation
                element_id = f"{prefix}:{element_name}" if prefix else element_name

                # Get unit reference
                unit_ref = element.get('unitRef')

                # Get value - optimize string handling
                value = element.text
                if not value or not value.strip():
                    # Only check children if text is empty - use direct iteration for speed
                    for sub_elem in element:
                        sub_text = sub_elem.text
                        if sub_text and sub_text.strip():
                            value = sub_text
                            break

                # Optimize string handling - inline conditional
                value = value.strip() if value else ""

                # Get decimals attribute - direct access
                decimals = element.get('decimals')

                # Optimize numeric conversion with faster try/except
                numeric_value = None
                if value:
                    try:
                        numeric_value = float(value)
                    except (ValueError, TypeError):
                        pass

                # Create base key for duplicate detection
                base_key = self._create_normalized_fact_key(element_id, context_ref)
                
                # Handle duplicates
                instance_id = None
                if base_key in base_keys:
                    # This is a duplicate - convert existing fact to use instance_id if needed
                    if base_key in facts_dict:
                        existing_fact = facts_dict[base_key]
                        # Move existing fact to new key with instance_id=0
                        del facts_dict[base_key]
                        existing_fact.instance_id = 0
                        facts_dict[self._create_normalized_fact_key(element_id, context_ref, 0)] = existing_fact
                    # Add new fact with next instance_id
                    instance_id = len(base_keys[base_key])
                    base_keys[base_key].append(True)
                else:
                    # First instance of this fact
                    base_keys[base_key] = [True]

                # Create fact object
                fact = Fact(
                    element_id=element_id,
                    context_ref=context_ref,
                    value=value,
                    unit_ref=unit_ref,
                    decimals=decimals,
                    numeric_value=numeric_value,
                    instance_id=instance_id
                )
                
                # Store fact with appropriate key
                key = self._create_normalized_fact_key(element_id, context_ref, instance_id)
                facts_dict[key] = fact
                fact_count += 1

            # Use lxml's optimized traversal methods
            if hasattr(root, 'iterchildren'):
                # Use lxml's optimized traversal methods
                for child in root.iterchildren():
                    process_element(child)
                    # Process nested elements with optimized iteration
                    for descendant in child.iterdescendants():
                        process_element(descendant)
            else:
                # Fallback for ElementTree
                for child in root:
                    process_element(child)
                    for descendant in child.findall('.//*'):
                        process_element(descendant)

            # Update instance facts
            self.facts = facts_dict

            log.debug(f"Extracted {fact_count} facts ({len(base_keys)} unique fact identifiers)")

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
            # Extract CIK/identifier from first context
            identifier = None
            if self.contexts:
                first = next(iter(self.contexts.values()))
                ident = first.entity.get('identifier')
                if ident and ident.isdigit():
                    identifier = ident.lstrip('0')

            # Collect all DEI facts into a dict: concept -> Fact
            self.dei_facts: Dict[str, Fact] = {}
            for fact in self.facts.values():
                eid = fact.element_id
                if eid.startswith('dei:'):
                    concept = eid.split(':', 1)[1]
                elif eid.startswith('dei_'):
                    concept = eid.split('_', 1)[1]
                else:
                    continue
                self.dei_facts[concept] = fact

            # Helper: get the first available DEI fact value
            def get_dei(*names):
                for n in names:
                    f = self.dei_facts.get(n)
                    if f:
                        return f.value
                return None

            # Build entity_info preserving existing keys
            self.entity_info = {
                'entity_name':             get_dei('EntityRegistrantName'),
                'ticker':                  get_dei('TradingSymbol'),
                'identifier':              identifier,
                'document_type':           get_dei('DocumentType'),
                'reporting_end_date':      None,
                'document_period_end_date':get_dei('DocumentPeriodEndDate'),
                'fiscal_year':             get_dei('DocumentFiscalYearFocus','FiscalYearFocus','FiscalYear'),
                'fiscal_period':           get_dei('DocumentFiscalPeriodFocus','FiscalPeriodFocus'),
                'fiscal_year_end_month':   None,
                'fiscal_year_end_day':     None,
                'annual_report':           False,
                'quarterly_report':        False,
                'amendment':               False,
            }

            # Determine reporting_end_date from contexts
            for ctx in self.contexts.values():
                period = getattr(ctx, 'period', {})
                if period.get('type') == 'instant':
                    ds = period.get('instant')
                    if ds:
                        try:
                            dt_obj = datetime.strptime(ds, '%Y-%m-%d').date()
                            curr = self.entity_info['reporting_end_date']
                            if curr is None or dt_obj > curr:
                                self.entity_info['reporting_end_date'] = dt_obj
                        except Exception:
                            pass

            # Parse fiscal year end date into month/day
            fye = get_dei('CurrentFiscalYearEndDate','FiscalYearEnd')
            if fye:
                try:
                    s = fye
                    if s.startswith('--'):
                        s = s[2:]
                    if '-' in s:
                        m, d = s.split('-', 1)
                        if m.isdigit() and d.isdigit():
                            self.entity_info['fiscal_year_end_month'] = int(m)
                            self.entity_info['fiscal_year_end_day'] = int(d)
                except Exception:
                    pass

            # Flags based on document_type
            dt_val = self.entity_info['document_type'] or ''
            self.entity_info['annual_report']    = (dt_val == '10-K')
            self.entity_info['quarterly_report'] = (dt_val == '10-Q')
            self.entity_info['amendment']        = ('/A' in dt_val)

            log.debug(f"Entity info: {self.entity_info}")
        except Exception as e:
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
                if 'period' in context.model_dump() and 'type' in context.period:
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
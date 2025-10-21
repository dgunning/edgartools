"""
Presentation parser for XBRL documents.

This module handles parsing of XBRL presentation linkbases and building
presentation trees for financial statement structure.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from lxml import etree as ET

from edgar.xbrl.core import extract_element_id
from edgar.xbrl.models import ElementCatalog, PresentationNode, PresentationTree, XBRLProcessingError

from .base import BaseParser


class PresentationParser(BaseParser):
    """Parser for XBRL presentation linkbases."""

    def __init__(self, presentation_roles: Dict[str, Dict[str, Any]],
                 presentation_trees: Dict[str, PresentationTree],
                 element_catalog: Dict[str, ElementCatalog]):
        """
        Initialize presentation parser with data structure references.

        Args:
            presentation_roles: Reference to presentation roles dictionary
            presentation_trees: Reference to presentation trees dictionary
            element_catalog: Reference to element catalog dictionary
        """
        super().__init__()

        # Store references to data structures
        self.presentation_roles = presentation_roles
        self.presentation_trees = presentation_trees
        self.element_catalog = element_catalog

    def parse_presentation(self, file_path: Union[str, Path]) -> None:
        """Parse presentation linkbase file and build presentation trees."""
        try:
            content = Path(file_path).read_text()
            self.parse_presentation_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing presentation file {file_path}: {str(e)}") from e

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

                    # Parse order attribute correctly
                    order = self._parse_order_attribute(arc)

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
            raise XBRLProcessingError(f"Error parsing presentation content: {str(e)}") from e

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

            # Use enhanced abstract detection (Issue #450 fix)
            # The element catalog may not have correct abstract info for standard taxonomy concepts
            from edgar.xbrl.abstract_detection import is_abstract_concept
            node.is_abstract = is_abstract_concept(
                concept_name=elem_info.name,
                schema_abstract=elem_info.abstract,
                has_children=False,  # Will be updated after children are processed
                has_values=False     # Will be determined later when facts are loaded
            )

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

                # Update preferred label and order after child is built
                if child_id in all_nodes:
                    if preferred_label:
                        all_nodes[child_id].preferred_label = preferred_label
                    all_nodes[child_id].order = rel['order']

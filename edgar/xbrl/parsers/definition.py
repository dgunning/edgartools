"""
Definition parser for XBRL documents.

This module handles parsing of XBRL definition linkbases and building
dimensional structures like tables, axes, and domains.
"""

from pathlib import Path
from typing import Any, Dict, List, Union

from edgar.xbrl.core import NAMESPACES, STANDARD_LABEL, extract_element_id
from edgar.xbrl.models import Axis, Domain, ElementCatalog, Table, XBRLProcessingError

from .base import BaseParser


class DefinitionParser(BaseParser):
    """Parser for XBRL definition linkbases."""

    def __init__(self, definition_roles: Dict[str, Dict[str, Any]],
                 tables: Dict[str, List[Table]],
                 axes: Dict[str, Axis],
                 domains: Dict[str, Domain],
                 element_catalog: Dict[str, ElementCatalog]):
        """
        Initialize definition parser with data structure references.

        Args:
            definition_roles: Reference to definition roles dictionary
            tables: Reference to tables dictionary
            axes: Reference to axes dictionary
            domains: Reference to domains dictionary
            element_catalog: Reference to element catalog dictionary
        """
        super().__init__()

        # Store references to data structures
        self.definition_roles = definition_roles
        self.tables = tables
        self.axes = axes
        self.domains = domains
        self.element_catalog = element_catalog

    def parse_definition(self, file_path: Union[str, Path]) -> None:
        """Parse definition linkbase file and build dimensional structures."""
        try:
            content = Path(file_path).read_text()
            self.parse_definition_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing definition file {file_path}: {str(e)}") from e

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
                    order = self._parse_order_attribute(arc)

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
            raise XBRLProcessingError(f"Error parsing definition content: {str(e)}") from e

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

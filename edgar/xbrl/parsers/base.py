"""
Base parser functionality for XBRL parsing components.

This module provides common utilities and base functionality shared across
all XBRL parser components.
"""

from typing import Any, Dict

from lxml import etree as ET

from edgar.core import log
from edgar.xbrl.core import NAMESPACES


class BaseParser:
    """Base class for XBRL parser components with common functionality."""

    def __init__(self):
        """Initialize base parser with common data structures."""
        # Common namespaces and utilities available to all parsers
        self.namespaces = NAMESPACES

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

    def _parse_order_attribute(self, arc) -> float:
        """Parse order attribute from arc, checking both order and xlink:order."""
        # Try xlink:order first (XBRL standard)
        order_value = arc.get('{http://www.w3.org/1999/xlink}order')
        if order_value is None:
            # Fallback to order attribute
            order_value = arc.get('order')

        # Debug logging to understand what's in the XBRL document
        if order_value is not None:
            log.debug(f"Found order attribute: {order_value}")
        else:
            # Log all attributes to see what's actually there
            all_attrs = dict(arc.attrib) if hasattr(arc, 'attrib') else {}
            log.debug(f"No order attribute found. Available attributes: {all_attrs}")

        try:
            return float(order_value) if order_value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _extract_role_info(self, role_element) -> Dict[str, Any]:
        """
        Extract role information from a role element.

        Args:
            role_element: XML element containing role definition

        Returns:
            Dictionary with role information
        """
        role_info = {}

        # Get role URI
        role_uri = role_element.get('roleURI', '')
        role_info['uri'] = role_uri

        # Extract role definition/label
        definition_elem = role_element.find('.//{http://www.xbrl.org/2003/linkbase}definition')
        if definition_elem is not None:
            role_info['definition'] = definition_elem.text or ''
        else:
            # Fallback: create definition from role URI
            role_info['definition'] = role_uri.split('/')[-1].replace('_', ' ') if role_uri else ''

        return role_info

    def _get_element_namespace_and_name(self, element_id: str) -> tuple[str, str]:
        """
        Extract namespace and local name from an element ID.

        Args:
            element_id: Element identifier (may include namespace prefix)

        Returns:
            Tuple of (namespace, local_name)
        """
        if ':' in element_id:
            prefix, local_name = element_id.split(':', 1)
            # Map common prefixes to namespaces
            namespace_map = {
                'us-gaap': 'http://fasb.org/us-gaap/2024',
                'dei': 'http://xbrl.sec.gov/dei/2024',
                'invest': 'http://xbrl.sec.gov/invest/2013-01-31',
                'country': 'http://xbrl.sec.gov/country/2023',
                'currency': 'http://xbrl.sec.gov/currency/2023',
                'exch': 'http://xbrl.sec.gov/exch/2023',
                'naics': 'http://xbrl.sec.gov/naics/2023',
                'sic': 'http://xbrl.sec.gov/sic/2023',
                'stpr': 'http://xbrl.sec.gov/stpr/2023',
            }
            namespace = namespace_map.get(prefix, f'http://unknown.namespace/{prefix}')
            return namespace, local_name
        else:
            return '', element_id

    def _normalize_element_id(self, element_id: str) -> str:
        """
        Normalize element ID to a consistent format.

        Args:
            element_id: Original element identifier

        Returns:
            Normalized element identifier
        """
        if ':' in element_id:
            prefix, name = element_id.split(':', 1)
            return f"{prefix}_{name}"
        return element_id

    def _log_parsing_progress(self, component: str, count: int, total: int = None):
        """
        Log parsing progress for debugging.

        Args:
            component: Name of component being parsed
            count: Number of items processed
            total: Total number of items (optional)
        """
        if total:
            log.debug(f"Parsed {count}/{total} {component}")
        else:
            log.debug(f"Parsed {count} {component}")

"""
Schema parser for XBRL documents.

This module handles parsing of XBRL taxonomy schemas and element catalog
creation with element definitions and properties.
"""

from pathlib import Path
from typing import Dict, Union

from lxml import etree as ET

from edgar.core import log
from edgar.xbrl.models import ElementCatalog, XBRLProcessingError

from .base import BaseParser


class SchemaParser(BaseParser):
    """Parser for XBRL taxonomy schemas."""

    def __init__(self, element_catalog: Dict[str, ElementCatalog]):
        """
        Initialize schema parser with data structure references.

        Args:
            element_catalog: Reference to element catalog dictionary
        """
        super().__init__()

        # Store references to data structures
        self.element_catalog = element_catalog

        # Will be set by coordinator when needed
        self.parse_labels_content = None
        self.parse_presentation_content = None
        self.parse_calculation_content = None
        self.parse_definition_content = None

    def set_linkbase_parsers(self, labels_parser, presentation_parser, calculation_parser, definition_parser):
        """
        Set references to other parsers for embedded linkbase processing.

        Args:
            labels_parser: LabelsParser instance
            presentation_parser: PresentationParser instance
            calculation_parser: CalculationParser instance
            definition_parser: DefinitionParser instance
        """
        self.parse_labels_content = labels_parser.parse_labels_content
        self.parse_presentation_content = presentation_parser.parse_presentation_content
        self.parse_calculation_content = calculation_parser.parse_calculation_content
        self.parse_definition_content = definition_parser.parse_definition_content

    def parse_schema(self, file_path: Union[str, Path]) -> None:
        """Parse schema file and extract element information."""
        try:
            content = Path(file_path).read_text()
            self.parse_schema_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing schema file {file_path}: {str(e)}") from e

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
                data_type = element.get('type', '')

                # Check for balance and period type
                # First check as attributes on the element (modern XBRL style)
                balance_type = element.get('{http://www.xbrl.org/2003/instance}balance')
                period_type = element.get('{http://www.xbrl.org/2003/instance}periodType')
                abstract = element.get('abstract', 'false').lower() == 'true'

                # If not found as attributes, look in nested annotations (legacy style)
                if not balance_type or not period_type:
                    annotation = element.find('.//{http://www.w3.org/2001/XMLSchema}annotation')
                    if annotation is not None:
                        for appinfo in annotation.findall('.//{http://www.w3.org/2001/XMLSchema}appinfo'):
                            if not balance_type:
                                balance_element = appinfo.find('.//{http://www.xbrl.org/2003/instance}balance')
                                if balance_element is not None:
                                    balance_type = balance_element.text

                            if not period_type:
                                period_element = appinfo.find('.//{http://www.xbrl.org/2003/instance}periodType')
                                if period_element is not None:
                                    period_type = period_element.text

                # Create element catalog entry
                self.element_catalog[element_id] = ElementCatalog(
                    name=element_id,
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
                if 'label' in embedded_linkbases['linkbases'] and self.parse_labels_content:
                    label_content = embedded_linkbases['linkbases']['label']
                    self.parse_labels_content(label_content)

                if 'presentation' in embedded_linkbases['linkbases'] and self.parse_presentation_content:
                    presentation_content = embedded_linkbases['linkbases']['presentation']
                    self.parse_presentation_content(presentation_content)

                if 'calculation' in embedded_linkbases['linkbases'] and self.parse_calculation_content:
                    calculation_content = embedded_linkbases['linkbases']['calculation']
                    self.parse_calculation_content(calculation_content)

                if 'definition' in embedded_linkbases['linkbases'] and self.parse_definition_content:
                    definition_content = embedded_linkbases['linkbases']['definition']
                    self.parse_definition_content(definition_content)

        except Exception as e:
            raise XBRLProcessingError(f"Error parsing schema content: {str(e)}") from e

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

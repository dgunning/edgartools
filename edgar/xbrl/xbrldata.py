from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edgar import Filing

import asyncio
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from functools import cached_property
from typing import Dict, List, Tuple, Union, Any, Optional, Set

import pandas as pd
from pydantic import BaseModel
from rich import box
from rich import print as rprint
from rich.console import Group
from rich.panel import Panel
from rich.table import Table, Column
from rich.text import Text
from rich.tree import Tree

from edgar.datatools import na_value
from edgar.richtools import repr_rich, colorize_words
from edgar.attachments import Attachments, Attachment
from edgar.core import log, split_camel_case, run_async_or_sync
from edgar.httprequests import download_file_async
from edgar.xbrl.calculations import CalculationLinkbase
from edgar.xbrl.concepts import Concept, concept_to_label
from edgar.xbrl.definitions import parse_definition_linkbase
from edgar.xbrl.instance import XBRLInstance
from edgar.xbrl.labels import parse_label_linkbase
from edgar.xbrl.statements import BalanceSheet, IncomeStatement, CashFlowStatement, StatementOfChangesInEquity,StatementOfComprehensiveIncome, StandardStatement
from edgar.xbrl.presentation import (XBRLPresentation, PresentationElement, get_root_element, get_axes_for_role,
    get_members_for_axis)
from pathlib import Path


__all__ = ['XBRLAttachments', 'XBRLInstance', 'LineItem', 'StatementDefinition', 'XBRLData',
           'Statements', 'Statement']

"""
This implementation includes:

Context and Fact classes to represent XBRL contexts and facts.
XBRLInstance class to parse the instance document, extracting contexts and facts.
StatementDefinition class to represent a single financial statement, organizing facts according to the presentation linkbase.
XBRL class to bring everything together, parsing the instance document and creating financial statements based on the presentation, label, and calculation linkbases.

The main() function demonstrates how to use the parser to access a specific financial statement (in this case, the Balance Sheet) and print its contents.
This implementation allows for:

Parsing of the XBRL instance document
Organization of facts into financial statements based on the presentation linkbase
Proper labeling of concepts using the label linkbase
Multi-period comparison (the get_fact_values method collects values for all available periods)
Hierarchical structure of financial statements (using the level from the presentation linkbase)

To use this code, you would need to integrate it with the previously created parsers for the presentation, label, and calculation linkbases. The XBRL class assumes these have already been parsed and are provided as dictionaries.
"""


class XBRLAttachments:
    """
    An adapter for the Attachments class that provides easy access to the XBRL documents.
    """

    def __init__(self, attachments: Attachments):
        self._documents = dict()
        if attachments.data_files:
            for attachment in attachments.data_files:
                if attachment.document_type in ["XML", 'EX-101.INS'] and attachment.extension.endswith(('.xml', '.XML')):
                    content = attachment.content
                    if '<xbrl' in content[:2000]:
                        self._documents['instance'] = attachment
                elif attachment.document_type == 'EX-101.SCH':
                    self._documents['schema'] = attachment
                elif attachment.document_type == 'EX-101.DEF':
                    self._documents['definition'] = attachment
                elif attachment.document_type == 'EX-101.CAL':
                    self._documents['calculation'] = attachment
                elif attachment.document_type == 'EX-101.LAB':
                    self._documents['label'] = attachment
                elif attachment.document_type == 'EX-101.PRE':
                    self._documents['presentation'] = attachment

    @property
    def empty(self):
        return not self._documents

    @property
    def has_instance_document(self):
        return 'instance' in self._documents

    @property
    def instance_only(self):
        return len(self._documents) == 1 and 'instance' in self._documents

    def get_xbrl(self) -> Optional[Union[XBRLInstance, 'XBRLData']]:
        if self.empty:
            return None
        elif self.instance_only:
            return XBRLInstance.parse(self._documents['instance'].download())
        else:
            parsed_documents = asyncio.run(self.load())
            if parsed_documents:
                instance_xml, presentation_xml, labels, calculations = parsed_documents
                return XBRLData.parse(instance_xml=instance_xml, presentation_xml=presentation_xml, labels=labels,
                                      calculations=calculations)

    def get_xbrl_instance(self):
        if self.has_instance_document:
            return XBRLInstance.parse(self._documents['instance'].download())

    def has_all_documents(self):
        return all(doc in self._documents for doc in
                   ['instance', 'schema', 'definition', 'label', 'calculation', 'presentation'])

    async def load(self) -> Tuple[str, str, Dict, CalculationLinkbase]:
        """
        Load the XBRL documents asynchronously and parse them.
        """

        parsers = {
                'definition': parse_definition_linkbase,
                'label': parse_label_linkbase,
                'calculation': CalculationLinkbase.parse,
                'presentation': lambda x: x,
                'instance': lambda x: x,
                'schema': lambda x: x
            }
        parsed_files = {}

        # Download all files concurrently
        load_tasks = []
        for doc_type in ['instance', 'schema', 'label', 'calculation', 'presentation']:
            attachment = self.get(doc_type)
            if attachment:
                load_tasks.append(XBRLAttachments.parse_content(doc_type, parsers[doc_type], attachment))

        # Wait for all downloads to complete
        results = await asyncio.gather(*load_tasks)
        for result in results:
            parsed_files.update(result)

        # If we don't have all documents, extract from schema
        if not self.has_all_documents() and 'schema' in parsed_files:
            embedded_linkbases = XBRLAttachments.extract_embedded_linkbases(parsed_files['schema'])

            for linkbase_type, content in embedded_linkbases['linkbases'].items():
                if linkbase_type not in parsed_files:
                    parsed_files[linkbase_type] = parsers[linkbase_type](content)

        # Return the required files
        return (parsed_files.get('instance', ''),
                parsed_files.get('presentation', ''),
                parsed_files.get('label', {}),
                parsed_files.get('calculation'))

    def load_content(self):
        """
        Load the XBRL documents and parse them.
        """
        if self.empty:
            return None
        elif self.instance_only:
            return XBRLInstance.parse(self._documents['instance'].download())
        else:
            instance_xml, presentation_xml, labels, calculations = asyncio.run(self.load())
            return XBRLData.parse(instance_xml=instance_xml, presentation_xml=presentation_xml, labels=labels,
                                  calculations=calculations)

    @staticmethod
    async def parse_content(doc_type: str, parser, attachment:Attachment):
        """
        Parse the content of an attachment asynchronously.
        doc_type: str: The type of document being parsed.
        parser: Callable: The parser function to use.
        attachment: Attachment: The attachment to parse.
        """
        return {doc_type: parser(attachment.content)}

    @staticmethod
    async def download_and_parse(client, doc_type: str, parser, url: str):
        """
        Download and parse a document asynchronously.
        doc_type: str: The type of document being parsed.
        parser: Callable: The parser function to use.
        url: str: The URL of the document to download.
        """
        content = await download_file_async(client, url)
        return {doc_type: parser(content)}

    @staticmethod
    def extract_embedded_linkbases(schema_content: str) -> Dict[str, Dict[str, str]]:
        """
        Extract embedded linkbases and role types from the schema file using ElementTree.
        """
        embedded_data = {
            'linkbases': {},
            'role_types': {}
        }

        # Register namespaces
        namespaces = {
            'xsd': 'http://www.w3.org/2001/XMLSchema',
            'link': 'http://www.xbrl.org/2003/linkbase',
            'xlink': 'http://www.w3.org/1999/xlink'
        }

        for prefix, uri in namespaces.items():
            ET.register_namespace(prefix, uri)

        # Parse the schema content
        root = ET.fromstring(schema_content)

        # Find all appinfo elements
        for appinfo in root.findall('.//xsd:appinfo', namespaces):
            # Extract role types
            for role_type in appinfo.findall('link:roleType', namespaces):
                role_uri = role_type.get('roleURI')
                role_id = role_type.get('id')
                definition = role_type.find('link:definition', namespaces)
                definition_text = definition.text if definition is not None else ""
                used_on = [elem.text for elem in role_type.findall('link:usedOn', namespaces)]

                embedded_data['role_types'][role_uri] = {
                    'id': role_id,
                    'definition': definition_text,
                    'used_on': used_on
                }

            # Find the linkbase element
            linkbase = appinfo.find('link:linkbase', namespaces)
            if linkbase is not None:
                # Extract the entire linkbase element as a string
                linkbase_string = ET.tostring(linkbase, encoding='unicode', method='xml')

                # Extract each type of linkbase
                for linkbase_type in ['presentation', 'label', 'calculation', 'definition']:
                    linkbase_elements = linkbase.findall(f'link:{linkbase_type}Link', namespaces)

                    if linkbase_elements:
                        # Convert all linkbase elements of this type to strings
                        linkbase_strings = [ET.tostring(elem, encoding='unicode', method='xml') for elem in
                                            linkbase_elements]

                        # Join multiple linkbase elements if there are more than one, and wrap them in the linkbase tags
                        embedded_data['linkbases'][linkbase_type] = f"{linkbase_string.split('>', 1)[0]}>\n" + \
                                                                    '\n'.join(linkbase_strings) + \
                                                                    "\n</link:linkbase>"
                    else:
                        print(f"Warning: {linkbase_type} linkbase not found in embedded linkbases")

        return embedded_data

    def get(self, doc_type: str):
        return self._documents.get(doc_type)

    def __rich__(self):
        table = Table(Column("Type"),
                      Column("Document"),
                      title="XBRL Documents",
                      box=box.SIMPLE)
        for doc_type, attachment in self._documents.items():
            table.add_row(doc_type, attachment.description)
        return table

    def __repr__(self):
        return repr_rich(self)


class LineItem(BaseModel):
    concept: str
    axis: Optional[str] = None
    segment: Optional[str] = None
    label: str
    values: Dict[str, Any]
    level: int
    preferred_label: Optional[str] = None
    is_abstract: bool = False
    section_type: Optional[str] = None  # 'main', 'subsection', 'total', 'detail'
    parent_section: Optional[str] = None  # e.g., 'Operating activities', 'Investing activities'

    @property
    def is_total(self) -> bool:
        return (
                self.preferred_label and
                ('totalLabel' in self.preferred_label or 'periodEndLabel' in self.preferred_label)
        )

    @property
    def is_main_section(self) -> bool:
        return (
                self.is_abstract and
                any(section in self.label.lower() for section in
                    ['operating activities', 'investing activities', 'financing activities'])
        )

    @property
    def is_subsection(self) -> bool:
        return (
                self.is_abstract and
                not self.is_main_section and
                self.label.endswith('Abstract')
        )

    @property
    def should_negate(self) -> bool:
        return (
                self.preferred_label and
                ('negatedLabel' in self.preferred_label or 'negatedTerseLabel' in self.preferred_label)
        )

    @property
    def has_dimensions(self) -> bool:
        """Check if this line item has dimensional values"""
        return any(
            any(dim_key != () for dim_key in period_values.keys())
            for period_values in self.values.values()
        )

    @property
    def base_values(self) -> Dict[str, Dict[str, Any]]:
        """Get only the base (non-dimensional) values"""
        return {
            period: period_values.get((), {})
            for period, period_values in self.values.items()
            if () in period_values
        }

    @property
    def dimensional_values(self) -> Dict[str, Dict[Tuple, Dict[str, Any]]]:
        """Get only the dimensional values"""
        return {
            period: {k: v for k, v in period_values.items() if k != ()}
            for period, period_values in self.values.items()
            if any(k != () for k in period_values.keys())
        }


class StatementDefinition():

    def __init__(self,
                 role: str,
                 label: str,
                 presentation_element: Optional[PresentationElement] = None):
        self.role: str = role
        self.name: str = role.split('/')[-1]
        self.label: str = label
        self._presentation_element: Optional[PresentationElement] = presentation_element
        self._line_items: List[LineItem] = []
        self._durations: Set[str] = set()
        self._xbrl_data: Optional['XBRLData'] = None
        self._built: bool = False

    @property
    def line_items(self) -> List[LineItem]:
        """
        Get the list of line items, building them if necessary.

        Returns:
            List[LineItem]: The list of line items in the statement
        """
        if not self._built and self._xbrl_data is not None:
            self._build_line_items()
        return self._line_items

    @property
    def durations(self) -> Set[str]:
        """
        Get the set of durations, building line items if necessary.

        Returns:
            Set[str]: The set of unique durations in the statement
        """
        if not self._built and self._xbrl_data is not None:
            self._build_line_items()
        return self._durations

    @property
    def empty(self) -> bool:
        return len(self.line_items) == 0

    def __hash__(self):
        return hash(self.role)

    def __eq__(self, other):
        if not isinstance(other, StatementDefinition):
            return False
        return self.role == other.role

    @staticmethod
    def _get_label_from_presentation_element(presentation_element: PresentationElement, labels: Dict) -> str:
        label = None
        if len(presentation_element.children) > 0:
            child = presentation_element.children[0]
            if child.node_type == 'Abstract':
                label = labels.get(child.concept, {}).get('label')
                if label:
                    return label.replace(' [Abstract]', '')

        if not label:
            return presentation_element.label.split('/')[-1]

    @classmethod
    def create(cls,
               role: str,
               presentation_element: PresentationElement,
               labels: Dict,
               xbrl_data: 'XBRLData') -> 'StatementDefinition':

        if not role or not presentation_element or not xbrl_data:
            raise ValueError("All parameters are required")

        # Factory method to create a StatementDefinition instance
        label: str = cls._get_label_from_presentation_element(presentation_element, labels)

        # Create the StatementDefinition
        statement_definition = cls(role=role, label=label, presentation_element=presentation_element)
        statement_definition._xbrl_data = xbrl_data

        return statement_definition

    @staticmethod
    def _find_line_items_container(element: PresentationElement) -> Optional[PresentationElement]:
        """Find the container for line items, handling both regular and dimensional structures"""

        # Case 1: Direct LineItems container
        if element.node_type == 'LineItems':
            return element

        # Case 2: Table structure with dimensions
        if element.node_type == 'Table':
            # Find the LineItems element within the table
            for child in element.children:
                if child.node_type == 'LineItems':
                    return child

            # If no explicit LineItems, look for the axis and domain
            for child in element.children:
                if child.node_type == 'Axis':
                    domain = next((c for c in child.children if c.node_type == 'Domain'), None)
                    if domain:
                        # Return domain to process its members
                        return domain

        # Case 3: Statement abstract without Table
        if (element.node_type == 'Abstract' and
                element.concept.endswith('Abstract') and
                not any(child.node_type == 'Table' for child in element.children)):
            return element

        # Recursive search
        for child in element.children:
            result = StatementDefinition._find_line_items_container(child)
            if result:
                return result

        return None

    def _build_line_items(self):
        """Internal method to build line items"""
        if self._built:
            return

        if self._xbrl_data is None:
            raise ValueError("XBRLData reference not set")
        if self._presentation_element is None:
            raise ValueError("Presentation element not set")

        self.build_line_items(
            self._presentation_element,
            self._xbrl_data.labels,
            self._xbrl_data.calculations,
            self._xbrl_data.instance
        )
        self._built = True

    def build_line_items(self, presentation_element: PresentationElement,
                         labels: Dict,
                         calculations: CalculationLinkbase,
                         instance: XBRLInstance):
        """Build line items handling both dimensional and non-dimensional structures"""

        current_main_section = None
        current_subsection = None

        def process_element(element: PresentationElement,
                            level: int,
                            parent_element: Optional[PresentationElement] = None,
                            axes: List[PresentationElement] = None) -> List[LineItem]:
            items = []
            concept = element.href.split('#')[-1]
            label = self.get_label(concept, labels, element.preferred_label)
            nonlocal current_main_section, current_subsection

            # Always create the base line item first
            concept_key = concept.replace('_', ':', 1)
            values, durations = self.get_fact_values(concept_key, instance, calculations)

            self._durations.update(durations)

            # Create base line item
            line_item = LineItem(
                concept=concept,
                label=label,
                values=values,
                level=level,
                preferred_label=element.preferred_label,
                is_abstract=element.node_type in ['Abstract', 'Header']
            )

            # Track sections
            if line_item.is_main_section:
                current_main_section = line_item
                current_subsection = None
                line_item.section_type = 'main'
            elif line_item.is_subsection:
                current_subsection = line_item
                line_item.section_type = 'subsection'
                line_item.parent_section = current_main_section.label if current_main_section else None
            elif line_item.is_total:
                line_item.section_type = 'total'
                line_item.parent_section = current_main_section.label if current_main_section else None
            else:
                line_item.section_type = 'detail'
                line_item.parent_section = current_main_section.label if current_main_section else None

            # Adjust level based on section hierarchy
            if current_subsection and not line_item.is_main_section:
                line_item.level += 1

            if values:
                items.append(line_item)

            # If we have axes, add dimensional items
            if axes:
                for axis in axes:
                    axis_concept = axis.href.split('#')[-1]
                    members = get_members_for_axis(axis)

                    for member in members:
                        member_concept = member.href.split('#')[-1]
                        dimension = {axis_concept.replace('_', ':', 1): member_concept.replace('_', ':', 1)}

                        # Get the fact values for this concept with dimension
                        concept_key = concept.replace('_', ':', 1)
                        values, durations = self.get_fact_values(concept_key, instance, calculations, dimension)
                        # If no values found, skip this member
                        if not values:
                            continue

                        self._durations.update(durations)

                        # Create line item for this member
                        member_label = self.get_label(member_concept, labels, member.preferred_label)
                        line_item = LineItem(
                            concept=concept,
                            axis=axis_concept.replace('_', ':', 1),
                            segment=member_concept.replace('_', ':', 1),
                            label=member_label,  # Use the member label
                            values=values,
                            level=level + 1,  # Indent member items
                            preferred_label=element.preferred_label,
                            is_abstract=False
                        )

                        # Set section information
                        if current_main_section:
                            line_item.parent_section = current_main_section.label
                        line_item.section_type = 'detail'

                        items.append(line_item)

            # Process children in presentation order (skip if handling dimensional items)
            for child in sorted(element.children, key=lambda x: x.order):
                child_items = process_element(child, level + 1, element, axes)
                items.extend(child_items)

            return items

        # Find the line items container
        line_items_container = self._find_line_items_container(presentation_element)
        if not line_items_container:
            return

        root = get_root_element(line_items_container)
        axes = get_axes_for_role(root)  # Can be [] or contain axis elements

        # Process all elements
        all_items = []
        for child in sorted(line_items_container.children, key=lambda x: x.order):
            items = process_element(child, 0, axes=axes)
            all_items.extend(items)

        self._line_items = all_items

    def rebuild(self) -> None:
        """Force rebuild of line items"""
        self._built = False
        self._line_items = []
        self._durations = set()
        if self._xbrl_data is not None:
            self._build_line_items()

    @staticmethod
    def concept_to_label(concept: str) -> str:
        return concept_to_label(concept)

    @staticmethod
    def get_label(concept: str, labels: Dict, preferred_label: str = None) -> str:
        concept_labels = labels.get(concept, {})
        if preferred_label:
            label = concept_labels.get(preferred_label.split('/')[-1])
            if label:
                return label

        # Fall back to the previous priority if preferred label is not found
        return (concept_labels.get('totalLabel')
                or concept_labels.get('terseLabel')
                or concept_labels.get('label')
                or StatementDefinition.concept_to_label(concept))

    @staticmethod
    def get_fact_values(concept: str,
                        instance: XBRLInstance,
                        calculation_links: CalculationLinkbase,
                        dimension: Optional[Dict[str, str]] = None) -> Tuple[Dict[str, Any], List[str]]:
        """
        Get fact values for a concept, optionally filtered by dimension

        Args:
            concept: The concept to get values for
            instance: XBRLInstance containing the facts
            calculation_links: Calculation linkbase for weight/sign
            dimension: Optional dictionary of axis:member pairs to filter by
        """
        # Query facts using the existing query_facts method
        if dimension:
            facts = instance.query_facts(concept=concept, dimensions=dimension)
        else:
            facts = instance.query_facts(concept=concept)

        # If no facts found, return empty values
        if facts.empty:
            return {}, []

        values = {}
        durations = facts['duration'].unique().tolist()

        # Get the calculation weight for this concept
        if calculation_links:
            calc = calculation_links.get_calculation(concept)
            weight = calc.weight if calc else 1.0
        else:
            weight = 1.0

        for _, fact in facts.iterrows():
            period = fact['end_date'] if fact[
                                             'period_type'] == 'instant' else f"{fact['start_date']} to {fact['end_date']}"

            # Apply the weight to the value
            value = fact['value']
            if weight == -1.0 and value and value[0] != '-':
                value = f"-{value}"

            # Get dimensional information from the fact
            dimensions = {}
            for col in facts.columns:
                if col not in ['concept', 'value', 'units', 'decimals', 'start_date',
                               'end_date', 'period_type', 'context_id', 'entity_id',
                               'duration'] and not pd.isna(fact[col]):
                    dimensions[col] = fact[col]

            # Create a unique key for dimensional values
            dim_key = tuple(sorted(dimensions.items()))

            # Ensure the nested dictionary structure exists
            if period not in values:
                values[period] = {}

            values[period][dim_key] = {
                'value': value,
                'units': fact.get('units'),
                'decimals': fact.get('decimals'),
                'dimensions': dimensions,
                'duration': fact.get('duration')
            }

        return values, durations

    def build_rich_tree(self, detailed: bool = False) -> Tree:
        root = Tree(f"[bold green]{self.name}[/bold green]")
        self._build_rich_tree_recursive(root, self.line_items, 0, detailed)
        return root

    def _build_rich_tree_recursive(self, tree: Tree, items: List[LineItem], current_level: int, detailed: bool):
        for item in items:
            if item.level > current_level:
                continue
            if item.level < current_level:
                return

            if detailed:
                node_text = f"[yellow]{item.label}[/yellow] ([cyan]{item.concept}[/cyan])"
                if item.values:
                    values_text = ", ".join(f"{k}: {v}" for k, v in item.values.items())
                    node_text += f"\n  [dim]{values_text}[/dim]"
            else:
                node_text = f"[cyan]{item.label}[/cyan]"

            child_tree = tree.add(node_text)
            self._build_rich_tree_recursive(child_tree, items[items.index(item) + 1:], item.level + 1, detailed)

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "Statement Definition: " + self.label

    def print_items(self, detailed: bool = False):
        tree = self.build_rich_tree(detailed)
        rprint(tree)

    def to_dict(self):
        # Convert the StatementDefinition object to a dictionary
        return {
            'name': self.name,
            'line_items': [item.dict() for item in self.line_items]
        }


def is_integer(s):
    if s is pd.NA or pd.isna(s) or not s:
        return False
    if not isinstance(s, str):
        return False
    if s[0] in ('-', '+'):
        s = s[1:]
    if '.' in s:
        if not s.replace('.', '').isdigit():
            return False
        integer_part, decimal_part = s.split('.')
        return decimal_part == '' or decimal_part.strip('0') == ''
    return s.isdigit()


def format_xbrl_value(value: Union[str, float],
                      decimals: str,
                      format_str: str = '{:>8,.0f}') -> str:
    """
    Format an XBRL value for display
    """
    if is_integer(value):
        value = float(value)
        if not pd.isna(decimals) and decimals != 'INF':
            try:
                decimal_int = int(decimals)
                if decimal_int < 0:
                    unit_divisor = 10 ** (-1 * decimal_int)
                    value /= unit_divisor
            except ValueError:
                pass
        if not pd.isna(decimals) and decimals == 'INF':
            return f"{value:>8}"
        else:
            return format_str.format(value)
    else:
        if pd.isna(value):
            value = ''
        return f"{value:>8}"


def create_unit_label(decimals: str):
    label = ""
    if decimals == '-6':
        label = "millions"
    elif decimals == '-3':
        label = "thousands"
    return Text(label, style="dim grey70")


def get_primary_units(divisor: int) -> str:
    if divisor == 1_000_000:
        return "Millions"
    elif divisor == 100_000:
        return "Hundreds of Thousands"
    elif divisor == 1_000:
        return "Thousands"
    elif divisor == 100:
        return "Hundreds"
    elif divisor == 10:
        return "Tens"
    else:
        return "Units"  # Default case if no match is found


def get_unit_divisor(df: pd.DataFrame, column: str = 'decimals') -> int:
    # Filter negative decimal values and convert them to integers
    negative_decimals = df[column].apply(pd.to_numeric, errors='coerce').dropna()
    negative_decimals = negative_decimals[negative_decimals < 0]

    if negative_decimals.empty:
        return 1  # Default to no scaling if no negative decimals found

    # Get the largest negative value (smallest divisor)
    smallest_divisor_decimal = negative_decimals.max()

    # Calculate the divisor
    divisor = 10 ** -smallest_divisor_decimal
    return int(divisor)


def format_label(label, level):
    return f"{' ' * level}{label}"


class Statement:
    format_columns = ['level', 'abstract', 'units', 'decimals', 'node_type', 'section_end', 'dimensions',
                      'has_dimensions', 'style']
    meta_columns = ['concept', 'segment'] + format_columns

    NAMES = {
        "CONSOLIDATEDSTATEMENTSOFOPERATIONS": "CONSOLIDATED STATEMENTS OF OPERATIONS",
        "CONSOLIDATEDSTATEMENTSOFCOMPREHENSIVEINCOME": "CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME",
        "CONSOLIDATEDBALANCESHEETSParenthetical": "CONSOLIDATED BALANCE SHEETS Parenthetical",
        "CONSOLIDATEDBALANCESHEETS": "CONSOLIDATED BALANCE SHEETS",
        "CONSOLIDATEDSTATEMENTSOFSHAREHOLDERSEQUITY": "CONSOLIDATED STATEMENTS OF SHAREHOLDERS EQUITY",
        "CONSOLIDATEDSTATEMENTSOFCASHFLOWS": "CONSOLIDATED STATEMENTS OF CASH FLOWS"
    }

    def __init__(self,
                 name: str,
                 entity: str,
                 df: pd.DataFrame,
                 definition: StatementDefinition,
                 display_name: str = None,
                 duration: str = None):
        self.name = name
        self.label = definition.label or name
        self.display_name = display_name or self.label
        self.entity = entity
        self.data = df
        self.definition: StatementDefinition = definition
        self.include_format = 'level' in df.columns
        self.include_concept = 'concept' in df.columns
        self.durations = definition.durations or set()
        self.display_duration = duration or ''

    @property
    def periods(self):
        return [col for col in self.data.columns if col not in self.meta_columns]

    @property
    def labels(self):
        return self.data.index.tolist()

    @property
    def concepts(self):
        return self.data['concept'].tolist() if 'concept' in self.data.columns else []

    def get_statement_name(self):
        normalized_name = self.NAMES.get(self.name)
        if not normalized_name:
            normalized_name = split_camel_case(self.name)
        return normalized_name

    def get_concept(self,
                    concept: str = None,
                    *,
                    label: str = None,
                    namespace: str = None) -> Optional[Concept]:
        assert label or concept, "Either label or concept must be provided"
        if label:
            results = self.data.loc[label]
        elif namespace:
            results = self.data[self.data['concept'] == f'{namespace}_{concept}']
        else:
            for concept_name in [concept, concept.replace(':', '_'), f'dei_{concept}', f'us-gaap_{concept}']:
                results = self.data[self.data['concept'] == concept_name]
                if len(results) > 0:
                    break

        if len(results) == 0:
            return None

        if isinstance(results, pd.Series):
            results = results.to_frame().T

        results = results.drop_duplicates()
        if len(results) == 1:
            fact = Concept(
                name=results['concept'].iloc[0],
                unit=na_value(results['units'].iloc[0]) if 'units' in results else None,
                label=results.index[0],
                decimals=na_value(results['decimals'].iloc[0]) if 'decimals' in results else None,
                value={col: results[col].iloc[0] for col in self.periods}
            )
            return fact

    def get_dimensional_items(self, concept: str = None, *, label: str = None) -> pd.DataFrame:
        """
        Get dimensional breakdowns for a specific concept or label.

        Args:
            concept: The concept name (e.g., 'us-gaap_Revenue')
            label: The label to get dimensions for (from label linkbase)

        Returns:
            DataFrame containing only the dimensional items for the specified concept/label
        """
        if 'level' not in self.data.columns:
            return pd.DataFrame()

        if label:
            try:
                if not self.data.loc[label, 'has_dimensions']:
                    return pd.DataFrame()

                # Get the concept for this label
                if 'concept' not in self.data.columns:
                    return pd.DataFrame()

                concept = self.data.loc[label, 'concept']
                base_level = self.data.loc[label, 'level']

                # Get all items with same concept at deeper levels
                dim_mask = (
                        (self.data['concept'] == concept) &
                        (self.data['level'] > base_level)
                )
                return self.data[dim_mask]

            except KeyError:
                return pd.DataFrame()

        elif concept:
            if 'concept' not in self.data.columns:
                raise ValueError("Concept column not included in statement")

            # Find base items for this concept
            base_mask = (
                    (self.data['concept'] == concept) &
                    (self.data['level'] == 0)  # Base items are at level 0
            )
            base_items = self.data[base_mask]

            if base_items.empty:
                return pd.DataFrame()

            # Get all dimensional items for this concept
            dim_mask = (
                    (self.data['concept'] == concept) &
                    (self.data['level'] > 0)
            )
            return self.data[dim_mask]

        return pd.DataFrame()

    def get_base_items(self) -> pd.DataFrame:
        """
        Get only the non-dimensional items (base concepts without dimensional qualifiers)

        Returns:
            DataFrame containing only the base (non-dimensional) items
        """
        if 'level' not in self.data.columns:
            return self.data

        base_mask = (
            # Either it's a header item (abstract)
                (self.data.get('abstract', False)) |
                # Or it's a main item at level 0
                (self.data['level'] == 0)
        )

        return self.data[base_mask]

    def filter_by_dimension(self, axis: str, member: str = None) -> pd.DataFrame:
        """
        Filter the statement to show only items with specific dimensional values.

        Args:
            axis: The axis concept name (e.g., 'us-gaap_GeographicAreasAxis')
            member: Optional member concept name (e.g., 'us-gaap_DomesticOperationsMember')

        Returns:
            DataFrame containing only the matching dimensional items
        """
        if 'concept' not in self.data.columns:
            raise ValueError("Concept column required for dimensional filtering")

        # Get base items that have dimensional breakdowns
        base_items = self.data[self.data['has_dimensions']]

        result_rows = []
        for base_label in base_items.index:
            base_concept = base_items.loc[base_label, 'concept']
            dim_items = self.get_dimensional_items(concept=base_concept)

            if not dim_items.empty:
                matching_dims = []

                # Filter dimensional items by axis and member
                for idx in dim_items.index:
                    dim_row = dim_items.loc[idx]
                    dimensions = dim_row.get('dimensions', {})

                    # Check if this item has the specified axis
                    if isinstance(dimensions, dict) and axis in dimensions:
                        # If member is specified, check for exact match
                        if member is None or dimensions[axis] == member:
                            dim_dict = dim_row.to_dict()
                            dim_dict['label'] = idx
                            matching_dims.append(dim_dict)

                # Only include base item if we found matching dimensional items
                if matching_dims:
                    base_row = base_items.loc[base_label].to_dict()
                    base_row['label'] = base_label
                    result_rows.append(base_row)
                    result_rows.extend(matching_dims)

        if result_rows:
            df = pd.DataFrame(result_rows)
            if 'label' in df.columns:
                df = df.set_index('label')
            return df

        return pd.DataFrame(columns=self.data.columns)

    def print_dimensional_structure(self):
        """
        Print a hierarchical view of the dimensional structure showing axes and members.
        """
        from rich.tree import Tree
        from rich.console import Console
        from collections import defaultdict

        console = Console()

        # Get base items with dimensions
        base_items = self.data[self.data['has_dimensions']]

        if base_items.empty:
            console.print("[italic]No dimensional items found in statement[/italic]")
            return

        # Create main tree
        main_tree = Tree(f"[bold blue]{self.display_name}[/bold blue]")

        for base_label in base_items.index:
            base_concept = base_items.loc[base_label, 'concept']
            dim_items = self.get_dimensional_items(concept=base_concept)

            if dim_items.empty:
                continue

            # Create branch for base concept
            concept_tree = main_tree.add(
                f"[bold white]{base_label}[/bold white] ([dim]{base_concept}[/dim])"
            )

            # Organize dimensions by axis
            axis_members = defaultdict(list)
            for idx in dim_items.index:
                dimensions = dim_items.loc[idx].get('dimensions', {})
                if isinstance(dimensions, dict):
                    for axis, member in dimensions.items():
                        axis_members[axis].append((idx, member))

            # Add axes and their members
            for axis, members in axis_members.items():
                # Get axis label if available
                axis_label = self.definition.labels.get(axis, {}).get('label', axis)
                axis_tree = concept_tree.add(f"[yellow]{axis_label}[/yellow] ([dim]{axis}[/dim])")

                # Add members under this axis
                for idx, member in members:
                    # Get member label if available
                    member_label = self.definition.labels.get(member, {}).get('label', member)
                    value = dim_items.loc[idx].get(self.periods[0], '')  # Get first period's value
                    if value:
                        axis_tree.add(
                            f"[green]{member_label}[/green] ([dim]{member}[/dim]): {value}"
                        )
                    else:
                        axis_tree.add(
                            f"[green]{member_label}[/green] ([dim]{member}[/dim])"
                        )

        console.print(main_tree)

    def get_dimensional_structure(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Get a dictionary showing the dimensional structure of the statement

        Returns:
            Dict mapping concepts to their dimensional breakdowns
        """
        structure = {}
        base_items = self.get_base_items()

        for label, row in base_items.iterrows():
            if row['has_dimensions']:
                concept = row['concept']
                if concept not in structure:
                    structure[concept] = {
                        'label': label,
                        'dimensions': []
                    }

                dim_items = self.get_dimensional_items(concept=concept)
                structure[concept]['dimensions'].extend(dim_items.index.tolist())

        return structure

    def get_dataframe(self,
                      include_format: bool = False,
                      include_concept: bool = True):
        columns = [col for col in self.data.columns if col not in self.meta_columns]
        if include_concept:
            columns.append('concept')
        if include_format:
            columns.extend(self.format_columns)
        columns = [col for col in columns if col in self.data.columns]
        return self.data[columns]

    def to_dataframe(self,
                     include_format: bool = False,
                     include_concept: bool = False):
        return self.get_dataframe(include_format, include_concept)

    def to_excel(self,
                 filename: str = None,
                 excel_writer: pd.ExcelWriter = None,
                 include_format: bool = False,
                 include_concept: bool = True):
        df = self.get_dataframe(include_format=include_format, include_concept=include_concept)
        if excel_writer:
            df.to_excel(excel_writer, index=True, sheet_name=self.name[:31])
        else:
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=True, sheet_name=self.name[:31])

    def print_structure(self, detailed: bool = False):
        self.definition.print_items(detailed)

    def durations_table(self):
        # Create a compact duration table
        if self.durations:
            duration_table = Table(
                Column("Duration", style="dim grey74"),
                box=None,
                show_header=False,
                padding=(0, 2)
            )

            # Format durations in rows of 3
            durations_list = sorted(list([d for d in self.durations if d != 'instant']))
            current_row = []

            for duration in durations_list:
                formatted_duration = duration.title()
                if duration == self.display_duration:
                    current_row.append(Text(formatted_duration, style="bold deep_sky_blue3"))
                else:
                    current_row.append(Text(formatted_duration, style="dim grey74"))

                if len(current_row) == 3:
                    duration_table.add_row(*current_row)
                    current_row = []

            # Add any remaining durations
            if current_row:
                duration_table.add_row(*current_row)
            return duration_table

    def __rich__(self):
        if self.data.empty:
            return Text.assemble(
                (f"{self.entity}\n", "bold deep_sky_blue2"),
                (self.display_name, "bold"),
                f"\nNo data found for {self.display_name}"
            )
        # Get value columns
        value_cols = [col for col in self.data.columns if col not in self.meta_columns + ['segment', 'axis']]

        # Create table
        if 'decimals' in self.data.columns:
            table = Table(
                Column("", width=50),  # Label column
                Column(""),  # Units column
                *(Column(col, justify="right") for col in value_cols),
                title=Text.assemble(
                    (f"{self.entity}\n", "bold deep_sky_blue2"),
                    (f"{self.display_name}\n", "bold"),
                    (f"{self.display_duration.title()}", "italic grey60")
                ),
                box=box.SIMPLE,
                padding=(0, 1),
                collapse_padding=True
            )
        else:
            table = Table(
                Column("", width=50),  # Label column
                *(Column(col, justify="right") for col in value_cols),
                title=Text.assemble(
                    (f"{self.entity}\n", "bold deep_sky_blue2"),
                    (self.display_name, "bold")
                ),
                box=box.SIMPLE,
                padding=(0, 1),
                collapse_padding=True
            )

        # Add rows
        for index, row in self.data.iterrows():
            style = row.get('style', 'Detail')

            # Determine text style
            if style == 'Header':
                label_style = "bold deep_sky_blue3"
                value_style = "bold white"
            elif style == 'Subsection':
                label_style = "italic grey60"
                value_style = "italic grey60"
            elif style == 'Total':
                label_style = "bold deep_sky_blue3"
                value_style = "bold deep_sky_blue3"
            else:
                label_style = "grey42"
                value_style = "grey42"

            # Format label with indentation
            indent = "  " * row.get('level', 0)
            if style == 'Header' or style == 'Subsection':
                formatted_label = f"{indent}{index}:"
            else:
                formatted_label = f"{indent}{index}"

            label = Text(formatted_label, style=label_style)

            # Format numerical values
            values = []
            for col in value_cols:
                raw_value = row[col]
                if pd.notna(raw_value) and raw_value != '':
                    try:
                        num_value = float(raw_value)
                        if num_value < 0:
                            formatted_value = f"({format_xbrl_value(str(abs(num_value)), row.get('decimals', '0'))})"
                        else:
                            formatted_value = format_xbrl_value(str(num_value), row.get('decimals', '0'))
                    except ValueError:
                        formatted_value = str(raw_value)
                else:
                    formatted_value = ""

                values.append(Text(formatted_value, style=value_style, justify="right"))

            if 'decimals' in self.data.columns:
                unit_label = create_unit_label(str(row.get('decimals', '')))
                table.add_row(label, unit_label, *values)
            else:
                table.add_row(label, *values)

        duration_table = self.durations_table()
        if not duration_table or len(duration_table.columns) < 2:
            return table

        # Return both tables in a group
        return Group(
            table,
            Text(""),  # Empty line as spacing
            Text("Available durations for this statement:", style="dim grey74"),
            duration_table
        )

    def __repr__(self):
        return repr_rich(self.__rich__(), width=240)

    def __str__(self):
        return f"{self.display_name}"


class Statements():

    def __init__(self, xbrl_data):
        self.xbrl_data = xbrl_data
        self.names = list(self.xbrl_data.statements_dict.keys())

    def get(self,
            statement_name: str,
            include_format: bool = True,
            include_concept: bool = True):
        return self.xbrl_data.get_statement(statement_name, include_format, include_concept)

    def __getattr__(self, name):
        if name in self.names:
            return self.get(name)

    def __contains__(self, item):
        return item in self.names

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.get(self.names[item])
        else:
            return self.get(item)

    def __len__(self):
        return len(self.names)

    def __iter__(self):
        self.n = 0
        return self

    def __next__(self):
        if self.n < len(self.names):
            statement_name: str = self.names[self.n]
            self.n += 1
            return self.get(statement_name)
        else:
            raise StopIteration

    @staticmethod
    def colorize_name(statement):
        words = split_camel_case(statement).split(" ")
        return colorize_words(words)

    def __rich__(self):
        table = Table("", "Statements", box=box.ROUNDED, show_header=True)
        for index, statement_name in enumerate(self.names):
            table.add_row(str(index), Statements.colorize_name(statement_name))
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


class XBRLData():
    """
       A parser for XBRL (eXtensible Business Reporting Language) documents.

       This class processes various XBRL components (instance, presentation, labels, calculations)
       and provides methods to extract and format financial statements.

       Attributes:
           instance (XBRLInstance): Parsed XBRL instance document.
           presentation (XBRLPresentation): Parsed XBRL presentation linkbase.
           labels (Dict): Dictionary of labels for XBRL concepts.
           calculations (Dict): Dictionary of calculation relationships.
           statements_dict (Dict[str, StatementDefinition]): Dictionary of parsed financial statements.

       Class Methods:
           parse(instance_xml: str, presentation_xml: str, labels: Dict, calculations: Dict) -> 'XBRL':
               Parse XBRL documents from XML strings and create an XBRL instance.

           from_filing(filing: Filing) -> 'XBRL':
               Asynchronously create an XBRL instance from a Filing object.

       """
    def __init__(self,
                 instance: XBRLInstance,
                 presentation: XBRLPresentation,
                 labels: Dict,
                 calculations: Optional[CalculationLinkbase] = None
                 ):
        self.instance = instance
        self.presentation = presentation
        self.labels = labels
        self.calculations = calculations
        self.statements_dict: Dict[str, StatementDefinition] = dict()
        self.label_to_concept_map: Dict[str, str] = dict()


    def _build_label_to_concept_map(self):
        for concept, label_dict in self.labels.items():
            for label_type, label in label_dict.items():
                self.label_to_concept_map[label.lower()] = concept

    @classmethod
    def parse(cls,
              *,
              instance_xml: str,
              presentation_xml: str,
              labels: Dict,
              calculations: CalculationLinkbase) -> 'XBRLData':
        """
        Parse XBRL documents from XML strings and create an XBRLParser instance.

        Args:
            instance_xml (str): XML string of the XBRL instance document.
            presentation_xml (str): XML string of the XBRL presentation linkbase.
            labels (Dict): Dictionary of labels for XBRL concepts.
            calculations (Dict): Dictionary of calculation relationships.

        Returns:
            XBRLData: An instance of XBRLParser with parsed XBRL components.
        """
        instance = XBRLInstance.parse(instance_xml)
        presentation = XBRLPresentation.parse(presentation_xml)
        xbrl_data = cls(
            instance=instance,
            presentation=presentation,
            labels=labels,
            calculations=calculations
        )
        xbrl_data._build_label_to_concept_map()
        xbrl_data.parse_financial_statements()
        return xbrl_data

    @classmethod
    async def from_filing(cls, filing: Filing):
        """
        Asynchronously create an XBRLParser instance from a Filing object.

        Args:
            filing (Filing): A Filing object containing XBRL document attachments.

        Returns:
            XBRLData: An instance of XBRLParser with parsed XBRL components.
        """
        xbrl_documents = XBRLAttachments(filing.attachments)
        if xbrl_documents.empty:
            log.warning(f"No XBRL documents found in the filing. {filing}")
            return None

        assert not xbrl_documents.instance_only, "Instance document must be accompanied by other XBRL documents"

        parsed_documents = await xbrl_documents.load()
        if parsed_documents:
            instance_xml, presentation_xml, labels, calculations = parsed_documents
            return cls.parse(instance_xml=instance_xml,
                             presentation_xml=presentation_xml,
                             labels=labels,
                             calculations=calculations)

    @classmethod
    def from_files(cls,
                   *,
                   instance_path: Path,
                   presentation_path: Path,
                   label_path: Path,
                   calculation_path: Path):
        """
        Create an XBRLData from local files.
        """
        instance_xml = instance_path.read_text() if instance_path.exists() else None
        presentation_xml = presentation_path.read_text() if presentation_path and presentation_path.exists() else None
        labels = parse_label_linkbase(label_path.read_text()) if label_path and label_path.exists() else None
        calculations = CalculationLinkbase.parse(
            calculation_path.read_text()) if calculation_path and calculation_path.exists() else None

        return cls.parse(instance_xml=instance_xml,
                         presentation_xml=presentation_xml,
                         labels=labels,
                         calculations=calculations)

    @classmethod
    def extract(cls, filing: 'Filing'):
        """
        Extract XBRL data from a filing object.
        """
        return run_async_or_sync(cls.from_filing(filing))

    def parse_financial_statements(self):
        """
        Parse financial statements based on the presentation structure.

        This method creates StatementDefinition objects for each role in the presentation
        linkbase and stores them in the statements dictionary.
        """
        for role, root_element in self.presentation.roles.items():
            statement_name = role.split('/')[-1]
            self.statements_dict[statement_name] = StatementDefinition.create(
                role,
                presentation_element=root_element,
                labels=self.labels,
                xbrl_data=self
            )

    @cached_property
    def statements(self):
        return Statements(self)

    @property
    def company(self):
        return self.instance.get_entity_name()

    @property
    def period_end(self):
        return self.instance.get_document_period()

    def print_structure(self):
        """Print the structure of the XBRL data."""
        if self.presentation:
            self.presentation.print_structure()

    def list_statement_definitions(self) -> List[str]:
        return list(self.statements_dict.keys())

    def get_statement_definition(self, statement_name: str) -> Optional[StatementDefinition]:
        """Find the statement in the statements dictionary."""
        statement = self.statements_dict.get(statement_name)
        if statement:
            return statement
        for key, statement in self.statements_dict.items():
            if statement_name.lower() == key.lower():
                return statement

    def has_statement(self, statement_name: str) -> bool:
        """Check if the statement exists in the statements dictionary."""
        return self.get_statement_definition(statement_name) is not None

    @staticmethod
    def get_correct_value(value_info):
        if isinstance(value_info, dict) and 'dimensional_values' in value_info:
            # Prefer the value with no dimensions
            no_dimension_value = next(
                (v['value'] for v in value_info['dimensional_values'].values() if not v['dimensions']), None)
            if no_dimension_value is not None:
                return no_dimension_value
            # If all values have dimensions, return the first one
            return next(iter(value_info['dimensional_values'].values()))['value']
        return value_info.get('value', '')

    def get_statement(self,
                      statement_name: str,
                      include_format: bool = True,
                      include_concept: bool = True,
                      empty_threshold: float = 0.9,
                      display_name: str = None,
                      duration: str = None) -> Optional[Statement]:

        statement_definition = self.get_statement_definition(statement_name)
        if not statement_definition:
            return None

        fiscal_period_focus = self.instance.get_fiscal_period_focus()
        is_quarterly = fiscal_period_focus in ['Q1', 'Q2', 'Q3', 'Q4']

        def format_value(value: str, decimals: str) -> str:
            """Convert value to raw numerical form"""
            if not value or value == '':
                return ''

            try:
                # Convert to float for numerical operations
                num_value = float(value)
                if pd.isna(decimals):
                    return f'{num_value:.0f}'
                elif decimals == 'INF':
                    return str(num_value)
                elif decimals.isdigit():
                    return f'{num_value:.{decimals}f}'
                return f'{num_value:.0f}'  # Return raw numerical value
            except ValueError:
                return value

        def get_format_info(item: LineItem) -> dict:
            """Get formatting information for the line item"""
            if item.is_main_section:
                style = 'Header'
            elif item.is_subsection:
                style = 'Subsection'
            elif item.is_total:
                style = 'Total'
            else:
                style = 'Detail'

            return {
                'level': item.level,
                'style': style,
                'is_abstract': item.is_abstract,
                'section': item.parent_section
            }

        # Collect data
        data = []
        line_items = statement_definition.line_items

        for i, item in enumerate(line_items):
            # Base row
            row = {
                'concept': item.concept,
                'label': item.label,
                'segment': item.segment,
                'presentation_order': i
            }

            if include_format:
                row.update(get_format_info(item))

            # Process values
            if not item.is_abstract:
                for period, period_facts in item.values.items():
                    end_date = period.split(' to ')[-1]
                    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
                    period_label = end_date_obj.strftime("%b %d, %Y") if is_quarterly else end_date.split('-')[0]

                    fact_key = ((item.axis, item.segment),) if item.segment else ()
                    if fact_key in period_facts:
                        base_fact = period_facts[fact_key]
                        current_duration = base_fact['duration']

                        # Format value
                        value = format_value(base_fact['value'], base_fact['decimals'])

                        column_key = (period_label, current_duration)
                        row[column_key] = value

                        if include_format:
                            row['units'] = base_fact['units']
                            row['decimals'] = base_fact['decimals']

            data.append(row)

        if len(data) == 0:
            # Create an empty dataframe with the required columns
            df = pd.DataFrame(columns=['concept', 'label', 'segment', 'presentation_order'])

            return Statement(
                df=df,
                name=statement_name,
                display_name=display_name,
                definition=statement_definition,
                entity=self.instance.get_entity_name(),
                duration=None
            )
        else:
            df = pd.DataFrame(data)

        period_columns, selected_duration, date_mapping = self._select_duration_and_columns(df, is_quarterly, duration)

        if not period_columns:
            # Happens for some rare occasions where annual
            period_cols = [col for col in df.columns if isinstance(col, tuple)]
            date_mapping = {col: col[0] for col in period_cols}

        # Select and rename columns
        format_columns = [col for col in df.columns if not isinstance(col, tuple)]
        df = df[period_columns + format_columns]
        df = df.rename(columns=date_mapping)

        # Sort and set index
        df = df.sort_values('presentation_order')
        df = df.set_index('label')
        df = df.drop('presentation_order', axis=1)

        # Drop columns that are mostly empty
        empty_counts = ((df.isna()) | (df == '')).sum() / len(df)
        columns_to_keep = empty_counts[empty_counts < empty_threshold].index
        df = df[columns_to_keep]

        # Select final columns
        value_columns = [col for col in df.columns if col not in
                         ['concept', 'level', 'style', 'is_abstract', 'units', 'decimals', 'section']]

        columns_to_include = value_columns
        if include_concept:
            columns_to_include.append('concept')
        if include_format:
            columns_to_include.extend(['level', 'style'])
        if 'decimals' in df.columns:
            columns_to_include.append('decimals')

        df = df[columns_to_include]

        return Statement(
            df=df,
            name=statement_name,
            display_name=display_name,
            definition=statement_definition,
            entity=self.instance.get_entity_name(),
            duration=selected_duration
        )

    @staticmethod
    def _select_duration_and_columns(df, is_quarterly: bool, preferred_duration: str = None):
        """
        Select the appropriate duration and return corresponding columns and selected duration,
        while also merging instant values into period columns.
        """
        period_columns = [col for col in df.columns if isinstance(col, tuple)]

        if not is_quarterly:
            # For annual reports, separate instant and annual columns
            instant_cols = [col for col in period_columns if col[1] == 'instant']
            annual_cols = [col for col in period_columns if col[1] == 'annual']

            # Group by date
            date_groups = defaultdict(dict)
            for col in instant_cols + annual_cols:
                date, duration = col
                date_groups[date][duration] = col

            # Merge instant values into annual columns
            final_columns = []
            date_mapping = {}
            for date, columns in date_groups.items():
                if 'annual' in columns:
                    annual_col = columns['annual']
                    if 'instant' in columns:
                        # Merge instant values
                        df[annual_col] = df[annual_col].fillna(df[columns['instant']])
                    final_columns.append(annual_col)
                    date_mapping[annual_col] = date
                elif 'instant' in columns:
                    # Fallback to instant column if no annual column exists
                    instant_col = columns['instant']
                    final_columns.append(instant_col)
                    date_mapping[instant_col] = date

            # Sort columns by date
            final_columns.sort(key=lambda x: x[0], reverse=True)
            return final_columns, 'annual', date_mapping

        # For quarterly reports
        # Group columns by date
        column_groups = defaultdict(dict)
        for col in period_columns:
            date, duration = col
            column_groups[date][duration] = col

        # Count non-empty values for each duration
        valid_durations = ['3 months', '6 months', '9 months', 'instant']
        duration_counts = {dur: 0 for dur in valid_durations}

        for date_group in column_groups.values():
            for dur in valid_durations:
                if dur in date_group:
                    non_empty = df[date_group[dur]].notna().sum()
                    duration_counts[dur] += non_empty

        # Choose the duration
        selected_duration = None
        if preferred_duration and preferred_duration in duration_counts and duration_counts[preferred_duration] > 0:
            selected_duration = preferred_duration
        else:
            # Select the duration with the most non-empty values
            valid_durations = [dur for dur in valid_durations if duration_counts[dur] > 0]
            if valid_durations:
                selected_duration = max(valid_durations, key=lambda x: duration_counts[x])

        if not selected_duration:
            return [], None, {}

        # Select and merge columns
        final_columns = []
        date_mapping = {}

        for date, columns in column_groups.items():
            if selected_duration in columns:
                period_col = columns[selected_duration]
                if 'instant' in columns:
                    # Merge instant values
                    df[period_col] = df[period_col].fillna(df[columns['instant']])
                final_columns.append(period_col)
                date_mapping[period_col] = date

        # Sort columns by date
        final_columns.sort(key=lambda x: datetime.strptime(x[0], "%b %d, %Y"), reverse=True)

        return final_columns, selected_duration, date_mapping

    def get_concept_for_label(self, label: str) -> Optional[str]:
        """
        Search for a concept using its label.

        Args:
            label (str): The label to search for.

        Returns:
            Optional[str]: The corresponding concept if found, None otherwise.
        """
        return self.label_to_concept_map.get(label.lower())

    def get_labels_for_concept(self, concept: str) -> Dict[str, str]:
        """
        Get all labels for a given concept.

        Args:
            concept (str): The concept to get labels for.

        Returns:
            Dict[str, str]: A dictionary of label types and their corresponding labels.
        """
        return self.labels.get(concept, {})

    def get_roles_for_label(self, label: str) -> List[str]:
        """
        Get all roles containing a concept identified by its label.

        Args:
            label (str): The label to search for.

        Returns:
            List[str]: A list of roles containing the concept identified by the label.
        """
        concept = self.get_concept_for_label(label)
        if concept:
            return self.presentation.get_roles_containing_concept(concept)
        return []

    def list_statements_for_label(self, label: str) -> List[str]:
        """
        Get a list of statement names containing a concept identified by its label.
        """
        return [role.split('/')[-1]
                for role in self.get_roles_for_label(label)]

    def pivot_on_dimension(self, statement_name: str, dimension: str, value_column: str = 'value') -> pd.DataFrame:
        statement = self.get_statement_definition(statement_name)
        if not statement:
            return pd.DataFrame()

        df_copy = self.instance.facts[self.instance.facts['concept'].isin(statement.concepts)].copy()
        df_copy['dim_value'] = df_copy['dimensions'].apply(lambda x: x.get(dimension))
        pivoted = df_copy.pivot(index='concept', columns='dim_value', values=value_column)
        return pivoted

    def compare_dimension_values(self, statement_name: str, dimension: str, value1: str, value2: str,
                                 value_column: str = 'value') -> pd.DataFrame:
        statement = self.get_statement_definition(statement_name)
        if not statement:
            return pd.DataFrame()

        df = self.instance.facts[self.instance.facts['concept'].isin(statement.concepts)]
        df1 = df[df['dimensions'].apply(lambda x: x.get(dimension) == value1)]
        df2 = df[df['dimensions'].apply(lambda x: x.get(dimension) == value2)]
        comparison = pd.merge(df1, df2, on='concept', suffixes=('_' + value1, '_' + value2))
        return comparison[[f'{value_column}_{value1}', f'{value_column}_{value2}']]

    def find_role_by_concept(self, concept: str) -> Optional[str]:
        """
        Helper method to find a role containing specific concepts.

        Args:
            primary_concept str: Concept names to search for.

        Returns:
            Optional[str]: The role containing the most matching concepts, or None if no matches found.
        """
        role_matches = defaultdict(int)
        for role in self.presentation.get_roles_containing_concept(concept):
            role_matches[role] += 1

        return max(role_matches, key=role_matches.get) if role_matches else None

    def get_statement_name_for_standard_name(self, standard_statement: StandardStatement) -> Optional[str]:
        role = self.presentation.get_role_by_standard_name(standard_statement.statement_name)
        if not role:
            role = self.find_role_by_concept(standard_statement.primary_concept)
        if role:
            statement_name = role.split('/')[-1]
            return statement_name

    def get_standard_statement_table(self):
        table = Table(Column("Name", width=34, style="bold"), Column("Accessor"),
                      box=box.SIMPLE_HEAD, show_header=True, title="Financial Statements")
        if self.get_statement_name_for_standard_name(BalanceSheet):
            table.add_row(Text("Balance Sheet"), Text('financials.balance_sheet', style="italic"))
        if self.get_statement_name_for_standard_name(IncomeStatement):
            table.add_row(Text("Income Statement"), Text('financials.income', style="italic"))
        if self.get_statement_name_for_standard_name(CashFlowStatement):
            table.add_row(Text("Cash Flow Statement"), Text('financials.cashflow', style="italic"))
        if self.get_statement_name_for_standard_name(StatementOfChangesInEquity):
            table.add_row(Text("Statement of Changes in Equity"), Text('financials.equity', style="italic"))
        if self.get_statement_name_for_standard_name(StatementOfComprehensiveIncome):
            table.add_row(Text("Statement of Comprehensive Income"), Text('financials.comprehensive_income', style="italic"))
        return table

    def __rich__(self):
        group = Group(
            self.instance,
            self.get_standard_statement_table(),
        )
        panel = Panel(group, title="XBRL")
        return panel

    def __repr__(self):
        return repr_rich(self)

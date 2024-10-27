from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edgar import Filing

import asyncio
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from functools import cached_property
from functools import lru_cache
from typing import Dict, List, Tuple, Union, Any, Optional, Set

import pandas as pd
from pydantic import BaseModel, Field, ConfigDict
from rich import box
from rich import print as rprint
from rich.console import Group
from rich.panel import Panel
from rich.table import Table, Column
from rich.text import Text
from rich.tree import Tree

from edgar.datatools import replace_all_na_with_empty, na_value
from edgar.richtools import repr_rich, colorize_words
from edgar.attachments import Attachments
from edgar.core import log, split_camel_case, run_async_or_sync
from edgar.httprequests import download_file_async
from edgar.xbrl.calculations import CalculationLinkbase
from edgar.xbrl.concepts import Concept, concept_to_label
from edgar.xbrl.definitions import parse_definition_linkbase
from edgar.xbrl.instance import XBRLInstance
from edgar.xbrl.labels import parse_label_linkbase
from edgar.xbrl.presentation import XBRLPresentation, PresentationElement, get_root_element, get_axes_for_role, \
    get_members_for_axis
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
                if attachment.document_type in ['XML', 'EX-101.INS']:
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
        download_tasks = []
        for doc_type in ['instance', 'schema', 'label', 'calculation', 'presentation']:
            attachment = self.get(doc_type)
            if attachment:
                download_tasks.append(XBRLAttachments.download_and_parse(doc_type, parsers[doc_type], attachment.url))

        # Wait for all downloads to complete
        results = await asyncio.gather(*download_tasks)
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

    @staticmethod
    async def download_and_parse(doc_type: str, parser, url: str):
        content = await download_file_async(url)
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
    label: str
    values: Dict[str, Any]
    level: int

    def __hash__(self):
        return hash((self.concept, self.label, self.level))


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

        if not role or not presentation_element or not labels or not xbrl_data:
            raise ValueError("All parameters are required")

        # Factory method to create a StatementDefinition instance
        label: str = cls._get_label_from_presentation_element(presentation_element, labels)

        # Create the StatementDefinition
        statement_definition = cls(role=role, label=label, presentation_element=presentation_element)
        statement_definition._xbrl_data = xbrl_data

        return statement_definition

    @staticmethod
    def _find_line_items_container(element: PresentationElement) -> Optional[PresentationElement]:
        """Find the StatementLineItems container in the hierarchy"""
        if element.node_type == 'LineItems':
            return element
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
                         instance: XBRLInstance,
                         include_segments: bool = True):
        seen_sections = defaultdict(int)
        seen_concepts = set()

        def process_element(element: PresentationElement, level: int, is_root: bool = False):
            concept = element.href.split('#')[-1]
            label = self.get_label(concept, labels, element.preferred_label)

            if seen_sections[label] > 0 and element.children:
                return

            if is_root and concept in seen_concepts:
                return

            seen_sections[label] += 1
            seen_concepts.add(concept)

            # Get the fact values for this concept. Use the version with ':' instead of '_'
            concept_key = concept.replace('_', ':', 1)

            # Only process if it's a line item or abstract
            if element.node_type in ['LineItem', 'Abstract']:
                values, durations = self.get_fact_values(concept_key, instance, calculations)
                self._line_items.append(LineItem(
                    concept=concept,
                    label=label,
                    values=values,
                    level=level
                ))

                # If segments are requested and this is a line item (not abstract)
                if include_segments and element.node_type == 'LineItem':
                    root = get_root_element(element)
                    axes = get_axes_for_role(root)

                    for axis in axes:
                        axis_name = axis.href.split('#')[-1]
                        members = get_members_for_axis(root, axis_name)
                        axis_key = axis_name.replace('_', ':', 1)
                        # Add a line item for each member
                        for member in members:
                            member_name = member.split('#')[-1]
                            member_key = member_name.replace('_', ':', 1)
                            # Create a new values dictionary for this member
                            member_values = {}
                            for period, period_values in values.items():
                                # Find the dimensional values for this member
                                member_key = tuple([(axis_key, member_key)])
                                if member_key in period_values:
                                    member_values[period] = {(): period_values[member_key]}

                            if member_values:  # Only add if we have values for this member
                                self._line_items.append(LineItem(
                                    concept=member_name,
                                    label=self.get_label(member_name, labels),
                                    values=member_values,
                                    level=level + 1
                                ))

                # Add the durations to the set
                self._durations.update(durations)

                # Process children
                for child in sorted(element.children, key=lambda x: x.order):
                    process_element(child, level + 1)

        line_items_container = self._find_line_items_container(presentation_element)

        if line_items_container:
            # Process only the elements under StatementLineItems
            for child in sorted(line_items_container.children, key=lambda x: x.order):
                process_element(child, 0, is_root=True)
        else:
            # Fallback: process all elements if no StatementLineItems container is found
            for child in sorted(presentation_element.children, key=lambda x: x.order):
                process_element(child, 0, is_root=True)

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
                        calculation_links: CalculationLinkbase) -> Tuple[Dict[str, Any], List[str]]:
        facts = instance.query_facts(concept=concept)
        values = {}

        # Get the durations for all facts for this concept
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

            # Create a dictionary of dimensions
            dimensions = {col: fact[col] for col in facts.columns if col not in
                          ['concept', 'value', 'units', 'decimals', 'start_date', 'end_date', 'period_type',
                           'context_id', 'entity_id',
                           'duration'] and not pd.isna(fact[col])}

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

    def __rich__(self):
        return self.build_rich_tree()

    def __repr__(self):
        return repr_rich(self)

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
                      format_str: str = '{:>10,.0f}') -> str:
    """
    Format an XBRL value for display
    """
    if is_integer(value):
        value = float(value)
        if decimals != 'INF':
            try:
                decimal_int = int(decimals)
                if decimal_int < 0:
                    unit_divisor = 10 ** (-1 * decimal_int)
                    value /= unit_divisor
            except ValueError:
                pass
        if decimals == 'INF':
            return f"{value:>10}"
        else:
            return format_str.format(value)
    else:
        if pd.isna(value):
            value = ''
        return f"{value:>10}"


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
    format_columns = ['level', 'abstract', 'units', 'decimals', 'node_type', 'section_end', 'has_dimensions']
    meta_columns = ['concept'] + format_columns

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
                 display_name: str = None):
        self.name = name
        self.label = definition.label or name
        self.display_name = display_name or self.label
        self.entity = entity
        self.data = df
        self.definition: StatementDefinition = definition
        self.include_format = 'level' in df.columns
        self.include_concept = 'concept' in df.columns
        self.durations = definition.durations or set()

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

    def get_dataframe(self,
                      include_format: bool = False,
                      include_concept: bool = False):
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

    @lru_cache(maxsize=1)
    def get_unit_divisor(self):
        return get_unit_divisor(self.data, "decimals")

    def get_primary_units(self):
        unit_divisor = self.get_unit_divisor()
        return get_primary_units(unit_divisor)

    def print_structure(self, detailed: bool = False):
        self.definition.print_items(detailed)

    def __rich__(self):
        # Get value columns (excluding formatting columns)
        value_cols = [col for col in self.data.columns if col not in self.meta_columns]

        # Create columns for the table
        if 'decimals' in self.data:
            columns = [
                Column('', ),  # Label column
                Column('', width=12)  # Units column
            ]
        else:
            columns = [Column('')]  # Label column only

        # Add value columns
        columns.extend([Column(col, justify='right') for col in value_cols])

        # Create table with title
        table = Table(
            *columns,
            title=Text.assemble(
                *[(f"{self.entity}\n", "bold deep_sky_blue2"),
                  (self.display_name, "bold")]
            ),
            box=box.SIMPLE,
            padding=(0, 1),  # Add some horizontal padding
            collapse_padding=True
        )

        # Add rows
        prev_level = 0
        for index, row in self.data.iterrows():
            # Get node type and formatting information
            node_type = row.get('node_type', 'Detail')
            is_section_end = row.get('section_end', False)
            has_dimensions = row.get('has_dimensions', False)
            level = row.get('level', 0)

            # Determine styles based on node type
            if node_type == 'Header':
                label_style = "bold deep_sky_blue3"
                row_style = ""
            elif node_type == 'Total':
                label_style = "bold white"
                row_style = "bold"
            elif node_type == 'Detail':
                label_style = "dim grey74"
                row_style = ""
            else:  # MainItem
                label_style = "white"
                row_style = ""

            # Add extra spacing before headers if not first row
            if node_type == 'Header' and prev_level < level:
                table.add_row("")

            # Format label
            label_text = index
            if has_dimensions:
                label_text += " †"  # Add indicator for items with dimensional breakdowns

            # Add indentation
            indent = "  " * level
            label = Text(f"{indent}{label_text}", style=label_style)

            # Format values
            if 'decimals' in self.data:
                # Create unit label with appropriate style
                unit_label = create_unit_label(na_value(row['decimals']))
                if node_type == 'Header':
                    unit_label = Text("")  # No unit label for headers

                # Create value columns
                values = [
                    label,
                    unit_label,
                    *[Text.assemble(
                        *[(format_xbrl_value(
                            value=row[col],
                            decimals=na_value(row['decimals'])
                        ), row_style)]
                    ) for col in value_cols]
                ]
            else:
                values = [
                    label,
                    *[Text.assemble(
                        *[(na_value(row[col]), row_style)]
                    ) for col in value_cols]
                ]

            # Add the row
            table.add_row(*values)

            # Add extra spacing after sections
            if is_section_end:
                table.add_row("")

            prev_level = level

        # Add footer if there are items with dimensional breakdowns
        if any(self.data.get('has_dimensions', False)):
            footer = Text("\n† Indicates items with dimensional breakdowns available",
                          style="dim italic")
            return Group(table, footer)

        return table

    def __repr__(self):
        return repr_rich(self.__rich__())

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
        for index, statement_name in enumerate(self.xbrl_data.statements_dict.keys()):
            table.add_row(str(index), Statements.colorize_name(statement_name))
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


class XBRLData(BaseModel):
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
    instance: XBRLInstance
    presentation: XBRLPresentation
    labels: Dict
    calculations: Optional[CalculationLinkbase] = None
    statements_dict: Dict[str, StatementDefinition] = Field(default_factory=dict)
    label_to_concept_map: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

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
            return cls.parse(instance_xml=instance_xml, presentation_xml=presentation_xml, labels=labels,
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

    def get_durations(self, statement_name):
        ...

    def get_statement(self,
                      statement_name: str,
                      include_format: bool = True,
                      include_concept: bool = True,
                      empty_threshold: float = 0.6,
                      display_name: str = None,
                      duration: str = None) -> Optional[Statement]:
        """
        Get a financial statement as a pandas DataFrame, with formatting and filtering applied.

        This method retrieves a financial statement, formats it into a DataFrame, applies
        various data cleaning and formatting operations, and returns the result.

        Args:
            statement_name (str): The name of the financial statement to retrieve.
            include_format (bool): Whether to include additional formatting information in the DataFrame.
            include_concept (bool): Whether to include the concept name in the DataFrame.
            empty_threshold (float): The threshold for dropping columns that are mostly empty.
            display_name (str): The display name for the financial statement.
            duration (str): The duration of the financial statement (either '3 months' or '6 months').

        Returns:
            Optional[pd.DataFrame]: A formatted DataFrame representing the financial statement,
                                    or None if the statement is not found.
        """
        statement_definition = self.get_statement_definition(statement_name)

        if not statement_definition:
            return None

        fiscal_period_focus = self.instance.get_fiscal_period_focus()
        is_quarterly = fiscal_period_focus in ['Q1', 'Q2', 'Q3', 'Q4']

        format_info = {
            item.concept: {'level': item.level, 'abstract': item.concept.endswith('Abstract'), 'label': item.label}
            for item in statement_definition.line_items
        }

        ordered_items = [item.concept for item in statement_definition.line_items]

        def get_format_info(item: LineItem, prev_item: Optional[LineItem], next_item: Optional[LineItem]) -> dict:
            """Generate enhanced formatting information for a line item"""
            is_abstract = item.concept.endswith('Abstract')
            is_total = 'Total' in item.label

            # Determine node type
            if is_abstract:
                node_type = 'Header'
            elif is_total:
                node_type = 'Total'
            elif item.level > 0:
                node_type = 'Detail'
            else:
                node_type = 'MainItem'

            # Determine if this ends a section
            ends_section = (
                    is_total or
                    (next_item and next_item.level < item.level) or
                    (next_item and next_item.concept.endswith('Abstract'))
                    or False
            )

            # Check for dimensional data
            has_dimensions = False
            for period_values in item.values.values():
                for dim_key, _ in period_values.items():
                    if dim_key:  # If there are any non-empty dimension tuples
                        has_dimensions = True
                        break
                if has_dimensions:
                    break

            return {
                'level': item.level,
                'abstract': is_abstract,
                'node_type': node_type,
                'section_end': ends_section,
                'has_dimensions': has_dimensions,
                'units': None if is_abstract else '',
                'decimals': None if is_abstract else ''
            }

        data = []
        line_items = statement_definition.line_items
        for i, item in enumerate(line_items):
            prev_item = line_items[i - 1] if i > 0 else None
            next_item = line_items[i + 1] if i < len(line_items) - 1 else None
            row = {'concept': item.concept, 'label': item.label}
            if include_format:
                row.update(get_format_info(item, prev_item, next_item))

            if not item.concept.endswith('Abstract'):
                for period, period_facts in item.values.items():
                    if () in period_facts:
                        default_fact = period_facts[()]

                        end_date = period.split(' to ')[-1]
                        year = end_date.split('-')[0]
                        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

                        period_label = end_date_obj.strftime("%b %d, %Y") if is_quarterly else year

                        current_value = default_fact['value']
                        current_duration = default_fact['duration']

                        include_period = True
                        if is_quarterly:
                            if duration:
                                if current_duration != duration:
                                    include_period = False
                            else:
                                # Prefer 3 months if the duration is not specified
                                if '3 months' in statement_definition.durations:
                                    include_period = current_duration == '3 months'

                        if include_period:
                            row[period_label] = current_value
                            if include_format:
                                row['units'] = default_fact['units']
                                row['decimals'] = default_fact['decimals']

            data.append(row)

        df = pd.DataFrame(data).convert_dtypes(dtype_backend="pyarrow").fillna(pd.NA)

        # Use both concept and label for grouping to preserve uniqueness
        df = df.groupby(['concept', 'label'], as_index=False).agg(
            lambda x: x.dropna().iloc[0] if len(x.dropna()) > 0 else None)

        # Set both concept and label as index
        df = df.set_index(['concept', 'label'])

        # Identify the columns
        period_columns = [col for col in df.columns if col not in
                          ['concept', 'level', 'abstract', 'node_type', 'section_end',
                           'has_dimensions', 'calculation', 'units', 'decimals']]

        period_columns = sorted(period_columns,
                                key=lambda x: (x.split()[-1], x.split()[0] if len(x.split()) > 1 else ''), reverse=True)

        format_columns = []
        if include_format:
            format_columns.extend(['level', 'abstract', 'node_type', 'section_end',
                                   'has_dimensions', 'units', 'decimals'])
        # Reorder the columns
        ordered_cols = period_columns + format_columns
        df = df[ordered_cols]

        if include_format:
            # Convert level to integer and replace NaN with empty string
            # df['level'] = pd.to_numeric(df['level'], errors='coerce').fillna(0).astype(int)

            # Ensure format columns have empty strings instead of NaN
            for col in ['units', 'decimals']:
                replace_all_na_with_empty(df[col])

        # Drop columns that are mostly empty
        empty_counts = ((df.isna()) | (df == '')).sum() / len(df)
        columns_to_keep = empty_counts[empty_counts < empty_threshold].index
        df = df[columns_to_keep]

        # Ensure the original order is preserved
        # Create a MultiIndex for reindexing
        reindex_tuples = [(concept, format_info[concept]['label']) for concept in ordered_items]
        new_index = pd.MultiIndex.from_tuples(reindex_tuples, names=['concept', 'label'])

        # Reindex the DataFrame
        df = df.reindex(new_index).fillna('')

        # Flatten the column index if it's multi-level
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [f"{col[0]}_{col[1]}" if isinstance(col, tuple) else col for col in df.columns]

        # Create and return Statements object
        df_reset = df.reset_index().set_index('label')

        columns_to_include = [col for col
                              in df_reset.columns if
                              col not in ['concept', 'level', 'abstract', 'units', 'decimals']]

        if include_concept:
            columns_to_include.append('concept')

        if include_format:
            columns_to_include.extend([col for col in df_reset.columns
                                       if col in ['level', 'abstract', 'units', 'decimals']
                                       ])

        df_reset = df_reset[columns_to_include]

        return Statement(
            df=df_reset,
            name=statement_name,
            display_name=display_name,
            definition=statement_definition,
            entity=self.instance.get_entity_name()
        )

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

    def __rich__(self):
        group = Group(
            self.instance,
            self.statements,
        )
        panel = Panel(group, title=Text.assemble("XBRL Data for ", (f"{self.company}\n", "bold deep_sky_blue3")))
        return panel

    def __repr__(self):
        return repr_rich(self)

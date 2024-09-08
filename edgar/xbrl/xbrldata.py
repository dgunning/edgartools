from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edgar import Filing

import asyncio
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from functools import cached_property
from functools import lru_cache
from typing import Dict, List, Tuple, Union, Any, Optional

import pandas as pd
from pydantic import BaseModel, Field
from rich import box
from rich import print as rprint
from rich.console import Group
from rich.panel import Panel
from rich.table import Table, Column
from rich.text import Text
from rich.tree import Tree

from edgar.richtools import repr_rich, colorize_words
from edgar.attachments import Attachments
from edgar.core import log, split_camel_case, run_async_or_sync
from edgar.httprequests import download_file_async
from edgar.xbrl.calculatons import parse_calculation_linkbase
from edgar.xbrl.concepts import Concept, concept_to_label
from edgar.xbrl.definitions import parse_definition_linkbase
from edgar.xbrl.facts import XBRLInstance
from edgar.xbrl.labels import parse_label_linkbase
from edgar.xbrl.presentation import XBRLPresentation, PresentationElement

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
                return XBRLData.parse(instance_xml, presentation_xml, labels, calculations)

    def get_xbrl_instance(self):
        if self.has_instance_document:
            return XBRLInstance.parse(self._documents['instance'].download())

    def has_all_documents(self):
        return all(doc in self._documents for doc in
                   ['instance', 'schema', 'definition', 'label', 'calculation', 'presentation'])

    async def load(self) -> Tuple[str, str, Dict, Dict]:
        """
        Load the XBRL documents asynchronously and parse them.
        """
        parsers = {
            'definition': parse_definition_linkbase,
            'label': parse_label_linkbase,
            'calculation': parse_calculation_linkbase,
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
                parsed_files.get('calculation', {}))

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


class StatementDefinition(BaseModel):
    # The name of the financial statement (e.g., "Balance Sheet", "Income Statement")
    name: str
    # A list of LineItem objects representing each line in the financial statement
    line_items: List[LineItem] = Field(default_factory=list)

    @property
    def label(self):
        return self.line_items[0].label.replace(' [Abstract]', '')

    @property
    def empty(self):
        return not self.line_items

    @classmethod
    def create(cls, name: str, presentation_element: PresentationElement, labels: Dict, calculations: Dict,
               instance: XBRLInstance, preferred_label: str = None) -> 'StatementDefinition':
        # Factory method to create a StatementDefinition instance
        statement = cls(name=name)
        # Build the line items for the statement
        statement.build_line_items(presentation_element, labels, calculations, instance, preferred_label)
        return statement

    def build_line_items(self, presentation_element: PresentationElement, labels: Dict, calculations: Dict,
                         instance: XBRLInstance, preferred_label: str = None):
        seen_sections = defaultdict(int)
        seen_concepts = set()
        self.line_items = []

        def process_element(element: PresentationElement, level: int, is_root: bool = False):
            concept = element.href.split('#')[-1]
            label = self.get_label(concept, labels, element.preferred_label or preferred_label)

            # Check if this is a section we've already seen
            if seen_sections[label] > 0 and element.children:
                # If it's a repeated section with children, skip this branch
                return

            # If it's at root level and we've seen this concept before, skip it
            if is_root and concept in seen_concepts:
                return

            seen_sections[label] += 1
            seen_concepts.add(concept)

            values = self.get_fact_values(concept, instance)
            self.line_items.append(LineItem(
                concept=concept,
                label=label,
                values=values,
                level=level
            ))

            for child in sorted(element.children, key=lambda x: x.order):
                process_element(child, level + 1)

        # Process root level elements
        for child in sorted(presentation_element.children, key=lambda x: x.order):
            process_element(child, 0, is_root=True)

        # Optionally, remove single-occurrence items from seen_sections
        seen_sections = {k: v for k, v in seen_sections.items() if v > 1}

        # You might want to log or return seen_sections for debugging
        return seen_sections

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
    @lru_cache(maxsize=1000)
    def get_fact_values(concept: str, instance: XBRLInstance) -> Dict[str, Any]:
        facts = instance.query_facts(concept=concept)
        values = {}
        for _, fact in facts.iterrows():
            if fact['period_type'] == 'instant':
                period = fact['end_date']
            else:
                period = f"{fact['start_date']} to {fact['end_date']}"

            # Create a unique key that includes the period and dimensions
            key = (period, tuple(sorted(fact['dimensions'])))

            # If this period doesn't exist in values, or if it does but the current fact has no dimensions (default)
            if period not in values or not fact['dimensions']:
                values[period] = {
                    'value': fact['value'],
                    'units': fact['units'],
                    'decimals': fact['decimals'],
                    'dimensions': fact['dimensions'],
                    'duration': fact['duration']  # Add the duration here
                }

            # Store all dimensional values in a separate dictionary
            if 'dimensional_values' not in values[period]:
                values[period]['dimensional_values'] = {}
            values[period]['dimensional_values'][key] = {
                'value': fact['value'],
                'units': fact['units'],
                'decimals': fact['decimals'],
                'dimensions': fact['dimensions'],
                'duration': fact['duration']  # Add the duration here as well
            }

        return values

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
    if not s or pd.isna(s):
        return False
    if s[0] in ('-', '+'):
        s = s[1:]
    if '.' in s:
        if not s.replace('.', '').isdigit():
            return False
        integer_part, decimal_part = s.split('.')
        return decimal_part == '' or decimal_part.strip('0') == ''
    return s.isdigit()


def format_xbrl_value(value: Union[str, float], decimals: str, unit_divisor: int = 1,
                      format_str: str = '{:>15,.0f}') -> str:
    if is_integer(value):
        value = float(value)
        if decimals != 'INF':
            try:
                decimal_int = int(decimals)
                if decimal_int < 0:
                    value /= unit_divisor
            except ValueError:
                pass
        if decimals == 'INF':
            return f"{value:>15}"
        else:
            return format_str.format(value)
    else:
        return f"{value:>15}"


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
    format_columns = ['level', 'abstract', 'units', 'decimals']
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
                 display_name: str = None,
                 label: str = None):
        self.name = name
        self.label = label or name
        self.display_name = display_name or self.label
        self.entity = entity
        self.data = df
        self.include_format = 'level' in df.columns
        self.include_concept = 'concept' in df.index.names

    @property
    def periods(self):
        return [col for col in self.data.columns if col not in self.meta_columns]

    @property
    def labels(self):
        return self.data.index.tolist()

    @property
    def concepts(self):
        return self.data.concept.tolist()

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
            results = self.data.query(f"index == '{label}'")
        elif namespace:
            results = self.data.query(f"concept == '{namespace}_{concept}'")
        else:
            # Look in "dei" and "us-gaap" namespaces
            for concept_name in [concept, concept.replace(':', '_'), f'dei_{concept}', f'us-gaap_{concept}']:
                results = self.data.query(f"concept == '{concept_name}'")
                if len(results) > 0:
                    break

        if len(results) == 0:
            return None

        results = results.drop_duplicates()
        if len(results) == 1:
            fact = Concept(
                name=results.concept.iloc[0],
                unit=results.units.iloc[0] if 'units' in results else None,
                label=results.index[0],
                decimals=results.decimals.iloc[0] if 'decimals' in results else None,
                value={col: results[col].iloc[0] for col in self.periods}
            )
            return fact

    def get_dataframe(self,
                      include_format: bool = False,
                      include_concept: bool = False):
        """
        Get the statement data as a DataFrame
        :param include_format: Include format columns (level, abstract, units, decimals)
        :param include_concept: Include the concept column
        :return: DataFrame
        """
        columns = [col for col in self.data.columns if col not in self.meta_columns]
        if include_concept:
            columns.append('concept')
        if include_format:
            columns.extend(self.format_columns)
        # Filter again to make sure the columns exist
        columns = [col for col in columns if col in self.data.columns]
        return self.data[columns].copy()

    def to_dataframe(self,
                     include_format: bool = False,
                     include_concept: bool = False):
        """
        Get the statement data as a DataFrame
        :param include_format: Include format columns (level, abstract, units, decimals)
        :param include_concept: Include the concept column
        :return: DataFrame
        """
        return self.get_dataframe(include_format, include_concept)

    def to_excel(self,
                 filename: str = None,
                 excel_writer: pd.ExcelWriter = None,
                 include_format: bool = False,
                 include_concept: bool = True):
        """
        Save the statement data to an Excel file
        :param filename: Output filename
        :param excel_writer: An existing ExcelWriter object
        :param include_format: Include format columns (level, abstract, units, decimals)
        :param include_concept: Include the concept column
        """
        df = self.get_dataframe(include_format=include_format, include_concept=include_concept)
        if excel_writer:
            df.to_excel(excel_writer, index=False, sheet_name=self.name[:31])
        else:
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name=self.name[:31])

    @lru_cache(maxsize=1)
    def get_unit_divisor(self):
        return get_unit_divisor(self.data, "decimals")

    def get_primary_units(self):
        unit_divisor = get_unit_divisor(self.data, )
        return get_primary_units(unit_divisor)

    def __rich__(self):
        cols = [col for col in self.data.columns if col not in self.meta_columns]
        columns = [Column('')] + [Column(col) for col in cols]

        table = Table(*columns,
                      title=Text.assemble(*[(f"{self.entity}\n", "bold red1"),
                                            (self.display_name, "bold")]),
                      box=box.SIMPLE)
        # What is the unit divisor for the values
        # unit_divisor = self.get_unit_divisor()
        for index, row in enumerate(self.data.itertuples()):

            # Detect the end of a section
            end_section = (index == len(self.data) - 1  # End of data
                           or  # Next line is abstract
                           (index < len(self.data) - 1 and self.data.iloc[index + 1].abstract))
            # Check if this is a total line
            is_total = row.Index.startswith('Total') and end_section

            row_style = "bold" if is_total else ""

            # Set the label style
            if row.abstract:
                label_style = "bold deep_sky_blue3"
            elif is_total:
                label_style = "bold"
            else:
                label_style = ""
            label = Text(format_label(row.Index, row.level), style=label_style)
            if 'decimals' in self.data:
                # For now don't use the unit divisor until we figure out the logic
                values = [label] + [Text.assemble(*[(format_xbrl_value(value=row[colindex + 1],
                                                                       decimals=row.decimals), row_style)])
                                    for colindex, col in enumerate(cols)]
            else:
                values = [label] + [Text.assemble(*[(row[colindex + 1], row_style)])
                                    for colindex, col in enumerate(cols)]

            table.add_row(*values, end_section=is_total)

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
    calculations: Dict
    statements_dict: Dict[str, StatementDefinition] = Field(default_factory=dict)
    label_to_concept_map: Dict[str, str] = Field(default_factory=dict)

    def _build_label_to_concept_map(self):
        for concept, label_dict in self.labels.items():
            for label_type, label in label_dict.items():
                self.label_to_concept_map[label.lower()] = concept

    @classmethod
    def parse(cls, instance_xml: str, presentation_xml: str, labels: Dict, calculations: Dict) -> 'XBRLData':
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
        parser = cls(
            instance=instance,
            presentation=presentation,
            labels=labels,
            calculations=calculations
        )
        parser._build_label_to_concept_map()
        parser.parse_financial_statements()
        return parser

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
            return cls.parse(instance_xml, presentation_xml, labels, calculations)

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
                statement_name,
                root_element,
                self.labels,
                self.calculations.get(role, {}),
                self.instance,
                preferred_label=root_element.preferred_label
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

            # Get fiscal period focus
        fiscal_period_focus = self.instance.get_fiscal_period_focus()
        is_quarterly = fiscal_period_focus in ['Q1', 'Q2', 'Q3', 'Q4']

        # Create format_info dictionary
        format_info = {
            item.concept: {'level': item.level, 'abstract': item.concept.endswith('Abstract'), 'label': item.label}
            for item in statement_definition.line_items
        }

        # Use the order of line_items as they appear in the statement
        ordered_items = [item.concept for item in statement_definition.line_items]

        # Create DataFrame with preserved order and abstract concepts
        data = []
        for item in statement_definition.line_items:
            row = {'concept': item.concept, 'label': item.label}
            if include_format:
                row['level'] = format_info[item.concept]['level']
                row['abstract'] = format_info[item.concept]['abstract']
                row['units'] = None if row['abstract'] else ''
                row['decimals'] = None if row['abstract'] else ''
            if not format_info[item.concept]['abstract']:
                period_values = {}
                for period, value_info in item.values.items():
                    end_date = period.split(' to ')[-1]
                    year = end_date.split('-')[0]
                    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

                    if is_quarterly:
                        period_label = end_date_obj.strftime("%b %d, %Y")
                    else:
                        period_label = year

                    current_value = self.get_correct_value(value_info)
                    has_dimensions = bool(value_info.get('dimensions', {}))
                    current_duration = value_info.get('duration', '')

                    # Check if this period should be included based on duration
                    include_period = (
                            not is_quarterly or
                            duration is None or
                            current_duration == duration
                    )

                    if include_period:
                        if period_label not in period_values or (
                                not has_dimensions and period_values[period_label]['has_dimensions']):
                            period_values[period_label] = {
                                'value': current_value,
                                'has_dimensions': has_dimensions,
                                'units': value_info.get('units', ''),
                                'decimals': value_info.get('decimals', ''),
                                'duration': current_duration
                            }

                # After processing all periods, add the selected values to the row
                for period_label, period_data in period_values.items():
                    row[period_label] = period_data['value']
                    if include_format:
                        row['units'] = period_data['units']
                        row['decimals'] = period_data['decimals']

            data.append(row)

        df = pd.DataFrame(data)

        if os.getenv('EDGAR_USE_PYARROW_BACKEND'):
            df = pd.DataFrame(data).convert_dtypes(dtype_backend="pyarrow")

        # Use both concept and label for grouping to preserve uniqueness
        df = df.groupby(['concept', 'label'], as_index=False).agg(
            lambda x: x.dropna().iloc[0] if len(x.dropna()) > 0 else None)

        # Set both concept and label as index
        df = df.set_index(['concept', 'label'])

        # Identify the columns
        period_columns = [col for col in df.columns if col not in ['level', 'abstract', 'units', 'decimals']]
        period_columns = sorted(period_columns,
                                key=lambda x: (x.split()[-1], x.split()[0] if len(x.split()) > 1 else ''), reverse=True)

        format_columns = []
        if include_format:
            format_columns.extend(['level', 'abstract', 'units', 'decimals'])

        # Reorder the columns
        df = df[period_columns + format_columns]

        if include_format:
            # Convert level to integer and replace NaN with empty string
            df['level'] = pd.to_numeric(df['level'], errors='coerce').fillna(0).astype(int)

            # Ensure format columns have empty strings instead of NaN
            for col in ['abstract', 'units', 'decimals']:
                df[col] = df[col].fillna('')

        df = df.fillna('')

        # Drop columns that are mostly empty
        empty_counts = (df == '').sum() / len(df)
        columns_to_keep = empty_counts[empty_counts < empty_threshold].index
        df = df[columns_to_keep]

        # Fill NaN with empty string for display purposes
        df = df.fillna('')

        # Ensure the original order is preserved
        # Create a MultiIndex for reindexing
        reindex_tuples = [(concept, format_info[concept]['label']) for concept in ordered_items]
        new_index = pd.MultiIndex.from_tuples(reindex_tuples, names=['concept', 'label'])

        # Reindex the DataFrame
        df = df.reindex(new_index)

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

        return Statement(df=df_reset,
                         name=statement_name,
                         display_name=display_name,
                         label=statement_definition.label,
                         entity=self.instance.get_entity_name())

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

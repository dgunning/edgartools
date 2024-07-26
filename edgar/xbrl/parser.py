import asyncio
import os
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict, defaultdict
from functools import cached_property
from typing import Dict, List, Tuple, Union, Any, Optional
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from rich import box
from rich import print as rprint
from rich.table import Table, Column
from rich.text import Text
from rich.tree import Tree

from edgar import Filing
from edgar._rich import repr_rich, colorize_words
from edgar.attachments import Attachment
from edgar.attachments import Attachments
from edgar.httprequests import download_file_async
from edgar.xbrl.concepts import PresentationElement, Concept
from edgar.xbrl.facts import XBRLInstance
from edgar.xbrl.labels import parse_labels
from edgar.core import log
__all__ = ['XBRLPresentation', 'XbrlDocuments', 'XBRLInstance', 'LineItem', 'StatementDefinition', 'XBRLData',
           'Statements', 'StatementData']

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


class FinancialStatementMapper:
    STANDARD_STATEMENTS = {
        'BALANCE_SHEET': [
            'CONSOLIDATEDBALANCESHEETS',
            'CONSOLIDATEDBALANCESHEET',
            'COMPREHENSIVEBALANCESHEETS',
            'COMPREHENSIVEBALANCESHEET',
            'BALANCESHEET',
            'BALANCESHEETS',
            'STATEMENTOFFINANCIALPOSITION',
            'STATEMENTSOFFINANCIALPOSITION',
            'CONSOLIDATEDSTATEMENTOFFINANCIALPOSITION',
            'CONSOLIDATEDSTATEMENTSOFFINANCIALPOSITION'
        ],
        'INCOME_STATEMENT': [
            'CONSOLIDATEDSTATEMENTSOFOPERATIONS',
            'CONSOLIDATEDSTATEMENTOFOPERATIONS',
            'STATEMENTSOFOPERATIONS',
            'STATEMENTOFOPERATIONS',
            'INCOMESTATEMENT',
            'INCOMESTATEMENTS',
            'CONSOLIDATEDINCOMESTATEMENT',
            'CONSOLIDATEDINCOMESTATEMENTS',
            'STATEMENTSOFINCOME',
            'STATEMENTOFINCOME',
            'CONSOLIDATEDSTATEMENTSOFINCOME',
            'CONSOLIDATEDSTATEMENTOFINCOME',
            'CONSOLIDATEDSTATEMENTSOFINCOMELOSS',
            'CONSOLIDATEDSTATEMENTOFINCOMELOSS',
            'STATEMENTSOFEARNINGS',
            'STATEMENTOFEARNINGS',
            'CONSOLIDATEDSTATEMENTSOFEARNINGS',
            'CONSOLIDATEDSTATEMENTOFEARNINGS'
        ],
        'CASH_FLOW': [
            'CONSOLIDATEDSTATEMENTSOFCASHFLOWS',
            'CONSOLIDATEDSTATEMENTOFCASHFLOWS',
            'STATEMENTOFCASHFLOWS',
            'STATEMENTSOFCASHFLOWS',
            'CASHFLOWSTATEMENT',
            'CASHFLOWSTATEMENTS'
        ],
        'EQUITY': [
            'CONSOLIDATEDSTATEMENTSOFSHAREHOLDERSEQUITY',
            'CONSOLIDATEDSTATEMENTOFSHAREHOLDERSEQUITY',
            'CONSOLIDATEDSTATEMENTSOFSTOCKHOLDERSEQUITY',
            'CONSOLIDATEDSTATEMENTOFSTOCKHOLDERSEQUITY',
            'STATEMENTOFSHAREHOLDERSEQUITY',
            'STATEMENTOFSTOCKHOLDERSEQUITY',
            'STATEMENTSOFCHANGESINEQUITY',
            'STATEMENTOFCHANGESINEQUITY',
            'CONSOLIDATEDSTATEMENTSOFCHANGESINEQUITY',
            'CONSOLIDATEDSTATEMENTOFCHANGESINEQUITY',
            'STATEMENTOFEQUITY',
            'STATEMENTSOFEQUITY'
        ],
        'COMPREHENSIVE_INCOME': [
            'CONSOLIDATEDSTATEMENTSOFCOMPREHENSIVEINCOME',
            'CONSOLIDATEDSTATEMENTOFCOMPREHENSIVEINCOME',
            'STATEMENTOFCOMPREHENSIVEINCOME',
            'STATEMENTSOFCOMPREHENSIVEINCOME',
            'COMPREHENSIVEINCOMESTATEMENT',
            'COMPREHENSIVEINCOMESTATEMENTS'
        ],
        'COVER_PAGE': [
            'COVERPAGE',
            'COVER',
            'DOCUMENTANDENTITYINFORMATION',
            'ENTITYINFORMATION'
        ]
    }

    @classmethod
    def get_standard_name(cls, role_name: str) -> Optional[str]:
        # Extract the last part of the URI and remove any file extensions
        role_name = role_name.split('/')[-1].split('.')[0]

        # Normalize the role name: remove non-alphanumeric characters and convert to uppercase
        role_name_normalized = ''.join(char.upper() for char in role_name if char.isalnum())

        for standard_name, variations in cls.STANDARD_STATEMENTS.items():
            for variation in variations:
                if variation == role_name_normalized:
                    return standard_name

        return None


class XBRLPresentation(BaseModel):
    # Dictionary to store presentation roles and their corresponding elements
    roles: Dict[str, PresentationElement] = Field(default_factory=dict)
    skipped_roles: List[str] = Field(default_factory=list)
    standard_statement_map: Dict[str, str] = Field(default_factory=dict)
    concept_index: Dict[str, List[str]] = Field(default_factory=lambda: defaultdict(list))

    # Configuration to allow arbitrary types in the model
    model_config = {
        "arbitrary_types_allowed": True
    }

    @classmethod
    def parse(cls, xml_string: str):
        presentation = cls()
        soup = BeautifulSoup(xml_string, 'xml')

        def normalize_concept(concept):
            return re.sub(r'_\d+$', '', concept)

        for plink in soup.find_all('presentationLink'):
            role = plink.get('xlink:role')

            # Parse loc elements
            locs = OrderedDict()
            for loc in plink.find_all('loc'):
                label = loc.get('xlink:label')
                href = loc.get('xlink:href')
                concept = href.split('#')[-1] if href else label
                normalized_concept = normalize_concept(concept)
                locs[label] = PresentationElement(label=label, href=href, order=0, concept=normalized_concept)

            # Parse presentationArc elements
            arcs = []
            for arc in plink.find_all('presentationArc'):
                parent_label = arc.get('xlink:from')
                child_label = arc.get('xlink:to')
                order = float(arc.get('order', '0'))
                arcs.append((parent_label, child_label, order))

            # If no loc elements were found, try to parse using the older format
            if not locs:
                for arc in arcs:
                    parent_label, child_label, order = arc
                    if parent_label not in locs:
                        normalized_concept = normalize_concept(parent_label)
                        locs[parent_label] = PresentationElement(label=parent_label, href='', order=0,
                                                                 concept=normalized_concept)
                    if child_label not in locs:
                        normalized_concept = normalize_concept(child_label)
                        locs[child_label] = PresentationElement(label=child_label, href='', order=0,
                                                                concept=normalized_concept)

            # Build the hierarchy
            for parent_label, child_label, order in arcs:
                if parent_label in locs and child_label in locs:
                    parent = locs[parent_label]
                    child = locs[child_label]
                    child.order = order
                    child.level = parent.level + 1

                    existing_child = next((c for c in parent.children if
                                           normalize_concept(c.concept) == normalize_concept(child.concept)), None)
                    if existing_child:
                        existing_child.children.extend(child.children)
                        if len(child.label) > len(existing_child.label):
                            existing_child.label = child.label
                        if len(child.concept) < len(existing_child.concept):
                            existing_child.concept = child.concept
                    else:
                        parent.children.append(child)

            # Add the top-level elements to the role only if there are children
            role_children = [loc for loc in locs.values() if not any(arc[1] == loc.label for arc in arcs)]
            if role_children:
                presentation.roles[role] = PresentationElement(label=role, href='', order=0,
                                                               concept=normalize_concept(role))
                presentation.roles[role].children = role_children

        # Build the statement map and concept index
        presentation._build_statement_map()
        presentation._build_concept_index()

        return presentation

    def _build_statement_map(self):
        for role, element in self.roles.items():
            standard_name = FinancialStatementMapper.get_standard_name(role)
            if standard_name:
                self.standard_statement_map[standard_name] = role

    def _build_concept_index(self):
        for role, element in self.roles.items():
            self._index_concepts(element, role)

    def _index_concepts(self, element: PresentationElement, role: str):
        self.concept_index[element.concept].append(role)
        for child in element.children:
            self._index_concepts(child, role)

    def get_role_by_standard_name(self, standard_name: str) -> Optional[str]:
        return self.standard_statement_map.get(standard_name)

    def get_roles_containing_concept(self, concept: str) -> List[str]:
        if '_' not in concept:
            namespaces = ['us-gaap', 'ifrs-full', 'dei']  # Add other common namespaces as needed
            for ns in namespaces:
                namespaced_concept = f"{ns}_{concept}"
                if namespaced_concept in self.concept_index:
                    return self.concept_index[namespaced_concept]

            # If the concept is already namespaced or not found with common namespaces
        return self.concept_index.get(concept, [])


    def list_roles(self) -> List[str]:
        """ List all available roles in the presentation linkbase. """
        return list(self.roles.keys())

    def get_skipped_roles(self):
        return self.skipped_roles

    def get_structure(self, role: str, detailed: bool = False) -> Optional[Tree]:
        """
        Get the presentation structure for a specific role.
        """
        if role:
            if role in self.roles:
                tree = Tree(f"[bold blue]{role}[/bold blue]")
                self._build_rich_tree(self.roles[role], tree, detailed)
                return tree

    def __rich__(self):
        main_tree = Tree("[bold green]XBRL Presentation Structure[/bold green]")
        for role, element in self.roles.items():
            role_tree = main_tree.add(f"[bold blue]{role}[/bold blue]")
            self._build_rich_tree(element, role_tree, detailed=False)
        return main_tree

    def __repr__(self):
        return repr_rich(self)

    def print_structure(self, role: Optional[str] = None, detailed: bool = False):
        # Print the presentation structure using Rich library's Tree
        if role:
            if role in self.roles:
                tree = self.get_structure(role, detailed)
                rprint(tree)
            else:
                print(f"Role '{role}' not found in the presentation linkbase.")
        else:
            rprint(self.__rich__())

    def _build_rich_tree(self, element: PresentationElement, tree: Tree, detailed: bool):
        # Recursively build the Rich Tree structure for visualization
        for child in sorted(element.children, key=lambda x: x.order):
            if detailed:
                # Detailed view: show full label and concept
                node_text = f"[yellow]{child.label}[/yellow] ([cyan]{child.href.split('#')[-1]}[/cyan])"
            else:
                # Simplified view: show only namespace and first part of the name
                concept = child.href.split('#')[-1]
                namespace, name = concept.split('_', 1)
                simplified_name = f"{namespace} {name.split('_')[0]}"
                node_text = f"[cyan]{simplified_name}[/cyan]"

            child_tree = tree.add(node_text)
            self._build_rich_tree(child, child_tree, detailed)


class XbrlDocuments:
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

    def has_all_documents(self):
        return all(doc in self._documents for doc in
                   ['instance', 'schema', 'definition', 'label', 'calculation', 'presentation'])

    async def load(self) -> Tuple[str, str, Dict, Dict]:
        """
        Load the XBRL documents asynchronously and parse them.
        """
        parsers = {
            'definition': parse_definitions,
            'label': parse_labels,
            'calculation': parse_calculation,
            'presentation': lambda x: x,
            'instance': lambda x: x,
            'schema': lambda x: x
        }
        parsed_files = {}

        # First, download and parse the instance and schema files
        for doc_type in ['instance', 'schema']:
            attachment = self.get(doc_type)
            if attachment:
                content = await download_file_async(attachment.url)
                parsed_files[doc_type] = parsers[doc_type](content)

        # If we don't have all documents, extract from schema
        if not self.has_all_documents() and 'schema' in parsed_files:
            embedded_linkbases = self.extract_embedded_linkbases(parsed_files['schema'])

            for linkbase_type, content in embedded_linkbases['linkbases'].items():
                if linkbase_type not in parsed_files:
                    parsed_files[linkbase_type] = parsers[linkbase_type](content)

        # Download and parse any remaining standalone linkbase files
        tasks = []
        for doc_type in ['definition', 'label', 'calculation', 'presentation']:
            if doc_type not in parsed_files:
                attachment = self.get(doc_type)
                if attachment:
                    tasks.append(self.download_and_parse(doc_type, parsers[doc_type]))

        if tasks:
            results = await asyncio.gather(*tasks)
            for result in results:
                parsed_files.update(result)

        # Return the required files
        return (parsed_files.get('instance', ''),
                parsed_files.get('presentation', ''),
                parsed_files.get('label', {}),
                parsed_files.get('calculation', {}))

    async def download_and_parse(self, doc_type: str, parser):
        attachment = self.get(doc_type)
        if attachment:
            content = await download_file_async(attachment.url)
            return {doc_type: parser(content)}
        return {}

    def extract_embedded_linkbases(self, schema_content: str) -> Dict[str, Dict[str, str]]:
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
               instance: XBRLInstance) -> 'StatementDefinition':
        # Factory method to create a StatementDefinition instance
        statement = cls(name=name)
        # Build the line items for the statement
        statement.build_line_items(presentation_element, labels, calculations, instance)
        return statement

    def build_line_items(self, presentation_element: PresentationElement, labels: Dict, calculations: Dict,
                         instance: XBRLInstance):
        seen_sections = defaultdict(int)
        seen_concepts = set()
        self.line_items = []

        def process_element(element: PresentationElement, level: int, is_root: bool = False):
            concept = element.href.split('#')[-1]
            label = self.get_label(concept, labels)

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
    def get_label(concept: str, labels: Dict) -> str:
        # Get the labels for this concept
        concept_labels = labels.get(concept, {})
        # Try to get the terseLabel first, then label, then fall back to the concept name
        label = (concept_labels.get('totalLabel')
                 or concept_labels.get('terseLabel')
                 or concept_labels.get('label') or concept)
        return label

    @staticmethod
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
    if not s:
        return False
    if s[0] in ('-', '+'):
        s = s[1:]
    if '.' in s:
        if not s.replace('.', '').isdigit():
            return False
        integer_part, decimal_part = s.split('.')
        return decimal_part == '' or decimal_part.strip('0') == ''
    return s.isdigit()


def format_currency(value: Union[str, float], format_str: str = '{:>15,.0f}') -> str:
    if is_integer(value):
        value = float(value)
        return format_str.format(value)
    else:
        return f"{value:>15}"


def format_label(label, level):
    return f"{' ' * level}{label}"


def split_camel_case(item):
    # Check if the string is all uppercase
    if item.isupper():
        return item
    else:
        # Split at the boundary between uppercase and camelCase
        return ' '.join(re.findall(r'[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z]*', item))


class StatementData:
    meta_columns = ['level', 'abstract', 'concept', 'units', 'decimals']

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
        elif len(results) > 1:
            # Get the first row
            results = results.iloc[0]

        # Now convert to a fact and return
        fact = Concept(
            name=results.concept.iloc[0],
            unit=results.units.iloc[0] if 'units' in results else None,
            label=results.index[0],
            decimals=results.decimals.iloc[0] if 'decimals' in results else None,
            value={col: results[col].iloc[0] for col in self.periods}
        )
        return fact

    def __str__(self):
        format_str = " with format" if self.include_format else ""
        return f"{self.name}({len(self.data)} concepts{format_str})"

    def __rich__(self):
        cols = [col for col in self.data.columns if col not in self.meta_columns]
        columns = [Column('')] + [Column(col) for col in cols]

        table = Table(*columns,
                      title=Text.assemble(*[(f"{self.entity}\n", "bold red1"),
                                            (self.display_name, "bold")]),
                      box=box.SIMPLE)
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

            values = [label] + [Text.assemble(*[(format_currency(row[index + 1]), row_style)])
                                for index, col in enumerate(cols)]

            table.add_row(*values, end_section=is_total)

        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


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
        table = Table("", "Statement", box=box.SIMPLE)
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
        assert filing.form in ['10-K', '10-Q', '10-K/A', '10-Q/A'], "Filing must be a 10-K or 10-Q"
        xbrl_documents = XbrlDocuments(filing.attachments)
        if xbrl_documents.empty:
            log.warn(f"No XBRL documents found in the filing. {filing}")
            return None

        parsed_documents = await xbrl_documents.load()
        if parsed_documents:
            instance_xml, presentation_xml, labels, calculations = parsed_documents
            return cls.parse(instance_xml, presentation_xml, labels, calculations)

    @classmethod
    def extract(cls, filing: Filing):
        """
        Extract XBRL data from a filing object.
        """
        return asyncio.run(cls.from_filing(filing))

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
                self.instance
            )

    @cached_property
    def statements(self):
        return Statements(self)

    def list_statements(self) -> List[str]:
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

    def get_statement(self,
                      statement_name: str,
                      include_format: bool = True,
                      include_concept: bool = True,
                      empty_threshold: float = 0.6,
                      display_name: str = None,
                      duration: str = None) -> Optional[StatementData]:
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
            item.label: {'level': item.level, 'abstract': item.concept.endswith('Abstract'), 'concept': item.concept}
            for item in statement_definition.line_items}

        # Use the order of line_items as they appear in the statement
        ordered_items = [item.label for item in statement_definition.line_items]

        # Create DataFrame with preserved order and abstract concepts
        data = []
        for item in statement_definition.line_items:
            row = {'label': item.label}
            if include_format:
                row['level'] = format_info[item.label]['level']
                row['abstract'] = format_info[item.label]['abstract']
                row['units'] = None if row['abstract'] else ''
                row['decimals'] = None if row['abstract'] else ''
            if include_concept:
                row['concept'] = format_info[item.label]['concept']
            if not format_info[item.label]['abstract']:
                for period, value_info in item.values.items():
                    end_date = period.split(' to ')[-1]
                    year = end_date.split('-')[0]
                    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

                    if is_quarterly:
                        # Only include periods matching the specified duration for quarterly reports.
                        # The default is 3 months
                        if value_info['duration'] == '6 months':
                            if value_info['duration'] == duration:
                                period_label = end_date_obj.strftime("%b %d, %Y")
                                row[period_label] = value_info['value']
                        else:
                            period_label = end_date_obj.strftime("%b %d, %Y")
                            row[period_label] = value_info['value']
                    else:
                        # For annual reports, include annual periods
                        period_label = year
                        row[period_label] = value_info['value']

                    if include_format:
                        row['units'] = value_info.get('units', '')
                        row['decimals'] = value_info.get('decimals', '')
            data.append(row)

        df = pd.DataFrame(data)

        if os.getenv('EDGAR_USE_PYARROW_BACKEND'):
            df = pd.DataFrame(data).convert_dtypes(dtype_backend="pyarrow")

        # Consolidate duplicate rows while preserving all information
        df = df.groupby('label', as_index=False).agg(lambda x: x.dropna().iloc[0] if len(x.dropna()) > 0 else None)

        df = df.set_index('label')

        # Sort columns by period (descending)
        period_columns = [col for col in df.columns if col not in ['level', 'abstract', 'units', 'decimals', 'concept']]
        period_columns = sorted(period_columns,
                                key=lambda x: (x.split()[-1], x.split()[0] if len(x.split()) > 1 else ''), reverse=True)

        format_columns = []
        if include_concept:
            format_columns.append('concept')
        if include_format:
            format_columns.extend(['level', 'abstract', 'units', 'decimals'])

        df = df[period_columns + format_columns]

        if include_format:
            # Convert level to integer and replace NaN with empty string
            df['level'] = pd.to_numeric(df['level'], errors='coerce').fillna(0).astype(int)

            # Ensure format columns have empty strings instead of NaN
            for col in ['abstract', 'units', 'decimals']:
                df[col] = df[col].fillna('')

        if include_concept:
            df['concept'] = df['concept'].fillna('')

        df = df.fillna('')

        # Drop columns that are mostly empty
        empty_counts = (df == '').sum() / len(df)
        columns_to_keep = empty_counts[empty_counts < empty_threshold].index
        df = df[columns_to_keep]

        # Fill NaN with empty string for display purposes
        df = df.fillna('')

        # Ensure the original order is preserved
        df = df.reindex(ordered_items)

        # Flatten the column index if it's multi-level
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [f"{col[0]}_{col[1]}" if isinstance(col, tuple) else col for col in df.columns]

        # Create and return Statements object
        return StatementData(df=df,
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
        return self.instance.__rich__()

    def __repr__(self):
        return repr_rich(self)


def parse_definitions(xml_string: str) -> Dict[str, List[Tuple[str, str, int]]]:
    """
       Parse an XBRL definition linkbase XML string and extract definition relationships.

       This function takes an XML string representing an XBRL definition linkbase and
       processes it to extract definition relationships between concepts. It organizes
       the relationships by role.

       Parameters:
       xml_string (str): A string containing the XML content of the XBRL definition linkbase.

       Returns:
       Dict[str, List[Tuple[str, str, int]]]: A dictionary where:
           - The key is the role URI of the definition link.
           - The value is a list of tuples, each representing a relationship:
             (from_concept, to_concept, order)
             where:
             - from_concept (str): The concept from which the relationship originates.
             - to_concept (str): The concept to which the relationship points.
             - order (int): The order of the relationship within its parent.

       Example:
       {
           "http://www.company.com/role/BalanceSheet": [
               ("Assets", "CurrentAssets", 1),
               ("Assets", "NonCurrentAssets", 2),
               ("Liabilities", "CurrentLiabilities", 1),
               ("Liabilities", "NonCurrentLiabilities", 2)
           ],
           "http://www.company.com/role/IncomeStatement": [
               ("Revenue", "OperatingRevenue", 1),
               ("Revenue", "NonOperatingRevenue", 2)
           ]
       }

       Note:
       - This function assumes the XML is well-formed and follows the XBRL definition linkbase structure.
       - It uses BeautifulSoup with the 'xml' parser to process the XML.
       - The function extracts concepts from the 'xlink:href' attribute, taking the part after the '#' symbol.
       - Relationships are only included if both the 'from' and 'to' concepts are found in the locator definitions.
       - The 'order' attribute is converted to an integer, defaulting to 0 if not present.
       """
    soup = BeautifulSoup(xml_string, 'xml')
    definitions = {}

    for definition_link in soup.find_all('definitionLink'):
        role = definition_link['xlink:role']
        definitions[role] = []

        locs = {}
        for loc in definition_link.find_all('loc'):
            label = loc['xlink:label']
            href = loc['xlink:href']
            concept = href.split('#')[-1]
            locs[label] = concept

        for arc in definition_link.find_all('definitionArc'):
            from_label = arc['xlink:from']
            to_label = arc['xlink:to']
            # Convert order to float instead of int
            order = float(arc.get('order', '0'))
            # arcrole = arc['xlink:arcrole']

            if from_label in locs and to_label in locs:
                from_concept = locs[from_label]
                to_concept = locs[to_label]
                definitions[role].append((from_concept, to_concept, order))

    return definitions


def parse_calculation(xml_string: str) -> Dict[str, List[Tuple[str, str, float, int]]]:
    """
    This parser does the following:

    It uses BeautifulSoup to parse the XML content.
    It iterates through all calculationLink elements in the file.
    For each calculationLink, it extracts the role and creates a list to store the calculation relationships for that role.
    It first processes all loc elements to create a mapping from labels to concepts.
    Then it processes all calculationArc elements, which define the calculation relationships between concepts.
    For each arc, it extracts the from and to concepts, the weight, and the order, and stores this information in the list for the current role.
    The result is a dictionary where keys are roles and values are lists of tuples. Each tuple contains (from_concept, to_concept, weight, order).

The resulting calculation_data dictionary will have a structure like this:
    {
    "http://www.apple.com/role/CONSOLIDATEDSTATEMENTSOFOPERATIONS": [
        ("us-gaap_OperatingIncomeLoss", "us-gaap_GrossProfit", 1.0, 1),
        ("us-gaap_OperatingIncomeLoss", "us-gaap_OperatingExpenses", -1.0, 2),
        ("us-gaap_OperatingExpenses", "us-gaap_ResearchAndDevelopmentExpense", 1.0, 1),
        ("us-gaap_OperatingExpenses", "us-gaap_SellingGeneralAndAdministrativeExpense", 1.0, 2),
        # ... other relationships ...
    ],
    # ... other roles ...
}
    """
    soup = BeautifulSoup(xml_string, 'xml')
    calculations = {}

    for calculation_link in soup.find_all('calculationLink'):
        role = calculation_link['xlink:role']
        calculations[role] = []

        locs = {}
        for loc in calculation_link.find_all('loc'):
            label = loc['xlink:label']
            href = loc['xlink:href']
            concept = href.split('#')[-1]
            locs[label] = concept

        for arc in calculation_link.find_all('calculationArc'):
            from_label = arc['xlink:from']
            to_label = arc['xlink:to']
            weight = float(arc['weight'])
            # Convert order to float instead of int
            order = float(arc['order'])

            if from_label in locs and to_label in locs:
                from_concept = locs[from_label]
                to_concept = locs[to_label]
                calculations[role].append((from_concept, to_concept, weight, order))

    return calculations


async def download_and_parse(attachment: Attachment, parse_func):
    content: str = await download_file_async(attachment.url)
    return parse_func(content)

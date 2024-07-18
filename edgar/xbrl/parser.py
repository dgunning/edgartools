import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from rich import box
from rich import print as rprint
from rich.table import Table, Column
from rich.tree import Tree

from edgar import Filing
from edgar._rich import repr_rich
from edgar.attachments import Attachment
from edgar.attachments import Attachments
from edgar.httprequests import download_file_async
from edgar.xbrl.concepts import PresentationElement, DEI_CONCEPTS

__all__ = ['XBRLPresentation', 'XbrlDocuments', 'XBRLInstance', 'LineItem', 'FinancialStatement', 'XBRLData']

"""
This implementation includes:

Context and Fact classes to represent XBRL contexts and facts.
XBRLInstance class to parse the instance document, extracting contexts and facts.
FinancialStatement class to represent a single financial statement, organizing facts according to the presentation linkbase.
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


class XBRLPresentation(BaseModel):
    # Dictionary to store presentation roles and their corresponding elements
    roles: Dict[str, PresentationElement] = Field(default_factory=dict)

    # Configuration to allow arbitrary types in the model
    model_config = {
        "arbitrary_types_allowed": True
    }

    @classmethod
    def parse(cls, xml_string: str):
        # Parse the XBRL presentation linkbase XML and create an XBRLPresentation object
        presentation = cls()
        soup = BeautifulSoup(xml_string, 'xml')

        # Parse roleRefs
        for role_ref in soup.find_all('roleRef'):
            role_uri = role_ref.get('roleURI')
            presentation.roles[role_uri] = PresentationElement(label=role_uri, href='', order=0)

        # Parse presentationLinks
        for plink in soup.find_all('presentationLink'):
            role = plink.get('xlink:role')

            # Parse loc elements
            locs = {}
            for loc in plink.find_all('loc'):
                label = loc.get('xlink:label')
                href = loc.get('xlink:href')
                locs[label] = PresentationElement(label=label, href=href, order=0)

            # Parse presentationArc elements to build the hierarchy
            for arc in plink.find_all('presentationArc'):
                parent_label = arc.get('xlink:from')
                child_label = arc.get('xlink:to')
                order = float(arc.get('order', '0'))

                if parent_label in locs and child_label in locs:
                    parent = locs[parent_label]
                    child = locs[child_label]
                    child.order = order
                    child.level = parent.level + 1
                    parent.children.append(child)

            # Add the top-level elements to the role
            if role in presentation.roles:
                presentation.roles[role].children = [loc for loc in locs.values() if loc.label.startswith('loc_')]

        return presentation

    def list_roles(self) -> List[str]:
        """ List all available roles in the presentation linkbase. """
        return list(self.roles.keys())

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
        for attachment in attachments.data_files:
            if attachment.document_type == 'XML':
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

    async def load(self) -> Tuple[str, str, Dict, Dict]:
        """
        Load the XBRL documents asynchronously and parse them.
        """
        tasks = []
        parsers = {
            'definition': parse_definitions,
            'label': parse_labels,
            'calculation': parse_calculation,
            'presentation': lambda x: x,
            'instance': lambda x: x
        }
        parsed_files = {}

        async def download_and_parse(doc_type, parser):
            # Download the file
            attachment = self.get(doc_type)
            if attachment:
                content = await download_file_async(attachment.url)
                parsed_files[doc_type] = parser(content)

        # Create the tasks
        for doc_type, parser in parsers.items():
            attachment = self.get(doc_type)
            if attachment:
                tasks += [download_and_parse(doc_type, parser)]

        # Now we can parse the instance document
        await asyncio.gather(*tasks)
        return (parsed_files['instance'],
                parsed_files['presentation'],
                parsed_files['label'],
                parsed_files['calculation'])

    async def _load_document(self, doc_type: str, attachment: Attachment, parse_func):
        content: Optional[str] = await download_file_async(attachment.url)
        setattr(self, doc_type, parse_func(content))

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


class XBRLInstance(BaseModel):
    # Dictionary to store context information, keyed by context ID
    contexts: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # DataFrame to store all facts from the XBRL instance
    facts: pd.DataFrame = Field(default_factory=lambda: pd.DataFrame(columns=[
        'concept', 'value', 'units', 'decimals', 'start_date', 'end_date',
        'period_type', 'context_id', 'entity_id', 'dimensions'
    ]))

    # Dictionary to store unit information, keyed by unit ID
    units: Dict[str, str] = Field(default_factory=dict)

    # Entity identifier (e.g., CIK for SEC filings)
    entity_id: Optional[str] = None

    # Dictionary to store Document and Entity Information (DEI) facts
    dei_facts: Dict[str, Any] = Field(default_factory=dict)

    # Configuration to allow arbitrary types in the model
    model_config = {
        "arbitrary_types_allowed": True
    }

    def extract_dei_facts(self):
        # Extract Document and Entity Information facts
        for concept in DEI_CONCEPTS:
            facts = self.query_facts(concept=concept)
            if not facts.empty:
                # For simplicity, we're taking the first fact if multiple exist
                fact = facts.iloc[0]
                self.dei_facts[concept] = {
                    'value': fact['value'],
                    'context_id': fact['context_id'],
                    'start_date': fact['start_date'],
                    'end_date': fact['end_date']
                }

    # Getter methods for common DEI facts

    def get_document_type(self):
        return self.dei_facts.get('dei:DocumentType', {}).get('value')

    def get_document_period(self):
        return self.dei_facts.get('dei:DocumentPeriodEndDate', {}).get('value')

    def get_fiscal_year_focus(self):
        return self.dei_facts.get('dei:DocumentFiscalYearFocus', {}).get('value')

    def get_fiscal_period_focus(self):
        return self.dei_facts.get('dei:DocumentFiscalPeriodFocus', {}).get('value')

    def get_entity_name(self):
        return self.dei_facts.get('dei:EntityRegistrantName', {}).get('value')

    @classmethod
    def parse(cls, instance_xml: str):
        # Parse the XBRL instance XML and create an XBRLInstance object
        instance = cls()
        soup = BeautifulSoup(instance_xml, 'xml')

        instance.parse_contexts(soup)
        instance.parse_units(soup)
        instance.parse_entity_identifier(soup)
        instance.parse_facts(soup)
        instance.extract_dei_facts()

        return instance

    def parse_contexts(self, soup: BeautifulSoup):
        # Parse context elements from the XBRL instance
        for context in soup.find_all('context'):
            context_id = context.get('id')
            entity = context.find('entity')
            period = context.find('period')

            self.contexts[context_id] = {
                'entity_id': entity.find('identifier').text if entity else None,
                'start_date': period.find('startDate').text if period.find('startDate') else None,
                'end_date': period.find('endDate').text if period.find('endDate') else period.find(
                    'instant').text if period.find('instant') else None,
                'dimensions': {dim.get('dimension'): dim.text for dim in context.find_all('explicitMember')}
            }

    def parse_units(self, soup: BeautifulSoup):
        # Parse unit elements from the XBRL instance
        for unit in soup.find_all('unit'):
            unit_id = unit.get('id')
            measure = unit.find('measure')
            if measure:
                self.units[unit_id] = measure.text

    def parse_entity_identifier(self, soup: BeautifulSoup):
        # Parse the entity identifier from the XBRL instance
        entity_identifier = soup.find('identifier')
        if entity_identifier:
            self.entity_id = entity_identifier.text

    def parse_facts(self, soup: BeautifulSoup):
        # Parse fact elements from the XBRL instance
        facts_data = []
        root = soup.find("xbrl")
        for fact_id, tag in enumerate(root.find_all(lambda t: t.namespace != "http://www.xbrl.org/"), start=1):
            if not ('contextRef' in tag.attrs or 'unitRef' in tag.attrs):
                continue
            concept = f"{tag.prefix}:{tag.name}"
            value = tag.text
            units = self.units.get(tag.get('unitRef'))
            decimals = tag.get('decimals')
            context_id = tag.get('contextRef')

            if context_id in self.contexts:
                context = self.contexts[context_id]
                start_date = context['start_date']
                end_date = context['end_date']
                period_type = 'instant' if start_date == end_date else 'duration'
                entity_id = context['entity_id']
                dimensions = context['dimensions']
            else:
                start_date = end_date = period_type = entity_id = None
                dimensions = {}

            facts_data.append({
                'concept': concept,
                'value': value,
                'units': units,
                'decimals': decimals,
                'start_date': start_date,
                'end_date': end_date,
                'period_type': period_type,
                'context_id': context_id,
                'entity_id': entity_id,
                'dimensions': dimensions
            })

        self.facts = pd.DataFrame(facts_data, index=pd.RangeIndex(start=1, stop=len(facts_data) + 1, name='fact_id'))

    def query_facts(self, **kwargs):
        # Query facts based on given criteria
        # Replace underscores with colons in the concept name if present
        if 'concept' in kwargs:
            kwargs['concept'] = kwargs['concept'].replace('_', ':')

        query = ' & '.join([f"{k} == '{v}'" for k, v in kwargs.items() if k != 'dimensions'])
        result = self.facts.query(query) if query else self.facts.copy()

        if 'dimensions' in kwargs:
            result = result[
                result['dimensions'].apply(lambda d: all(item in d.items() for item in kwargs['dimensions'].items()))]

        return result

    def __rich__(self):
        table = Table(Column("Company"),
                      Column("Fiscal period"),
                      Column("Period end"),
                      Column("Facts"),
                      Column("Form"),
                      title="XBRL", box=box.SIMPLE)
        table.add_row(self.get_entity_name(),
                      f"{self.get_fiscal_period_focus()} {self.get_fiscal_year_focus()}",
                      self.get_document_period(),
                      f"{len(self.facts):,}",
                      self.get_document_type())
        return table

    def __repr__(self):
        return repr_rich(self)


class LineItem(BaseModel):
    concept: str
    label: str
    values: Dict[str, Any]
    level: int


class FinancialStatement(BaseModel):
    # The name of the financial statement (e.g., "Balance Sheet", "Income Statement")
    name: str
    # A list of LineItem objects representing each line in the financial statement
    line_items: List[LineItem] = Field(default_factory=list)

    @classmethod
    def create(cls, name: str, presentation_element: PresentationElement, labels: Dict, calculations: Dict,
               instance: XBRLInstance) -> 'FinancialStatement':
        # Factory method to create a FinancialStatement instance
        statement = cls(name=name)
        # Build the line items for the statement
        statement.build_line_items(presentation_element, labels, calculations, instance)
        return statement

    def build_line_items(self, presentation_element: PresentationElement, labels: Dict, calculations: Dict,
                         instance: XBRLInstance):
        # Recursive function to process each element in the presentation hierarchy
        def process_element(element: PresentationElement, level: int):
            # Extract the concept name from the href attribute
            concept = element.href.split('#')[-1]
            # Get the label for this concept
            label = self.get_label(concept, labels)
            # Get the fact values for this concept from the instance document
            values = self.get_fact_values(concept, instance)
            # Create a new LineItem and add it to the list
            self.line_items.append(LineItem(
                concept=concept,
                label=label,
                values=values,
                level=level
            ))
            # Process all child elements, incrementing the level
            for child in sorted(element.children, key=lambda x: x.order):
                process_element(child, level + 1)

        # Start processing from the root element's children
        for child in sorted(presentation_element.children, key=lambda x: x.order):
            process_element(child, 0)

    @staticmethod
    def get_label(concept: str, labels: Dict) -> str:
        # Get the labels for this concept
        concept_labels = labels.get(concept, {})
        # Try to get the terseLabel first, then label, then fall back to the concept name
        return concept_labels.get('terseLabel') or concept_labels.get('label') or concept

    @staticmethod
    def get_fact_values(concept: str, instance: XBRLInstance) -> Dict[str, Any]:
        # Query the instance document for facts related to this concept
        facts = instance.query_facts(concept=concept)
        values = {}
        for _, fact in facts.iterrows():
            if fact['period_type'] == 'instant':
                # For instant facts, we only care about the end date
                period = fact['end_date']
            else:
                # For duration facts, we want to show the full period
                start = fact['start_date'] if fact['start_date'] else 'Unknown'
                end = fact['end_date'] if fact['end_date'] else 'Unknown'
                period = f"{start} to {end}"

            # Convert the period to a datetime object for sorting
            if isinstance(period, str) and 'to' in period:
                sort_date = datetime.strptime(period.split(' to ')[1], '%Y-%m-%d')
            else:
                sort_date = datetime.strptime(period, '%Y-%m-%d')

            values[period] = {'value': fact['value'], 'sort_date': sort_date}

        # Sort the values by date in descending order
        return dict(sorted(values.items(), key=lambda x: x[1]['sort_date'], reverse=True))

    def to_dict(self):
        # Convert the FinancialStatement object to a dictionary
        return {
            'name': self.name,
            'line_items': [item.dict() for item in self.line_items]
        }


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
           statements (Dict[str, FinancialStatement]): Dictionary of parsed financial statements.

       Class Methods:
           parse(instance_xml: str, presentation_xml: str, labels: Dict, calculations: Dict) -> 'XBRL':
               Parse XBRL documents from XML strings and create an XBRL instance.

           from_filing(filing: Filing) -> 'XBRL':
               Asynchronously create an XBRL instance from a Filing object.

       Instance Methods:
           parse_financial_statements():
               Parse financial statements based on the presentation structure.

           get_statement(name: str) -> Optional[FinancialStatement]:
               Retrieve a specific financial statement by name.

           get_financial_statement(statement_name: str) -> Optional[pd.DataFrame]:
               Get a financial statement as a pandas DataFrame, with formatting and filtering applied.

           get_balance_sheet() -> Optional[pd.DataFrame]:
               Get the balance sheet as a pandas DataFrame.

           get_income_statement() -> Optional[pd.DataFrame]:
               Get the income statement as a pandas DataFrame.

           get_cash_flow_statement() -> Optional[pd.DataFrame]:
               Get the cash flow statement as a pandas DataFrame.
       """
    instance: XBRLInstance
    presentation: XBRLPresentation
    labels: Dict
    calculations: Dict
    statements: Dict[str, FinancialStatement] = Field(default_factory=dict)

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
        xbrl_documents = XbrlDocuments(filing.attachments)
        instance_xml, presentation_xml, labels, calculations = await xbrl_documents.load()
        return cls.parse(instance_xml, presentation_xml, labels, calculations)

    def parse_financial_statements(self):
        """
        Parse financial statements based on the presentation structure.

        This method creates FinancialStatement objects for each role in the presentation
        linkbase and stores them in the statements dictionary.
        """
        for role, root_element in self.presentation.roles.items():
            statement_name = role.split('/')[-1]
            self.statements[statement_name] = FinancialStatement.create(
                statement_name,
                root_element,
                self.labels,
                self.calculations.get(role, {}),
                self.instance
            )

    def get_statement(self, statement_name: str, include_format_info: bool = False) -> Optional[pd.DataFrame]:
        """
        Get a financial statement as a pandas DataFrame, with formatting and filtering applied.

        This method retrieves a financial statement, formats it into a DataFrame, applies
        various data cleaning and formatting operations, and returns the result.

        Args:
            statement_name (str): The name of the financial statement to retrieve.
            include_format_info (bool): Whether to include additional formatting information in the DataFrame.

        Returns:
            Optional[pd.DataFrame]: A formatted DataFrame representing the financial statement,
                                    or None if the statement is not found.
        """
        statement = self.statements.get(statement_name)

        if not statement:
            print(f"Statement not found: {statement_name}")
            return None

        # Create format_info dictionary
        format_info = {item.label: {'level': item.level, 'abstract': item.concept.endswith('Abstract')}
                       for item in statement.line_items}

        # Use the order of line_items as they appear in the statement
        ordered_items = [item.label for item in statement.line_items]

        # Create DataFrame with preserved order
        data = {year: {} for year in set(period.split(' to ')[-1].split('-')[0]
                                         for item in statement.line_items
                                         for period in item.values)}
        for item in statement.line_items:
            for period, value_info in item.values.items():
                year = period.split(' to ')[-1].split('-')[0]
                data[year][item.label] = value_info['value']

        df = pd.DataFrame(data).T
        df = df.reindex(columns=ordered_items)

        # Sort rows by year (descending)
        df = df.sort_index(ascending=False)

        # Replace empty strings with NaN for non-abstract items
        for col in df.columns:
            if not format_info[col]['abstract']:
                df[col] = df[col].replace('', np.nan)

        # Remove rows that are entirely empty (excluding abstract items)
        df = df.dropna(how='all')

        # Drop rows with significantly less data
        def row_data_ratio(row):
            non_abstract = [not format_info[col]['abstract'] for col in df.columns]
            return row[non_abstract].notna().sum() / sum(non_abstract) if sum(non_abstract) > 0 else 0

        latest_row_ratio = row_data_ratio(df.iloc[0])
        rows_to_keep = [df.index[0]]  # Always keep the most recent period

        for idx in df.index[1:]:
            if row_data_ratio(df.loc[idx]) >= 0.4 * latest_row_ratio:  # Threshold at 40%
                rows_to_keep.append(idx)
            else:
                break  # Stop checking once we find a row to drop

        df = df.loc[rows_to_keep]

        # Fill NaN with empty string for display purposes
        df = df.fillna('')

        # Transpose the DataFrame to get the final structure
        df = df.T

        # Add format info if requested
        if include_format_info:
            # Clean up format_info to only include rows that are in the DataFrame
            format_info = {row: info for row, info in format_info.items() if row in df.index}

            # Add level and abstract information as new columns
            df['abstract'] = pd.Series({row: format_info.get(row, {}).get('abstract', False) for row in df.index})
            df['level'] = pd.Series({row: format_info.get(row, {}).get('level', 0) for row in df.index})
            #df['level_name'] = df.index.str.extract(r'\s*\[(\w+)\]$', expand=False).fillna('')

        # Extract concept type and clean labels
        #df.index = df.index.str.replace(r'\s*\[(\w+)\]$', '', regex=True)

        return df

    def get_balance_sheet(self, include_format_info=False) -> Optional[pd.DataFrame]:
        """
        Get the balance sheet as a pandas DataFrame.
        """
        return self.get_statement("CONSOLIDATEDBALANCESHEETS", include_format_info=include_format_info)

    def get_statement_of_operations(self, include_format_info=False) -> Optional[pd.DataFrame]:
        """
        Get the income statement as a pandas DataFrame.
        """
        return self.get_statement("CONSOLIDATEDSTATEMENTSOFOPERATIONS", include_format_info=include_format_info)

    def get_cash_flow_statement(self, include_format_info=False) -> Optional[pd.DataFrame]:
        """
        Get the cash flow statement as a pandas DataFrame.
        """
        return self.get_statement("CONSOLIDATEDSTATEMENTSOFCASHFLOWS", include_format_info=include_format_info)

    def get_statement_of_shareholders_equity(self, include_format_info=False) -> Optional[pd.DataFrame]:
        return self.get_statement("CONSOLIDATEDSTATEMENTSOFSHAREHOLDERSEQUITY", include_format_info=include_format_info)

    def get_statement_of_income(self, include_format_info=False) -> Optional[pd.DataFrame]:
        return self.get_statement("CONSOLIDATEDSTATEMENTSOFCOMPREHENSIVEINCOME", include_format_info=include_format_info)

    def __rich__(self):
        return self.instance.__rich__()

    def __repr__(self):
        return repr_rich(self)


def parse_labels(xml_string: str) -> Dict[str, Dict[str, str]]:
    """
        Parse an XBRL label linkbase XML string and extract label information.

        This function takes an XML string representing an XBRL label linkbase and
        processes it to extract label information for each concept. It organizes
        the labels by concept and role.

        Parameters:
        xml_string (str): A string containing the XML content of the XBRL label linkbase.

        Returns:
        Dict[str, Dict[str, str]]: A nested dictionary where:
            - The outer key is the concept name (without the 'lab_' prefix).
            - The inner key is the role of the label (last part of the role URI).
            - The value is the text content of the label.

        Example:
        {
            'Assets': {
                'label': 'Assets',
                'terseLabel': 'Assets',
                'totalLabel': 'Total Assets'
            },
            'Liabilities': {
                'label': 'Liabilities',
                'terseLabel': 'Liabilities'
            }
        }

        Note:
        - This function assumes the XML is well-formed and follows the XBRL label linkbase structure.
        - It uses BeautifulSoup with the 'xml' parser to process the XML.
        - The function removes the 'lab_' prefix from concept names and extracts only the last part of the role URI.
        """
    soup = BeautifulSoup(xml_string, 'xml')
    labels = {}

    for label in soup.find_all('label'):
        concept = label.get('xlink:label').split('_', 1)[1]  # Remove the 'lab_' prefix
        role = label.get('xlink:role').split('/')[-1]  # Get the last part of the role URI
        text = label.text

        if concept not in labels:
            labels[concept] = {}
        labels[concept][role] = text

    return labels


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
            order = int(arc.get('order', '0'))
            arcrole = arc['xlink:arcrole']

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
            order = int(arc['order'])

            if from_label in locs and to_label in locs:
                from_concept = locs[from_label]
                to_concept = locs[to_label]
                calculations[role].append((from_concept, to_concept, weight, order))

    return calculations


async def download_and_parse(attachment: Attachment, parse_func):
    content: str = await download_file_async(attachment.url)
    return parse_func(content)

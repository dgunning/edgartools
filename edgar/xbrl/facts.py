from typing import Dict, Any, Optional

import pandas as pd
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from rich import box
from rich.table import Table, Column

from edgar._rich import repr_rich
from edgar.xbrl.concepts import DEI_CONCEPTS
from edgar.xbrl.dimensions import Dimensions

__all__ = ['XBRLInstance']


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

    @property
    def dimensions(self):
        return Dimensions(self)

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
        facts_data = []
        for tag in soup.find_all(lambda t: t.namespace != "http://www.xbrl.org/"):
            if not ('contextRef' in tag.attrs or 'unitRef' in tag.attrs):
                continue
            concept = f"{tag.prefix}:{tag.name}"
            value = tag.text.strip()
            units = tag.get('unitRef')
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

        self.facts = pd.DataFrame(facts_data)

    def get_all_dimensions(self):
        return set().union(*self.facts['dimensions'].apply(lambda x: x.keys()))

    def get_dimension_values(self, dimension):
        return self.facts['dimensions'].apply(lambda x: x.get(dimension)).dropna().unique()

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

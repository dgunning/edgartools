import hashlib
from functools import lru_cache
from typing import Dict, Any, Optional, List

import pandas as pd
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, Field
from rich import box
from rich.table import Table
from rich.text import Text

from edgar.core import datefmt
from edgar.richtools import repr_rich
from edgar.xbrl.dimensions import Dimensions
from edgar.xmltools import child_text


@lru_cache(maxsize=128)
def get_duration_label(start_date, end_date):
    if start_date is None or end_date is None:
        return 'instant'

    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    delta = relativedelta(end, start)

    days = (end - start).days

    if days <= 31:
        return '1 month'
    elif days <= 100:
        return '3 months'
    elif days <= 196:
        return '6 months'
    elif days <= 290:
        return '9 months'
    elif days <= 380:
        return 'annual'
    else:
        years = delta.years
        months = delta.months
        if months > 0:
            return f'{years} years {months} months'
        else:
            return f'{years} years'


class XBRLInstance(BaseModel):
    contexts: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    facts: pd.DataFrame = Field(default_factory=lambda: pd.DataFrame())
    units: Dict[str, str] = Field(default_factory=dict)
    entity_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def _get_single_value(self, concept) -> Optional[Any]:
        """
        Get a single value for a concept. Returns None if there are multiple values or no values.
        """
        facts = self.query_facts(concept=concept)
        if len(facts) == 1:
            return facts['value'].item()
        return None

    @property
    def dimensions(self):
        return Dimensions(self)

    def get_document_type(self):
        # Get the document type from the DEI facts
        return self._get_single_value('dei:DocumentType')

    def get_document_period(self):
        # Get the document period from the DEI facts
        return self._get_single_value('dei:DocumentPeriodEndDate')

    def get_fiscal_year_focus(self):
        # Get the fiscal year focus from the DEI facts
        return self._get_single_value('dei:DocumentFiscalYearFocus')

    def get_fiscal_period_focus(self):
        # Get the fiscal period focus from the DEI facts
        return self._get_single_value('dei:DocumentFiscalPeriodFocus')

    def get_common_stock_outstanding(self):
        # Get the number of common stock shares outstanding from the DEI facts
        return self._get_single_value('dei:EntityCommonStockSharesOutstanding')

    def get_entity_name(self):
        # Get the name of the entity (company) from the DEI facts
        return self._get_single_value('dei:EntityRegistrantName')

    @classmethod
    def parse(cls, instance_xml: str):
        instance = cls()
        soup = BeautifulSoup(instance_xml, 'xml')

        instance.parse_contexts(soup)
        instance.parse_units(soup)
        instance.parse_entity_identifier(soup)
        instance.parse_facts(soup)

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
                'end_date': child_text(period,'endDate') ,
                'instant': child_text(period, 'instant'),
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
        seen_facts = set()
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
                end_date = context['end_date'] or context['instant']
                period_type = 'instant' if context.get('instant') else 'duration'
                duration = get_duration_label(start_date, end_date)
                entity_id = context['entity_id']
                dimensions = context['dimensions']
            else:
                start_date = end_date = period_type = duration = entity_id = None
                dimensions = {}

            fact_id = f"{concept}_{context_id}_{value}_{start_date}_{end_date}"
            if fact_id in seen_facts:
                continue
            seen_facts.add(fact_id)

            fact_data = {
                'concept': concept,
                'value': value,
                'units': units,
                'decimals': decimals,
                'start_date': start_date,
                'end_date': end_date,
                'period_type': period_type,
                'duration': duration,
                'context_id': context_id,
                'entity_id': entity_id,
            }
            fact_data.update(dimensions)
            facts_data.append(fact_data)

        # Create MultiIndex DataFrame
        self.facts = pd.DataFrame(facts_data)
        non_dim_columns = ['concept', 'value', 'units', 'decimals', 'start_date', 'end_date',
                           'period_type', 'duration', 'context_id', 'entity_id']
        dim_columns = [col for col in self.facts.columns if col not in non_dim_columns]

        self.facts = self.facts.set_index(['concept'] + dim_columns)
        self.facts = self.facts.convert_dtypes(dtype_backend="pyarrow")

    @lru_cache(maxsize=128)
    def get_all_dimensions(self):
        return set(self.facts.index.names) - {'concept'}

    @lru_cache(maxsize=128)
    def get_dimension_values(self, dimension):
        if dimension in self.facts.index.names:
            return self.facts.index.get_level_values(dimension).dropna().unique().tolist()
        return []

    @staticmethod
    def _get_schema(concept):
        return concept.split(':')[0] if ':' in concept else ''

    @property
    @lru_cache(maxsize=1)
    def dimension_columns(self) -> List[str]:
        """Cache the list of dimension columns"""
        standard_columns = {'concept', 'value', 'units', 'decimals', 'start_date',
                          'end_date', 'period_type', 'context_id', 'entity_id', 'duration'}
        return [col for col in self.facts.columns if col not in standard_columns]

    def query_facts(self, schema=None, axis=None, **kwargs):
        """
            Query facts from the XBRL instance based on specified criteria.

            This method allows for flexible querying of facts based on schema, concept names,
            dimensional attributes, and other non-dimensional attributes. It handles cases where
            queried concepts or dimensions may not exist in the instance.

            Parameters:
            -----------
            schema : str, optional
                The schema to filter facts by (e.g., 'dei', 'us-gaap'). If provided, only facts
                from this schema will be returned.

            **kwargs : dict
                Additional query parameters. Special keys include:
                - 'concept': str or list of str
                    The concept name(s) to filter by. Can be a single concept name or a list of concepts.
                - 'dimensions': dict
                    A dictionary of dimensional filters where keys are dimension names and values
                    are either a single value or a list of values to filter by.
                Any other keys are treated as non-dimensional attributes to filter by (e.g., 'units', 'period_type').

            Returns:
            --------
            pandas.DataFrame
                A DataFrame containing the queried facts. The DataFrame will have the following characteristics:
                - Each row represents a fact that matches the query criteria.
                - Columns include 'concept' and any relevant dimensional and non-dimensional attributes.
                - Empty columns (containing only NaN values) are dropped.
                - If no facts match the query criteria, an empty DataFrame with the original column structure is returned.

            Examples:
            ---------
            # Query all facts from the 'us-gaap' schema
            instance.query_facts(schema='us-gaap')

            # Query facts for a specific concept
            instance.query_facts(concept='Assets')

            # Query facts with dimensional filters
            instance.query_facts(dimensions={'ProductOrServiceAxis': 'ProductMember'})

            # Combine multiple filters
            instance.query_facts(schema='us-gaap', concept='Revenue',
                                 dimensions={'GeographyAxis': ['NorthAmericaMember', 'EuropeMember']},
                                 period_type='duration')

            Notes:
            ------
            - The method uses boolean indexing for filtering, which allows it to handle cases
              where queried concepts or dimensions don't exist in the instance without raising errors.
            - Dimensional filters are applied using the MultiIndex structure of the facts DataFrame.
            - Non-dimensional attributes are filtered using column-wise operations.
            """

        # Start with all facts
        result = self.facts

        # Apply index-level filters first while keeping the index structure
        if schema:
            mask = result.index.get_level_values('concept').map(self._get_schema) == schema
            result = result[mask]

        if axis:
            if axis in result.index.names:
                result = result[result.index.get_level_values(axis).notnull()]

        # Handle concept filtering at index level
        if 'concept' in kwargs:
            value = kwargs.pop('concept')
            if isinstance(value, list):
                result = result[result.index.get_level_values('concept').isin(value)]
            else:
                result = result[result.index.get_level_values('concept') == value]

        # Handle dimensional filters while still indexed
        if 'dimensions' in kwargs:
            query_dims = kwargs.pop('dimensions')
            # If dimensions is empty then we filter to only facts that have no dimensions
            if query_dims == {}:
                dim_cols = [col for col in result.index.names if col != 'concept']
                if dim_cols:
                    result = result[result.index.get_level_values(dim_cols[0]).isna()]
                    for dim in dim_cols[1:]:
                        result = result[result.index.get_level_values(dim).isna()]
            else:
                # Filter for specific dimension values
                for dim, value in query_dims.items():
                    if dim in result.index.names:
                        if isinstance(value, list):
                            result = result[result.index.get_level_values(dim).isin(value)]
                        else:
                            result = result[result.index.get_level_values(dim) == value]

        # If the result is empty after index filtering, return empty DataFrame
        if result.empty:
            return pd.DataFrame(columns=self.facts.reset_index().columns)

        # Only reset index if we have remaining column filters
        if kwargs:
            result = result.reset_index()

            # Apply remaining column filters vectorized
            mask = pd.Series(True, index=result.index)
            for key, value in kwargs.items():
                if key in result.columns:
                    if isinstance(value, list):
                        mask &= result[key].isin(value)
                    else:
                        mask &= result[key] == value
            result = result[mask]

            # Drop empty columns
            result = result.dropna(axis=1, how='all')
        else:
            # If no column filters, just reset index to maintain consistent output format
            result = result.reset_index()

        return result

    def get_facts_for_concept(self, concept):
        return self.query_facts(concept=concept)

    def get_facts_for_schema(self, schema):
        return self.query_facts(schema=schema)

    @property
    def instance_hash(self) -> str:
        hash_string = f"{self.get_entity_name()}_{self.get_document_period()}_{len(self.facts)}"
        return hashlib.md5(hash_string.encode()).hexdigest()

    def __hash__(self):
        return hash(self.instance_hash)

    def __eq__(self, other):
        if not isinstance(other, XBRLInstance):
            return False
        return self.instance_hash == other.instance_hash

    def __rich__(self):
        fields = [('Company', Text(self.get_entity_name(), style="bold deep_sky_blue3")),('Form', self.get_document_type())]
        if self.get_document_period():
            fields.append(('Period', datefmt(self.get_document_period(), '%B %d, %Y')))
        fields.append(('Facts', f"{len(self.facts):,}"))
        table = Table(*[field[0] for field in fields], title="XBRL Instance", box=box.SIMPLE_HEAD)
        table.add_row(*[field[1] for field in fields])

        return table

    def __repr__(self):
        return repr_rich(self)

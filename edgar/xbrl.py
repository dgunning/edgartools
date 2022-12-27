from functools import lru_cache
from typing import Dict, Union

import duckdb
import pandas as pd
from bs4 import BeautifulSoup
from pydantic import BaseModel

from edgar.core import log
from edgar.xml import child_text

"""
This module parses XBRL documents into objects that contain the structured data
The main capability is to convert XBRL documents into FilingXbrl objects.

This wraps the underlying data read from the XBL document.
Unlike other XBRL parsing tools, this does not do full XBRL parsing with schema validation etc, but is sufficient
for getting data from XBRL document. So it's quite a bit faster since it does not have to download anything.

"""

__all__ = [
    'FilingXbrl',
    'NamespaceInfo'
]


class NamespaceInfo(BaseModel):
    xmlns: str
    namespace2tag: Dict[str, str]


class FilingXbrl:

    """
    Represents the XBRL data for a single filing.
    It wraps the underlying dataset of facts into a `facts` property.

    """

    def __init__(self,
                 facts: pd.DataFrame,
                 namespace_info: NamespaceInfo):
        self.facts: pd.DataFrame = facts
        self.namepace_info: NamespaceInfo = namespace_info

    def _dei_value(self, fact: str):
        res = self.facts.query(f"namespace=='dei' & fact=='{fact}' ")
        if not res.empty:
            return res.value.item()

    @property
    def company_name(self):
        return self._dei_value('EntityRegistrantName')

    @property
    def cik(self):
        val = self._dei_value('EntityCentralIndexKey')
        return int(val) if val else None

    @property
    def form_type(self):
        return self._dei_value('DocumentType')

    @lru_cache(maxsize=1)
    def to_duckdb(self):
        con = duckdb.connect(database=':memory:')
        con.register('facts', self.facts)
        log.info("Created an in-memory DuckDB database with table 'facts'")
        return con

    @classmethod
    def parse(cls, xbrl_text: str):
        soup = BeautifulSoup(xbrl_text, features="xml")
        xbrl_tag = soup.find("xbrl")

        xmlns = xbrl_tag.attrs.get("xmlns")
        namespace2tag = {v: k.partition(':')[2] for k, v in xbrl_tag.attrs.items() if ':' in k}

        unit_map = dict()
        context_map = dict()

        def get_unit(unit_ref: str):
            return unit_map.get(unit_ref)

        def get_context(context_ref: str):
            context = context_map.get(context_ref)
            if context:
                start_date, end_date = context.get('period', (None, None))
                dims: Union[str, None] = context.get('dimensions')
                return start_date, end_date, dims
            else:
                return None, None, None

        for ctx in xbrl_tag.find_all('context', recursive=False):
            context_id = ctx.attrs['id']
            context_map[context_id] = {'id': child_text(ctx, 'identifier')}
            instant = child_text(ctx, 'instant')
            if instant:
                context_map[context_id]['period'] = instant, instant
            else:
                context_map[context_id]['period'] = child_text(ctx, 'startDate'), child_text(ctx, 'endDate')

            # Parse segments
            segment = ctx.find('segment')
            if segment:
                context_map[context_id]['dimensions'] = {m.attrs['dimension']: m.text
                                                         for m in
                                                         segment.find_all('xbrldi:explicitMember')}

        # Parse units
        for unit in xbrl_tag.find_all('unit', recursive=False):
            unit_id = unit.attrs['id']
            divide = unit.find('divide')
            if divide:
                numerator = child_text(divide.find('unitNumerator'), 'measure')
                denominator = child_text(divide.find('unitDenominator'), 'measure')
                unit_map[unit_id] = f"{numerator} per {denominator}"
            else:
                unit_map[unit_id] = child_text(unit, 'measure') or ''

            # Remove iso427 from units
            unit_map[unit_id] = unit_map[unit_id].replace('iso4217:', '')

        # Now parse facts
        facts = []
        for tag in xbrl_tag.find_all(recursive=False):
            if 'contextRef' in tag.attrs or 'unitRef' in tag.attrs:
                ctx_ref = tag.attrs.get('contextRef')
                start, end, dimensions = get_context(ctx_ref)
                units = get_unit(tag.attrs.get('unitRef'))
                facts.append({'namespace': namespace2tag.get(tag.namespace),
                              'fact': tag.name,
                              'value': tag.text,
                              'units': units,
                              'start_date': start,
                              'end_date': end,
                              'dimensions': dimensions})
        facts_dataframe = (pd.DataFrame(facts)
                           .assign(value=lambda df: df.value.replace({'true': True, 'false': False}))
                           )
        return cls(facts=facts_dataframe,
                   namespace_info=NamespaceInfo(xmlns=xmlns, namespace2tag=namespace2tag))

    def __repr__(self):
        return f"""Filing XBRL({self.company_name} {self.cik} {self.form_type})"""

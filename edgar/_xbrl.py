from functools import lru_cache
from typing import Dict, Union, Tuple, Optional

import pandas as pd
from bs4 import BeautifulSoup
from rich.console import Group, Text
from rich.panel import Panel
from rich import box

from edgar._rich import repr_rich, df_to_rich_table
from edgar._xml import child_text
from edgar.core import log

"""
This module parses XBRL documents into objects that contain the structured data
The main capability is to convert XBRL documents into FilingXbrl objects.

This wraps the underlying data read from the XBL document.
Unlike other XBRL parsing tools, this does not do full XBRL parsing with schema validation etc, but is sufficient
for getting data from XBRL document. So it's quite a bit faster since it does not have to download anything.

See https://specifications.xbrl.org/presentation.html

"""

__all__ = [
    'FilingXbrl',
    'NamespaceInfo'
]


class NamespaceInfo:
    """
    This class contains the namespace tags and links parsed from the start of an (XBRL) XML document
    """

    def __init__(self,
                 xmlns: str,
                 namespace2tag: Dict[str, str]
                 ):
        self.xmlns: str = xmlns
        self.namespace2tag: Dict[str, str] = namespace2tag

    def __len__(self):
        return len(self.namespace2tag)

    def summary(self) -> pd.DataFrame:
        return (pd.DataFrame(self.namespace2tag.items(),
                             columns=['namespace', 'taxonomy'])
                .filter(['taxonomy', 'namespace'])
                .sort_values('taxonomy')
                .reset_index(drop=True)
                )

    def __repr__(self):
        return f"NamespaceInfo(xmlns={self.xmlns}, namespace2tag={self.namespace2tag})"


class XbrlFacts:

    def __init__(self, data: pd.DataFrame):
        self.data = data

    def __len__(self):
        return len(self.data)

    def query(self, expr, **kwargs):
        return self.data.query(expr, **kwargs)

    @property
    def empty(self) -> bool:
        return self.data.empty

    def __str__(self):
        return f"XbrlFacts(contains {len(self)} company facts)"

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __rich__(self):
        return Group(
            Text("Facts"),
            df_to_rich_table(self.data[['namespace', 'fact', 'value']].set_index('fact'),
                             max_rows=20),
        )


class FilingXbrl:
    """
    Represents the XBRL data for a single filing.
    It wraps the underlying dataset of facts into a `facts` property.

    """

    def __init__(self,
                 facts: pd.DataFrame,
                 namespace_info: NamespaceInfo):
        self.facts: XbrlFacts = XbrlFacts(facts)
        self.namespace_info: NamespaceInfo = namespace_info

    def _dei_value(self, fact: str):
        res = self.facts.data.query(f"namespace=='dei' & fact=='{fact}' ")
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

    @property
    def fiscal_year_end_date(self):
        res = self.facts.data.query("namespace=='dei' and fact=='CurrentFiscalYearEndDate'")
        if not res.empty:
            return res.iloc[0].end_date

    @property
    def period_end_date(self):
        res = self.facts.data.query("namespace=='dei' and fact=='DocumentPeriodEndDate'")
        if not res.empty:
            return res.iloc[0].end_date

    def _default_gaap_dimension(self,
                                include_null_dimensions: bool = False
                                ):
        # The default dimension is the dimension that has the largest mean value for a set of facts
        fact_names = ['Assets',
                      'Liabilities',
                      'LiabilitiesAndStockholdersEquity',
                      'Revenues',
                      'CashAndCashEquivalentsAtCarryingValue',
                      'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents']
        # Filter the facts data to these facts
        res = self.facts.data.query(f"namespace=='us-gaap' and fact in {fact_names}")
        # now find the single dimension that has the largest mean numeric value
        res = (res
               .query("value.str.isnumeric()")
               .assign(value=lambda df: df.value.astype(float))
               .groupby('dimensions')
               .sum(numeric_only=True)
               .sort_values(['value'], ascending=False)
               .reset_index()
               )
        if not res.empty:
            return res.iloc[0].dimensions

    @property
    @lru_cache(maxsize=1)
    def gaap(self) -> Optional[pd.DataFrame]:
        """Get the GAAP facts for the fiscal year-end date"""
        period_end_date = self.period_end_date
        if period_end_date:
            res = self.facts.data.query(
                f"namespace=='us-gaap' and end_date=='{period_end_date}' and dimensions.isnull()")
            if res.empty:
                # Look for the default gaap dimension
                default_dimension = self._default_gaap_dimension()
                log.warning(
                    f"No default dimension detected in {self.form_type} XBRL for {self.company_name} [{self.cik}] "
                    f"Using {default_dimension} as the default dimension")
                res = self.facts.data.query(
                    f'namespace=="us-gaap" and end_date=="{period_end_date}" and dimensions=="{default_dimension}"')
            return (res
                    .filter(["fact", "value", "units"])
                    .drop_duplicates()
                    .reset_index(drop=True)
                    )

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

        def get_context(context_ref: str) -> Tuple[str, str, Union[str, None]]:
            """Get the value of the context for that context id"""
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
                context_map[context_id]['dimensions'] = str({m.attrs['dimension']: m.text
                                                             for m in
                                                             segment.find_all('xbrldi:explicitMember')})

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

    def summary(self) -> pd.DataFrame:
        """Summarize this FilingXBRL as a dataframe"""
        return pd.DataFrame(
            [{"company": self.company_name,
              "cik": self.cik,
              "form": self.form_type,
              "namespaces": len(self.namespace_info),
              "facts": len(self.facts), }]
        )

    def __str__(self):
        return f"""Filing XBRL({self.company_name} {self.cik} {self.form_type})"""

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __rich__(self):
        return Panel(Group(
            Text(f"Form {self.form_type} Extracted XBRL"),
            df_to_rich_table(self.summary().set_index("company")),
            Text("Facts"),
            df_to_rich_table(self.facts.data[['namespace', 'fact', 'value', 'units', 'end_date']], max_rows=10),
            Text("Taxonomies"),
            df_to_rich_table(self.namespace_info.summary())
        ), box=box.ROUNDED
        )

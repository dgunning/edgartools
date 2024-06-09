from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Union, Tuple, Optional

import pandas as pd
from bs4 import BeautifulSoup
from pydantic import BaseModel
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

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


def get_period(start_date, end_date):
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    # Same day
    if start == end:
        return start_date

    # Full year
    if start == datetime(start.year, 1, 1) and end == datetime(end.year, 12, 31):
        return str(start.year)

        # Check for each quarter
    quarters = {
        1: ('-01-01', '-03-31'),
        2: ('-04-01', '-06-30'),
        3: ('-07-01', '-09-30'),
        4: ('-10-01', '-12-31'),
    }
    for quarter, (start_suffix, end_suffix) in quarters.items():
        if (start_date == f"{start.year}{start_suffix}") and (end_date == f"{end.year}{end_suffix}"):
            return f"Q{quarter} {start.year}"

    # Month
    if start.day == 1 and end == (start + pd.offsets.MonthEnd(1)):
        return start.strftime('%b %Y')

    # Default to range
    return f"{start_date} to {end_date}"


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
        return (pd.DataFrame(data=self.namespace2tag.items(),
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
        res = self.data.query(f"namespace=='us-gaap' and fact in {fact_names}")
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

    def get_dei(self, fact: str):
        res = self.data.query(f"namespace=='dei' & fact=='{fact}' & dimensions.isnull()")
        if not res.empty:
            # Get the first row
            return res.iloc[0].value

    @property
    def period_end_date(self):
        return self.get_dei('DocumentPeriodEndDate')

    @lru_cache(maxsize=1)
    def get_facts_for_namespace(self, namespace: str, end_date: Optional[str] = None):
        """Get the facts for the namespace and period"""
        end_date = end_date or self.period_end_date
        criteria = f"namespace=='{namespace}' and end_date=='{end_date}' and dimensions.isnull()"
        res = self.data.query(criteria)
        if res.empty:
            # Look for the default gaap dimension
            default_dimension = self._default_gaap_dimension()
            log.warning(f"No default dimension detected .. using {default_dimension} as the default dimension")
            res = self.data.query(
                f'namespace=="{namespace}" and end_date=="{end_date}" and dimensions=="{default_dimension}"')
        return (res
                .filter(["fact", "value", "units", "start_date", "end_date", "period"])
                .drop_duplicates()
                .reset_index(drop=True)
                )

    def get_fact(self, fact: str, namespace: str, end_date: Optional[str] = None):
        # Get the fact value for the namespace and period
        end_date = end_date or self.period_end_date
        facts = self.get_facts_for_namespace(namespace=namespace, end_date=end_date)
        if not facts.empty:
            res = facts[facts.fact == fact]
            if not res.empty:
                return res.iloc[0].value

    @property
    def years(self):
        # Find the periods that are years
        res = self.data.query("period.str.len() == 4")
        return sorted(res.period.unique().tolist())

    @property
    def periods(self):
        # Find the periods that are years
        return self.data.period.unique().tolist()

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


class ReportingPeriod(BaseModel):
    start_date: datetime
    end_date: datetime
    period_type: str


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

    @property
    def company_name(self):
        return self.facts.get_dei('EntityRegistrantName')

    @property
    def cik(self):
        val = self.facts.get_dei('EntityCentralIndexKey')
        return int(val) if val else None

    @property
    def form_type(self):
        return self.facts.get_dei('DocumentType')

    @property
    def fiscal_year_end_date(self):
        res = self.facts.data.query("namespace=='dei' and fact=='CurrentFiscalYearEndDate'")
        if not res.empty:
            return res.iloc[0].end_date

    @property
    def fiscal_year_focus(self):
        return self.facts.get_dei('DocumentFiscalYearFocus')

    @property
    @lru_cache(maxsize=1)
    def fiscal_period_focus(self):
        return self.facts.get_dei('DocumentFiscalPeriodFocus')

    @property
    def period(self):
        if self.fiscal_year_focus:
            if self.fiscal_period_focus:
                if self.fiscal_period_focus.startswith('Q'):
                    return f"{self.fiscal_period_focus} {self.fiscal_year_focus}"
                else:
                    return self.fiscal_year_focus
            else:
                return self.fiscal_year_focus
        else:
            return self.period_end_date

    @property
    def period_end_date(self):
        return self.facts.period_end_date

    def get_periods(self,
                    period_type: Optional[str] = None,
                    min_count=8) -> Optional[List[Tuple[str, str]]]:
        """
        Get the periods in the filing. For Fiscal years,
        it returns a Tuple of the years
        For quarters, it returns a List of Tuple of the quarters
            e.g [('2017-02-01', '2017-04-30'), ('2016-02-01', '2016-04-30')]
        """
        # Ensure 'data' is a DataFrame to avoid in-place modifications on slices
        data = self.facts.data.copy()
        data['start_date'] = pd.to_datetime(data['start_date']).dt.normalize()
        data['end_date'] = pd.to_datetime(data['end_date']).dt.normalize()
        data = data.copy()

        # Filter for valid entries using .loc with a condition
        condition = data['dimensions'].isna()
        filtered_data = data.loc[condition].copy()

        if filtered_data.empty:
            return []

        filtered_data.loc[:, 'duration_days'] = (
                filtered_data.loc[:, 'end_date'] - filtered_data.loc[:, 'start_date']).dt.days

        # Define the period type based on the duration in days

        def determine_period_type(days):
            if days == 0:
                return 'instant'
            elif 75 <= days <= 105:
                return 'quarter'
            # The filing 0001193125-21-170978 has a period of 241 days. Should it be included
            elif 335 <= days <= 395:
                return 'year'
            else:
                return 'other'

        filtered_data.loc[:, 'period_type'] = filtered_data['duration_days'].apply(determine_period_type)

        # Filter by period type
        if period_type:
            filtered_data = filtered_data[filtered_data['period_type'] == period_type]

        # Count occurrences of each unique period
        period_counts = filtered_data.filter(
            ['start_date', 'end_date', 'period_type']).value_counts().to_frame().reset_index()

        # Optionally filter periods by occurrence count
        period_counts = period_counts[period_counts['count'] > min_count]

        # Convert start_date and end_date back to str 'YYYY-MM-DD' format
        period_counts['start_date'] = period_counts['start_date'].dt.strftime('%Y-%m-%d')
        period_counts['end_date'] = period_counts['end_date'].dt.strftime('%Y-%m-%d')

        # Sort by start date descending
        period_counts = period_counts.sort_values('start_date', ascending=False)

        # Return a list of tuples containing start and end dates
        return [tuple(r) for r in
                period_counts.filter(['start_date', 'end_date']).to_numpy()] if not period_counts.empty else None

    def get_fiscal_periods(self) -> List[Tuple[str, str]]:
        """
        Get only the periods that match this fiscal period focus

        """
        if self.fiscal_period_focus == 'FY':
            return self.get_periods(period_type="year")
        elif self.fiscal_period_focus.startswith('Q'):
            return self.get_periods(period_type="quarter")

    @lru_cache(maxsize=1)
    def get_facts_by_periods(self, fiscal_periods: bool = True) -> pd.DataFrame:
        """
        Get the facts for the specified periods.
        This method filters the facts data for the specified periods and
        returns a DataFrame with the facts for the specified periods.

        |                                       | 2017-12-31   | 2016-12-31   |   2015-12-31 |
        |:--------------------------------------|:-------------|:-------------|-------------:|
        | AdjustedGainLossOnSaleOfBusiness      | -25101000    | 0            |            0 |
        | AdjustmentToCapitalIncomeTax          |              |              |     -1768000 |

        :param fiscal_periods: If True, filter to only fiscal periods
        """

        # Pivot the data
        facts = self.facts.data.sort_values(by='dimensions', na_position='first')
        # Using 'end_date' as columns to display data based on the period's end date
        facts_by_period = facts.pivot_table(
            index='fact',
            columns='end_date',
            values='value',
            aggfunc='first'
            # Using 'first' to handle duplicates, other options could be 'sum' or 'mean' based on context
        )

        # Replace NaN with pd.NA for better compatibility across different data types
        facts_by_period = facts_by_period.fillna(pd.NA)

        # Sort the columns in descending order to have the latest period first
        facts_by_period = facts_by_period[sorted(facts_by_period.columns, reverse=True)].reset_index()

        # Remove the index name
        facts_by_period.columns.name = None
        df = facts_by_period.set_index('fact')
        if fiscal_periods:
            xbrl_fiscal_periods = self.get_fiscal_periods()
            if xbrl_fiscal_periods:
                fiscal_end_dates = sorted(set([end for _, end in xbrl_fiscal_periods]), reverse=True)
                return df[fiscal_end_dates]
            else:
                """ 
                If we are here, then we can't figure out the fiscal periods but there's a chance that the
                downstream code will still display appropriate data. THis is an edge case for 
                filing (form='10-K/A', company='Pershing Square Tontine Holdings, Ltd.', 
                accession_no='0001193125-21-170978')
                """
                pass

        return df

    def get_fiscal_period_facts(self, fact_names: Optional[List[str]] = None,
                                threshold_percentage: float = 0.4) -> pd.DataFrame:
        """
        Get the facts for the fiscal periods, dropping previous period columns that are mostly empty
        relative to the current period based on a specified threshold percentage.

        :param fact_names: Optional list of fact names to filter the DataFrame.
        :param threshold_percentage: Threshold for the percentage of non-empty values in the current period
                                     required to keep a previous period column.
        :return: A DataFrame of fiscal period facts with irrelevant columns dropped.
        """
        # Retrieve the DataFrame for fiscal periods
        fiscal_period_facts: pd.DataFrame = self.get_facts_by_periods(fiscal_periods=True)

        # Filter by specified fact names if provided
        if fact_names:
            fact_names = [fact for fact in fact_names if fact in fiscal_period_facts.index]
            fiscal_period_facts = fiscal_period_facts.loc[fact_names]

        # Ensure the DataFrame is sorted with the most recent fiscal period first
        fiscal_period_facts = fiscal_period_facts[sorted(fiscal_period_facts.columns, reverse=True)]

        # Determine the number of non-empty values in the current fiscal period
        current_period = fiscal_period_facts.columns[0]  # Assuming the first column is the most recent period
        current_period_non_empty_count = fiscal_period_facts[current_period].notna().sum()

        # Calculate the minimum number of non-empty values needed to retain a column
        min_non_empty_count = current_period_non_empty_count * threshold_percentage

        # Filter out columns where the number of non-empty values is less than the calculated minimum
        columns_to_keep = [col for col in fiscal_period_facts.columns if
                           fiscal_period_facts[col].notna().sum() >= min_non_empty_count]

        # Adjust DataFrame to only include necessary columns
        fiscal_period_facts_filtered = fiscal_period_facts[columns_to_keep]

        return fiscal_period_facts_filtered

    @property
    def years(self):
        return self.facts.years

    @property
    def gaap(self) -> Optional[pd.DataFrame]:
        return self.facts.get_facts_for_namespace(namespace='us-gaap', end_date=self.period_end_date)

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

        def get_context(context_ref: str) -> Optional[Tuple[str, str, Union[str, None]]]:
            """Get the value of the context for that context id"""
            context = context_map.get(context_ref)
            if context:
                start_date, end_date = context.get('period', (None, None))
                dims: Union[str, None] = context.get('dimensions')
                return start_date, end_date, dims

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
                           .assign(value=lambda df: df.value.replace({'true': True, 'false': False}),
                                   period=lambda df: df.apply(lambda x: get_period(x['start_date'], x['end_date']),
                                                              axis=1)
                                   )

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

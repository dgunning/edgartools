from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from typing import List, Optional, Union

import pyarrow.compute as pc

from edgar._party import Address

__all__ = [
    'FilingManager',
    'OtherManager',
    'CoverPage',
    'SummaryPage',
    'Signature',
    'PrimaryDocument13F',
    'ThirteenF',
    'HoldingsView',
    'HoldingsComparison',
    'HoldingsHistory',
    'THIRTEENF_FORMS',
    'format_date',
]

THIRTEENF_FORMS = ['13F-HR', "13F-HR/A", "13F-NT", "13F-NT/A", "13F-CTR", "13F-CTR/A"]


def format_date(date: Union[str, datetime]) -> str:
    if isinstance(date, str):
        return date
    return date.strftime("%Y-%m-%d")


@dataclass(frozen=True)
class FilingManager:
    name: str
    address: Address


@dataclass(frozen=True)
class OtherManager:
    cik: str
    name: str
    file_number: str
    sequence_number: int = None


@dataclass(frozen=True)
class CoverPage:
    report_calendar_or_quarter: str
    report_type: str
    filing_manager: FilingManager
    other_managers: List[OtherManager]


@dataclass(frozen=True)
class SummaryPage:
    other_included_managers_count: int
    total_value: Decimal
    total_holdings: int
    other_managers: List['OtherManager'] = None


@dataclass(frozen=True)
class Signature:
    name: str
    title: str
    phone: str
    signature: str
    city: str
    state_or_country: str
    date: str


@dataclass(frozen=True)
class PrimaryDocument13F:
    report_period: datetime
    cover_page: CoverPage
    summary_page: SummaryPage
    signature: Signature
    additional_information: str


class HoldingsView:
    """View of 13F holdings as a Rich-renderable, iterable object."""

    def __init__(self, data, thirteen_f, display_limit: int = 200):
        self.data = data              # The summary DataFrame
        self._thirteen_f = thirteen_f  # For title/metadata in rendering
        self.display_limit = display_limit

    def __rich__(self):
        from edgar.thirteenf.rendering import render_holdings_view
        return render_holdings_view(self, display_limit=self.display_limit)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        """Iterate over rows as dicts."""
        for _, row in self.data.iterrows():
            yield row.to_dict()

    def __getitem__(self, index):
        """Slice the underlying DataFrame."""
        if isinstance(index, int):
            return self.data.iloc[index].to_dict()
        return self.data.iloc[index]


class HoldingsComparison:
    """Comparison of 13F holdings between two consecutive quarters."""

    def __init__(self, data, current_period: str, previous_period: str, manager_name: str,
                 display_limit: int = 200):
        self.data = data
        self.current_period = current_period
        self.previous_period = previous_period
        self.manager_name = manager_name
        self.display_limit = display_limit

    def __rich__(self):
        from edgar.thirteenf.rendering import render_holdings_comparison
        return render_holdings_comparison(self, display_limit=self.display_limit)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        """Iterate over rows as dicts."""
        for _, row in self.data.iterrows():
            yield row.to_dict()

    def __getitem__(self, index):
        """Slice the underlying DataFrame."""
        if isinstance(index, int):
            return self.data.iloc[index].to_dict()
        return self.data.iloc[index]


class HoldingsHistory:
    """Multi-quarter share history for 13F holdings with sparkline trends."""

    def __init__(self, data, periods: list, manager_name: str,
                 display_limit: int = 100):
        self.data = data
        self.periods = periods
        self.manager_name = manager_name
        self.display_limit = display_limit

    def __rich__(self):
        from edgar.thirteenf.rendering import render_holdings_history
        return render_holdings_history(self, display_limit=self.display_limit)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        """Iterate over rows as dicts."""
        for _, row in self.data.iterrows():
            yield row.to_dict()

    def __getitem__(self, index):
        """Slice the underlying DataFrame."""
        if isinstance(index, int):
            return self.data.iloc[index].to_dict()
        return self.data.iloc[index]


class ThirteenF:
    """
    A 13F-HR is a quarterly report filed by institutional investment managers that have over $100 million in qualifying
    assets under management. The report is filed with the Securities & Exchange Commission (SEC) and discloses all
    the firm's equity holdings that it held at the end of the quarter. The report is due within 45 days of the end
    of the quarter. The 13F-HR is a public document that is available on the SEC's website.
    """

    def __init__(self, filing, use_latest_period_of_report=False):
        from edgar.thirteenf.parsers.primary_xml import parse_primary_document_xml

        assert filing.form in THIRTEENF_FORMS, f"Form {filing.form} is not a valid 13F form"
        self._actual_filing = filing  # The filing passed in
        self.__related_filings = None  # Lazy-loaded: all related filings
        self.__same_day_filings = None  # Lazy-loaded: same-date + same-form subset

        if use_latest_period_of_report:
            # Use the last related filing filed on the same date.
            # It should also be the one that has the CONFORMED_PERIOD_OF_REPORT closest to filing_date
            self.filing = self._same_day_filings[-1]
        else:
            # Use the exact filing that was passed in
            self.filing = self._actual_filing

        # Parse primary document if XML is available (2013+ filings)
        # For older TXT-only filings (2012 and earlier), primary_form_information will be None
        primary_xml = self.filing.xml()
        self.primary_form_information = parse_primary_document_xml(primary_xml) if primary_xml else None

    @property
    def _related_filings(self):
        """Lazy-load related 13F filings (used by previous_holding_report)."""
        if self.__related_filings is None:
            self.__related_filings = self._actual_filing.related_filings().filter(
                form=self._actual_filing.form
            )
        return self.__related_filings

    @property
    def _same_day_filings(self):
        """Lazy-load related filings filed on the same date with the same form."""
        if self.__same_day_filings is None:
            self.__same_day_filings = self._related_filings.filter(
                filing_date=self._actual_filing.filing_date,
                form=self._actual_filing.form
            )
        return self.__same_day_filings

    def has_infotable(self):
        return self.filing.form in ['13F-HR', "13F-HR/A"]

    @property
    def form(self):
        return self.filing.form

    @property
    @lru_cache(maxsize=1)
    def infotable_xml(self):
        """Returns XML content if available (2013+ filings)"""
        if self.has_infotable():
            result = self._get_infotable_from_attachment()
            if result and result[0] and result[1] == 'xml' and "informationTable" in result[0]:
                return result[0]
        return None

    def _get_infotable_from_attachment(self):
        """
        Use the filing homepage to get the infotable file.
        Returns a tuple of (content, format) where format is 'xml' or 'txt'.
        """
        if self.has_infotable():
            # Try XML format first (2013+)
            query = "document_type=='INFORMATION TABLE' and document.lower().endswith('.xml')"
            attachments = self.filing.attachments.query(query)
            if len(attachments) > 0:
                return (attachments.get_by_index(0).download(), 'xml')

            # Fall back to TXT format (2012 and earlier)
            # The primary document itself contains the table in TXT format
            # Try various description patterns first
            query = "description=='FORM 13F' or description=='INFORMATION TABLE'"
            attachments = self.filing.attachments.query(query)
            if len(attachments) > 0:
                # Filter for .txt files only
                txt_attachments = [att for att in attachments if att.document.lower().endswith('.txt')]
                if txt_attachments:
                    return (txt_attachments[0].download(), 'txt')

            # Final fallback: For older filings, descriptions may be unreliable
            # Look for sequence number 1 with .txt extension
            try:
                att = self.filing.attachments.get_by_sequence(1)
                if att and att.document.lower().endswith('.txt'):
                    return (att.download(), 'txt')
            except (KeyError, AttributeError):
                pass

            return (None, None)

    @property
    @lru_cache(maxsize=1)
    def infotable_txt(self):
        """Returns TXT content if available (pre-2013 filings)"""
        if self.has_infotable():
            result = self._get_infotable_from_attachment()
            if result and result[0] and result[1] == 'txt':
                return result[0]

            # Fallback: Some filings have the information table embedded in the main HTML
            # instead of as a separate attachment. Try to extract it from the main HTML.
            if not result or not result[0]:
                html = self.filing.html()
                if html and "Form 13F Information Table" in html:
                    return html
        return None

    @property
    @lru_cache(maxsize=1)
    def infotable_html(self):
        if self.has_infotable():
            query = "document_type=='INFORMATION TABLE' and document.lower().endswith('.html')"
            attachments = self.filing.attachments.query(query)
            return attachments[0].download()

    @property
    @lru_cache(maxsize=1)
    def infotable(self):
        """
        Returns the information table as a pandas DataFrame (disaggregated by manager).

        For multi-manager filings, this returns separate rows for each manager combination's
        holdings of the same security. Use the `holdings` property for an aggregated view.

        Supports both XML format (2013+) and TXT format (2012 and earlier).

        Returns:
            pd.DataFrame: Holdings disaggregated by manager, with OtherManager column

        See Also:
            holdings: Aggregated view (recommended for most users)
        """
        from edgar.thirteenf.parsers.infotable_txt import parse_infotable_txt
        from edgar.thirteenf.parsers.infotable_xml import parse_infotable_xml

        if self.has_infotable():
            # Try XML format first
            if self.infotable_xml:
                return parse_infotable_xml(self.infotable_xml)
            # Fall back to TXT format
            elif self.infotable_txt:
                return parse_infotable_txt(self.infotable_txt)
        return None

    @property
    @lru_cache(maxsize=1)
    def holdings(self):
        """
        Returns aggregated holdings by security (user-friendly view).

        For multi-manager filings, this aggregates holdings across all manager combinations,
        providing a single row per unique security. This is the recommended view for most users
        as it matches industry-standard presentation (CNBC, Bloomberg, etc.).

        Aggregation logic:
        - Group by CUSIP (unique security identifier)
        - Sum: SharesPrnAmount, Value, SoleVoting, SharedVoting, NonVoting
        - Keep: Issuer, Class, Cusip, Ticker, Type, PutCall (when consistent)
        - Drop: OtherManager, InvestmentDiscretion (manager-specific fields)

        Returns:
            pd.DataFrame: Holdings aggregated by security, sorted by value descending

        Example:
            >>> thirteen_f.holdings  # Aggregated view (e.g., 40 rows for Berkshire)
            >>> thirteen_f.infotable  # Disaggregated by manager (e.g., 121 rows)

        See Also:
            infotable: Disaggregated view showing manager-specific holdings
        """
        import pandas as pd

        infotable = self.infotable
        if infotable is None or len(infotable) == 0:
            return None

        # Work on a copy to avoid modifying the cached infotable
        df = infotable.copy()

        # Columns to keep as-is (first value when grouping)
        id_cols = ['Issuer', 'Class', 'Cusip', 'Ticker']

        # Columns to sum across managers
        sum_cols = ['SharesPrnAmount', 'Value', 'SoleVoting', 'SharedVoting', 'NonVoting']

        # Check if numeric columns need conversion (handle potential object/string dtypes)
        # Use pd.api.types for pandas 2.x/3.x compatibility
        for col in sum_cols:
            if col in df.columns and (pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col])):
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('int64')

        # Aggregate by CUSIP
        agg_dict = {}

        # Keep first value for ID columns
        for col in id_cols:
            if col in df.columns:
                agg_dict[col] = 'first'

        # Sum numeric columns
        for col in sum_cols:
            if col in df.columns:
                agg_dict[col] = 'sum'

        # Handle Type and PutCall - keep if consistent across managers, otherwise use first
        for col in ['Type', 'PutCall']:
            if col in df.columns:
                agg_dict[col] = 'first'  # Use first value (typically consistent per CUSIP)

        # Group by CUSIP and aggregate
        holdings = df.groupby('Cusip', as_index=False).agg(agg_dict)

        # Sort by value descending
        if 'Value' in holdings.columns:
            holdings = holdings.sort_values('Value', ascending=False).reset_index(drop=True)

        return holdings

    @property
    def accession_number(self):
        return self.filing.accession_no

    @property
    def total_value(self):
        """Total value of holdings in thousands of dollars"""
        if self.primary_form_information:
            return self.primary_form_information.summary_page.total_value
        # For TXT-only filings, calculate from infotable
        infotable = self.infotable
        if infotable is not None and len(infotable) > 0:
            return Decimal(int(infotable['Value'].sum()))
        return None

    @property
    def total_holdings(self):
        """Total number of holdings"""
        if self.primary_form_information:
            return self.primary_form_information.summary_page.total_holdings
        # For TXT-only filings, count from infotable
        infotable = self.infotable
        if infotable is not None:
            return len(infotable)
        return None

    @property
    def other_managers(self) -> list:
        """
        List of other included managers in this consolidated 13F filing.

        For multi-manager institutional filings (e.g., State Street, Bank of America),
        this returns the affiliated entities whose holdings are reported together.
        Each manager includes CIK, name, file number, and sequence number.

        Returns:
            list[OtherManager]: List of other managers, or empty list if none

        Example:
            >>> thirteenf.other_managers
            [OtherManager(cik='0001102113', name='BANK OF AMERICA NA', ...)]
        """
        if self.primary_form_information:
            summary_page = self.primary_form_information.summary_page
            if summary_page and summary_page.other_managers:
                return summary_page.other_managers
        return []

    @property
    def report_period(self):
        """Report period end date"""
        if self.primary_form_information:
            return format_date(self.primary_form_information.report_period)
        # For TXT-only filings, use CONFORMED_PERIOD_OF_REPORT from filing header
        if hasattr(self.filing, 'period_of_report') and self.filing.period_of_report:
            return format_date(self.filing.period_of_report)
        return None

    @property
    def filing_date(self):
        return format_date(self.filing.filing_date)

    @property
    def investment_manager(self):
        # This is really the firm e.g. Spark Growth Management Partners II, LLC
        if self.primary_form_information:
            return self.primary_form_information.cover_page.filing_manager
        return None

    @property
    def signer(self):
        # This is the person who signed the filing. Could be the Reporting Manager but could be someone else
        # like the CFO
        if self.primary_form_information:
            return self.primary_form_information.signature.name
        return None

    # Enhanced manager name properties for better clarity
    @property
    def management_company_name(self) -> str:
        """
        The legal name of the investment management company that filed the 13F.

        This is the institutional entity (e.g., "Berkshire Hathaway Inc", "Vanguard Group Inc")
        that is legally responsible for managing the assets, not an individual person's name.

        Returns:
            str: The legal name of the management company, or company name from filing if not available

        Example:
            >>> thirteen_f.management_company_name
            'Berkshire Hathaway Inc'
        """
        if self.investment_manager:
            return self.investment_manager.name
        # For TXT-only filings, use company name from filing
        return self.filing.company

    @property
    def filing_signer_name(self) -> str:
        """
        The name of the individual who signed the 13F filing.

        This is typically an administrative officer (CFO, CCO, Compliance Officer, etc.)
        rather than the famous portfolio manager. For example, Berkshire Hathaway's 13F
        is signed by "Marc D. Hamburg" (SVP), not Warren Buffett.

        Returns:
            str: The name of the person who signed the filing

        Example:
            >>> thirteen_f.filing_signer_name
            'Marc D. Hamburg'
        """
        return self.signer

    @property
    def filing_signer_title(self) -> Optional[str]:
        """
        The business title of the individual who signed the 13F filing.

        Common titles include: CFO, CCO, Senior Vice President, Chief Compliance Officer,
        Secretary, Treasurer, etc. This helps distinguish administrative signers from
        portfolio managers.

        Returns:
            str: The business title of the filing signer, or None if not available

        Example:
            >>> thirteen_f.filing_signer_title
            'Senior Vice President'
        """
        if self.primary_form_information:
            return self.primary_form_information.signature.title
        return None

    @property
    def manager_name(self) -> str:
        """
        DEPRECATED: Use management_company_name instead.

        Returns the management company name for backwards compatibility.
        This property name was misleading as it suggested an individual manager's name.

        Returns:
            str: The management company name

        Warning:
            This property is deprecated and may be removed in future versions.
            Use management_company_name for the company name, or see get_portfolio_managers()
            if you need information about individual portfolio managers.
        """
        import warnings
        warnings.warn(
            "manager_name is deprecated and misleading. Use management_company_name for the "
            "company name, or get_portfolio_managers() for individual manager information.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.management_company_name

    def get_portfolio_managers(self, include_approximate: bool = False) -> list[dict]:
        """
        Get information about the actual portfolio managers for this fund.

        Note: 13F filings do not contain individual portfolio manager names.
        This method provides a curated mapping for well-known funds based on
        public information. Results may not be current or complete.

        Args:
            include_approximate (bool): If True, includes approximate/historical
                                      manager information even if not current

        Returns:
            list[dict]: List of portfolio manager information with keys:
                       'name', 'title', 'status', 'source', 'last_updated'

        Example:
            >>> thirteen_f.get_portfolio_managers()
            [
                {
                    'name': 'Warren Buffett',
                    'title': 'Chairman & CEO',
                    'status': 'active',
                    'source': 'public_records',
                    'last_updated': '2024-01-01'
                }
            ]
        """
        from edgar.thirteenf.manager_lookup import lookup_portfolio_managers
        return lookup_portfolio_managers(
            self.management_company_name,
            getattr(self.filing, 'cik', None),
            include_approximate=include_approximate
        )

    def _lookup_portfolio_managers(self, company_name: str, include_approximate: bool = False) -> list[dict]:
        """
        Private method for testing - looks up portfolio managers by company name.

        Args:
            company_name: Name of the management company
            include_approximate: Whether to include approximate/historical data

        Returns:
            list[dict]: List of portfolio manager information
        """
        from edgar.thirteenf.manager_lookup import lookup_portfolio_managers
        return lookup_portfolio_managers(company_name, cik=None, include_approximate=include_approximate)

    def get_manager_info_summary(self) -> dict:
        """
        Get a comprehensive summary of all available manager information.

        This provides a clear breakdown of what information is available from the 13F
        filing versus external sources, helping users understand the data limitations.

        Returns:
            dict: Summary with keys 'from_13f_filing', 'external_sources', 'limitations'

        Example:
            >>> thirteen_f.get_manager_info_summary()
            {
                'from_13f_filing': {
                    'management_company': 'Berkshire Hathaway Inc',
                    'filing_signer': 'Marc D. Hamburg',
                    'signer_title': 'Senior Vice President'
                },
                'external_sources': {
                    'portfolio_managers': [
                        {'name': 'Warren Buffett', 'title': 'Chairman & CEO', 'status': 'active'}
                    ]
                },
                'limitations': [
                    '13F filings do not contain individual portfolio manager names',
                    'External manager data may not be current or complete',
                    'Filing signer is typically an administrative officer, not the portfolio manager'
                ]
            }
        """
        portfolio_managers = self.get_portfolio_managers()

        return {
            'from_13f_filing': {
                'management_company': self.management_company_name,
                'filing_signer': self.filing_signer_name,
                'signer_title': self.filing_signer_title,
                'form': self.form,
                'period_of_report': str(self.report_period)
            },
            'external_sources': {
                'portfolio_managers': portfolio_managers,
                'manager_count': len(portfolio_managers)
            },
            'limitations': [
                '13F filings do not contain individual portfolio manager names',
                'External manager data may not be current or complete',
                'Filing signer is typically an administrative officer, not the portfolio manager',
                'Portfolio manager information is sourced from public records and may be outdated'
            ]
        }

    def is_filing_signer_likely_portfolio_manager(self) -> bool:
        """
        Determine if the filing signer is likely to be a portfolio manager.

        This uses heuristics based on the signer's title to assess whether they
        might be involved in investment decisions rather than just administrative functions.

        Returns:
            bool: True if signer appears to be investment-focused, False if administrative

        Example:
            >>> thirteen_f.is_filing_signer_likely_portfolio_manager()
            False  # For administrative titles like CFO, CCO, etc.
        """
        from edgar.thirteenf.manager_lookup import is_filing_signer_likely_portfolio_manager
        return is_filing_signer_likely_portfolio_manager(self.filing_signer_title)

    @lru_cache(maxsize=8)
    def previous_holding_report(self):
        if len(self.report_period) == 1:
            return None
        # Look in the related filings data for the row with this accession number
        idx = pc.equal(self._related_filings.data['accession_number'], self.accession_number).index(True).as_py()
        if idx == 0:
            return None
        previous_filing = self._related_filings[idx - 1]
        return ThirteenF(previous_filing, use_latest_period_of_report=False)

    def holdings_view(self, display_limit: int = 200) -> Optional['HoldingsView']:
        """Return a view of current holdings as a renderable, iterable object.

        Unlike .holdings (a raw DataFrame), this returns a HoldingsView with
        __rich__(), __iter__(), and __getitem__() for display and downstream use.
        """
        from edgar.thirteenf.rendering import infotable_summary
        summary = infotable_summary(self)
        if summary is None:
            return None
        return HoldingsView(data=summary, thirteen_f=self, display_limit=display_limit)

    def compare_holdings(self, display_limit: int = 200) -> Optional['HoldingsComparison']:
        """Compare current holdings with the previous quarter.

        Returns a HoldingsComparison with per-security changes including
        share and value deltas, percentage changes, and status labels
        (NEW, CLOSED, INCREASED, DECREASED, UNCHANGED).

        Args:
            display_limit: Max rows to show in Rich display (default 200).
                           The .data DataFrame always contains all rows.

        Returns:
            HoldingsComparison or None if previous holdings are unavailable
        """
        import numpy as np
        import pandas as pd

        current = self.holdings
        if current is None or len(current) == 0:
            return None

        prev_report = self.previous_holding_report()
        if prev_report is None:
            return None
        previous = prev_report.holdings
        if previous is None or len(previous) == 0:
            return None

        cur = current[['Cusip', 'Ticker', 'Issuer', 'SharesPrnAmount', 'Value']].copy()
        cur.columns = ['Cusip', 'Ticker', 'Issuer', 'Shares', 'Value']

        prev = previous[['Cusip', 'Ticker', 'Issuer', 'SharesPrnAmount', 'Value']].copy()
        prev.columns = ['Cusip', 'Ticker_prev', 'Issuer_prev', 'PrevShares', 'PrevValue']

        merged = cur.merge(prev, on='Cusip', how='outer')

        # Coalesce Ticker / Issuer
        merged['Ticker'] = merged['Ticker'].fillna(merged['Ticker_prev'])
        merged['Issuer'] = merged['Issuer'].fillna(merged['Issuer_prev'])
        merged.drop(columns=['Ticker_prev', 'Issuer_prev'], inplace=True)

        # Fill missing numeric values with NaN (they stay NaN for NEW/CLOSED)
        for col in ['Shares', 'PrevShares', 'Value', 'PrevValue']:
            merged[col] = pd.to_numeric(merged[col], errors='coerce')

        merged['ShareChange'] = merged['Shares'] - merged['PrevShares']
        merged['ShareChangePct'] = np.where(
            merged['PrevShares'].notna() & (merged['PrevShares'] != 0),
            (merged['ShareChange'] / merged['PrevShares']) * 100,
            np.nan,
        )
        merged['ValueChange'] = merged['Value'] - merged['PrevValue']
        merged['ValueChangePct'] = np.where(
            merged['PrevValue'].notna() & (merged['PrevValue'] != 0),
            (merged['ValueChange'] / merged['PrevValue']) * 100,
            np.nan,
        )

        def _status(row):
            if pd.isna(row['PrevShares']):
                return 'NEW'
            if pd.isna(row['Shares']):
                return 'CLOSED'
            if row['ShareChange'] > 0:
                return 'INCREASED'
            if row['ShareChange'] < 0:
                return 'DECREASED'
            return 'UNCHANGED'

        merged['Status'] = merged.apply(_status, axis=1)
        merged.sort_values('ValueChange', key=lambda s: s.abs(), ascending=False, inplace=True, na_position='last')
        merged.reset_index(drop=True, inplace=True)

        return HoldingsComparison(
            data=merged,
            current_period=self.report_period,
            previous_period=prev_report.report_period,
            manager_name=self.management_company_name,
            display_limit=display_limit,
        )

    def holding_history(self, periods: int = 4, display_limit: int = 100) -> Optional['HoldingsHistory']:
        """Track share counts across multiple quarters.

        Walks backward through previous holding reports and builds a
        DataFrame with one column per quarter (oldest→newest, left→right)
        plus a Unicode sparkline trend.

        Args:
            periods: Number of quarters to include (default 4)
            display_limit: Max rows to show in Rich display (default 200).
                           The .data DataFrame always contains all rows.

        Returns:
            HoldingsHistory or None if current holdings are unavailable
        """
        import pandas as pd

        reports = [self]
        current = self
        for _ in range(periods - 1):
            prev = current.previous_holding_report()
            if prev is None:
                break
            reports.append(prev)
            current = prev

        if not reports:
            return None

        # Reverse so oldest is first
        reports = list(reversed(reports))

        # Deduplicate by report_period — keep the latest filing for each period
        seen = {}
        for r in reports:
            seen[r.report_period] = r  # later entry (newer filing) overwrites
        reports = [seen[k] for k in dict.fromkeys(r.report_period for r in reports)]
        period_labels = [r.report_period for r in reports]

        merged = None
        for report in reports:
            h = report.holdings
            if h is None or len(h) == 0:
                continue
            col_name = report.report_period
            subset = h[['Cusip', 'Ticker', 'Issuer', 'SharesPrnAmount']].copy()
            subset.rename(columns={'SharesPrnAmount': col_name}, inplace=True)

            if merged is None:
                merged = subset
            else:
                # Merge on Cusip; coalesce Ticker/Issuer from newer data
                merged = merged.merge(
                    subset[['Cusip', col_name]],
                    on='Cusip',
                    how='outer',
                )
                # Update Ticker/Issuer from this (newer) report where missing
                new_ids = subset[['Cusip', 'Ticker', 'Issuer']].drop_duplicates('Cusip')
                for id_col in ['Ticker', 'Issuer']:
                    mapping = new_ids.set_index('Cusip')[id_col]
                    mask = merged[id_col].isna()
                    merged.loc[mask, id_col] = merged.loc[mask, 'Cusip'].map(mapping)

        if merged is None:
            return None

        # Sort by most recent period's shares descending
        most_recent = period_labels[-1]
        if most_recent in merged.columns:
            merged.sort_values(most_recent, ascending=False, na_position='last', inplace=True)
        merged.reset_index(drop=True, inplace=True)

        return HoldingsHistory(
            data=merged,
            periods=period_labels,
            manager_name=self.management_company_name,
            display_limit=display_limit,
        )

    def __rich__(self):
        from edgar.thirteenf.rendering import render_rich
        return render_rich(self)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())


# For backward compatibility, expose parse methods as static methods
ThirteenF.parse_primary_document_xml = staticmethod(lambda xml: __import__('edgar.thirteenf.parsers.primary_xml', fromlist=['parse_primary_document_xml']).parse_primary_document_xml(xml))
ThirteenF.parse_infotable_xml = staticmethod(lambda xml: __import__('edgar.thirteenf.parsers.infotable_xml', fromlist=['parse_infotable_xml']).parse_infotable_xml(xml))
ThirteenF.parse_infotable_txt = staticmethod(lambda txt: __import__('edgar.thirteenf.parsers.infotable_txt', fromlist=['parse_infotable_txt']).parse_infotable_txt(txt))

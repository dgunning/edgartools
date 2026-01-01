"""
ProxyStatement class for DEF 14A (Proxy Statement) filings.

Extracts executive compensation, pay vs performance metrics, and governance
data from XBRL facts using the SEC's Executive Compensation Disclosure (ECD)
taxonomy.
"""
import logging
from decimal import Decimal
from functools import cached_property
from typing import TYPE_CHECKING, List, Optional

import pandas as pd
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich

from .models import (
    PROXY_FORMS,
    NamedExecutive,
)

if TYPE_CHECKING:
    from edgar._filings import Filing

log = logging.getLogger(__name__)

__all__ = ['ProxyStatement']


class ProxyStatement:
    """
    DEF 14A Proxy Statement data object.

    Provides structured access to executive compensation and pay vs performance
    data from proxy statements. Data is extracted from XBRL using the SEC's
    Executive Compensation Disclosure (ECD) taxonomy.

    Usage:
        >>> from edgar import Company
        >>> company = Company("AAPL")
        >>> filing = company.get_filings(form="DEF 14A").latest()
        >>> proxy = filing.obj()
        >>> print(f"CEO: {proxy.peo_name}")
        >>> print(f"CEO Total Compensation: ${proxy.peo_total_comp:,}")
        >>> df = proxy.executive_compensation  # 5-year DataFrame
    """

    def __init__(self, filing: 'Filing'):
        """
        Initialize ProxyStatement from a Filing.

        Args:
            filing: SEC Filing object for a DEF 14A form
        """
        assert filing.form in PROXY_FORMS, f"Form {filing.form} is not a valid proxy form"
        self._filing = filing
        self._xbrl = None
        self._facts_df = None

    @classmethod
    def from_filing(cls, filing: 'Filing') -> Optional['ProxyStatement']:
        """Create a ProxyStatement from a Filing object."""
        return cls(filing)

    @property
    def filing(self) -> 'Filing':
        """The source Filing object."""
        return self._filing

    @cached_property
    def has_xbrl(self) -> bool:
        """
        Whether this filing has XBRL data.

        XBRL is required for large accelerated filers and accelerated filers
        under SEC Pay vs Performance rules. Smaller reporting companies,
        emerging growth companies, SPACs, and registered investment companies
        may not have XBRL data.

        Returns:
            True if XBRL data is available, False otherwise
        """
        return self._xbrl_data is not None

    @cached_property
    def _xbrl_data(self):
        """Lazily load XBRL data."""
        return self._filing.xbrl()

    @cached_property
    def _facts_dataframe(self) -> Optional[pd.DataFrame]:
        """Get facts as DataFrame for querying."""
        if self._xbrl_data and self._xbrl_data.facts:
            return self._xbrl_data.facts.to_dataframe()
        return None

    def _get_concept_value(self, concept: str, numeric: bool = False) -> Optional[str]:
        """
        Extract the most recent value for a specific XBRL concept.

        Args:
            concept: XBRL concept name (e.g., 'ecd:PeoName')
            numeric: If True, return numeric_value instead of value

        Returns:
            The value as string, or None if not found
        """
        if self._facts_dataframe is None:
            return None

        df = self._facts_dataframe
        data = df[df['concept'] == concept]

        if len(data) == 0:
            return None

        # Get the most recent value (by period_end if available)
        if 'period_end' in data.columns:
            data = data.sort_values('period_end', ascending=False)

        if numeric and 'numeric_value' in data.columns:
            return data.iloc[0]['numeric_value']
        return data.iloc[0]['value']

    def _get_concept_series(self, concept: str) -> pd.DataFrame:
        """
        Extract a time series for a specific XBRL concept.

        Returns DataFrame with period_end and value columns.
        """
        if self._facts_dataframe is None:
            return pd.DataFrame(columns=['period_end', 'value'])

        df = self._facts_dataframe
        data = df[df['concept'] == concept].copy()

        if len(data) == 0:
            return pd.DataFrame(columns=['period_end', 'value'])

        result = data[['period_end', 'numeric_value']].copy()
        result = result.sort_values('period_end')
        result.columns = ['period_end', 'value']
        return result.drop_duplicates(subset=['period_end'])

    def _decimal_or_none(self, value) -> Optional[Decimal]:
        """Convert value to Decimal, handling None and NaN."""
        if value is None or pd.isna(value):
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    # Basic Metadata
    @property
    def form(self) -> str:
        """Form type (DEF 14A, DEFA14A, etc.)."""
        return self._filing.form

    @property
    def filing_date(self) -> str:
        """Date filed with SEC."""
        return str(self._filing.filing_date)

    @property
    def company_name(self) -> Optional[str]:
        """Company legal name."""
        return self._get_concept_value('dei:EntityRegistrantName')

    @property
    def cik(self) -> str:
        """Central Index Key."""
        return str(self._filing.cik)

    @property
    def accession_number(self) -> str:
        """SEC accession number."""
        return self._filing.accession_no

    @property
    def fiscal_year_end(self) -> Optional[str]:
        """Fiscal year end date."""
        return self._get_concept_value('dei:DocumentPeriodEndDate')

    # Executive Compensation Properties
    @property
    def peo_name(self) -> Optional[str]:
        """Principal Executive Officer (CEO) name."""
        return self._get_concept_value('ecd:PeoName')

    @cached_property
    def peo_total_comp(self) -> Optional[Decimal]:
        """PEO total compensation from Summary Compensation Table (most recent year)."""
        series = self._get_concept_series('ecd:PeoTotalCompAmt')
        if len(series) > 0:
            return self._decimal_or_none(series.iloc[-1]['value'])
        return None

    @cached_property
    def peo_actually_paid_comp(self) -> Optional[Decimal]:
        """PEO Compensation Actually Paid (most recent year)."""
        series = self._get_concept_series('ecd:PeoActuallyPaidCompAmt')
        if len(series) > 0:
            return self._decimal_or_none(series.iloc[-1]['value'])
        return None

    @cached_property
    def neo_avg_total_comp(self) -> Optional[Decimal]:
        """Non-PEO NEO average total compensation (most recent year)."""
        series = self._get_concept_series('ecd:NonPeoNeoAvgTotalCompAmt')
        if len(series) > 0:
            return self._decimal_or_none(series.iloc[-1]['value'])
        return None

    @cached_property
    def neo_avg_actually_paid_comp(self) -> Optional[Decimal]:
        """Non-PEO NEO average Compensation Actually Paid (most recent year)."""
        series = self._get_concept_series('ecd:NonPeoNeoAvgCompActuallyPaidAmt')
        if len(series) > 0:
            return self._decimal_or_none(series.iloc[-1]['value'])
        return None

    # Pay vs Performance Properties
    @cached_property
    def total_shareholder_return(self) -> Optional[Decimal]:
        """Company Total Shareholder Return (most recent year)."""
        series = self._get_concept_series('ecd:TotalShareholderRtnAmt')
        if len(series) > 0:
            return self._decimal_or_none(series.iloc[-1]['value'])
        return None

    @cached_property
    def peer_group_tsr(self) -> Optional[Decimal]:
        """Peer Group Total Shareholder Return (most recent year)."""
        series = self._get_concept_series('ecd:PeerGroupTotalShareholderRtnAmt')
        if len(series) > 0:
            return self._decimal_or_none(series.iloc[-1]['value'])
        return None

    @cached_property
    def net_income(self) -> Optional[Decimal]:
        """Net Income (most recent year)."""
        series = self._get_concept_series('us-gaap:NetIncomeLoss')
        if len(series) > 0:
            return self._decimal_or_none(series.iloc[-1]['value'])
        return None

    @property
    def company_selected_measure(self) -> Optional[str]:
        """Company-selected performance measure name."""
        return self._get_concept_value('ecd:CoSelectedMeasureName')

    @cached_property
    def company_selected_measure_value(self) -> Optional[Decimal]:
        """Company-selected performance measure value (most recent year)."""
        series = self._get_concept_series('ecd:CoSelectedMeasureAmt')
        if len(series) > 0:
            return self._decimal_or_none(series.iloc[-1]['value'])
        return None

    @cached_property
    def performance_measures(self) -> List[str]:
        """List of performance measures used by the company."""
        if self._facts_dataframe is None:
            return []

        df = self._facts_dataframe
        data = df[df['concept'] == 'ecd:MeasureName']

        if len(data) == 0:
            return []

        return data['value'].dropna().unique().tolist()

    # Governance Properties
    @cached_property
    def insider_trading_policy_adopted(self) -> Optional[bool]:
        """Whether company has adopted insider trading policy."""
        value = self._get_concept_value('ecd:InsiderTrdPoliciesProcAdoptedFlag')
        if value is None:
            return None
        return str(value).lower() in ('true', 'yes', '1', 'y')

    # DataFrame Properties
    @cached_property
    def executive_compensation(self) -> pd.DataFrame:
        """
        5-year executive compensation time series DataFrame.

        Columns:
            - fiscal_year_end: End of fiscal year
            - peo_total_comp: PEO total from SCT
            - peo_actually_paid_comp: PEO compensation actually paid
            - neo_avg_total_comp: Non-PEO NEO average total
            - neo_avg_actually_paid_comp: Non-PEO NEO average CAP
        """
        peo_total = self._get_concept_series('ecd:PeoTotalCompAmt')
        peo_paid = self._get_concept_series('ecd:PeoActuallyPaidCompAmt')
        neo_total = self._get_concept_series('ecd:NonPeoNeoAvgTotalCompAmt')
        neo_paid = self._get_concept_series('ecd:NonPeoNeoAvgCompActuallyPaidAmt')

        # Start with PEO total compensation as base
        if len(peo_total) == 0:
            return pd.DataFrame(columns=[
                'fiscal_year_end', 'peo_total_comp', 'peo_actually_paid_comp',
                'neo_avg_total_comp', 'neo_avg_actually_paid_comp'
            ])

        result = peo_total.rename(columns={'value': 'peo_total_comp'})

        # Merge other series
        for series, col_name in [
            (peo_paid, 'peo_actually_paid_comp'),
            (neo_total, 'neo_avg_total_comp'),
            (neo_paid, 'neo_avg_actually_paid_comp'),
        ]:
            if len(series) > 0:
                series = series.rename(columns={'value': col_name})
                result = result.merge(series, on='period_end', how='outer')

        result = result.rename(columns={'period_end': 'fiscal_year_end'})
        result = result.sort_values('fiscal_year_end')

        # Ensure all columns exist
        for col in ['peo_total_comp', 'peo_actually_paid_comp',
                    'neo_avg_total_comp', 'neo_avg_actually_paid_comp']:
            if col not in result.columns:
                result[col] = None

        return result[['fiscal_year_end', 'peo_total_comp', 'peo_actually_paid_comp',
                       'neo_avg_total_comp', 'neo_avg_actually_paid_comp']].reset_index(drop=True)

    @cached_property
    def pay_vs_performance(self) -> pd.DataFrame:
        """
        5-year pay vs performance metrics DataFrame.

        Columns:
            - fiscal_year_end: End of fiscal year
            - peo_actually_paid_comp: CEO compensation actually paid
            - neo_avg_actually_paid_comp: NEO average CAP
            - total_shareholder_return: Company TSR
            - peer_group_tsr: Peer group TSR
            - net_income: Net income
            - company_selected_measure_value: Company KPI value
        """
        tsr = self._get_concept_series('ecd:TotalShareholderRtnAmt')
        peer_tsr = self._get_concept_series('ecd:PeerGroupTotalShareholderRtnAmt')
        net_inc = self._get_concept_series('us-gaap:NetIncomeLoss')
        peo_paid = self._get_concept_series('ecd:PeoActuallyPaidCompAmt')
        neo_paid = self._get_concept_series('ecd:NonPeoNeoAvgCompActuallyPaidAmt')
        co_measure = self._get_concept_series('ecd:CoSelectedMeasureAmt')

        # Start with TSR as base
        if len(tsr) == 0:
            return pd.DataFrame(columns=[
                'fiscal_year_end', 'peo_actually_paid_comp', 'neo_avg_actually_paid_comp',
                'total_shareholder_return', 'peer_group_tsr', 'net_income',
                'company_selected_measure_value'
            ])

        result = tsr.rename(columns={'value': 'total_shareholder_return'})

        # Merge other series
        for series, col_name in [
            (peer_tsr, 'peer_group_tsr'),
            (net_inc, 'net_income'),
            (peo_paid, 'peo_actually_paid_comp'),
            (neo_paid, 'neo_avg_actually_paid_comp'),
            (co_measure, 'company_selected_measure_value'),
        ]:
            if len(series) > 0:
                series = series.rename(columns={'value': col_name})
                result = result.merge(series, on='period_end', how='outer')

        result = result.rename(columns={'period_end': 'fiscal_year_end'})
        result = result.sort_values('fiscal_year_end')

        # Ensure all columns exist
        for col in ['peo_actually_paid_comp', 'neo_avg_actually_paid_comp',
                    'total_shareholder_return', 'peer_group_tsr', 'net_income',
                    'company_selected_measure_value']:
            if col not in result.columns:
                result[col] = None

        return result[['fiscal_year_end', 'peo_actually_paid_comp', 'neo_avg_actually_paid_comp',
                       'total_shareholder_return', 'peer_group_tsr', 'net_income',
                       'company_selected_measure_value']].reset_index(drop=True)

    # Named Executives (Dimensional Data)
    @cached_property
    def has_individual_executive_data(self) -> bool:
        """Whether individual executive dimensions are available."""
        if self._facts_dataframe is None:
            return False

        df = self._facts_dataframe
        return bool('dim_ecd_IndividualAxis' in df.columns and df['dim_ecd_IndividualAxis'].notna().any())

    @cached_property
    def named_executives(self) -> List[NamedExecutive]:
        """
        Individual named executive officers (when dimensionally tagged).

        Returns list of NamedExecutive dataclasses with individual compensation data.
        Only available when company uses dimensional XBRL tagging (~60% of companies).
        """
        if self._facts_dataframe is None or not self.has_individual_executive_data:
            return []

        df = self._facts_dataframe
        peo_names = df[df['concept'] == 'ecd:PeoName'].copy()

        executives = []

        if 'dim_ecd_IndividualAxis' in peo_names.columns:
            for _, row in peo_names.iterrows():
                if pd.notna(row.get('dim_ecd_IndividualAxis')):
                    executives.append(NamedExecutive(
                        name=row['value'],
                        member_id=row.get('dim_ecd_IndividualAxis'),
                        role=row.get('dim_ecd_ExecutiveCategoryAxis', 'PEO'),
                        fiscal_year_end=str(row.get('period_end', ''))
                    ))

        return executives

    def __str__(self) -> str:
        amendment = " (Amendment)" if '/A' in self.form else ""
        company_display = self.company_name or "Unknown Company"
        return f"DEF 14A{amendment}: {company_display} - {self.fiscal_year_end or self.filing_date}"

    def __rich__(self):
        # Header
        title = Text()
        title.append("DEF 14A Proxy Statement", style="bold blue")
        if '/A' in self.form:
            title.append(" (Amendment)", style="yellow")
        if self.company_name:
            title.append(f" - {self.company_name}", style="bold")

        # Info table
        info_table = Table(box=None, show_header=False, padding=(0, 2))
        info_table.add_column("Field", style="dim")
        info_table.add_column("Value")

        info_table.add_row("Form", self.form)
        info_table.add_row("Filing Date", self.filing_date)
        if self.fiscal_year_end:
            info_table.add_row("Fiscal Year End", self.fiscal_year_end)
        info_table.add_row("CIK", str(self.cik))

        header_panel = Panel(
            info_table,
            title=title,
            border_style="blue",
        )

        elements = [header_panel]

        # Show message if no XBRL data
        if not self.has_xbrl:
            no_xbrl_text = Text()
            no_xbrl_text.append("\nNo XBRL data available. ", style="yellow")
            no_xbrl_text.append(
                "Executive compensation data requires XBRL (not available for SRCs, EGCs, SPACs, or funds).",
                style="dim"
            )
            elements.append(no_xbrl_text)
            return Group(*elements)

        # Executive Compensation Section
        if self.peo_name or self.peo_total_comp:
            comp_table = Table(
                title="Executive Compensation",
                box=box.SIMPLE,
                show_header=True,
            )
            comp_table.add_column("", style="dim")
            comp_table.add_column("Summary Comp Table", justify="right")
            comp_table.add_column("Actually Paid", justify="right")

            peo_label = f"PEO ({self.peo_name})" if self.peo_name else "PEO"
            peo_sct = f"${self.peo_total_comp:,.0f}" if self.peo_total_comp else "-"
            peo_cap = f"${self.peo_actually_paid_comp:,.0f}" if self.peo_actually_paid_comp else "-"
            comp_table.add_row(peo_label, peo_sct, peo_cap)

            neo_sct = f"${self.neo_avg_total_comp:,.0f}" if self.neo_avg_total_comp else "-"
            neo_cap = f"${self.neo_avg_actually_paid_comp:,.0f}" if self.neo_avg_actually_paid_comp else "-"
            comp_table.add_row("NEO Average", neo_sct, neo_cap)

            elements.append(Text())
            elements.append(comp_table)

        # Pay vs Performance Section
        if self.total_shareholder_return or self.net_income:
            pvp_table = Table(
                title="Pay vs Performance",
                box=box.SIMPLE,
                show_header=True,
            )
            pvp_table.add_column("Metric", style="dim")
            pvp_table.add_column("Value", justify="right")

            if self.total_shareholder_return:
                pvp_table.add_row("Company TSR", f"{self.total_shareholder_return:.1f}%")
            if self.peer_group_tsr:
                pvp_table.add_row("Peer Group TSR", f"{self.peer_group_tsr:.1f}%")
            if self.net_income:
                # Format large numbers
                if abs(self.net_income) >= 1_000_000_000:
                    pvp_table.add_row("Net Income", f"${self.net_income / 1_000_000_000:.1f}B")
                else:
                    pvp_table.add_row("Net Income", f"${self.net_income:,.0f}")
            if self.company_selected_measure:
                measure_val = ""
                if self.company_selected_measure_value:
                    if abs(self.company_selected_measure_value) >= 1_000_000_000:
                        measure_val = f" (${self.company_selected_measure_value / 1_000_000_000:.1f}B)"
                    else:
                        measure_val = f" (${self.company_selected_measure_value:,.0f})"
                pvp_table.add_row("Company Measure", f"{self.company_selected_measure}{measure_val}")

            elements.append(Text())
            elements.append(pvp_table)

        # Governance indicators
        if self.insider_trading_policy_adopted is not None:
            gov_text = Text()
            gov_text.append("Governance: ", style="bold")
            if self.insider_trading_policy_adopted:
                gov_text.append("Insider Trading Policy Adopted", style="green")
            else:
                gov_text.append("No Insider Trading Policy", style="red")
            elements.append(Text())
            elements.append(gov_text)

        # Performance Measures
        if self.performance_measures:
            measures_text = Text()
            measures_text.append("Performance Measures: ", style="bold dim")
            measures_text.append(", ".join(self.performance_measures[:5]))
            if len(self.performance_measures) > 5:
                measures_text.append(f" (+{len(self.performance_measures) - 5} more)", style="dim")
            elements.append(Text())
            elements.append(measures_text)

        return Group(*elements)

    def __repr__(self):
        return repr_rich(self.__rich__())

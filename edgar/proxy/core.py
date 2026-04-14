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
        assert filing.form in PROXY_FORMS, (
            f"Form '{filing.form}' is not a recognized proxy form. "
            f"Expected one of: DEF 14A, DEFA14A, DEFC14A, DFAN14A, PRE 14A, PREC14A, etc."
        )
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

    # Award Timing Properties (SEC Rule 402(x) — since 2023)
    @cached_property
    def award_timing_mnpi_considered(self) -> Optional[bool]:
        """Whether equity award timing decisions considered material nonpublic information."""
        value = self._get_concept_value('ecd:AwardTmgMnpiCnsdrdFlag')
        if value is None:
            return None
        return str(value).lower() in ('true', 'yes', '1', 'y')

    @cached_property
    def award_dates_predetermined(self) -> Optional[bool]:
        """Whether equity award grant dates were predetermined."""
        value = self._get_concept_value('ecd:AwardTmgPredtrmndFlag')
        if value is None:
            return None
        return str(value).lower() in ('true', 'yes', '1', 'y')

    @cached_property
    def mnpi_disclosure_timed_for_comp_value(self) -> Optional[bool]:
        """Whether MNPI disclosure was timed to affect compensation value."""
        value = self._get_concept_value('ecd:MnpiDiscTimedForCompValFlag')
        if value is None:
            return None
        return str(value).lower() in ('true', 'yes', '1', 'y')

    @cached_property
    def awards_close_to_mnpi(self) -> pd.DataFrame:
        """
        Awards granted within 4 business days of MNPI disclosure.

        Required since 2023 for companies that granted equity awards close to
        material nonpublic information disclosures. Each row represents one
        award grant to a named executive officer.

        Columns:
            - grant_date: Date the award was granted
            - executive: Executive member identifier
            - award_type: Type of award (e.g., stock option)
            - exercise_price: Exercise price of the award
            - grant_date_fair_value: Fair value on grant date
            - underlying_securities: Number of underlying securities
            - market_price_change_pct: Percentage change in underlying security market price
        """
        if self._facts_dataframe is None:
            return pd.DataFrame(columns=[
                'grant_date', 'executive', 'award_type', 'exercise_price',
                'grant_date_fair_value', 'underlying_securities', 'market_price_change_pct'
            ])

        df = self._facts_dataframe
        names = df[df['concept'] == 'ecd:AwardsCloseToMnpiDiscIndName']

        if len(names) == 0:
            return pd.DataFrame(columns=[
                'grant_date', 'executive', 'award_type', 'exercise_price',
                'grant_date_fair_value', 'underlying_securities', 'market_price_change_pct'
            ])

        rows = []
        for _, name_row in names.iterrows():
            individual = name_row.get('dim_ecd_IndividualAxis')
            award_type = name_row.get('dim_us-gaap_AwardTypeAxis')

            # Build filter for matching dimensional rows
            def _match(concept_df):
                mask = concept_df['concept'].notna()
                if individual is not None and 'dim_ecd_IndividualAxis' in concept_df.columns:
                    mask = mask & (concept_df['dim_ecd_IndividualAxis'] == individual)
                if award_type is not None and 'dim_us-gaap_AwardTypeAxis' in concept_df.columns:
                    mask = mask & (concept_df['dim_us-gaap_AwardTypeAxis'] == award_type)
                return concept_df[mask]

            exercise_price = _match(df[df['concept'] == 'ecd:AwardExrcPrice'])
            fair_value = _match(df[df['concept'] == 'ecd:AwardGrantDateFairValue'])
            securities = _match(df[df['concept'] == 'ecd:AwardUndrlygSecuritiesAmt'])
            pct_change = _match(df[df['concept'] == 'ecd:UndrlygSecurityMktPriceChngPct'])

            # Clean up the executive identifier (e.g., "jnj:DuatoMember" → "DuatoMember")
            exec_id = str(individual) if individual else None
            if exec_id and ':' in exec_id:
                exec_id = exec_id.split(':', 1)[1]
            if exec_id and exec_id.endswith('Member'):
                exec_id = exec_id[:-6]

            # Clean up award type
            award_type_str = str(award_type) if award_type else None
            if award_type_str and ':' in award_type_str:
                award_type_str = award_type_str.split(':', 1)[1]
            if award_type_str and award_type_str.endswith('Member'):
                award_type_str = award_type_str[:-6]

            rows.append({
                'grant_date': name_row['value'],
                'executive': exec_id,
                'award_type': award_type_str,
                'exercise_price': self._decimal_or_none(
                    exercise_price.iloc[0]['numeric_value'] if len(exercise_price) > 0 else None
                ),
                'grant_date_fair_value': self._decimal_or_none(
                    fair_value.iloc[0]['numeric_value'] if len(fair_value) > 0 else None
                ),
                'underlying_securities': self._decimal_or_none(
                    securities.iloc[0]['numeric_value'] if len(securities) > 0 else None
                ),
                'market_price_change_pct': self._decimal_or_none(
                    pct_change.iloc[0]['numeric_value'] if len(pct_change) > 0 else None
                ),
            })

        return pd.DataFrame(rows)

    # HTML Extraction Properties
    @cached_property
    def _filing_text(self) -> Optional[str]:
        """Full text of the filing for HTML extraction."""
        try:
            return self._filing.markdown()
        except Exception:
            try:
                return self._filing.text()
            except Exception:
                return None

    @cached_property
    def voting_proposals(self) -> List['VotingProposal']:
        """
        Voting proposals with board recommendations, extracted from HTML.

        Each proposal includes the proposal number, description, board
        recommendation (FOR/AGAINST/ABSTAIN), and classified type
        (director_election, say_on_pay, auditor_ratification, etc.).

        Returns:
            List of VotingProposal dataclasses, sorted by proposal number.
            Returns empty list if text extraction fails.
        """
        from edgar.proxy.html_extractor import extract_voting_proposals
        text = self._filing_text
        if not text:
            return []
        return extract_voting_proposals(text)

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

    def to_context(self, detail: str = 'standard') -> str:
        """
        AI-optimized context string.

        Args:
            detail: 'minimal' (~100 tokens), 'standard' (~300 tokens), 'full' (~500+ tokens)
        """
        from edgar.display.formatting import format_currency_short

        lines = []

        # === IDENTITY ===
        company = self.company_name or "Unknown Company"
        lines.append(f"PROXY: {company}")
        lines.append("")

        # === CORE METADATA ===
        lines.append(f"Filed: {self.filing_date}")
        if self.fiscal_year_end:
            lines.append(f"Fiscal Year End: {self.fiscal_year_end}")
        lines.append(f"Form: {self.form}")

        if not self.has_xbrl:
            lines.append("XBRL: Not available")
            if detail == 'minimal':
                return "\n".join(lines)
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  .has_xbrl                Whether XBRL data is present")
            return "\n".join(lines)

        if detail == 'minimal':
            # Headline compensation
            peo_comp = self.peo_total_comp
            if peo_comp:
                lines.append(f"CEO Total Comp: {format_currency_short(float(peo_comp))}")
            return "\n".join(lines)

        # === STANDARD ===
        lines.append(f"CIK: {self.cik}")

        # Executive compensation
        peo_comp = self.peo_total_comp
        peo_name = self.peo_name
        neo_comp = self.neo_avg_total_comp
        if peo_comp or neo_comp:
            lines.append("")
            lines.append("EXECUTIVE COMPENSATION:")
            if peo_name:
                lines.append(f"  CEO: {peo_name}")
            if peo_comp:
                lines.append(f"  CEO Total Comp: {format_currency_short(float(peo_comp))}")
            peo_cap = self.peo_actually_paid_comp
            if peo_cap:
                lines.append(f"  CEO Actually Paid: {format_currency_short(float(peo_cap))}")
            if neo_comp:
                lines.append(f"  NEO Avg Total Comp: {format_currency_short(float(neo_comp))}")

        # Pay vs performance highlights
        tsr = self.total_shareholder_return
        peer_tsr = self.peer_group_tsr
        if tsr is not None:
            lines.append("")
            lines.append("PAY VS PERFORMANCE:")
            lines.append(f"  Total Shareholder Return: ${float(tsr):,.2f}")
            if peer_tsr is not None:
                lines.append(f"  Peer Group TSR: ${float(peer_tsr):,.2f}")
            ni = self.net_income
            if ni is not None:
                lines.append(f"  Net Income: {format_currency_short(float(ni))}")

        # Award timing
        mnpi_considered = self.award_timing_mnpi_considered
        if mnpi_considered is not None:
            lines.append("")
            lines.append("AWARD TIMING:")
            lines.append(f"  MNPI Considered: {'Yes' if mnpi_considered else 'No'}")
            predetermined = self.award_dates_predetermined
            if predetermined is not None:
                lines.append(f"  Dates Predetermined: {'Yes' if predetermined else 'No'}")
            mnpi_timed = self.mnpi_disclosure_timed_for_comp_value
            if mnpi_timed is not None:
                lines.append(f"  MNPI Timed for Comp Value: {'Yes' if mnpi_timed else 'No'}")

        # Available actions
        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  .executive_compensation  Multi-year comp DataFrame")
        lines.append("  .pay_vs_performance      Pay vs performance DataFrame")
        lines.append("  .peo_total_comp          CEO total compensation")
        lines.append("  .named_executives        Named executive officers list")
        lines.append("  .performance_measures    Company performance measures")
        lines.append("  .awards_close_to_mnpi    Awards granted near MNPI disclosure")
        lines.append("  .voting_proposals        Voting proposals with board recommendations")

        if detail == 'standard':
            return "\n".join(lines)

        # === FULL ===
        # Voting proposals
        try:
            proposals = self.voting_proposals
            if proposals:
                lines.append("")
                lines.append(f"VOTING PROPOSALS: {len(proposals)}")
                for p in proposals:
                    rec = f" (Board: {p.board_recommendation})" if p.board_recommendation else ""
                    lines.append(f"  {p.number}. {p.description}{rec} [{p.proposal_type}]")
        except Exception:
            pass

        # Named executives
        try:
            if self.has_individual_executive_data:
                execs = self.named_executives
                if execs:
                    lines.append("")
                    lines.append(f"NAMED EXECUTIVES: {len(execs)}")
                    for ex in execs[:8]:
                        role_str = f" ({ex.role})" if ex.role else ""
                        lines.append(f"  {ex.name}{role_str}")
        except Exception:
            pass

        # Performance measures
        try:
            measures = self.performance_measures
            if measures:
                lines.append("")
                lines.append("PERFORMANCE MEASURES:")
                for m in measures[:5]:
                    lines.append(f"  {m}")
        except Exception:
            pass

        # Governance
        try:
            itp = self.insider_trading_policy_adopted
            if itp is not None:
                lines.append("")
                lines.append(f"Insider Trading Policy: {'Adopted' if itp else 'Not adopted'}")
        except Exception:
            pass

        # Awards close to MNPI
        try:
            awards_df = self.awards_close_to_mnpi
            if len(awards_df) > 0:
                lines.append("")
                lines.append(f"AWARDS CLOSE TO MNPI: {len(awards_df)} grants")
                for _, row in awards_df.iterrows():
                    exec_name = row.get('executive', 'Unknown')
                    grant_date = row.get('grant_date', '')
                    fair_value = row.get('grant_date_fair_value')
                    fv_str = f" (FV: ${float(fair_value):,.0f})" if fair_value else ""
                    lines.append(f"  {exec_name}: {grant_date}{fv_str}")
        except Exception:
            pass

        return "\n".join(lines)

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

        # Award Timing
        mnpi_considered = self.award_timing_mnpi_considered
        if mnpi_considered is not None:
            timing_text = Text()
            timing_text.append("Award Timing: ", style="bold")
            parts = []
            if mnpi_considered:
                parts.append("MNPI considered")
            predetermined = self.award_dates_predetermined
            if predetermined:
                parts.append("dates predetermined")
            mnpi_timed = self.mnpi_disclosure_timed_for_comp_value
            if mnpi_timed:
                parts.append("MNPI timed for comp value")
            if parts:
                timing_text.append(", ".join(parts))
            else:
                timing_text.append("No MNPI timing concerns", style="green")
            elements.append(Text())
            elements.append(timing_text)

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

        # Voting Proposals
        try:
            proposals = self.voting_proposals
            if proposals:
                prop_table = Table(
                    title="Voting Proposals",
                    box=box.SIMPLE,
                    show_header=True,
                )
                prop_table.add_column("#", style="dim", width=3)
                prop_table.add_column("Proposal", ratio=3)
                prop_table.add_column("Type", style="dim", ratio=1)
                prop_table.add_column("Board", justify="center", width=8)

                for p in proposals:
                    rec_style = "green" if p.board_recommendation == "FOR" else "red" if p.board_recommendation == "AGAINST" else ""
                    rec_text = p.board_recommendation or "-"
                    prop_table.add_row(
                        str(p.number),
                        p.description,
                        p.proposal_type.replace('_', ' '),
                        Text(rec_text, style=rec_style),
                    )
                elements.append(Text())
                elements.append(prop_table)
        except Exception:
            pass

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

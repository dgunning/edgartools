"""
Enhanced EntityFacts class for AI-ready company facts analysis.

This module provides the main EntityFacts class with investment-focused
analytics and AI-ready interfaces.
"""

from collections import defaultdict
from datetime import date
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional

if TYPE_CHECKING:
    from edgar.entity.query import FactQuery
    from edgar.enums import PeriodType

from typing import Union

import httpx
import orjson as json
import pandas as pd
from pandas.core.interchange.dataframe_protocol import DataFrame
from rich.box import SIMPLE, SIMPLE_HEAVY
from rich.columns import Columns
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.core import log
from edgar.entity.enhanced_statement import MultiPeriodStatement
from edgar.entity.models import FinancialFact
from edgar.httprequests import download_json
from edgar.storage import get_edgar_data_directory, is_using_local_storage


class NoCompanyFactsFound(Exception):
    """Exception raised when no company facts are found for a given CIK."""

    def __init__(self, cik: int):
        super().__init__()
        self.message = f"""No Company facts found for cik {cik}"""


def download_company_facts_from_sec(cik: int) -> Dict[str, Any]:
    """
    Download company facts from the SEC
    """
    from edgar.urls import build_company_facts_url
    company_facts_url = build_company_facts_url(cik)
    try:
        return download_json(company_facts_url)
    except httpx.HTTPStatusError as err:
        if err.response.status_code == 404:
            log.warning(f"No company facts found on url {company_facts_url}")
            raise NoCompanyFactsFound(cik=cik) from None
        else:
            raise


def load_company_facts_from_local(cik: int) -> Optional[Dict[str, Any]]:
    """
    Load company facts from local data
    """
    company_facts_dir = get_edgar_data_directory() / "companyfacts"
    if not company_facts_dir.exists():
        return None
    company_facts_file = company_facts_dir / f"CIK{cik:010}.json"
    if not company_facts_file.exists():
        raise NoCompanyFactsFound(cik=cik)

    return json.loads(company_facts_file.read_text())


@lru_cache(maxsize=32)
def get_company_facts(cik: int):
    """
    Get company facts for a given CIK.

    Args:
        cik: The company CIK

    Returns:
        CompanyFacts: The company facts

    Raises:
        NoCompanyFactsFound: If no facts are found for the given CIK
    """
    if is_using_local_storage():
        company_facts_json = load_company_facts_from_local(cik)
    else:
        company_facts_json = download_company_facts_from_sec(cik)
    from edgar.entity.parser import EntityFactsParser
    return EntityFactsParser.parse_company_facts(company_facts_json)


class EntityFacts:
    """
    AI-ready company facts with investment-focused analytics.

    This class provides a comprehensive interface for analyzing company financial data,
    with support for both traditional DataFrame-based workflows and modern AI/LLM
    consumption patterns.
    """

    def __init__(self, cik: int, name: str, facts: List[FinancialFact]):
        """
        Initialize EntityFacts with company information and facts.

        Args:
            cik: Company CIK number
            name: Company name
            facts: List of FinancialFact objects
        """
        self.cik = cik
        self.name = name
        self._facts = facts
        self._fact_index = self._build_indices()
        self._cache = {}

    def _build_indices(self) -> Dict[str, Dict]:
        """Build optimized indices for fast querying"""
        indices = {
            'by_concept': defaultdict(list),
            'by_period': defaultdict(list),
            'by_statement': defaultdict(list),
            'by_form': defaultdict(list),
            'by_fiscal_year': defaultdict(list),
            'by_fiscal_period': defaultdict(list)
        }

        for fact in self._facts:
            # Index by concept
            indices['by_concept'][fact.concept].append(fact)
            if fact.label:
                indices['by_concept'][fact.label.lower()].append(fact)

            # Index by period
            period_key = f"{fact.fiscal_year}-{fact.fiscal_period}"
            indices['by_period'][period_key].append(fact)

            # Index by fiscal year and period
            indices['by_fiscal_year'][fact.fiscal_year].append(fact)
            indices['by_fiscal_period'][fact.fiscal_period].append(fact)

            # Index by statement type
            if fact.statement_type:
                indices['by_statement'][fact.statement_type].append(fact)

            # Index by form type
            indices['by_form'][fact.form_type].append(fact)

        return indices

    def __len__(self) -> int:
        """Return the total number of facts"""
        return len(self._facts)

    def __iter__(self) -> Iterator[FinancialFact]:
        """Iterate over all facts"""
        return iter(self._facts)

    def get_all_facts(self) -> List[FinancialFact]:
        """
        Get all facts for this entity.

        Returns:
            List of all FinancialFact objects
        """
        return self._facts

    def to_dataframe(self,
                     include_metadata: bool = False,
                     columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Export all facts to a pandas DataFrame for analysis.

        This method provides direct access to all financial facts in a tabular format,
        enabling custom analysis, filtering, and integration with data science workflows.

        Args:
            include_metadata: Include filing references and data quality metadata (default: False)
            columns: Specific columns to include. If None, includes standard columns.

        Returns:
            DataFrame with one row per fact, sorted by concept and period_end

        Example:
            Basic export for exploration:
            >>> facts = company.get_facts()
            >>> df = facts.to_dataframe()
            >>> print(df.head())

            Export with metadata for audit trail:
            >>> df_full = facts.to_dataframe(include_metadata=True)

            Custom columns for specific analysis:
            >>> df_slim = facts.to_dataframe(columns=['concept', 'fiscal_year', 'numeric_value'])

            Filter and analyze:
            >>> df = annual_facts.to_dataframe()
            >>> revenue = df[df['concept'].str.contains('Revenue')]
            >>> print(revenue[['fiscal_year', 'numeric_value']])
        """
        # Build records from facts
        records = []
        for fact in self._facts:
            record = {
                'concept': fact.concept,
                'label': fact.label,
                'value': fact.value,
                'numeric_value': fact.numeric_value,
                'unit': fact.unit,
                'period_type': fact.period_type,
                'period_start': fact.period_start,
                'period_end': fact.period_end,
                'fiscal_year': fact.fiscal_year,
                'fiscal_period': fact.fiscal_period
            }

            # Add metadata if requested
            if include_metadata:
                record.update({
                    'accession': fact.accession,
                    'filing_date': fact.filing_date,
                    'form_type': fact.form_type,
                    'statement_type': fact.statement_type,
                    'taxonomy': fact.taxonomy,
                    'scale': fact.scale,
                    'data_quality': fact.data_quality.value if fact.data_quality else None,
                    'is_audited': fact.is_audited,
                    'confidence_score': fact.confidence_score
                })

            records.append(record)

        # Create DataFrame
        df = pd.DataFrame(records)

        # Filter to specific columns if requested
        if columns is not None:
            df = df[columns]

        # Sort for consistency
        if not df.empty:
            sort_cols = []
            if 'concept' in df.columns:
                sort_cols.append('concept')
            if 'period_end' in df.columns:
                sort_cols.append('period_end')
            if sort_cols:
                df = df.sort_values(sort_cols).reset_index(drop=True)

        return df

    def filter_by_period_type(self, period_type: Union[str, 'PeriodType']) -> 'EntityFacts':
        """
        Filter facts by period type and return a new EntityFacts instance.

        Args:
            period_type: Period type to filter by - either PeriodType enum or string
                        ('annual', 'quarterly', 'monthly')

        Returns:
            New EntityFacts instance with filtered facts

        Example:
            >>> annual_facts = facts.filter_by_period_type('annual')
            >>> quarterly_facts = facts.filter_by_period_type(PeriodType.QUARTERLY)
        """
        # Use the query interface to filter facts
        filtered_facts = self.query().by_period_type(period_type).execute()

        # Create a new EntityFacts instance with the filtered facts
        return EntityFacts(
            cik=self.cik,
            name=self.name,
            facts=filtered_facts
        )

    def __rich__(self):
        """Creates a rich representation providing an at-a-glance view of company facts."""
        # Title
        title = Text.assemble(
            "📊 ", 
            (self.name, "bold green"),
            " Financial Facts"
        )

        # Summary Statistics Table
        stats = Table(box=SIMPLE_HEAVY, show_header=False, padding=(0, 1))
        stats.add_column("Metric", style="dim")
        stats.add_column("Value", style="bold")

        # Get date range
        dates = [f.filing_date for f in self._facts if f.filing_date]
        if dates:
            min_date = min(dates)
            max_date = max(dates)
            date_range = f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
        else:
            date_range = "No dates available"

        # Count unique concepts
        unique_concepts = len(set(f.concept for f in self._facts))

        # Count by form type
        form_counts = defaultdict(int)
        for fact in self._facts:
            form_counts[fact.form_type] += 1

        # Get fiscal years covered
        fiscal_years = sorted(set(f.fiscal_year for f in self._facts if f.fiscal_year))
        if fiscal_years:
            year_range = f"{min(fiscal_years)} - {max(fiscal_years)}"
        else:
            year_range = "N/A"

        stats.add_row("CIK", str(self.cik))
        stats.add_row("Total Facts", f"{len(self._facts):,}")
        stats.add_row("Unique Concepts", f"{unique_concepts:,}")
        stats.add_row("Date Range", date_range)
        stats.add_row("Fiscal Years", year_range)

        stats_panel = Panel(
            stats,
            title="📈 Summary Statistics",
            border_style="bright_black"
        )

        # Key Financial Metrics Table
        metrics = Table(box=SIMPLE, show_header=True, padding=(0, 1))
        metrics.add_column("Metric", style="bold")
        metrics.add_column("Value", justify="right")
        metrics.add_column("Period")
        metrics.add_column("Quality", style="dim")

        # Try to get key metrics
        key_metrics = [
            ('Revenue', 'Revenue'),
            ('Net Income', 'NetIncome'),
            ('Total Assets', 'Assets'),
            ('Total Liabilities', 'Liabilities'),
            ('Stockholders Equity', 'StockholdersEquity'),
            ('Operating Income', 'OperatingIncome'),
            ('Public Float', 'dei:EntityPublicFloat'),
            ('Shares Outstanding', 'dei:EntityCommonStockSharesOutstanding')
        ]

        has_metrics = False
        for label, concept in key_metrics:
            fact = self.get_fact(concept)
            if fact:
                has_metrics = True
                # Format value based on unit
                if fact.numeric_value:
                    if 'share' in fact.unit.lower():
                        value = f"{fact.numeric_value:,.0f}"
                    else:
                        value = f"${fact.numeric_value:,.0f}"
                else:
                    value = str(fact.value)

                period = f"{fact.fiscal_period} {fact.fiscal_year}"
                quality = fact.data_quality.value if fact.data_quality else "N/A"
                metrics.add_row(label, value, period, quality)

        if has_metrics:
            metrics_panel = Panel(
                metrics,
                title="💰 Key Financial Metrics",
                border_style="bright_black"
            )
        else:
            metrics_panel = Panel(
                Text("No key financial metrics available", style="dim"),
                title="💰 Key Financial Metrics",
                border_style="bright_black"
            )

        # Available Statements
        statement_counts = defaultdict(int)
        for fact in self._facts:
            if fact.statement_type:
                statement_counts[fact.statement_type] += 1

        if statement_counts:
            statements = Table(box=SIMPLE, show_header=True, padding=(0, 1))
            statements.add_column("Statement Type", style="bold")
            statements.add_column("Fact Count", justify="right")

            for stmt_type, count in sorted(statement_counts.items()):
                statements.add_row(stmt_type, f"{count:,}")

            statements_panel = Panel(
                statements,
                title="📋 Available Statements",
                border_style="bright_black"
            )
        else:
            statements_panel = Panel(
                Text("No statement information available", style="dim"),
                title="📋 Available Statements",
                border_style="bright_black"
            )

        # Recent Filings
        filing_info = defaultdict(lambda: {'count': 0, 'date': None})
        for fact in self._facts:
            key = fact.form_type
            filing_info[key]['count'] += 1
            if fact.filing_date:
                if filing_info[key]['date'] is None or fact.filing_date > filing_info[key]['date']:
                    filing_info[key]['date'] = fact.filing_date

        filings = Table(box=SIMPLE, show_header=True, padding=(0, 1))
        filings.add_column("Form", style="bold")
        filings.add_column("Latest Filing")
        filings.add_column("Facts", justify="right")

        # Sort by most recent filing date
        sorted_filings = sorted(
            filing_info.items(),
            key=lambda x: x[1]['date'] or date.min,
            reverse=True
        )[:5]  # Show top 5

        for form_type, info in sorted_filings:
            date_str = info['date'].strftime('%Y-%m-%d') if info['date'] else "N/A"
            filings.add_row(form_type, date_str, f"{info['count']:,}")

        filings_panel = Panel(
            filings,
            title="📄 Recent Filings",
            border_style="bright_black"
        )

        # Data Quality Summary
        quality_counts = defaultdict(int)
        audited_count = sum(1 for f in self._facts if f.is_audited)

        for fact in self._facts:
            if fact.data_quality:
                quality_counts[fact.data_quality.value] += 1

        quality = Table(box=SIMPLE, show_header=False, padding=(0, 1))
        quality.add_column("Metric", style="dim")
        quality.add_column("Value", style="bold")

        if quality_counts:
            for q_level, count in sorted(quality_counts.items()):
                percentage = (count / len(self._facts)) * 100
                quality.add_row(f"{q_level} Quality", f"{count:,} ({percentage:.1f}%)")

        if audited_count > 0:
            audit_percentage = (audited_count / len(self._facts)) * 100
            quality.add_row("Audited Facts", f"{audited_count:,} ({audit_percentage:.1f}%)")

        quality_panel = Panel(
            quality,
            title="✅ Data Quality",
            border_style="bright_black"
        )

        # Combine all sections
        content_renderables = [
            Padding("", (1, 0, 0, 0)),
            stats_panel,
            Columns([metrics_panel, statements_panel], equal=True, expand=True),
            Columns([filings_panel, quality_panel], equal=True, expand=True)
        ]

        content = Group(*content_renderables)

        # Create the main panel
        return Panel(
            content,
            title=title,
            subtitle=f"SEC XBRL Facts • {len(self._facts):,} total facts",
            border_style="blue"
        )

    def __repr__(self):
        """String representation using rich formatting."""
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())

    # Core query interface
    def query(self) -> 'FactQuery':
        """
        Start building a facts query.

        Returns:
            FactQuery: A new query builder instance

        Example:
            >>> facts.query().by_concept('Revenue').latest(4).to_dataframe()
        """
        from edgar.entity.query import FactQuery
        return FactQuery(self._facts, self._fact_index)

    # Convenience methods for common queries
    def get_fact(self, concept: str, period: Optional[str] = None) -> Optional[FinancialFact]:
        """
        Get a single fact by concept and optional period.

        Args:
            concept: Concept name or label
            period: Optional period in format "YYYY-QN" or "YYYY-FY"

        Returns:
            The most recent matching fact, or None if not found
        """
        # Try exact concept match first
        facts = self._fact_index['by_concept'].get(concept, [])

        # Try case-insensitive label match
        if not facts:
            facts = self._fact_index['by_concept'].get(concept.lower(), [])

        if not facts:
            return None

        # Filter by period if specified
        if period:
            facts = [f for f in facts if f"{f.fiscal_year}-{f.fiscal_period}" == period]

        # Return most recent
        if facts:
            return max(facts, key=lambda f: (f.filing_date, f.period_end))

        return None

    def time_series(self, concept: str, periods: int = 20) -> pd.DataFrame:
        """
        Get time series data for a concept.

        Args:
            concept: Concept name or label
            periods: Number of periods to retrieve

        Returns:
            DataFrame with time series data
        """
        from edgar.entity.query import FactQuery
        query = FactQuery(self._facts, self._fact_index)

        # Get facts and limit
        return query \
            .by_concept(concept) \
            .sort_by('filing_date', ascending=False) \
            .to_dataframe('period_end', 'numeric_value', 'fiscal_period', 'fiscal_year') \
            .head(periods)

    # DEI (Document and Entity Information) helpers
    def dei_facts(self, as_of: Optional[date] = None) -> pd.DataFrame:
        """
        Get Document and Entity Information (DEI) facts.

        DEI facts contain company metadata like entity name, trading symbol,
        fiscal year-end, shares outstanding, public float, etc.

        Args:
            as_of: Optional date for point-in-time view (gets latest if not specified)

        Returns:
            DataFrame with DEI facts

        Example:
            # Get latest DEI facts
            dei = facts.dei_facts()

            # Get DEI facts as of specific date
            dei = facts.dei_facts(as_of=date(2024, 12, 31))
        """
        from edgar.entity.query import FactQuery
        query = FactQuery(self._facts, self._fact_index)

        # Get DEI taxonomy facts
        query = query.by_concept('dei:', exact=False)

        if as_of:
            query = query.as_of(as_of)
        else:
            # Get latest instant facts for DEI data
            query = query.latest_instant()

        facts = query.execute()

        if not facts:
            return pd.DataFrame()

        # Convert to simple DataFrame
        records = []
        for fact in facts:
            records.append({
                'concept': fact.concept,
                'label': fact.label,
                'value': fact.get_formatted_value(),
                'raw_value': fact.numeric_value or fact.value,
                'unit': fact.unit,
                'period_end': fact.period_end,
                'filing_date': fact.filing_date,
                'form_type': fact.form_type
            })

        df = pd.DataFrame(records)

        # Sort by concept for consistent ordering
        if not df.empty:
            df = df.sort_values('concept').reset_index(drop=True)

        return df

    def entity_info(self) -> Dict[str, Any]:
        """
        Get key entity information as a clean dictionary.

        Returns:
            Dictionary with entity name, shares outstanding, public float, etc.

        Example:
            info = facts.entity_info()
            print(f"Company: {info.get('entity_name', 'Unknown')}")
            print(f"Shares Outstanding: {info.get('shares_outstanding', 'N/A')}")
        """
        dei_df = self.dei_facts()

        info = {
            'entity_name': self.name,
            'cik': self.cik
        }

        if dei_df.empty:
            return info

        # Map common DEI concepts to friendly keys
        concept_mapping = {
            'dei:EntityCommonStockSharesOutstanding': 'shares_outstanding',
            'dei:EntityPublicFloat': 'public_float',
            'dei:TradingSymbol': 'trading_symbol',
            'dei:EntityFilerCategory': 'filer_category',
            'dei:EntityCurrentReportingStatus': 'reporting_status',
            'dei:EntityWellKnownSeasonedIssuer': 'well_known_seasoned_issuer',
            'dei:EntityVoluntaryFilers': 'voluntary_filer',
            'dei:EntitySmallBusiness': 'small_business',
            'dei:EntityEmergingGrowthCompany': 'emerging_growth_company',
            'dei:EntityShellCompany': 'shell_company'
        }

        for _, row in dei_df.iterrows():
            concept = row['concept']
            if concept in concept_mapping:
                key = concept_mapping[concept]
                info[key] = row['value']
                info[f'{key}_raw'] = row['raw_value']
                info[f'{key}_as_of'] = row['period_end']

        return info

    # Standardized financial concept access methods (FEAT-411)
    def get_revenue(self, period: Optional[str] = None, unit: Optional[str] = None) -> Optional[float]:
        """
        Get standardized revenue value across all companies.

        This method handles various revenue concept names (Revenue, Contract Revenue, Net Sales, etc.)
        and provides consistent access regardless of company-specific naming conventions.

        Args:
            period: Optional period in format "YYYY-QN" or "YYYY-FY"
            unit: Optional unit filter (defaults to USD if not specified)

        Returns:
            Revenue value as float, or None if not found

        Example:
            >>> revenue = facts.get_revenue()
            >>> quarterly_revenue = facts.get_revenue(period="2024-Q1")
        """
        return self._get_standardized_concept_value(
            concept_variants=[
                'RevenueFromContractWithCustomerExcludingAssessedTax',
                'SalesRevenueNet',
                'Revenues',
                'Revenue',
                'TotalRevenues',
                'NetSales'
            ],
            period=period,
            unit=unit,
            fallback_calculation=self._calculate_revenue_from_components,
            strict_unit_match=True
        )

    def get_net_income(self, period: Optional[str] = None, unit: Optional[str] = None) -> Optional[float]:
        """
        Get standardized net income value across all companies.

        Handles various net income concept names and provides consistent access.

        Args:
            period: Optional period in format "YYYY-QN" or "YYYY-FY"
            unit: Optional unit filter (defaults to USD if not specified)

        Returns:
            Net income value as float, or None if not found

        Example:
            >>> net_income = facts.get_net_income()
            >>> annual_income = facts.get_net_income(period="2024-FY")
        """
        return self._get_standardized_concept_value(
            concept_variants=[
                'NetIncomeLoss',
                'ProfitLoss',
                'NetIncome',
                'NetEarnings',
                'NetIncomeLossAttributableToParent'
            ],
            period=period,
            unit=unit
        )

    def get_total_assets(self, period: Optional[str] = None, unit: Optional[str] = None) -> Optional[float]:
        """
        Get standardized total assets value across all companies.

        Args:
            period: Optional period in format "YYYY-QN" or "YYYY-FY"
            unit: Optional unit filter (defaults to USD if not specified)

        Returns:
            Total assets value as float, or None if not found

        Example:
            >>> assets = facts.get_total_assets()
            >>> q4_assets = facts.get_total_assets(period="2024-Q4")
        """
        return self._get_standardized_concept_value(
            concept_variants=[
                'Assets',
                'TotalAssets',
                'AssetsCurrent'  # Fallback for some filings
            ],
            period=period,
            unit=unit
        )

    def get_total_liabilities(self, period: Optional[str] = None, unit: Optional[str] = None) -> Optional[float]:
        """
        Get standardized total liabilities value across all companies.

        Args:
            period: Optional period in format "YYYY-QN" or "YYYY-FY"
            unit: Optional unit filter (defaults to USD if not specified)

        Returns:
            Total liabilities value as float, or None if not found

        Example:
            >>> liabilities = facts.get_total_liabilities()
        """
        return self._get_standardized_concept_value(
            concept_variants=[
                'Liabilities',
                'TotalLiabilities',
                'LiabilitiesAndStockholdersEquity'  # Some companies structure it this way
            ],
            period=period,
            unit=unit
        )

    def get_shareholders_equity(self, period: Optional[str] = None, unit: Optional[str] = None) -> Optional[float]:
        """
        Get standardized shareholders equity value across all companies.

        Args:
            period: Optional period in format "YYYY-QN" or "YYYY-FY"
            unit: Optional unit filter (defaults to USD if not specified)

        Returns:
            Shareholders equity value as float, or None if not found

        Example:
            >>> equity = facts.get_shareholders_equity()
        """
        return self._get_standardized_concept_value(
            concept_variants=[
                'StockholdersEquity',
                'ShareholdersEquity',
                'TotalEquity',
                'PartnersCapital',  # For partnerships
                'MembersEquity'     # For LLCs
            ],
            period=period,
            unit=unit
        )

    def get_operating_income(self, period: Optional[str] = None, unit: Optional[str] = None) -> Optional[float]:
        """
        Get standardized operating income value across all companies.

        Args:
            period: Optional period in format "YYYY-QN" or "YYYY-FY"
            unit: Optional unit filter (defaults to USD if not specified)

        Returns:
            Operating income value as float, or None if not found

        Example:
            >>> op_income = facts.get_operating_income()
        """
        return self._get_standardized_concept_value(
            concept_variants=[
                'OperatingIncomeLoss',
                'OperatingIncome',
                'IncomeLossFromOperations',
                'OperatingProfit'
            ],
            period=period,
            unit=unit
        )

    def get_gross_profit(self, period: Optional[str] = None, unit: Optional[str] = None) -> Optional[float]:
        """
        Get standardized gross profit value across all companies.

        Args:
            period: Optional period in format "YYYY-QN" or "YYYY-FY"
            unit: Optional unit filter (defaults to USD if not specified)

        Returns:
            Gross profit value as float, or None if not found

        Example:
            >>> gross_profit = facts.get_gross_profit()
        """
        return self._get_standardized_concept_value(
            concept_variants=[
                'GrossProfit',
                'GrossMargin'
            ],
            period=period,
            unit=unit,
            fallback_calculation=self._calculate_gross_profit_from_components
        )

    # Convenient properties for common DEI facts
    @property
    def shares_outstanding(self) -> Optional[float]:
        """
        Get the most recent shares outstanding value.

        Returns:
            Number of shares outstanding as float, or None if not available

        Example:
            shares = facts.shares_outstanding
            if shares:
                print(f"Shares Outstanding: {shares:,.0f}")
        """
        fact = self.get_fact('dei:EntityCommonStockSharesOutstanding')
        return fact.numeric_value if fact else None

    @property
    def public_float(self) -> Optional[float]:
        """
        Get the most recent public float value.

        Returns:
            Public float value as float, or None if not available

        Example:
            float_val = facts.public_float
            if float_val:
                print(f"Public Float: ${float_val:,.0f}")
        """
        fact = self.get_fact('dei:EntityPublicFloat')
        return fact.numeric_value if fact else None

    @property
    def shares_outstanding_fact(self) -> Optional[FinancialFact]:
        """
        Get the most recent shares outstanding fact with full context.

        Returns:
            FinancialFact object with shares outstanding data, or None

        Example:
            fact = facts.shares_outstanding_fact
            if fact:
                print(f"Shares: {fact.get_formatted_value()} as of {fact.period_end}")
        """
        return self.get_fact('dei:EntityCommonStockSharesOutstanding')

    @property
    def public_float_fact(self) -> Optional[FinancialFact]:
        """
        Get the most recent public float fact with full context.

        Returns:
            FinancialFact object with public float data, or None

        Example:
            fact = facts.public_float_fact
            if fact:
                print(f"Float: {fact.get_formatted_value()} as of {fact.period_end}")
        """
        return self.get_fact('dei:EntityPublicFloat')

    # Financial statement helpers
    def income_statement(self, periods: int = 4, period_length: Optional[int] = None, as_dataframe: bool = False,
                         annual: bool = True, concise_format: bool = False) -> Union[DataFrame, MultiPeriodStatement]:
        """
        Get income statement facts for recent periods.

        Args:
            periods: Number of periods to retrieve
            period_length: Optional filter for period length in months (3=quarterly, 12=annual)
            as_dataframe: If True, return DataFrame; if False, return MultiPeriodStatement
            annual: If True, prefer annual (FY) periods over interim periods
            concise_format: If True, display values as $1.0B, if False display as $1,000,000,000

        Returns:
            MultiPeriodStatement or DataFrame with income statement data

        Example:
            # Get hierarchical multi-period statement (default)
            stmt = facts.income_statement(periods=4, annual=True)
            print(stmt)  # Rich display with hierarchy

            # Get with concise format
            stmt = facts.income_statement(periods=4, concise_format=True)

            # Get DataFrame for analysis
            df = facts.income_statement(periods=4, as_dataframe=True)

            # Convert statement to DataFrame later
            stmt = facts.income_statement(periods=4)
            df = stmt.to_dataframe()
        """
        # Always build the enhanced multi-period statement
        from edgar.entity.enhanced_statement import EnhancedStatementBuilder
        builder = EnhancedStatementBuilder()
        enhanced_stmt = builder.build_multi_period_statement(
            facts=self._facts,
            statement_type='IncomeStatement',
            periods=periods,
            annual=annual
        )
        enhanced_stmt.company_name = self.name
        enhanced_stmt.cik = str(self.cik)
        enhanced_stmt.concise_format = concise_format

        # Return DataFrame if requested
        if as_dataframe:
            return enhanced_stmt.to_dataframe()

        return enhanced_stmt

    def balance_sheet(self, periods: int = 4, as_of: Optional[date] = None, as_dataframe: bool = False,
                      annual: bool = True, concise_format: bool = False) -> Union[pd.DataFrame, MultiPeriodStatement]:
        """
        Get balance sheet facts for recent periods or as of a specific date.

        Args:
            periods: Number of periods to retrieve (ignored if as_of is specified)
            as_of: Optional date for point-in-time view; if specified, gets single snapshot
            as_dataframe: If True, return DataFrame; if False, return MultiPeriodStatement
            annual: If True, prefer annual (FY) periods over interim periods
            concise_format: If True, display values as $1.0B, if False display as $1,000,000,000

        Returns:
            MultiPeriodStatement or DataFrame with balance sheet data

        Example:
            # Get hierarchical multi-period statement (default)
            stmt = facts.balance_sheet(periods=4, annual=True)
            print(stmt)  # Rich display with hierarchy

            # Get DataFrame for analysis
            df = facts.balance_sheet(periods=4, as_dataframe=True)

            # Convert statement to DataFrame later
            stmt = facts.balance_sheet(periods=4)
            df = stmt.to_dataframe()
        """
        if not as_of:
            # Always build the enhanced multi-period statement for regular periods
            from edgar.entity.enhanced_statement import EnhancedStatementBuilder
            builder = EnhancedStatementBuilder()
            enhanced_stmt = builder.build_multi_period_statement(
                facts=self._facts,
                statement_type='BalanceSheet',
                periods=periods,
                annual=annual
            )
            enhanced_stmt.company_name = self.name
            enhanced_stmt.cik = str(self.cik)
            enhanced_stmt.concise_format = concise_format

            # Return DataFrame if requested
            if as_dataframe:
                return enhanced_stmt.to_dataframe()

            return enhanced_stmt
        from edgar.entity.query import FactQuery
        query = FactQuery(self._facts, self._fact_index)

        query = query.by_statement_type('BalanceSheet')

        if as_of:
            # Point-in-time view - get latest instant facts as of the specified date
            query = query.as_of(as_of).latest_instant()
            facts = query.execute()

            if not facts:
                if not as_dataframe:
                    from edgar.entity.statement import FinancialStatement
                    return FinancialStatement(
                        data=pd.DataFrame(),
                        statement_type="BalanceSheet",
                        entity_name=self.name,
                        period_lengths=[],
                        mixed_periods=False
                    )
                else:
                    return pd.DataFrame()

            # Convert to simple DataFrame for point-in-time view
            records = []
            for fact in facts:
                records.append({
                    'label': fact.label,
                    'concept': fact.concept,
                    'value': fact.get_formatted_value(),
                    'raw_value': fact.numeric_value or fact.value,
                    'unit': fact.unit,
                    'period_end': fact.period_end,
                    'filing_date': fact.filing_date,
                    'form_type': fact.form_type
                })

            df = pd.DataFrame(records)

            if not as_dataframe:
                from edgar.entity.statement import FinancialStatement
                # For point-in-time, create a single-column statement
                if not df.empty:
                    period_label = f"As of {as_of}"
                    pivot_data = pd.DataFrame({
                        period_label: df.set_index('label')['raw_value']
                    })
                else:
                    pivot_data = pd.DataFrame()

                return FinancialStatement(
                    data=pivot_data,
                    statement_type="BalanceSheet",
                    entity_name=self.name,
                    period_lengths=['instant'],
                    mixed_periods=False
                )
            else:
                return df
        else:
            # Multi-period view - get trends over time using latest instant facts per period
            # Pass entity information and return preference (flip the boolean)
            result = query.latest_periods(periods, annual=annual).pivot_by_period(
                return_statement=not as_dataframe)

            # If returning a Statement object, set the entity name
            if not as_dataframe and hasattr(result, 'entity_name'):
                result.entity_name = self.name

            return result

    def cash_flow(self, periods: int = 4, period_length: Optional[int] = None, as_dataframe: bool = False,
                  annual: bool = True, concise_format: bool = False) -> Union[DataFrame, MultiPeriodStatement]:
        """
        Get cash flow statement facts.

        Args:
            periods: Number of periods to retrieve
            period_length: Optional filter for period length in months (3=quarterly, 12=annual)
            as_dataframe: If True, return DataFrame; if False, return MultiPeriodStatement
            annual: If True, prefer annual (FY) periods over interim periods
            concise_format: If True, display values as $1.0B, if False display as $1,000,000,000

        Returns:
            MultiPeriodStatement or DataFrame with cash flow data

        Example:
            # Get hierarchical multi-period statement (default)
            stmt = facts.cash_flow(periods=4, annual=True)
            print(stmt)  # Rich display with hierarchy

            # Get DataFrame for analysis
            df = facts.cash_flow(periods=4, as_dataframe=True)

            # Convert statement to DataFrame later
            stmt = facts.cash_flow(periods=4)
            df = stmt.to_dataframe()
        """
        # Always build the enhanced multi-period statement
        from edgar.entity.enhanced_statement import EnhancedStatementBuilder
        builder = EnhancedStatementBuilder()
        enhanced_stmt = builder.build_multi_period_statement(
            facts=self._facts,
            statement_type='CashFlow',
            periods=periods,
            annual=annual
        )
        enhanced_stmt.company_name = self.name
        enhanced_stmt.cik = str(self.cik)
        enhanced_stmt.concise_format = concise_format

        # Return DataFrame if requested
        if as_dataframe:
            return enhanced_stmt.to_dataframe()

        return enhanced_stmt

    # Investment analytics
    def calculate_ratios(self) -> Dict[str, float]:
        """
        Calculate common financial ratios.

        Returns:
            Dictionary of ratio names to values
        """
        # This will be implemented in Phase 3
        # For now, return a placeholder
        return {
            "note": "Ratio calculation will be implemented in Phase 3"
        }

    def peer_comparison(self, peer_ciks: List[int],
                        metrics: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Compare key metrics with peer companies.

        Args:
            peer_ciks: List of peer company CIKs
            metrics: Optional list of specific metrics to compare

        Returns:
            DataFrame with comparative analysis
        """
        # This will be implemented in Phase 3
        # For now, return a placeholder
        return pd.DataFrame({
            "note": ["Peer comparison will be implemented in Phase 3"]
        })

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detect unusual patterns or potential red flags.

        Returns:
            List of detected anomalies with descriptions
        """
        # This will be implemented in Phase 3
        # For now, return a placeholder
        return [{
            "type": "placeholder",
            "message": "Anomaly detection will be implemented in Phase 3"
        }]

    # AI-ready methods
    def to_llm_context(self,
                       focus_areas: Optional[List[str]] = None,
                       time_period: str = "recent") -> Dict[str, Any]:
        """
        Generate comprehensive context for LLM analysis.

        Args:
            focus_areas: Specific areas to emphasize (e.g., ['profitability', 'growth'])
            time_period: Time period to analyze ('recent', '5Y', '10Y', 'all')

        Returns:
            Dictionary with structured context for LLM consumption
        """
        context = {
            "company": {
                "name": self.name,
                "cik": self.cik,
                "total_facts": len(self._facts)
            },
            "data_summary": self._generate_data_summary(),
            "recent_filings": self._get_recent_filings_summary(),
            "key_metrics": self._extract_key_metrics(time_period)
        }

        # Add time period context
        if time_period == "recent":
            context["time_period"] = "Most recent reported period"
        elif time_period == "5Y":
            context["time_period"] = "Five year historical view"
        elif time_period == "10Y":
            context["time_period"] = "Ten year historical view"
        else:
            context["time_period"] = "All available historical data"

        # Add focus area analysis if specified
        if focus_areas:
            context["focus_analysis"] = {}
            for area in focus_areas:
                if area == "profitability":
                    context["focus_analysis"][area] = self._analyze_profitability()
                elif area == "growth":
                    context["focus_analysis"][area] = self._analyze_growth()
                elif area == "liquidity":
                    context["focus_analysis"][area] = self._analyze_liquidity()

        return context

    def to_agent_tools(self) -> List[Dict[str, Any]]:
        """
        Export facts as tools for AI agents (MCP-compatible).

        Returns:
            List of tool definitions for agent consumption
        """
        return [
            {
                "name": f"get_{self.name.lower().replace(' ', '_')}_financials",
                "description": f"Retrieve financial data for {self.name}",
                "parameters": {
                    "statement": {
                        "type": "string",
                        "description": "Financial statement type (income_statement, balance_sheet, cash_flow)",
                        "enum": ["income_statement", "balance_sheet", "cash_flow"]
                    },
                    "periods": {
                        "type": "integer",
                        "description": "Number of periods to retrieve",
                        "default": 4
                    }
                },
                "returns": "Financial data with context"
            },
            {
                "name": f"analyze_{self.name.lower().replace(' ', '_')}_trends",
                "description": f"Analyze financial trends for {self.name}",
                "parameters": {
                    "metric": {
                        "type": "string",
                        "description": "Financial metric to analyze (e.g., Revenue, NetIncome)"
                    },
                    "periods": {
                        "type": "integer",
                        "description": "Number of periods to analyze",
                        "default": 8
                    }
                },
                "returns": "Trend analysis with insights"
            },
            {
                "name": f"get_{self.name.lower().replace(' ', '_')}_fact",
                "description": f"Get a specific financial fact for {self.name}",
                "parameters": {
                    "concept": {
                        "type": "string",
                        "description": "The financial concept to retrieve (e.g., Revenue, Assets)"
                    },
                    "period": {
                        "type": "string",
                        "description": "Optional period (e.g., 2024-Q4, 2024-FY)",
                        "required": False
                    }
                },
                "returns": "Fact value with full context"
            }
        ]

    # Helper methods
    def _generate_data_summary(self) -> Dict[str, Any]:
        """Generate a summary of available data"""
        unique_concepts = len(set(f.concept for f in self._facts))

        # Get date range
        dates = [f.filing_date for f in self._facts if f.filing_date]
        if dates:
            min_date = min(dates)
            max_date = max(dates)
            date_range = f"{min_date} to {max_date}"
        else:
            date_range = "Unknown"

        # Count by form type
        form_counts = defaultdict(int)
        for fact in self._facts:
            form_counts[fact.form_type] += 1

        return {
            "total_facts": len(self._facts),
            "unique_concepts": unique_concepts,
            "date_range": date_range,
            "form_types": dict(form_counts),
            "fiscal_years": sorted(set(f.fiscal_year for f in self._facts if f.fiscal_year))
        }

    def _get_recent_filings_summary(self) -> List[Dict[str, Any]]:
        """Get summary of recent filings"""
        # Group facts by filing
        filings = defaultdict(list)
        for fact in self._facts:
            key = (fact.form_type, fact.filing_date, fact.accession)
            filings[key].append(fact)

        # Sort by filing date
        recent_filings = sorted(filings.keys(), key=lambda x: x[1] or date.min, reverse=True)[:5]

        summaries = []
        for form_type, filing_date, accession in recent_filings:
            summaries.append({
                "form": form_type,
                "date": str(filing_date) if filing_date else "Unknown",
                "fact_count": len(filings[(form_type, filing_date, accession)])
            })

        return summaries

    def _extract_key_metrics(self, time_period: str) -> Dict[str, Any]:
        """Extract key financial metrics for the specified time period"""
        # Define key metrics to extract
        key_concepts = [
            'Revenue', 'NetIncome', 'Assets', 'Liabilities',
            'StockholdersEquity', 'OperatingIncome', 'EarningsPerShare'
        ]

        metrics = {}
        for concept in key_concepts:
            fact = self.get_fact(concept)
            if fact:
                metrics[concept] = {
                    "value": fact.numeric_value or fact.value,
                    "unit": fact.unit,
                    "period": f"{fact.fiscal_period} {fact.fiscal_year}",
                    "quality": fact.data_quality.value
                }

        return metrics

    def _analyze_profitability(self) -> Dict[str, Any]:
        """Analyze profitability metrics"""
        revenue = self.get_fact('Revenue')
        net_income = self.get_fact('NetIncome')

        analysis = {}

        if revenue and net_income and revenue.numeric_value and net_income.numeric_value:
            net_margin = (net_income.numeric_value / revenue.numeric_value) * 100
            analysis["net_margin"] = {
                "value": round(net_margin, 2),
                "unit": "percent",
                "interpretation": f"For every dollar of revenue, {self.name} generates ${net_margin / 100:.2f} in profit"
            }

        return analysis

    def _analyze_growth(self) -> Dict[str, Any]:
        """Analyze growth trends"""
        # Get revenue time series
        revenue_series = self.time_series('Revenue', periods=8)

        if len(revenue_series) >= 2:
            # Calculate year-over-year growth
            latest = revenue_series.iloc[0]['numeric_value']
            prior = revenue_series.iloc[1]['numeric_value']

            if prior and prior != 0:
                growth_rate = ((latest - prior) / prior) * 100
                return {
                    "revenue_growth_yoy": {
                        "value": round(growth_rate, 2),
                        "unit": "percent",
                        "period_comparison": f"{revenue_series.iloc[0]['fiscal_period']} vs {revenue_series.iloc[1]['fiscal_period']}"
                    }
                }

        return {"message": "Insufficient data for growth analysis"}

    def _analyze_liquidity(self) -> Dict[str, Any]:
        """Analyze liquidity metrics"""
        current_assets = self.get_fact('CurrentAssets')
        current_liabilities = self.get_fact('CurrentLiabilities')

        if current_assets and current_liabilities and current_assets.numeric_value and current_liabilities.numeric_value:
            current_ratio = current_assets.numeric_value / current_liabilities.numeric_value
            return {
                "current_ratio": {
                    "value": round(current_ratio, 2),
                    "interpretation": f"{self.name} has ${current_ratio:.2f} in current assets for every $1 of current liabilities"
                }
            }

        return {"message": "Insufficient data for liquidity analysis"}

    # Helper methods for standardized concept access (FEAT-411)
    def _get_standardized_concept_value(self,
                                      concept_variants: List[str],
                                      period: Optional[str] = None,
                                      unit: Optional[str] = None,
                                      fallback_calculation: Optional[callable] = None,
                                      return_detailed: bool = False,
                                      strict_unit_match: bool = False) -> Optional[float]:
        """
        Core method for retrieving standardized concept values with enhanced unit handling.

        Args:
            concept_variants: List of concept names to try in priority order
            period: Optional period filter
            unit: Optional unit filter (defaults to USD)
            fallback_calculation: Optional function to calculate value from components
            return_detailed: If True, return UnitResult instead of just value
            strict_unit_match: If True, require exact unit match. If False, allow compatible units.

        Returns:
            Numeric value or None if not found (or UnitResult if return_detailed=True)
        """
        from edgar.entity.unit_handling import UnitNormalizer, UnitResult

        # Default to USD if no unit specified
        target_unit = unit or 'USD'

        # Try each concept variant in priority order
        for concept in concept_variants:
            # Try both with and without namespace prefix
            for concept_variant in [concept, f'us-gaap:{concept}']:
                fact = self.get_fact(concept_variant, period)
                if fact and fact.numeric_value is not None:
                    # Use enhanced unit handling
                    unit_result = UnitNormalizer.get_normalized_value(
                        fact=fact,
                        target_unit=target_unit,
                        apply_scale=True,
                        strict_unit_match=strict_unit_match
                    )

                    if unit_result.success:
                        if return_detailed:
                            return unit_result
                        return unit_result.value

        # Try fallback calculation if provided
        if fallback_calculation:
            try:
                fallback_value = fallback_calculation(period, target_unit)
                if fallback_value is not None:
                    if return_detailed:
                        return UnitResult(
                            value=fallback_value,
                            normalized_unit=UnitNormalizer.normalize_unit(target_unit),
                            original_unit=target_unit,
                            success=True,
                            error_reason="Calculated from components"
                        )
                    return fallback_value
            except Exception as e:
                # Fallback calculation failed, continue
                if return_detailed:
                    return UnitResult(
                        value=None,
                        normalized_unit=None,
                        original_unit=target_unit or "",
                        success=False,
                        error_reason=f"Fallback calculation failed: {str(e)}"
                    )

        # No value found
        if return_detailed:
            return UnitResult(
                value=None,
                normalized_unit=None,
                original_unit=target_unit or "",
                success=False,
                error_reason="No matching concept found",
                suggestions=["Try checking if company uses alternative concept names"]
            )

        return None

    def _calculate_revenue_from_components(self, period: Optional[str] = None, unit: str = 'USD') -> Optional[float]:
        """
        Calculate revenue from Gross Profit + Cost of Revenue when explicit revenue not available.

        This follows the same logic as the enhanced_statement.py revenue deduplication.
        """
        from edgar.entity.unit_handling import UnitNormalizer

        gross_profit_fact = self.get_fact('GrossProfit', period)
        cost_of_revenue_fact = self.get_fact('CostOfRevenue', period)

        # Try alternative cost concepts
        if not cost_of_revenue_fact:
            for cost_concept in ['CostOfGoodsAndServicesSold', 'CostOfGoodsSold', 'CostOfSales']:
                cost_of_revenue_fact = self.get_fact(cost_concept, period)
                if cost_of_revenue_fact:
                    break

        if (gross_profit_fact and cost_of_revenue_fact and
            gross_profit_fact.numeric_value is not None and
            cost_of_revenue_fact.numeric_value is not None):

            # Use enhanced unit compatibility checking
            gp_result = UnitNormalizer.get_normalized_value(gross_profit_fact, target_unit=unit, apply_scale=True, strict_unit_match=True)
            cr_result = UnitNormalizer.get_normalized_value(cost_of_revenue_fact, target_unit=unit, apply_scale=True, strict_unit_match=True)

            if gp_result.success and cr_result.success:
                return gp_result.value + cr_result.value

            # Try compatibility check if direct match failed
            if UnitNormalizer.are_compatible(gross_profit_fact.unit, cost_of_revenue_fact.unit):
                # Same unit type but different representations - try calculation anyway
                gp_normalized = UnitNormalizer.get_normalized_value(gross_profit_fact, apply_scale=True, strict_unit_match=False)
                cr_normalized = UnitNormalizer.get_normalized_value(cost_of_revenue_fact, apply_scale=True, strict_unit_match=False)

                if gp_normalized.success and cr_normalized.success:
                    return gp_normalized.value + cr_normalized.value

        return None

    def _calculate_gross_profit_from_components(self, period: Optional[str] = None, unit: str = 'USD') -> Optional[float]:
        """
        Calculate gross profit from Revenue - Cost of Revenue when explicit gross profit not available.
        """
        from edgar.entity.unit_handling import UnitNormalizer

        # Try to get revenue using standardized method (but avoid infinite recursion)
        revenue_fact = None
        for concept in ['RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'Revenues', 'Revenue']:
            revenue_fact = self.get_fact(concept, period)
            if revenue_fact:
                break

        cost_of_revenue_fact = self.get_fact('CostOfRevenue', period)

        # Try alternative cost concepts
        if not cost_of_revenue_fact:
            for cost_concept in ['CostOfGoodsAndServicesSold', 'CostOfGoodsSold', 'CostOfSales']:
                cost_of_revenue_fact = self.get_fact(cost_concept, period)
                if cost_of_revenue_fact:
                    break

        if (revenue_fact and cost_of_revenue_fact and
            revenue_fact.numeric_value is not None and
            cost_of_revenue_fact.numeric_value is not None):

            # Use enhanced unit compatibility checking
            rev_result = UnitNormalizer.get_normalized_value(revenue_fact, target_unit=unit, apply_scale=True)
            cr_result = UnitNormalizer.get_normalized_value(cost_of_revenue_fact, target_unit=unit, apply_scale=True)

            if rev_result.success and cr_result.success:
                return rev_result.value - cr_result.value

            # Try compatibility check if direct match failed
            if UnitNormalizer.are_compatible(revenue_fact.unit, cost_of_revenue_fact.unit):
                # Same unit type but different representations - try calculation anyway
                rev_normalized = UnitNormalizer.get_normalized_value(revenue_fact, apply_scale=True)
                cr_normalized = UnitNormalizer.get_normalized_value(cost_of_revenue_fact, apply_scale=True)

                if rev_normalized.success and cr_normalized.success:
                    return rev_normalized.value - cr_normalized.value

        return None

    def get_concept_mapping_info(self, concept_variants: List[str]) -> Dict[str, Any]:
        """
        Get information about which concept variants are available for this company.

        Useful for debugging standardized method behavior and understanding
        company-specific concept usage.

        Args:
            concept_variants: List of concept names to check

        Returns:
            Dictionary with availability and confidence information

        Example:
            >>> info = facts.get_concept_mapping_info(['Revenue', 'Revenues', 'NetSales'])
            >>> print(f"Available concepts: {info['available']}")
        """
        info = {
            'available': [],
            'missing': [],
            'fact_details': {}
        }

        for concept in concept_variants:
            fact = self.get_fact(concept)
            if fact:
                info['available'].append(concept)
                info['fact_details'][concept] = {
                    'label': fact.label,
                    'unit': fact.unit,
                    'latest_period': f"{fact.fiscal_period} {fact.fiscal_year}",
                    'latest_value': fact.numeric_value,
                    'filing_date': fact.filing_date
                }
            else:
                info['missing'].append(concept)

        return info

    # Enhanced methods with detailed unit information (FEAT-411 Unit Handling)
    def get_revenue_detailed(self, period: Optional[str] = None, unit: Optional[str] = None):
        """
        Get revenue with detailed unit information and error reporting.

        Args:
            period: Optional period in format "YYYY-QN" or "YYYY-FY"
            unit: Optional unit filter (defaults to USD)

        Returns:
            UnitResult with value, unit info, and error details

        Example:
            >>> result = facts.get_revenue_detailed()
            >>> if result.success:
            ...     print(f"Revenue: ${result.value/1e9:.1f}B (unit: {result.normalized_unit})")
            ... else:
            ...     print(f"Error: {result.error_reason}")
            ...     for suggestion in result.suggestions:
            ...         print(f"  - {suggestion}")
        """
        return self._get_standardized_concept_value(
            concept_variants=[
                'RevenueFromContractWithCustomerExcludingAssessedTax',
                'SalesRevenueNet',
                'Revenues',
                'Revenue',
                'TotalRevenues',
                'NetSales'
            ],
            period=period,
            unit=unit,
            fallback_calculation=self._calculate_revenue_from_components,
            return_detailed=True
        )

    def get_net_income_detailed(self, period: Optional[str] = None, unit: Optional[str] = None):
        """
        Get net income with detailed unit information and error reporting.

        Args:
            period: Optional period in format "YYYY-QN" or "YYYY-FY"
            unit: Optional unit filter (defaults to USD)

        Returns:
            UnitResult with value, unit info, and error details
        """
        return self._get_standardized_concept_value(
            concept_variants=[
                'NetIncomeLoss',
                'ProfitLoss',
                'NetIncome',
                'NetEarnings',
                'NetIncomeLossAttributableToParent'
            ],
            period=period,
            unit=unit,
            return_detailed=True
        )

    def check_unit_compatibility(self, concept1: str, concept2: str, period: Optional[str] = None) -> Dict[str, Any]:
        """
        Check unit compatibility between two concepts for calculations.

        Args:
            concept1: First concept name
            concept2: Second concept name
            period: Optional period filter

        Returns:
            Dictionary with compatibility info and suggestions

        Example:
            >>> compat = facts.check_unit_compatibility('Revenue', 'CostOfRevenue')
            >>> if compat['compatible']:
            ...     print("Units are compatible for calculations")
            ... else:
            ...     print(f"Unit issue: {compat['issue']}")
        """
        from edgar.entity.unit_handling import UnitNormalizer

        fact1 = self.get_fact(concept1, period)
        fact2 = self.get_fact(concept2, period)

        result = {
            'compatible': False,
            'concept1': concept1,
            'concept2': concept2,
            'fact1_found': fact1 is not None,
            'fact2_found': fact2 is not None,
            'issue': None,
            'suggestions': []
        }

        if not fact1:
            result['issue'] = f"Concept '{concept1}' not found"
            result['suggestions'].append(f"Check if {concept1} exists for this company")
            return result

        if not fact2:
            result['issue'] = f"Concept '{concept2}' not found"
            result['suggestions'].append(f"Check if {concept2} exists for this company")
            return result

        # Check unit compatibility
        compatible = UnitNormalizer.are_compatible(fact1.unit, fact2.unit)
        result['compatible'] = compatible

        result['fact1_unit'] = fact1.unit
        result['fact2_unit'] = fact2.unit
        result['fact1_normalized'] = UnitNormalizer.normalize_unit(fact1.unit)
        result['fact2_normalized'] = UnitNormalizer.normalize_unit(fact2.unit)

        if not compatible:
            result['issue'] = f"Incompatible units: {fact1.unit} vs {fact2.unit}"

            unit1_type = UnitNormalizer.get_unit_type(fact1.unit)
            unit2_type = UnitNormalizer.get_unit_type(fact2.unit)

            if unit1_type != unit2_type:
                result['suggestions'].append(f"Unit type mismatch: {unit1_type.value} vs {unit2_type.value}")
            else:
                result['suggestions'].append("Same unit type but different representations")

        return result

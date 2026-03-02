"""
Core entity classes for working with SEC filings.

This module provides the main classes for interacting with SEC entities,
including companies, funds, and individuals.
"""
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import date
from functools import cached_property
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple, TypeVar, Union

import pyarrow as pa

if TYPE_CHECKING:
    import pandas as pd
    from edgar.entity.enhanced_statement import MultiPeriodStatement, StructuredStatement
    from edgar.entity.filings import EntityFilings
    from edgar.enums import FilerCategory, FormType, PeriodType

from rich import box
from rich.columns import Columns
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar._filings import Filings
from edgar.company_reports import TenK, TenQ
from edgar.display.styles import get_style, SYMBOLS
from edgar.entity.data import Address, CompanyData, EntityData
from edgar.entity.entity_facts import EntityFacts, NoCompanyFactsFound, get_company_facts
from edgar.entity.tickers import get_icon_from_ticker
from edgar.financials import Financials
from edgar.display.formatting import cik_text, datefmt, reverse_name
from edgar.reference.tickers import find_cik
from edgar.richtools import Docs, repr_rich

if TYPE_CHECKING:
    from edgar.enums import FormType

# Import constants and utilities from separate modules
from edgar.entity.constants import COMPANY_FORMS
from edgar.entity.utils import has_company_filings, normalize_cik

# TTM (Trailing Twelve Months) imports
from edgar.ttm.calculator import TTMCalculator, TTMMetric
from edgar.ttm.statement import TTMStatement, TTMStatementBuilder
from edgar.ttm.splits import detect_splits, apply_split_adjustments

# Type variables for better type annotations
T = TypeVar('T')

__all__ = [
    'SecFiler',
    'Entity',
    'Company',
    'CompanyNotFoundError',
    'EntityData',
    'CompanyData',
    'ConceptList',
    'get_entity',
    'get_company',
    'NoCompanyFactsFound',
    'has_company_filings',
    'COMPANY_FORMS',
]


class CompanyNotFoundError(Exception):
    """Raised when a company cannot be found by ticker, CIK, or name."""

    def __init__(self, identifier, suggestions=None):
        self.identifier = identifier
        self.suggestions = suggestions or []
        super().__init__(str(self))

    def __str__(self):
        msg = f"Company not found: '{self.identifier}'"
        if self.suggestions:
            suggestions_str = ", ".join(
                f"'{s['ticker']}' ({s['company']})" for s in self.suggestions[:3]
            )
            msg += f"\n  Similar: {suggestions_str}"
        msg += "\n  Tip: Search by name with find_company(\"...\") or pass a CIK directly."
        return msg


def _get_suggestions(identifier: str, max_suggestions: int = 3):
    """Get fuzzy-match suggestions for a failed company lookup."""
    try:
        from edgar.entity.search import _get_company_search_index
        results = _get_company_search_index().search(identifier, top_n=max_suggestions, threshold=40)
        if not results.empty:
            return [{'ticker': row.ticker, 'company': row.company}
                    for _, row in results.results.iterrows()]
    except Exception:
        pass
    return []


class ConceptList:
    """
    A list of XBRL concepts available for a company.

    Provides convenient iteration, display, and conversion methods.

    Example:
        >>> concepts = company.list_concepts(search="revenue")
        >>> concepts  # Rich table display
        >>> for c in concepts:
        ...     print(c['concept'])
        >>> concepts.to_list()  # Get as plain list
        >>> concepts.to_dataframe()  # Get as DataFrame
    """

    def __init__(self, concepts: List[dict], search: Optional[str] = None,
                 statement: Optional[str] = None, company_name: Optional[str] = None):
        self._concepts = concepts
        self._search = search
        self._statement = statement
        self._company_name = company_name

    def __len__(self) -> int:
        return len(self._concepts)

    def __iter__(self):
        return iter(self._concepts)

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._concepts[item]
        elif isinstance(item, slice):
            return ConceptList(
                self._concepts[item],
                search=self._search,
                statement=self._statement,
                company_name=self._company_name
            )
        else:
            raise TypeError(f"indices must be integers or slices, not {type(item).__name__}")

    def __bool__(self) -> bool:
        return len(self._concepts) > 0

    def to_list(self) -> List[dict]:
        """Return concepts as a plain list of dicts."""
        return list(self._concepts)

    def to_dataframe(self) -> "pd.DataFrame":
        """Return concepts as a pandas DataFrame."""
        import pandas as pd
        if not self._concepts:
            return pd.DataFrame(columns=['concept', 'label', 'statements', 'fact_count'])
        return pd.DataFrame(self._concepts)

    def __rich__(self):
        """Rich display with formatted table."""
        # Build title
        title_parts = ["Concepts"]
        if self._company_name:
            title_parts = [f"{self._company_name} Concepts"]
        if self._search:
            title_parts.append(f"matching '{self._search}'")
        if self._statement:
            title_parts.append(f"in {self._statement}")
        title = " ".join(title_parts)

        if not self._concepts:
            return Panel(
                Text("No concepts found", style="dim italic"),
                title=title,
                box=box.ROUNDED
            )

        # Simple list format - full concept names for copy-paste usability
        lines = []
        for c in self._concepts:
            # Format: "  123  us-gaap:ConceptName  Label"
            line = Text.assemble(
                (f"{c['fact_count']:>5}  ", "green"),
                (c['concept'], "cyan"),
                ("  ", ""),
                (c['label'], "dim"),
            )
            line.no_wrap = True
            lines.append(line)

        # Add summary footer
        footer = Text(f"\n{len(self._concepts)} concepts", style="dim")

        return Group(
            Text(title, style="bold deep_sky_blue1"),
            Text(""),
            *lines,
            footer
        )

    def __repr__(self) -> str:
        return repr_rich(self)


class SecFiler(ABC):
    """
    Abstract base class for all SEC filing entities.

    This is the root of the entity hierarchy and defines the common interface
    that all entity types must implement.
    """

    @abstractmethod
    def get_filings(self, **kwargs) -> Filings:
        """Get filings for this entity."""
        pass

    @abstractmethod
    def get_facts(self) -> Optional[EntityFacts]:
        """Get structured facts about this entity."""
        pass

    @property
    @abstractmethod
    def cik(self) -> int:
        """Get the CIK number for this entity."""
        pass

    @property
    @abstractmethod
    def data(self) -> 'EntityData':
        """Get detailed data for this entity."""
        pass


class Entity(SecFiler):
    """
    Represents any entity that files with the SEC.

    This is the base concrete implementation that can be used directly
    or specialized for specific entity types.
    """

    def __init__(self, cik_or_identifier: Union[str, int]):
        # If it's a ticker, convert to CIK first
        if isinstance(cik_or_identifier, str) and not cik_or_identifier.isdigit():
            cik = find_cik(cik_or_identifier)
            if cik is None:
                raise CompanyNotFoundError(
                    cik_or_identifier,
                    suggestions=_get_suggestions(cik_or_identifier)
                )
            self._cik = cik
        else:
            self._cik = normalize_cik(cik_or_identifier)

        self._data = None

    @property
    def cik(self) -> int:
        """Get the CIK number for this entity."""
        return self._cik

    @property
    def name(self):
        """Get the name of the company."""
        if hasattr(self.data, 'name'):
            return self.data.name
        return None

    @cached_property
    def display_name(self) -> str:
        """Reverse the name if it is a company"""
        if self.is_company:
            return self.name
        return reverse_name(self.name)

    @cached_property
    def data(self) -> 'EntityData':
        """Get detailed data for this entity."""
        if self._data is None:
            # Import locally to avoid circular imports
            from edgar.entity.submissions import get_entity_submissions

            # get_entity_submissions returns the EntityData directly
            entity_data = get_entity_submissions(self.cik)

            if entity_data:
                self._data = entity_data
                self._data._not_found = False
            else:
                # Instead of raising an error, create a default EntityData
                #log.warning(f"Could not find entity data for CIK {self.cik}, using placeholder data")
                from edgar.entity.data import create_default_entity_data
                self._data = create_default_entity_data(self.cik)
                self._data._not_found = True
        return self._data

    def mailing_address(self) -> Optional[Address]:
        """Get the mailing address of the entity."""
        if hasattr(self.data, 'mailing_address') and self.data.mailing_address:
            return self.data.mailing_address

    def business_address(self) -> Optional[Address]:
        """Get the business address of the entity."""
        if hasattr(self.data, 'business_address') and self.data.business_address:
            return self.data.business_address


    @property
    def not_found(self) -> bool:
        """
        Check if the entity data was not found.

        Returns:
            True if the entity data could not be found, False otherwise
        """
        if not hasattr(self, '_data') or self._data is None:
            # We haven't loaded the data yet, so we don't know if it's not found
            # Loading the data will set the not_found flag
            _ = self.data

        return getattr(self._data, '_not_found', False)

    @property
    def is_company(self) -> bool:
        """
        Check if this entity is a company.

        Returns:
            True if the entity is a company, False otherwise
        """
        return self.data.is_company

    @property
    def is_individual(self) -> bool:
        """
        Check if this entity is an individual.

        Returns:
            True if the entity is an individual, False otherwise
        """
        return not self.is_company

    @cached_property
    def filer_category(self) -> 'FilerCategory':
        """
        Get the parsed filer category for this entity.

        The SEC classifies filers into categories based on their public float:
        - Large Accelerated Filer: >= $700 million
        - Accelerated Filer: >= $75 million and < $700 million
        - Non-Accelerated Filer: < $75 million

        Additional qualifications may apply:
        - Smaller Reporting Company (SRC)
        - Emerging Growth Company (EGC)

        Returns:
            FilerCategory object with parsed status and qualifications

        Example:
            >>> company = Company("AAPL")
            >>> company.filer_category.status
            <FilerStatus.LARGE_ACCELERATED: 'Large accelerated filer'>
            >>> company.is_large_accelerated_filer
            True
        """
        from edgar.enums import FilerCategory
        category_str = getattr(self.data, 'category', None)
        return FilerCategory.from_string(category_str)

    @property
    def is_large_accelerated_filer(self) -> bool:
        """Check if this entity is a large accelerated filer (public float >= $700M)."""
        return self.filer_category.is_large_accelerated_filer

    @property
    def is_accelerated_filer(self) -> bool:
        """Check if this entity is an accelerated filer (public float >= $75M and < $700M)."""
        return self.filer_category.is_accelerated_filer

    @property
    def is_non_accelerated_filer(self) -> bool:
        """Check if this entity is a non-accelerated filer (public float < $75M)."""
        return self.filer_category.is_non_accelerated_filer

    @property
    def is_smaller_reporting_company(self) -> bool:
        """Check if this entity qualifies as a Smaller Reporting Company (SRC)."""
        return self.filer_category.is_smaller_reporting_company

    @property
    def is_emerging_growth_company(self) -> bool:
        """Check if this entity qualifies as an Emerging Growth Company (EGC)."""
        return self.filer_category.is_emerging_growth_company

    def get_filings(self,
                   *,
                   year: Optional[Union[int, List[int]]] = None,
                   quarter: Optional[Union[int, List[int]]] = None,
                   form: Optional[Union[str, 'FormType', List[Union[str, 'FormType']]]] = None,
                   accession_number: Optional[Union[str, List]] = None,
                   file_number: Optional[Union[str, List]] = None,
                   filing_date: Optional[Union[str, Tuple[str, str]]] = None,
                   date: Optional[Union[str, Tuple[str, str]]] = None,
                   amendments: bool = True,
                   is_xbrl: Optional[bool] = None,
                   is_inline_xbrl: Optional[bool] = None,
                   sort_by: Optional[Union[str, List[Tuple[str, str]]]] = None,
                   trigger_full_load: bool = True) -> 'EntityFilings':
        """
        Get the entity's filings and optionally filter by multiple criteria.

        This method has a special behavior for loading filings. When first called,
        it only loads the most recent filings. If trigger_full_load=True, it will 
        automatically fetch all historical filings from the SEC (potentially making 
        multiple API calls) as needed.

        Args:
            year: The year or list of years to filter by (e.g. 2023, [2022, 2023])
            quarter: The quarter or list of quarters to filter by (1-4, e.g. 4, [3, 4])
            form: The form type (e.g. FormType.ANNUAL_REPORT, '10-K', or ['10-Q', '10-K'])
            accession_number: The accession number that identifies a filing
            file_number: The file number e.g. 001-39504
            filing_date: Filter by filing date (YYYY-MM-DD or range)
            date: Alias for filing_date
            amendments: Whether to include amendments (default: True)
            is_xbrl: Whether the filing is XBRL
            is_inline_xbrl: Whether the filing is Inline XBRL
            sort_by: Sort criteria
            trigger_full_load: Whether to load all historical filings if not already loaded

        Returns:
            Filtered filings matching the criteria
        """
        # Simply delegate to the EntityData implementation
        # This preserves the lazy-loading behavior while keeping the API clean
        return self.data.get_filings(
            year=year,
            quarter=quarter,
            form=form,
            accession_number=accession_number,
            file_number=file_number,
            filing_date=filing_date or date,
            amendments=amendments,
            is_xbrl=is_xbrl,
            is_inline_xbrl=is_inline_xbrl,
            sort_by=sort_by,
            trigger_full_load=trigger_full_load
        )

    def _empty_company_filings(self):
        """
        Create an empty filings container.

        Args:
            cik: The CIK number
            company_name: The company name

        Returns:
            EntityFilings: An empty filings container
        """
        from edgar.entity.filings import COMPANY_FILINGS_SCHEMA, EntityFilings
        table = pa.Table.from_arrays([[] for _ in range(13)], schema=COMPANY_FILINGS_SCHEMA)
        return EntityFilings(table, cik=self.cik, company_name=self.name)

    def get_facts(self, period_type: Optional[Union[str, 'PeriodType']] = None) -> Optional[EntityFacts]:
        """
        Get structured facts about this entity.

        Args:
            period_type: Optional filter by period type. Can be PeriodType enum
                        or string ('annual', 'quarterly', 'monthly').

        Returns:
            EntityFacts object, optionally filtered by period type
        """
        try:
            facts = get_company_facts(self.cik)
            if facts and period_type:
                # Apply period type filtering to the facts
                return facts.filter_by_period_type(period_type)
            return facts
        except NoCompanyFactsFound:
            return None

    def get_structured_statement(self, 
                                statement_type: str,
                                fiscal_year: Optional[int] = None,
                                fiscal_period: Optional[str] = None,
                                use_canonical: bool = True,
                                include_missing: bool = False) -> Optional['StructuredStatement']:
        """
        Get a hierarchically structured financial statement.

        This method uses learned canonical structures to build complete financial
        statements with proper hierarchy and relationships, filling in missing
        concepts when requested.

        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', 'CashFlow')
            fiscal_year: Fiscal year to retrieve (defaults to latest)
            fiscal_period: Fiscal period ('FY', 'Q1', 'Q2', 'Q3', 'Q4')
            use_canonical: Use canonical structure for organization (recommended)
            include_missing: Include placeholders for missing canonical concepts

        Returns:
            StructuredStatement with hierarchical organization or None if no data

        Example:
            >>> company = Company('AAPL')
            >>> stmt = company.get_structured_statement('IncomeStatement', 2024, 'Q4')
            >>> print(stmt.get_hierarchical_display())
        """
        from edgar.entity.statement_builder import StatementBuilder

        facts_data = self.get_facts()
        if not facts_data:
            return None

        # Get all facts
        all_facts = facts_data.get_all_facts()
        if not all_facts:
            return None

        # Build the statement
        builder = StatementBuilder(cik=str(self.cik))
        structured_stmt = builder.build_statement(
            facts=all_facts,
            statement_type=statement_type,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            use_canonical=use_canonical,
            include_missing=include_missing
        )

        # Add company metadata
        structured_stmt.company_name = self.name

        return structured_stmt

    def latest(self, form: str, n=1):
        """Get the latest filing(s) for a given form."""
        filings = self.get_filings(form=form, trigger_full_load=False)
        # If initial load doesn't have enough results, try full load
        if len(filings) < n:
            filings = self.get_filings(form=form, trigger_full_load=True)
        return filings.latest(n)

    def __str__(self):
        if hasattr(self, 'data'):
            return f"Entity({self.data.name} [{self.cik}])"
        return f"Entity(CIK={self.cik})"

    def __rich__(self):
        return self.data.__rich__()

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __bool__(self):
        """
        Allow truthiness check for entities.

        Returns False if the entity was not found via the SEC API (valid CIK but no data).
        This enables code patterns like: `if company: do_something()`
        """
        return not self.not_found


class Company(Entity):
    """
    Represents a public company that files with the SEC.

    Provides company-specific functionality like financial statements,
    ticker lookup, etc.
    """

    def __init__(self, cik_or_ticker: Union[str, int]):


        super().__init__(cik_or_ticker)

    @property
    def data(self) -> 'EntityData':  # We'll return the base type to simplify
        """Get detailed data for this company."""
        # For simplicity, return the base EntityData
        # Type checkers will still see this as a CompanyData due to the annotation
        return super().data

    @property
    def tickers(self):
        """Get all ticker symbols for this company."""
        if hasattr(self.data, 'tickers'):
            return self.data.tickers
        return []

    def get_ticker(self) -> Optional[str]:
        """Get the primary ticker symbol for this company."""
        if self.data and self.data.tickers and len(self.data.tickers) > 0:
            return self.data.tickers[0]
        return None

    def get_exchanges(self ):
        """Get all exchanges for this company."""
        if hasattr(self.data, 'exchanges'):
            return self.data.exchanges
        return []

    def get_financials(self) -> Optional[Financials]:
        """
        Get financial statements from this company's latest 10-K annual report.

        This is the recommended starting point for financial analysis. Returns a
        Financials object with access to income statement, balance sheet, and
        cash flow statement — typically covering 3 years of data.

        Returns:
            Financials object, or None if no 10-K filing is available

        Example::

            financials = Company("AAPL").get_financials()
            financials.income_statement()
            financials.balance_sheet()
            financials.cashflow_statement()
            financials.get_revenue()        # Quick access to a single value
        """
        tenk_filing = self.latest_tenk
        if tenk_filing is not None:
            return tenk_filing.financials
        return None

    def get_quarterly_financials(self) -> Optional[Financials]:
        """
        Get financial statements from this company's latest 10-Q quarterly report.

        Returns a Financials object with the same interface as get_financials(),
        but with quarterly data instead of annual.

        Returns:
            Financials object, or None if no 10-Q filing is available

        Example::

            quarterly = Company("AAPL").get_quarterly_financials()
            quarterly.income_statement()
            quarterly.balance_sheet()
        """
        tenq_filing = self.latest_tenq
        if tenq_filing is not None:
            return tenq_filing.financials
        return None

    @property
    def fiscal_year_end(self):
        """Get the fiscal year end date for this company."""
        if hasattr(self.data, 'fiscal_year_end'):
            return self.data.fiscal_year_end
        return None

    @property
    def sic(self):
        """Get the SIC code for this company."""
        if hasattr(self.data, 'sic'):
            return self.data.sic
        return None

    @property
    def industry(self):
        """Get the industry description for this company."""
        if hasattr(self.data, 'sic_description'):
            return self.data.sic_description
        return None

    @property
    def is_foreign(self) -> bool:
        """
        Check if this company is incorporated outside the United States.

        Uses the SEC state of incorporation code to determine if the company
        is registered in a foreign jurisdiction.

        Returns:
            True if incorporated in a foreign country, False if US or unknown

        Example:
            >>> company = Company('BABA')
            >>> company.is_foreign
            True
            >>> Company('AAPL').is_foreign
            False
        """
        if hasattr(self.data, 'state_of_incorporation') and self.data.state_of_incorporation:
            from edgar.reference._codes import is_foreign_company
            return is_foreign_company(self.data.state_of_incorporation)
        return False

    @property
    def filer_type(self) -> Optional[str]:
        """
        Get the filer type based on state of incorporation.

        Returns:
            'Domestic' - Incorporated in US
            'Canadian' - Incorporated in Canada
            'Foreign' - Incorporated elsewhere
            None - Unknown or state of incorporation not available

        Example:
            >>> Company('AAPL').filer_type
            'Domestic'
            >>> Company('BABA').filer_type
            'Foreign'
            >>> Company('CNQ').filer_type  # Canadian Natural Resources
            'Canadian'
        """
        if hasattr(self.data, 'state_of_incorporation') and self.data.state_of_incorporation:
            from edgar.reference._codes import get_filer_type
            return get_filer_type(self.data.state_of_incorporation)
        return None

    def _get_form_types(self, limit: int = 100) -> set:
        """
        Get unique form types from recent filings efficiently.

        Args:
            limit: Maximum number of recent filings to check

        Returns:
            Set of form type strings (e.g., {'10-K', '10-Q', '8-K'})
        """
        filings = self.get_filings(trigger_full_load=False)
        if filings is None or filings.empty:
            return set()

        form_column = filings.data['form']
        actual_limit = min(limit, len(form_column))
        return set(form_column.slice(0, actual_limit).to_pylist())

    @cached_property
    def business_category(self) -> str:
        """
        Get the primary business category for this company.

        Classification uses multiple signals:
        - SIC code (definitive for REITs, Banks, Insurance, SPACs)
        - SEC form types filed (investment company forms, 13F, N-2)
        - Entity type from SEC data
        - Company name patterns (for disambiguation)

        Returns:
            One of: 'Operating Company', 'ETF', 'Mutual Fund', 'Closed-End Fund',
                   'BDC', 'REIT', 'Investment Manager', 'Bank', 'Insurance Company',
                   'SPAC', 'Holding Company', 'Unknown'

        Example:
            >>> Company('AAPL').business_category
            'Operating Company'

            >>> Company('O').business_category
            'REIT'

            >>> Company('JPM').business_category
            'Bank'
        """
        from edgar.entity.categorization import classify_business_category

        form_types = self._get_form_types()
        entity_type = getattr(self.data, 'entity_type', None)

        return classify_business_category(
            sic=self.sic,
            entity_type=entity_type,
            name=self.name or '',
            form_types=form_types
        )

    def is_fund(self) -> bool:
        """
        Check if company is an investment fund (ETF, Mutual Fund, or Closed-End Fund).

        Returns:
            True if the company is classified as any type of fund

        Example:
            >>> Company('AAPL').is_fund()
            False
        """
        return self.business_category in ['ETF', 'Mutual Fund', 'Closed-End Fund']

    def is_financial_institution(self) -> bool:
        """
        Check if company is a financial institution.

        Includes Banks, Insurance Companies, Investment Managers, and BDCs.

        Returns:
            True if classified as a financial institution

        Example:
            >>> Company('JPM').is_financial_institution()
            True
            >>> Company('AAPL').is_financial_institution()
            False
        """
        return self.business_category in [
            'Bank', 'Insurance Company', 'Investment Manager', 'BDC'
        ]

    def is_operating_company(self) -> bool:
        """
        Check if company is a standard operating company.

        Returns:
            True if classified as an Operating Company

        Example:
            >>> Company('AAPL').is_operating_company()
            True
            >>> Company('JPM').is_operating_company()
            False
        """
        return self.business_category == 'Operating Company'

    @property
    def latest_tenk(self) -> Optional[TenK]:
        """Get the latest unamended 10-K filing for this company."""
        latest_10k = self.get_filings(form='10-K', amendments=False, trigger_full_load=False).latest()
        if latest_10k is not None:
            return latest_10k.obj()
        return None

    @property
    def latest_tenq(self) -> Optional[TenQ]:
        """Get the latest unamended 10-Q filing for this company."""
        latest_10q = self.get_filings(form='10-Q', amendments=False, trigger_full_load=False).latest()
        if latest_10q is not None:
            return latest_10q.obj()
        return None

    def get_icon(self):
        return get_icon_from_ticker(self.tickers[0])

    # Enhanced financial data properties and methods
    def get_facts(self, period_type: Optional[Union[str, 'PeriodType']] = None) -> Optional['EntityFacts']:
        """
        Get structured facts about this company with industry-specific enhancements.

        Overrides Entity.get_facts() to inject SIC code and ticker for industry-specific
        virtual tree extensions.

        Args:
            period_type: Optional filter by period type. Can be PeriodType enum
                        or string ('annual', 'quarterly', 'monthly').

        Returns:
            EntityFacts object with SIC code and ticker set, optionally filtered by period type
        """
        facts = super().get_facts(period_type)
        if facts:
            # Inject SIC code and ticker for industry-specific statement building
            # Ticker is used for curated industries like payment_networks where SIC doesn't map well
            facts._sic_code = self.sic
            facts._ticker = self.tickers[0] if self.tickers else None
        return facts

    @property
    def facts(self) -> Optional['EntityFacts']:
        """Get enhanced structured facts about this company."""
        return self.get_facts()

    @property
    def docs(self):
        """Access comprehensive Company API documentation."""
        return Docs(self)

    @property
    def public_float(self) -> Optional[float]:
        """Get the public float value for this company."""
        facts = self.facts
        if facts:
            return facts.public_float
        return None

    @property
    def shares_outstanding(self) -> Optional[float]:
        """Get the shares outstanding for this company.""" 
        facts = self.facts
        if facts:
            return facts.shares_outstanding
        return None

    def income_statement(
        self,
        periods: int = 4,
        period: str = 'annual',
        annual: Optional[bool] = None,
        as_dataframe: bool = False,
        concise_format: bool = False
    ) -> Union["MultiPeriodStatement", TTMStatement, "pd.DataFrame", None]:
        """
        Get income statement data for this company.

        Args:
            periods: Number of periods to retrieve (default: 4)
            period: 'annual', 'quarterly', or 'ttm' (trailing twelve months)
            annual: Legacy parameter - if provided, overrides period (True='annual', False='quarterly')
            as_dataframe: If True, return DataFrame; if False, return Statement object
            concise_format: If True, display values as $1.0B, if False display as $1,000,000,000

        Returns:
            MultiPeriodStatement, TTMStatement, or DataFrame with income statement data

        Example:
            >>> company = Company("AAPL")
            >>> stmt = company.income_statement(period='ttm')  # Trailing 12 months
            >>> stmt = company.income_statement(period='quarterly', periods=8)
        """
        # Handle legacy parameter
        if annual is not None:
            period = 'annual' if annual else 'quarterly'

        facts = self.facts
        if not facts:
            return None

        try:
            if period == 'ttm':
                # Build TTM statement with split-adjusted facts
                adjusted_facts = self._get_split_adjusted_facts()
                adjusted_facts = self._prepare_quarterly_facts(adjusted_facts)

                # TTMEntityFacts removed - using EntityFacts directly
                ttm_facts = EntityFacts(self.cik, self.name, adjusted_facts, self.sic)
                builder = TTMStatementBuilder(ttm_facts)
                stmt = builder.build_income_statement(max_periods=periods)

                if as_dataframe:
                    return stmt.to_dataframe()
                return stmt

            elif period == 'quarterly':
                # Build quarterly statement with derived Q4
                adjusted_facts = self._get_split_adjusted_facts()
                adjusted_facts = self._prepare_quarterly_facts(adjusted_facts)

                # TTMEntityFacts removed - using EntityFacts directly
                ttm_facts = EntityFacts(self.cik, self.name, adjusted_facts, self.sic)
                return ttm_facts.income_statement(
                    periods=periods,
                    annual=False,
                    as_dataframe=as_dataframe,
                    concise_format=concise_format
                )

            else:  # annual
                return facts.income_statement(
                    periods=periods,
                    annual=True,
                    as_dataframe=as_dataframe,
                    concise_format=concise_format
                )
        except Exception as e:
            from edgar.core import log
            log.debug(f"Error getting income statement for {self.name}: {e}")
        return None

    def balance_sheet(
        self,
        periods: int = 4,
        period: str = 'annual',
        annual: Optional[bool] = None,
        as_dataframe: bool = False,
        concise_format: bool = False
    ) -> Union["MultiPeriodStatement", "pd.DataFrame", None]:
        """
        Get balance sheet data for this company.

        Args:
            periods: Number of periods to retrieve (default: 4)
            period: 'annual' or 'quarterly' (TTM not applicable for balance sheet)
            annual: Legacy parameter - if provided, overrides period
            as_dataframe: If True, return DataFrame; if False, return Statement object
            concise_format: If True, display values as $1.0B, if False display as $1,000,000,000

        Returns:
            MultiPeriodStatement or DataFrame with balance sheet data

        Raises:
            ValueError: If period='ttm' (not applicable for balance sheet)
        """
        if annual is not None:
            period = 'annual' if annual else 'quarterly'

        if period == 'ttm':
            raise ValueError("TTM not applicable for Balance Sheet (point-in-time data)")

        facts = self.facts
        if facts:
            try:
                return facts.balance_sheet(
                    periods=periods,
                    annual=(period == 'annual'),
                    as_dataframe=as_dataframe,
                    concise_format=concise_format
                )
            except Exception as e:
                from edgar.core import log
                log.debug(f"Error getting balance sheet for {self.name}: {e}")
        return None

    def cashflow_statement(
        self,
        periods: int = 4,
        period: str = 'annual',
        annual: Optional[bool] = None,
        as_dataframe: bool = False,
        concise_format: bool = False
    ) -> Union["MultiPeriodStatement", TTMStatement, "pd.DataFrame", None]:
        """
        Get cash flow statement data for this company.

        Args:
            periods: Number of periods to retrieve (default: 4)
            period: 'annual', 'quarterly', or 'ttm' (trailing twelve months)
            annual: Legacy parameter - if provided, overrides period
            as_dataframe: If True, return DataFrame; if False, return Statement object
            concise_format: If True, display values as $1.0B, if False display as $1,000,000,000

        Returns:
            MultiPeriodStatement, TTMStatement, or DataFrame with cash flow data
        """
        if annual is not None:
            period = 'annual' if annual else 'quarterly'

        facts = self.facts
        if not facts:
            return None

        try:
            if period == 'ttm':
                adjusted_facts = self._get_split_adjusted_facts()
                adjusted_facts = self._prepare_quarterly_facts(adjusted_facts)

                # TTMEntityFacts removed - using EntityFacts directly
                ttm_facts = EntityFacts(self.cik, self.name, adjusted_facts, self.sic)
                builder = TTMStatementBuilder(ttm_facts)
                stmt = builder.build_cashflow_statement(max_periods=periods)

                if as_dataframe:
                    return stmt.to_dataframe()
                return stmt

            elif period == 'quarterly':
                # Build quarterly statement with derived Q4
                adjusted_facts = self._get_split_adjusted_facts()
                adjusted_facts = self._prepare_quarterly_facts(adjusted_facts)

                # TTMEntityFacts removed - using EntityFacts directly
                ttm_facts = EntityFacts(self.cik, self.name, adjusted_facts, self.sic)
                return ttm_facts.cashflow_statement(
                    periods=periods,
                    annual=False,
                    as_dataframe=as_dataframe,
                    concise_format=concise_format
                )

            else:  # annual
                return facts.cashflow_statement(
                    periods=periods,
                    annual=True,
                    as_dataframe=as_dataframe,
                    concise_format=concise_format
                )
        except Exception as e:
            from edgar.core import log
            log.debug(f"Error getting cash flow for {self.name}: {e}")
        return None

    def cash_flow(
        self,
        periods: int = 4,
        period: str = 'annual',
        annual: Optional[bool] = None,
        as_dataframe: bool = False,
        concise_format: bool = False
    ) -> Union["MultiPeriodStatement", TTMStatement, "pd.DataFrame", None]:
        """Deprecated: Use cashflow_statement() instead."""
        import warnings
        warnings.warn(
            "cash_flow() is deprecated and will be removed in v6.0. "
            "Use cashflow_statement() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.cashflow_statement(
            periods=periods, period=period, annual=annual,
            as_dataframe=as_dataframe, concise_format=concise_format
        )

    def cash_flow_statement(self, **kwargs):
        """Alias for cashflow_statement()."""
        return self.cashflow_statement(**kwargs)

    # -------------------------------------------------------------------------
    # Concept Discovery Methods
    # -------------------------------------------------------------------------

    def list_concepts(
        self,
        search: Optional[str] = None,
        statement: Optional[str] = None,
        limit: int = 20,
    ) -> ConceptList:
        """List available XBRL concepts for this company.

        Helps discover valid concept names for use with get_ttm() and other methods.
        Concepts are sorted by frequency (most reported first).

        Args:
            search: Filter concepts containing this string (case-insensitive)
            statement: Filter by statement type ('IncomeStatement', 'BalanceSheet',
                      'CashFlowStatement', 'ComprehensiveIncome', 'StatementOfEquity')
            limit: Maximum number of concepts to return (default: 20, use 0 for all)

        Returns:
            ConceptList object with rich display, iteration, and conversion methods

        Example:
            >>> company = Company("AAPL")
            >>> # Find revenue-related concepts (displays as nice table)
            >>> company.list_concepts(search="revenue")

            >>> # Iterate over concepts
            >>> for c in company.list_concepts(search="revenue"):
            ...     print(c['concept'])

            >>> # Get as plain list or DataFrame
            >>> company.list_concepts().to_list()
            >>> company.list_concepts().to_dataframe()
        """
        facts_obj = self.facts
        if not facts_obj or not facts_obj._facts:
            return ConceptList([], search=search, statement=statement, company_name=self.name)

        # Build concept index with metadata
        concept_info: dict = {}
        for f in facts_obj._facts:
            if f.concept not in concept_info:
                concept_info[f.concept] = {
                    'labels': set(),
                    'statements': set(),
                    'count': 0
                }
            info = concept_info[f.concept]
            info['count'] += 1
            if f.label:
                info['labels'].add(f.label)
            if f.statement_type:
                info['statements'].add(f.statement_type)

        # Build results with filtering
        results = []
        search_lower = search.lower() if search else None

        for concept, info in concept_info.items():
            # Apply search filter
            if search_lower and search_lower not in concept.lower():
                continue

            # Apply statement filter
            if statement and statement not in info['statements']:
                continue

            # Get primary label (first one, or derive from concept name)
            if info['labels']:
                label = next(iter(info['labels']))
            else:
                # Extract readable name from concept (e.g., "us-gaap:NetIncomeLoss" -> "Net Income Loss")
                name = concept.split(':')[-1]
                # Add spaces before capital letters
                label = re.sub(r'(?<!^)(?=[A-Z])', ' ', name)

            results.append({
                'concept': concept,
                'label': label,
                'statements': sorted(info['statements']),
                'fact_count': info['count']
            })

        # Sort by fact count (most reported = most important)
        results.sort(key=lambda x: x['fact_count'], reverse=True)

        # Apply limit
        if limit > 0:
            results = results[:limit]

        return ConceptList(results, search=search, statement=statement, company_name=self.name)

    # -------------------------------------------------------------------------
    # TTM (Trailing Twelve Months) Methods
    # -------------------------------------------------------------------------

    def _get_split_adjusted_facts(self) -> List:
        """Get all facts, adjusted for stock splits.

        Results are cached to avoid redundant computation when called
        multiple times (e.g., for income_statement and cash_flow).

        Returns:
            List of FinancialFact objects with split-adjusted values
        """
        # Check cache first
        cache_attr = '_cached_split_adjusted_facts'
        if hasattr(self, cache_attr):
            return getattr(self, cache_attr)

        facts_obj = self.facts
        if not facts_obj or not facts_obj._facts:
            return []

        facts = facts_obj._facts

        # Detect and apply split adjustments
        splits = detect_splits(facts)
        if splits:
            facts = apply_split_adjustments(facts, splits)

        # Cache the result
        object.__setattr__(self, cache_attr, facts)
        return facts

    def _prepare_quarterly_facts(self, facts: List) -> List:
        """Enhance facts with derived Q4 data for quarterly analysis.

        Derives Q2, Q3, Q4 from YTD and annual facts when discrete quarters
        are not available. Also derives Q4 EPS from net income and shares.

        Args:
            facts: List of FinancialFact objects

        Returns:
            Original facts plus derived quarterly facts
        """
        from edgar.entity.models import FinancialFact

        # Group by concept
        concept_facts = defaultdict(list)
        for f in facts:
            concept_facts[f.concept].append(f)

        derived_facts = []

        # Derive quarterly data for each concept
        for _, c_facts in concept_facts.items():
            try:
                calc = TTMCalculator(c_facts)
                quarterly = calc._quarterize_facts()

                # Add only derived quarters
                for qf in quarterly:
                    if qf.calculation_context and 'derived' in qf.calculation_context:
                        derived_facts.append(qf)
            except (ValueError, KeyError, AttributeError, IndexError, TypeError):
                # Skip concepts that can't be quarterized (e.g., insufficient data, balance sheet items)
                continue

        # Derive EPS for Q4 using Net Income and Shares
        def _collect_facts(concepts: List[str]) -> List[FinancialFact]:
            collected = []
            for name in concepts:
                if name in concept_facts:
                    collected.extend(concept_facts[name])
                for prefix in ['us-gaap', 'ifrs-full']:
                    prefixed = f"{prefix}:{name}"
                    if prefixed in concept_facts:
                        collected.extend(concept_facts[prefixed])
            return collected

        net_income_facts = _collect_facts([
            "NetIncomeLoss",
            "NetIncomeLossAvailableToCommonStockholdersBasic",
        ])

        shares_basic = _collect_facts([
            "WeightedAverageNumberOfSharesOutstandingBasic",
            "WeightedAverageNumberOfSharesOutstandingBasicAndDiluted",
        ])
        shares_diluted = _collect_facts([
            "WeightedAverageNumberOfDilutedSharesOutstanding",
            "WeightedAverageNumberOfSharesOutstandingDiluted",
        ])

        def _has_eps_for_period(concept_name: str, period_end: date, fiscal_period: str) -> bool:
            candidates = [concept_name]
            if ":" in concept_name:
                candidates.append(concept_name.split(":", 1)[1])
            else:
                candidates.append(f"us-gaap:{concept_name}")
                candidates.append(f"ifrs-full:{concept_name}")

            for name in candidates:
                for fact in concept_facts.get(name, []):
                    if (fact.period_end == period_end and
                        fact.fiscal_period == fiscal_period and
                        fact.period_type == "duration"):
                        return True
            return False

        # Derive basic EPS
        if net_income_facts and shares_basic:
            calc = TTMCalculator(net_income_facts)
            for eps_fact in calc.derive_eps_for_quarter(
                net_income_facts, shares_basic, "us-gaap:EarningsPerShareBasic"
            ):
                if not _has_eps_for_period(eps_fact.concept, eps_fact.period_end, eps_fact.fiscal_period):
                    derived_facts.append(eps_fact)

        # Derive diluted EPS
        if net_income_facts and shares_diluted:
            calc = TTMCalculator(net_income_facts)
            for eps_fact in calc.derive_eps_for_quarter(
                net_income_facts, shares_diluted, "us-gaap:EarningsPerShareDiluted"
            ):
                if not _has_eps_for_period(eps_fact.concept, eps_fact.period_end, eps_fact.fiscal_period):
                    derived_facts.append(eps_fact)

        return facts + derived_facts

    def get_ttm(self, concept: str, as_of: Optional[Union[date, str]] = None) -> TTMMetric:
        """Calculate Trailing Twelve Months value for a concept.

        Args:
            concept: XBRL concept name (e.g., 'Revenues', 'us-gaap:NetIncomeLoss')
            as_of: Calculate TTM as of this date. Accepts:
                   - date object
                   - ISO string 'YYYY-MM-DD'
                   - Quarter string 'YYYY-QN' (e.g., '2024-Q2')

        Returns:
            TTMMetric with value, periods, and metadata

        Raises:
            KeyError: If concept not found
            ValueError: If insufficient data for TTM calculation

        Example:
            >>> company = Company("AAPL")
            >>> ttm = company.get_ttm("Revenues")
            >>> print(f"TTM Revenue: ${ttm.value / 1e9:.1f}B")
        """
        facts = self._get_split_adjusted_facts()

        # Handle concept name normalization
        if ':' not in concept:
            concept_candidates = [concept, f'us-gaap:{concept}', f'ifrs-full:{concept}']
        else:
            concept_candidates = [concept]

        target_facts = [f for f in facts if f.concept in concept_candidates]

        if not target_facts:
            raise KeyError(f"Concept '{concept}' not found in facts")

        calc = TTMCalculator(target_facts)
        as_of_date = self._parse_ttm_date(as_of)

        return calc.calculate_ttm(as_of=as_of_date)

    def get_ttm_revenue(self, as_of: Optional[Union[date, str]] = None) -> TTMMetric:
        """Get Trailing Twelve Months revenue.

        Tries common revenue concepts in order of preference.

        Args:
            as_of: Calculate TTM as of this date (optional)

        Returns:
            TTMMetric with revenue value and metadata

        Raises:
            KeyError: If no revenue concept found
        """
        revenue_concepts = [
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'Revenues',
            'SalesRevenueNet',
            'Revenue'
        ]
        for concept in revenue_concepts:
            try:
                return self.get_ttm(concept, as_of)
            except KeyError:
                continue
        raise KeyError("Could not find revenue concept in company facts")

    def get_ttm_net_income(self, as_of: Optional[Union[date, str]] = None) -> TTMMetric:
        """Get Trailing Twelve Months net income.

        Tries common net income concepts in order of preference.

        Args:
            as_of: Calculate TTM as of this date (optional)

        Returns:
            TTMMetric with net income value and metadata

        Raises:
            KeyError: If no net income concept found
        """
        income_concepts = ['NetIncomeLoss', 'NetIncome', 'ProfitLoss']
        for concept in income_concepts:
            try:
                return self.get_ttm(concept, as_of)
            except KeyError:
                continue
        raise KeyError("Could not find net income concept in company facts")

    def _parse_ttm_date(self, as_of: Optional[Union[date, str]]) -> Optional[date]:
        """Parse TTM 'as_of' parameter into a date object.

        Args:
            as_of: Date, ISO string 'YYYY-MM-DD', or quarter string 'YYYY-QN'

        Returns:
            Parsed date or None if as_of is None

        Raises:
            TypeError: If as_of is not a date, str, or None
            ValueError: If string format is invalid or values are out of range
        """
        if as_of is None:
            return None

        if isinstance(as_of, date):
            return as_of

        if not isinstance(as_of, str):
            raise TypeError(f"as_of must be date, str, or None, got {type(as_of).__name__}")

        # Try ISO format: YYYY-MM-DD
        if '-' in as_of and len(as_of.split('-')) == 3:
            try:
                parsed = date.fromisoformat(as_of)
                # Validate reasonable year range
                if parsed.year < 1900 or parsed.year > 2100:
                    raise ValueError(f"Year must be between 1900 and 2100, got {parsed.year}")
                return parsed
            except ValueError as e:
                if "year" in str(e).lower():
                    raise
                raise ValueError(f"Invalid date format: '{as_of}'. Expected ISO format YYYY-MM-DD") from e

        # Try quarter format: YYYY-QN
        parts = as_of.upper().split('-')
        if len(parts) == 2 and 'Q' in parts[1]:
            try:
                year = int(parts[0])
                if year < 1900 or year > 2100:
                    raise ValueError(f"Year must be between 1900 and 2100, got {year}")

                q = int(parts[1].replace('Q', ''))
                if q not in (1, 2, 3, 4):
                    raise ValueError(f"Quarter must be 1-4, got {q}")

                # Map to quarter end dates
                quarter_ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
                month, day = quarter_ends[q]
                return date(year, month, day)
            except ValueError:
                raise
            except (TypeError, KeyError) as e:
                raise ValueError(f"Invalid quarter format: '{as_of}'. Expected YYYY-QN (e.g., '2024-Q2')") from e

        raise ValueError(f"Invalid date format: '{as_of}'. Use 'YYYY-MM-DD' or 'YYYY-QN'")

    def __str__(self):
        if hasattr(self, 'data') and self.data.name:
            # Handle individuals (persons)
            if self.data.is_individual:
                return f"{self.display_name} (Person) CIK:{self.cik}"

            # Company format
            ticker = self.get_ticker()
            parts = [self.data.name]
            if ticker:
                parts.append(f"[{ticker}]")
            parts.append(f"CIK:{self.cik}")
            if self.industry:
                parts.append(f"• {self.industry}")
            return " ".join(parts)
        # Fallback for minimal data
        return f"Company(CIK={self.cik})"

    def __repr__(self):
        # Delegate to the rich representation for consistency with the old implementation
        return repr_rich(self.__rich__())

    def to_context(self, detail: str = 'standard', max_tokens: Optional[int] = None) -> str:
        """
        Get AI-optimized plain text representation.

        Uses Markdown-KV format (60.7% accuracy, 25% fewer tokens than JSON) optimized
        for LLM consumption. For terminal display, use print(company) instead.

        Research basis: improvingagents.com/blog/best-input-data-format-for-llms

        Args:
            detail: Level of detail to include:
                - 'minimal': Basic company info (~100-150 tokens)
                - 'standard': Adds industry, category, available actions (~250-350 tokens)
                - 'full': Adds addresses, phone, filing stats (~500+ tokens)
            max_tokens: Optional token limit override using 4 chars/token heuristic

        Returns:
            Markdown-formatted key-value representation optimized for LLMs

        Example:
            >>> from edgar import Company
            >>> company = Company("AAPL")
            >>> print(company.to_context('minimal'))
            COMPANY: Apple Inc.
            CIK: 0000320193
            Ticker: AAPL

            >>> print(company.to_context('standard'))
            COMPANY: Apple Inc.
            CIK: 0000320193
            Ticker: AAPL
            Exchange: NASDAQ
            Industry: Electronic Computers (SIC 3571)
            Category: Large accelerated filer
            Fiscal Year End: September 30

            AVAILABLE ACTIONS:
              - Use .get_filings() to access SEC filings
              - Use .financials to get financial statements
              - Use .facts to access company facts API
              - Use .docs for detailed API documentation
        """
        lines = []

        # Header
        lines.append(f"COMPANY: {self.data.name}")
        lines.append(f"CIK: {str(self.cik).zfill(10)}")

        # Ticker (always included)
        ticker = self.get_ticker()
        if ticker:
            lines.append(f"Ticker: {ticker}")

        # Standard and full include more details
        if detail in ['standard', 'full']:
            # Exchange
            if hasattr(self.data, 'exchanges') and self.data.exchanges:
                exchanges_str = ", ".join(self.data.exchanges) if isinstance(self.data.exchanges, (list, tuple)) else str(self.data.exchanges)
                lines.append(f"Exchange: {exchanges_str}")

            # Industry classification
            if hasattr(self.data, 'sic') and self.data.sic:
                sic_desc = getattr(self.data, 'sic_description', '')
                if sic_desc:
                    lines.append(f"Industry: {sic_desc} (SIC {self.data.sic})")
                else:
                    lines.append(f"SIC Code: {self.data.sic}")

            # Entity type
            if hasattr(self.data, 'entity_type') and self.data.entity_type:
                lines.append(f"Entity Type: {self.data.entity_type.title()}")

            # Category
            if hasattr(self.data, 'category') and self.data.category:
                lines.append(f"Category: {self.data.category}")

            # Fiscal year end
            if hasattr(self.data, 'fiscal_year_end') and self.data.fiscal_year_end:
                lines.append(f"Fiscal Year End: {self._format_fiscal_year_date(self.data.fiscal_year_end)}")

            # Available actions
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  - Use .get_filings() to access SEC filings")
            lines.append("  - Use .financials to get financial statements")
            lines.append("  - Use .facts to access company facts API")
            lines.append("  - Use .docs for detailed API documentation")

        # Full includes addresses and contact info
        if detail == 'full':
            # Business address
            if hasattr(self.data, 'business_address') and self.data.business_address:
                addr = self.data.business_address
                lines.append("")
                lines.append("BUSINESS ADDRESS:")
                if hasattr(addr, 'street1') and addr.street1:
                    lines.append(f"  {addr.street1}")
                if hasattr(addr, 'street2') and addr.street2:
                    lines.append(f"  {addr.street2}")
                if hasattr(addr, 'city') and hasattr(addr, 'state_or_country') and addr.city and addr.state_or_country:
                    zip_code = f" {addr.zip_code}" if hasattr(addr, 'zip_code') and addr.zip_code else ""
                    lines.append(f"  {addr.city}, {addr.state_or_country}{zip_code}")

            # Contact information
            if hasattr(self.data, 'phone') and self.data.phone:
                lines.append(f"Phone: {self.data.phone}")

            # Mailing address (if different from business address)
            if hasattr(self.data, 'mailing_address') and self.data.mailing_address:
                mail_addr = self.data.mailing_address
                if hasattr(self.data, 'business_address'):
                    # Only include if different
                    business_addr = self.data.business_address
                    if (not hasattr(business_addr, 'street1') or
                        mail_addr.street1 != business_addr.street1):
                        lines.append("")
                        lines.append("MAILING ADDRESS:")
                        if hasattr(mail_addr, 'street1') and mail_addr.street1:
                            lines.append(f"  {mail_addr.street1}")
                        if hasattr(mail_addr, 'city') and hasattr(mail_addr, 'state_or_country'):
                            zip_code = f" {mail_addr.zip_code}" if hasattr(mail_addr, 'zip_code') and mail_addr.zip_code else ""
                            lines.append(f"  {mail_addr.city}, {mail_addr.state_or_country}{zip_code}")

        text = "\n".join(lines)

        # Token limiting (4 chars/token heuristic) - only if max_tokens specified
        if max_tokens is not None:
            max_chars = max_tokens * 4
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[Truncated for token limit]"

        return text

    def text(self, max_tokens: int = 2000) -> str:
        """
        Deprecated: Use to_context() instead.

        Get AI-optimized plain text representation.
        This method is deprecated and will be removed in a future version.
        Use to_context() for consistent naming with other AI-native methods.

        Args:
            max_tokens: Approximate token limit using 4 chars/token heuristic (default: 2000)

        Returns:
            Markdown-formatted key-value representation optimized for LLMs
        """
        import warnings
        warnings.warn(
            "Company.text() is deprecated and will be removed in a future version. "
            "Use Company.to_context() instead for consistent naming.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.to_context(max_tokens=max_tokens)

    def __rich__(self):
        """Creates a rich representation of the company with detailed information.

        Design follows the EdgarTools display language (docs/internal/design-language.md):
        - Single outer border (card-based) with box.ROUNDED
        - No emojis - uses unicode symbols from SYMBOLS
        - Semantic colors from edgar.display.styles
        - Compact layout with whitespace section separation
        """
        # Build header line: Company Name + Ticker(s)
        # Show up to 2 tickers, then "+ N more" for additional
        tickers = self.tickers if hasattr(self, 'tickers') else []
        if tickers:
            if len(tickers) == 1:
                ticker_text = Text(tickers[0], style=get_style("ticker"))
            elif len(tickers) == 2:
                ticker_text = Text.assemble(
                    (tickers[0], get_style("ticker")),
                    (" / ", get_style("metadata")),
                    (tickers[1], get_style("ticker"))
                )
            else:
                ticker_text = Text.assemble(
                    (tickers[0], get_style("ticker")),
                    (" / ", get_style("metadata")),
                    (tickers[1], get_style("ticker")),
                    (f" +{len(tickers) - 2}", get_style("metadata"))
                )
            header = Text.assemble(
                (self.data.name, get_style("company_name")),
                "  ",
                ticker_text
            )
        else:
            header = Text(self.data.name, style=get_style("company_name"))

        # Build subtitle line: CIK • Exchange • Category
        subtitle_parts = [cik_text(self.cik)]

        # Add exchange if available
        if hasattr(self.data, 'exchanges') and self.data.exchanges and self.data.exchanges[0]:
            subtitle_parts.append(Text(self.data.exchanges[0], style=get_style("value")))

        # Add simplified category
        if hasattr(self.data, 'category') and self.data.category:
            # Shorten the category text
            category = self.data.category
            if 'Emerging growth' in category:
                category = 'Emerging Growth'
            elif 'Large accelerated' in category:
                category = 'Large Accelerated Filer'
            elif 'accelerated' in category.lower():
                category = 'Accelerated Filer'
            elif 'Non-accelerated' in category:
                category = 'Non-accelerated Filer'
            subtitle_parts.append(Text(category, style=get_style("metadata")))

        # Add filer type indicator for non-domestic companies
        if self.filer_type == 'Foreign':
            subtitle_parts.append(Text(self.filer_type, style=get_style("foreign")))
        elif self.filer_type == 'Canadian':
            subtitle_parts.append(Text(self.filer_type, style=get_style("canadian")))

        subtitle = Text(f" {SYMBOLS['bullet']} ").join(subtitle_parts)

        # Build content sections
        content_lines = []

        # Section 1: Core details (compact key-value pairs)
        details_table = Table(box=None, show_header=False, padding=(0, 2), expand=False)
        details_table.add_column("Label", style=get_style("label"), width=14)
        details_table.add_column("Value", style=get_style("value_highlight"))

        # Industry
        if hasattr(self.data, 'sic') and self.data.sic:
            sic_desc = getattr(self.data, 'sic_description', '') or ''
            details_table.add_row("Industry", f"{self.data.sic}: {sic_desc}")

        # Fiscal Year End
        if hasattr(self.data, 'fiscal_year_end') and self.data.fiscal_year_end:
            fy_end = self._format_fiscal_year_date(self.data.fiscal_year_end)
            details_table.add_row("Fiscal Year", fy_end)

        # State of Incorporation
        if hasattr(self.data, 'state_of_incorporation') and self.data.state_of_incorporation:
            from edgar.reference._codes import get_place_name
            code = self.data.state_of_incorporation
            # Always look up full name from place_codes.csv, fallback to description or code
            state_name = get_place_name(code)
            if not state_name:
                state_name = getattr(self.data, 'state_of_incorporation_description', None) or code
            details_table.add_row("Incorporated", state_name)

        # Entity Type (for non-companies or when relevant)
        if hasattr(self.data, 'entity_type') and self.data.entity_type and self.data.is_individual:
            details_table.add_row("Type", "Individual")

        # Phone
        if hasattr(self.data, 'phone') and self.data.phone:
            details_table.add_row("Phone", self.data.phone)

        # Website
        if hasattr(self.data, 'website') and self.data.website:
            details_table.add_row("Website", self.data.website)

        # Address (single line, business address preferred)
        address = None
        if hasattr(self.data, 'business_address') and not self.data.business_address.empty:
            address = self.data.business_address
        elif hasattr(self.data, 'mailing_address') and not self.data.mailing_address.empty:
            address = self.data.mailing_address

        if address:
            # Format address as single line
            addr_parts = []
            if address.street1:
                addr_parts.append(address.street1)
            if address.street2:
                addr_parts.append(address.street2)
            city_state = []
            if address.city:
                city_state.append(address.city)
            if address.state_or_country:
                city_state.append(address.state_or_country)
            if city_state:
                addr_parts.append(", ".join(city_state))
            if address.zipcode:
                addr_parts[-1] = addr_parts[-1] + " " + address.zipcode if addr_parts else address.zipcode

            if addr_parts:
                details_table.add_row("Address", ", ".join(addr_parts[:2]) if len(addr_parts) > 2 else ", ".join(addr_parts))

        content_lines.append(details_table)

        # Section 2: Former Names (only if most recent change was within last 2 years)
        if hasattr(self.data, 'former_names') and self.data.former_names:
            from datetime import date, timedelta
            most_recent = self.data.former_names[0]
            two_years_ago = date.today() - timedelta(days=730)
            # Check if the most recent name change was within last 2 years
            most_recent_date_str = most_recent.get('to')
            most_recent_date = date.fromisoformat(most_recent_date_str) if most_recent_date_str else None
            if most_recent_date and most_recent_date >= two_years_ago:
                content_lines.append(Text(""))  # Spacing
                content_lines.append(Text("Former Names", style=get_style("section_header")))

                for former_name in self.data.former_names[:3]:  # Limit to 3
                    from_date = datefmt(former_name['from'], '%b %Y')
                    to_date = datefmt(former_name['to'], '%b %Y')
                    content_lines.append(Text.assemble(
                        ("  ", ""),
                        (former_name['name'], "italic"),
                        (" (", get_style("metadata")),
                        (f"{from_date} {SYMBOLS['arrow_right']} {to_date}", get_style("metadata")),
                        (")", get_style("metadata"))
                    ))

                # Show count if more than 3
                if len(self.data.former_names) > 3:
                    remaining = len(self.data.former_names) - 3
                    content_lines.append(Text(f"  {SYMBOLS['ellipsis']} and {remaining} more", style=get_style("metadata")))

        content = Group(
            header,
            subtitle,
            Text(""),  # Spacing after header
            *content_lines
        )

        # Create the card with single border (design language compliant)
        # Fixed width ensures consistent appearance across different companies
        return Panel(
            content,
            border_style=get_style("border"),
            box=box.ROUNDED,
            padding=(0, 1),
            width=85,
            subtitle=Text.assemble(
                ("SEC Entity Data", get_style("metadata")),
                f" {SYMBOLS['bullet']} ",
                ("company.docs", get_style("hint")),
                (" for usage guide", get_style("metadata"))
            ),
            subtitle_align="right"
        )

    @staticmethod
    def _get_operating_type_emoticon(entity_type: str) -> str:
        """
        Generate a meaningful single-width symbol based on the SEC entity type.
        All symbols are chosen to be single-width to work well with rich borders.

        Args:
            entity_type (str): The SEC entity type (case-insensitive)

        Returns:
            str: A single-width symbol representing the entity type
        """
        symbols = {
            "operating": "○",  # Circle for active operations
            "subsidiary": "→",  # Arrow showing connection to parent
            "inactive": "×",  # Cross for inactive
            "holding company": "■",  # Square for solid corporate structure
            "investment company": "$",  # Dollar for investment focus
            "investment trust": "$",  # Dollar for investment focus
            "shell": "□",  # Empty square for shell
            "development stage": "∆",  # Triangle for growth/development
            "financial services": "¢",  # Cent sign for financial services
            "reit": "⌂",  # House symbol
            "spv": "◊",  # Diamond for special purpose
            "joint venture": "∞"  # Infinity for partnership
        }

        # Clean input: convert to lowercase and strip whitespace
        cleaned_type = entity_type.lower().strip()

        # Handle some common variations
        if "investment" in cleaned_type:
            return symbols["investment company"]
        if "real estate" in cleaned_type or "reit" in cleaned_type:
            return symbols["reit"]

        # Return default question mark if type not found
        return symbols.get(cleaned_type, "")

    @staticmethod
    def _format_fiscal_year_date(date_str):
        """Format fiscal year end date in a human-readable format."""
        if not date_str:
            return "-"

        # Dictionary of months
        months = {
            "01": "Jan", "02": "Feb", "03": "Mar",
            "04": "Apr", "05": "May", "06": "Jun",
            "07": "Jul", "08": "Aug", "09": "Sep",
            "10": "Oct", "11": "Nov", "12": "Dec"
        }

        # Extract month and day
        month = date_str[:2]
        if month not in months:
            return date_str

        try:
            day = str(int(date_str[2:]))  # Remove leading zero
            return f"{months[month]} {day}"
        except (ValueError, IndexError):
            return date_str


# Factory functions for backward compatibility

def get_entity(cik_or_identifier: Union[str, int]) -> Entity:
    """
    Get any SEC filing entity by CIK or identifier.

    Args:
        cik_or_identifier: CIK number (as int or str) or other identifier

    Returns:
        Entity instance
    """
    return Entity(cik_or_identifier)


def get_company(cik_or_ticker: Union[str, int]) -> Company:
    """
    Get a public company by CIK or ticker.

    Args:
        cik_or_ticker: CIK number or ticker symbol

    Returns:
        Company instance
    """
    return Company(cik_or_ticker)


def public_companies() -> Iterable[Company]:
    """
    Iterator over all known public companies.

    Returns:
        Iterable of Company objects
    """
    from edgar.reference.tickers import get_cik_tickers

    df = get_cik_tickers()
    for _, row in df.iterrows():
        c = Company(row.cik)
        yield c



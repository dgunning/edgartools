"""
Filings-related classes for the Entity package.

This module contains classes related to SEC filings for entities, including
collections of filings and filing facts.
"""
from typing import List, Union

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
from rich.box import SIMPLE
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar._filings import Filing, Filings, PagingState
from edgar.core import IntString, log, listify
from edgar.formatting import accession_number_text, display_size
from edgar.reference.forms import describe_form
from edgar.richtools import Docs, df_to_rich_table, repr_rich

__all__ = [
    'EntityFiling',
    'EntityFilings',
    'EntityFacts',
    'empty_company_filings'
]


class EntityFiling(Filing):
    """
    Represents a single SEC filing for an entity.

    This extends the base Filing class with additional information
    and methods specific to SEC entities.

    Attributes:
        items (str): Filing items from SEC metadata. For 8-K filings, this indicates
            which items are included (e.g., "2.02,9.01").

            **Data Source**: This value comes from SEC filing metadata, not from parsing
            the filing document itself.

            **Legacy SGML Limitation**: For legacy SGML filings (1999-2001), the SEC's
            historical metadata may be incorrect or incomplete. Modern XML filings (2005+)
            have accurate metadata.

            **Workaround for Legacy Filings**: For accurate item extraction from legacy
            SGML 8-K filings, parse the filing text directly using regex patterns.
            See GitHub Issue #462 for example code.
    """

    def __init__(self,
                 cik: int,
                 company: str,
                 form: str,
                 filing_date: str,
                 report_date: str,
                 acceptance_datetime: str,
                 accession_no: str,
                 file_number: str,
                 items: str,
                 size: int,
                 primary_document: str,
                 primary_doc_description: str,
                 is_xbrl: bool,
                 is_inline_xbrl: bool):
        super().__init__(cik=cik, company=company, form=form, filing_date=filing_date, accession_no=accession_no)
        self.report_date = report_date
        self.acceptance_datetime = acceptance_datetime
        self.file_number: str = file_number
        self.items: str = items  # See class docstring for important notes on data source and limitations
        self.size: int = size
        self.primary_document: str = primary_document
        self.primary_doc_description: str = primary_doc_description
        self.is_xbrl: bool = is_xbrl
        self.is_inline_xbrl: bool = is_inline_xbrl

    def related_filings(self):
        """Get all the filings related to this one by file number."""
        return self.get_entity().get_filings(file_number=self.file_number, sort_by="filing_date")

    def __str__(self):
        return (f"Filing(company='{self.company}', cik={self.cik}, form='{self.form}', "
                f"filing_date='{self.filing_date}', accession_no='{self.accession_no}')"
                )


class EntityFilings(Filings):
    """
    Collection of SEC filings for an entity.

    This extends the base Filings class with additional methods and properties
    specific to entity filings.
    """

    def __init__(self,
                 data: pa.Table,
                 cik: int,
                 company_name: str,
                 original_state: PagingState = None):
        super().__init__(data, original_state=original_state)
        self.cik = cik
        self.company_name = company_name

    @property
    def docs(self):
        return Docs(self)

    def __getitem__(self, item):
        return self.get_filing_at(item)

    @property
    def empty(self):
        return len(self.data) == 0

    def get_filing_at(self, item: int):
        """Get the filing at the specified index."""
        return EntityFiling(
            cik=self.cik,
            company=self.company_name,
            form=self.data['form'][item].as_py(),
            filing_date=self.data['filing_date'][item].as_py(),
            report_date=self.data['reportDate'][item].as_py(),
            acceptance_datetime=self.data['acceptanceDateTime'][item].as_py(),
            accession_no=self.data['accession_number'][item].as_py(),
            file_number=self.data['fileNumber'][item].as_py(),
            items=self.data['items'][item].as_py(),
            size=self.data['size'][item].as_py(),
            primary_document=self.data['primaryDocument'][item].as_py(),
            primary_doc_description=self.data['primaryDocDescription'][item].as_py(),
            is_xbrl=self.data['isXBRL'][item].as_py(),
            is_inline_xbrl=self.data['isInlineXBRL'][item].as_py()
        )

    def filter(self,
               form: Union[str, List[str]] = None,
               amendments: bool = None,
               filing_date: str = None,
               date: str = None,
               cik: Union[int, str, List[Union[int, str]]] = None,
               ticker: Union[str, List[str]] = None,
               accession_number: Union[str, List[str]] = None,
               file_number: Union[str, List[str]] = None):
        """
        Filter the filings based on various criteria.

        Args:
            form: Filter by form type
            amendments: Include amendments
            filing_date: Filter by filing date
            date: Alias for filing_date
            cik: Filter by CIK
            ticker: Filter by ticker
            accession_number: Filter by accession number
            file_number: Filter by file number

        Returns:
            Filtered EntityFilings
        """
        # The super filter returns Filings. We want EntityFilings
        res = super().filter(form=form,
                             amendments=amendments,
                             filing_date=filing_date,
                             date=date,
                             cik=cik,
                             ticker=ticker,
                             accession_number=accession_number)
        if file_number:
            data  = res.data.filter(
                pc.is_in(res.data['fileNumber'], pa.array(listify(file_number))))
        else:
            data = res.data
        return EntityFilings(data=data, cik=self.cik, company_name=self.company_name)

    def latest(self, n: int = 1):
        """
        Get the latest n filings.

        Args:
            n: Number of filings to return

        Returns:
            Latest filing(s) - single filing if n=1, otherwise EntityFilings
        """
        sort_indices = pc.sort_indices(self.data, sort_keys=[("filing_date", "descending")])
        sort_indices_top = sort_indices[:min(n, len(sort_indices))]
        latest_filing_index = pc.take(data=self.data, indices=sort_indices_top)
        filings = EntityFilings(latest_filing_index,
                               cik=self.cik,
                               company_name=self.company_name)
        if filings.empty:
            return None
        if len(filings) == 1:
            return filings[0]
        else:
            return filings

    def head(self, n: int):
        """
        Get the first n filings.

        Args:
            n: Number of filings to return

        Returns:
            EntityFilings containing the first n filings
        """
        selection = self._head(n)
        return EntityFilings(data=selection, cik=self.cik, company_name=self.company_name)

    def tail(self, n: int):
        """
        Get the last n filings.

        Args:
            n: Number of filings to return

        Returns:
            EntityFilings containing the last n filings
        """
        selection = self._tail(n)
        return EntityFilings(data=selection, cik=self.cik, company_name=self.company_name)

    def sample(self, n: int):
        """
        Get a random sample of n filings.

        Args:
            n: Number of filings to sample

        Returns:
            EntityFilings containing n random filings
        """
        selection = self._sample(n)
        return EntityFilings(data=selection, cik=self.cik, company_name=self.company_name)


    @staticmethod
    def summarize(data) -> pd.DataFrame:
        """
        Summarize filing data as a pandas DataFrame.

        Args:
            data: Filing data to summarize

        Returns:
            DataFrame with summarized data
        """
        return (data
                .assign(size=lambda df: df['size'].apply(display_size),
                        isXBRL=lambda df: df.isXBRL.map({'1': "\u2713", 1: "\u2713"}).fillna(""),
                        )
                .filter(["form", "filing_date", "accession_number", "isXBRL"])
                .rename(columns={"filing_date": "filed", "isXBRL": "xbrl"})
                )

    def next(self):
        """
        Show the next page of filings.

        Returns:
            EntityFilings with the next page of data, or None if at the end
        """
        data_page = self.data_pager.next()
        if data_page is None:
            log.warning("End of data .. use prev() \u2190 ")
            return None
        start_index, _ = self.data_pager._current_range
        filings_state = PagingState(page_start=start_index, num_records=len(self))
        return EntityFilings(data_page,
                            cik=self.cik,
                            company_name=self.company_name,
                            original_state=filings_state)

    def previous(self):
        """
        Show the previous page of filings.

        Returns:
            EntityFilings with the previous page of data, or None if at the beginning
        """
        data_page = self.data_pager.previous()
        if data_page is None:
            log.warning(" No previous data .. use next() \u2192 ")
            return None
        start_index, _ = self.data_pager._current_range
        filings_state = PagingState(page_start=start_index, num_records=len(self))
        return EntityFilings(data_page,
                            cik=self.cik,
                            company_name=self.company_name,
                            original_state=filings_state)

    def __repr__(self):
        return repr_rich(self.__rich__())

    def to_context(self, detail: str = 'standard') -> str:
        """
        Returns AI-optimized entity filings summary for language models.

        This method extends Filings.to_context() with entity-specific context,
        providing structured information in a markdown-KV format optimized for AI navigation.

        Args:
            detail: Level of detail to include:
                - 'minimal': Basic collection info (~150 tokens)
                - 'standard': Adds sample entries (~300 tokens)
                - 'full': Adds form breakdown and crowdfunding details (~500 tokens)

        Returns:
            Markdown-KV formatted context string optimized for LLMs

        Example:
            >>> company = Company(1881570)
            >>> filings = company.get_filings(form='C')
            >>> print(filings.to_context('standard'))
            FILINGS FOR: ViiT Health Inc
            CIK: 1881570

            Total: 5 filings
            Forms: C, C-U, C-AR
            Date Range: 2024-01-01 to 2025-06-11

            AVAILABLE ACTIONS:
              - Use .latest() to get most recent filing
              - Use [index] to access specific filing (e.g., filings[0])
              - Use .filter(form='C') to narrow by form type
              - Use .docs for detailed API documentation

            SAMPLE FILINGS:
              0. Form C - 2025-06-11 - ViiT Health Inc
              1. Form C-U - 2024-12-15 - ViiT Health Inc
              2. Form C-AR - 2024-08-20 - ViiT Health Inc
              ... (2 more)

            CROWDFUNDING FILINGS:
              C: 1 filing
              C-U: 2 filings
              C-AR: 2 filings
        """
        lines = []

        # Header with entity info
        lines.append(f"FILINGS FOR: {self.company_name}")
        lines.append(f"CIK: {self.cik}")
        lines.append("")

        # Get base context from parent (without the header lines)
        base_context = super().to_context(detail=detail)
        # Skip first 2 lines (header and blank) from parent
        base_lines = base_context.split('\n')[2:]
        lines.extend(base_lines)

        # Add entity-specific insights for standard/full
        if detail in ['standard', 'full'] and len(self) > 0:
            # Crowdfunding-specific breakdown
            cf_forms = ['C', 'C/A', 'C-U', 'C-AR', 'C-TR']
            forms_list = self.data['form'].to_pylist()
            cf_filings = [f for f in forms_list if f.split('/')[0] in cf_forms]

            if cf_filings:
                from collections import Counter
                cf_counts = Counter(cf_filings)

                lines.append("")
                lines.append("CROWDFUNDING FILINGS:")
                # Order by typical lifecycle: C, C-U, C-AR, C-TR
                for form in ['C', 'C/A', 'C-U', 'C-AR', 'C-TR']:
                    if form in cf_counts:
                        cnt = cf_counts[form]
                        lines.append(f"  {form}: {cnt} {'filing' if cnt == 1 else 'filings'}")

        return "\n".join(lines)

    def __rich__(self):
        # Create table with appropriate columns and styling
        table = Table(
            show_header=True,
            header_style="bold",
            show_edge=True,
            expand=False,
            padding=(0, 1),
            box=SIMPLE,
            row_styles=["", "bold"]
        )

        # Add columns with specific styling and alignment
        table.add_column("#", style="dim", justify="right")
        table.add_column("Form", width=10, style="bold yellow")
        table.add_column("Description", width=60, style="bold blue"),
        table.add_column("Filing Date", width=11)
        table.add_column("Accession Number", width=20)

        # Get current page from data pager
        current_page = self.data_pager.current()

        # Calculate start index for proper indexing
        start_idx = self._original_state.page_start if self._original_state else self.data_pager.start_index

        # Iterate through rows in current page
        for i in range(len(current_page)):
            form = current_page['form'][i].as_py()
            description = describe_form(current_page['form'][i].as_py(), prepend_form=False)

            row = [
                str(start_idx + i),
                form,
                description,
                str(current_page['filing_date'][i].as_py()),
                accession_number_text(current_page['accession_number'][i].as_py())
            ]
            table.add_row(*row)

        # Show paging information only if there are multiple pages
        elements = [table]

        if self.data_pager.total_pages > 1:
            total_filings = self._original_state.num_records
            current_count = len(current_page)
            start_num = start_idx + 1
            end_num = start_idx + current_count

            page_info = Text.assemble(
                ("Showing ", "dim"),
                (f"{start_num:,}", "bold red"),
                (" to ", "dim"),
                (f"{end_num:,}", "bold red"),
                (" of ", "dim"),
                (f"{total_filings:,}", "bold"),
                (" filings.", "dim"),
                (" Page using ", "dim"),
                ("← prev()", "bold gray54"),
                (" and ", "dim"),
                ("next() →", "bold gray54")
            )

            elements.extend([Text("\n"), page_info])

        # Get the title
        title = Text.assemble(
            ("Filings for ", "bold"),
            (f"{self.company_name}", "bold green"),
            (" [", "dim"),
            (f"{self.cik}", "bold yellow"),
            ("]", "dim")
        )

        # Get the subtitle
        start_date, end_date = self.date_range
        date_range_text = f"Company filings between {start_date:%Y-%m-%d} and {end_date:%Y-%m-%d}" if start_date else "Company filings"
        subtitle = Text.assemble(
            (date_range_text, "dim"),
            " • ",
            ("filings.docs", "cyan dim"),
            (" for usage guide", "dim")
        )
        return Panel(
            Group(*elements),
            title=title,
            subtitle=subtitle,
            border_style="bold grey54",
            expand=False
        )


class EntityFacts:
    """
    Contains structured facts data about an entity from XBRL filings.
    """

    def __init__(self,
                 cik: int,
                 name: str,
                 facts: pa.Table,
                 fact_meta: pd.DataFrame):
        self.cik: int = cik
        self.name: str = name
        self.facts: pa.Table = facts
        self.fact_meta: pd.DataFrame = fact_meta

    def to_pandas(self) -> pd.DataFrame:
        """Convert facts to a pandas DataFrame."""
        return self.facts.to_pandas()

    def __len__(self):
        return len(self.facts)

    def num_facts(self) -> int:
        """Get the number of facts."""
        return len(self.fact_meta)

    def __rich__(self):
        return Panel(
            Group(
                df_to_rich_table(self.facts)
            ), title=f"Company Facts({self.name} [{self.cik}] {len(self.facts):,} total facts)"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

COMPANY_FILINGS_SCHEMA = schema = pa.schema([
            ('accession_number', pa.string()),
            ('filing_date', pa.date32()),
            ('reportDate', pa.string()),
            ('acceptanceDateTime', pa.timestamp('us')),  # Changed to timestamp
            ('act', pa.string()),
            ('form', pa.string()),
            ('fileNumber', pa.string()),
            ('items', pa.string()),
            ('size', pa.string()),
            ('isXBRL', pa.string()),
            ('isInlineXBRL', pa.string()),
            ('primaryDocument', pa.string()),
            ('primaryDocDescription', pa.string())
        ])

def empty_company_filings(cik:IntString, company_name:str):
    """
    Create an empty filings container.

    Args:
        cik: The CIK number
        company_name: The company name

    Returns:
        EntityFilings: An empty filings container
    """
    table = pa.Table.from_arrays([[] for _ in range(13)], schema=COMPANY_FILINGS_SCHEMA)
    return EntityFilings(table, cik=cik, company_name=company_name)


# For backward compatibility
CompanyFiling = EntityFiling
CompanyFilings = EntityFilings
CompanyFacts = EntityFacts


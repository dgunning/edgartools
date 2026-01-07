"""Filing selection mechanisms for the test harness."""

from typing import List, Optional, Dict, Any
from datetime import datetime

from edgar import Company, get_filings, Filing
from edgar.reference.company_subsets import get_popular_companies


class FilingSelector:
    """Unified interface for selecting SEC filings for testing.

    Provides multiple selection strategies:
    - Date range selection
    - Company subset selection
    - Random sampling
    - Accession number lookup
    - Company list selection
    - Config-based selection
    """

    @staticmethod
    def by_date_range(
        form: str,
        start_date: str,
        end_date: str,
        sample: Optional[int] = None
    ) -> List[Filing]:
        """Select filings by date range.

        Args:
            form: Form type (e.g., '10-K', '8-K', '10-Q')
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            sample: Optional number of filings to randomly sample

        Returns:
            List of Filing objects

        Example:
            >>> filings = FilingSelector.by_date_range(
            ...     form="10-K",
            ...     start_date="2024-01-01",
            ...     end_date="2024-03-31",
            ...     sample=10
            ... )
        """
        try:
            filings = get_filings(
                form=form,
                filing_date=f"{start_date}:{end_date}"
            )

            if sample:
                filings = filings.sample(sample)

            return list(filings)
        except Exception:
            # Return empty list if date range has no filings or causes errors
            return []

    @staticmethod
    def by_company_subset(
        form: str,
        subset_name: str,
        sample: Optional[int] = None,
        latest_n: int = 1
    ) -> List[Filing]:
        """Select filings using company subsets.

        Args:
            form: Form type (e.g., '10-K', '8-K', '10-Q')
            subset_name: Subset name ('MEGA_CAP', 'LARGE_CAP', etc.)
            sample: Optional number of companies to sample from subset
            latest_n: Number of latest filings per company (default: 1)

        Returns:
            List of Filing objects

        Example:
            >>> filings = FilingSelector.by_company_subset(
            ...     form="10-Q",
            ...     subset_name="MEGA_CAP",
            ...     sample=5
            ... )
        """
        # Get companies from subset
        companies_data = get_popular_companies(tier=subset_name)

        # Convert to list (get_popular_companies returns iterable of dicts)
        companies_list = list(companies_data)

        if sample and len(companies_list) > sample:
            import random
            companies_to_use = random.sample(companies_list, sample)
        else:
            companies_to_use = companies_list

        # Get filings for these companies
        filings = []
        for company_info in companies_to_use:
            try:
                ticker = company_info.get('ticker') or company_info.get('Ticker')
                if ticker:
                    company = Company(ticker)
                    company_filings = company.get_filings(form=form)
                    if company_filings and len(company_filings) > 0:
                        # Get latest N filings - convert to list first
                        company_filings_list = list(company_filings)
                        for i in range(min(latest_n, len(company_filings_list))):
                            filings.append(company_filings_list[i])
            except Exception:
                # Skip companies that fail (delisted, etc.)
                continue

        return filings

    @staticmethod
    def by_accession(accessions: List[str]) -> List[Filing]:
        """Select specific filings by accession number.

        Args:
            accessions: List of accession numbers

        Returns:
            List of Filing objects

        Example:
            >>> filings = FilingSelector.by_accession([
            ...     "0001234567-24-000001",
            ...     "0001234567-24-000002"
            ... ])
        """
        from edgar import get_by_accession_number

        filings = []
        for accession in accessions:
            try:
                filing = get_by_accession_number(accession)
                if filing:
                    filings.append(filing)
            except Exception:
                # Skip invalid accession numbers
                continue

        return filings

    @staticmethod
    def by_random_sample(
        form: str,
        year: int,
        sample: int,
        seed: Optional[int] = None
    ) -> List[Filing]:
        """Random sample of filings from a year.

        Args:
            form: Form type (e.g., '10-K', '8-K', '10-Q')
            year: Year to sample from
            sample: Number of filings to sample
            seed: Optional random seed for reproducibility

        Returns:
            List of Filing objects

        Example:
            >>> filings = FilingSelector.by_random_sample(
            ...     form="8-K",
            ...     year=2024,
            ...     sample=20,
            ...     seed=42  # For reproducibility
            ... )
        """
        import random

        if seed is not None:
            random.seed(seed)

        filings = get_filings(form=form, year=year, quarter=1)

        # Convert to list and use random.sample for reproducibility with seed
        filings_list = list(filings)
        if len(filings_list) <= sample:
            return filings_list

        return random.sample(filings_list, sample)

    @staticmethod
    def by_company_list(
        companies: List[str],
        form: str,
        latest_n: int = 1
    ) -> List[Filing]:
        """Filings from a specific list of companies.

        Args:
            companies: List of company tickers or CIKs
            form: Form type (e.g., '10-K', '8-K', '10-Q')
            latest_n: Number of latest filings per company (default: 1)

        Returns:
            List of Filing objects

        Example:
            >>> filings = FilingSelector.by_company_list(
            ...     companies=["AAPL", "MSFT", "GOOGL"],
            ...     form="10-K",
            ...     latest_n=2  # Last 2 10-Ks from each
            ... )
        """
        filings = []
        for company_id in companies:
            try:
                company = Company(company_id)
                company_filings = company.get_filings(form=form)
                if company_filings and len(company_filings) > 0:
                    # Get latest N filings - convert to list first
                    company_filings_list = list(company_filings)
                    for i in range(min(latest_n, len(company_filings_list))):
                        filings.append(company_filings_list[i])
            except Exception:
                # Skip companies that fail
                continue

        return filings

    @staticmethod
    def by_recent(
        form: str,
        days: int = 7,
        sample: Optional[int] = None
    ) -> List[Filing]:
        """Select recent filings from the last N days.

        Args:
            form: Form type (e.g., '10-K', '8-K', '10-Q')
            days: Number of days back to look (default: 7)
            sample: Optional number to sample

        Returns:
            List of Filing objects

        Example:
            >>> filings = FilingSelector.by_recent(
            ...     form="8-K",
            ...     days=3,
            ...     sample=10
            ... )
        """
        from edgar import get_current_filings

        current = get_current_filings()
        filings = [f for f in current if f.form == form]

        if sample and len(filings) > sample:
            import random
            filings = random.sample(filings, sample)

        return filings[:sample] if sample else filings

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> List[Filing]:
        """Select filings based on configuration dictionary.

        Args:
            config: Configuration dictionary with 'method' and 'params'

        Returns:
            List of Filing objects

        Example:
            >>> config = {
            ...     'method': 'date_range',
            ...     'params': {
            ...         'form': '10-K',
            ...         'start_date': '2024-01-01',
            ...         'end_date': '2024-03-31',
            ...         'sample': 10
            ...     }
            ... }
            >>> filings = FilingSelector.from_config(config)
        """
        method = config.get('method')
        params = config.get('params', {})

        if method == 'date_range':
            return cls.by_date_range(**params)
        elif method == 'company_subset':
            return cls.by_company_subset(**params)
        elif method == 'accession':
            return cls.by_accession(**params)
        elif method == 'random_sample':
            return cls.by_random_sample(**params)
        elif method == 'company_list':
            return cls.by_company_list(**params)
        elif method == 'recent':
            return cls.by_recent(**params)
        else:
            raise ValueError(f"Unknown selection method: {method}")

    @staticmethod
    def count_available(form: str, year: Optional[int] = None) -> int:
        """Count available filings for a form type.

        Args:
            form: Form type (e.g., '10-K', '8-K', '10-Q')
            year: Optional year to filter by

        Returns:
            Number of available filings

        Example:
            >>> count = FilingSelector.count_available("10-K", year=2024)
        """
        if year:
            filings = get_filings(form=form, year=year, quarter=1)
        else:
            # Get current year
            current_year = datetime.now().year
            filings = get_filings(form=form, year=current_year, quarter=1)

        return len(filings)

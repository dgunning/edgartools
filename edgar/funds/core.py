"""
Core classes for working with investment funds.

This module provides the main classes used to interact with investment funds:
- Fund: Represents an investment fund entity
- FundClass: Represents a specific share class of a fund
- FundSeries: Represents a fund series
"""
import logging
import re
from typing import List, Optional, Union, TYPE_CHECKING

import pandas as pd
from rich import box
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.entity.core import Entity
from edgar.richtools import repr_rich

if TYPE_CHECKING:
    from edgar._filings import Filings

log = logging.getLogger(__name__)


class Fund(Entity):
    """
    Represents an investment fund that files with the SEC.
    
    Provides fund-specific functionality like share classes, series information,
    portfolio holdings, etc.
    """
    
    def __init__(self, cik_or_identifier: Union[str, int]):
        # Import locally to avoid circular imports
        from edgar.funds.data import resolve_fund_identifier
        
        # Handle fund-specific identifiers
        super().__init__(resolve_fund_identifier(cik_or_identifier))
        self._series_id = None
        self._cached_classes = None
        self._cached_series = None  # Will be initialized as list in get_series()
        self._cached_portfolio = None
    
    @property
    def data(self) -> 'EntityData':
        """Get detailed data for this fund."""
        base_data = super().data
        
        # If we already have fund-specific data, return it
        if hasattr(base_data, 'is_fund') and base_data.is_fund:
            return base_data
            
        # Otherwise, try to convert to fund-specific data
        # This could be enhanced in the future
        return base_data
        
    def get_classes(self) -> List['FundClass']:
        """
        Get all share classes of this fund.
        
        Returns:
            List of FundClass instances representing the share classes
        """
        # Import locally to avoid circular imports
        from edgar.funds.data import get_fund_classes
        
        if self._cached_classes is None:
            self._cached_classes = get_fund_classes(self)
            
        return self._cached_classes
        
    def get_series(self) -> List['FundSeries']:
        """
        Get all fund series offered by this fund company.
        
        Returns:
            List of FundSeries instances representing the fund series offered
        """
        # Import locally to avoid circular imports
        from edgar.funds.data import get_fund_series

        if self._cached_series is None:
            self._cached_series = get_fund_series(self)
            
        return self._cached_series
        
    def get_portfolio(self) -> pd.DataFrame:
        """
        Get the most recent portfolio holdings.
        
        Returns:
            DataFrame containing portfolio holdings data
        """
        # Import locally to avoid circular imports
        from edgar.funds.data import get_fund_portfolio
        
        if self._cached_portfolio is None:
            self._cached_portfolio = get_fund_portfolio(self)
            
        return self._cached_portfolio
    
    def get_ticker(self) -> Optional[str]:
        """
        Get the primary ticker for this fund.
        
        Returns:
            Primary ticker symbol or None if not available
        """
        # Look for tickers in data first
        if hasattr(self.data, 'tickers') and self.data.tickers:
            return self.data.tickers[0]
            
        # Otherwise look for ticker in fund classes
        classes = self.get_classes()
        for cls in classes:
            if cls.ticker:
                return cls.ticker
                
        return None
    
    def __str__(self):
        ticker = self.get_ticker()
        ticker_str = f" - {ticker}" if ticker else ""
        
        if hasattr(self, 'data'):
            return f"Fund({self.data.name} [{self.cik}]{ticker_str})"
        return f"Fund(CIK={self.cik}{ticker_str})"

    
    def __rich__(self):
        """Creates a rich representation of the fund with detailed information."""
        # The title of the panel
        ticker = self.get_ticker()
        entity_title = Text.assemble("🏦 ",
                                 (self.data.name, "bold green"),
                                 " ",
                                 (f"[{self.cik}] ", "dim"),
                                 (ticker if ticker else "", "bold yellow")
                                 )
            
        # Primary Information Table
        main_info = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0, 1))
        main_info.add_column("Row", style="")  # Single column for the entire row
            
        row_parts = []
        row_parts.extend([Text("CIK", style="dim"), Text(str(self.cik), style="bold blue")])
        row_parts.extend([
                Text("Type", style="dim"),
                Text("Investment Fund", style="bold yellow"),
                Text("$", style="bold yellow")
        ])
        main_info.add_row(*row_parts)
        
        # Additional fund information
        fund_info = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        fund_info.add_column("Key", style="dim")
        fund_info.add_column("Value", style="bold")
        
        # Add any additional fund company information
        if hasattr(self.data, 'category'):
            fund_info.add_row("Category", self.data.category or "-")
        if hasattr(self.data, 'sic'):
            fund_info.add_row("SIC", self.data.sic or "-")
        
        # Get all series for this fund
        all_series = self.get_series()
        all_classes = self.get_classes()
        
        # Series panels to display
        series_panels = []
        
        # Create a table for each series showing its classes
        for series in all_series:
            # Create a table for this series
            series_table = Table(box=box.SIMPLE, padding=(0, 1))
            series_table.add_column("Class ID", style="dim")
            series_table.add_column("Class Name", style="bold")
            series_table.add_column("Ticker", style="bold yellow")
            
            # Find classes that belong to this series
            series_classes = [cls for cls in all_classes 
                             if hasattr(cls, 'series_id') and cls.series_id == series.series_id]
            
            # If we don't have explicit series associations, just add all classes for single series funds
            if not series_classes and len(all_series) == 1:
                series_classes = all_classes
                
            # Add each class to the table
            if series_classes:
                for cls in series_classes:
                    series_table.add_row(
                        cls.class_id,
                        cls.name,
                        cls.ticker or "-"
                    )
            else:
                # No classes found for this series
                series_table.add_row("-", "No share classes found", "-")
            
            # Create a panel for this series
            series_panel = Panel(
                series_table,
                title=f"[cyan bold]{series.name}[/] [dim]({series.series_id})[/]",
                border_style="cyan"
            )
            
            series_panels.append(series_panel)
        
        # If we have series, create a panel with all series
        if series_panels:
            # Create a group with all series panels
            series_group = Group(*series_panels)
            series_section = Panel(
                series_group,
                title="📈 Fund Series",
                border_style="grey50"
            )
            
            # Add the series section to content
            content_renderables = [
                Padding("", (1, 0, 0, 0)),
                Panel(Group(main_info, fund_info), title="📋 Fund Information", border_style="grey50"),
                series_section
            ]
        else:
            # No series found, just show classes directly
            if all_classes:
                classes_table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
                classes_table.add_column("Class ID")
                classes_table.add_column("Class Name")
                classes_table.add_column("Ticker", style="bold yellow")
                    
                for class_obj in all_classes:
                    classes_table.add_row(
                        class_obj.class_id,
                        class_obj.name,
                        class_obj.ticker or "-"
                    )
                    
                classes_panel = Panel(
                    classes_table,
                    title="📊 Share Classes",
                    border_style="grey50"
                )
                
                # Combine all sections
                content_renderables = [
                    Padding("", (1, 0, 0, 0)),
                    Panel(Group(main_info, fund_info), title="📋 Fund Information", border_style="grey50"),
                    classes_panel
                ]
            else:
                # No series or classes
                content_renderables = [
                    Padding("", (1, 0, 0, 0)),
                    Panel(Group(main_info, fund_info), title="📋 Fund Information", border_style="grey50"),
                    Panel(Text("No series or classes found for this fund."), title="⚠️ Note", border_style="yellow")
                ]
        
        # Create the content group
        content = Group(*content_renderables)
            
        # Create the main panel
        return Panel(
            content,
            title=entity_title,
            subtitle="SEC Fund Data",
            border_style="grey50"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

class FundClass:
    """
    Represents a specific class of an investment fund.
    
    Fund classes typically have their own ticker symbols and fee structures,
    but belong to the same underlying fund. Each class belongs to a specific
    fund series.
    """
    
    def __init__(self, class_id: str, fund: Fund, name: Optional[str] = None, 
                ticker: Optional[str] = None, series_id: Optional[str] = None):
        self.class_id = class_id
        self.fund = fund
        self._name = name
        self._ticker = ticker
        self.series_id = series_id  # The series ID this class belongs to
        
    @property
    def ticker(self) -> Optional[str]:
        """
        Get the ticker for this fund class.
        
        Returns:
            Ticker symbol or None if not available
        """
        if self._ticker:
            return self._ticker
            
        # Try to get ticker from current implementation
        try:
            # Import inside the function to avoid circular imports
            from edgar.funds import get_fund_with_filings
            fund_class = get_fund_with_filings(self.class_id)
            if fund_class and hasattr(fund_class, 'ticker'):
                self._ticker = fund_class.ticker
                return self._ticker
        except Exception:
            pass
            
        return None
        
    @property
    def name(self) -> str:
        """
        Get the name of this fund class.
        
        Returns:
            Name of the fund class
        """
        if self._name:
            return self._name
            
        # Try to get name from the current implementation
        try:
            # Import inside the function to avoid circular imports
            from edgar.funds import get_fund_with_filings
            fund_class = get_fund_with_filings(self.class_id)
            if fund_class and hasattr(fund_class, 'name'):
                self._name = fund_class.name
                return self._name
        except Exception:
            pass
            
        # Fallback to default name
        return f"{self.fund.data.name} - Class {self.class_id[-1]}"
        
    def get_performance(self) -> pd.DataFrame:
        """
        Get performance data for this fund class.
        
        Returns:
            DataFrame containing performance data
        """
        # Look for N-CSR filings (shareholder reports) which contain performance data
        filings = self.fund.get_filings(form=['N-CSR'])
        if filings:
            latest_ncsr = filings.latest()
            if latest_ncsr:
                # Parse N-CSR for performance data
                # This would be implemented in a future version
                pass
                
        return pd.DataFrame()
        
    def get_filings(self, **kwargs) -> 'Filings':
        """
        Get filings for this specific fund class.
        
        Args:
            **kwargs: Filtering parameters passed to get_filings
            
        Returns:
            Filings object with filtered filings
        """
        return self.fund.get_filings(**kwargs)
    
    def __str__(self):
        ticker_str = f" - {self.ticker}" if self.ticker else ""
        return f"FundClass({self.name} [{self.class_id}]{ticker_str})"
        
    def __repr__(self):
        return self.__str__()
        
    def __rich__(self):
        """Creates a rich representation of the fund class."""
        table = Table(
            title=None,
            box=box.ROUNDED,
            show_header=True
        )
            
        table.add_column("Fund", style="bold")
        table.add_column("Class ID", style="bold")
        table.add_column("Series ID", style="bold cyan")
        table.add_column("Ticker", style="bold yellow")
            
        table.add_row(
                self.fund.name, 
                self.class_id, 
                self.series_id or "Unknown", 
                self.ticker or ""
        )
            
        return Panel(
                table,
                title=f"🏦 {self.name}",
                subtitle="Fund Class"
        )

class FundSeries:
    """Represents a fund series with multiple share classes."""
    
    def __init__(self, series_id: str, name: str, fund: Fund):
        self.series_id = series_id
        self.name = name
        self.fund = fund
        
    def get_classes(self) -> List[FundClass]:
        """
        Get all share classes in this series.
        
        Returns:
            List of FundClass instances belonging to this specific series
        """
        # Get all classes for the fund
        all_classes = self.fund.get_classes()
        
        # Filter to get only classes for this series
        series_classes = [
            cls for cls in all_classes 
            if hasattr(cls, 'series_id') and cls.series_id == self.series_id
        ]
        
        # If we didn't find any classes specifically marked with this series_id,
        # and this is the only series for the fund, return all classes
        if not series_classes and len(self.fund.get_series()) == 1:
            return all_classes
            
        return series_classes
    
    def get_filings(self, **kwargs) -> 'Filings':
        """
        Get filings for this fund series.
        
        Args:
            **kwargs: Filtering parameters passed to get_filings
            
        Returns:
            Filings object with filtered filings
        """
        return self.fund.get_filings(**kwargs)
        
    def __str__(self):
        return f"FundSeries({self.name} [{self.series_id}])"
    
    def __repr__(self):
        return self.__str__()
    
    def __rich__(self):
        """Creates a rich representation of the fund series."""

        # Import rich components locally to prevent circular imports

            
        # Primary information
        main_info = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
        main_info.add_column("Fund", style="bold")
        main_info.add_column("Series ID", style="bold")
            
        main_info.add_row(self.fund.name, self.series_id)
            
        # Classes information
        classes = self.get_classes()
        if classes:
            classes_table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
            classes_table.add_column("Class ID")
            classes_table.add_column("Class Name")
            classes_table.add_column("Ticker", style="bold yellow")
                
            for class_obj in classes:
                classes_table.add_row(
                        class_obj.class_id,
                    class_obj.name,
                    class_obj.ticker or "-"
                )
                
            classes_panel = Panel(
                classes_table,
                title="📊 Share Classes",
                border_style="grey50"
            )
                
            content = Group(main_info, classes_panel)
        else:
            content = Group(main_info)
            
        return Panel(
            content,
            title=f"🏦 {self.name}",
            subtitle="Fund Series"
        )


def get_fund(fund_identifier: str) -> Union[Fund, FundClass]:
    """
    Get a fund or fund class by identifier.
    
    This function provides a smart factory that returns either a Fund or FundClass
    depending on the type of identifier provided.
    
    Args:
        fund_identifier: Fund ticker (e.g., 'VFINX'), Series ID (e.g., 'S000001234'), 
                        Class ID (e.g., 'C000012345'), or CIK number
                        
    Returns:
        Fund object if the identifier refers to a fund, or
        FundClass object if the identifier refers to a specific share class
    """
    # Determine if this is a fund class ticker like 'VFINX'
    if is_fund_class_ticker(fund_identifier):
        # Import data functions
        from edgar.funds.data import direct_get_fund
        
        # Try our direct implementation
        fund_info = direct_get_fund(fund_identifier)
        if fund_info and hasattr(fund_info, 'company_cik'):
            fund = Fund(fund_info.company_cik)
            # Get the class ID
            class_id = fund_info.class_contract_id
            # For fund tickers, we'll construct a standardized class name
            # based on the class name in the fund_info
            class_name = f"{fund_info.class_contract_name}"
            
            # Get series ID if available
            series_id = fund_info.series if hasattr(fund_info, 'series') else None
            
            # Create a fund class with this information
            return FundClass(
                class_id=class_id,
                fund=fund,
                name=class_name,
                ticker=fund_identifier,
                series_id=series_id
            )
        
        # Fallback to the old way
        fund = Fund(get_fund_for_class_ticker(fund_identifier))
        class_id = get_class_id_for_ticker(fund_identifier)
        
        # Try to find a series ID for this class by checking the fund's series
        series_id = None
        if fund.get_series() and len(fund.get_series()) == 1:
            # If there's only one series, assume the class belongs to it
            series_id = fund.get_series()[0].series_id
            
        return FundClass(class_id, fund, ticker=fund_identifier, series_id=series_id)
    
    # Check if this is a Class ID (C000XXXXX)
    if isinstance(fund_identifier, str) and fund_identifier.upper().startswith('C') and fund_identifier[1:].isdigit():
        # For class IDs, we need to get the parent fund first
        try:
            # Import data functions
            from edgar.funds.data import direct_get_fund_with_filings
            
            # Try our direct implementation first
            fund_info = direct_get_fund_with_filings(fund_identifier)
            if fund_info and hasattr(fund_info, 'fund_cik') and hasattr(fund_info, 'name'):
                fund = Fund(fund_info.fund_cik)
                # Try to get the series ID if available
                series_id = None
                if hasattr(fund_info, 'fund') and hasattr(fund_info.fund, 'ident_info'):
                    series_str = fund_info.fund.ident_info.get('Series', '')
                    if series_str and series_str.startswith('S'):
                        series_match = re.match(r'([S]\d+)', series_str)
                        if series_match:
                            series_id = series_match.group(1)
                
                return FundClass(fund_identifier, fund, name=fund_info.name, series_id=series_id)
        except Exception as e:
            # Fall back to the legacy implementation if needed
            try:
                # Import locally from the package
                from edgar.funds import get_fund_with_filings
                fund_info = get_fund_with_filings(fund_identifier)
                if fund_info and hasattr(fund_info, 'fund_cik'):
                    fund = Fund(fund_info.fund_cik)
                    name = fund_info.name if hasattr(fund_info, 'name') else None
                    # Try to get the series ID
                    series_id = None
                    if hasattr(fund_info, 'fund') and hasattr(fund_info.fund, 'ident_info'):
                        series_str = fund_info.fund.ident_info.get('Series', '')
                        if series_str and series_str.startswith('S'):
                            series_match = re.match(r'([S]\d+)', series_str)
                            if series_match:
                                series_id = series_match.group(1)
                    
                    return FundClass(fund_identifier, fund, name=name, series_id=series_id)
            except Exception as inner_e:
                log.warning(f"Error resolving fund class {fund_identifier}: {e} / {inner_e}")
    
    # Otherwise return a Fund
    return Fund(fund_identifier)


# Helper functions for fund ticker resolution

def is_fund_class_ticker(identifier: str) -> bool:
    """
    Determine if the given identifier is a fund class ticker.
    
    Args:
        identifier: The identifier to check
        
    Returns:
        True if it's a fund class ticker, False otherwise
    """
    from edgar.funds.data import is_fund_ticker
    return is_fund_ticker(identifier)


def get_fund_for_class_ticker(ticker: str) -> int:
    """
    Get the fund CIK associated with a class ticker.
    
    Args:
        ticker: The class ticker
        
    Returns:
        Fund CIK as integer
    """
    from edgar.funds.data import direct_get_fund
    
    try:
        fund_info = direct_get_fund(ticker)
        if fund_info and hasattr(fund_info, 'company_cik'):
            return int(fund_info.company_cik)
    except Exception as e:
        log.warning(f"Error getting fund for ticker {ticker}: {e}")
    
    return -1  # Invalid CIK


def get_class_id_for_ticker(ticker: str) -> str:
    """
    Get the class ID for a fund class ticker.
    
    Args:
        ticker: The class ticker
        
    Returns:
        Class ID string
    """
    from edgar.funds.data import direct_get_fund
    
    try:
        fund_info = direct_get_fund(ticker)
        if fund_info and hasattr(fund_info, 'class_contract_id'):
            return fund_info.class_contract_id
    except Exception as e:
        log.warning(f"Error getting class ID for ticker {ticker}: {e}")
    
    # Fallback - create a synthetic class ID
    # Many fund tickers use last character as class designator
    if len(ticker) > 0:
        return f"C000000{ticker[-1].upper()}"
    return "C0000000"
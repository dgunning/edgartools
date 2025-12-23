"""
BDC Portfolio Investment data models.

This module provides structured access to individual investment holdings
from a BDC's Schedule of Investments (SOI).
"""
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import date
from typing import Optional

import pandas as pd
from rich import box
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich

__all__ = [
    'DataQuality',
    'PortfolioInvestment',
    'PortfolioInvestments',
]

# XBRL concepts for investment data
CONCEPT_FAIR_VALUE = 'us-gaap_InvestmentOwnedAtFairValue'
CONCEPT_COST = 'us-gaap_InvestmentOwnedAtCost'
CONCEPT_PRINCIPAL = 'us-gaap_InvestmentOwnedBalancePrincipalAmount'
CONCEPT_SHARES = 'us-gaap_InvestmentOwnedBalanceShares'
CONCEPT_INTEREST_RATE = 'us-gaap_InvestmentInterestRate'
CONCEPT_PIK_RATE = 'us-gaap_InvestmentInterestRatePaidInKind'
CONCEPT_SPREAD = 'us-gaap_InvestmentBasisSpreadVariableRate'
CONCEPT_PCT_NET_ASSETS = 'us-gaap_InvestmentOwnedPercentOfNetAssets'

# Known investment types for parsing (order matters - more specific first)
INVESTMENT_TYPES = [
    # Secured Debt (used by some BDCs like Main Street)
    'First lien secured debt',
    'Second lien secured debt',
    'Senior secured debt',
    'Secured debt',
    # Loans - most specific first
    'First lien senior secured revolving loan',
    'First lien senior secured delayed draw term loan',
    'First lien senior secured term loan',
    'First lien senior secured loan',
    'Second lien senior secured loan',
    'Senior secured revolving loan',
    'Senior secured term loan',
    'Senior secured loan',
    'Senior subordinated loan',
    'Junior secured loan',
    'Subordinated certificate',
    'Subordinated debt',
    'Subordinated loan',
    'Subordinated note',
    'Unsecured debt',
    'Unsecured loan',
    'Mezzanine debt',
    'Mezzanine loan',
    'Term loan',
    'Revolver',
    'Revolving loan',
    # Preferred
    'Series A-1 preferred units',
    'Series A-1 preferred stock',
    'Series A preferred units',
    'Series A preferred shares',
    'Series A preferred stock',
    'Series B preferred units',
    'Series B preferred shares',
    'Series B preferred stock',
    'Series C-1 preferred shares',
    'Series C-2 preferred shares',
    'Series C preferred shares',
    'Series C preferred units',
    'Series D preferred units',
    'Series D units',
    'Series E units',
    'Senior preferred units',
    'Senior preferred stock',
    'Junior preferred stock',
    'Preferred shares',
    'Preferred stock',
    'Preferred units',
    'Preferred equity',
    # Common equity
    'Class A-1 common units',
    'Class A-2 common units',
    'Class A common units',
    'Class A common stock',
    'Class B common units',
    'Class B common stock',
    'Class C common units',
    'Common units',
    'Common stock',
    'Common shares',
    'Common equity',
    'Ordinary shares',
    # Class units (without common/preferred qualifier)
    'Class A-1 units',
    'Class A-2 units',
    'Class A units',
    'Class B units',
    'Class C units',
    # Member units (used by some BDCs like Main Street)
    'Class A Preferred Member Units',
    'Class B Preferred Member Units',
    'Preferred Member Units',
    'Class A Member Units',
    'Class B Member Units',
    'Member Units',
    # Other equity
    'LLC units',
    'LLC interest',
    'LP units',
    'LP interest',
    'Membership units',
    'Membership interest',
    'Member interest',
    'Class A membership units',
    'Class B membership units',
    'Partnership interest',
    'Equity interest',
    'Equity',
    # Warrants
    'Warrants to purchase shares of common stock',
    'Warrant to purchase shares of common stock',
    'Warrant to purchase common stock',
    'Warrant to purchase units',
    'Warrants',
    'Options',
    # Series units
    'Series A common units',
    'Series B common units',
    'Series A units',
    'Series B units',
    'Series C units',
    # Class interests
    'Class A common interest',
    'Class B common interest',
    'Class A preferred units',
    'Class B preferred units',
    # Certificates
    'Subordinated certificates',
    'Senior certificates',
    'Certificates',
    # Notes
    'First lien senior secured note',
    'Second lien senior secured note',
    'Senior subordinated note',
    'Senior secured note',
    'Subordinated note',
    'Unsecured note',
    # Partnership/LP interests
    'Limited partnership interests',
    'Limited partnership interest',
    'Limited partner interests',
    'Limited partner interest',
    'Limited partnership units',
    'General partnership interest',
    'Partnership units',
    'Class A LP interests',
    'Class A LP interest',
    'LP interests',
    # Notes (plural forms)
    'First lien senior secured notes',
    'Second lien senior secured notes',
    'Senior secured notes',
    'Senior subordinated notes',
    'Subordinated notes',
    'Unsecured notes',
    # Additional preferred
    'Series A-2 preferred shares',
    'Series A-3 preferred shares',
    'Series C-3 preferred shares',
    'Middle preferred shares',
    'Warrant to purchase shares of Series C preferred stock',
    'Warrant to purchase shares of Series A preferred stock',
    'Warrant to purchase shares of Series B preferred stock',
    # Additional common
    'Class A-1 common stock',
    'Series C common units',
    'Common member units',
    # Other
    'Loan instrument units',
    'Co-invest units',
    'Series E-1 preferred stock',
    'Warrant to purchase units of Class A common units',
]


def _parse_investment_identifier(dimension_label: str) -> tuple[str, str, str]:
    """
    Parse the dimension label to extract company name and investment type.

    Handles multiple formats:
    1. ARCC format: "Company Name, First lien senior secured loan"
    2. HTGC format: "Debt Investments Software and Armis, Inc., Senior Secured, Maturity Date..."
    3. Category rollups: "Debt Investments Software (52.80%)" - treated as Unknown type

    Args:
        dimension_label: The full dimension label, e.g.,
            "us-gaap:InvestmentIdentifierAxis: Company Name, First lien senior secured loan"

    Returns:
        Tuple of (identifier, company_name, investment_type)
    """
    # Strip the axis prefix
    identifier = dimension_label
    if ':' in dimension_label:
        parts = dimension_label.split(': ', 1)
        if len(parts) > 1:
            identifier = parts[1].strip()

    # Check for category rollup pattern (e.g., "Debt Investments Software (52.80%)")
    # These should be excluded as they're not individual investments
    if re.search(r'\(\d+\.\d+%\)\s*$', identifier):
        return identifier, identifier, "Unknown"

    company_name = identifier
    investment_type = "Unknown"

    # Try standard format first (investment type at end)
    for inv_type in INVESTMENT_TYPES:
        # Look for the investment type at the end, preceded by comma
        # Support optional numeric suffixes like "1", "2", "1.1", "2.1"
        pattern = rf',\s*{re.escape(inv_type)}(\s*[\d.]*)?$'
        match = re.search(pattern, identifier, re.IGNORECASE)
        if match:
            company_name = identifier[:match.start()].strip()
            investment_type = identifier[match.start() + 1:].strip()
            return identifier, company_name, investment_type

    # Try HTGC format: "Debt Investments [Industry] and [Company], Senior Secured, ..."
    # Look for ", Senior Secured" anywhere in the string
    htgc_match = re.search(r',\s*(Senior Secured)\s*,', identifier, re.IGNORECASE)
    if htgc_match:
        investment_type = "Senior Secured"
        # Extract company name - look for " and " before "Senior Secured"
        and_match = re.search(r'\s+and\s+(.+?)(?:,\s*Senior Secured)', identifier, re.IGNORECASE)
        if and_match:
            company_name = and_match.group(1).strip()
        return identifier, company_name, investment_type

    # Check for patterns like "Total [Company]" which are rollups
    if identifier.startswith('Total ') or identifier.startswith('Investments ') or \
       identifier.startswith('Investment Fund ') or identifier.startswith('Debt Investments (') or \
       identifier.startswith('Equity Investments ('):
        return identifier, identifier, "Unknown"

    return identifier, company_name, investment_type


@dataclass(frozen=True)
class DataQuality:
    """
    Data quality metrics for a PortfolioInvestments collection.

    Provides coverage percentages for each field to help users understand
    data completeness and reliability.
    """
    total_investments: int
    fair_value_coverage: float  # Percentage with fair value
    cost_coverage: float  # Percentage with cost
    principal_coverage: float  # Percentage with principal (debt only)
    interest_rate_coverage: float  # Percentage with interest rate (debt only)
    pik_rate_coverage: float  # Percentage with PIK rate
    spread_coverage: float  # Percentage with spread
    debt_count: int  # Number of debt investments
    equity_count: int  # Number of equity investments

    def __rich__(self):
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Total Investments", str(self.total_investments))
        table.add_row("Debt", str(self.debt_count))
        table.add_row("Equity", str(self.equity_count))
        table.add_row("", "")
        table.add_row("Fair Value Coverage", f"{self.fair_value_coverage:.0%}")
        table.add_row("Cost Coverage", f"{self.cost_coverage:.0%}")
        table.add_row("Principal Coverage", f"{self.principal_coverage:.0%}")
        table.add_row("Interest Rate Coverage", f"{self.interest_rate_coverage:.0%}")
        table.add_row("PIK Rate Coverage", f"{self.pik_rate_coverage:.0%}")
        table.add_row("Spread Coverage", f"{self.spread_coverage:.0%}")

        return Panel(
            table,
            title="Data Quality",
            border_style="green" if self.fair_value_coverage > 0.9 else "yellow",
            width=40
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


@dataclass(frozen=True)
class PortfolioInvestment:
    """
    A single investment holding from a BDC's Schedule of Investments.

    Represents an individual investment in a portfolio company, including
    debt instruments (loans) and equity positions.
    """
    identifier: str  # Full investment identifier
    company_name: str  # Parsed company name
    investment_type: str  # Type of investment (loan, equity, etc.)
    fair_value: Optional[Decimal] = None
    cost: Optional[Decimal] = None
    principal_amount: Optional[Decimal] = None
    shares: Optional[int] = None
    interest_rate: Optional[float] = None
    pik_rate: Optional[float] = None  # Paid-in-kind interest rate
    spread: Optional[float] = None
    percent_of_net_assets: Optional[float] = None

    @property
    def unrealized_gain_loss(self) -> Optional[Decimal]:
        """Calculate unrealized gain/loss (fair value - cost)."""
        if self.fair_value is not None and self.cost is not None:
            return self.fair_value - self.cost
        return None

    @property
    def is_debt(self) -> bool:
        """Check if this is a debt investment."""
        debt_types = ['loan', 'debt', 'mezzanine']
        return any(t in self.investment_type.lower() for t in debt_types)

    @property
    def is_equity(self) -> bool:
        """Check if this is an equity investment."""
        equity_types = ['equity', 'stock', 'shares', 'warrants', 'units', 'membership']
        return any(t in self.investment_type.lower() for t in equity_types)

    def __rich__(self):
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Field", style="dim")
        table.add_column("Value")

        table.add_row("Type", self.investment_type)

        if self.fair_value is not None:
            table.add_row("Fair Value", f"${self.fair_value:,.0f}")
        if self.cost is not None:
            table.add_row("Cost", f"${self.cost:,.0f}")
        if self.unrealized_gain_loss is not None:
            gain_loss = self.unrealized_gain_loss
            style = "green" if gain_loss >= 0 else "red"
            table.add_row("Unrealized G/L", f"[{style}]${gain_loss:,.0f}[/{style}]")
        if self.principal_amount is not None:
            table.add_row("Principal", f"${self.principal_amount:,.0f}")
        if self.shares is not None:
            table.add_row("Shares", f"{self.shares:,}")
        if self.interest_rate is not None:
            table.add_row("Interest Rate", f"{self.interest_rate:.2%}")
        if self.pik_rate is not None:
            table.add_row("PIK Rate", f"{self.pik_rate:.2%}")
        if self.spread is not None:
            table.add_row("Spread", f"{self.spread:.2%}")
        if self.percent_of_net_assets is not None:
            table.add_row("% of Net Assets", f"{self.percent_of_net_assets:.2%}")

        return Panel(
            table,
            title=self.company_name,
            subtitle=self.investment_type,
            border_style="blue",
            width=80
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class PortfolioInvestments:
    """
    A collection of portfolio investments from a BDC's Schedule of Investments.

    Provides filtering, aggregation, and display capabilities for BDC holdings.

    Attributes:
        period: The date of the data (e.g., '2024-12-31')
        data_quality: Coverage metrics for data completeness
    """

    def __init__(
        self,
        investments: list[PortfolioInvestment],
        period: Optional[str] = None
    ):
        self._investments = investments
        self._period = period

    def __len__(self) -> int:
        return len(self._investments)

    def __getitem__(self, item) -> PortfolioInvestment:
        return self._investments[item]

    def __iter__(self):
        return iter(self._investments)

    @property
    def period(self) -> Optional[str]:
        """The period date for this data (e.g., '2024-12-31')."""
        return self._period

    @property
    def data_quality(self) -> DataQuality:
        """Data quality metrics showing coverage for each field."""
        total = len(self._investments)
        if total == 0:
            return DataQuality(
                total_investments=0,
                fair_value_coverage=0.0,
                cost_coverage=0.0,
                principal_coverage=0.0,
                interest_rate_coverage=0.0,
                pik_rate_coverage=0.0,
                spread_coverage=0.0,
                debt_count=0,
                equity_count=0,
            )

        return DataQuality(
            total_investments=total,
            fair_value_coverage=sum(1 for i in self._investments if i.fair_value) / total,
            cost_coverage=sum(1 for i in self._investments if i.cost) / total,
            principal_coverage=sum(1 for i in self._investments if i.principal_amount) / total,
            interest_rate_coverage=sum(1 for i in self._investments if i.interest_rate) / total,
            pik_rate_coverage=sum(1 for i in self._investments if i.pik_rate) / total,
            spread_coverage=sum(1 for i in self._investments if i.spread) / total,
            debt_count=sum(1 for i in self._investments if i.is_debt),
            equity_count=sum(1 for i in self._investments if i.is_equity),
        )

    @property
    def total_fair_value(self) -> Decimal:
        """Total fair value of all investments."""
        return sum(
            (inv.fair_value for inv in self._investments if inv.fair_value is not None),
            Decimal(0)
        )

    @property
    def total_cost(self) -> Decimal:
        """Total cost basis of all investments."""
        return sum(
            (inv.cost for inv in self._investments if inv.cost is not None),
            Decimal(0)
        )

    @property
    def total_unrealized_gain_loss(self) -> Decimal:
        """Total unrealized gain/loss across all investments."""
        return self.total_fair_value - self.total_cost

    def filter(
        self,
        investment_type: Optional[str] = None,
        company_name: Optional[str] = None,
        min_fair_value: Optional[Decimal] = None,
    ) -> 'PortfolioInvestments':
        """
        Filter investments by criteria.

        Args:
            investment_type: Filter by investment type (partial match, case-insensitive)
            company_name: Filter by company name (partial match, case-insensitive)
            min_fair_value: Minimum fair value threshold

        Returns:
            New PortfolioInvestments with matching investments
        """
        investments = self._investments

        if investment_type:
            investments = [
                inv for inv in investments
                if investment_type.lower() in inv.investment_type.lower()
            ]

        if company_name:
            investments = [
                inv for inv in investments
                if company_name.lower() in inv.company_name.lower()
            ]

        if min_fair_value is not None:
            investments = [
                inv for inv in investments
                if inv.fair_value is not None and inv.fair_value >= min_fair_value
            ]

        return PortfolioInvestments(investments, period=self._period)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame."""
        return pd.DataFrame([
            {
                'company_name': inv.company_name,
                'investment_type': inv.investment_type,
                'fair_value': float(inv.fair_value) if inv.fair_value else None,
                'cost': float(inv.cost) if inv.cost else None,
                'principal_amount': float(inv.principal_amount) if inv.principal_amount else None,
                'shares': inv.shares,
                'interest_rate': inv.interest_rate,
                'pik_rate': inv.pik_rate,
                'spread': inv.spread,
                'percent_of_net_assets': inv.percent_of_net_assets,
            }
            for inv in self._investments
        ])

    def __rich__(self):
        table = Table(
            title="Portfolio Investments",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold",
            row_styles=["", "dim"],
        )
        table.add_column("#", justify="right", style="dim")
        table.add_column("Company", style="bold", max_width=80, overflow="fold")
        table.add_column("Type", max_width=30)
        table.add_column("Fair Value", justify="right")
        table.add_column("Cost", justify="right")
        table.add_column("Rate", justify="right")

        # Show first 30 investments
        for idx, inv in enumerate(self._investments[:30]):
            fair_value = f"${inv.fair_value:,.0f}" if inv.fair_value else ""
            cost = f"${inv.cost:,.0f}" if inv.cost else ""
            rate = f"{inv.interest_rate:.2%}" if inv.interest_rate else ""

            table.add_row(
                str(idx),
                inv.company_name,
                inv.investment_type[:30],
                fair_value,
                cost,
                rate,
            )

        if len(self._investments) > 30:
            table.add_row("...", "...", "...", "...", "...", "...")

        # Summary
        summary = Table(box=box.SIMPLE, show_header=False)
        summary.add_column("Metric", style="dim")
        summary.add_column("Value", style="bold")
        summary.add_row("Total Investments", str(len(self._investments)))
        summary.add_row("Total Fair Value", f"${self.total_fair_value:,.0f}")
        summary.add_row("Total Cost", f"${self.total_cost:,.0f}")

        gain_loss = self.total_unrealized_gain_loss
        style = "green" if gain_loss >= 0 else "red"
        summary.add_row("Unrealized G/L", f"[{style}]${gain_loss:,.0f}[/{style}]")

        from rich.console import Group
        return Panel(
            Group(table, summary),
            title="BDC Portfolio Investments",
            border_style="blue",
            expand=False,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    @classmethod
    def from_statement(
        cls,
        statement,
        period: Optional[str] = None,
        include_untyped: bool = False
    ) -> 'PortfolioInvestments':
        """
        Create PortfolioInvestments from an XBRL Schedule of Investments Statement.

        Args:
            statement: The Statement from xbrl.statements.schedule_of_investments()
            period: Optional period column (e.g., '2024-12-31'). If None, uses latest.
            include_untyped: If False (default), excludes investments with "Unknown" type.
                These are typically company-level rollup entries that would inflate totals.

        Returns:
            PortfolioInvestments collection
        """
        df = statement.to_dataframe()

        # Find the period column to use
        if period is None:
            # Find date columns (exclude metadata columns)
            date_cols = [
                col for col in df.columns
                if re.match(r'\d{4}-\d{2}-\d{2}', str(col))
            ]
            if not date_cols:
                return cls([], period=None)
            # Use the latest (first) date column
            period = date_cols[0]

        # Filter to rows with values and dimension labels
        mask = (
            df[period].notna() &
            df['dimension_label'].notna() &
            df['dimension_label'].str.contains('InvestmentIdentifierAxis', na=False)
        )
        data = df[mask].copy()

        if data.empty:
            return cls([], period=period)

        # Group by dimension_label and pivot concepts
        investments = {}
        for _, row in data.iterrows():
            dim_label = row['dimension_label']
            concept = row['concept']
            value = row[period]

            if dim_label not in investments:
                identifier, company_name, inv_type = _parse_investment_identifier(dim_label)
                investments[dim_label] = {
                    'identifier': identifier,
                    'company_name': company_name,
                    'investment_type': inv_type,
                }

            # Map concept to field
            inv = investments[dim_label]

            # Skip empty or invalid values
            if pd.isna(value) or value == '':
                continue

            try:
                if concept == CONCEPT_FAIR_VALUE:
                    inv['fair_value'] = Decimal(str(value))
                elif concept == CONCEPT_COST:
                    inv['cost'] = Decimal(str(value))
                elif concept == CONCEPT_PRINCIPAL:
                    inv['principal_amount'] = Decimal(str(value))
                elif concept == CONCEPT_SHARES:
                    inv['shares'] = int(float(value))
                elif concept == CONCEPT_INTEREST_RATE:
                    inv['interest_rate'] = float(value)
                elif concept == CONCEPT_PIK_RATE:
                    inv['pik_rate'] = float(value)
                elif concept == CONCEPT_SPREAD:
                    inv['spread'] = float(value)
                elif concept == CONCEPT_PCT_NET_ASSETS:
                    inv['percent_of_net_assets'] = float(value)
            except (ValueError, TypeError, InvalidOperation):
                # Skip values that can't be converted
                pass

        # Create PortfolioInvestment objects
        portfolio = [
            PortfolioInvestment(**inv_data)
            for inv_data in investments.values()
        ]

        # Filter out Unknown types unless include_untyped is True
        # Unknown types are typically company-level rollups that inflate totals
        if not include_untyped:
            portfolio = [inv for inv in portfolio if inv.investment_type != "Unknown"]

        # Sort by fair value (largest first)
        portfolio.sort(
            key=lambda x: x.fair_value if x.fair_value is not None else Decimal(0),
            reverse=True
        )

        return cls(portfolio, period=period)

    @classmethod
    def from_xbrl(
        cls,
        xbrl,
        period: Optional[str] = None,
        include_untyped: bool = False
    ) -> 'PortfolioInvestments':
        """
        Create PortfolioInvestments directly from XBRL facts.

        This method extracts investment data directly from XBRL facts using the
        dimension columns (dim_*), which works for BDCs that have dimensional
        investment data in facts but not in the Statement presentation hierarchy.

        Args:
            xbrl: The XBRL object from filing.xbrl()
            period: Optional period (e.g., '2024-12-31'). If None, uses latest instant.
            include_untyped: If False (default), excludes investments with "Unknown" type.

        Returns:
            PortfolioInvestments collection
        """
        all_facts = xbrl.facts.get_facts()

        # Determine the period to use
        if period is None:
            # Find the latest instant period with fair value data
            fv_facts = [
                f for f in all_facts
                if f.get('concept') == 'us-gaap:InvestmentOwnedAtFairValue'
                and f.get('period_type') == 'instant'
            ]
            if not fv_facts:
                return cls([], period=None)

            # Get unique periods and use the latest
            periods = set(f.get('period_instant') for f in fv_facts if f.get('period_instant'))
            if not periods:
                return cls([], period=None)
            period = max(periods)

        # The dimension key for investment identifier
        dim_key = 'dim_us-gaap_InvestmentIdentifierAxis'

        # Filter facts to the target period with investment dimension
        period_key = f'instant_{period}'

        # Collect all relevant concepts for the period
        relevant_concepts = {
            'us-gaap:InvestmentOwnedAtFairValue': 'fair_value',
            'us-gaap:InvestmentOwnedAtCost': 'cost',
            'us-gaap:InvestmentOwnedBalancePrincipalAmount': 'principal_amount',
            'us-gaap:InvestmentOwnedBalanceShares': 'shares',
            'us-gaap:InvestmentInterestRate': 'interest_rate',
            'us-gaap:InvestmentInterestRatePaidInKind': 'pik_rate',
            'us-gaap:InvestmentBasisSpreadVariableRate': 'spread',
            'us-gaap:InvestmentOwnedPercentOfNetAssets': 'percent_of_net_assets',
        }

        # Group facts by investment identifier
        investments = {}
        for fact in all_facts:
            # Check if this is a relevant concept
            concept = fact.get('concept')
            if concept not in relevant_concepts:
                continue

            # Check for investment dimension
            inv_identifier = fact.get(dim_key)
            if not inv_identifier:
                continue

            # Check period matches
            fact_period = fact.get('period_instant')
            if fact_period != period:
                continue

            # Initialize investment if needed
            if inv_identifier not in investments:
                # Parse the identifier to get company name and type
                # Format: "us-gaap:InvestmentIdentifierAxis: Company Name, Investment Type"
                # But here we just have the member value, not the axis prefix
                full_label = f"us-gaap:InvestmentIdentifierAxis: {inv_identifier}"
                identifier, company_name, inv_type = _parse_investment_identifier(full_label)
                investments[inv_identifier] = {
                    'identifier': identifier,
                    'company_name': company_name,
                    'investment_type': inv_type,
                }

            # Map the value to the appropriate field
            field_name = relevant_concepts[concept]
            value = fact.get('numeric_value') or fact.get('value')

            if value is None or pd.isna(value):
                continue

            try:
                if field_name in ('fair_value', 'cost', 'principal_amount'):
                    investments[inv_identifier][field_name] = Decimal(str(value))
                elif field_name == 'shares':
                    investments[inv_identifier][field_name] = int(float(value))
                elif field_name in ('interest_rate', 'pik_rate', 'spread', 'percent_of_net_assets'):
                    investments[inv_identifier][field_name] = float(value)
            except (ValueError, TypeError, InvalidOperation):
                pass

        # Create PortfolioInvestment objects
        portfolio = [
            PortfolioInvestment(**inv_data)
            for inv_data in investments.values()
        ]

        # Filter out Unknown types unless include_untyped is True
        if not include_untyped:
            portfolio = [inv for inv in portfolio if inv.investment_type != "Unknown"]

        # Sort by fair value (largest first)
        portfolio.sort(
            key=lambda x: x.fair_value if x.fair_value is not None else Decimal(0),
            reverse=True
        )

        return cls(portfolio, period=period)

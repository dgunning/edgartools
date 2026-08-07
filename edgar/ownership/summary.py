"""
High-level ownership summaries for SEC forms 3, 4 and 5.

The ``OwnershipSummary`` hierarchy (``InitialOwnershipSummary`` for Form 3,
``TransactionSummary`` for Forms 4/5) aggregates the per-row records from
``summary_records`` (``SecurityHolding`` / ``TransactionActivity``) and provides
DataFrame export and rich display of an entire filing's holdings or transactions.
``SecurityHolding`` and ``TransactionActivity`` are re-exported here for
backward compatibility.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Union

import pandas as pd
from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.ownership.core import detect_10b5_1_plan, format_numeric, safe_numeric
from edgar.ownership.summary_records import SecurityHolding, TransactionActivity

__all__ = [
    'SecurityHolding',
    'TransactionActivity',
    'OwnershipSummary',
    'InitialOwnershipSummary',
    'TransactionSummary',
]



@dataclass
class OwnershipSummary:
    """Base summary class for ownership forms"""
    reporting_date: Union[str, date]
    issuer_name: str
    issuer_ticker: str
    insider_name: str
    position: str
    form_type: str
    remarks: str = ""

    @property
    def issuer(self) -> str:
        """Return formatted issuer info"""
        return f"{self.issuer_name} ({self.issuer_ticker})"

    def to_dataframe(self, include_metadata: bool = True) -> pd.DataFrame:
        """Convert summary to DataFrame - base implementation"""
        if include_metadata:
            return pd.DataFrame([{
                'Date': pd.to_datetime(self.reporting_date),
                'Form': f"Form {self.form_type}",
                'Issuer': self.issuer_name,
                'Ticker': self.issuer_ticker,
                'Insider': self.insider_name,
                'Position': self.position,
                'Remarks': self.remarks
            }])
        return pd.DataFrame()

    def __rich__(self):
        """Base rich display implementation - should be overridden"""
        raise NotImplementedError("Subclasses must implement __rich__")


@dataclass
class InitialOwnershipSummary(OwnershipSummary):
    """Summary for Form 3 (Initial Ownership Statement)"""
    holdings: List[SecurityHolding] = field(default_factory=list)
    no_securities: bool = False

    @property
    def total_shares(self) -> int:
        """Get total non-derivative shares owned"""
        return int(sum(safe_numeric(h.shares) or 0 for h in self.holdings if not h.is_derivative))

    @property
    def has_derivatives(self) -> bool:
        """Check if there are derivative holdings"""
        return any(h.is_derivative for h in self.holdings)

    def to_dataframe(self, include_metadata: bool = True) -> pd.DataFrame:
        """Convert Form 3 holdings to DataFrame"""
        # Start with base metadata
        base_df = super().to_dataframe(include_metadata)

        # If no holdings or no_securities is True, return just metadata
        if self.no_securities or not self.holdings:
            if include_metadata:
                base_df['Total Shares'] = 0
                base_df['Has Derivatives'] = False
                base_df['Holdings'] = 0
                return base_df
            return pd.DataFrame()

        # Convert holdings to DataFrame rows
        holdings_data = []

        for holding in self.holdings:
            data = {
                'Security Type': 'Common Stock' if not holding.is_derivative else 'Derivative',
                'Security Title': holding.security_title,
                'Shares': safe_numeric(holding.shares),
                'Ownership Type': 'Direct' if holding.direct_ownership else 'Indirect',
                'Ownership Nature': holding.ownership_nature
            }

            # Add derivative-specific fields
            if holding.is_derivative:
                data.update({
                    'Underlying Security': holding.underlying_security,
                    'Underlying Shares': safe_numeric(holding.underlying_shares),
                    'Exercise Price': safe_numeric(holding.exercise_price),
                    'Exercise Date': holding.exercise_date,
                    'Expiration Date': holding.expiration_date
                })

            # Add metadata if requested
            if include_metadata:
                data.update({
                    'Date': pd.to_datetime(self.reporting_date),
                    'Form': f"Form {self.form_type}",
                    'Issuer': self.issuer_name,
                    'Ticker': self.issuer_ticker,
                    'Insider': self.insider_name,
                    'Position': self.position
                })

            holdings_data.append(data)

        # Convert to DataFrame
        return pd.DataFrame(holdings_data)

    def to_summary_dataframe(self) -> pd.DataFrame:
        """Convert to a summarized DataFrame (one row)"""
        df = super().to_dataframe(True)

        # Add summary data
        df['Total Shares'] = self.total_shares
        df['Has Derivatives'] = self.has_derivatives
        df['Holdings'] = len(self.holdings)

        # Split into non-derivative and derivative counts
        non_deriv = [h for h in self.holdings if not h.is_derivative]
        deriv = [h for h in self.holdings if h.is_derivative]

        df['Common Stock Holdings'] = len(non_deriv)
        df['Derivative Holdings'] = len(deriv)

        return df

    def __rich__(self):
        """Generate a rich display for the initial ownership summary"""
        # Create header with basic info
        header = Table.grid(padding=(0, 1))
        header.add_column(style="bold blue")
        header.add_column()
        header.add_row("Insider:", self.insider_name)
        header.add_row("Position:", self.position)
        header.add_row("Company:", self.issuer)
        header.add_row("Date:", str(self.reporting_date))
        header.add_row("Form:", f"Form {self.form_type} (Initial Statement of Beneficial Ownership)")

        elements = [header]

        if self.no_securities:
            no_holdings_text = Text("No Securities Beneficially Owned", style="italic")
            elements.append(no_holdings_text)
        elif not self.holdings:
            no_holdings_text = Text("No holdings reported", style="italic")
            elements.append(no_holdings_text)
        else:
            # Group holdings by type
            non_derivative = [h for h in self.holdings if not h.is_derivative]
            derivative = [h for h in self.holdings if h.is_derivative]

            # Display non-derivative holdings (common stock)
            if non_derivative:
                stock_table = Table(box=box.SIMPLE, title="Common Stock Holdings", title_style="bold")
                stock_table.add_column("Security", style="bold")
                stock_table.add_column("Shares", justify="right")
                stock_table.add_column("Ownership")

                for holding in non_derivative:
                    stock_table.add_row(
                        holding.security_title,
                        format_numeric(holding.shares),
                        holding.ownership_description
                    )

                elements.append(stock_table)

            # Display derivative holdings
            if derivative:
                deriv_table = Table(box=box.SIMPLE, title="Derivative Securities", title_style="bold")
                deriv_table.add_column("Security", style="bold")
                deriv_table.add_column("Underlying", style="italic")
                deriv_table.add_column("Shares", justify="right")
                deriv_table.add_column("Exercise Price", justify="right", style="green")  # Highlight exercise price
                deriv_table.add_column("Expiration", style="dim")
                deriv_table.add_column("Ownership")

                for holding in derivative:
                    deriv_table.add_row(
                        holding.security_title,
                        holding.underlying_security,
                        format_numeric(holding.underlying_shares),
                        format_numeric(holding.exercise_price, currency=True),
                        holding.expiration_date or "N/A",
                        holding.ownership_description
                    )

                elements.append(deriv_table)

        # Add remarks if present
        if self.remarks:
            remarks_text = Text(f"Remarks: {self.remarks}", style="italic")
            elements.append(remarks_text)

        # Combine all elements
        return Panel(
            Group(*elements),
            title="[bold]Initial Beneficial Ownership[/bold]",
            expand=False
        )


@dataclass
class TransactionSummary(OwnershipSummary):
    """Summary for Form 4/5 (Transaction Report)"""
    transactions: List[TransactionActivity] = field(default_factory=list)
    remaining_shares: Optional[int] = None
    has_derivative_transactions: bool = False
    aff10b5_one: Optional[bool] = None
    all_footnotes_text: str = ""

    @property
    def transaction_types(self) -> List[str]:
        """Get unique transaction types"""
        return list(set(t.transaction_type for t in self.transactions))

    @property
    def has_only_derivatives(self) -> bool:
        """Check if filing only contains derivative transactions"""
        return all(t.is_derivative for t in self.transactions)

    @property
    def has_non_derivatives(self) -> bool:
        """Check if filing contains non-derivative transactions"""
        return any(not t.is_derivative for t in self.transactions)

    @property
    def has_10b5_1_plan(self) -> Optional[bool]:
        """
        Check if any transaction in this summary was executed under a Rule 10b5-1 trading plan.

        Returns:
            The official aff10b5One value when present
            True if a 10b5-1 plan is detected in transaction or filing footnotes
            False if footnotes exist but reference no 10b5-1 plan
            None if neither the checkbox nor any footnote evidence is available
        """
        # 1. The document-level <aff10b5One> checkbox is authoritative when present.
        if self.aff10b5_one is not None:
            return self.aff10b5_one

        # 2. Fall back to footnote evidence. Per-transaction footnote attribution
        #    is frequently empty even when a 10b5-1 footnote exists, so also scan
        #    the full footnote set of the filing.
        results = [t.is_10b5_1_plan for t in self.transactions]
        full_scan = detect_10b5_1_plan(self.all_footnotes_text)

        if any(r is True for r in results) or full_scan is True:
            return True

        # Footnotes exist but reference no 10b5-1 plan.
        if any(r is False for r in results) or full_scan is False:
            return False

        # No checkbox and no footnote evidence.
        return None

    @property
    def net_change(self) -> int:
        """Calculate total net change in shares"""
        purchases = sum(t.shares_numeric or 0 for t in self.transactions
                        if t.transaction_type == "purchase")
        sales = sum(t.shares_numeric or 0 for t in self.transactions
                    if t.transaction_type == "sale")
        return int(purchases - sales)

    @property
    def net_value(self) -> float:
        """Calculate total net value"""
        purchase_value = sum(t.value_numeric or 0 for t in self.transactions
                             if t.transaction_type == "purchase")
        sale_value = sum(t.value_numeric or 0 for t in self.transactions
                         if t.transaction_type == "sale")
        return purchase_value - sale_value

    @property
    def primary_activity(self) -> str:
        """Determine the primary activity type for display purposes"""
        # Handle derivative-only case
        if self.has_only_derivatives:
            if "derivative_purchase" in self.transaction_types and "derivative_sale" in self.transaction_types:
                return "DERIVATIVE TRANSACTIONS"
            elif "derivative_purchase" in self.transaction_types:
                return "DERIVATIVE ACQUISITION"
            elif "derivative_sale" in self.transaction_types:
                return "DERIVATIVE DISPOSITION"
            else:
                return "DERIVATIVE TRANSACTION"

        # Original logic for non-derivative transactions
        if "purchase" in self.transaction_types and "sale" in self.transaction_types:
            return "Mixed Transactions"
        elif "purchase" in self.transaction_types:
            return "Purchase"
        elif "sale" in self.transaction_types:
            return "Sale"
        elif "tax" in self.transaction_types:
            return "Tax Withholding"
        elif "award" in self.transaction_types:
            return "Grant/Award"
        elif "exercise" in self.transaction_types:
            return "Option Exercise"
        elif "conversion" in self.transaction_types:
            return "Conversion"
        elif len(self.transactions) > 0:
            # Just use the first transaction type if we have transactions
            return self.transactions[0].transaction_type.title()
        else:
            return "No Transactions"

    def to_dataframe(self, include_metadata: bool = True,
                     detailed: bool = True) -> pd.DataFrame:
        """
        Convert transaction summary to DataFrame

        Args:
            include_metadata: Whether to include filing metadata (issuer, insider, etc.)
            detailed: If True, return all transactions as separate rows
                     If False, return a single summary row
        """
        if not self.transactions:
            # Return basic metadata only if no transactions
            return super().to_dataframe(include_metadata)

        if detailed:
            # Detailed mode - one row per transaction
            transactions_data = []

            for trans in self.transactions:
                data = {
                    'Transaction Type': trans.transaction_type.title(),
                    'Code': trans.code,
                    'Description': trans.display_name,
                    'Shares': trans.shares,
                    'Price': trans.price_numeric,  # Add price column
                    'Value': trans.value if trans.value > 0 else None
                }

                # Add metadata if requested
                if include_metadata:
                    data.update({
                        'Date': pd.to_datetime(self.reporting_date),
                        'Form': f"Form {self.form_type}",
                        'Issuer': self.issuer_name,
                        'Ticker': self.issuer_ticker,
                        'Insider': self.insider_name,
                        'Position': self.position,
                        'Remaining Shares': self.remaining_shares
                    })

                transactions_data.append(data)

            return pd.DataFrame(transactions_data)
        else:
            # Summary mode - aggregated transactions in one row
            df = super().to_dataframe(include_metadata)

            # Add transaction summary data
            df['Transaction Count'] = len(self.transactions)
            df['Net Change'] = self.net_change
            df['Net Value'] = self.net_value
            df['Remaining Shares'] = self.remaining_shares
            df['Primary Activity'] = self.primary_activity

            # Add counts by transaction type
            for trans_type in set(t.transaction_type for t in self.transactions):
                type_transactions = [t for t in self.transactions if t.transaction_type == trans_type]
                type_count = sum(1 for t in self.transactions if t.transaction_type == trans_type)
                type_shares = sum(t.shares_numeric or 0 for t in self.transactions if t.transaction_type == trans_type)
                df[f'{trans_type.title()} Count'] = type_count
                df[f'{trans_type.title()} Shares'] = type_shares

                if trans_type in ('purchase', 'sale'):
                    type_value = sum(t.value for t in self.transactions
                                     if t.transaction_type == trans_type and t.value > 0)
                    df[f'{trans_type.title()} Value'] = type_value

                    # Add average price
                    valid_price_transactions = [t for t in type_transactions if t.price_numeric]
                    if valid_price_transactions:
                        weighted_price_sum = sum((t.price_numeric or 0) * (t.shares_numeric or 0)
                                                 for t in valid_price_transactions)
                        weighted_shares = sum(t.shares_numeric or 0 for t in valid_price_transactions)
                        if weighted_shares > 0:
                            df[f'Avg {trans_type.title()} Price'] = weighted_price_sum / weighted_shares

            return df

    def to_summary_dataframe(self) -> pd.DataFrame:
        """Alias for to_dataframe(detailed=False) for API consistency"""
        return self.to_dataframe(detailed=False)

    def __rich__(self):
        """Generate a rich display for the transaction summary"""
        # Create header with basic info
        header = Table.grid(padding=(0, 1))
        header.add_column(style="bold blue")
        header.add_column()
        header.add_row("Insider:", self.insider_name)
        header.add_row("Position:", self.position)
        header.add_row("Company:", self.issuer)
        header.add_row("Date:", str(self.reporting_date))
        header.add_row("Form:", f"Form {self.form_type}")

        elements = [header]

        # Create transaction table with price column
        if self.transactions:
            # Group transactions by type
            non_derivative_trans = [t for t in self.transactions if not t.is_derivative]
            derivative_trans = [t for t in self.transactions if t.is_derivative]

            # Display non-derivative transactions if present
            if non_derivative_trans:
                transaction_table = Table(box=box.SIMPLE, title="Common Stock Transactions", title_style="bold")
                transaction_table.add_column("Type", style="bold")
                transaction_table.add_column("Code", justify="center")
                transaction_table.add_column("Description", style="italic")
                transaction_table.add_column("Shares", justify="right")
                transaction_table.add_column("Price/Share", justify="right")
                transaction_table.add_column("Value", justify="right")

                # Add rows for each non-derivative transaction
                for transaction in non_derivative_trans:
                    transaction_table.add_row(
                        Text(transaction.transaction_type.upper(), style=transaction.style),
                        transaction.code,
                        transaction.display_name,
                        format_numeric(transaction.shares),
                        format_numeric(transaction.price_per_share, currency=True),
                        format_numeric(transaction.value, currency=True)
                    )

                # Calculate summary data for purchases and sales
                purchase_transactions = [t for t in non_derivative_trans if t.transaction_type == "purchase"]
                sale_transactions = [t for t in non_derivative_trans if t.transaction_type == "sale"]

                # Add summary rows for non-derivative transactions
                if purchase_transactions or sale_transactions:
                    net_change = sum(t.shares_numeric or 0 for t in purchase_transactions) - \
                                 sum(t.shares_numeric or 0 for t in sale_transactions)
                    net_value = sum(t.value_numeric or 0 for t in purchase_transactions) - \
                                sum(t.value_numeric or 0 for t in sale_transactions)

                    net_style = "green bold" if net_change >= 0 else "red bold"

                    # First add NET CHANGE row
                    transaction_table.add_row(
                        Text("NET CHANGE", style=net_style),
                        "", "",
                        Text(f"{net_change:,}", style=net_style),
                        "",
                        Text(f"${net_value:,.2f}", style=net_style)
                    )

                    # Add average price info after the net change row
                    if purchase_transactions:
                        total_purchase_shares = sum(t.shares_numeric or 0 for t in purchase_transactions)
                        if total_purchase_shares > 0:
                            avg_purchase_price = sum((t.price_numeric or 0) * (t.shares_numeric or 0)
                                                     for t in purchase_transactions) / total_purchase_shares
                            transaction_table.add_row(
                                Text("AVG BUY PRICE", style="green dim"),
                                "", "", "",
                                Text(format_numeric(avg_purchase_price, currency=True), style="green"),
                                ""
                            )

                    if sale_transactions:
                        total_sale_shares = sum(t.shares_numeric or 0 for t in sale_transactions)
                        if total_sale_shares > 0:
                            avg_sale_price = sum((t.price_numeric or 0) * (t.shares_numeric or 0)
                                                 for t in sale_transactions) / total_sale_shares
                            transaction_table.add_row(
                                Text("AVG SELL PRICE", style="red dim"),
                                "", "", "",
                                Text(format_numeric(avg_sale_price, currency=True), style="red"),
                                ""
                            )

                elements.append(transaction_table)

            # Display derivative transactions if present
            if derivative_trans:
                derivative_table = Table(box=box.SIMPLE,
                                         title="Derivative Securities Transactions",
                                         title_style="bold blue")
                derivative_table.add_column("Type", style="bold")
                derivative_table.add_column("Security", style="italic")
                derivative_table.add_column("Underlying", style="italic")
                derivative_table.add_column("Shares", justify="right")
                derivative_table.add_column("Exercise Price", justify="right")
                derivative_table.add_column("Expiration", justify="right")

                # Add rows for each derivative transaction
                for transaction in derivative_trans:
                    derivative_table.add_row(
                        Text("ACQUIRE" if transaction.transaction_type == "derivative_purchase"
                             else "DISPOSE", style=transaction.style),
                        transaction.security_title,
                        transaction.underlying_security,
                        format_numeric(transaction.shares),
                        format_numeric(transaction.price_per_share, currency=True),
                        transaction.expiration_date or "N/A"
                    )

                elements.append(derivative_table)
        else:
            # No transactions handling
            no_trans_text = Text("No transactions reported", style="italic")
            elements.append(no_trans_text)

        # Position info and remarks remain unchanged...

        # Create position info
        position_table = Table.grid(padding=(0, 1))
        position_table.add_column(style="bold")
        position_table.add_column()

        if self.remaining_shares is not None:
            position_table.add_row(
                "REMAINING POSITION:",
                f"{self.remaining_shares:,} shares"
            )

        elements.append(position_table)

        # Add remarks if present
        if self.remarks:
            remarks_text = Text(f"Remarks: {self.remarks}", style="italic")
            elements.append(remarks_text)

        # Combine all elements
        return Panel(
            Group(*elements),
            title=f"[bold]Ownership Transactions ({self.primary_activity}) [/bold]",
            expand=False
        )

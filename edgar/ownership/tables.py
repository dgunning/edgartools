"""
Holdings and transactions tables for SEC ownership forms (3, 4, 5).

Contains the derivative / non-derivative holding and transaction records, their
collection wrappers (``DataHolder`` subclasses), and the ``NonDerivativeTable`` /
``DerivativeTable`` containers that parse them out of the Form 3/4/5 XML.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from bs4 import Tag
from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.core import get_bool
from edgar.datatools import convert_to_numeric
from edgar.display.formatting import yes_no
from edgar.ownership.core import (
    describe_ownership,
    format_amount,
    format_currency,
    get_footnotes,
    translate_transaction_types,
)
from edgar.ownership.models import TransactionCode
from edgar.richtools import df_to_rich_table, repr_rich
from edgar.xmltools import child_text, child_value

__all__ = [
    'DataHolder',
    'DerivativeHolding',
    'NonDerivativeHolding',
    'DerivativeTransaction',
    'NonDerivativeTransaction',
    'DerivativeHoldings',
    'NonDerivativeHoldings',
    'DerivativeTransactions',
    'NonDerivativeTransactions',
    'NonDerivativeTable',
    'DerivativeTable',
]


class DataHolder:

    def __init__(self,
                 data=None,
                 name="DataHolder"):
        self.data = data
        self.name = name

    def __len__(self):
        return 0 if self.data is None else len(self.data)

    def __getitem__(self, item):
        return self.data[item]

    @property
    def empty(self):
        return self.data is None or len(self.data) == 0

    def __rich__(self):
        return Group(Text(f"{self.name}"),
                     df_to_rich_table(self.data) if not self.empty else Text("No data")
                     )

    def __repr__(self):
        return repr_rich(self.__rich__())


@dataclass(frozen=True)
class DerivativeHolding:
    security: str
    underlying: str
    exercise_price: str
    exercise_date: str
    expiration_date: str
    underlying_shares: int
    direct_indirect: str
    nature_of_ownership: str


@dataclass(frozen=True)
class NonDerivativeHolding:
    security: str
    shares: str
    direct: bool
    nature_of_ownership: str


@dataclass(frozen=True)
class DerivativeTransaction:
    security: str
    underlying: str
    underlying_shares: str
    exercise_price: object
    exercise_date: str
    expiration_date: str
    shares: object
    direct_indirect: str
    price: str
    acquired_disposed: str
    date: str
    remaining: str
    form: str
    transaction_code: str
    equity_swap: str
    footnotes: str


@dataclass(frozen=True)
class NonDerivativeTransaction:
    security: str
    date: str
    shares: int
    remaining: int
    price: float
    acquired_disposed: str
    direct_indirect: str
    form: str
    transaction_code: str
    transaction_type: str
    equity_swap: str
    footnotes: str


class DerivativeHoldings(DataHolder):

    def __init__(self,
                 data: Optional[pd.DataFrame] = None):
        super().__init__(data, "DerivativeHoldings")

    def __getitem__(self, item):
        if not self.empty:
            rec = self.data.iloc[item]
            return DerivativeHolding(
                security=rec.Security,
                underlying=rec.Underlying,
                underlying_shares=rec.UnderlyingShares,
                exercise_price=rec.ExercisePrice,
                exercise_date=rec.ExerciseDate,
                expiration_date=rec.ExpirationDate,
                direct_indirect=rec.DirectIndirect,
                nature_of_ownership=rec['Nature Of Ownership']
            )

    def summary(self) -> pd.DataFrame:
        cols = ['Security', 'Underlying', 'UnderlyingShares', 'ExercisePrice', 'ExerciseDate']
        if self.empty:
            return pd.DataFrame(columns=cols)
        return (self.data
        .filter(cols)
        .rename(
            columns={'UnderlyingShares': 'Shares', 'ExercisePrice': 'Ex price', 'ExerciseDate': 'Ex date'})
        )

    def __rich__(self):
        table = Table('Security', 'Underlying', 'Shares', 'Exercise Price', box=box.SIMPLE, row_styles=["", "dim"])
        for row in self.data.itertuples():
            table.add_row(row.Security, row.Underlying, format_amount(row.UnderlyingShares), row.ExercisePrice)
        return Panel(table, title="⚙ Derivative Holdings")

    def __repr__(self):
        return repr_rich(self.__rich__())


class NonDerivativeHoldings(DataHolder):

    def __init__(self,
                 data: Optional[pd.DataFrame] = None):
        super().__init__(data, "NonDerivativeHoldings")

    def __getitem__(self, item):
        if not self.empty:
            rec = self.data.iloc[item]
            return NonDerivativeHolding(
                security=rec.Security,
                shares=rec.Shares,
                direct=rec.Direct,
                nature_of_ownership=rec['NatureOfOwnership']
            )

    def summary(self):
        cols = ['Shares', 'Direct', 'NatureOfOwnership', 'Security']
        if self.empty:
            return pd.DataFrame(columns=cols)
        return self.data

    def __rich__(self):
        table = Table('Security', 'Shares', 'Direct', 'Nature Of Ownership', box=box.SIMPLE, row_styles=["", "dim"])
        for row in self.data.itertuples():
            table.add_row(row.Security, format_amount(row.Shares), row.Direct, row.NatureOfOwnership, )
        return Panel(Group(table), title="\U0001F3E6 Common Stock Holdings")

    def __repr__(self):
        return repr_rich(self.__rich__())


class DerivativeTransactions(DataHolder):

    def __init__(self,
                 data: Optional[pd.DataFrame] = None):
        super().__init__(data, "DerivativeTransactions")

    def __getitem__(self, item):
        if not self.empty:
            rec = self.data.iloc[item]
            return DerivativeTransaction(
                security=rec.Security,
                underlying=rec.Underlying,
                underlying_shares=rec.UnderlyingShares,
                exercise_price=rec.ExercisePrice,
                exercise_date=rec.ExerciseDate,
                expiration_date=rec.ExpirationDate,
                shares=rec.Shares,
                direct_indirect=rec.DirectIndirect,
                price=rec.Price,
                acquired_disposed=rec.AcquiredDisposed,
                date=rec.Date,
                remaining=rec.Remaining,
                form=rec.form,
                transaction_code=rec.Code,
                equity_swap=rec.EquitySwap,
                footnotes=rec.footnotes
            )

    def shares_disposed(self):
        if not self.empty:
            return self.data[self.data.AcquiredDisposed == 'D'].Shares.sum()

    @property
    def disposals(self):
        if not self.empty:
            return self.data[self.data.AcquiredDisposed == 'D']

    @property
    def acquisitions(self):
        if not self.empty:
            return self.data[self.data.AcquiredDisposed == 'A']

    def __str__(self):
        return f"DerivativeTransaction - {len(self)} transactions"

    def summary(self):
        cols = ['Date', 'Security', 'Shares', 'Remaining', 'Price', 'Underlying', ]
        if self.empty:
            return pd.DataFrame(columns=cols[1:])
        return (self.data
                .assign(BuySell=lambda df: df.AcquiredDisposed.replace({'A': '+', 'D': '-'}))
                .assign(Shares=lambda df: df.BuySell + df.Shares.astype(str))
                .filter(cols)
                .set_index('Date')
                )

    def __rich__(self):
        return Group(
            df_to_rich_table(self.summary(), index_name='Date')
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class NonDerivativeTransactions(DataHolder):

    def __init__(self,
                 data: Optional[pd.DataFrame] = None):
        super().__init__(data, "NonDerivativeTransactions")

    def trades(self):
        # If all trades are buys (AcquiredDisplosed=='A') or sells 'D' return all data
        if self.data.AcquiredDisposed.unique() in ['A', 'D']:
            return self.data

    def __getitem__(self, item):
        if not self.empty:
            rec = self.data.iloc[item]
            return NonDerivativeTransaction(
                security=rec.Security,
                date=rec.Date,
                shares=rec.Shares,
                remaining=rec.Remaining,
                price=rec.Price,
                acquired_disposed=rec.AcquiredDisposed,
                direct_indirect=rec.DirectIndirect,
                form=rec.form,
                transaction_code=rec.Code,
                transaction_type=translate_transaction_types(rec.Code),
                equity_swap=rec.EquitySwap,
                footnotes=rec.footnotes
            )

    def summary(self) -> pd.DataFrame:
        cols = ['Date', 'Security', 'Shares', 'Remaining', 'Price']
        if self.empty:
            return pd.DataFrame(columns=cols)
        return (self
                .data
                .assign(BuySell=lambda df: df.AcquiredDisposed.replace({'A': '+', 'D': '-'}),
                        Shares=lambda df: df.BuySell + df.Shares.astype(str),
                        )
                .filter(cols)
                )

    def __rich__(self):
        table = Table('Date', 'Security', 'Action', 'Shares', 'Remaining', 'Price', "Ownership",
                      box=box.SIMPLE, row_styles=["dim", ""])
        for row in self.data.itertuples():
            table.add_row(row.Date,
                          row.Security,
                          translate_transaction_types(row.Code),
                          format_amount(row.Shares),
                          format_amount(row.Remaining),
                          format_currency(row.Price),
                          describe_ownership(row.DirectIndirect, row.NatureOfOwnership),
                          )

        return Panel(Group(table), title="\U0001F4B8 Common Stock Transactions")

    def __repr__(self):
        return repr_rich(self.__rich__())


class NonDerivativeTable:
    """
    Contains non-derivative holdings and transactions
    """

    def __init__(self,
                 holdings: NonDerivativeHoldings,
                 transactions: NonDerivativeTransactions,
                 form: str):
        self.holdings: NonDerivativeHoldings = holdings
        self.transactions: NonDerivativeTransactions = transactions
        self.form = form

    @property
    def market_trades(self):
        # Transactions with a status of 'P' or 'S'. These are trades that are not internal to the company
        if self.has_transactions:
            return self.transactions.data[self.transactions.data.Code.isin(TransactionCode.TRADES)]

    @property
    def non_market_trades(self):
        if self.has_transactions:
            # Everything that is not a common trade (external to the company)
            return self.transactions.data[~self.transactions.data.Code.isin(TransactionCode.TRADES)]

    @property
    def exercised_trades(self):
        # The trades that have the purpose Exercise
        if self.has_transactions:
            return self.transactions.data[self.transactions.data.TransactionType == 'Exercise']

    @property
    def has_holdings(self):
        return not self.holdings.empty

    @property
    def has_transactions(self):
        return not self.transactions.empty

    @property
    def empty(self):
        return self.holdings.empty and self.transactions.empty

    @classmethod
    def extract(cls,
                table: Tag,
                form: str):
        if not table:
            return cls(holdings=NonDerivativeHoldings(), transactions=NonDerivativeTransactions(), form=form)
        transactions = NonDerivativeTable.extract_transactions(table)
        holdings = NonDerivativeTable.extract_holdings(table)
        return cls(transactions=transactions, holdings=holdings, form=form)

    @staticmethod
    def extract_holdings(table: Tag) -> NonDerivativeHoldings:
        holding_tags = table.find_all("nonDerivativeHolding")
        if len(holding_tags) == 0:
            return NonDerivativeHoldings()

        holdings = []
        for holding_tag in holding_tags:
            if not isinstance(holding_tag, Tag):
                continue
            ownership_nature_tag = holding_tag.find("ownershipNature")
            if not isinstance(ownership_nature_tag, Tag):
                continue
            holding = dict(
                [
                    ('Security', child_value(holding_tag, 'securityTitle')),
                    ('Shares', child_value(holding_tag, 'sharesOwnedFollowingTransaction')),
                    ('Direct', yes_no(child_value(ownership_nature_tag, 'directOrIndirectOwnership') == "D")),
                    ('NatureOfOwnership', child_value(ownership_nature_tag, 'natureOfOwnership') or ""),
                ]
            )

            holdings.append(holding)
        # Create the holdings dataframe
        holdings_df = pd.DataFrame(holdings)

        # Convert to numeric if we can.
        if holdings_df['Shares'].str.isnumeric().all():
            holdings_df['Shares'] = convert_to_numeric(holdings_df['Shares'])

        return NonDerivativeHoldings(holdings_df)

    @staticmethod
    def extract_transactions(table: Tag) -> NonDerivativeTransactions:
        """
        Extract transactions from the table tag
        :param table:
        :return:
        """
        transaction_tags = table.find_all("nonDerivativeTransaction")
        if len(transaction_tags) == 0:
            return NonDerivativeTransactions(
                pd.DataFrame(columns=['Date', 'Security', 'Shares', 'Remaining', 'Price', 'AcquiredDisposed',
                                      'DirectIndirect', 'NatureOfOwnership'])
            )
        transactions = []
        for transaction_tag in transaction_tags:
            if not isinstance(transaction_tag, Tag):
                continue
            transaction_amt_tag = transaction_tag.find("transactionAmounts")
            if not isinstance(transaction_amt_tag, Tag):
                continue
            ownership_nature_tag = transaction_tag.find("ownershipNature")
            if not isinstance(ownership_nature_tag, Tag):
                continue
            post_transaction_tag = transaction_tag.find("postTransactionAmounts")
            if not isinstance(post_transaction_tag, Tag):
                continue

            transaction = dict(
                [
                    ('Security', child_value(transaction_tag, 'securityTitle')),
                    ('Date', child_value(transaction_tag, 'transactionDate')),
                    ('Shares', child_text(transaction_amt_tag, 'transactionShares')),
                    ('Remaining', child_text(post_transaction_tag, 'sharesOwnedFollowingTransaction')),
                    ('Price', child_text(transaction_amt_tag, 'transactionPricePerShare')),
                    ('AcquiredDisposed', child_text(transaction_amt_tag, 'transactionAcquiredDisposedCode')),
                    ('DirectIndirect', child_text(ownership_nature_tag, 'directOrIndirectOwnership')),
                    ('NatureOfOwnership', child_text(ownership_nature_tag, 'natureOfOwnership')),
                ]
            )
            transaction_coding_tag = transaction_tag.find("transactionCoding")
            if transaction_coding_tag and isinstance(transaction_coding_tag, Tag):
                transaction_coding = dict(
                    [
                        ('form', child_text(transaction_coding_tag, 'transactionFormType')),
                        ('Code', child_text(transaction_coding_tag, 'transactionCode')),
                        ('EquitySwap', get_bool(child_text(transaction_coding_tag, 'equitySwapInvolved'))),
                        ('footnotes', get_footnotes(transaction_coding_tag))
                    ]
                )
                transaction.update(transaction_coding)

            transactions.append(transaction)
        transaction_df = (pd.DataFrame(transactions)
        .assign(
            TransactionType=lambda df: df.Code.apply(lambda x: TransactionCode.TRANSACTION_TYPES.get(x, x)))
        )
        # Convert to numeric if we can.
        for column in ['Shares', 'Remaining', 'Price']:
            transaction_df[column] = convert_to_numeric(transaction_df[column])
        # Change Nan to None
        transaction_df = transaction_df.replace({np.nan: None}).infer_objects()

        return NonDerivativeTransactions(transaction_df)

    def __rich__(self):
        if self.form == "3":
            holding_or_transaction = self.holdings.__rich__()
        else:
            holding_or_transaction = self.transactions.__rich__()
        if not holding_or_transaction:
            holding_or_transaction = Text("")
        return Panel(holding_or_transaction, title="Common stock acquired, displosed or benefially owned")

    def __repr__(self):
        return repr_rich(self.__rich__())


class DerivativeTable:
    """
    A container for the holdings and transactions in the <derivativeTable></derivativeTable>
    """

    def __init__(self,
                 holdings: DerivativeHoldings,
                 transactions: DerivativeTransactions,
                 form: str):
        self.holdings: DerivativeHoldings = holdings
        self.transactions: DerivativeTransactions = transactions
        self.form = form

    @staticmethod
    def _empty_trades() -> pd.DataFrame:
        return pd.DataFrame(columns=['Date', 'Security', 'Shares', 'Remaining', 'Price', 'Underlying', ])

    @property
    def derivative_trades(self):
        if self.has_transactions:
            return DataHolder(self.transactions.data)

    @property
    def has_holdings(self):
        return not self.holdings.empty

    @property
    def has_transactions(self):
        return not self.transactions.empty

    @property
    def empty(self):
        return self.holdings.empty and self.transactions.empty

    @classmethod
    def extract(cls,
                table: Tag,
                form: str):
        if not table:
            return cls(holdings=DerivativeHoldings(), transactions=DerivativeTransactions(), form=form)
        transactions = cls.extract_transactions(table)
        holdings = cls.extract_holdings(table)
        return cls(transactions=transactions, holdings=holdings, form=form)

    @staticmethod
    def extract_transactions(table: Tag) -> DerivativeTransactions:
        trans_tags = table.find_all("derivativeTransaction")
        if len(trans_tags) == 0:
            return DerivativeTransactions()

        transactions = []
        for transaction_tag in trans_tags:
            if not isinstance(transaction_tag, Tag):
                continue
            transaction_amt_tag = transaction_tag.find("transactionAmounts")
            if not isinstance(transaction_amt_tag, Tag):
                continue
            underlying_tag = transaction_tag.find("underlyingSecurity")
            if not isinstance(underlying_tag, Tag):
                continue
            ownership_nature_tag = transaction_tag.find("ownershipNature")
            if not isinstance(ownership_nature_tag, Tag):
                continue
            post_transaction_tag = transaction_tag.find("postTransactionAmounts")
            if not isinstance(post_transaction_tag, Tag):
                continue

            transaction = dict(
                [
                    ('Security', child_value(transaction_tag, 'securityTitle')),
                    ('Underlying', child_value(underlying_tag, 'underlyingSecurityTitle')),
                    ('UnderlyingShares', child_value(underlying_tag, 'underlyingSecurityShares')),
                    ('ExercisePrice', child_value(transaction_tag, 'conversionOrExercisePrice')),
                    ('ExerciseDate', child_value(transaction_tag, 'exerciseDate')),
                    ('ExpirationDate', child_value(transaction_tag, 'expirationDate')),
                    ('Shares', child_text(transaction_tag, 'transactionShares')),
                    ('DirectIndirect', child_text(ownership_nature_tag, 'directOrIndirectOwnership')),
                    ('Price', child_text(transaction_amt_tag, 'transactionPricePerShare')),
                    ('AcquiredDisposed', child_text(transaction_amt_tag, 'transactionAcquiredDisposedCode')),
                    ('Date', child_value(transaction_tag, 'transactionDate')),
                    ('Remaining', child_text(post_transaction_tag, 'sharesOwnedFollowingTransaction')),
                ]
            )

            # Add transaction coding
            transaction_coding_tag = transaction_tag.find("transactionCoding")
            if transaction_coding_tag and isinstance(transaction_coding_tag, Tag):
                transaction_coding = dict(
                    [
                        ('form', child_text(transaction_coding_tag, 'transactionFormType')),
                        ('Code', child_text(transaction_coding_tag, 'transactionCode')),
                        ('EquitySwap', get_bool(child_text(transaction_coding_tag, 'equitySwapInvolved'))),
                        ('footnotes', get_footnotes(transaction_coding_tag))
                    ]
                )
                transaction.update(transaction_coding)
            transactions.append(transaction)

        # Now create the transaction dataframe
        transaction_df = (pd.DataFrame(transactions)
        .assign(
            TransactionType=lambda df: df.Code.apply(lambda x: TransactionCode.TRANSACTION_TYPES.get(x, x)))
        )
        # convert to numeric if we can
        for col in ['Shares', 'UnderlyingShares', 'ExercisePrice', 'Price', 'Remaining']:
            try:
                transaction_df[col] = pd.to_numeric(transaction_df[col])
            except ValueError:
                # Handle the case where conversion fails
                pass
                # print(f"Warning: Conversion failed for column {col}")

        return DerivativeTransactions(transaction_df)

    @staticmethod
    def extract_holdings(table: Tag) -> DerivativeHoldings:
        holding_tags = table.find_all("derivativeHolding")
        if len(holding_tags) == 0:
            return DerivativeHoldings()
        holdings = []
        for holding_tag in holding_tags:
            if not isinstance(holding_tag, Tag):
                continue
            underlying_security_tag = holding_tag.find("underlyingSecurity")
            if not isinstance(underlying_security_tag, Tag):
                continue
            ownership_nature = holding_tag.find("ownershipNature")
            if not isinstance(ownership_nature, Tag):
                continue

            holding = dict(
                [
                    ('Security', child_value(holding_tag, 'securityTitle')),
                    ('Underlying', child_value(underlying_security_tag, 'underlyingSecurityTitle')),
                    ('UnderlyingShares', child_value(underlying_security_tag, 'underlyingSecurityShares')),
                    ('ExercisePrice', child_value(holding_tag, 'conversionOrExercisePrice')),
                    ('ExerciseDate', child_value(holding_tag, 'exerciseDate')),
                    ('ExpirationDate', child_value(holding_tag, 'expirationDate')),
                    ('DirectIndirect', child_text(ownership_nature, 'directOrIndirectOwnership')),
                    ('Nature Of Ownership', child_value(ownership_nature, 'natureOfOwnership')),
                ]
            )
            holdings.append(holding)
        holdings_dataframe = (pd.DataFrame(holdings)
                              .assign(UnderlyingShares=lambda df: convert_to_numeric(df.UnderlyingShares))
                              )

        return DerivativeHoldings(holdings_dataframe)

    def __rich__(self):
        renderables = []
        if self.form == "3":
            if self.has_holdings:
                renderables.append(self.holdings)
        else:
            if self.has_transactions:
                renderables.append(self.transactions)
        if len(renderables) == 0:
            renderables.append(Text(""))
        return Panel(Group(*renderables), title="Derivative table")

    def __repr__(self):
        return repr_rich(self.__rich__())

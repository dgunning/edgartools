"""
Holdings and transactions row records for SEC ownership forms (3, 4, 5).

Contains the derivative / non-derivative holding and transaction records and
their collection wrappers (``DataHolder`` subclasses). The ``NonDerivativeTable``
/ ``DerivativeTable`` containers that parse these out of the Form 3/4/5 XML live
in ``table_containers``.
"""
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.ownership.core import (
    describe_ownership,
    format_amount,
    format_currency,
    translate_transaction_types,
)
from edgar.richtools import df_to_rich_table, repr_rich

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



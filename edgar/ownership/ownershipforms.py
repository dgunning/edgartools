"""
Ownership contains the domain model for forms
- 3 initial ownership
- 4 changes in ownership and
- 5 annual ownership statement

The top level object is Ownership

"""
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from typing import List, Dict, Tuple, Optional, Union, Any

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup, ResultSet
from bs4 import Tag
from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table, Column

from edgar._party import Address
from edgar.core import (IntString, get_bool)
from edgar.formatting import reverse_name, yes_no
from edgar.datatools import convert_to_numeric
from edgar.entity import Entity
from edgar.ownership.core import format_amount, format_currency, safe_numeric, format_numeric
from edgar.richtools import repr_rich, df_to_rich_table
from edgar.xmltools import (child_text, child_value)
import itertools
from edgar.ownership.html_render import ownership_to_html
__all__ = [
    'Owner',
    'Issuer',
    'Address',
    'Footnotes',
    'OwnerSignature',
    'TransactionCode',
    'Ownership',
    'Form3',
    'Form4',
    'Form5',
    'DerivativeHolding',
    'DerivativeHoldings',
    'translate_ownership',
    'NonDerivativeHolding',
    'NonDerivativeHoldings',
    'DerivativeTransaction',
    'DerivativeTransactions',
    'ReportingOwners',
    'ReportingRelationship',
    'PostTransactionAmounts',
    'NonDerivativeTransaction',
    'NonDerivativeTransactions',
    'TransactionActivity',
    'TransactionSummary',
    'OwnershipSummary',
]


def describe_ownership(direct_indirect: str, nature_of_ownership: str) -> str:
    """
    Describe the ownership
    :param direct_indirect:
    :param nature_of_ownership:
    :return:
    """
    if direct_indirect == 'D':
        return "Direct"
    if direct_indirect == 'I':
        if nature_of_ownership:
            return f"Indirect ({nature_of_ownership})"
        return "Indirect"
    return ""


def translate(value: str, translations: Dict[str, str]) -> str:
    return translations.get(value, value)


def translate_buy_sell(buy_sell: str) -> str:
    return translate(buy_sell, BUY_SELL)


def translate_transaction_types(code: str) -> str:
    return translate(code, TransactionCode.TRANSACTION_TYPES)


BUY_SELL = {'A': 'Buy', 'D': 'Sell'}

DIRECT_OR_INDIRECT_OWNERSHIP = {'D': 'Direct', 'I': 'Indirect'}

FORM_DESCRIPTIONS = {'3': 'Initial beneficial ownership',
                     '4': 'Changes in beneficial ownership',
                     '5': 'Annual statement of beneficial ownership',
                     }


def translate_ownership(value: str) -> str:
    return translate(value, DIRECT_OR_INDIRECT_OWNERSHIP)


class Issuer:

    def __init__(self,
                 cik: IntString,
                 name: str,
                 ticker: str):
        self.cik: IntString = cik
        self.name: str = name
        self.ticker: str = ticker

    def __repr__(self):
        return f"Issuer(cik='{self.cik or ''}', name={self.name or ''}, ticker={self.ticker or ''})"


class ReportingRelationship:
    """
    The relationship of the reporter to the company
    """

    def __init__(self,
                 is_director: bool,
                 is_officer: bool,
                 is_other: bool,
                 is_ten_pct_owner: bool,
                 officer_title: str = None):
        self.is_director: bool = is_director
        self.is_officer: bool = is_officer
        self.is_ten_pct_owner: bool = is_ten_pct_owner
        self.is_other: bool = is_other
        self.officer_title: str = officer_title

    def __repr__(self):
        return (f"ReportingRelationship(is_director={self.is_director}, is_officer={self.is_officer}, "
                f"is_ten_pct_owner={self.is_ten_pct_owner}, officer_title={self.officer_title})"
                )


class TransactionCode:

    def __init__(self,
                 form: str,
                 code: str,
                 equity_swap_involved: bool,
                 footnote: str):
        self.form: str = form
        self.code: str = code
        self.equity_swap: bool = equity_swap_involved
        self.footnote: str = footnote

    @property
    def description(self):
        return TransactionCode.DESCRIPTIONS.get(self.code, self.code)

    DESCRIPTIONS = {'A': 'Grant or award',
                    'C': 'Conversion of derivative',
                    'D': 'Disposition to the issuer',
                    'E': 'Expiration of short position',
                    'F': 'Payment of exercise price or tax',
                    'G': 'Gift',
                    'H': 'Expiration of long position',
                    'I': 'Disposition otherwise than to the issuer',
                    'M': 'Exercise or conversion of exempt derivative',
                    'O': 'Exercise of out-of-the-money derivative',
                    'P': 'Open market or private purchase',
                    'S': 'Open market or private sale',
                    'U': 'Disposition pursuant to a tender of shares',
                    'X': 'Exercise of in-the-money or at-the-money derivative',
                    'Z': 'Deposit or withdrawal from voting trust'}

    TRANSACTION_TYPES = {'A': 'Award',
                         'C': 'Conversion',
                         'D': 'Disposition',
                         'E': 'Expiration',
                         'F': 'Tax Withholding',
                         'G': 'Gift',
                         'H': 'Expiration',
                         'I': 'Discretionary',
                         'J': 'Other',
                         'M': 'Exercise',
                         'O': 'Exercise',
                         'P': 'Purchase',
                         'S': 'Sale',
                         'U': 'Disposition',
                         'W': 'Willed',
                         'X': 'Exercise',
                         'Z': 'Trust'
                         }

    TRADES = ['P', 'S']

    def __repr__(self):
        return (f"ReportingRelationship(form={self.form}, code={self.code}, "
                f"equity_swap={self.equity_swap}, footnote={self.footnote})")


class PostTransactionAmounts:

    def __init__(self,
                 shares_owned: int):
        self.share_owned: int = shares_owned

    def __repr__(self):
        return f"PostTransactionAmounts(shares_owned={self.share_owned})"


class Underyling:

    def __init__(self,
                 underlying_security_title: str,
                 number_of_shares: int):
        self.security = underlying_security_title
        self.num_shares = number_of_shares

    def __repr__(self):
        return f"Underlying(security={self.security}, shares={self.num_shares})"


class OwnerSignature:

    def __init__(self,
                 signature: str,
                 date: str):
        self.signature = signature
        self.date = date

    def __rich__(self):
        return Text(f"{self.date} {self.signature}")

    def __repr__(self):
        return repr_rich(self.__rich__())


class OwnerSignatures:

    def __init__(self, signatures: List[OwnerSignature]):
        self.signatures = signatures

    def __len__(self):
        return len(self.signatures)

    def __rich__(self):
        title = "\U0001F58A Signature"
        if len(self.signatures) > 1:
            title += "s"

        return Panel(Group(*self.signatures), title=title)

    def __repr__(self):
        return repr_rich(self.__rich__())


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


class Footnotes:

    def __init__(self,
                 footnotes: Dict[str, str]):
        self._footnotes = footnotes

    def __getitem__(self, item):
        return self._footnotes[item]

    def get(self,
            footnote_id: str,
            default_value: str = None):
        return self._footnotes.get(footnote_id, default_value)

    def summary(self) -> pd.DataFrame:
        return pd.DataFrame([(k, v) for k, v in self._footnotes.items()],
                            columns=["id", "footnote"]).set_index("id")

    def __len__(self):
        return len(self._footnotes)

    def __str__(self):
        return str(self._footnotes)

    def __rich__(self):
        table = Table("", "Footnote", title="Footnotes", box=box.SIMPLE, row_styles=["", "dim"])
        for id, footnote in self._footnotes.items():
            table.add_row(id, footnote)
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())

    @classmethod
    def extract(cls,
                tag: Tag):
        footnotes_el = tag.find("footnotes")
        return cls(
            {el.attrs['id']: el.text.strip()
             for el in footnotes_el.find_all("footnote")
             } if footnotes_el else {}
        )


def transaction_footnote_id(tag: Tag) -> Tuple[str, str]:
    return 'footnote', tag.attrs.get("id") if tag else None


def get_footnotes(tag: Tag) -> str:
    return '\n'.join([
        el.attrs.get('id') for el in tag.find_all("footnoteId")
    ])


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
                 data: pd.DataFrame = None):
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
        return Panel(table, title="\u2699 Derivative Holdings")

    def __repr__(self):
        return repr_rich(self.__rich__())


class NonDerivativeHoldings(DataHolder):

    def __init__(self,
                 data: pd.DataFrame = None):
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
                 data: pd.DataFrame = None):
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
                 data: pd.DataFrame = None):
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
            ownership_nature_tag = holding_tag.find("ownershipNature")
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
            transaction_amt_tag = transaction_tag.find("transactionAmounts")
            ownership_nature_tag = transaction_tag.find("ownershipNature")
            post_transaction_tag = transaction_tag.find("postTransactionAmounts")

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
            if transaction_coding_tag:
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
            transaction_amt_tag = transaction_tag.find("transactionAmounts")
            underlying_tag = transaction_tag.find("underlyingSecurity")
            ownership_nature_tag = transaction_tag.find("ownershipNature")
            post_transaction_tag = transaction_tag.find("postTransactionAmounts")

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
            if transaction_coding_tag:
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
            underlying_security_tag = holding_tag.find("underlyingSecurity")
            ownership_nature = holding_tag.find("ownershipNature")

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


@dataclass(frozen=True)
class Owner:
    cik: str
    is_company: bool
    name: str
    address: Address
    is_director: bool
    is_officer: bool
    is_other: bool
    is_ten_pct_owner: bool
    officer_title: str = None

    @property
    def position(self):
        return Owner.display_title(officer_title=self.officer_title,
                                   is_officer=self.is_officer,
                                   is_director=self.is_director,
                                   is_other=self.is_other,
                                   is_ten_pct_owner=self.is_ten_pct_owner)

    @staticmethod
    def display_title(officer_title: str = None,
                      is_officer: bool = False,
                      is_director: bool = False,
                      is_other: bool = False,
                      is_ten_pct_owner: bool = False):
        if officer_title:
            return officer_title

        title: str = ""
        if is_director:
            title = "Director"
        elif is_officer:
            title = "Officer"
        elif is_other:
            title = "Other"

        if is_ten_pct_owner:
            title = f"{title}, 10% Owner" if title else "10% Owner"
        return title

    def __repr__(self):
        return f"Owner(cik='{self.cik or ''}', name={self.name or ''})"


class ReportingOwners():

    def __init__(self, owners: List[Owner]):
        self.owners: List[Owner] = owners

    def __getitem__(self, item):
        return self.owners[item]

    def __len__(self):
        return len(self.owners)

    def __rich__(self):
        table = Table(Column("Owner", style="bold deep_sky_blue1"),
                      "Position",
                      "Cik",
                      "Location", box=box.SIMPLE,
                      row_styles=["", "bold"])
        for owner in self.owners:
            table.add_row(owner.name, owner.position, owner.cik, f"{owner.address.city}")

        title = "\U0001F468\u200D\U0001F4BC Reporting Owner"
        if len(self) > 1:
            title += "s"
        return Panel(table, title=title, expand=False)

    def __repr__(self):
        return repr_rich(self.__rich__())

    @classmethod
    def from_reporting_owner_tags(cls, reporting_owners: ResultSet, remarks: str = ''):
        # Reporting Owner
        owners = []

        for reporting_owner_tag in reporting_owners:
            reporting_owner_id_tag = reporting_owner_tag.find("reportingOwnerId")

            cik = child_text(reporting_owner_id_tag, "rptOwnerCik")
            owner_name = child_text(reporting_owner_id_tag, "rptOwnerName")

            # Check if it is a company. If not, reverse the name
            entity = Entity(int(cik))

            # Check if the entity is a company or an individual
            is_company = entity and entity.data.is_company
            if not is_company:
                owner_name = reverse_name(owner_name)

            reporting_owner_address_tag = reporting_owner_tag.find("reportingOwnerAddress")

            reporting_owner_rel_tag = reporting_owner_tag.find("reportingOwnerRelationship")

            is_director = get_bool(child_text(reporting_owner_rel_tag, "isDirector"))
            is_officer = get_bool(child_text(reporting_owner_rel_tag, "isOfficer"))
            is_ten_pct_owner = get_bool(child_text(reporting_owner_rel_tag, "isTenPercentOwner"))
            is_other = get_bool(child_text(reporting_owner_rel_tag, "isOther"))
            officer_title = child_text(reporting_owner_rel_tag, "officerTitle")

            # Sometimes the officer title contains 'See remarks'
            if officer_title and 'see remarks' in officer_title.lower():
                officer_title = remarks

            # Owner
            owner = Owner(
                cik=cik,
                is_company=is_company,
                name=owner_name,
                address=Address(
                    street1=child_text(reporting_owner_address_tag, "rptOwnerStreet1"),
                    street2=child_text(reporting_owner_address_tag, "rptOwnerStreet2"),
                    city=child_text(reporting_owner_address_tag, "rptOwnerCity"),
                    state_or_country=child_text(reporting_owner_address_tag, "rptOwnerState"),
                    state_or_country_description=child_text(reporting_owner_address_tag, "rptOwnerStateDescription"),
                    zipcode=child_text(reporting_owner_address_tag, "rptOwnerZipCode")
                ),
                is_director=is_director,
                is_officer=is_officer,
                is_other=is_other,
                is_ten_pct_owner=is_ten_pct_owner,
                officer_title=officer_title
            )
            owners.append(owner)
        return cls(owners)


@dataclass
class SecurityHolding:
    """Represents a security holding (for Form 3)"""
    security_type: str  # "non-derivative" or "derivative"
    security_title: str
    shares: int
    direct_ownership: bool
    ownership_nature: str = ""
    underlying_security: str = ""
    underlying_shares: int = 0
    exercise_price: Optional[float] = None
    exercise_date: str = ""
    expiration_date: str = ""

    @property
    def ownership_description(self) -> str:
        """Get description of ownership"""
        if self.direct_ownership:
            return "Direct"
        elif self.ownership_nature:
            return f"Indirect ({self.ownership_nature})"
        else:
            return "Indirect"

    @property
    def is_derivative(self) -> bool:
        """Check if this is a derivative security"""
        return self.security_type == "derivative"


@dataclass
class TransactionActivity:
    """Represents a specific transaction activity type"""
    transaction_type: str
    code: str
    shares: Any = 0  # Handle footnote references
    value: Any = 0
    price_per_share: Any = None  # Add explicit price per share field
    description: str = ""
    security_type: str = "non-derivative"  # "non-derivative" or "derivative"
    security_title: str = ""
    underlying_security: str = ""  # For derivative securities
    exercise_date: Optional[str] = None
    expiration_date: Optional[str] = None

    @property
    def shares_numeric(self) -> Optional[int]:
        """Get shares as a numeric value, handling footnotes"""
        return safe_numeric(self.shares)

    @property
    def value_numeric(self) -> Optional[float]:
        """Get value as a numeric value, handling footnotes"""
        return safe_numeric(self.value)

    @property
    def price_numeric(self) -> Optional[float]:
        """Get price as a numeric value, handling footnotes"""
        return safe_numeric(self.price_per_share)

    @property
    def is_derivative(self) -> bool:
        """Check if this is a derivative transaction"""
        return self.security_type == "derivative"

    @property
    def code_description(self) -> str:
        """Get a description for the transaction code"""
        code_descriptions = {
            'P': 'Open Market Purchase',
            'S': 'Open Market Sale',
            'A': 'Grant/Award',
            'M': 'Option Exercise',
            'F': 'Tax Withholding',
            'G': 'Gift',
            'X': 'Option Exercise',
            'D': 'Disposition to Issuer',
            'C': 'Conversion',
            'E': 'Expiration of Short Position',
            'H': 'Expiration of Long Position',
            'I': 'Discretionary Transaction',
            'O': 'Exercise of Out-of-Money Derivative',
            'U': 'Disposition (Tender of Shares)',
            'Z': 'Deposit/Withdrawal (Voting Trust)'
        }
        return code_descriptions.get(self.code, f"Other ({self.code})")

    @property
    def display_name(self) -> str:
        """Get the display name for the transaction"""
        if self.description:
            return self.description

        if self.security_type == "derivative":
            base_desc = self.code_description
            if self.underlying_security:
                return f"{base_desc} ({self.underlying_security})"
            return base_desc

        return self.code_description

    @property
    def style(self) -> str:
        """Get appropriate style for the transaction type"""
        if self.transaction_type == "purchase":
            return "green bold"
        elif self.transaction_type == "sale":
            return "red bold"
        elif self.transaction_type == "tax":
            return "yellow"
        elif self.transaction_type == "award":
            return "blue"
        elif self.transaction_type == "exercise":
            return "magenta"
        elif self.transaction_type == "conversion":
            return "cyan"
        elif self.transaction_type == "expiration":
            return "dim"
        else:
            return "white"


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
        return sum(safe_numeric(h.shares) or 0 for h in self.holdings if not h.is_derivative)

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
                deriv_table.add_column("Expiration",  style="dim")
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
    def net_change(self) -> int:
        """Calculate total net change in shares"""
        purchases = sum(t.shares_numeric or 0 for t in self.transactions
                        if t.transaction_type == "purchase")
        sales = sum(t.shares_numeric or 0 for t in self.transactions
                    if t.transaction_type == "sale")
        return purchases - sales

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


class Ownership:
    """
    Contains information from ownership documents - Forms 3, 4 and 5
    """

    def __init__(self,
                 form: str,
                 footnotes: Footnotes,
                 issuer: Issuer,
                 reporting_owners: ReportingOwners,
                 non_derivative_table: NonDerivativeTable,
                 derivative_table: DerivativeTable,
                 signatures: OwnerSignatures,
                 reporting_period: str,
                 remarks: str,
                 no_securities: bool = False
                 ):
        self.form: str = form
        self.footnotes: Footnotes = footnotes
        self.issuer: Issuer = issuer
        self.reporting_owners: ReportingOwners = reporting_owners
        self.non_derivative_table: NonDerivativeTable = non_derivative_table
        self.derivative_table: DerivativeTable = derivative_table
        self.signatures: OwnerSignatures = signatures
        self.reporting_period: str = reporting_period
        self.remarks: str = remarks
        self.no_securities = no_securities

    def extract_form3_holdings(self) -> List[SecurityHolding]:
        """Extract all holdings from Form 3"""
        holdings = []

        # Extract non-derivative holdings
        if self.non_derivative_table and self.non_derivative_table.has_holdings:
            for _, row in self.non_derivative_table.holdings.data.iterrows():
                holdings.append(SecurityHolding(
                    security_type="non-derivative",
                    security_title=row.Security,
                    shares=row.Shares,
                    direct_ownership=row.Direct == "Yes",
                    ownership_nature=row.NatureOfOwnership
                ))

        # Extract derivative holdings
        if self.derivative_table and self.derivative_table.has_holdings:
            for _, row in self.derivative_table.holdings.data.iterrows():
                holdings.append(SecurityHolding(
                    security_type="derivative",
                    security_title=row.Security,
                    shares=0,  # Derivative securities don't have direct shares
                    direct_ownership=row.DirectIndirect == "D",
                    ownership_nature=row.get("Nature Of Ownership", ""),
                    underlying_security=row.Underlying,
                    underlying_shares=row.UnderlyingShares,
                    exercise_price=row.ExercisePrice if pd.notna(row.ExercisePrice) else None,
                    exercise_date=row.ExerciseDate if pd.notna(row.ExerciseDate) else "",
                    expiration_date=row.ExpirationDate if pd.notna(row.ExpirationDate) else ""
                ))

        return holdings

    def get_transaction_activities(self) -> List[TransactionActivity]:
        """Extract all transaction activities from the filing"""
        activities = []

        # Process non-derivative market transactions (P and S codes)
        if self.market_trades is not None and not self.market_trades.empty:
            for _, row in self.market_trades.iterrows():
                transaction_type = "purchase" if row.AcquiredDisposed == 'A' else "sale"
                row_shares = int("0" + "".join(itertools.takewhile(str.isdigit, row.Shares))) \
                    if isinstance(row.Shares, str) else row.Shares
                activities.append(TransactionActivity(
                    transaction_type=transaction_type,
                    code=row.Code,
                    shares=row_shares,
                    price_per_share=row.Price,
                    value=row_shares * row.Price if not pd.isna(row.Price) else 0,
                    security_type="non-derivative",
                    security_title=row.Security,
                ))

        # Process non-derivative non-market transactions (other codes)
        non_market = self.non_derivative_table.non_market_trades
        if non_market is not None and isinstance(non_market, pd.DataFrame) and not non_market.empty:
            for _, row in non_market.iterrows():
                # Determine transaction type from code
                if row.Code == 'M':  # Option exercise
                    transaction_type = "exercise"
                elif row.Code == 'A':  # Award
                    transaction_type = "award"
                elif row.Code == 'F':  # Tax withholding
                    transaction_type = "tax"
                elif row.Code == 'G':  # Gift
                    transaction_type = "gift"
                elif row.Code == 'C':  # Conversion
                    transaction_type = "conversion"
                elif row.AcquiredDisposed == 'A':
                    transaction_type = "other_acquisition"
                else:
                    transaction_type = "other_disposition"

                row_shares = int("0" + "".join(itertools.takewhile(str.isdigit, row.Shares))) \
                    if isinstance(row.Shares, str) else row.Shares
                activities.append(TransactionActivity(
                    transaction_type=transaction_type,
                    code=row.Code,
                    shares=row_shares,
                    price_per_share=row.Price if pd.notna(row.Price) else None,  # Add price
                    # Don't calculate value for non-market transactions unless price available
                    value=row_shares * row.Price if pd.notna(row.Price) and row.Price > 0 else 0,
                    security_type="non-derivative",
                    security_title=row.Security,
                ))

        # Process derivative transactions
        if self.derivative_table and self.derivative_table.has_transactions:
            derivative_trans = self.derivative_table.transactions.data
            if not derivative_trans.empty:
                for _, row in derivative_trans.iterrows():
                    transaction_type = "derivative_purchase" if row.AcquiredDisposed == 'A' else "derivative_sale"
                    underlying, price = safe_numeric(row.UnderlyingShares), safe_numeric(row.Price)

                    row_underlying_shares = int("0" + "".join(itertools.takewhile(str.isdigit, row.UnderlyingShares))) \
                        if isinstance(row.UnderlyingShares, str) else row.UnderlyingShares
                    activities.append(TransactionActivity(
                        transaction_type=transaction_type,
                        code=row.Code,
                        shares=row_underlying_shares,
                        price_per_share=row.ExercisePrice if pd.notna(row.ExercisePrice) else None,
                        value=row_underlying_shares * row.Price if price and underlying else 0,
                        security_type="derivative",
                        security_title=row.Security,
                        underlying_security=row.Underlying,
                        exercise_date=row.ExerciseDate if pd.notna(row.ExerciseDate) else None,
                        expiration_date=row.ExpirationDate if pd.notna(row.ExpirationDate) else None,
                    ))
        return activities

    @property
    @lru_cache(maxsize=8)
    def market_trades(self):
        return self.non_derivative_table.market_trades

    @property
    def common_stock_purchases(self):
        """Get all common stock purchase transactions"""
        if self.market_trades is not None and not self.market_trades.empty:
            return self.market_trades[self.market_trades.AcquiredDisposed == 'A']
        return pd.DataFrame()

    @property
    def common_stock_sales(self):
        """Get all common stock sale transactions"""
        if self.market_trades is not None and not self.market_trades.empty:
            return self.market_trades[self.market_trades.AcquiredDisposed == 'D']
        return pd.DataFrame()

    @property
    def option_exercises(self):
        """Get option exercise transactions"""
        if not self.non_derivative_table.has_transactions:
            return pd.DataFrame()
        return self.non_derivative_table.exercised_trades

    def get_ownership_summary(self) -> Union[InitialOwnershipSummary, TransactionSummary]:
        """Get the appropriate summary based on form type"""
        if self.form == "3":
            # Form 3 - Initial ownership statement
            return InitialOwnershipSummary(
                reporting_date=self.reporting_period,
                issuer_name=self.issuer.name,
                issuer_ticker=self.issuer.ticker,
                insider_name=self._get_owner(),
                position=self.reporting_owners.owners[0].position,
                form_type=self.form,
                holdings=self.extract_form3_holdings(),
                no_securities=self.no_securities,
                remarks=self.remarks if self.remarks else ""
            )
        else:
            # Form 4/5 - Transaction report
            activities = self.get_transaction_activities()

            # Get remaining shares
            remaining = None
            if self.market_trades is not None and not self.market_trades.empty:
                if 'Remaining' in self.market_trades.columns and not self.market_trades.Remaining.isna().all():
                    remaining = self.market_trades.Remaining.iloc[-1]

            # Alternative sources for remaining shares
            if remaining is None and self.non_derivative_table.has_transactions:
                all_transactions = self.non_derivative_table.transactions.data
                if 'Remaining' in all_transactions.columns and not all_transactions.Remaining.isna().all():
                    remaining = all_transactions.Remaining.iloc[-1]

            # Detect derivative transactions
            has_derivative = self.derivative_table and self.derivative_table.has_transactions

            return TransactionSummary(
                reporting_date=self.reporting_period,
                issuer_name=self.issuer.name,
                issuer_ticker=self.issuer.ticker,
                insider_name=self._get_owner(),
                position=self.reporting_owners.owners[0].position,
                form_type=self.form,
                transactions=activities,
                remaining_shares=remaining,
                has_derivative_transactions=has_derivative,
                remarks=self.remarks if self.remarks else ""
            )

    def to_dataframe(self, detailed: bool = True, include_metadata: bool = True) -> pd.DataFrame:
        """
        Convert ownership data to DataFrame

        Args:
            detailed: Whether to show individual transactions/holdings (True) or summary (False)
            include_metadata: Whether to include filing metadata columns

        Returns:
            DataFrame with ownership data
        """
        summary = self.get_ownership_summary()
        if detailed:
            return summary.to_dataframe(include_metadata=include_metadata)
        else:
            return summary.to_summary_dataframe()

    def _get_owner(self):
        owners = [
            owner.name for owner in self.reporting_owners.owners
        ]
        return " / ".join(owners)

    @property
    @lru_cache(maxsize=8)
    def derivative_trades(self):
        # First get the derivative trades from the derivative table
        return self.derivative_table.derivative_trades

    @property
    @lru_cache(maxsize=8)
    def shares_traded(self):
        # Sum the Shares if Shares is all numeric
        if np.issubdtype(self.market_trades.Shares.dtype, np.number):
            return self.market_trades.Shares.sum()

    @classmethod
    def from_xml(cls,
                 content: str):
        return cls(**cls.parse_xml(content))

    @classmethod
    def parse_xml(cls,
                  content: str):
        soup = BeautifulSoup(content, "xml")

        root = soup.find("ownershipDocument")

        # Period of report
        report_period = child_text(root, "periodOfReport")

        remarks = child_text(root, "remarks")

        no_securities = child_text(root, "noSecuritiesOwned") == "1"

        # Footnotes
        footnotes = Footnotes.extract(root)

        # Issuer
        issuer_tag = root.find("issuer")
        issuer = Issuer(
            cik=child_text(issuer_tag, "issuerCik"),
            name=child_text(issuer_tag, "issuerName"),
            ticker=child_text(issuer_tag, "issuerTradingSymbol")
        )

        # Signature
        ownership_signatures = OwnerSignatures([OwnerSignature(
            signature=child_text(el, "signatureName").strip(),
            date=child_text(el, "signatureDate")
        ) for el in root.find_all("ownerSignature")]
        )

        # Reporting Owner
        reporting_owner = ReportingOwners.from_reporting_owner_tags(root.find_all("reportingOwner"), remarks=remarks)

        form = child_text(root, "documentType")
        # Non derivatives
        non_derivative_table_tag = root.find("nonDerivativeTable")
        non_derivative_table = NonDerivativeTable.extract(non_derivative_table_tag, form=form)

        # Derivatives
        derivative_table_tag = root.find("derivativeTable")
        derivative_table = DerivativeTable.extract(derivative_table_tag, form=form)

        ownership_document = {
            'form': form,
            'footnotes': footnotes,
            'issuer': issuer,
            'reporting_owners': reporting_owner,
            'signatures': ownership_signatures,
            'non_derivative_table': non_derivative_table,
            'derivative_table': derivative_table,
            'reporting_period': report_period,
            'remarks': remarks,
            'no_securities': no_securities
        }
        return ownership_document

    def to_html(self) -> str:
        """Return the HTML representation of this ownership form."""
        return ownership_to_html(self)

    def _repr_html_(self):
        """Return the HTML representation for display in Jupyter"""
        return self.to_html()

    def __rich__(self):
        ownership_summary = self.get_ownership_summary()
        return ownership_summary.__rich__()

    def __repr__(self):
        return repr_rich(self.__rich__())


class Form3(Ownership):

    def __init__(self, **fields):
        super().__init__(**fields)

    @classmethod
    def parse_xml(cls,
                  content: str):
        return cls(**Ownership.parse_xml(content))


class Form4(Ownership):

    def __init__(self, **fields):
        super().__init__(**fields)

    @classmethod
    def parse_xml(cls,
                  content: str):
        return cls(**Ownership.parse_xml(content))


class Form5(Ownership):

    def __init__(self, **fields):
        super().__init__(**fields)

    @classmethod
    def parse_xml(cls,
                  content: str):
        return cls(**Ownership.parse_xml(content))

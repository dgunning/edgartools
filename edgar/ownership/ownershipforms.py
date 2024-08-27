"""
Ownership contains the domain model for forms
- 3 initial ownership
- 4 changes in ownership and
- 5 annual ownership statement

The top level object is Ownership

"""
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Dict, Tuple, Optional, Union

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup, ResultSet
from bs4 import Tag
from pydantic import BaseModel
from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table, Column

from edgar._party import Address
from edgar.core import IntString, get_bool, reverse_name, yes_no
from edgar.datatools import convert_to_numeric
from edgar.entities import Entity
from edgar.ownership.form345 import compute_average_price, format_amount, format_currency
from edgar.richtools import repr_rich, df_to_rich_table
from edgar.xmltools import (child_text, child_value)

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
            return NonDerivativeTransactions()
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
                #print(f"Warning: Conversion failed for column {col}")

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
        table = Table(Column("Owner", style="bold deep_sky_blue1"), "Position", "Location", box=box.SIMPLE, row_styles=["", "bold"])
        for owner in self.owners:
            table.add_row(owner.name, owner.position, f"{owner.address.city}")

        title = "\U0001F468\u200D\U0001F4BC Reporting Owner"
        if len(self) > 1:
            title += "s"
        return Panel(table, title=title)

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
            entity = Entity(int(cik), include_old_filings=False)

            # Check if the entity is a company or an individual
            is_company = entity and entity.is_company
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


class InsiderMarketTradeSummary(BaseModel):
    """ A summary of the insider buy/sell transactions """
    period: str
    owner: str
    ownership_nature: str
    position: str
    buy_sell: str
    shares: Union[int, float]
    price: Union[int, float]
    remaining: Optional[Union[int, float]] = None

    def __rich__(self):
        table = Table("Period", Column("Owner", style="bold deep_sky_blue1"),
                      "Position", "Buy/Sell", "Shares", "Price", "Remaining", box=box.SIMPLE)
        table.add_row(self.period,
                      self.owner,
                      self.position,
                      self.buy_sell, format_amount(self.shares),
                      format_currency(self.price),
                      format_amount(self.remaining))
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


class NonMarketTradeSummary():

    def __init__(self, data: pd.DataFrame):
        self.data = data

    def empty(self):
        return self.data is None or len(self.data) == 0

    def __len__(self):
        return 0 if self.data is None else len(self.data)

    def __rich__(self):
        table = Table(Column("Date", style="bold"), "Action", "Shares", "Price", "Security", box=box.SIMPLE, row_styles=["", "dim"])
        for row in self.data.itertuples():
            table.add_row(row.Date, row.TransactionType, format_amount(row.Shares), format_currency(row.Price),
                          row.Security)
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


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

    @property
    @lru_cache(maxsize=8)
    def market_trades(self):
        return self.non_derivative_table.market_trades

    def _get_owner(self):
        owner = self.reporting_owners.owners[0].name
        num_owners = len(self.reporting_owners)
        if num_owners == 2:
            owner = owner + " and one other"
        elif num_owners > 2:
            owner = owner + f" and {num_owners - 1} others"
        return owner

    def get_insider_market_trade_summary(self) -> Optional[InsiderMarketTradeSummary]:
        """A summary of Buys and Sells"""
        if self.market_trades is None or self.market_trades.empty:
            return None
        trades = self.market_trades
        owner = self._get_owner()
        position = self.reporting_owners.owners[0].position
        return InsiderMarketTradeSummary(period=self.reporting_period,
                                         owner=owner,
                                         ownership_nature=describe_ownership(trades.DirectIndirect.iloc[-1],
                                                                             trades.NatureOfOwnership.iloc[-1]),
                                         position=position,
                                         buy_sell=translate_buy_sell(trades.AcquiredDisposed.iloc[-1]),
                                         shares=trades.Shares.sum(),
                                         price=compute_average_price(shares=trades.Shares, price=trades.Price),
                                         remaining=trades.Remaining.iloc[-1])

    def get_non_market_trade_summary(self) -> Optional[NonMarketTradeSummary]:
        non_market_trades = self.non_derivative_table.non_market_trades
        if non_market_trades is not None and not non_market_trades.empty:
            return NonMarketTradeSummary(non_market_trades)

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

    def summary(self):
        return pd.DataFrame(
            [{'Period': self.reporting_period,
              'Issuer': self.issuer.name,
              'Ticker': self.issuer.ticker}
             ]
        ).set_index('Period')

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

    def __rich__(self):
        renderables = [self.reporting_owners]

        # Common trades
        if self.form == "5":
            if self.non_derivative_table.has_transactions:
                renderables.append(self.non_derivative_table.transactions)
        else:
            insider_trade_summary = self.get_insider_market_trade_summary()
            if insider_trade_summary:
                action_color = "green" if insider_trade_summary.buy_sell == "Buy" else "red1"
                table = Table(Column("Date", style="bold"),
                              Column("Action",style=action_color),
                              Column("Shares", style=action_color),
                              "Price",
                              "Ownership",
                              "Remaining",
                              box=box.SIMPLE)
                table.add_row(insider_trade_summary.period,
                              insider_trade_summary.buy_sell,
                              format_amount(insider_trade_summary.shares),
                              format_currency(insider_trade_summary.price),
                              insider_trade_summary.ownership_nature,
                              format_amount(insider_trade_summary.remaining))
                panel = Panel(table, title="\U0001F4C8 Common Stock Trading Summary")
                renderables.append(panel)

        # Non market trade summary
        non_market_trade_summary = self.get_non_market_trade_summary()
        if non_market_trade_summary and not non_market_trade_summary.empty():
            panel = Panel(non_market_trade_summary, title="\U0001F4B8 Non Market Activity")
            renderables.append(panel)

        # Holdings
        # Non - Derivative Holdings
        if self.non_derivative_table.has_holdings:
            renderables.append(self.non_derivative_table.holdings)

        # Derivative Holdings
        if self.derivative_table.has_holdings:
            renderables.append(self.derivative_table.holdings)

        # Signature
        renderables.append(self.signatures)

        return Panel(Group(*renderables),
                     title=f"FORM {self.form} {self.issuer.name} ({self.issuer.ticker}) {self.reporting_period}")

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

    def __rich__(self):
        renderables = [self.reporting_owners]

        # Common trades
        if self.non_derivative_table.has_transactions:
            renderables.append(self.non_derivative_table.transactions)

        # Holdings
        # Non - Derivative Holdings
        if self.non_derivative_table.has_holdings:
            renderables.append(self.non_derivative_table.holdings)

        # Derivative Holdings
        if self.derivative_table.has_holdings:
            renderables.append(self.derivative_table.holdings)

        # Signature
        renderables.append(self.signatures)

        return Panel(Group(*renderables),
                     title=f"FORM {self.form} {self.issuer.name} ({self.issuer.ticker}) {self.reporting_period}")

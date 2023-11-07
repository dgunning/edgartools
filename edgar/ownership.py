"""
Ownership contains the domain model for forms
- 3 initial ownership
- 4 changes in ownership and
- 5 annual ownership statement

The top level object is Ownership

"""
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import List, Dict, Tuple, Optional

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup, ResultSet
from bs4 import Tag
from rich.columns import Columns
from rich.console import Group, Text
from rich.panel import Panel

from edgar._companies import Entity
from edgar._party import Address
from edgar._rich import repr_rich, df_to_rich_table
from edgar._xml import (child_text, child_value)
from edgar.core import IntString, get_bool, reverse_name, yes_no

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


def translate(value: str, translations: Dict[str, str]) -> str:
    return translations.get(value, value)


def is_numeric(series: pd.Series) -> bool:
    return np.issubdtype(series.dtype, np.number) or series.str.replace(".", "", regex=False).str.isnumeric().all()


def compute_average_price(shares: pd.Series, price: pd.Series) -> Decimal:
    """
    Compute the average price of the trades
    :param shares: The number of shares as a series
    :param price: The price per share as a series
    :return:
    """
    if is_numeric(shares) and is_numeric(price):
        shares = pd.to_numeric(shares)
        price = pd.to_numeric(price)
        value = (shares * price).sum() / shares.sum()
        return Decimal(str(value)).quantize(Decimal('0.01'))


def compute_total_value(shares: pd.Series, price: pd.Series) -> Decimal:
    """
    Compute the total value of the trades
    :param shares: The number of shares as a series
    :param price: The price per share as a series
    :return:
    """
    if is_numeric(shares) and is_numeric(price):
        shares = pd.to_numeric(shares)
        price = pd.to_numeric(price)
        value = (shares * price).sum()
        return Decimal(str(value)).quantize(Decimal('0.01'))


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

    def __repr__(self):
        return f"OwnerSignature(signature={self.signature}, date={self.date})"


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
        return Group(Text("Footnotes", style="bold"),
                     df_to_rich_table(self.summary(), index_name="id"),
                     )

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
        return (self
        .data
        .filter(cols)
        .rename(
            columns={'UnderlyingShares': 'Shares', 'ExercisePrice': 'Ex price', 'ExerciseDate': 'Ex date'})
        )

    def __rich__(self):
        return Group(Text("Holdings", style="bold"),
                     df_to_rich_table(self.summary().set_index('Security'), index_name='Security')
                     )

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
                nature_of_ownership=rec['Nature Of Ownership']
            )

    def summary(self):
        cols = ['Security', 'Shares', 'Direct', 'Nature Of Ownership']
        if self.empty:
            return pd.DataFrame(columns=cols)
        return self.data

    def __rich__(self):
        return Group(Text("Holdings", style="bold"),
                     df_to_rich_table(self.summary().set_index('Security'), index_name='Security')
                     )

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

    def __str__(self):
        return f"DerivativeTransaction - {len(self)} transactions"

    def summary(self):
        cols = ['Date', 'Security', 'Shares', 'Remaining', 'Price', 'Underlying', ]
        if self.empty:
            return pd.DataFrame(columns=cols[1:])
        return (self.data
                .assign(BuySell=lambda df: df.AcquiredDisposed.replace({'A': '+', 'D': '-'}))
                .assign(Shares=lambda df: df.BuySell + df.Shares)
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
                equity_swap=rec.EquitySwap,
                footnotes=rec.footnotes
            )

    def summary(self) -> pd.DataFrame:
        cols = ['Date', 'Security', 'Shares', 'Remaining', 'Price']
        if self.empty:
            return pd.DataFrame(columns=cols)
        return (self
                .data
                .assign(BuySell=lambda df: df.AcquiredDisposed.replace({'A': '+', 'D': '-'}))
                .assign(Shares=lambda df: df.BuySell + df.Shares.astype(str))
                .filter(cols)
                )

    def __rich__(self):
        return Group(
            df_to_rich_table(self.summary().set_index('Date'), index_name='Date')
        )

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
    def common_trades(self):
        if self.has_transactions:
            return DataHolder(self.transactions.data[self.transactions.data.Code.isin(TransactionCode.TRADES)])

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
                    ('Nature Of Ownership', child_value(ownership_nature_tag, 'natureOfOwnership') or ""),
                ]
            )

            holdings.append(holding)
        # Create the holdings dataframe
        holdings_df = pd.DataFrame(holdings)

        # Convert to numeric if we can.
        if holdings_df['Shares'].str.isnumeric().all():
            holdings_df['Shares'] = pd.to_numeric(holdings_df['Shares'], errors="ignore")

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
            if transaction_df[column].str.isnumeric().all():
                transaction_df[column] = pd.to_numeric(transaction_df[column], errors="ignore")
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
        return DerivativeHoldings(pd.DataFrame(holdings))

    def __rich__(self):
        if self.form == "3":
            holding_or_transaction = self.holdings.__rich__()
        else:
            holding_or_transaction = self.transactions.__rich__()
        if not holding_or_transaction:
            holding_or_transaction = Text("")
        return Panel(holding_or_transaction, title="Options acquired, displosed or benefially owned")

    def __repr__(self):
        return repr_rich(self.__rich__())


@dataclass(frozen=True)
class Owner:
    cik: str
    name: str
    address: Address
    is_director: bool
    is_officer: bool
    is_other: bool
    is_ten_pct_owner: bool
    officer_title: str = None

    def __repr__(self):
        return f"Owner(cik='{self.cik or ''}', name={self.name or ''})"


class ReportingOwners(DataHolder):

    def __init__(self, data):
        super().__init__(data, "ReportingOwners")

    def __getitem__(self, item):
        rec = self.data.iloc[item]
        return Owner(
            cik=rec.Cik,
            name=rec.Owner,
            address=Address(
                street1=rec.Street1,
                street2=rec.Street2,
                city=rec.City,
                state_or_country=rec.StateCountry,
                state_or_country_description=rec.StateCountryDesc,
                zipcode=rec.ZipCode
            ),
            is_director=rec.IsDirector,
            is_officer=rec.IsOfficer,
            is_other=rec.IsOther,
            is_ten_pct_owner=rec.IsTenPctOwner,
            officer_title=rec.OfficerTitle
        )

    def __rich__(self):
        return Group(
            df_to_rich_table(self.data
                             .assign(Director=lambda df: df.IsDirector.apply(yes_no),
                                     Officer=lambda df: df.IsOfficer.apply(yes_no),
                                     TenPctOwner=lambda df: df.IsTenPctOwner.apply(yes_no),
                                     )
                             .filter(['Owner', 'Director', 'Officer', 'TenPctOwner'])
                             .rename(columns={'Owner': 'Reporting Owner', 'TenPctOwner': '10% Owner'})
                             .set_index(['Reporting Owner']),
                             index_name='Reporting Owner')
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    @classmethod
    def from_reporting_owner_tags(cls, reporting_owners: ResultSet):
        # Reporting Owner
        records = []

        for reporting_owner_tag in reporting_owners:
            record = {}
            reporting_owner_id_tag = reporting_owner_tag.find("reportingOwnerId")

            record["Cik"] = child_text(reporting_owner_id_tag, "rptOwnerCik")
            record["Owner"] = child_text(reporting_owner_id_tag, "rptOwnerName")

            # Check if it is a company. If not, reverse the name
            entity = Entity(record["Cik"])

            if not entity.is_company:
                record["Owner"] = reverse_name(record["Owner"])

            reporting_owner_address_tag = reporting_owner_tag.find("reportingOwnerAddress")

            record['Street1'] = child_text(reporting_owner_address_tag, "rptOwnerStreet1")
            record['Street2'] = child_text(reporting_owner_address_tag, "rptOwnerStreet2")
            record['City'] = child_text(reporting_owner_address_tag, "rptOwnerCity")
            record['StateCountry'] = child_text(reporting_owner_address_tag, "rptOwnerState")
            record['StateCountryDesc'] = child_text(reporting_owner_address_tag, "rptOwnerStateDescription")
            record['ZipCode'] = child_text(reporting_owner_address_tag, "rptOwnerZipCode")

            reporting_owner_rel_tag = reporting_owner_tag.find("reportingOwnerRelationship")

            record['IsDirector'] = get_bool(child_text(reporting_owner_rel_tag, "isDirector"))
            record['IsOfficer'] = get_bool(child_text(reporting_owner_rel_tag, "isOfficer"))
            record['IsTenPctOwner'] = get_bool(child_text(reporting_owner_rel_tag, "isTenPercentOwner"))
            record['IsOther'] = get_bool(child_text(reporting_owner_rel_tag, "isOther"))
            record['OfficerTitle'] = child_text(reporting_owner_rel_tag, "officerTitle")
            records.append(record)

        data = pd.DataFrame(records)
        return cls(data)


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
                 signatures: List[OwnerSignature],
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
        self.signatures: List[OwnerSignature] = signatures
        self.reporting_period: str = reporting_period
        self.remarks: str = remarks
        self.no_securities = no_securities

    @property
    @lru_cache(maxsize=8)
    def common_trades(self):
        return self.non_derivative_table.common_trades

    @property
    @lru_cache(maxsize=8)
    def derivative_trades(self):
        # First get the derivative trades from the derivative table
        return self.derivative_table.derivative_trades

    @property
    @lru_cache(maxsize=8)
    def shares_owned(self):
        shares_owned_value = Decimal(0.0).quantize(Decimal('0.01'))
        trades = self.common_trades.data

        if trades is not None and not trades.empty:
            # Get the last trade
            last_trade = trades.iloc[-1]
            shares_owned_value += int(last_trade.Remaining)

        derivatives = self.derivative_trades
        if derivatives is not None and not derivatives.empty:
            # Get the last trade
            last_trade = derivatives.data.iloc[-1]
            shares_owned_value += Decimal(last_trade.Remaining).quantize(Decimal('0.01'))

        return shares_owned_value

    @property
    @lru_cache(maxsize=8)
    def insider_stock_summary(self):
        if self.common_trades.empty:
            return None
        return StockSummary(
            insider=self.reporting_owners[0].name,  # Change to get a summary of the owners
            shares_traded=self.common_trades.data.Shares.sum() if is_numeric(
                self.common_trades.data.Shares) else None,
            average_price=compute_average_price(shares=self.common_trades.data.Shares,
                                                price=self.common_trades.data.Price),
            total_value=compute_total_value(shares=self.common_trades.data.Shares,
                                            price=self.common_trades.data.Price),
            shares_owned=self.shares_owned,
            reporting_period=self.reporting_period
        )

    @property
    @lru_cache(maxsize=8)
    def shares_traded(self):
        # Sum the Shares if Shares is all numeric
        if np.issubdtype(self.common_trades.data.Shares.dtype, np.number):
            return self.common_trades.data.Shares.sum()

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
        ownership_signatures = [OwnerSignature(
            signature=child_text(el, "signatureName"),
            date=child_text(el, "signatureDate")
        ) for el in root.find_all("ownerSignature")]

        # Reporting Owner
        reporting_owner = ReportingOwners.from_reporting_owner_tags(root.find_all("reportingOwner"))

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
        header_panel = Panel(
            Group(
                Text(f"Form {self.form} {FORM_DESCRIPTIONS.get(self.form, '')}", style="bold dark_sea_green4"),
                Columns([df_to_rich_table(self.summary(), index_name='Period'),
                self.reporting_owners.__rich__()])
            )
        )
        renderables = [header_panel, self.non_derivative_table.__rich__()]
        # Add derivatives if they exist
        if not self.derivative_table.empty:
            renderables.append(self.derivative_table.__rich__())

        return Group(*renderables)

    def __repr__(self):
        return repr_rich(self.__rich__())


@dataclass
class StockSummary:
    """
    Used to summarize the stock transactions of the insider
    """
    insider: str
    reporting_period: str
    shares_traded: Optional[Decimal] = None
    average_price: Optional[Decimal] = None
    total_value: Optional[Decimal] = None
    shares_owned: Optional[Decimal] = None

    def to_dict(self):
        return {
            'Reporting Owner': self.insider,
            'Shares Traded': self.shares_traded,
            'Average Price': self.average_price,
            'Total Value': self.total_value,
            'Shares Owned': self.shares_owned,
            'Reporting Period': self.reporting_period
        }


class Form3(Ownership):

    def __init__(self, **fields):
        super().__init__(**fields)


class Form4(Ownership):

    def __init__(self, **fields):
        super().__init__(**fields)


class Form5(Ownership):

    def __init__(self, **fields):
        super().__init__(**fields)

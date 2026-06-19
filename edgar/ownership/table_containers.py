"""
Holdings/transactions table containers for SEC ownership forms (3, 4, 5).

``NonDerivativeTable`` and ``DerivativeTable`` wrap the holdings and transactions
for the ``<nonDerivativeTable>`` / ``<derivativeTable>`` sections of a Form 3/4/5
filing, including the ``extract*`` classmethods that parse them out of the XML.
The row records and their ``DataHolder`` collection wrappers live in ``tables``.
"""
import numpy as np
import pandas as pd
from bs4 import Tag
from rich.console import Group, Text
from rich.panel import Panel

from edgar.core import get_bool
from edgar.datatools import convert_to_numeric
from edgar.display.formatting import yes_no
from edgar.ownership.core import get_footnotes
from edgar.ownership.models import TransactionCode
from edgar.ownership.tables import (
    DataHolder,
    DerivativeHoldings,
    DerivativeTransactions,
    NonDerivativeHoldings,
    NonDerivativeTransactions,
)
from edgar.richtools import repr_rich
from edgar.xmltools import child_text, child_value

__all__ = [
    'NonDerivativeTable',
    'DerivativeTable',
]


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
                    # Collect footnoteId references from the whole transaction, not just
                    # <transactionCoding>: footnotes attach to securityTitle, transaction
                    # date, shares, price, etc. (edgartools-t043).
                    ('footnotes', get_footnotes(transaction_tag)),
                ]
            )
            transaction_coding_tag = transaction_tag.find("transactionCoding")
            if transaction_coding_tag and isinstance(transaction_coding_tag, Tag):
                transaction_coding = dict(
                    [
                        ('form', child_text(transaction_coding_tag, 'transactionFormType')),
                        ('Code', child_text(transaction_coding_tag, 'transactionCode')),
                        ('EquitySwap', get_bool(child_text(transaction_coding_tag, 'equitySwapInvolved'))),
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
                    # Collect footnoteId references from the whole transaction, not just
                    # <transactionCoding> (edgartools-t043).
                    ('footnotes', get_footnotes(transaction_tag)),
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

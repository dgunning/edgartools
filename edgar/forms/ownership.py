"""
Ownership contains the domain model for forms
- 3 initial ownership
- 4 changes in ownership and
- 5 annual ownership statement

The top level object is Ownership

"""
from dataclasses import dataclass
from typing import List, Dict, Tuple

import pandas as pd
from bs4 import BeautifulSoup
from bs4 import Tag
from rich.console import Group, Text
from rich.panel import Panel

from edgar._party import Address
from edgar._rich import repr_rich, df_to_rich_table
from edgar._xml import (child_text, child_value)
from edgar.core import IntString
from edgar.core import get_bool

__all__ = [
    'Owner',
    'Issuer',
    'Address',
    'Footnotes',
    'OwnerSignature',
    'TransactionCode',
    'Ownership',
    'DerivativeHolding',
    'DerivativeHoldings',
    'translate_ownership',
    'NonDerivativeHolding',
    'NonDerivativeHoldings',
    'DerivativeTransaction',
    'DerivativeTransactions',
    'ReportingRelationship',
    'PostTransactionAmounts',
    'NonDerivativeTransaction',
    'NonDerivativeTransactions',
]


def translate(value: str, translations: Dict[str, str]) -> str:
    return translations.get(value, value)


DIRECT_OR_INDIRECT_OWNERSHIP = {'D': 'Direct', 'I': 'Indirect'}

FORM_DESCRIPTIONS = {'3': 'Initial beneficial ownership',
                     '4': 'Changes in beneficial ownership',
                     '5': 'Annual statement of beneficial ownership',
                     }


def translate_ownership(value: str) -> str:
    return translate(value, DIRECT_OR_INDIRECT_OWNERSHIP)


class Owner:

    def __init__(self,
                 cik: IntString,
                 name: str):
        self.cik: IntString = cik
        self.name: str = name

    def __repr__(self):
        return f"Owner(cik='{self.cik or ''}', name={self.name or ''})"


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

    @property
    def empty(self):
        return self.data is None or len(self.data) == 0

    def __rich__(self) -> str:
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

    def __rich__(self) -> str:
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
    direct: bool
    ownership_nature: str


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
            return DerivativeHolding(**rec)

    def summary(self) -> pd.DataFrame:
        cols = ['security', 'underlying', 'underlying_shares', 'exercise_price', 'exercise_date']
        if self.empty:
            return pd.DataFrame(columns=cols)
        return (self
        .data
        .filter(cols)
        .rename(
            columns={'underlying_shares': 'shares', 'exercise_price': 'ex price', 'exercise_date': 'ex date'})
        )

    def __rich__(self) -> str:
        return Group(Text("Holdings", style="bold"),
                     df_to_rich_table(self.summary().set_index('security'), index_name='security')
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
            return NonDerivativeHolding(**rec)

    def summary(self):
        cols = ['security', 'direct', 'ownership_nature']
        if self.empty:
            return pd.DataFrame(columns=cols)
        return self.data

    def __rich__(self) -> str:
        return Group(Text("Holdings", style="bold"),
                     df_to_rich_table(self.summary().set_index('security'), index_name='security')
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
            return DerivativeTransaction(**rec)

    def __str__(self):
        return f"DerivativeTransaction - {len(self)} transactions"

    def summary(self):
        cols = ['date', 'security', 'underlying', 'shares', 'remaining', 'price']
        if self.empty:
            return pd.DataFrame(columns=cols[1:])
        return (self.data
                .assign(buy_sell=lambda df: df.acquired_disposed.replace({'A': '+', 'D': '-'}))
                .assign(shares=lambda df: df.buy_sell + df.shares)
                .filter(['date', 'security', 'underlying', 'shares', 'remaining', 'price'])
                .set_index('date')
                )

    def __rich__(self) -> str:
        return Group(Text("Transactions", style="bold"),
                     df_to_rich_table(self.summary(), index_name='date')
                     )

    def __repr__(self):
        return repr_rich(self.__rich__())


class NonDerivativeTransactions(DataHolder):

    def __init__(self,
                 data: pd.DataFrame = None):
        super().__init__(data, "NonDerivativeTransactions")

    def __getitem__(self, item):
        if not self.empty:
            rec = self.data.iloc[item]
            return NonDerivativeTransaction(**rec)

    def summary(self) -> pd.DataFrame:
        cols = ['date', 'security', 'shares', 'remaining', 'price']
        if self.empty:
            return pd.DataFrame(columns=cols)
        return (self
                .data
                .assign(buy_sell=lambda df: df.acquired_disposed.replace({'A': '+', 'D': '-'}))
                .assign(shares=lambda df: df.buy_sell + df.shares)
                .filter(cols)
                )

    def __rich__(self) -> str:
        return Group(Text("Transactions", style="bold"),
                     df_to_rich_table(self.summary().set_index('date'), index_name='date')
                     )

    def __repr__(self):
        return repr_rich(self.__rich__())


class NonDerivativeTable:
    """
    Contains non-derivative holdings and transactions
    """

    def __init__(self,
                 holdings: NonDerivativeHoldings,
                 transactions: NonDerivativeTransactions):
        self.holdings: NonDerivativeHoldings = holdings
        self.transactions: NonDerivativeTransactions = transactions

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
                table: Tag = None):
        if not table:
            return cls(holdings=NonDerivativeHoldings(), transactions=NonDerivativeTransactions())
        transactions = NonDerivativeTable.extract_transactions(table)
        holdings = NonDerivativeTable.extract_holdings(table)
        return cls(transactions=transactions, holdings=holdings)

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
                    ('security', child_value(holding_tag, 'securityTitle')),
                    ('direct', child_value(ownership_nature_tag, 'directOrIndirectOwnership') == "D"),
                    ('ownership_nature', child_value(ownership_nature_tag, 'natureOfOwnership')),
                ]
            )

            holdings.append(holding)
        # Create the holdings dataframe
        holdings_df = pd.DataFrame(holdings)

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
                    ('security', child_value(transaction_tag, 'securityTitle')),
                    ('date', child_value(transaction_tag, 'transactionDate')),
                    ('shares', child_text(transaction_amt_tag, 'transactionShares')),
                    ('remaining', child_text(post_transaction_tag, 'sharesOwnedFollowingTransaction')),
                    ('price', child_text(transaction_amt_tag, 'transactionPricePerShare')),
                    ('acquired_disposed', child_text(transaction_amt_tag, 'transactionAcquiredDisposedCode')),
                    ('direct_indirect', child_text(ownership_nature_tag, 'directOrIndirectOwnership')),
                ]
            )
            transaction_coding_tag = transaction_tag.find("transactionCoding")
            if transaction_coding_tag:
                transaction_coding = dict(
                    [
                        ('form', child_text(transaction_coding_tag, 'transactionFormType')),
                        ('transaction_code', child_text(transaction_coding_tag, 'transactionCode')),
                        ('equity_swap', get_bool(child_text(transaction_coding_tag, 'equitySwapInvolved'))),
                        ('footnotes', get_footnotes(transaction_coding_tag))
                    ]
                )
                transaction.update(transaction_coding)

            transactions.append(transaction)
        return NonDerivativeTransactions(pd.DataFrame(transactions))

    def __rich__(self) -> str:
        return Panel(Group(
            Text("0 non derivative holdings") if self.holdings.empty else self.holdings.__rich__(),
            Text("0 non derivative transactions") if self.transactions.empty else self.transactions.__rich__()
        ), title="Non Derivatives"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class DerivativeTable:
    """
    A container for the holdings and transactions in the <derivativeTable></derivativeTable>
    """

    def __init__(self,
                 holdings: DerivativeHoldings,
                 transactions: DerivativeTransactions):
        self.holdings: DerivativeHoldings = holdings
        self.transactions: DerivativeTransactions = transactions

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
                table: Tag = None):
        if not table:
            return cls(holdings=DerivativeHoldings(), transactions=DerivativeTransactions())
        transactions = cls.extract_transactions(table)
        holdings = cls.extract_holdings(table)
        return cls(transactions=transactions, holdings=holdings)

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
                    ('security', child_value(transaction_tag, 'securityTitle')),
                    ('underlying', child_value(underlying_tag, 'underlyingSecurityTitle')),
                    ('underlying_shares', child_value(underlying_tag, 'underlyingSecurityShares')),
                    ('exercise_price', child_value(transaction_tag, 'conversionOrExercisePrice')),
                    ('exercise_date', child_value(transaction_tag, 'exerciseDate')),
                    ('expiration_date', child_value(transaction_tag, 'expirationDate')),
                    ('shares', child_text(transaction_tag, 'transactionShares')),
                    ('direct_indirect', child_text(ownership_nature_tag, 'directOrIndirectOwnership')),
                    ('price', child_text(transaction_amt_tag, 'transactionPricePerShare')),
                    ('acquired_disposed', child_text(transaction_amt_tag, 'transactionAcquiredDisposedCode')),
                    ('date', child_value(transaction_tag, 'transactionDate')),
                    ('remaining', child_text(post_transaction_tag, 'sharesOwnedFollowingTransaction')),
                ]
            )

            # Add transaction coding
            transaction_coding_tag = transaction_tag.find("transactionCoding")
            if transaction_coding_tag:
                transaction_coding = dict(
                    [
                        ('form', child_text(transaction_coding_tag, 'transactionFormType')),
                        ('transaction_code', child_text(transaction_coding_tag, 'transactionCode')),
                        ('equity_swap', get_bool(child_text(transaction_coding_tag, 'equitySwapInvolved'))),
                        ('footnotes', get_footnotes(transaction_coding_tag))
                    ]
                )
                transaction.update(transaction_coding)
            transactions.append(transaction)
        return DerivativeTransactions(pd.DataFrame(transactions))

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
                    ('security', child_value(holding_tag, 'securityTitle')),
                    ('underlying', child_value(underlying_security_tag, 'underlyingSecurityTitle')),
                    ('underlying_shares', child_value(underlying_security_tag, 'underlyingSecurityShares')),
                    ('exercise_price', child_value(holding_tag, 'conversionOrExercisePrice')),
                    ('exercise_date', child_value(holding_tag, 'exerciseDate')),
                    ('expiration_date', child_value(holding_tag, 'expirationDate')),
                    ('direct_indirect', child_text(ownership_nature, 'directOrIndirectOwnership')),
                    ('nature_of_ownership', child_value(ownership_nature, 'natureOfOwnership')),
                ]
            )
            holdings.append(holding)
        return DerivativeHoldings(pd.DataFrame(holdings))

    def __rich__(self) -> str:
        return Panel(Group(
            Text("0 derivative holdings") if self.holdings.empty else self.holdings.__rich__(),
            Text("0 derivative transactions") if self.transactions.empty else self.transactions.__rich__()
        ), title="Derivatives"
        )

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
                 reporting_owner: Owner,
                 reporting_owner_address: Address,
                 reporting_relationship: ReportingRelationship,
                 non_derivatives: NonDerivativeTable,
                 derivatives: DerivativeTable,
                 signatures: List[OwnerSignature],
                 reporting_period: str,
                 remarks: str,
                 no_securities: bool = False
                 ):
        self.form: str = form
        self.footnotes: Footnotes = footnotes
        self.issuer: Issuer = issuer
        self.reporting_owner: Owner = reporting_owner
        self.reporting_owner_address: Address = reporting_owner_address
        self.reporting_relationship: ReportingRelationship = reporting_relationship
        self.non_derivatives: NonDerivativeTable = non_derivatives
        self.derivatives: DerivativeTable = derivatives
        self.signatures: List[OwnerSignature] = signatures
        self.reporting_period: str = reporting_period
        self.remarks: str = remarks
        self.no_securities = no_securities

    def summary(self):
        return pd.DataFrame(
            [{'issuer': self.issuer.name,
              'ticker': self.issuer.ticker,
              'reporting owner': self.reporting_owner.name,
              'period': self.reporting_period}]
        ).set_index('ticker')

    @classmethod
    def from_xml(cls,
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

        # Reporting Owner
        reporting_owner_tag = root.find("reportingOwner")
        reporting_owner_id_tag = reporting_owner_tag.find("reportingOwnerId")
        reporting_owner = Owner(
            cik=child_text(reporting_owner_id_tag, "rptOwnerCik"),
            name=child_text(reporting_owner_id_tag, "rptOwnerName")
        )

        # Signature
        ownership_signatures = [OwnerSignature(
            signature=child_text(el, "signatureName"),
            date=child_text(el, "signatureDate")
        ) for el in root.find_all("ownerSignature")]

        reporting_owner_address_tag = reporting_owner_tag.find("reportingOwnerAddress")
        reporting_owner_address = Address(
            street1=child_text(reporting_owner_address_tag, "rptOwnerStreet1"),
            street2=child_text(reporting_owner_address_tag, "rptOwnerStreet2"),
            city=child_text(reporting_owner_address_tag, "rptOwnerCity"),
            state_or_country=child_text(reporting_owner_address_tag, "rptOwnerState"),
            zipcode=child_text(reporting_owner_address_tag, "rptOwnerZipCode"),
            state_or_country_description=child_text(reporting_owner_address_tag, "rptOwnerStateDescription")
        )

        reporting_owner_rel_tag = reporting_owner_tag.find("reportingOwnerRelationship")
        reporting_relationship = ReportingRelationship(
            is_director=get_bool(child_text(reporting_owner_rel_tag, "isDirector")),
            is_officer=get_bool(child_text(reporting_owner_rel_tag, "isOfficer")),
            is_ten_pct_owner=get_bool(child_text(reporting_owner_rel_tag, "isTenPercentOwner")),
            is_other=get_bool(child_text(reporting_owner_rel_tag, "isOther")),
            officer_title=child_text(reporting_owner_rel_tag, "officerTitle")
        )

        # Non derivatives
        non_derivative_table_tag = root.find("nonDerivativeTable")
        non_derivative_table = NonDerivativeTable.extract(non_derivative_table_tag)

        # Derivatives
        derivative_table_tag = root.find("derivativeTable")
        derivative_table = DerivativeTable.extract(derivative_table_tag)

        ownership_document = Ownership(
            form=child_text(root, "documentType"),
            footnotes=footnotes,
            issuer=issuer,
            reporting_owner=reporting_owner,
            reporting_owner_address=reporting_owner_address,
            reporting_relationship=reporting_relationship,
            signatures=ownership_signatures,
            non_derivatives=non_derivative_table,
            derivatives=derivative_table,
            reporting_period=report_period,
            remarks=remarks,
            no_securities=no_securities
        )
        return ownership_document

    def __rich__(self) -> str:
        return Group(Panel(
            Group(
                Text(f"Form {self.form} {FORM_DESCRIPTIONS.get(self.form, '')}", style="bold dark_sea_green4"),
                df_to_rich_table(self.summary(), index_name='ticker'))),
            self.non_derivatives.__rich__(),
            self.derivatives.__rich__(),
            self.footnotes.__rich__()
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

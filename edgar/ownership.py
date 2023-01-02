from typing import List, Dict, Union, Optional, Tuple

import pandas as pd
from bs4 import BeautifulSoup
from bs4 import Tag


from edgar.xml import (child_text, child_value, child_value_or_footnote, value_or_footnote)
from edgar.core import get_bool


__all__ = [
    'translate_ownership',
    'Issuer',
    'Owner',
    'Address',
    'Footnotes',
    'HoldingsHolder',
    'OwnerSignature',
    'TransactionCode',
    'TransactionsHolder',
    'OwnershipDocument',
    'ReportingRelationship',
    'PostTransactionAmounts',

]

IntString = Union[str, int]


def translate(value: str, translations: Dict[str, str]) -> str:
    return translations.get(value, value)


DIRECT_OR_INDIRECT_OWNERSHIP = {'D': 'Direct', 'I': 'Indirect'}


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


class Address:

    def __init__(self,
                 street1: str,
                 street2: Optional[str] = None,
                 city: Optional[str] = None,
                 state: Optional[str] = None,
                 zipcode: Optional[str] = None,
                 state_description: Optional[str] = None
                 ):
        self.street1: str = street1
        self.street2: Optional[str] = street2
        self.city: Optional[str] = city
        self.state: Optional[str] = state
        self.zipcode: Optional[str] = zipcode
        self.state_description: Optional[str] = state_description

    def __repr__(self):
        return (f"Address(street1='{self.street1}', street2={self.street2}, city={self.city}, "
                f"zipcode={self.zipcode}, state={self.state})")


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

    def __repr__(self):
        if self.empty:
            return f"{self.name} (no data)"
        else:
            return f"{self.name} - {len(self)} items"


class TransactionsHolder(DataHolder):

    def __init__(self,
                 data: pd.DataFrame = None):
        super().__init__(data, "Transactions")


class HoldingsHolder(DataHolder):

    def __init__(self,
                 data: pd.DataFrame = None):
        super().__init__(data, "Holdings")


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

    def __len__(self):
        return len(self._footnotes)

    def __repr__(self):
        return str(self._footnotes)

    @classmethod
    def extract(cls,
                tag: Tag):
        footnotes_el = tag.find("footnotes")
        return cls(
            {el.attrs['id']: el.text
             for el in footnotes_el.find_all("footnote")
             } if footnotes_el else {}
        )


def security(tag: Tag) -> Tuple[str, str]:
    return 'security', child_value(tag, 'securityTitle')


def underlying_security(tag: Tag) -> Tuple[str, str]:
    return 'underlying_security', child_value(tag, 'underlyingSecurityTitle')


def underlying_shares(tag: Tag) -> Tuple[str, str]:
    return 'underlying_shares', child_value(tag, 'underlyingSecurityShares')


def transaction_date(tag: Tag) -> Tuple[str, str]:
    return 'transaction_date', child_value(tag, 'transactionDate')


def num_shares(tag: Tag) -> Tuple[str, str]:
    return 'num_shares', child_text(tag, 'transactionShares')


def remaining_shares(tag: Tag) -> Tuple[str, str]:
    return 'remaining_shares', child_value(tag, 'sharesOwnedFollowingTransaction')


def share_price(tag: Tag) -> Tuple[str, str]:
    return 'share_price', child_text(tag, 'transactionPricePerShare')


def acquired_displosed(tag: Tag) -> Tuple[str, str]:
    return 'acquired_displosed', child_text(tag, 'transactionAcquiredDisplodedCode')


def ownership(tag: Tag) -> Tuple[str, str]:
    return 'ownership', child_text(tag, 'directOrIndirectOwnership')


def form_type(tag: Tag) -> Tuple[str, str]:
    return 'form', child_text(tag, 'transactionFormType')


def transaction_code(tag: Tag) -> Tuple[str, str]:
    return 'transaction_code', child_text(tag, 'transactionCode')


def equity_swap(tag: Tag) -> Tuple[str, str]:
    return 'equity_swap', child_text(tag, 'equitySwapInvolved')


def transaction_footnote_id(tag: Tag) -> Tuple[str, str]:
    return 'footnote', tag.attrs.get("id") if tag else None


def exercise_price(tag: Tag) -> Tuple[str, str]:
    return 'exercise_price', child_value_or_footnote(tag, 'conversionOrExercisePrice')


def exercise_date(tag: Tag) -> Tuple[str, str]:
    return 'exercise_date', child_value_or_footnote(tag, 'exerciseDate')


def expiration_date(tag: Tag) -> Tuple[str, str]:
    return 'expiration_date', child_value_or_footnote(tag, 'expirationDate')


def get_footnotes(tag: Tag) -> str:
    return '\n'.join([
        el.attrs.get('id') for el in tag.find_all("footnoteId")
    ])


class NonDerivativeTable:

    def __init__(self,
                 holdings: HoldingsHolder,
                 transactions: TransactionsHolder):
        self.holdings: HoldingsHolder = holdings
        self.transactions: TransactionsHolder = transactions

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
            return cls(holdings=HoldingsHolder(), transactions=TransactionsHolder())
        transactions = NonDerivativeTable.extract_transactions(table)
        holdings = NonDerivativeTable.extract_holdings(table)
        return cls(transactions=transactions, holdings=holdings)

    @staticmethod
    def extract_holdings(table: Tag) -> HoldingsHolder:
        holding_tags = table.find_all("nonDerivativeHolding")
        if len(holding_tags) == 0:
            return HoldingsHolder()

        holdings = []
        for holding_tag in holding_tags:
            ownership_nature = holding_tag.find("ownershipNature")
            holding = dict(
                [
                    security(holding_tag),
                    ownership(ownership_nature)
                ]
            )

            nature_of_ownership = ownership_nature.find("natureOfOwnership")
            if nature_of_ownership:
                holding['nature_of_onership'] = value_or_footnote(nature_of_ownership)

            # Post transaction amounts
            post_trans_tag = holding_tag.find("postTransactionAmounts")
            if post_trans_tag:
                holding.update(
                    dict([
                        remaining_shares(post_trans_tag)
                    ])
                )
                shares_remaining = post_trans_tag.find("sharesPwnedFollowingTransaction")
                if shares_remaining:
                    shares_remaining_footnotes = get_footnotes(shares_remaining)
                    if shares_remaining_footnotes:
                        holding['footnote'] = shares_remaining_footnotes

            holdings.append(holding)

        return HoldingsHolder(pd.DataFrame(holdings))

    @staticmethod
    def extract_transactions(table: Tag) -> TransactionsHolder:
        """
        Extract transactions from the table tag
        :param table:
        :return:
        """
        transaction_tags = table.find_all("nonDerivativeTransaction")
        if len(transaction_tags) == 0:
            return TransactionsHolder()
        transactions = []
        for trans_tag in transaction_tags:
            trans_amt_tag = trans_tag.find("transactionAmounts")
            ownership_nature = trans_tag.find("ownershipNature")
            post_trans_tag = trans_tag.find("postTransactionAmounts")
            transaction = dict(
                [
                    security(trans_tag),
                    transaction_date(trans_tag),
                    num_shares(trans_amt_tag),
                    remaining_shares(post_trans_tag),
                    share_price(trans_amt_tag),
                    acquired_displosed(trans_amt_tag),
                    ownership(ownership_nature)
                ]
            )
            trans_coding_tag = trans_tag.find("transactionCoding")
            if trans_coding_tag:
                footnote_tag = trans_coding_tag.find("footnoteId")
                transaction_coding = dict(
                    [
                        form_type(trans_coding_tag),
                        transaction_code(trans_coding_tag),
                        equity_swap(trans_coding_tag),
                        transaction_footnote_id(footnote_tag)
                    ]
                )
                transaction.update(transaction_coding)

            transactions.append(transaction)
        return TransactionsHolder(pd.DataFrame(transactions))


class DerivativeTable:
    """
    A container for the holdings and transactions in the <derivativeTable></derivativeTable>
    """

    def __init__(self,
                 holdings: HoldingsHolder,
                 transactions:TransactionsHolder):
        self.holdings: HoldingsHolder = holdings
        self.transactions: TransactionsHolder = transactions

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
            return cls(holdings=HoldingsHolder(), transactions=TransactionsHolder())
        transactions = cls.extract_transactions(table)
        holdings = cls.extract_holdings(table)
        return cls(transactions=transactions, holdings=holdings)

    @staticmethod
    def extract_transactions(table: Tag) -> TransactionsHolder:
        trans_tags = table.find_all("derivativeTransaction")
        if len(trans_tags) == 0:
            return TransactionsHolder()

        transactions = []
        for trans_tag in trans_tags:
            trans_amt_el = trans_tag.find("transactionAmounts")
            underlying_tag = trans_tag.find("underlyingSecurity")
            ownership_nature_tag = trans_tag.find("ownershipNature")
            post_trans_tag = trans_tag.find("postTransactionAmounts")

            transaction = dict(
                [
                    security(trans_tag),
                    underlying_security(underlying_tag),
                    exercise_price(trans_tag),
                    exercise_date(trans_tag),
                    expiration_date(trans_tag),
                    num_shares(trans_amt_el),
                    underlying_shares(underlying_tag),
                    ownership(ownership_nature_tag),
                    share_price(trans_amt_el),
                    acquired_displosed(trans_amt_el),
                    transaction_date(trans_tag),
                    remaining_shares(post_trans_tag)
                ]
            )

            # Add transaction coding
            trans_coding_tag = trans_tag.find("transactionCoding")
            if trans_coding_tag:
                footnote_tag = trans_coding_tag.find("footnoteId")
                transaction_coding = dict(
                    [
                        form_type(trans_coding_tag),
                        transaction_code(trans_coding_tag),
                        equity_swap(trans_coding_tag),
                        transaction_footnote_id(footnote_tag)
                    ]
                )
                transaction.update(transaction_coding)
            transactions.append(transaction)
        return TransactionsHolder(pd.DataFrame(transactions))

    @staticmethod
    def extract_holdings(table: Tag) -> HoldingsHolder:
        holding_tags = table.find_all("derivativeHolding")
        if len(holding_tags) == 0:
            return HoldingsHolder()
        holdings = []
        for holding_tag in holding_tags:
            underlying_tag = holding_tag.find("underlyingSecurity")
            ownership_nature = holding_tag.find("ownershipNature")

            holding = dict(
                [
                    security(holding_tag),
                    underlying_security(underlying_tag),
                    exercise_price(holding_tag),
                    exercise_date(holding_tag),
                    expiration_date(holding_tag),
                    underlying_shares(underlying_tag),
                    ownership(ownership_nature)
                ]
            )
            holdings.append(holding)
        return HoldingsHolder(pd.DataFrame(holdings))


class OwnershipDocument:

    def __init__(self,
                 form: str,
                 footnotes: Dict[str, str],
                 issuer: Issuer,
                 reporting_owner: Owner,
                 reporting_owner_address: Address,
                 reporting_relationship: ReportingRelationship,
                 non_derivatives: NonDerivativeTable,
                 derivatives: DerivativeTable,
                 signatures: List[OwnerSignature],
                 reporting_period: str,
                 remarks: str
                 ):
        self.form: str = form
        self.footnotes: Dict[str, str] = footnotes
        self.issuer: Issuer = issuer
        self.reporting_owner: Owner = reporting_owner
        self.reporting_owner_address: Address = reporting_owner_address
        self.reporting_relationship: ReportingRelationship = reporting_relationship
        self.non_derivatives: NonDerivativeTable = non_derivatives
        self.derivatives: DerivativeTable = derivatives
        self.signatures: List[OwnerSignature] = signatures
        self.reporting_period: str = reporting_period
        self.remarks: str = remarks

    @classmethod
    def from_xml(cls,
                 content: str):
        soup = BeautifulSoup(content, "xml")

        root = soup.find("ownershipDocument")

        # Period of report
        report_period = child_text(root, "periodOfReport")

        remarks = child_text(root, "remarks")

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
            state=child_text(reporting_owner_address_tag, "rptOwnerState"),
            zipcode=child_text(reporting_owner_address_tag, "rptOwnerZipCode"),
            state_description=child_text(reporting_owner_address_tag, "rptOwnerStateDescription")
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

        ownership_document = OwnershipDocument(
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
            remarks=remarks
        )
        return ownership_document

    def __repr__(self):
        return (f"Form {self.form} Ownership(issuer={self.issuer.name} [{self.issuer.cik}], "
                f"period={self.reporting_period})")

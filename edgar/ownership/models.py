"""
Leaf value objects for SEC ownership forms (3, 4, 5).

These are the self-contained domain primitives with no dependencies on other
ownership classes — issuer/owner metadata, transaction codes, signatures and
footnotes. They are re-exported from ``edgar.ownership.ownershipforms`` and the
``edgar.ownership`` package for backward compatibility.
"""
from typing import Dict, List, Optional

import pandas as pd
from bs4 import Tag
from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.core import IntString
from edgar.richtools import repr_rich

__all__ = [
    'Issuer',
    'ReportingRelationship',
    'TransactionCode',
    'PostTransactionAmounts',
    'Underyling',
    'OwnerSignature',
    'OwnerSignatures',
    'Footnotes',
]


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
                 officer_title: Optional[str] = None):
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


class Footnotes:

    def __init__(self,
                 footnotes: Dict[str, str]):
        self._footnotes = footnotes

    def __getitem__(self, item):
        return self._footnotes[item]

    def get(self,
            footnote_id: str,
            default_value: Optional[str] = None):
        return self._footnotes.get(footnote_id, default_value)

    @property
    def text(self) -> str:
        """All footnote text combined into a single string."""
        return " ".join(self._footnotes.values())

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
             for el in footnotes_el.find_all("footnote") if isinstance(el, Tag)
             } if footnotes_el and isinstance(footnotes_el, Tag) else {}
        )

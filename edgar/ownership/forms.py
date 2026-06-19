"""
Top-level domain objects for SEC ownership forms.

``Ownership`` is the shared parser and accessor surface for Forms 3, 4 and 5;
``Form3``/``Form4``/``Form5`` are thin typed subclasses. Holdings/transaction
tables live in ``tables``, summaries in ``summary``, and the text/HTML rendering
in ``text_render``/``html_render``.
"""
import itertools
from functools import cached_property
from typing import List, Optional, Union

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup, Tag

from edgar.ownership.core import safe_numeric
from edgar.ownership.html_render import ownership_to_html
from edgar.ownership.models import (
    Footnotes,
    Issuer,
    OwnerSignature,
    OwnerSignatures,
)
from edgar.ownership.owners import ReportingOwners
from edgar.ownership.summary import InitialOwnershipSummary, TransactionSummary
from edgar.ownership.summary_records import SecurityHolding, TransactionActivity
from edgar.ownership.table_containers import DerivativeTable, NonDerivativeTable
from edgar.ownership.tables import (
    DerivativeHoldings,
    DerivativeTransactions,
    NonDerivativeHoldings,
    NonDerivativeTransactions,
)
from edgar.ownership.text_render import ownership_to_context
from edgar.richtools import repr_rich
from edgar.xmltools import child_text

__all__ = [
    'Ownership',
    'Form3',
    'Form4',
    'Form5',
]


def _parse_aff10b5_one(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized in {'1', 'true'}:
        return True
    if normalized in {'0', 'false'}:
        return False
    return None


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
                 no_securities: bool = False,
                 aff10b5_one: Optional[bool] = None,
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
        self.aff10b5_one = aff10b5_one

    @property
    def insider_name(self):
        return self._get_owner()

    @property
    def position(self):
        return "/ ".join([o.position for o in self.reporting_owners.owners])

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

    def _resolve_footnotes(self, footnote_ids: str) -> str:
        """
        Resolve footnote IDs to their full text.

        Args:
            footnote_ids: Newline-separated string of footnote IDs (e.g., "F1\nF2")

        Returns:
            Combined text of all footnotes, separated by spaces
        """
        if not footnote_ids or not footnote_ids.strip():
            return ""

        texts = []
        for fid in footnote_ids.strip().split('\n'):
            fid = fid.strip()
            if fid and self.footnotes:
                text = self.footnotes.get(fid, "")
                if text:
                    texts.append(text)

        return " ".join(texts)

    def get_transaction_activities(self) -> List[TransactionActivity]:
        """Extract all transaction activities from the filing"""
        activities = []

        # Process non-derivative market transactions (P and S codes)
        if self.market_trades is not None and not self.market_trades.empty:
            for _, row in self.market_trades.iterrows():
                transaction_type = "purchase" if row.AcquiredDisposed == 'A' else "sale"
                row_shares = int("0" + "".join(itertools.takewhile(str.isdigit, row.Shares))) \
                    if isinstance(row.Shares, str) else row.Shares
                footnote_ids = getattr(row, 'footnotes', '') or ''
                activities.append(TransactionActivity(
                    transaction_type=transaction_type,
                    code=row.Code,
                    shares=row_shares,
                    price_per_share=row.Price,
                    value=row_shares * row.Price if not pd.isna(row.Price) else 0,
                    security_type="non-derivative",
                    security_title=row.Security,
                    footnote_ids=footnote_ids,
                    footnotes_text=self._resolve_footnotes(footnote_ids),
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
                footnote_ids = getattr(row, 'footnotes', '') or ''
                activities.append(TransactionActivity(
                    transaction_type=transaction_type,
                    code=row.Code,
                    shares=row_shares,
                    price_per_share=row.Price if pd.notna(row.Price) else None,  # Add price
                    # Don't calculate value for non-market transactions unless price available
                    value=row_shares * row.Price if pd.notna(row.Price) and row.Price > 0 else 0,
                    security_type="non-derivative",
                    security_title=row.Security,
                    footnote_ids=footnote_ids,
                    footnotes_text=self._resolve_footnotes(footnote_ids),
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
                    footnote_ids = getattr(row, 'footnotes', '') or ''
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
                        footnote_ids=footnote_ids,
                        footnotes_text=self._resolve_footnotes(footnote_ids),
                    ))
        return activities

    @cached_property
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
                aff10b5_one=self.aff10b5_one,
                all_footnotes_text=self.footnotes.text if self.footnotes else "",
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

    @cached_property
    def derivative_trades(self):
        # First get the derivative trades from the derivative table
        return self.derivative_table.derivative_trades

    @cached_property
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
        if not isinstance(root, Tag):
            raise ValueError("Could not find ownershipDocument in XML")

        # Period of report
        report_period = child_text(root, "periodOfReport")

        remarks = child_text(root, "remarks") or ""

        no_securities = child_text(root, "noSecuritiesOwned") == "1"
        aff10b5_one = _parse_aff10b5_one(child_text(root, "aff10b5One"))

        # Footnotes
        footnotes = Footnotes.extract(root)

        # Issuer
        issuer_tag = root.find("issuer")
        if not isinstance(issuer_tag, Tag):
            raise ValueError("Could not find issuer in XML")
        issuer = Issuer(
            cik=child_text(issuer_tag, "issuerCik") or "",
            name=child_text(issuer_tag, "issuerName") or "",
            ticker=child_text(issuer_tag, "issuerTradingSymbol") or ""
        )

        # Signature
        ownership_signatures = OwnerSignatures([OwnerSignature(
            signature=(child_text(el, "signatureName") or "").strip(),
            date=child_text(el, "signatureDate") or ""
        ) for el in root.find_all("ownerSignature") if isinstance(el, Tag)]
        )

        # Reporting Owner
        reporting_owner = ReportingOwners.from_reporting_owner_tags(root.find_all("reportingOwner"), remarks=remarks)

        form = child_text(root, "documentType") or ""
        # Non derivatives
        non_derivative_table_tag = root.find("nonDerivativeTable")
        non_derivative_table = NonDerivativeTable.extract(non_derivative_table_tag, form=form) if isinstance(non_derivative_table_tag, Tag) else NonDerivativeTable(holdings=NonDerivativeHoldings(), transactions=NonDerivativeTransactions(), form=form)

        # Derivatives
        derivative_table_tag = root.find("derivativeTable")
        derivative_table = DerivativeTable.extract(derivative_table_tag, form=form) if isinstance(derivative_table_tag, Tag) else DerivativeTable(holdings=DerivativeHoldings(), transactions=DerivativeTransactions(), form=form)

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
            'no_securities': no_securities,
            'aff10b5_one': aff10b5_one
        }
        return ownership_document

    def to_context(self, detail: str = 'standard') -> str:
        """
        AI-optimized context string.

        Args:
            detail: 'minimal' (~100 tokens), 'standard' (~300 tokens), 'full' (~500+ tokens)
        """
        return ownership_to_context(self, detail)

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

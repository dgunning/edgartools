from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd
from bs4 import BeautifulSoup, Tag
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Column, Table
from rich.text import Text

from edgar._party import Address, Contact, Filer
from edgar.entity import Company
from edgar.richtools import repr_rich
from edgar.xmltools import child_text, child_texts

__all__ = ['Form144',
           'SecuritiesHolder',
           'SecuritiesInformationHolder',
           'SecuritiesToBeSoldHolder',
           'SecuritiesSoldPast3MonthsHolder',
           'concat_securities_information',
           'concat_securities_to_be_sold'
           ]


@dataclass(frozen=True)
class SecuritiesInformation:
    """
          <securitiesInformation>
         <securitiesClassTitle>Common stock</securitiesClassTitle>
         <brokerOrMarketmakerDetails>
            <name>Virtu Financial</name>
            <address>
               <com:street1>One Liberty Plaza</com:street1>
               <com:street2>165 Broadway</com:street2>
               <com:city>New York</com:city>
               <com:stateOrCountry>NY</com:stateOrCountry>
               <com:zipCode>10006</com:zipCode>
            </address>
         </brokerOrMarketmakerDetails>
         <noOfUnitsSold>17087</noOfUnitsSold>
         <aggregateMarketValue>1282000.00</aggregateMarketValue>
         <noOfUnitsOutstanding>161514066</noOfUnitsOutstanding>
         <approxSaleDate>08/27/2022</approxSaleDate>
         <securitiesExchangeName>CHX</securitiesExchangeName>
      </securitiesInformation>
    """
    security_class: str
    units_to_be_sold: int
    aggregate_market_value: float
    units_outstanding: int
    approx_sale_date: str
    exchange_name: str
    broker_name: str
    broker_address: Address

    def to_dict(self):
        # Convert this object to a dictionary
        return {
            'security_class': self.security_class,
            'units_to_be_sold': self.units_to_be_sold,
            'market_value': self.aggregate_market_value,
            'units_outstanding': self.units_outstanding,
            'approx_sale_date': self.approx_sale_date,
            'exchange_name': self.exchange_name,
            'broker_name': self.broker_name
        }

    @classmethod
    def from_tag(cls, tag: Tag):
        security_class = child_text(tag, 'securitiesClassTitle')
        units_to_be_sold = child_text(tag, 'noOfUnitsSold')
        aggregate_market_value = child_text(tag, 'aggregateMarketValue')
        units_outstanding = child_text(tag, 'noOfUnitsOutstanding')
        approx_sale_date = child_text(tag, 'approxSaleDate')
        exchange_name = child_text(tag, 'securitiesExchangeName')

        # Get the broker or market maker
        broker_or_marketmaker_tag = tag.find('brokerOrMarketmakerDetails')
        if isinstance(broker_or_marketmaker_tag, Tag):
            broker_name = child_text(broker_or_marketmaker_tag, 'name')
            # Get the address
            address_el = broker_or_marketmaker_tag.find('address')
            if isinstance(address_el, Tag):
                address = Address(
                    street1=child_text(address_el, 'street1'),
                    street2=child_text(address_el, 'street2'),
                    city=child_text(address_el, 'city'),
                    state_or_country=child_text(address_el, 'stateOrCountry'),
                    zipcode=child_text(address_el, 'zipCode')
                )
            else:
                address = None
        else:
            broker_name = None
            address = None

        return cls(
            security_class=security_class or "",
            units_to_be_sold=int(units_to_be_sold or "0"),
            aggregate_market_value=float(aggregate_market_value) if aggregate_market_value else None,
            units_outstanding=int(units_outstanding or "0"),
            approx_sale_date=approx_sale_date,
            exchange_name=exchange_name,
            broker_name=broker_name,
            broker_address=address
        )


@dataclass(frozen=True)
class SecuritiesToBeSold:
    """
          <securitiesToBeSold>
         <securitiesClassTitle>Common stock - 2</securitiesClassTitle>
         <acquiredDate>01/01/1933</acquiredDate>
         <natureOfAcquisitionTransaction>Employee Stock Award -1</natureOfAcquisitionTransaction>
         <nameOfPersonfromWhomAcquired>Issuer-1</nameOfPersonfromWhomAcquired>
         <isGiftTransaction>Y</isGiftTransaction>
         <donarAcquiredDate>01/01/1933</donarAcquiredDate>
         <amountOfSecuritiesAcquired>17087</amountOfSecuritiesAcquired>
         <paymentDate>08/15/2021</paymentDate>
         <natureOfPayment>CASH-25</natureOfPayment>
      </securitiesToBeSold>
    """
    security_class: str
    acquired_date: str
    nature_of_acquisition_transaction: str
    name_of_person_from_whom_acquired: str
    is_gift_transaction: str
    donar_acquired_date: str
    amount_of_securities_acquired: int
    payment_date: str
    nature_of_payment: str

    def to_dict(self):
        # Convert this object to a dictionary
        return {
            'security_class': self.security_class,
            'acquired_date': self.acquired_date,
            'amount_acquired': self.amount_of_securities_acquired,
            'nature_of_acquisition': self.nature_of_acquisition_transaction,
            'acquired_from': self.name_of_person_from_whom_acquired,
            'nature_of_payment': self.nature_of_payment,
            'is_gift': self.is_gift_transaction,
            'donar_acquired_date': self.donar_acquired_date,
            'payment_date': self.payment_date
        }

    @classmethod
    def from_tag(cls, tag: Tag):
        security_class = child_text(tag, 'securitiesClassTitle')
        acquired_date = child_text(tag, 'acquiredDate')
        nature_of_acquisition_transaction = child_text(tag, 'natureOfAcquisitionTransaction')
        name_of_person_from_whom_acquired = child_text(tag, 'nameOfPersonfromWhomAcquired')
        is_gift_transaction = child_text(tag, 'isGiftTransaction')
        donar_acquired_date = child_text(tag, 'donarAcquiredDate')
        amount_of_securities_acquired = child_text(tag, 'amountOfSecuritiesAcquired')
        payment_date = child_text(tag, 'paymentDate')
        nature_of_payment = child_text(tag, 'natureOfPayment')
        return cls(
            security_class=security_class,
            acquired_date=acquired_date,
            nature_of_acquisition_transaction=nature_of_acquisition_transaction,
            name_of_person_from_whom_acquired=name_of_person_from_whom_acquired,
            is_gift_transaction=is_gift_transaction,
            donar_acquired_date=donar_acquired_date,
            amount_of_securities_acquired=int(amount_of_securities_acquired),
            payment_date=payment_date,
            nature_of_payment=nature_of_payment
        )


@dataclass(frozen=True)
class SecuritiesSoldPast3Months:
    """
          <securitiesSoldInPast3Months>
         <sellerDetails>
            <name>Virtu Financial</name>
            <address>
               <com:street1>One Liberty Plaza</com:street1>
               <com:street2>165 Broadway</com:street2>
               <com:city>New York</com:city>
               <com:stateOrCountry>NY</com:stateOrCountry>
               <com:zipCode>10006</com:zipCode>
            </address>
         </sellerDetails>
         <securitiesClassTitle>Common Stock</securitiesClassTitle>
         <saleDate>08/27/2022</saleDate>
         <amountOfSecuritiesSold>0</amountOfSecuritiesSold>
         <grossProceeds>0.00</grossProceeds>
      </securitiesSoldInPast3Months>
    """
    seller_name: str
    seller_address: Address
    security_class: str
    sale_date: str
    amount_of_securities_sold: int
    gross_proceeds: float

    def to_dict(self):
        # Convert this object to a dictionary
        return {
            'security_class': self.security_class,
            'seller_name': self.seller_name,
            'sale_date': self.sale_date,
            'amount_sold': self.amount_of_securities_sold,
            'gross_proceeds': self.gross_proceeds
        }

    @classmethod
    def from_tag(cls, tag: Tag):
        seller_details = tag.find('sellerDetails')
        seller_name = child_text(seller_details, 'name')
        # Get the address
        address_el = seller_details.find('address')
        seller_address = Address(
            street1=child_text(address_el, 'street1'),
            street2=child_text(address_el, 'street2'),
            city=child_text(address_el, 'city'),
            state_or_country=child_text(address_el, 'stateOrCountry'),
            zipcode=child_text(address_el, 'zipCode')
        )
        security_class = child_text(tag, 'securitiesClassTitle')
        sale_date = child_text(tag, 'saleDate')
        amount_of_securities_sold = child_text(tag, 'amountOfSecuritiesSold')
        gross_proceeds = child_text(tag, 'grossProceeds')
        return cls(
            seller_name=seller_name,
            seller_address=seller_address,
            security_class=security_class,
            sale_date=sale_date,
            amount_of_securities_sold=int(amount_of_securities_sold),
            gross_proceeds=float(gross_proceeds) if gross_proceeds else None
        )


@dataclass(frozen=True)
class NoticeSignature:
    """
          <noticeSignature>
         <noticeDate>09/08/2022</noticeDate>
         <planAdoptionDates>
            <planAdoptionDate>08/15/2022</planAdoptionDate>
            <planAdoptionDate>08/15/2022</planAdoptionDate>
            <planAdoptionDate>01/02/1933</planAdoptionDate>
         </planAdoptionDates>
         <signature>/s/ Jan van der Velden</signature>
      </noticeSignature>
    """
    notice_date: str
    plan_adoption_dates: List[str]
    signature: str

    @classmethod
    def from_tag(cls, tag: Tag):
        notice_date = child_text(tag, 'noticeDate')
        # Get text directly from each planAdoptionDate tag (child_text looks for nested elements)
        plan_adoption_dates = [d.text.strip() for d in tag.find_all('planAdoptionDate')]
        signature = child_text(tag, 'signature')
        return cls(
            notice_date=notice_date,
            plan_adoption_dates=plan_adoption_dates,
            signature=signature
        )


class SecuritiesHolder:
    """
    Base wrapper class for securities DataFrames.

    Provides safe access to DataFrame data with empty checks and iteration support.
    Follows the DataHolder pattern from ownership forms.
    """

    def __init__(self, data: Optional[pd.DataFrame] = None, name: str = "SecuritiesHolder"):
        self._data = data if data is not None else pd.DataFrame()
        self._name = name

    @property
    def data(self) -> pd.DataFrame:
        """Access the underlying DataFrame."""
        return self._data

    @property
    def empty(self) -> bool:
        """Check if the holder contains no data."""
        return self._data is None or len(self._data) == 0

    def __len__(self) -> int:
        return 0 if self._data is None else len(self._data)

    def __getitem__(self, item: int):
        """Get row at index as a named tuple."""
        if self.empty:
            return None
        if item < 0 or item >= len(self._data):
            return None
        return self._data.iloc[item]

    def __iter__(self) -> Iterator:
        """Iterate over rows."""
        if not self.empty:
            for row in self._data.itertuples():
                yield row

    def __bool__(self) -> bool:
        return not self.empty


class SecuritiesInformationHolder(SecuritiesHolder):
    """
    Holder for securities information from Form 144.

    Provides aggregation properties for multi-security filings.
    """

    def __init__(self, data: Optional[pd.DataFrame] = None):
        super().__init__(data, "SecuritiesInformation")

    @property
    def total_units_to_be_sold(self) -> int:
        """Total units to be sold across all securities."""
        if self.empty:
            return 0
        return int(self._data['units_to_be_sold'].sum())

    @property
    def total_market_value(self) -> float:
        """Total aggregate market value across all securities."""
        if self.empty:
            return 0.0
        return float(self._data['market_value'].sum())

    @property
    def security_classes(self) -> List[str]:
        """List of all security classes in the filing."""
        if self.empty:
            return []
        return self._data['security_class'].tolist()

    @property
    def exchanges(self) -> List[str]:
        """List of unique exchanges in the filing."""
        if self.empty:
            return []
        return self._data['exchange_name'].unique().tolist()

    @property
    def brokers(self) -> List[str]:
        """List of unique brokers in the filing."""
        if self.empty:
            return []
        return self._data['broker_name'].unique().tolist()

    @property
    def percent_of_outstanding(self) -> float:
        """Percentage of total outstanding shares being sold."""
        if self.empty:
            return 0.0
        outstanding = self._data['units_outstanding'].iloc[0]
        if outstanding == 0:
            return 0.0
        return (self.total_units_to_be_sold / outstanding) * 100

    @property
    def avg_price_per_unit(self) -> float:
        """Average price per unit being sold."""
        if self.empty or self.total_units_to_be_sold == 0:
            return 0.0
        return self.total_market_value / self.total_units_to_be_sold


class SecuritiesToBeSoldHolder(SecuritiesHolder):
    """
    Holder for securities to be sold information.

    Provides aggregation for acquisition history.
    """

    def __init__(self, data: Optional[pd.DataFrame] = None):
        super().__init__(data, "SecuritiesToBeSold")

    @property
    def total_amount_acquired(self) -> int:
        """Total amount of securities acquired across all entries."""
        if self.empty:
            return 0
        return int(self._data['amount_acquired'].sum())

    @property
    def acquisition_dates(self) -> List[str]:
        """List of unique acquisition dates."""
        if self.empty:
            return []
        return self._data['acquired_date'].unique().tolist()

    @property
    def has_gift_transactions(self) -> bool:
        """Check if any securities were acquired as gifts."""
        if self.empty:
            return False
        return 'Y' in self._data['is_gift'].values


class SecuritiesSoldPast3MonthsHolder(SecuritiesHolder):
    """
    Holder for securities sold in past 3 months.

    Provides aggregation for recent sale activity.
    """

    def __init__(self, data: Optional[pd.DataFrame] = None):
        super().__init__(data, "SecuritiesSoldPast3Months")

    @property
    def total_amount_sold(self) -> int:
        """Total amount of securities sold in past 3 months."""
        if self.empty:
            return 0
        return int(self._data['amount_sold'].sum())

    @property
    def total_gross_proceeds(self) -> float:
        """Total gross proceeds from past 3 months sales."""
        if self.empty:
            return 0.0
        return float(self._data['gross_proceeds'].sum())

    @property
    def sellers(self) -> List[str]:
        """List of unique sellers."""
        if self.empty:
            return []
        return self._data['seller_name'].unique().tolist()


class Form144:

    def __init__(self,
                 filing,
                 filer: Filer,
                 contact: Contact,
                 issuer_cik: str,
                 issuer_name: str,
                 sec_file_number: str,
                 issuer_contact_phone: str,
                 person_selling: str,
                 relationships: List[str],
                 address: Address,
                 securities_information: pd.DataFrame,
                 securities_to_be_sold: pd.DataFrame,
                 securities_sold_past_3_months: pd.DataFrame,
                 nothing_to_report: bool,
                 remarks: str,
                 notice_signature: NoticeSignature
                 ):
        assert filing.form in ['144', '144/A'], f"This form should be a Form 144 but was {filing.form}"
        self._filing = filing
        self.filer = filer
        self.contact: Contact = contact
        self.issuer_cik = issuer_cik
        self.issuer_name = issuer_name
        self.sec_file_number = sec_file_number
        self.issuer_contact_phone = issuer_contact_phone
        self.person_selling = person_selling
        self.relationships = relationships
        self.address = address

        # Wrap DataFrames in holder classes for safe access and aggregation
        self._securities_information = SecuritiesInformationHolder(securities_information)
        self._securities_to_be_sold = SecuritiesToBeSoldHolder(securities_to_be_sold)
        self._securities_sold_past_3_months = SecuritiesSoldPast3MonthsHolder(securities_sold_past_3_months)

        self.nothing_to_report = nothing_to_report
        self.remarks = remarks
        self.notice_signature = notice_signature

    # === DataFrame Access Properties (backward compatible) ===

    @property
    def securities_information(self) -> pd.DataFrame:
        """Access raw securities information DataFrame (backward compatible)."""
        return self._securities_information.data

    @property
    def securities_to_be_sold(self) -> pd.DataFrame:
        """Access raw securities to be sold DataFrame (backward compatible)."""
        return self._securities_to_be_sold.data

    @property
    def securities_sold_past_3_months(self) -> pd.DataFrame:
        """Access raw securities sold past 3 months DataFrame (backward compatible)."""
        return self._securities_sold_past_3_months.data

    # === Holder Access Properties (new API) ===

    @property
    def securities_info(self) -> SecuritiesInformationHolder:
        """Access securities information with aggregation support."""
        return self._securities_information

    @property
    def securities_selling(self) -> SecuritiesToBeSoldHolder:
        """Access securities to be sold with aggregation support."""
        return self._securities_to_be_sold

    @property
    def recent_sales(self) -> SecuritiesSoldPast3MonthsHolder:
        """Access securities sold in past 3 months with aggregation support."""
        return self._securities_sold_past_3_months

    # === Filing Information ===

    @property
    def company(self) -> Company:
        """Get the Company object for the issuer."""
        return Company(self.issuer_cik)

    @property
    def is_amendment(self) -> bool:
        """Check if this is an amendment (144/A)."""
        return '/A' in self._filing.form

    @property
    def filing_date(self):
        """Get the filing date."""
        return self._filing.filing_date

    # === Aggregation Properties ===

    @property
    def total_units_to_be_sold(self) -> int:
        """Total units to be sold across all securities."""
        return self._securities_information.total_units_to_be_sold

    @property
    def total_market_value(self) -> float:
        """Total aggregate market value across all securities."""
        return self._securities_information.total_market_value

    @property
    def total_amount_acquired(self) -> int:
        """Total amount of securities acquired (from securities_to_be_sold)."""
        return self._securities_to_be_sold.total_amount_acquired

    @property
    def total_amount_sold_past_3_months(self) -> int:
        """Total amount sold in past 3 months."""
        return self._securities_sold_past_3_months.total_amount_sold

    @property
    def total_gross_proceeds_past_3_months(self) -> float:
        """Total gross proceeds from past 3 months."""
        return self._securities_sold_past_3_months.total_gross_proceeds

    @property
    def num_securities(self) -> int:
        """Number of securities in the filing."""
        return len(self._securities_information)

    @property
    def is_multi_security(self) -> bool:
        """Check if filing contains multiple securities."""
        return len(self._securities_information) > 1

    # === Convenience Properties ===

    @property
    def units_to_be_sold(self) -> int:
        """Total units to be sold across all securities."""
        return self._securities_information.total_units_to_be_sold

    @property
    def market_value(self) -> float:
        """Total market value across all securities."""
        return self._securities_information.total_market_value

    @property
    def approx_sale_date(self) -> Optional[str]:
        """Approximate sale date of the first security (for single-security filings)."""
        if self._securities_information.empty:
            return None
        return str(self._securities_information.data.iloc[0].approx_sale_date)

    @property
    def security_class(self) -> Optional[str]:
        """Security class of the first security (for single-security filings)."""
        if self._securities_information.empty:
            return None
        return str(self._securities_information.data.iloc[0].security_class)

    @property
    def broker_name(self) -> Optional[str]:
        """Broker name for the first security (for single-security filings)."""
        if self._securities_information.empty:
            return None
        return str(self._securities_information.data.iloc[0].broker_name)

    @property
    def exchange_name(self) -> Optional[str]:
        """Exchange name for the first security (for single-security filings)."""
        if self._securities_information.empty:
            return None
        return str(self._securities_information.data.iloc[0].exchange_name)

    # === Analyst Metrics ===

    @property
    def percent_of_holdings(self) -> float:
        """Percentage of outstanding shares being sold."""
        return self._securities_information.percent_of_outstanding

    @property
    def avg_price_per_unit(self) -> float:
        """Average price per unit across all securities."""
        return self._securities_information.avg_price_per_unit

    def _valid_plan_dates(self) -> List[str]:
        """Filter out placeholder dates (1933 dates are SEC form defaults)."""
        return [d for d in self.notice_signature.plan_adoption_dates
                if d and not d.endswith('/1933')]

    @property
    def is_10b5_1_plan(self) -> bool:
        """Whether this sale is under a 10b5-1 trading plan."""
        return bool(self._valid_plan_dates())

    @property
    def days_since_plan_adoption(self) -> Optional[int]:
        """Days from most recent plan adoption to sale date."""
        valid_dates = self._valid_plan_dates()
        if not valid_dates or not self.approx_sale_date:
            return None
        try:
            sale_date = pd.to_datetime(self.approx_sale_date, format='%m/%d/%Y')
            plan_dates = [pd.to_datetime(d, format='%m/%d/%Y') for d in valid_dates]
            most_recent = max(plan_dates)
            return (sale_date - most_recent).days
        except (ValueError, TypeError):
            return None

    @property
    def cooling_off_compliant(self) -> Optional[bool]:
        """Whether 90-day cooling-off period was observed (post-2022 SEC rule)."""
        days = self.days_since_plan_adoption
        if days is None:
            return None
        return bool(days >= 90)

    @property
    def holding_period_days(self) -> Optional[int]:
        """Average days between acquisition and sale."""
        if self._securities_to_be_sold.empty or not self.approx_sale_date:
            return None
        try:
            sale_date = pd.to_datetime(self.approx_sale_date, format='%m/%d/%Y')
            df = self._securities_to_be_sold.data
            # Filter out placeholder dates (1933 dates are SEC form defaults)
            valid_dates = df[~df['acquired_date'].str.endswith('/1933')]['acquired_date']
            if valid_dates.empty:
                return None
            acquired_dates = pd.to_datetime(valid_dates, format='%m/%d/%Y')
            avg_days = (sale_date - acquired_dates).dt.days.mean()
            return int(avg_days)
        except (ValueError, TypeError):
            return None

    @property
    def holding_period_years(self) -> Optional[float]:
        """Average holding period in years."""
        days = self.holding_period_days
        if days is None:
            return None
        return round(days / 365.25, 1)

    # === Anomaly Detection ===

    @property
    def is_large_liquidation(self) -> bool:
        """Flag if selling >5% of outstanding shares."""
        return bool(self.percent_of_holdings > 5.0)

    @property
    def is_short_hold(self) -> bool:
        """Flag if holding period <1 year."""
        years = self.holding_period_years
        return bool(years is not None and years < 1.0)

    @property
    def has_multiple_plans(self) -> bool:
        """Flag if multiple 10b5-1 plan adoption dates."""
        valid = self._valid_plan_dates()
        return len(set(valid)) > 1

    @property
    def anomaly_flags(self) -> List[str]:
        """List of anomaly flags for quick screening."""
        flags = []
        if self.is_large_liquidation:
            flags.append('LARGE_LIQUIDATION')
        if self.is_short_hold:
            flags.append('SHORT_HOLD')
        if self.cooling_off_compliant is False:
            flags.append('COOLING_OFF_VIOLATION')
        if self.has_multiple_plans:
            flags.append('MULTIPLE_PLANS')
        return flags

    # === Summary Methods ===

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the Form 144 filing.

        Returns:
            Dictionary with key filing information
        """
        return {
            'person_selling': self.person_selling,
            'issuer': self.issuer_name,
            'issuer_cik': self.issuer_cik,
            'relationships': self.relationships,
            'num_securities': self.num_securities,
            'total_units_to_be_sold': self.total_units_to_be_sold,
            'total_market_value': self.total_market_value,
            'security_classes': self._securities_information.security_classes,
            'exchanges': self._securities_information.exchanges,
            'nothing_to_report_past_3_months': self.nothing_to_report,
            'total_sold_past_3_months': self.total_amount_sold_past_3_months,
            'is_amendment': self.is_amendment,
            'filing_date': self.filing_date,
        }

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the Form 144 to a summary DataFrame.

        Returns:
            DataFrame with one row per security, including filing metadata
        """
        if self._securities_information.empty:
            return pd.DataFrame()

        df = self._securities_information.data.copy()
        df['person_selling'] = self.person_selling
        df['issuer'] = self.issuer_name
        df['issuer_cik'] = self.issuer_cik
        df['filing_date'] = self.filing_date
        df['is_amendment'] = self.is_amendment

        return df

    def to_analyst_summary(self) -> Dict[str, Any]:
        """
        Summary optimized for investment analysis.

        Returns dict with all key metrics for quick screening including:
        - Identity and relationship info
        - Sale metrics (units, value, % of holdings)
        - Timing analysis (holding period, 10b5-1 compliance)
        - Anomaly flags for unusual activity
        """
        return {
            # Identity
            'person_selling': self.person_selling,
            'issuer': self.issuer_name,
            'issuer_cik': self.issuer_cik,
            'relationships': self.relationships,
            'filing_date': str(self.filing_date),

            # Sale metrics
            'units_to_sell': self.units_to_be_sold,
            'market_value': self.market_value,
            'percent_of_holdings': round(self.percent_of_holdings, 2),
            'avg_price_per_unit': round(self.avg_price_per_unit, 2),

            # Timing
            'sale_date': self.approx_sale_date,
            'holding_period_years': self.holding_period_years,

            # 10b5-1 Plan
            'is_10b5_1_plan': self.is_10b5_1_plan,
            'days_since_plan_adoption': self.days_since_plan_adoption,
            'cooling_off_compliant': self.cooling_off_compliant,

            # Recent activity
            'sold_past_3_months': self.total_amount_sold_past_3_months,
            'proceeds_past_3_months': self.total_gross_proceeds_past_3_months,

            # Flags
            'anomaly_flags': self.anomaly_flags,

            # Metadata
            'is_amendment': self.is_amendment,
            'exchange': self.exchange_name,
            'broker': self.broker_name,
        }

    @staticmethod
    def parse_xml(xml: str) -> Dict[str, object]:
        soup = BeautifulSoup(xml, 'xml')

        root = soup.find('edgarSubmission')

        form144 = {}

        header_data = root.find('headerData')
        filer_info_el = header_data.find('filerInfo')

        filer_el = filer_info_el.find('filer')
        filer_credentials_el = filer_el.find('filerCredentials')
        form144['filer'] = Filer(
            cik=child_text(filer_credentials_el, 'cik'),
            entity_name=child_text(filer_credentials_el, 'name'),
            file_number=child_text(filer_credentials_el, 'secFileNumber')
        )

        # Contact info
        contact_el = filer_el.find('contact')
        form144['contact'] = Contact(
            name=child_text(contact_el, 'name'),
            phone_number=child_text(contact_el, 'phone'),
            email=child_text(contact_el, 'email')
        ) if contact_el else None

        form_data = root.find('formData')
        # Issuer
        issuer_el = form_data.find('issuerInfo')
        form144['issuer_cik'] = child_text(issuer_el, 'issuerCik')
        form144['issuer_name'] = child_text(issuer_el, 'issuerName')
        form144['sec_file_number'] = child_text(issuer_el, 'secFileNumber')
        form144['issuer_contact_phone'] = child_text(issuer_el, 'issuerContactPhone')
        form144['person_selling'] = child_text(issuer_el, 'nameOfPersonForWhoseAccountTheSecuritiesAreToBeSold')

        relationship_el = issuer_el.find('relationshipsToIssuer')
        form144['relationships'] = child_texts(relationship_el, 'relationshipToIssuer')

        issuer_address_el = issuer_el.find("issuerAddress")
        address: Address = Address(
            street1=child_text(issuer_address_el, "street1"),
            street2=child_text(issuer_address_el, "street2"),
            city=child_text(issuer_address_el, "city"),
            state_or_country=child_text(issuer_address_el, "stateOrCountry"),
            state_or_country_description=child_text(issuer_address_el, "stateOrCountryDescription"),
            zipcode=child_text(issuer_address_el, "zipCode")
        )
        form144['address'] = address

        # Securities Information
        form144['securities_information'] = pd.DataFrame([
            SecuritiesInformation.from_tag(el).to_dict()
            for el in form_data.find_all('securitiesInformation')
        ])

        # Securities to be sold
        form144['securities_to_be_sold'] = pd.DataFrame([
            SecuritiesToBeSold.from_tag(el).to_dict()
            for el in form_data.find_all('securitiesToBeSold')
        ])
        # Nothing to report flag
        form144['nothing_to_report'] = child_text(form_data, 'nothingToReportFlagOnSecuritiesSoldInPast3Months')

        # Securities sold in past 3 months
        form144['securities_sold_past_3_months'] = pd.DataFrame([
            SecuritiesSoldPast3Months.from_tag(el).to_dict()
            for el in form_data.find_all('securitiesSoldInPast3Months')
        ])

        # Remarks
        form144['remarks'] = child_text(form_data, 'remarks')

        # Notice signature
        form144['notice_signature'] = NoticeSignature.from_tag(form_data.find('noticeSignature'))
        return form144

    @classmethod
    def from_filing(cls, filing):
        assert filing.form in ['144', '144/A'], f"This form should be a Form 144 but was {filing.form}"
        xml = filing.xml()

        if xml:
            form144 = cls.parse_xml(xml)
            return cls(filing=filing, **form144)
        return None

    # === Display Properties ===

    def _metrics_table(self) -> Table:
        """Build key metrics summary table."""
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Label", style="dim")
        table.add_column("Value", style="bold")
        table.add_column("Label2", style="dim")
        table.add_column("Value2", style="bold")

        # Row 1: Seller & Relationship
        table.add_row(
            "Seller", Text(self.person_selling, style="deep_sky_blue1"),
            "Relationship", ', '.join(self.relationships) if self.relationships else "-"
        )

        # Row 2: Units & Market Value
        units_text = f"{self.units_to_be_sold:,}" if self.units_to_be_sold else "-"
        if self.security_class:
            units_text += f" {self.security_class}"
        market_value_text = f"${self.market_value:,.2f}" if self.market_value else "-"
        table.add_row(
            "Units", Text(units_text, style="red1"),
            "Market Value", market_value_text
        )

        # Row 3: % Holdings & Avg Price
        pct_text = f"{self.percent_of_holdings:.2f}%" if self.percent_of_holdings else "-"
        avg_price_text = f"${self.avg_price_per_unit:.2f}" if self.avg_price_per_unit else "-"
        table.add_row(
            "% Holdings", pct_text,
            "Avg Price", avg_price_text
        )

        # Row 4: Sale Date & Exchange/Broker
        sale_date = self.approx_sale_date or "-"
        exchange_broker = f"{self.exchange_name or '-'} / {self.broker_name or '-'}"
        table.add_row(
            "Sale Date", sale_date,
            "Exchange/Broker", exchange_broker
        )

        return table

    def _compliance_table(self) -> Table:
        """Build 10b5-1 plan compliance row."""
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Label", style="dim")
        table.add_column("Value")
        table.add_column("Label2", style="dim")
        table.add_column("Value2")
        table.add_column("Label3", style="dim")
        table.add_column("Value3")

        # 10b5-1 Plan status
        plan_text = Text("Yes", style="bold") if self.is_10b5_1_plan else Text("No", style="dim")

        # Days since adoption
        days = self.days_since_plan_adoption
        days_text = str(days) if days is not None else "-"

        # Cooling off compliance
        compliant = self.cooling_off_compliant
        if compliant is True:
            compliant_text = Text("Compliant", style="green")
        elif compliant is False:
            compliant_text = Text("Violation", style="red bold")
        else:
            compliant_text = Text("-", style="dim")

        table.add_row(
            "10b5-1 Plan", plan_text,
            "Days Since Adoption", days_text,
            "Cooling Off", compliant_text
        )

        return table

    def _flags_text(self) -> Text:
        """Build anomaly flags display."""
        flags = self.anomaly_flags
        if not flags:
            return Text("Anomalies: None", style="green")
        else:
            return Text(f"Anomalies: {', '.join(flags)}", style="red bold")

    def _securities_info_panel(self) -> Optional[Panel]:
        """Securities information panel - returns None if empty."""
        if self._securities_information.empty:
            return None

        table = Table("Security Class", "Date of Sale",
                      Column(header="Units To Be Sold", style="red1"),
                      "Market Value", "Shares Outstanding", "Exchange", "Broker",
                      box=box.SIMPLE, row_styles=["", "dim"])

        for row in self.securities_information.itertuples():
            table.add_row(
                row.security_class,
                row.approx_sale_date,
                f"{row.units_to_be_sold:,}",
                f"${row.market_value:,.0f}",
                f"{row.units_outstanding:,}",
                row.exchange_name,
                row.broker_name
            )

        return Panel(table, title="Securities Information", border_style="dim")

    def _securities_to_sell_panel(self) -> Optional[Panel]:
        """Securities to be sold panel - returns None if empty."""
        if self._securities_to_be_sold.empty:
            return None

        table = Table("Security Class", "Date Acquired",
                      Column(header="Units Acquired", style="green"),
                      "Nature of Acquisition", "Acquired From", "Gift",
                      "Payment Date", "Nature of Payment",
                      box=box.SIMPLE, row_styles=["", "dim"])

        for row in self.securities_to_be_sold.itertuples():
            table.add_row(
                row.security_class,
                row.acquired_date,
                f"{row.amount_acquired:,}",
                row.nature_of_acquisition,
                row.acquired_from,
                row.is_gift,
                row.payment_date,
                row.nature_of_payment
            )

        return Panel(table, title="Securities To Be Sold", border_style="dim")

    def _past_3_months_panel(self):
        """Securities sold past 3 months panel - returns Text if empty, Panel if has data."""
        if self._securities_sold_past_3_months.empty:
            return Text("Securities Sold Past 3 Months: None", style="dim")

        table = Table("Security Class", "Sale Date",
                      Column(header="Amount Sold", style="red1"),
                      "Proceeds", "Seller Name",
                      box=box.SIMPLE, row_styles=["", "dim"])

        for row in self.securities_sold_past_3_months.itertuples():
            table.add_row(
                row.security_class,
                row.sale_date,
                f"{row.amount_sold:,}",
                f"${row.gross_proceeds:,.2f}",
                row.seller_name
            )

        return Panel(table, title="Securities Sold Past 3 Months", border_style="dim")

    def _signature_footer(self) -> Table:
        """Build signature footer."""
        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("Signature", ratio=3)
        table.add_column("Date", ratio=1, justify="right")

        table.add_row(
            self.notice_signature.signature or "",
            self.notice_signature.notice_date or ""
        )

        # Add plan adoption dates if present
        if self.notice_signature.plan_adoption_dates:
            valid_dates = [d for d in self.notice_signature.plan_adoption_dates if d and d != '01/01/1933']
            if valid_dates:
                table.add_row(
                    Text(f"Plan Adoption: {', '.join(valid_dates)}", style="dim"),
                    ""
                )

        return table

    def __rich__(self):
        # Build title with amendment indicator
        form_type = f"Form {self._filing.form}"
        if self.is_amendment:
            title = f"{form_type} [yellow](Amendment)[/yellow]"
        else:
            title = form_type

        # Subtitle with issuer info
        subtitle = f"{self.issuer_name} (CIK: {self.issuer_cik})"

        # Build sections list
        sections = [
            self._metrics_table(),
            self._compliance_table(),
            self._flags_text(),
        ]

        # Conditional data tables
        if panel := self._securities_info_panel():
            sections.append(panel)
        if panel := self._securities_to_sell_panel():
            sections.append(panel)

        # Past 3 months always returns something (Text if empty, Panel if has data)
        sections.append(self._past_3_months_panel())

        # Signature footer
        sections.append(self._signature_footer())

        # Remarks (if any)
        if self.remarks:
            sections.append(Text(f"Remarks: {self.remarks}", style="italic"))

        return Panel(
            Group(*sections),
            title=title,
            subtitle=subtitle,
            subtitle_align="left"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


def concat_securities_information(form144_lst: List[Form144]):
    return pd.concat([form144.securities_information for form144 in form144_lst])


def concat_securities_to_be_sold(form144_lst: List[Form144]):
    return pd.concat([form144.securities_to_be_sold for form144 in form144_lst])

from typing import List, Optional

from bs4 import Tag
from rich.console import Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from pydantic import BaseModel
from edgar.richtools import repr_rich
from edgar.xmltools import child_text, child_value
from edgar.core import IntString

__all__ = [
    'Address',
    'Issuer',
    'Person',
    'Name',
    'Filer',
    'get_addresses_as_columns'
]


class Address(BaseModel):

    street1: Optional[str] = None
    street2: Optional[str] = None
    city: Optional[str] = None
    state_or_country: Optional[str] = None
    state_or_country_description: Optional[str] = None
    zipcode: Optional[str] = None

    @property
    def empty(self):
        return not self.street1 and not self.street2 and not self.city and not self.state_or_country and not self.zipcode

    def __str__(self):
        if not self.street1:
            return ""
        address_format = "{street1}\n"
        if self.street2:
            address_format += "{street2}\n"
        address_format += "{city}, {state_or_country} {zipcode}"

        return address_format.format(
            street1=self.street1,
            street2=self.street2,
            city=self.city,
            state_or_country=self.state_or_country_description or self.state_or_country,
            zipcode=self.zipcode or ""
        )

    def __repr__(self):
        return (f'Address(street1="{self.street1 or ""}", street2="{self.street2 or ""}", city="{self.city or ""}",'
                f'zipcode="{self.zipcode or ""}", state_or_country="{self.state_or_country} or "")'
                )


def get_addresses_as_columns(mailing_address: Optional[Address], business_address: Optional[Address]) -> Columns:
    """
    Returns a rich Columns object with mailing and business addresses
    """
    addresses = []
    if mailing_address and not mailing_address.empty:
        addresses.append(Panel(Text(str(mailing_address)), title='\U00002709 Mailing Address', width=40))
    if business_address and not business_address.empty:
        addresses.append(Panel((Text(str(business_address))), title='\U0001F3E2 Business Address', width=40))
    return Columns(addresses, equal=True, expand=True)


class Issuer:
    """
     <primaryIssuer>
        <cik>0001961089</cik>
        <entityName>1685 38th REIT, L.L.C.</entityName>
        <issuerAddress>
            <street1>2029 CENTURY PARK EAST</street1>
            <street2>SUITE 1370</street2>
            <city>LOS ANGELES</city>
            <stateOrCountry>CA</stateOrCountry>
            <stateOrCountryDescription>CALIFORNIA</stateOrCountryDescription>
            <zipCode>90067</zipCode>
        </issuerAddress>
        <issuerPhoneNumber>424-313-1550</issuerPhoneNumber>
        <jurisdictionOfInc>DELAWARE</jurisdictionOfInc>
        <issuerPreviousNameList>
            <value>None</value>
        </issuerPreviousNameList>
        <edgarPreviousNameList>
            <value>None</value>
        </edgarPreviousNameList>
        <entityType>Limited Liability Company</entityType>
        <yearOfInc>
            <withinFiveYears>true</withinFiveYears>
            <value>2022</value>
        </yearOfInc>
    </primaryIssuer>

    """

    def __init__(self,
                 cik: IntString,
                 entity_name: str,
                 entity_type: str,
                 primary_address: Address,
                 phone_number: str,
                 jurisdiction: str,
                 issuer_previous_names: List[str],
                 edgar_previous_names: List[str],
                 year_of_incorporation: IntString,
                 incorporated_within_5_years: bool):
        self.cik = cik
        self.entity_name: str = entity_name
        self.entity_type = entity_type
        self.primary_address: Address = primary_address
        self.phone_number: str = phone_number
        self.issuer_previous_names = issuer_previous_names
        self.edgar_previous_names = edgar_previous_names
        self.jurisdiction: str = jurisdiction
        self.year_of_incorporation = year_of_incorporation
        self.incorporated_within_5_years: bool = incorporated_within_5_years

    @classmethod
    def from_xml(cls, issuer_el: Tag):
        # edgar previous names
        edgar_previous_names_el = issuer_el.find("edgarPreviousNameList")
        edgar_previous_names = [el.text
                                for el in edgar_previous_names_el.find_all("value")
                                if el.text != 'None'] if edgar_previous_names_el else []

        # issuer previous names
        issuer_previous_names_el = issuer_el.find("issuerPreviousNameList")
        issuer_previous_names = [el.text
                                 for el in issuer_previous_names_el.find_all("value")
                                 if el.text != 'None'] if issuer_previous_names_el else []

        year_of_inc_el = issuer_el.find("yearOfInc")

        # Address
        issuer_address_el = issuer_el.find("issuerAddress")
        address: Address = Address(
            street1=child_text(issuer_address_el, "street1"),
            street2=child_text(issuer_address_el, "street2"),
            city=child_text(issuer_address_el, "city"),
            state_or_country=child_text(issuer_address_el, "stateOrCountry"),
            state_or_country_description=child_text(issuer_address_el, "stateOrCountryDescription"),
            zipcode=child_text(issuer_address_el, "zipCode")
        )

        return cls(
            cik=child_text(issuer_el, "cik"),
            entity_name=child_text(issuer_el, "entityName"),
            phone_number=child_text(issuer_el, "issuerPhoneNumber"),
            jurisdiction=child_text(issuer_el, "jurisdictionOfInc"),
            entity_type=child_text(issuer_el, "entityType"),
            edgar_previous_names=edgar_previous_names,
            primary_address=address,
            issuer_previous_names=issuer_previous_names,
            year_of_incorporation=child_value(issuer_el, "yearOfInc"),
            incorporated_within_5_years=year_of_inc_el and child_text(year_of_inc_el, "withinFiveYears") == "true"
        )

    def __rich__(self):
        table = Table("issuer", "entity type", "incorporated")
        table.add_row(self.entity_name, self.entity_type, self.year_of_incorporation)
        return Group(table)

    def __repr__(self):
        return repr_rich(self.__rich__())


class Person:

    def __init__(self,
                 first_name: str,
                 last_name: str,
                 address: Optional[Address] = None):
        self.first_name = first_name
        self.last_name = last_name
        self.address: Address = address

    def __str__(self):
        return f"{self.first_name} {self.first_name}"

    def __repr__(self):
        return f"{self.first_name} {self.last_name}"


class Name:

    def __init__(self,
                 first_name: str,
                 middle_name: str,
                 last_name: str,
                 suffix:Optional[str]=None):
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.suffix = suffix

    @property
    def full_name(self):
        return f"{self.first_name}{' ' + self.middle_name or ''} {self.last_name} {self.suffix or ''}".rstrip()

    def __str__(self):
        return self.full_name

    def __repr__(self):
        return self.full_name


class Filer:

    def __init__(self,
                 cik: str,
                 entity_name: str,
                 file_number: str
                 ):
        self.cik: str = cik
        self.entity_name: str = entity_name
        self.file_number: str = file_number

    def __str__(self):
        return f"{self.entity_name} ({self.cik})"

    def __repr__(self):
        return f"{self.entity_name} ({self.cik})"


class Contact:

    def __init__(self,
                 name: str,
                 phone_number: str,
                 email: str):
        self.name: str = name
        self.phone_number: str = phone_number
        self.email: str = email

    def __str__(self):
        return f"{self.name} ({self.phone_number}) {self.email}"

    def __repr__(self):
        return f"{self.name} ({self.phone_number}) {self.email}"

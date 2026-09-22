from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.core import IntString
from edgar.richtools import repr_rich
from edgar.xmltools import XmlNode, child_text, child_value, element_text, find_all_elements, find_element

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

    @classmethod
    def from_dict(cls, address_dict: Dict[str, Any]):
        return Address(
                street1=address_dict.get('STREET1'),
                street2=address_dict.get('STREET2'),
                city=address_dict.get('CITY'),
                state_or_country=address_dict.get('STATE'),
                zipcode=address_dict.get('ZIP')
            )

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


def get_addresses_as_columns(*,
                             mailing_address: Optional[Address],
                             business_address: Optional[Address]) -> Columns:
    """
    Returns a rich Columns object with mailing and business addresses
    """
    addresses = []
    if mailing_address and not mailing_address.empty:
        addresses.append(Panel(Text(str(mailing_address)), title='\U00002709 Mailing Address', width=40))
    if business_address and not business_address.empty:
        addresses.append(Panel((Text(str(business_address))), title='\U0001F3E2 Business Address', width=40))
    return Columns(addresses, equal=True, expand=True)


def _previous_names(previous_name_list_el: Optional[XmlNode]) -> List[str]:
    """The previous-name entries of an `<...PreviousNameList>` element.

    SEC writes these as `<value>` in most filings but `<previousName>` in others;
    both spellings are collected, in document order, filtering the literal `'None'`
    placeholder SEC writes for "no previous names" and any element that appears
    under both spellings.
    """
    if previous_name_list_el is None:
        return []
    names = []
    seen = set()
    for el in (find_all_elements(previous_name_list_el, "value")
              + find_all_elements(previous_name_list_el, "previousName")):
        text = element_text(el)
        if text == 'None' or text in seen:
            continue
        seen.add(text)
        names.append(text)
    return names


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
    def from_xml(cls, issuer_el: XmlNode):
        # edgar previous names
        edgar_previous_names_el = find_element(issuer_el, "edgarPreviousNameList")
        edgar_previous_names = _previous_names(edgar_previous_names_el)

        # issuer previous names
        issuer_previous_names_el = find_element(issuer_el, "issuerPreviousNameList")
        issuer_previous_names = _previous_names(issuer_previous_names_el)

        year_of_inc_el = find_element(issuer_el, "yearOfInc")

        # Address
        issuer_address_el = find_element(issuer_el, "issuerAddress")
        address: Address = Address(
            street1=child_text(issuer_address_el, "street1") if issuer_address_el is not None else None,
            street2=child_text(issuer_address_el, "street2") if issuer_address_el is not None else None,
            city=child_text(issuer_address_el, "city") if issuer_address_el is not None else None,
            state_or_country=child_text(issuer_address_el, "stateOrCountry") if issuer_address_el is not None else None,
            state_or_country_description=child_text(issuer_address_el, "stateOrCountryDescription") if issuer_address_el is not None else None,
            zipcode=child_text(issuer_address_el, "zipCode") if issuer_address_el is not None else None
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
            incorporated_within_5_years=(child_text(year_of_inc_el, "withinFiveYears") == "true"
                                         if year_of_inc_el is not None else None)
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
                 address: Optional[Address] = None,
                 relationships: Optional[List[str]] = None,
                 relationship_clarification: Optional[str] = None):
        self.first_name = first_name
        self.last_name = last_name
        self.address: Address = address
        # Form D related-person relationships, e.g. ["Executive Officer", "Director",
        # "Promoter"] from <relatedPersonRelationshipList>. Empty for contexts that
        # don't carry a relationship.
        self.relationships: List[str] = relationships or []
        self.relationship_clarification: Optional[str] = relationship_clarification

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"{self.first_name} {self.last_name}"


class Name:

    def __init__(self,
                 first_name: str,
                 middle_name: Optional[str],
                 last_name: str,
                 suffix: Optional[str] = None):
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.suffix = suffix

    @property
    def full_name(self):
        # Every part is optional in practice: the XML parsers feed this from
        # child_text(), which returns None for an absent element — a filer with no
        # <middleName> is the common case, not an edge case.
        return " ".join(part for part in
                        (self.first_name, self.middle_name, self.last_name, self.suffix)
                        if part)

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

"""
Reporting owners for SEC ownership forms (3, 4, 5).

``Owner`` is the parsed reporting-person record; ``ReportingOwners`` is the
collection wrapper that builds owners from the form's ``reportingOwner`` XML
tags (resolving each owner's entity to decide whether to reverse the name).
"""
from dataclasses import dataclass
from typing import List, Optional

from bs4 import ResultSet
from rich import box
from rich.panel import Panel
from rich.table import Column, Table

from edgar._party import Address
from edgar.core import get_bool
from edgar.display.formatting import reverse_name
from edgar.entity import Entity
from edgar.richtools import repr_rich
from edgar.xmltools import child_text

__all__ = [
    'Owner',
    'ReportingOwners',
]


@dataclass(frozen=True)
class Owner:
    cik: str
    is_company: bool
    name: str
    name_unreversed: str
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
    def display_title(officer_title: Optional[str] = None,
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
        table = Table(Column("Owner", style="bold deep_sky_blue1"),
                      "Position",
                      "Cik",
                      "Location", box=box.SIMPLE,
                      row_styles=["", "bold"])
        for owner in self.owners:
            table.add_row(owner.name, owner.position, owner.cik, f"{owner.address.city}")

        title = "\U0001F468‍\U0001F4BC Reporting Owner"
        if len(self) > 1:
            title += "s"
        return Panel(table, title=title, expand=False)

    def __repr__(self):
        return repr_rich(self.__rich__())

    @classmethod
    def from_reporting_owner_tags(cls, reporting_owners: ResultSet, remarks: str = ''):
        # Reporting Owner
        owners = []

        for reporting_owner_tag in reporting_owners:
            reporting_owner_id_tag = reporting_owner_tag.find("reportingOwnerId")

            cik = child_text(reporting_owner_id_tag, "rptOwnerCik")
            unreversed_owner_name = child_text(reporting_owner_id_tag, "rptOwnerName")

            # Check if it is a company. If not, reverse the name
            entity = Entity(int(cik))

            # Check if the entity is a company or an individual
            is_company = entity and entity.data.is_company
            if not is_company:
                owner_name = reverse_name(unreversed_owner_name)
            else:
                owner_name = unreversed_owner_name

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
                name_unreversed=unreversed_owner_name,
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

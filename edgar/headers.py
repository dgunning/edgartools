from datetime import datetime
from typing import Any, Dict, List, Optional

import orjson as json
import pandas as pd
from bs4 import BeautifulSoup, Comment, Tag
from pydantic import BaseModel
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Column, Table
from rich.text import Text

from edgar._party import Address, get_addresses_as_columns
from edgar.config import SEC_BASE_URL
from edgar.formatting import display_size
from edgar.httprequests import download_file
from edgar.reference import describe_form
from edgar.richtools import repr_rich

__all__ = ['FilingDirectory', 'IndexHeaders', 'ReportingOwner', 'CompanyData', 'FilingValues', 'FormerCompany']


class FilingDirectory:
    """
    The location for the filing on SEC EDGAR and detailed locations and timestamps for the files in the filing
    Sourced from the index.json file in the filing directory
    """

    def __init__(self, name: str, parent_dir: str, items: pd.DataFrame):
        self.name = name
        self.parent_dir = parent_dir
        self.items = items

    @property
    def accession_number(self):
        "Convert 000121390024004875 to 0001213900-24-004875"
        accession_no = self.name.split("/")[-1]
        return f"{accession_no[:10]}-{accession_no[10:12]}-{accession_no[12:]}"

    @property
    def index_headers(self):
        return download_file(f"{SEC_BASE_URL}/{self.name}/{self.accession_number}-index-headers.html")

    @classmethod
    def load(cls, basedir: str):
        index_url = f"{basedir}/index.json"
        index = json.loads(download_file(index_url))
        directory_json = index['directory']
        items = (pd.DataFrame(data=directory_json['item'])
                 .rename(columns={"name": "Name", "last-modified": "LastModified", "size": "Size"})
                 .filter(["Name", "LastModified", "Size"])
                 )
        directory: FilingDirectory = FilingDirectory(
            name=directory_json['name'],
            parent_dir=directory_json['parent-dir'],
            items=items
        )
        return directory

    def __len__(self):
        return len(self.items)

    def __rich__(self):
        table = Table(
            "Name", "LastModified", "Size",
            title=Text(f"Filing Directory {self.name}", style="bold"),
            row_styles=["", "bold"],
            box=box.SIMPLE)
        for _, row in self.items.iterrows():
            table.add_row(row['Name'], row['LastModified'], display_size(row['Size']))
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


"""
 Represent the SEC filing headers of a filing.

 The headers are extracted from the HTML file of the filing. This is the file  `<accession-number>-index-headers.html` 

"""


class CompanyData(BaseModel):
    conformed_name: str
    cik: str
    assigned_sic: Optional[str] = None
    organization_name: Optional[str] = None
    irs_number: Optional[str] = None
    fiscal_year_end: Optional[str] = None

    @property
    def name(self):
        return self.conformed_name

    def __rich__(self):
        table = Table(Column("", style="bold deep_sky_blue1"), "",
                      box=box.ROUNDED,
                      show_header=False,
                      )
        table.add_row(self.conformed_name, self.cik)
        return table


class FilingValues(BaseModel):
    form_type: str
    act: str
    file_number: str
    film_number: str


class FormerCompany(BaseModel):
    former_conformed_name: str
    date_changed: str


class Filer(BaseModel):
    company_data: CompanyData
    filing_values: FilingValues
    business_address: Address
    mail_address: Address
    former_company: List[FormerCompany]

    def __rich__(self):
        contents = [self.company_data,
                    get_addresses_as_columns(business_address=self.business_address, mailing_address=self.mail_address)
                    ]

        return Panel(Group(*contents), title="Filer", style="bold", box=box.ROUNDED)

    def __repr__(self):
        return repr_rich(self.__rich__())


class SubjectCompany(BaseModel):
    company_data: CompanyData
    filing_values: FilingValues
    business_address: Address
    mail_address: Address
    former_company: List[FormerCompany]

    def __rich__(self):
        contents = [self.company_data,
                    get_addresses_as_columns(business_address=self.business_address, mailing_address=self.mail_address)
                    ]

        return Panel(Group(*contents), title="Subject Company", style="bold", box=box.ROUNDED)

    def __repr__(self):
        return repr_rich(self.__rich__())


class OwnerData(BaseModel):
    conformed_name: str
    cik: str
    organization_name: Optional[str] = None

    @property
    def name(self):
        return self.conformed_name

    def __rich__(self):
        table = Table(Column("", style="bold deep_sky_blue1"), "",
                      box=box.ROUNDED,
                      show_header=False,
                      )
        table.add_row(self.conformed_name, self.cik)
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


class ReportingOwner(BaseModel):
    company_data: Optional[CompanyData]
    owner_data: Optional[OwnerData]
    filing_values: FilingValues
    mail_address: Address

    def __rich__(self):
        contents = []
        if self.company_data:
            contents.append(self.company_data)
        if self.owner_data:
            contents.append(self.owner_data)
        contents.append(Text(str(self.mail_address)))

        return Panel(Group(*contents), title="Reporting Owner", style="bold", box=box.ROUNDED)

    def __repr__(self):
        return repr_rich(self.__rich__())


class Issuer(BaseModel):
    company_data: CompanyData
    mail_address: Address
    business_address: Address


nested_tags = [
    'filer',
    'issuer',
    'subject_company',
    'reporting_owner',
    'owner_data',
    'company_data',
    'filing_values',
    'business_address',
    'mail_address',
    'former_company'
]


class IndexHeaders(BaseModel):
    """
    Represent the SEC filing headers of a filing.
    This is parsed from the comment section of the HTML file `<accession-number>-index-headers.html`
    """
    filing_date: str
    acceptance_datetime: datetime
    accession_number: str
    form: str
    public_document_count: int
    period: Optional[str] = None
    items: List[str]
    date_of_filing_date_change: Optional[str] = None
    effectiveness_date: Optional[str] = None
    filer: Optional[Filer] = None
    reporting_owner: Optional[ReportingOwner] = None
    subject_company: Optional[SubjectCompany] = None
    issuer: Optional[Issuer] = None

    @property
    def company_name(self):
        if self.filer:
            return self.filer.company_data.conformed_name
        elif self.subject_company:
            return self.subject_company.company_data.conformed_name
        elif self.issuer:
            return self.issuer.company_data.conformed_name
        return ""

    @property
    def title(self):
        return f"{self.form} - {self.company_name} {self.accession_number}"

    @staticmethod
    def _prepare_address(data: Dict[str, Any], address_type: str) -> Address:
        """
        Prepare an address object from the data dictionary.
        """
        address_dict = data.pop(address_type, {})
        address_dict['zipcode'] = address_dict.pop('zip', '')
        address_dict['state_or_country'] = address_dict.pop('state', '')
        return Address(**address_dict)

    @classmethod
    def load(cls, header_text: str):
        """
        Load the IndexHeaders from the HTML file content.
        """
        soup = BeautifulSoup(header_text, 'html.parser')

        # The SEC-HEADER tag contains the filing header information
        header_text = soup.find_all(string=lambda text: isinstance(text, Comment))[0].strip()


        lines = header_text.strip().split("\n")
        data: Dict[str, Any] = {}
        stack = [data]

        for line in lines:
            line = line.strip()
            # Skip the main SEC-HEADER tag
            if line.startswith("<SEC-HEADER>"):
                continue

            # Handle closing tags by popping the context stack
            if line.startswith("</"):
                if len(stack) > 1:  # Ensure we don't pop the root context
                    stack.pop()
                continue

            # Handle opening tags and values
            if line.startswith("<"):
                tag = line[1:].split(">")[0]
                class_name = tag.lower().replace("-", "_")
                value = line[len(tag) + 2:].strip()

                # If there is a value, add it to the current context
                if class_name not in nested_tags:
                    if isinstance(stack[-1], dict):
                        if class_name not in stack[-1]:
                            stack[-1][class_name] = value
                        else:
                            if not isinstance(stack[-1][class_name], list):
                                stack[-1][class_name] = [stack[-1][class_name]]
                            stack[-1][class_name].append(value)
                else:
                    # Create a new context for nested tags
                    new_context = {}
                    if isinstance(stack[-1], dict):
                        stack[-1][class_name] = new_context
                    elif isinstance(stack[-1], list):
                        stack[-1].append(new_context)
                    stack.append(new_context)
            else:
                # Handle text content within the current context
                if isinstance(stack[-1], dict):
                    stack[-1][class_name] = line
                elif isinstance(stack[-1], list):
                    stack[-1].append(line)
                else:
                    stack[-1] = [stack[-1], line]

        # Parsing nested objects into their respective classes
        filer_data = data.pop("filer", None)
        filer = None
        if filer_data:
            # Extract and initialize nested CompanyData for Filer
            company_data = CompanyData(**filer_data.pop("company_data", {}))
            # Extract and initialize nested FilingValues for Filer
            filing_values = FilingValues(
                form_type=filer_data["filing_values"].get("form_type", ""),
                act=filer_data["filing_values"].get("act", ""),
                file_number=filer_data["filing_values"].get("file_number", ""),
                film_number=filer_data["filing_values"].get("film_number", "")
            )
            # Extract and initialize nested Business and Mail Address for Filer
            business_address = cls._prepare_address(filer_data, "business_address")
            mail_address = cls._prepare_address(filer_data, "mail_address")

            # Handle FormerCompany elements
            former_company_raw = filer_data.pop("former_company", [])
            former_company = []
            if isinstance(former_company_raw, list):
                for fc in former_company_raw:
                    if isinstance(fc, dict):
                        former_company.append(FormerCompany(**fc))
                    elif isinstance(fc, str):
                        former_company.append(FormerCompany(former_conformed_name=fc, date_changed=''))

            # Initialize Filer with nested data
            filer = Filer(
                company_data=company_data,
                filing_values=filing_values,
                business_address=business_address,
                mail_address=mail_address,
                former_company=former_company
            )
            data["filer"] = filer

        # Process SubjectCompany if present
        subject_company_data = data.pop("subject_company", None)
        subject_company = None
        if subject_company_data:
            # Extract and initialize nested CompanyData for SubjectCompany
            company_data = CompanyData(**subject_company_data.pop("company_data", {}))
            # Extract and initialize nested FilingValues for SubjectCompany
            filing_values = FilingValues(
                form_type=subject_company_data["filing_values"].get("form_type", ""),
                act=subject_company_data["filing_values"].get("act", ""),
                file_number=subject_company_data["filing_values"].get("file_number", ""),
                film_number=subject_company_data["filing_values"].get("film_number", "")
            )
            # Extract and initialize nested Business and Mail Address for SubjectCompany
            business_address = cls._prepare_address(subject_company_data, "business_address")
            mail_address = cls._prepare_address(subject_company_data, "mail_address")

            # Handle FormerCompany elements
            former_company_raw = subject_company_data.pop("former_company", [])
            former_company = []
            if isinstance(former_company_raw, list):
                for fc in former_company_raw:
                    if isinstance(fc, dict):
                        former_company.append(FormerCompany(**fc))
                    elif isinstance(fc, str):
                        former_company.append(FormerCompany(former_conformed_name=fc, date_changed=''))

            # Initialize SubjectCompany with nested data
            subject_company = SubjectCompany(
                company_data=company_data,
                filing_values=filing_values,
                business_address=business_address,
                mail_address=mail_address,
                former_company=former_company
            )
            data["subject_company"] = subject_company

        # Process ReportingOwner if present
        reporting_owner_data = data.pop("reporting_owner", None)
        reporting_owner = None
        if reporting_owner_data:
            # Extract and initialize nested OwnerData or CompanyData for ReportingOwner
            owner_data = reporting_owner_data.pop("owner_data", None)
            company_data = reporting_owner_data.pop("company_data", None)
            owner_data_obj = OwnerData(**owner_data) if owner_data else None
            company_data_obj = CompanyData(**company_data) if company_data else None

            # Extract and initialize nested FilingValues for ReportingOwner
            filing_values = FilingValues(
                form_type=reporting_owner_data["filing_values"].get("form_type", ""),
                act=reporting_owner_data["filing_values"].get("act", ""),
                file_number=reporting_owner_data["filing_values"].get("file_number", ""),
                film_number=reporting_owner_data["filing_values"].get("film_number", "")
            )
            # Extract and initialize nested Mail Address for ReportingOwner
            mail_address = cls._prepare_address(reporting_owner_data, "mail_address")

            # Initialize ReportingOwner with nested data
            reporting_owner = ReportingOwner(
                company_data=company_data_obj,
                owner_data=owner_data_obj,
                filing_values=filing_values,
                mail_address=mail_address
            )
            data["reporting_owner"] = reporting_owner

            # Process Issuer if present
        issuer_data = data.pop("issuer", None)
        issuer = None
        if issuer_data:
            # Extract and initialize nested CompanyData for Issuer
            company_data = CompanyData(**issuer_data.pop("company_data", {}))
            # Extract and initialize nested Business and Mail Address for Issuer
            business_address = cls._prepare_address(issuer_data, "business_address")
            mail_address = cls._prepare_address(issuer_data, "mail_address")

            # Initialize Issuer with nested data
            issuer = Issuer(
                company_data=company_data,
                business_address=business_address,
                mail_address=mail_address
            )
            data["issuer"] = issuer

        # Ensure items is a list
        items = data.pop("items", [])
        if isinstance(items, str):
            items = [items]

        # Convert acceptance_datetime to datetime object
        acceptance_datetime_str = data.pop("acceptance_datetime")
        acceptance_datetime = datetime.strptime(acceptance_datetime_str,
                                                '%Y%m%d%H%M%S') if acceptance_datetime_str else None

        # Convert filing_date to date object
        filing_date_str = data.pop("filing_date", None)
        filing_date = datetime.strptime(filing_date_str, '%Y%m%d').strftime('%Y-%m-%d') if filing_date_str else None

        date_of_change_str = data.pop("date_of_filing_date_change", None)
        if date_of_change_str:
            data["date_of_filing_date_change"] = datetime.strptime(date_of_change_str, '%Y%m%d').strftime('%Y-%m-%d')

        # The type is really the form
        data["form"] = data.pop("type")

        # The public document count is an integer
        data["public_document_count"] = int(data.pop("public_document_count", 0))

        # Prepare the final dictionary for IndexHeaders initialization
        sec_header_data = {
            **data,
            "filing_date": filing_date,
            "acceptance_datetime": acceptance_datetime,
            "items": items,
            "filer": filer,
            "subject_company": subject_company,
            "reporting_owner": reporting_owner,
            "issuer": issuer
        }

        # The <PRE> block contains the HTML for the documents
        #documents = IndexHeaders._extract_documents_from_pre(soup.find("pre"))

        # Initialize IndexHeaders with the parsed data
        return cls(**sec_header_data)

    @staticmethod
    def _extract_documents_from_pre(pre_tag:Tag):
        soup = BeautifulSoup(pre_tag.text)
        document_tags = soup.find_all("document")
        for document_tag in document_tags:
            document_tag.find("type")


    @staticmethod
    def _extract_comment_text(soup):
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        if comments:
            return comments[0].strip()
        return None

    @staticmethod
    def _extract_accession_number(title: str):
        import re
        match = re.search(r'SEC EDGAR Submission (\d{10}-\d{2}-\d{6})', title)
        if match:
            return match.group(1)
        return None

    def __rich__(self):
        # Summary Information
        summary_table = Table("Filing Date", "Acceptance Datetime", "Documents", box=box.ROUNDED)
        summary_table.add_row(
            self.filing_date,
            datetime.strftime(self.acceptance_datetime, '%Y-%m-%d %H:%M:%S'),
            str(self.public_document_count))

        main_contents = [summary_table]
        if self.filer:
            main_contents.append(self.filer)
        if self.subject_company:
            main_contents.append(self.subject_company)
        if self.reporting_owner:
            main_contents.append(self.reporting_owner)

        if self.items and len(self.items) > 0:
            items_table = Table("Items", box=box.ROUNDED)
            for item in self.items:
                items_table.add_row(item)
            main_contents.append(items_table)

        main_panel: Panel = Panel(
            Group(*main_contents),
            box=box.ROUNDED,
            title=self.title,
            subtitle=describe_form(self.form),
            style="bold"
        )
        return main_panel

    def __repr__(self):
        return repr_rich(self.__rich__())

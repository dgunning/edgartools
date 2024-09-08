import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from rich.table import Table, Column
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box
from rich.console import Group
from edgar.reference import describe_form, states
from edgar.richtools import repr_rich
from edgar._party import Address, get_addresses_as_columns
from edgar.core import datefmt, reverse_name
from datetime import datetime

# Title text
mailing_address_title = "\U0001F4EC Mailing Address"
business_address_title = "\U0001F4EC Business Address"
company_title = "\U0001F3E2 Company Information"
filing_information_title = "\U0001F4D1 Filing Information"
reporting_owner_title = "\U0001F468 Reporting Owner"
issuer_title = "\U0001F4B5 Issuer"
filing_title = "\U0001F4D1 Filing"

__all__ = ['FilingMetadata', 'CompanyInformation', 'FilingInformation', 'FormerCompany', 'Filer', 'Owner',
           'ReportingOwner', 'SubjectCompany', 'Issuer', 'FilingHeader']


def preprocess_old_headers(text: str) -> str:
    """
    Preprocess old SEC headers to convert from a tag-based format to a tab-indented format
    and ensure no lines with hanging tags are included in the output.
    """
    # Pattern to find content enclosed within full tags, capturing tag names and content between them
    full_tag_pattern = re.compile(r'<([\w-]+)>\n(.*?)\n</\1>', re.DOTALL)

    # Convert full tag content to tabbed format without the tag name
    def full_tag_to_tabbed(match):
        content = match.group(2).strip()
        # Indent the content
        indented_content = '\n'.join('\t' + line for line in content.split('\n'))
        return f'{indented_content}'

    # Apply the full tag conversion
    result = full_tag_pattern.sub(full_tag_to_tabbed, text)

    # Remove any leftover standalone tags and any text following them on the same line
    result = re.sub(r'<[^/>]+>.*$', '', result, flags=re.MULTILINE)  # Removing entire lines with standalone tags

    # Ensure no hanging start or end tags remain
    result = re.sub(r'</?[\w-]+>', '', result)  # Now correctly handles tags with hyphens

    return result


class FilingMetadata:
    def __init__(self, metadata: Dict[str, Any]):
        self.metadata = metadata

    def get(self, key: str):
        value = self.metadata.get(key)
        if value:
            # Adjusted regular expressions to match correct date formats
            if re.match(r"^(20|19)\d{12}$", value):  # YYYY-MM-DD HH:MM:SS
                value = datefmt(value, "%Y-%m-%d %H:%M:%S")
            elif re.match(r"^(20|19)\d{6}$", value):  # YYYY-MM-DD
                value = datefmt(value, "%Y-%m-%d")
        return value

    def __getitem__(self, key: str):
        return self.get(key)

    def __rich__(self):
        # Ordered keys to be displayed first
        ordered_keys = ["ACCESSION NUMBER", "FILED AS OF DATE", "ACCEPTANCE-DATETIME", "CONFORMED SUBMISSION TYPE"]
        table = Table("", "", row_styles=["bold", ""], show_header=False, box=box.ROUNDED)

        # Add rows for ordered keys first if present
        for key in ordered_keys:
            value = self.get(key)
            if value is not None:
                table.add_row(f"{key}:", value)

        # Add the rest of the keys
        for key in self.metadata:
            if key not in ordered_keys:
                value = self.get(key)
                if value is not None:
                    table.add_row(f"{key}:", value)

        return table


@dataclass(frozen=True)
class CompanyInformation:
    name: str
    cik: str
    sic: str
    irs_number: str
    state_of_incorporation: str
    fiscal_year_end: str

    def __rich__(self):
        table = Table(Column("Company", style="bold deep_sky_blue1"), "Industry", "Incorporated", "Year End",
                      box=box.ROUNDED)
        table.add_row(f"{self.name} [{self.cik}]",
                      self.sic,
                      states.get(self.state_of_incorporation, self.state_of_incorporation),
                      self.fiscal_year_end)
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


@dataclass(frozen=True)
class FilingInformation:
    form: str
    file_number: str
    sec_act: str
    film_number: str

    def __rich__(self):
        table = Table("File Number", "SEC Act", "Film #", "Form", box=box.ROUNDED)
        table.add_row(self.file_number, self.sec_act, self.film_number, self.form)
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


@dataclass(frozen=True)
class FormerCompany:
    name: str
    date_of_change: str


@dataclass(frozen=True)
class Filer:
    company_information: CompanyInformation
    filing_information: FilingInformation
    business_address: Address
    mailing_address: Address
    former_company_names: Optional[List[FormerCompany]] = None

    def __rich__(self):
        filer_renderables = [self.company_information]

        # Addresses
        if self.business_address or self.mailing_address:
            filer_renderables.append(get_addresses_as_columns(self.business_address, self.mailing_address))

        # Former Company Names
        if self.former_company_names:
            former_company_table = Table("Former Name", "Changed", box=box.ROUNDED)
            for company_name in self.former_company_names:
                former_company_table.add_row(company_name.name, datefmt(company_name.date_of_change, '%b %d, %Y'))
            filer_renderables.append(former_company_table)

        return Panel(
            Group(*filer_renderables),
            title="Filer"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


@dataclass(frozen=True)
class Owner:
    name: str
    cik: str


@dataclass(frozen=True)
class ReportingOwner:
    owner: Owner
    company_information: CompanyInformation
    filing_information: FilingInformation
    business_address: Address
    mailing_address: Address

    def __rich__(self):
        top_renderables = []

        # Owner Table
        if self.owner:
            reporting_owner_table = Table(Column("Owner", style="bold deep_sky_blue1"), "CIK", box=box.ROUNDED)
            reporting_owner_table.add_row(self.owner.name, self.owner.cik)

            top_renderables = [reporting_owner_table]
        # Reporting Owner Filing Values
        if self.filing_information:
            filing_values_table = Table("File Number", "SEC Act", "Film #", box=box.ROUNDED)
            filing_values_table.add_row(self.filing_information.file_number,
                                        self.filing_information.sec_act,
                                        self.filing_information.film_number)
            top_renderables.append(filing_values_table)

        reporting_owner_renderables = [Columns(top_renderables)]

        # Addresses
        if self.business_address or self.mailing_address:
            reporting_owner_renderables.append(get_addresses_as_columns(self.business_address, self.mailing_address))

        return Panel(
            Group(
                *reporting_owner_renderables
            ),
            title=reporting_owner_title
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


@dataclass(frozen=True)
class SubjectCompany:
    company_information: CompanyInformation
    filing_information: FilingInformation
    business_address: Address
    mailing_address: Address
    former_company_names: Optional[List[FormerCompany]] = None

    def __rich__(self):
        subject_company_renderables = [self.company_information]

        # Addresses
        if self.business_address is not None or self.mailing_address is not None:
            subject_company_renderables.append(get_addresses_as_columns(self.business_address, self.mailing_address))

        if self.former_company_names or self.filing_information:
            name_and_filing_columns = []
            # Former Company Names
            if self.former_company_names:
                former_company_table = Table("Former Name", "Changed", box=box.ROUNDED)
                for company_name in self.former_company_names:
                    former_company_table.add_row(company_name.name, datefmt(company_name.date_of_change, '%b %d, %Y'))
                name_and_filing_columns.append(former_company_table)

            # Filing Information
            if self.filing_information:
                name_and_filing_columns.append(self.filing_information)

            subject_company_renderables.append(Columns(name_and_filing_columns))

        return Panel(
            Group(
                *subject_company_renderables
            ),
            title="Subject Company"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


@dataclass(frozen=True)
class Issuer:
    company_information: CompanyInformation
    business_address: Address
    mailing_address: Address

    def __rich__(self):
        issuer_table = Table(Column("Company", style="bold deep_sky_blue1"), "CIK", "SIC", "Fiscal Year End",
                             box=box.ROUNDED)
        issuer_table.add_row(self.company_information.name,
                             self.company_information.cik,
                             self.company_information.sic,
                             self.company_information.fiscal_year_end)

        # The list of renderables for the issuer panel
        issuer_renderables = [issuer_table]

        # Addresses
        if self.business_address or self.mailing_address:
            issuer_renderables.append(get_addresses_as_columns(self.business_address, self.mailing_address))

        return Panel(
            Group(
                *issuer_renderables
            ),
            title=issuer_title
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class FilingHeader:
    """
    Contains the parsed representation of the SEC-HEADER text at the top of the full submission text
    <SEC-HEADER>

    </SEC-HEADER>
    """

    def __init__(self,
                 text: str,
                 filing_metadata: Dict[str, str],
                 filers: List[Filer] = None,
                 reporting_owners: List[ReportingOwner] = None,
                 issuers: List[Issuer] = None,
                 subject_companies: List[SubjectCompany] = None):
        self.text: str = text
        self.filing_metadata: FilingMetadata = FilingMetadata(filing_metadata)
        self.filers: List[Filer] = filers
        self.reporting_owners: List[ReportingOwner] = reporting_owners
        self.issuers: List[Issuer] = issuers
        self.subject_companies: List[SubjectCompany] = subject_companies

    @property
    def accession_number(self):
        return self.filing_metadata.get("ACCESSION NUMBER")

    @property
    def form(self):
        return self.filing_metadata.get("CONFORMED SUBMISSION TYPE")

    @property
    def period_of_report(self):
        return self.filing_metadata.get("CONFORMED PERIOD OF REPORT")

    @property
    def filing_date(self):
        return self.filing_metadata.get("FILED AS OF DATE")

    @property
    def date_as_of_change(self):
        return self.filing_metadata.get("DATE AS OF CHANGE")

    @property
    def document_count(self):
        count = self.filing_metadata.get("PUBLIC DOCUMENT COUNT")
        if count and count.isdigit():
            return int(count)

    @property
    def acceptance_datetime(self):
        acceptance = self.filing_metadata.get("ACCEPTANCE-DATETIME")
        if acceptance:
            return datetime.strptime(acceptance, "%Y-%m-%d %H:%M:%S")

    @property
    def file_numbers(self):
        """Return the file numbers associated with this filing"""
        numbers = []
        if self.filers:
            numbers.extend([filer.filing_information.file_number for filer in self.filers])
        if self.reporting_owners:
            numbers.extend(
                [reporting_owner.filing_information.file_number for reporting_owner in self.reporting_owners])
        if self.subject_companies:
            numbers.extend(
                [subject_company.filing_information.file_number for subject_company in self.subject_companies])
        return list(set(numbers))

    @classmethod
    def parse_from_sgml_text(cls, header_text: str, preprocess=False):
        """
        Parse the SEC-HEADER text at the top of the submission text
        """
        data: Dict[str, Any] = {}
        current_header = None
        current_subheader = None

        # Preprocess the text to handle a different format from the 1990's
        if preprocess:
            header_text = preprocess_old_headers(header_text)

        # Read the lines in the content. This starts with <ACCEPTANCE-DATETIME>20230606213204
        lines = header_text.split('\n')
        for index, line in enumerate(header_text.split('\n')):
            if not line:
                continue

            # Keep track of the nesting level
            nesting_level = len(line) - len(line.lstrip('\t'))

            # Nested increases
            nesting_will_increase = index < len(lines) - 1 and nesting_level < len(lines[index + 1]) - len(
                lines[index + 1].lstrip('\t'))

            # The line ends with a ':' meaning nested content follows e.g. "REPORTING-OWNER:"
            line_ends_with_colon = line.rstrip('\t').endswith(':')

            is_header = (nesting_level == 0 and line_ends_with_colon) or nesting_will_increase
            if is_header:
                # Nested line means a subheader e.g. "OWNER DATA:"
                if line.startswith('\t'):
                    current_subheader = line.strip().split(':')[0]
                    if current_subheader == "FORMER COMPANY":  # Special case. This is a list of companies
                        if current_subheader not in data[current_header][-1]:
                            data[current_header][-1][current_subheader] = []
                        data[current_header][-1][current_subheader].append({})
                    else:
                        data[current_header][-1][current_subheader] = {}  # Expect only one record per key

                # Top level header
                else:
                    current_header = line.strip().split(':')[0]
                    if current_header not in data:
                        data[current_header] = []
                    data[current_header].append({})
            else:
                if line.strip().startswith("<"):
                    # The line looks like this <KEY>VALUE
                    key, value = line.split('>')
                    # Strip the leading '<' from the key
                    key = key[1:]
                    
                    # If the key already exists, we should convert it to a list
                    if key in data:
                        if isinstance(data[key], list):
                            data[key].append(value)
                        else:
                            data[key] = [data[key], value]
                    else:
                        data[key] = value
                elif ':' in line:
                    parts = line.strip().split(':')
                    if len(parts) == 2:
                        key, value = line.strip().split(':')
                    else:
                        key, value = parts[0], ":".join(parts[1:])
                    value = value.strip()
                    if not current_header:
                        # If the key already exists, we should convert it to a list
                        if key in data:
                            if isinstance(data[key], list):
                                data[key].append(value)
                            else:
                                data[key] = [data[key], value]
                        else:
                            data[key] = value
                    elif not current_subheader:
                        continue
                    else:
                        if current_subheader == "FORMER COMPANY":
                            data[current_header][-1][current_subheader][-1][key.strip()] = value
                        else:
                            data[current_header][-1][current_subheader][key.strip()] = value

        # The filer
        filers = []
        for filer_values in data.get('FILER', data.get('FILED BY', {})):
            filer_company_values = filer_values.get('COMPANY DATA')
            company_obj = None
            if filer_company_values:
                company_obj = CompanyInformation(
                    name=filer_company_values.get('COMPANY CONFORMED NAME'),
                    cik=filer_company_values.get('CENTRAL INDEX KEY'),
                    sic=filer_company_values.get('STANDARD INDUSTRIAL CLASSIFICATION'),
                    irs_number=filer_company_values.get('IRS NUMBER'),
                    state_of_incorporation=filer_company_values.get('STATE OF INCORPORATION'),
                    fiscal_year_end=filer_company_values.get('FISCAL YEAR END')
                )
            # Filing Values
            filing_values_text_section = filer_values.get('FILING VALUES')
            filing_values_obj = None
            if filing_values_text_section:
                filing_values_obj = FilingInformation(
                    form=filing_values_text_section.get('FORM TYPE'),
                    sec_act=filing_values_text_section.get('SEC ACT'),
                    file_number=filing_values_text_section.get('SEC FILE NUMBER'),
                    film_number=filing_values_text_section.get('FILM NUMBER')
                )
            # Now create the filer
            filer = Filer(
                company_information=company_obj,
                filing_information=filing_values_obj,
                business_address=Address(
                    street1=filer_values['BUSINESS ADDRESS'].get('STREET 1'),
                    street2=filer_values['BUSINESS ADDRESS'].get('STREET 2'),
                    city=filer_values['BUSINESS ADDRESS'].get('CITY'),
                    state_or_country=filer_values['BUSINESS ADDRESS'].get('STATE'),
                    zipcode=filer_values['BUSINESS ADDRESS'].get('ZIP'),

                ) if 'BUSINESS ADDRESS' in filer_values else None,
                mailing_address=Address(
                    street1=filer_values['MAIL ADDRESS'].get('STREET 1'),
                    street2=filer_values['MAIL ADDRESS'].get('STREET 2'),
                    city=filer_values['MAIL ADDRESS'].get('CITY'),
                    state_or_country=filer_values['MAIL ADDRESS'].get('STATE'),
                    zipcode=filer_values['MAIL ADDRESS'].get('ZIP'),

                ) if 'MAIL ADDRESS' in filer_values else None,
                former_company_names=[FormerCompany(date_of_change=record.get('DATE OF NAME CHANGE'),
                                                    name=record.get('FORMER CONFORMED NAME'))
                                      for record in filer_values['FORMER COMPANY']
                                      ]
                if 'FORMER COMPANY' in filer_values else None
            )
            filers.append(filer)

        # Reporting Owner

        reporting_owners = []

        for reporting_owner_values in data.get('REPORTING-OWNER', []):
            reporting_owner = None

            if reporting_owner_values:
                owner, name, cik = None, None, None
                if "OWNER DATA" in reporting_owner_values:
                    name = reporting_owner_values.get('OWNER DATA').get('COMPANY CONFORMED NAME')
                    cik = reporting_owner_values.get('OWNER DATA').get('CENTRAL INDEX KEY')
                elif 'COMPANY DATA' in reporting_owner_values:
                    name = reporting_owner_values['COMPANY DATA'].get('COMPANY CONFORMED NAME')
                    cik = reporting_owner_values['COMPANY DATA'].get('CENTRAL INDEX KEY')
                if cik:
                    from edgar.entities import Entity, EntityData
                    entity: EntityData = Entity(cik, include_old_filings=False)
                    if entity and not entity.is_company:
                        name = reverse_name(name)
                    owner = Owner(name=name, cik=cik)

                # Company Information
                company_information = CompanyInformation(
                    name=reporting_owner_values.get('COMPANY DATA').get('COMPANY CONFORMED NAME'),
                    cik=reporting_owner_values.get('COMPANY DATA').get('CENTRAL INDEX KEY'),
                    sic=reporting_owner_values.get('COMPANY DATA').get('STANDARD INDUSTRIAL CLASSIFICATION'),
                    irs_number=reporting_owner_values.get('COMPANY DATA').get('IRS NUMBER'),
                    state_of_incorporation=reporting_owner_values.get('COMPANY DATA').get('STATE OF INCORPORATION'),
                    fiscal_year_end=reporting_owner_values.get('COMPANY DATA').get('FISCAL YEAR END')
                ) if "COMPANY DATA" in reporting_owner_values else None

                # Filing Information
                filing_information = FilingInformation(
                    form=reporting_owner_values.get('FILING VALUES').get('FORM TYPE'),
                    sec_act=reporting_owner_values.get('FILING VALUES').get('SEC ACT'),
                    file_number=reporting_owner_values.get('FILING VALUES').get('SEC FILE NUMBER'),
                    film_number=reporting_owner_values.get('FILING VALUES').get('FILM NUMBER')
                ) if ('FILING VALUES' in reporting_owner_values and
                      reporting_owner_values.get('FILING VALUES').get('SEC FILE NUMBER')) else None

                # Business Address
                business_address = Address(
                    street1=reporting_owner_values.get('BUSINESS ADDRESS').get('STREET 1'),
                    street2=reporting_owner_values.get('BUSINESS ADDRESS').get('STREET 2'),
                    city=reporting_owner_values.get('BUSINESS ADDRESS').get('CITY'),
                    state_or_country=reporting_owner_values.get('BUSINESS ADDRESS').get('STATE'),
                    zipcode=reporting_owner_values.get('BUSINESS ADDRESS').get('ZIP'),
                ) if 'BUSINESS ADDRESS' in reporting_owner_values else None

                # Mailing Address
                mailing_address = Address(
                    street1=reporting_owner_values.get('MAIL ADDRESS').get('STREET 1'),
                    street2=reporting_owner_values.get('MAIL ADDRESS').get('STREET 2'),
                    city=reporting_owner_values.get('MAIL ADDRESS').get('CITY'),
                    state_or_country=reporting_owner_values.get('MAIL ADDRESS').get('STATE'),
                    zipcode=reporting_owner_values.get('MAIL ADDRESS').get('ZIP'),
                ) if 'MAIL ADDRESS' in reporting_owner_values else None

                # Now create the reporting owner
                reporting_owner = ReportingOwner(
                    owner=owner,
                    company_information=company_information,
                    filing_information=filing_information,
                    business_address=business_address,
                    mailing_address=mailing_address
                )
            reporting_owners.append(reporting_owner)

        # Issuer
        issuers = []
        for issuer_values in data.get('ISSUER', []):
            issuer = Issuer(
                company_information=CompanyInformation(
                    name=issuer_values.get('COMPANY DATA').get('COMPANY CONFORMED NAME'),
                    cik=issuer_values.get('COMPANY DATA').get('CENTRAL INDEX KEY'),
                    sic=issuer_values.get('COMPANY DATA').get('STANDARD INDUSTRIAL CLASSIFICATION'),
                    irs_number=issuer_values.get('COMPANY DATA').get('IRS NUMBER'),
                    state_of_incorporation=issuer_values.get('COMPANY DATA').get('STATE OF INCORPORATION'),
                    fiscal_year_end=issuer_values.get('COMPANY DATA').get('FISCAL YEAR END')
                ) if 'COMPANY DATA' in issuer_values else None,
                business_address=Address(
                    street1=issuer_values.get('BUSINESS ADDRESS').get('STREET 1'),
                    street2=issuer_values.get('BUSINESS ADDRESS').get('STREET 2'),
                    city=issuer_values.get('BUSINESS ADDRESS').get('CITY'),
                    state_or_country=issuer_values.get('BUSINESS ADDRESS').get('STATE'),
                    zipcode=issuer_values.get('BUSINESS ADDRESS').get('ZIP'),
                ) if 'BUSINESS ADDRESS' in issuer_values else None,
                mailing_address=Address(
                    street1=issuer_values.get('MAIL ADDRESS').get('STREET 1'),
                    street2=issuer_values.get('MAIL ADDRESS').get('STREET 2'),
                    city=issuer_values.get('MAIL ADDRESS').get('CITY'),
                    state_or_country=issuer_values.get('MAIL ADDRESS').get('STATE'),
                    zipcode=issuer_values.get('MAIL ADDRESS').get('ZIP'),
                ) if 'MAIL ADDRESS' in issuer_values else None
            )
            issuers.append(issuer)

        subject_companies = []
        for subject_company_values in data.get('SUBJECT COMPANY', []):
            subject_company = SubjectCompany(
                company_information=CompanyInformation(
                    name=subject_company_values.get('COMPANY DATA').get('COMPANY CONFORMED NAME'),
                    cik=subject_company_values.get('COMPANY DATA').get('CENTRAL INDEX KEY'),
                    sic=subject_company_values.get('COMPANY DATA').get('STANDARD INDUSTRIAL CLASSIFICATION'),
                    irs_number=subject_company_values.get('COMPANY DATA').get('IRS NUMBER'),
                    state_of_incorporation=subject_company_values.get('COMPANY DATA').get('STATE OF INCORPORATION'),
                    fiscal_year_end=subject_company_values.get('COMPANY DATA').get('FISCAL YEAR END')
                ) if 'COMPANY DATA' in subject_company_values else None,
                filing_information=FilingInformation(
                    form=subject_company_values.get('FILING VALUES').get('FORM TYPE'),
                    sec_act=subject_company_values.get('FILING VALUES').get('SEC ACT'),
                    file_number=subject_company_values.get('FILING VALUES').get('SEC FILE NUMBER'),
                    film_number=subject_company_values.get('FILING VALUES').get('FILM NUMBER')
                ) if 'FILING VALUES' in subject_company_values else None,
                business_address=Address(
                    street1=subject_company_values.get('BUSINESS ADDRESS').get('STREET 1'),

                    street2=subject_company_values.get('BUSINESS ADDRESS').get('STREET 2'),
                    city=subject_company_values.get('BUSINESS ADDRESS').get('CITY'),
                    state_or_country=subject_company_values.get('BUSINESS ADDRESS').get('STATE'),
                    zipcode=subject_company_values.get('BUSINESS ADDRESS').get('ZIP'),
                ) if 'BUSINESS ADDRESS' in subject_company_values else None,
                mailing_address=Address(
                    street1=subject_company_values.get('MAIL ADDRESS').get('STREET 1'),
                    street2=subject_company_values.get('MAIL ADDRESS').get('STREET 2'),
                    city=subject_company_values.get('MAIL ADDRESS').get('CITY'),
                    state_or_country=subject_company_values.get('MAIL ADDRESS').get('STATE'),
                    zipcode=subject_company_values.get('MAIL ADDRESS').get('ZIP'),
                ) if 'MAIL ADDRESS' in subject_company_values else None,
                former_company_names=[FormerCompany(date_of_change=record.get('DATE OF NAME CHANGE'),
                                                    name=record.get('FORMER CONFORMED NAME'))
                                      for record in subject_company_values['FORMER COMPANY']
                                      ]
                if 'FORMER COMPANY' in subject_company_values else None
            )
            subject_companies.append(subject_company)
            
        # Convert all lists to strings
        for key, value in data.items():
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                data[key] = ', '.join(value)

        # Create a dict of the values in data that are not nested dicts
        filing_metadata = {key: value
                           for key, value in data.items()
                           if isinstance(value, str) and value}

        # The header text contains <ACCEPTANCE-DATETIME>20230612172243. Replace with the formatted date
        header_text = re.sub(r'<ACCEPTANCE-DATETIME>(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})',
                             r'ACCEPTANCE-DATETIME:            \1-\2-\3 \4:\5:\6', header_text)

        # Remove empty lines from header_text
        header_text = '\n'.join([line for line in header_text.split('\n') if line.strip()])

        # Create the Header object
        return cls(
            text=header_text,
            filing_metadata=filing_metadata,
            filers=filers,
            reporting_owners=reporting_owners,
            issuers=issuers,
            subject_companies=subject_companies
        )

    def __rich__(self):

        # Filing Metadata
        metadata_table = self.filing_metadata.__rich__()

        # Keep a list of renderables for rich
        renderables = [metadata_table]

        # SUBJECT COMPANY
        for subject_company in self.subject_companies:
            renderables.append(subject_company.__rich__())

        # FILER
        for filer in self.filers:
            renderables.append(filer.__rich__())

        # REPORTING OWNER
        for reporting_owner in self.reporting_owners:
            renderables.append(reporting_owner.__rich__())

        # ISSUER
        for issuer in self.issuers:
            renderables.append(issuer.__rich__())
        return Panel(
            Group(
                *renderables
            ),
            title=Text(describe_form(self.form), style="bold"),
            subtitle=Text(f"Form {self.form}")
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

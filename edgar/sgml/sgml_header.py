import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from rich import box
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Column, Table
from rich.text import Text

from edgar._party import Address, get_addresses_as_columns
from edgar.core import log
from edgar.formatting import datefmt, reverse_name
from edgar.reference import describe_form, states
from edgar.richtools import repr_rich

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


def collect_repeated_tags(text: str, tag_name: str) -> list[str]:
    """
    Collects values from sequences of unclosed tags with the same name.
    Example:
        <ITEMS>06b
        <ITEMS>3C
        Returns: ['06b', '3C']
    """
    pattern = f"<{tag_name}>([^\n<]+)"  # Match tag and capture until newline or next tag
    return [match.group(1).strip() for match in re.finditer(pattern, text, re.MULTILINE)]


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

    def update(self, property:str, value:str):
        self.metadata[property] = value

    @property
    def num_documents(self):
        count = self.metadata.get("PUBLIC DOCUMENT COUNT")
        if count and count.isdigit():
            return int(count)

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

    def __str__(self):
        return f"{self.company_information.name} [{self.company_information.cik}]"

    def __rich__(self):
        filer_renderables = [self.company_information]

        # Addresses
        if self.business_address or self.mailing_address:
            filer_renderables.append(
                get_addresses_as_columns(business_address=self.business_address, mailing_address=self.mailing_address))

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
            reporting_owner_renderables.append(
                get_addresses_as_columns(business_address=self.business_address, mailing_address=self.mailing_address))

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
            subject_company_renderables.append(get_addresses_as_columns(business_address=self.business_address,
                                                                        mailing_address=self.mailing_address))

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
    former_company_names: Optional[List[FormerCompany]] = None

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
            issuer_renderables.append(
                get_addresses_as_columns(business_address=self.business_address, mailing_address=self.mailing_address))

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
                 issuer: Issuer = None,
                 subject_companies: List[SubjectCompany] = None):
        self.text: str = text
        self.filing_metadata: FilingMetadata = FilingMetadata(filing_metadata)
        self.filers: List[Filer] = filers
        self.reporting_owners: List[ReportingOwner] = reporting_owners
        self.issuer: Issuer = issuer
        self.subject_companies: List[SubjectCompany] = subject_companies

    def is_empty(self):
        return not self.filing_metadata.metadata

    @property
    def accession_number(self):
        return self.filing_metadata.get("ACCESSION NUMBER")

    @property
    def cik(self):
        cik = self.filing_metadata.get("CIK")
        if cik:
            return int(cik)
        # Get from the filers
        if self.filers and len(self.filers) > 0:
            company = self.filers[0].company_information
            if company and company.cik:
                return int(company.cik)
        return cik

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
    def parse_submission_format_header(cls, parsed_data: Dict[str, Any]):
        """Parse SUBMISSION format into same data structure"""

        # Transform SUBMISSION format into expected structure
        filers = []
        reporting_owners = []
        subject_companies = []

        metadata = {
            "ACCESSION NUMBER": parsed_data.get("ACCESSION-NUMBER"),
            "CONFORMED SUBMISSION TYPE": parsed_data.get("TYPE"),
            "FILED AS OF DATE": parsed_data.get("FILING-DATE"),
            "DATE AS OF CHANGE": parsed_data.get("DATE-OF-FILING-DATE-CHANGE"),
            "EFFECTIVE DATE": parsed_data.get("EFFECTIVENESS-DATE"),
        }

        # Handle FILER section
        for filer_data in parsed_data.get('FILER', []):
            # Create Filer object from COMPANY-DATA
            company_data = filer_data.get('COMPANY-DATA', {})
            company_info = CompanyInformation(
                name=company_data.get('CONFORMED-NAME'),
                cik=company_data.get('CIK'),
                sic=company_data.get('STANDARD INDUSTRIAL CLASSIFICATION'),
                irs_number=company_data.get('IRS NUMBER'),
                state_of_incorporation=company_data.get('STATE-OF-INCORPORATION'),
                fiscal_year_end=company_data.get('FISCAL-YEAR-END')
            )

            # Create Filing Information from FILING-VALUES
            filing_values = filer_data.get('FILING-VALUES', {})
            filing_info = FilingInformation(
                form=filing_values.get('FORM-TYPE'),
                file_number=filing_values.get('FILE-NUMBER'),
                sec_act=filing_values.get('ACT'),
                film_number=filing_values.get('FILM-NUMBER')
            )

            # Create Address objects
            business_address = Address.from_dict(
                filer_data.get('BUSINESS-ADDRESS', {})) if 'BUSINESS-ADDRESS' in filer_data else None
            mail_address = Address.from_dict(
                filer_data.get('MAIL-ADDRESS', {})) if 'MAIL-ADDRESS' in filer_data else None

            # Create Filer object
            filer = Filer(
                company_information=company_info,
                filing_information=filing_info,
                business_address=business_address,
                mailing_address=mail_address
            )
            filers.append(filer)
        # Handle REPORTING-OWNER section
        for reporting_owner_data in parsed_data.get('REPORTING-OWNER', []):

            # Create Owner object
            owner = Owner(
                name=reporting_owner_data.get('OWNER-DATA', {}).get('CONFORMED-NAME'),
                cik=reporting_owner_data.get('OWNER-DATA', {}).get('CIK')
            )

            # Create Company Information object
            company_data = reporting_owner_data.get('COMPANY-DATA', {})
            company_info = CompanyInformation(
                name=company_data.get('CONFORMED-NAME'),
                cik=company_data.get('CIK'),
                sic=company_data.get('STANDARD-INDUSTRIAL-CLASSIFICATION'),
                irs_number=company_data.get('IRS-NUMBER'),
                state_of_incorporation=company_data.get('STATE-OF-INCORPORATION'),
                fiscal_year_end=company_data.get('FISCAL-YEAR-END')
            )

            # Create Filing Information object
            filing_values = reporting_owner_data.get('FILING-VALUES', {})
            filing_info = FilingInformation(
                form=filing_values.get('FORM-TYPE'),
                file_number=filing_values.get('FILE-NUMBER'),
                sec_act=filing_values.get('ACT'),
                film_number=filing_values.get('FILM-NUMBER')
            )

            business_address_record = reporting_owner_data.get('BUSINESS-ADDRESS')
            if business_address_record:
                # Create Address objects
                business_address = Address(
                    street1=business_address_record.get('STREET1'),
                    city=business_address_record.get('CITY'),
                    state_or_country=business_address_record.get('STATE'),
                    zipcode=business_address_record.get('ZIP')
                )
            else:
                business_address = None

            # The mailing address
            mail_address_record = reporting_owner_data.get('MAIL-ADDRESS')
            if mail_address_record:
                mail_address = Address(
                    street1=reporting_owner_data.get('MAIL-ADDRESS', {}).get('STREET1'),
                    city=reporting_owner_data.get('MAIL-ADDRESS', {}).get('CITY'),
                    state_or_country=reporting_owner_data.get('MAIL-ADDRESS', {}).get('STATE'),
                    zipcode=reporting_owner_data.get('MAIL-ADDRESS', {}).get('ZIP')
                )
            else:
                mail_address = None

            # Create Reporting Owner object
            reporting_owner = ReportingOwner(
                owner=owner,
                company_information=company_info,
                filing_information=filing_info,
                business_address=business_address,
                mailing_address=mail_address
            )
            reporting_owners.append(reporting_owner)

        # Handle ISSUER section
        issuer_record = parsed_data.get('ISSUER', [])
        if issuer_record:
            # Create Address objects
            business_address = Address.from_dict(
                issuer_record.get('BUSINESS-ADDRESS', {})) if 'BUSINESS-ADDRESS' in issuer_record else None
            mail_address = Address.from_dict(
                issuer_record.get('MAIL-ADDRESS', {})) if 'MAIL-ADDRESS' in issuer_record else None

            # Former Company Names
            former_company_names = []
            for former_company in issuer_record.get('FORMER-COMPANY', []):
                former_company_names.append(FormerCompany(
                    name=former_company.get('FORMER-CONFORMED-NAME'),
                    date_of_change=former_company.get('DATE-CHANGED')
                ))
            issuer = Issuer(
                company_information=CompanyInformation(
                    name=issuer_record.get('COMPANY-DATA', {}).get('CONFORMED-NAME'),
                    cik=issuer_record.get('COMPANY-DATA', {}).get('CIK'),
                    sic=issuer_record.get('COMPANY-DATA', {}).get('STANDARD-INDUSTRIAL-CLASSIFICATION'),
                    irs_number=issuer_record.get('COMPANY-DATA', {}).get('IRS-NUMBER'),
                    state_of_incorporation=issuer_record.get('COMPANY-DATA', {}).get('STATE-OF-INCORPORATION'),
                    fiscal_year_end=issuer_record.get('COMPANY-DATA', {}).get('FISCAL-YEAR-END')
                ),
                business_address=business_address,
                mailing_address=mail_address,
                former_company_names=former_company_names
            )

        else:
            issuer = None

        # Handle SUBJECT-COMPANY section
        for subject_company_data in parsed_data.get('SUBJECT-COMPANY', []):
            # Create Company Information object
            company_data = subject_company_data.get('COMPANY-DATA', {})
            company_info = CompanyInformation(
                name=company_data.get('CONFORMED-NAME'),
                cik=company_data.get('CIK'),
                sic=company_data.get('STANDARD-INDUSTRIAL-CLASSIFICATION'),
                irs_number=company_data.get('IRS-NUMBER'),
                state_of_incorporation=company_data.get('STATE-OF-INCORPORATION'),
                fiscal_year_end=company_data.get('FISCAL-YEAR-END')
            )

            # Create Filing Information object
            filing_values = subject_company_data.get('FILING-VALUES', {})
            filing_info = FilingInformation(
                form=filing_values.get('FORM-TYPE'),
                file_number=filing_values.get('FILE-NUMBER'),
                sec_act=filing_values.get('ACT'),
                film_number=filing_values.get('FILM-NUMBER')
            )

            business_address_record = subject_company_data.get('BUSINESS-ADDRESS')
            if business_address_record:
                # Create Address objects
                business_address = Address(
                    street1=business_address_record.get('STREET1'),
                    city=business_address_record.get('CITY'),
                    state_or_country=business_address_record.get('STATE'),
                    zipcode=business_address_record.get('ZIP')
                )
            else:
                business_address = None

            # The mailing address
            mail_address_record = subject_company_data.get('MAIL-ADDRESS')
            if mail_address_record:
                mail_address = Address(
                    street1=subject_company_data.get('MAIL-ADDRESS', {}).get('STREET1'),
                    city=subject_company_data.get('MAIL-ADDRESS', {}).get('CITY'),
                    state_or_country=subject_company_data.get('MAIL-ADDRESS', {}).get('STATE'),
                    zipcode=subject_company_data.get('MAIL-ADDRESS', {}).get('ZIP')
                )
            else:
                mail_address = None

            # Former Company Names
            former_company_names = []
            for former_company in subject_company_data.get('FORMER-COMPANY', []):
                former_company_names.append(FormerCompany(
                    name=former_company.get('FORMER-CONFORMED-NAME'),
                    date_of_change=former_company.get('DATE-CHANGED')
                ))

            # Create Subject Company object
            subject_company = SubjectCompany(
                company_information=company_info,
                filing_information=filing_info,
                business_address=business_address,
                mailing_address=mail_address,
                former_company_names=former_company_names
            )
            subject_companies.append(subject_company)

        return cls(
            text='header_text',
            filing_metadata=metadata,
            filers=filers,
            reporting_owners=reporting_owners,
            issuer=issuer,
            subject_companies=subject_companies
        )

    @staticmethod
    def _is_valid_sgml_tag(line: str) -> bool:
        """
        Check if line contains a valid SGML header tag (not HTML/XBRL content).

        SGML header tags are uppercase with no namespace prefixes.
        HTML/XBRL tags often have lowercase letters or namespace prefixes like 'ix:'.

        Args:
            line: The line to check

        Returns:
            bool: True if line contains a valid SGML tag, False otherwise
        """
        stripped = line.strip()
        if not stripped.startswith('<'):
            return False

        # Find the end of the tag
        tag_end = stripped.find('>')
        if tag_end == -1:
            return False

        # Extract tag name (without the < >)
        tag = stripped[1:tag_end]

        # Skip closing tags
        if tag.startswith('/'):
            return False

        # SGML header tags characteristics:
        # 1. No namespace prefixes (no ':' character)
        # 2. Uppercase letters, numbers, and hyphens only
        # 3. Should not contain attributes or spaces
        if ':' in tag or ' ' in tag:
            return False

        # Check if tag is uppercase (SGML convention)
        if tag != tag.upper():
            return False

        # Additional check: Should contain only letters, numbers, and hyphens
        import re
        if not re.match(r'^[A-Z0-9\-]+$', tag):
            return False

        return True

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

        # In case there are double newlines, replace them with a single newline
        header_text = header_text.replace('\n\n', '\n')

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
                    if isinstance(data[current_header], list):
                        data[current_header].append({})
            else:
                if line.strip().startswith("<"):
                    # Only process valid SGML header tags, skip HTML/XBRL content
                    if not cls._is_valid_sgml_tag(line):
                        continue

                    # The line looks like this <KEY>VALUE
                    # Handle lines with multiple '>' characters (e.g., XBRL inline content)
                    split_parts = line.split('>', 1)  # Split only on first '>' character
                    if len(split_parts) >= 2:
                        key, value = split_parts[0], split_parts[1]
                        # Strip the leading '<' from the key
                        key = key[1:]
                    else:
                        # Skip malformed lines that don't have a '>' character
                        continue

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
                            subheader_obj = data[current_header][-1][current_subheader][-1]
                            subheader_obj[key.strip()] = value
                        else:
                            try:
                                data[current_header][-1][current_subheader][key.strip()] = value
                            except KeyError:
                                # Some filings from the 2000's have an issue with malformed headers
                                log.warning("Subheader '%s' not found in header '%s'", current_subheader, current_header)

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
                    from edgar.entity import Entity
                    entity: Entity = Entity(cik)
                    if entity and not entity.data.is_company:
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
        issuer_data = data.get('ISSUER')
        # This will be a list but we only expect one record
        issuer_record = issuer_data[0] if issuer_data else None
        issuer = Issuer(
                company_information=CompanyInformation(
                    name=issuer_record.get('COMPANY DATA').get('COMPANY CONFORMED NAME'),
                    cik=issuer_record.get('COMPANY DATA').get('CENTRAL INDEX KEY'),
                    sic=issuer_record.get('COMPANY DATA').get('STANDARD INDUSTRIAL CLASSIFICATION'),
                    irs_number=issuer_record.get('COMPANY DATA').get('IRS NUMBER'),
                    state_of_incorporation=issuer_record.get('COMPANY DATA').get('STATE OF INCORPORATION'),
                    fiscal_year_end=issuer_record.get('COMPANY DATA').get('FISCAL YEAR END')
                ) if 'COMPANY DATA' in issuer_record else None,
                business_address=Address(
                    street1=issuer_record.get('BUSINESS ADDRESS').get('STREET 1'),
                    street2=issuer_record.get('BUSINESS ADDRESS').get('STREET 2'),
                    city=issuer_record.get('BUSINESS ADDRESS').get('CITY'),
                    state_or_country=issuer_record.get('BUSINESS ADDRESS').get('STATE'),
                    zipcode=issuer_record.get('BUSINESS ADDRESS').get('ZIP'),
                ) if 'BUSINESS ADDRESS' in issuer_record else None,
                mailing_address=Address(
                    street1=issuer_record.get('MAIL ADDRESS').get('STREET 1'),
                    street2=issuer_record.get('MAIL ADDRESS').get('STREET 2'),
                    city=issuer_record.get('MAIL ADDRESS').get('CITY'),
                    state_or_country=issuer_record.get('MAIL ADDRESS').get('STATE'),
                    zipcode=issuer_record.get('MAIL ADDRESS').get('ZIP'),
                ) if 'MAIL ADDRESS' in issuer_record else None
            ) if issuer_record else None

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
            issuer=issuer,
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
        if self.issuer:
            renderables.append(self.issuer.__rich__())
        return Panel(
            Group(
                *renderables
            ),
            title=Text(describe_form(self.form), style="bold"),
            subtitle=Text(f"Form {self.form}")
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

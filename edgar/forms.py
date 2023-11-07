import re
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd
from bs4 import BeautifulSoup
from rich.console import Group, Text
from rich.markdown import Markdown
from rich.panel import Panel

from edgar._markdown import markdown_to_rich
from edgar._rich import df_to_rich_table, repr_rich
from edgar.core import download_text, http_client, sec_dot_gov
from edgar.financials import Financials

__all__ = [
    'SecForms',
    'list_forms',
    'FUND_FORMS',
    'EightK',
    'TenK',
    'TenQ'
]

FUND_FORMS = ["NPORT-P", "NPORT-EX"]


@lru_cache(maxsize=1)
def list_forms():
    forms_html = download_text('https://www.sec.gov/forms', http_client())
    soup = BeautifulSoup(forms_html, features="lxml")
    data_table = soup.find("table")
    tbody = data_table.find("tbody")

    rows = []
    for tr in tbody.find_all('tr'):
        cells = tr.find_all('td')
        rows.append({"Form": cells[0].text.replace("Number:", "").strip(),
                     "Description": cells[1].text.replace("Description:", "").strip(),
                     "Url": f"{sec_dot_gov}{cells[1].find('a').attrs['href']}" if cells[1].find('a') else "",
                     "LastUpdated": cells[2].text.replace("Last Updated:", "").strip(),
                     "SECNumber": cells[3].text.replace("SEC Number:", "").strip(),
                     "Topics": cells[4].text.replace("Topic(s):", "").strip()
                     })
    return SecForms(pd.DataFrame(rows))


@dataclass(frozen=True)
class SecForm:
    form: str
    description: str
    url: str
    sec_number: str
    topics: str

    def open(self):
        import webbrowser
        webbrowser.open(self.url)

    def __str__(self):
        return f"Form {self.form}: {self.description}"

    def __rich__(self):
        return Group(
            Text(f"Form {self.form}: {self.description}"),
            df_to_rich_table(
                pd.DataFrame([{"Topics": self.topics, "SEC Number": self.sec_number, "Url": self.url}])
                .set_index("Topics")
                , index_name="Topics")
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class SecForms:

    def __init__(self,
                 data: pd.DataFrame):
        self.data = data

    def get_form(self, form: str):
        row = self.data.query(f"Form=='{form}'")
        if len(row) == 1:
            return SecForm(
                form=row.Form.item(),
                description=row.Description.item(),
                sec_number=row.SECNumber.item(),
                url=row.Url.item(),
                topics=row.Topics.item()
            )

    @classmethod
    def load(cls):
        return SecForms(list_forms())

    def __getitem__(self, item):
        return self.get_form(item)

    def __len__(self):
        return len(self.data)

    def summary(self) -> pd.DataFrame:
        return self.data[['Form', 'Description', 'Topics']]

    def __rich__(self):
        return Group(
            Text("SEC Forms List"),
            df_to_rich_table(self.summary().set_index("Form"), index_name="Form", max_rows=200)
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


def find_section(pattern, sections):
    for index, section in enumerate(sections):
        if re.search(pattern, section, re.IGNORECASE):
            return index, section


@dataclass(frozen=True)
class FilingItem:
    item_num: str
    text: str

    def __str__(self):
        return f"""
        ## {self.item_num}
        {self.text}
        """

    def __rich__(self):
        return Markdown(str(self))


class CompanyReport:

    def __init__(self, filing):
        self._filing = filing

    @property
    def form(self):
        return self._filing.form

    @property
    def company(self):
        return self._filing.company

    @property
    def income_statement(self):
        return self.financials.income_statement if self.financials else None

    @property
    def balance_sheet(self):
        return self.financials.balance_sheet if self.financials else None

    @property
    def cash_flow_statement(self):
        return self.financials.cash_flow_statement if self.financials else None

    @property
    @lru_cache(1)
    def financials(self):
        xbrl = self._filing.xbrl()
        if xbrl:
            return Financials.from_gaap(xbrl.gaap)

    def __rich__(self):
        return Panel(
            Group(
            self._filing.__rich__(),
            self.financials or Text("No financial data available")
            )
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class TenK(CompanyReport):

    def __init__(self, filing):
        assert filing.form in ['10-K', '10-K/A'], f"This form should be a 10-K but was {filing.form}"
        super().__init__(filing)

    def __str__(self):
        return f"""TenK('{self.company}')"""

class TenQ(CompanyReport):

    def __init__(self, filing):
        assert filing.form in ['10-Q', '10-Q/A'], f"This form should be a 10-Q but was {filing.form}"
        super().__init__(filing)

    def __str__(self):
        return f"""TenQ('{self.company}')"""



class EightK:

    def __init__(self, filing):
        assert filing.form in ['8-K', '8-K/A'], f"This form should be an 8-K but was {filing.form}"
        self._filing = filing
        self.items = [
            FilingItem(item_num, item_text)
            for item_num, item_text
            in EightK.find_items(filing)
        ]

    @property
    def filing_date(self):
        return self._filing.filing_date

    @property
    def form(self):
        return self._filing.form

    @property
    def company(self):
        return self._filing.company

    def to_markdown(self):
        return '\n'.join([str(item) for item in self.items])

    def __rich__(self):
        return Panel(
            Group(
                self._filing.__rich__(),
                markdown_to_rich(self.to_markdown())
            )
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    @staticmethod
    def find_items(filing):
        sections = filing.sections()
        emerging_section = find_section(r'If\W+an\W+emerging\W+growth\W+company', sections)
        # If not found then start at top
        emerging_loc = emerging_section[0] if emerging_section else 0

        signature = find_section("SIGNATURES?", sections)
        if not signature:
            signature = find_section(r"this\W+report\W+to\W+be\W+signed\W+on\W+its\W+behalf\W+by\W+the\W+undersigned",
                                     sections)
        signature_loc = signature[0]

        current_item_num = None
        current_item = ""
        for section in sections[emerging_loc + 1: signature_loc]:
            for line in section.split("\n"):
                match = re.match(r"\W*(Item\s\d.\d{2})\.?(.*)?", line, re.IGNORECASE)
                if match:
                    if current_item:
                        yield current_item_num, current_item.strip()
                    current_item_num, header = match.groups()
                    current_item = header.strip() + "\n" if header else ""
                else:
                    if current_item_num is not None:
                        current_item += line + "\n"
        yield current_item_num, current_item.strip()


import re
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd
from bs4 import BeautifulSoup
from rich.console import Group, Text
from rich.markdown import Markdown

from edgar.richtools import df_to_rich_table, repr_rich
from edgar.core import sec_dot_gov
from edgar.httprequests import download_file

__all__ = [
    'SecForms',
    'list_forms',
    'FUND_FORMS'
]

FUND_FORMS = ["NPORT-P", "NPORT-EX"]


@lru_cache(maxsize=1)
def list_forms():
    rows = []
    for page in range(7):
        forms_html = download_file(f'https://www.sec.gov/forms?page={page}')
        soup = BeautifulSoup(forms_html, features="lxml")
        data_table = soup.find("table")
        tbody = data_table.find("tbody")

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

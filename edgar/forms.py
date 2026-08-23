import re
from dataclasses import dataclass
from functools import lru_cache

import lxml.html
import pandas as pd
from rich.console import Group, Text
from rich.markdown import Markdown

from edgar.config import SEC_BASE_URL
from edgar.documents.utils.html_utils import create_lxml_parser
from edgar.httprequests import download_file
from edgar.richtools import df_to_rich_table, repr_rich

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
        # This page was already parsed by lxml -- bs4 was only a wrapper over
        # it (features="lxml") -- so the tree is the same one, minus a layer.
        # download_file returns bytes for these pages, but str elsewhere and in
        # tests; bs4 took either. Feeding bytes is also what keeps an encoding
        # declaration from raising, so normalise toward bytes rather than str.
        if isinstance(forms_html, str):
            forms_html = forms_html.encode("utf-8", errors="replace")
        root = lxml.html.fromstring(forms_html, parser=create_lxml_parser())
        # descendant-or-self, not .//: lxml roots a document trimmed to a
        # single <table> AT that table, so a descendant-only search finds
        # nothing. bs4's find() matched it either way.
        data_table = root.xpath("descendant-or-self::table")[0]
        tbody = data_table.xpath("descendant-or-self::tbody")[0]

        for tr in tbody.xpath('.//tr'):
            cells = tr.xpath('.//td')
            # text_content(), not .text: lxml's .text is the node's own leading
            # text only, where bs4's .text was every descendant's.
            link = cells[1].find('.//a')
            rows.append({"Form": cells[0].text_content().replace("Number:", "").strip(),
                         "Description": cells[1].text_content().replace("Description:", "").strip(),
                         "Url": f"{SEC_BASE_URL}{link.get('href')}" if link is not None else "",
                         "LastUpdated": cells[2].text_content().replace("Last Updated:", "").strip(),
                         "SECNumber": cells[3].text_content().replace("SEC Number:", "").strip(),
                         "Topics": cells[4].text_content().replace("Topic(s):", "").strip()
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
        # list_forms() already returns a SecForms; wrapping it again put a SecForms
        # in .data where a DataFrame belongs.
        return list_forms()

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

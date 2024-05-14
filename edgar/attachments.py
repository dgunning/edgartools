import re
from typing import List, Optional

from bs4 import BeautifulSoup
from pydantic import BaseModel, HttpUrl

from edgar.core import sec_dot_gov
from edgar.httprequests import get_with_retry_async


class Attachment(BaseModel):
    sequence_number: int
    description: str
    url: HttpUrl
    document_type: str
    size: Optional[int]


def sec_document_url(attachment_url: str) -> str:
    # Remove "ix?doc=/" or "ix.xhtml?doc=/" from the filing url
    attachment_url = re.sub(r"ix(\.xhtml)?\?doc=/", "", attachment_url)
    return f"{sec_dot_gov}{attachment_url}"


class Attachments:

    def __init__(self, document_files: List[Attachment],
                 data_files: List[Attachment]):
        self.documents = document_files
        self.data_files = data_files

    @classmethod
    async def load(cls, url: HttpUrl):
        response = await get_with_retry_async(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        tables = soup.find_all('table', class_='tableFile')

        def parse_table(table):
            rows = table.find_all('tr')[1:]  # Skip header row
            documents = []
            for row in rows:
                cols = row.find_all('td')
                if len(cols) == 5:  # Ensure row has all required columns

                    sequence_number = int(cols[0].text.strip() or 10000)
                    description = cols[1].text.strip()
                    document_path = sec_document_url(cols[2].a['href'].strip())
                    document_type = cols[3].text.strip()
                    size = cols[4].text.strip()
                    size = int(size) if size.isdigit() else None

                    doc = Attachment(
                        sequence_number=sequence_number,
                        description=description,
                        url=document_path,
                        document_type=document_type,
                        size=size
                    )
                    documents.append(doc)
            return documents

        document_files = parse_table(tables[0]) if tables else []
        data_files = parse_table(tables[1]) if len(tables) > 1 else []

        return cls(document_files, data_files)

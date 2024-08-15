import http.server
import os
import re
import signal
import socketserver
import tempfile
import time
import webbrowser
import zipfile
from functools import lru_cache
from pathlib import Path
from threading import Thread
from typing import List, Optional, Tuple
from typing import Union

from bs4 import BeautifulSoup
from pydantic import BaseModel, field_validator
from rich import box
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table, Column
from rich.text import Text

from edgar.richtools import repr_rich
from edgar.core import sec_dot_gov, display_size, binary_extensions, text_extensions
from edgar.httprequests import get_with_retry, download_file, download_file_async

xbrl_document_types = ['XBRL INSTANCE DOCUMENT', 'XBRL INSTANCE FILE', 'EXTRACTED XBRL INSTANCE DOCUMENT']

__all__ = ['Attachment', 'Attachments', 'FilingHomepage', 'FilerInfo', 'AttachmentServer', 'sec_document_url']


def sec_document_url(attachment_url: str) -> str:
    # Remove "ix?doc=/" or "ix.xhtml?doc=/" from the filing url
    attachment_url = re.sub(r"ix(\.xhtml)?\?doc=/", "", attachment_url)
    return f"{sec_dot_gov}{attachment_url}"


class FilerInfo(BaseModel):
    company_name: str
    identification: str
    addresses: List[str]

    def __rich__(self):
        return Panel(
            Columns([self.identification, Text("   "), self.addresses[0], self.addresses[1]]),
            title=self.company_name
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class Attachment(BaseModel):
    """
    A class to represent an attachment in an SEC filing
    """
    sequence_number: str
    description: str
    document: str
    ixbrl: bool
    path: str
    document_type: str
    size: Optional[int]

    @property
    def url(self):
        return sec_document_url(self.path)

    @property
    def extension(self):
        """The actual extension of the filing document
         Usually one of .xml or .html or .pdf or .txt or .paper
         """
        return os.path.splitext(self.path)[1]

    @property
    def display_extension(self) -> str:
        """This is the extension displayed in the html e.g. "es220296680_4-davis.html"
        The actual extension would be "es220296680_4-davis.xml", that displays as html in the browser
        """
        return os.path.splitext(self.document)[1]

    @field_validator('sequence_number')
    def validate_sequence_number(cls, v):
        if not v.isdigit() and v != '':
            raise ValueError('sequence_number must be digits or an empty string')
        return v

    def is_text(self) -> bool:
        """Is this a text document"""
        return self.extension in text_extensions

    def is_binary(self) -> bool:
        """Is this a binary document"""
        return self.extension in binary_extensions

    @property
    def empty(self):
        """Some older filings have no document url. So effectively this attachment is empty"""
        return self.document is None or self.document.strip() == ''

    def download(self, path: Optional[Union[str, Path]] = None) -> Optional[Union[str, bytes]]:
        """
            Download the file to a specified path.
            If the path is not provided, return the downloaded content as text or bytes.
            If the path is a directory, the file is saved with its original name in that directory.
            If the path is a file, the file is saved with the given path name.
            """
        downloaded = download_file(self.url, as_text=self.is_text())
        if path is None:
            return downloaded

        # Ensure path is a Path object
        path = Path(path)

        # Determine if the path is a directory or a file
        if path.is_dir():
            file_path = path / self.document
        else:
            file_path = path

        # Save the file
        if isinstance(downloaded, bytes):
            file_path.write_bytes(downloaded)
        else:
            file_path.write_text(downloaded)

        return str(file_path)

    def __rich__(self):
        table = Table("Document", "Description", "Type", "Size", box=box.ROUNDED)
        table.add_row(self.document, self.description, self.document_type,
                      display_size(self.size))
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return repr_rich(self.__rich__())


class Attachments:
    """
    A class to represent the attachments of an SEC filing
    """

    def __init__(self,
                 document_files: List[Attachment],
                 data_files: Optional[List[Attachment]],
                 primary_documents: List[Attachment]):
        self.documents = document_files
        self.data_files = data_files
        self._attachments = document_files + (data_files or [])
        self.primary_documents = primary_documents

    def __getitem__(self, item: Union[int, str]):
        if isinstance(item, int):
            return self._attachments[item]
        elif isinstance(item, str):
            for doc in self._attachments:
                if doc.document == item:
                    return doc
        raise KeyError(f"Document not found: {item}")

    def get_by_sequence(self, sequence: Union[str, int]):
        for doc in self._attachments:
            if doc.sequence_number == str(sequence):
                return doc
        raise KeyError(f"Document not found: {sequence}")

    @property
    def primary_html_document(self) -> Optional[Attachment]:
        """Get the primary xml document on the filing"""
        for doc in self.primary_documents:
            if doc.display_extension == ".html" or doc.display_extension == '.htm':
                return doc
        # Shouldn't get here but just open the first document
        return self.primary_documents[0]

    @property
    def primary_xml_document(self) -> Optional[Attachment]:
        """Get the primary xml document on the filing"""
        for doc in self.primary_documents:
            if doc.display_extension == ".xml":
                return doc

    @property
    def text_document(self):
        for doc in reversed(self.documents):
            if doc.description == "Complete submission text file":
                return doc
        return None

    @property
    def exhibits(self):
        """
        Get all the exhibits in the filing.
        This is the primary document plus all the documents listed as EX-XX
        """
        primary_documents = [self.primary_html_document]
        exhibits_documents = self.query("re.match('EX-', document_type)", False).documents
        return Attachments(
            document_files=primary_documents + exhibits_documents, data_files=[], primary_documents=primary_documents)

    @property
    def graphics(self):
        return self.query("document_type=='GRAPHIC'")

    def query(self, query_str: str, include_data_files: bool = True):
        """
        Query attachments based on a simple query string.
        Supports conditions on 'document', 'description', and 'document_type'.
        Example query: "document.endswith('.htm') and 'RELEASE' in description and document_type in ['EX-99.1', 'EX-99', 'EX-99.01']"
        """
        allowed_attrs = {'document', 'description', 'document_type'}

        # Precompile regex for finding attributes and match patterns
        attr_regex = re.compile(rf"\b({'|'.join(allowed_attrs)})\b")
        match_regex = re.compile(r"re\.match\('(.*)', (\w+)\)")

        def safe_eval(attachment, query):
            # Replace attribute references with attachment attributes
            query = attr_regex.sub(lambda m: f"attachment.{m.group(0)}", query)

            # Handle regex match explicitly
            match = match_regex.search(query)
            if match:
                pattern, attr = match.groups()
                query = query.replace(f"re.match('{pattern}', {attr})",
                                      f"re.match(r'{pattern}', attachment.{attr})")

            return eval(query, {"re": re, "attachment": attachment})

        # Evaluate the query for documents and data files
        new_documents = [attachment for attachment in self.documents if safe_eval(attachment, query_str)]
        if include_data_files:
            new_data_files = [attachment for attachment in self.data_files if
                              safe_eval(attachment, query_str)] if self.data_files else None
        else:
            new_data_files = []

        return Attachments(document_files=new_documents, data_files=new_data_files,
                           primary_documents=self.primary_documents)

    @staticmethod
    async def _download_all_attachments(attachments: List[Attachment]):
        import asyncio
        return await asyncio.gather(
            *[download_file_async(attachment.url, as_text=attachment.is_text()) for attachment in attachments])

    def download(self, path: Union[str, Path], archive: bool = False):
        """
        Download all the attachments to a specified path.
        If the path is a directory, the file is saved with its original name in that directory.
        If the path is a file, the file is saved with the given path name.
        If archive is True, the attachments are saved in a zip file.
        path: str or Path - The path to save the attachments
        archive: bool (default False) - If True, save the attachments in a zip file
        """

        import asyncio
        loop = asyncio.get_event_loop()
        downloaded_files = loop.run_until_complete(Attachments._download_all_attachments(self._attachments))

        # Ensure path is a Path object
        path = Path(path)

        # If the path is a directory, save the files in that directory
        if path.is_dir():
            for attachment, downloaded in zip(self._attachments, downloaded_files):
                file_path = path / attachment.document
                if isinstance(downloaded, bytes):
                    file_path.write_bytes(downloaded)
                else:
                    file_path.write_text(downloaded, encoding='utf-8')

        # If the path is an archive file, save the files in that file
        else:
            if archive:
                with zipfile.ZipFile(path, 'w') as zipf:
                    for attachment, downloaded in zip(self._attachments, downloaded_files):
                        if isinstance(downloaded, bytes):
                            zipf.writestr(attachment.document, downloaded)
                        else:
                            zipf.writestr(attachment.document, downloaded.encode('utf-8'))
            else:
                raise ValueError("Path must be a directory or an archive file")

    def serve(self, port: int = 8000) -> Tuple[Thread, socketserver.TCPServer, str]:
        """
        Serve the attachment on a local server
        The server can be stopped using CTRL-C
        port: int (default 8000) - The port to serve the attachment
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self.download(temp_path)

            class Handler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=temp_dir, **kwargs)

            primary_html = os.path.basename(self.primary_html_document.path)

            url = f'http://localhost:{port}/{primary_html}'

            httpd = socketserver.TCPServer(("", port), Handler)

            def serve_forever():
                with httpd:
                    httpd.serve_forever()

            thread = Thread(target=serve_forever)
            thread.daemon = True
            thread.start()

            print(f"Serving at port {port}")
            # Wait for the server to start
            time.sleep(1)

            def signal_handler(sig, frame):
                print("Stopping server...")
                httpd.shutdown()
                thread.join()
                print("Server stopped.")

            signal.signal(signal.SIGINT, signal_handler)
            webbrowser.open(url)

            # Keep the main thread alive to handle signals
            while thread.is_alive():
                time.sleep(0.1)

            return thread, httpd, url

    def __len__(self):
        return len(self._attachments)

    def __iter__(self):
        self.n = 0
        return self

    def __next__(self):
        if self.n < len(self):
            _attachment = self._attachments[self.n]
            assert _attachment is not None

            self.n += 1
            return _attachment
        else:
            raise StopIteration

    def __rich__(self):

        # Document files
        document_table = Table('Seq', Column('Document'), 'Description', 'Type', 'Size',
                               title='Documents',
                               row_styles=["", "bold"],
                               box=box.SIMPLE)
        for index, _attachment in enumerate(self.documents):
            document_table.add_row(str(_attachment.sequence_number),
                                   _attachment.document,
                                   _attachment.description,
                                   _attachment.document_type,
                                   display_size(_attachment.size))
        document_panel = Panel(document_table, box=box.ROUNDED)

        renderables = [document_panel]

        # Data files
        if self.data_files:
            data_table = Table('Seq', Column('Document'), 'Description', 'Type', 'Size',
                               title='Data Files',
                               row_styles=["", "bold"],
                               box=box.SIMPLE)
            for index, _attachment in enumerate(self.data_files):
                data_table.add_row(str(_attachment.sequence_number),
                                   _attachment.document,
                                   _attachment.description,
                                   _attachment.document_type,
                                   display_size(_attachment.size))
            data_panel = Panel(data_table, box=box.ROUNDED)
            renderables.append(data_panel)

        return Group(*renderables)

    def __repr__(self):
        return repr_rich(self.__rich__())

    @classmethod
    def load(cls, soup: BeautifulSoup):
        """
        Load the attachments from the SEC filing home page
        """
        tables = soup.find_all('table', class_='tableFile')

        def parse_table(table, documents: bool):
            min_seq = None
            # The list of attachments which are primary. This is the first document in the filing
            # Plus additional document with the same sequence number
            primary_documents: List[Attachment] = []

            rows = table.find_all('tr')[1:]  # Skip header row
            attachments = []
            for index, row in enumerate(rows):
                cols = row.find_all('td')
                sequence_number = cols[0].text.strip().replace('\xa0', '-')

                description = cols[1].text.strip()
                # The document text is the text of the document link.
                document_text = cols[2].text.strip()
                document = document_text.split(' ')[0].strip()
                iXbrl = 'iXBRL' in document_text
                path = cols[2].a['href'].strip()
                document_type = cols[3].text.strip()
                size = cols[4].text.strip()

                try:
                    size = int(size)
                except ValueError:
                    size = None

                attachment = Attachment(
                    sequence_number=sequence_number,
                    description=description,
                    document=document,
                    ixbrl=iXbrl,
                    path=path,
                    document_type=document_type,
                    size=size
                )
                # Add the attachment to the list
                attachments.append(attachment)
                # If this is the first document, set it as the primary document
                if documents:
                    if min_seq is None:
                        min_seq = sequence_number
                    if sequence_number == min_seq:
                        primary_documents.append(attachment)
            return attachments, primary_documents

        if tables:
            document_files, primary_documents = parse_table(tables[0], documents=True)
        else:
            document_files, primary_documents = [], []

        if len(tables) > 1:
            data_files, _ = parse_table(tables[1], documents=False)
        else:
            data_files = None

        return cls(document_files, data_files, primary_documents)


class AttachmentServer:
    def __init__(self, attachments: Attachments, port: int = 8000):
        self.attachments = attachments
        self.port = port
        self.thread = None
        self.httpd = None
        self.url = None
        self.setup()

    def setup(self):
        temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(temp_dir.name)
        self.attachments.download(temp_path)

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=temp_dir.name, **kwargs)

        primary_html = os.path.basename(self.primary_html_document.path)

        self.url = f'http://localhost:{self.port}/{primary_html}'

        self.httpd = socketserver.TCPServer(("", self.port), Handler)

        def serve_forever():
            with self.httpd:
                self.httpd.serve_forever()

        self.thread = Thread(target=serve_forever)
        self.thread.daemon = True

        signal.signal(signal.SIGINT, self.signal_handler)

    def start(self):
        self.thread.start()
        print(f"Serving at port {self.port}")
        webbrowser.open(self.url)

        # Keep the main thread alive to handle signals
        while self.thread.is_alive():
            time.sleep(0.1)

    def stop(self):
        print("Stopping server...")
        self.httpd.shutdown()
        self.thread.join()
        print("Server stopped.")

    def signal_handler(self, sig, frame):
        self.stop()
        exit(0)  # Ensure the program exits



class FilingHomepage:

    def __init__(self,
                 url: str,
                 soup: BeautifulSoup,
                 attachments: Attachments):
        self.attachments = attachments
        self.url = url
        self._soup = soup

    def open(self):
        webbrowser.open(self.url)

    @property
    def documents(self):
        return self.attachments.documents

    @property
    def datafiles(self):
        return self.attachments.data_files

    @property
    def primary_html_document(self) -> Optional[Attachment]:
        """Get the primary xml document on the filing"""
        return self.attachments.primary_html_document

    @property
    def primary_xml_document(self) -> Optional[Attachment]:
        """Get the primary xml document on the filing"""
        return self.attachments.primary_xml_document

    @property
    def primary_documents(self):
        return self.attachments.primary_documents

    @property
    def text_document(self):
        return self.attachments.text_document

    @property
    def xbrl_document(self):
        """Find and return the xbrl document."""

        if self.datafiles is None:
            return None
        for datafile in reversed(self.datafiles):
            if datafile.description in xbrl_document_types:
                return datafile

    @lru_cache(maxsize=None)
    def get_filers(self):
        filer_divs = self._soup.find_all("div", id="filerDiv")
        filer_infos = []
        for filer_div in filer_divs:

            # Get the company name
            company_info_div = filer_div.find("div", class_="companyInfo")

            company_name_span = company_info_div.find("span", class_="companyName")
            company_name = (re.sub("\n", "", company_name_span.text.strip())
                            .replace("(see all company filings)", "").rstrip()
                            if company_name_span else "")

            # Get the identification information
            ident_info_div = company_info_div.find("p", class_="identInfo")

            # Replace <br> with newlines
            for br in ident_info_div.find_all("br"):
                br.replace_with("\n")

            identification = ident_info_div.text

            # Get the mailing information
            mailer_divs = filer_div.find_all("div", class_="mailer")
            # For each mailed_div.text remove multiple spaces after a newline

            addresses = [re.sub(r'\n\s+', '\n', mailer_div.text.strip())
                         for mailer_div in mailer_divs]

            # Create the filer info
            filer_info = FilerInfo(company_name=company_name, identification=identification, addresses=addresses)

            filer_infos.append(filer_info)

        return filer_infos

    @classmethod
    def load(cls, url: str):
        response = get_with_retry(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        attachments = Attachments.load(soup)
        return cls(url, soup, attachments)

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __rich__(self):

        return Panel(
            Group(
                self.attachments,
                Group(
                    *[filer_info.__rich__() for filer_info in self.get_filers()]
                )
            ))

import re
import zipfile
from collections import defaultdict
from functools import cached_property
from pathlib import Path
from typing import Iterator, Dict, DefaultDict
from typing import List, Union, Optional, Tuple

from edgar.attachments import Attachments, Attachment, get_document_type
from edgar.httprequests import stream_with_retry
from edgar.sgml.sgml_header import FilingHeader
from edgar.sgml.sgml_parser import SGMLParser, SGMLFormatType, SGMLDocument
from edgar.sgml.filing_summary import FilingSummary
from edgar.sgml.tools import is_xml


__all__ = ['iter_documents', 'list_documents', 'FilingSGML', 'FilingHeader']


def parse_document(document_str: str) -> SGMLDocument:
    """
    Parse a single SGML document section, maintaining raw content.
    """
    # Extract individual fields with separate patterns
    type_match = re.search(r'<TYPE>([^<\n]+)', document_str)
    sequence_match = re.search(r'<SEQUENCE>([^<\n]+)', document_str)
    filename_match = re.search(r'<FILENAME>([^<\n]+)', document_str)
    description_match = re.search(r'<DESCRIPTION>([^<\n]+)', document_str)

    return SGMLDocument(
        type=type_match.group(1).strip() if type_match else "",
        sequence=sequence_match.group(1).strip() if sequence_match else "",
        filename=filename_match.group(1).strip() if filename_match else "",
        description=description_match.group(1).strip() if description_match else "",
        raw_content=document_str
    )


def read_content(source: Union[str, Path]) -> Iterator[str]:
    """
    Read content from either a URL or file path, yielding lines as strings.
    Automatically handles gzip-compressed files with .gz extension.

    Args:
        source: Either a URL string or a file path

    Yields:
        str: Lines of content from the source

    Raises:
        TooManyRequestsError: If the server returns a 429 response
        FileNotFoundError: If the file path doesn't exist
        gzip.BadGzipFile: If the file is not a valid gzip file
    """
    if isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
        # Handle URL using stream_with_retry
        for response in stream_with_retry(source):
            # Process each line from the response and decode from bytes
            for line in response.iter_lines():
                if line is not None:
                    yield line + "\n"
    else:
        # Handle file path
        path = Path(source)
        
        # Check if the file is gzip-compressed
        if str(path).endswith('.gz'):
            import gzip
            with gzip.open(path, 'rt', encoding='utf-8', errors='replace') as file:
                yield from file
        else:
            # Regular file handling
            with path.open('r', encoding='utf-8', errors='replace') as file:
                yield from file


def read_content_as_string(source: Union[str, Path]) -> str:
    """
    Read content from either a URL or file path into a string.
    Uses existing read_content generator function.

    Args:
        source: Either a URL string or a file path

    Returns:
        str: Full content as string

    Raises:
        TooManyRequestsError: If the server returns a 429 response
        FileNotFoundError: If file path doesn't exist
    """
    # Convert lines from read_content to string
    lines = []
    for line in read_content(source):
        # Handle both string and bytes from response
        if isinstance(line, bytes):
            lines.append(line.decode('utf-8', errors='replace'))
        else:
            lines.append(line)

    return ''.join(lines)


def iter_documents(source: Union[str, Path]) -> Iterator[SGMLDocument]:
    """
    Stream SGML documents from either a URL or file path, yielding parsed documents.

    Args:
        source: Either a URL string or a file path (string or Path object)

    Yields:
        SGMLDocument objects containing the parsed content

    Raises:
        ValueError: If the source is invalid
        ConnectionError: If URL retrieval fails after retries
        FileNotFoundError: If the file path doesn't exist
    """
    try:
        content = ''.join(read_content(source))
        document_pattern = re.compile(r'<DOCUMENT>([\s\S]*?)</DOCUMENT>')

        for match in document_pattern.finditer(content):
            document = parse_document(match.group(1))
            if document:
                yield document

    except (ValueError, ConnectionError, FileNotFoundError) as e:
        raise type(e)(f"Error processing source {source}: {str(e)}")

def list_documents(source: Union[str, Path]) -> list[SGMLDocument]:
    """
    Convenience method to parse all documents from a source into a list.

    Args:
        source: Either a URL string or a file path

    Returns:
        List of SGMLDocument objects
    """
    return list(iter_documents(source))


def parse_file(source: Union[str, Path]) -> list[SGMLDocument]:
    """
    Convenience method to parse all documents from a source into a list.

    Args:
        source: Either a URL string or a file path

    Returns:
        List of SGMLDocument objects
    """
    return list(iter_documents(source))

def parse_submission_text(content: str) -> Tuple[FilingHeader, DefaultDict[str, List[SGMLDocument]]]:
    """
    Parses the raw submission text and returns the filing header along with
    a dictionary mapping document sequence numbers to lists of SGMLDocument objects.
    Args:
        content (str): The raw text content of the submission.
    Returns:
        Tuple[FilingHeader, DefaultDict[str, List[SGMLDocument]]]:
            A tuple where the first element is the FilingHeader object representing
            the parsed header information, and the second element is a defaultdict
            mapping document sequence identifiers to their corresponding list of SGMLDocument objects.
    Details:
        - For submissions with the SGMLFormatType.SUBMISSION format, the function uses
          the pre-parsed filer data to create the FilingHeader.
        - For SEC-DOCUMENT formatted content, the header is initially parsed from the SGML text;
          if this fails, the header is parsed again with preprocessing enabled.
        - The function creates an SGMLDocument for each parsed document and groups them by
          their sequence identifier.
    Raises:
        Exception: Any exceptions raised during header parsing (handled internally
                   by attempting to preprocess the header in case of failure).
    """
    # Create parser and get structure including header and documents
    parser = SGMLParser()
    parsed_data = parser.parse(content)

    # Create FilingHeader using already parsed data
    if parsed_data['format'] == SGMLFormatType.SUBMISSION:
        # For submission format, we already have parsed filer data
        header = FilingHeader.parse_submission_format_header(parsed_data=parsed_data)
    else:
        # For SEC-DOCUMENT format, pass the header text to the
        # specialized header parser since we need additional processing
        try:
            header = FilingHeader.parse_from_sgml_text(parsed_data['header'])
        except Exception:
            header = FilingHeader.parse_from_sgml_text(parsed_data['header'], preprocess=True)

    # Create document dictionary
    documents = defaultdict(list)
    for doc_data in parsed_data['documents']:
        doc = SGMLDocument.from_parsed_data(doc_data)
        documents[doc.sequence].append(doc)
    return header, documents



class FilingSGML:
    """
    Main class that parses and provides access to both the header and documents
    from an SGML filing.
    """
    __slots__ = ('header', '_documents_by_sequence', '__dict__')  # Use slots for memory efficiency

    def __init__(self, header: FilingHeader, documents: defaultdict[str, List[SGMLDocument]]):
        """
        Initialize FilingSGML with parsed header and documents.

        Args:
            header (FilingHeader): Parsed header information
            documents (Dict[str, SGMLDocument]): Dictionary of parsed documents keyed by sequence
        """
        self.header:FilingHeader = header
        self._documents_by_sequence:defaultdict[str, List[SGMLDocument]] = documents
        self._documents_by_name:Dict[str, SGMLDocument] = {
            doc.filename: doc for doc_lst in documents.values() for doc in doc_lst
        }

    @property
    def accession_number(self):
        return self.header.accession_number

    @property
    def cik(self):
        return self.header.cik

    @cached_property
    def entity(self):
        from edgar.entity import Entity
        cik = self.cik
        if cik:
            return Entity(cik)

    @property
    def form(self):
        return self.header.form

    @property
    def filing_date(self):
        return self.header.filing_date

    @property
    def date_as_of_change(self):
        return self.header.date_as_of_change

    @property
    def effective_date(self):
        return self.header.filing_metadata.get('EFFECTIVE DATE')

    @property
    def path(self):
        """
        Get the root path of the filing.
        """
        if self.accession_number:
            return f"/Archives/edgar/data/{self.header.cik}/{self.accession_number.replace('-', '')}"
        else:
            return "/<SGML FILE>"


    def html(self):
        html_document = self.attachments.primary_html_document
        if html_document and not html_document.is_binary() and not html_document.empty:
            html_text = self.get_content(html_document.document)
            if isinstance(html_text, bytes):
                html_text = html_text.decode('utf-8')
            return html_text

    def xml(self):
        xml_document = self.attachments.primary_xml_document
        if xml_document and not xml_document.is_binary() and not xml_document.empty:
            xml_text = self.get_content(xml_document.document)
            if isinstance(xml_text, bytes):
                xml_text = xml_text.decode('utf-8')
            return xml_text

    def get_content(self, filename: str) -> Optional[str]:
        """
        Get the content of a document by its filename.
        """
        document = self._documents_by_name.get(filename)
        if document:
            return document.content

    @cached_property
    def attachments(self) -> Attachments:
        """
        Get all attachments from the filing.
        """
        is_datafile = False
        documents, datafiles, primary_files = [], [], []

        # Get the filing summary
        filing_summary = self.filing_summary

        for sequence, document_lst in self._documents_by_sequence.items():
            for document in document_lst:
                attachment = Attachment(
                    sequence_number=sequence,
                    ixbrl=False,
                    path=f"{self.path}/{document.filename}",
                    document=document.filename,
                    document_type=get_document_type(filename=document.filename, declared_document_type=document.type),
                    description=document.description,
                    size=None,
                    sgml_document=document,
                    filing_sgml=self
                )
                # Add from the filing summary if available
                if filing_summary:
                    report = filing_summary.get_reports_by_filename(document.filename)
                    if report:
                        attachment.purpose = report.short_name
                # Check if the document is a primary document
                if sequence == "1":
                    primary_files.append(attachment)
                    documents.append(attachment)
                else:
                    if not is_datafile:
                        is_datafile = is_xml(filename=document.filename)
                    if is_datafile:
                        datafiles.append(attachment)
                    else:
                        documents.append(attachment)

        return Attachments(document_files=documents, data_files=datafiles, primary_documents=primary_files, sgml=self)

    @cached_property
    def filing_summary(self):
        summary_attachment = self._documents_by_name.get("FilingSummary.xml")
        if summary_attachment:
            filing_summary = FilingSummary.parse(summary_attachment.content)
            filing_summary.reports._filing_summary = filing_summary
            filing_summary._filing_sgml = self
            return filing_summary

    def download(self,  path: Union[str, Path], archive: bool = False):
        """
        Download all the attachments to a specified path.
        If the path is a directory, the file is saved with its original name in that directory.
        If the path is a file, the file is saved with the given path name.
        If archive is True, the attachments are saved in a zip file.
        path: str or Path - The path to save the attachments
        archive: bool (default False) - If True, save the attachments in a zip file
        """
        if archive:
            if path.is_dir():
                raise ValueError("Path must be a zip file name to create zipfile")
            else:
                with zipfile.ZipFile(path, 'w') as zipf:
                    for document in self._documents_by_name.values():
                        zipf.writestr(document.filename, document.content)
        else:
            if path.is_dir():
                for document in self._documents_by_name.values():
                    file_path = path / document.filename
                    content = document.content
                    if isinstance(content, bytes):
                        file_path.write_bytes(content)
                    else:
                        file_path.write_text(content, encoding='utf-8')
            else:
                raise ValueError("Path must be a directory")

    @property
    def primary_documents(self):
        """
        Get the primary documents from the filing.
        """
        return self.attachments.primary_documents


    @classmethod
    def from_source(cls, source: Union[str, Path]) -> "FilingSGML":
        """
        Create FilingSGML instance from either a URL or file path.
        Parses both header and documents.

        Args:
            source: Either a URL string or a file path

        Returns:
            FilingSGML: New instance with parsed header and documents

        Raises:
            ValueError: If header section cannot be found
            IOError: If file cannot be read
        """
        # Read content once
        content = read_content_as_string(source)

        # Parse header and documents
        header, documents = parse_submission_text(content)

        # Create FilingSGML instance
        return cls(header=header, documents=documents)
    
    @classmethod
    def from_text(cls, full_text_submission: str) -> "FilingSGML":
        """
        Create FilingSGML instance from either full text submission.
        Parses both header and documents.

        Args:
            full_text_submission: String containing full text submission

        Returns:
            FilingSGML: New instance with parsed header and documents

        Raises:
            ValueError: If header section cannot be found
        """
        # Parse header and documents
        header, documents = parse_submission_text(full_text_submission)

        # Create FilingSGML instance
        return cls(header=header, documents=documents)


    def get_document_by_sequence(self, sequence: str) -> Optional[SGMLDocument]:
        """
        Get a document by its sequence number.
        Direct dictionary lookup for O(1) performance.
        """
        results = self._documents_by_sequence.get(sequence)
        if results and len(results) > 0:
            return results[0]

    def get_document_by_name(self, filename: str) -> Optional[SGMLDocument]:
        """
        Get a document by its filename.
        Direct dictionary lookup for O(1) performance.
        """
        return self._documents_by_name.get(filename)

    @classmethod
    def from_filing(cls, filing: 'Filing') -> 'FilingSGML':
        """Create from a Filing object that provides text_url."""
        filing_sgml = cls.from_source(filing.text_url)
        if not filing_sgml.accession_number:
            filing_sgml.header.filing_metadata.update('ACCESSION NUMBER', filing.accession_no)
        if not filing_sgml.header.filing_metadata.get("CIK"):
            filing_sgml.header.filing_metadata.update('CIK', str(filing.cik).zfill(10))
        if not filing_sgml.header.form:
            filing_sgml.header.filing_metadata.update("CONFORMED SUBMISSION TYPE", filing.form)
        return filing_sgml

    def __str__(self) -> str:
        """String representation with basic filing info."""
        doc_count = len(self._documents_by_name)
        return f"FilingSGML(accession={self.header.accession_number}, document_count={doc_count})"

    def __repr__(self) -> str:
        return str(self)

    def get_document_sequences(self) -> List[str]:
        """
        Get all document sequences.
        Using list() is more efficient than sorted() when order doesn't matter.
        """
        return list(self._documents_by_sequence.keys())

    def get_all_document_types(self) -> List[str]:
        """
        Get unique document types in filing.
        Using set for deduplication.
        """
        return list({doc.type for doc in self._documents_by_sequence.values()})

    def get_document_count(self) -> int:
        """Get total number of documents."""
        return len(self._documents_by_sequence)
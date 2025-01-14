import re
from pathlib import Path
from typing import List, Union, Optional
from typing import Iterator
from functools import cached_property
from edgar.httprequests import stream_with_retry
from edgar.sgml.header import FilingHeader
from edgar.sgml.parsers import SGMLParser, SGMLFormatType, SGMLDocument
from edgar.sgml.tools import is_xml
from collections import defaultdict
from edgar.attachments import Attachments, Attachment

__all__ = ['iter_documents', 'list_documents', 'FilingSgml', 'FilingHeader']


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

    Args:
        source: Either a URL string or a file path

    Yields:
        str: Lines of content from the source

    Raises:
        TooManyRequestsError: If the server returns a 429 response
        FileNotFoundError: If the file path doesn't exist
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
        with path.open('r', encoding='utf-8') as file:
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



class FilingSgml:
    """
    Main class that parses and provides access to both the header and documents
    from an SGML filing.
    """
    __slots__ = ('header', 'documents', '__dict__')  # Use slots for memory efficiency

    def __init__(self, header: FilingHeader, documents: defaultdict[str, SGMLDocument]):
        """
        Initialize FilingSGML with parsed header and documents.

        Args:
            header (FilingHeader): Parsed header information
            documents (Dict[str, SGMLDocument]): Dictionary of parsed documents keyed by sequence
        """
        self.header:FilingHeader = header
        self.documents:defaultdict[str, SGMLDocument] = documents

    def html(self):
        document_lst = self.documents.get("1")
        for document in document_lst:
            if document.filename.lower().endswith((".htm", ".html")):
                return document.content

    def xml(self):
        document_lst = self.documents.get("1")
        for document in document_lst:
            if document.filename.lower().endswith(".xml"):
                return document.content

    @cached_property
    def attachments(self) -> Attachments:
        """
        Get all attachments from the filing.
        """
        is_datafile = False
        documents, datafiles, primary_files = [], [], []
        for sequence, document_lst in self.documents.items():
            for document in document_lst:
                attachment = Attachment(
                    sequence_number=sequence,
                    ixbrl=False,
                    path="<in sgml>",
                    document=document.filename,
                    document_type=document.type,
                    description=document.description,
                    size=None
                )
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

        return Attachments(document_files=documents, data_files=datafiles, primary_documents=primary_files)


    @classmethod
    def from_source(cls, source: Union[str, Path]) -> 'FilingSGML':
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

        # Create parser and get structure including header and documents
        parser = SGMLParser()
        parsed_data = parser.parse(content)

        # Create FilingHeader using already parsed data
        if parsed_data['format'] == SGMLFormatType.SUBMISSION:
            # For submission format, we already have parsed filer data
            metadata = {
                "ACCESSION NUMBER": parsed_data.get("ACCESSION-NUMBER"),
                "CONFORMED SUBMISSION TYPE": parsed_data.get("TYPE"),
                "FILED AS OF DATE": parsed_data.get("FILING-DATE"),
                "DATE AS OF CHANGE": parsed_data.get("DATE-OF-FILING-DATE-CHANGE"),
                "EFFECTIVE DATE": parsed_data.get("EFFECTIVENESS-DATE"),
            }

            # No need to reparse the header text
            header = FilingHeader(
                text=parsed_data['header'],
                filing_metadata=metadata,
                filers=parsed_data.get('filer', []),
                reporting_owners=parsed_data.get('reporting_owners', []),
                issuers=parsed_data.get('issuers', []),
                subject_companies=parsed_data.get('subject_companies', [])
            )
        else:
            # For SEC-DOCUMENT format, pass the header text to the
            # specialized header parser since we need additional processing
            header = FilingHeader.parse_from_sgml_text(parsed_data['header'])

        # Create document dictionary
        documents = defaultdict(list)
        for doc_data in parsed_data['documents']:
            doc = SGMLDocument.from_parsed_data(doc_data)
            documents[doc.sequence].append(doc)

        return cls(header=header, documents=documents)


    def get_document_by_sequence(self, sequence: str) -> Optional[SGMLDocument]:
        """
        Get a document by its sequence number.
        Direct dictionary lookup for O(1) performance.
        """
        results = self.documents.get(sequence)
        if results and len(results) > 0:
            return results[0]

    def get_documents_by_type(self, doc_type: str) -> List[SGMLDocument]:
        """
        Get all documents of a specific type.
        """
        return [doc for doc in self.documents.values() if doc.type == doc_type]

    @classmethod
    def from_filing(cls, filing: 'Filing') -> 'FilingSGML':
        """Create from a Filing object that provides text_url."""
        return cls.from_source(filing.text_url)

    def __str__(self) -> str:
        """String representation with basic filing info."""
        doc_count = len(self.documents)
        return f"FilingSGML(accession={self.header.accession_number}, document_count={doc_count})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        docs = [f"{k}:{v.type}" for k, v in self.documents.items()]
        return f"FilingSGML(header={self.header!r}, documents={docs!r})"

    def get_document_sequences(self) -> List[str]:
        """
        Get all document sequences.
        Using list() is more efficient than sorted() when order doesn't matter.
        """
        return list(self.documents.keys())

    def get_all_document_types(self) -> List[str]:
        """
        Get unique document types in filing.
        Using set for deduplication.
        """
        return list({doc.type for doc in self.documents.values()})

    def get_document_count(self) -> int:
        """Get total number of documents."""
        return len(self.documents)
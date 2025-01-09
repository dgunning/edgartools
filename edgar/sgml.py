
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, Union, Optional

from edgar.httprequests import stream_with_retry

__all__ = ['SgmlDocument', 'iter_documents', 'FilingSgml']



@dataclass
class SgmlDocument:
    type: str
    sequence: str
    filename: str
    description: str
    raw_content: str = ""

    def __str__(self):
        return f"Document(type={self.type}, sequence={self.sequence}, filename={self.filename}, description={self.description})"

    def text(self) -> str:
        """Extract content between <TEXT> tags."""
        match = re.search(r'<TEXT>([\s\S]*?)</TEXT>', self.raw_content, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def xml(self) -> Optional[str]:
        """Extract content between <XML> tags if present."""
        match = re.search(r'<XML>([\s\S]*?)</XML>', self.raw_content, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else None

    def html(self) -> Optional[str]:
        """Extract content between <HTML> tags if present."""
        match = re.search(r'<HTML>([\s\S]*?)</HTML>', self.raw_content, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else None

    def xbrl(self) -> Optional[str]:
        """Extract content between <XBRL> tags if present."""
        match = re.search(r'<XBRL>([\s\S]*?)</XBRL>', self.raw_content, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else None

    def get_content_type(self) -> str:
        """
        Determine the primary content type of the document.
        Returns: 'xml', 'html', 'xbrl', or 'text'
        """
        if self.xml():
            return 'xml'
        elif self.html():
            return 'html'
        elif self.xbrl():
            return 'xbrl'
        return 'text'

def strip_tags(text: str, start_tag: str, end_tag: str) -> str:
    """Strip XML/HTML tags from text if present."""
    if text.startswith(start_tag) and text.endswith(end_tag):
        return text[len(start_tag):-len(end_tag)].strip()
    return text


def parse_document(document_str: str) -> SgmlDocument:
    """
    Parse a single SGML document section, maintaining raw content.
    """
    # Extract individual fields with separate patterns
    type_match = re.search(r'<TYPE>([^<\n]+)', document_str)
    sequence_match = re.search(r'<SEQUENCE>([^<\n]+)', document_str)
    filename_match = re.search(r'<FILENAME>([^<\n]+)', document_str)
    description_match = re.search(r'<DESCRIPTION>([^<\n]+)', document_str)

    return SgmlDocument(
        type=type_match.group(1).strip() if type_match else "",
        sequence=sequence_match.group(1).strip() if sequence_match else "",
        filename=filename_match.group(1).strip() if filename_match else "",
        description=description_match.group(1).strip() if description_match else "",
        raw_content=document_str
    )


def read_content(source: Union[str, Path]) -> Iterator[str]:
    """
    Read content from either a URL or file path, yielding lines.

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
            # Process each line from the response
            for line in response.iter_lines():
                yield line
    else:
        # Handle file path
        path = Path(source)
        with path.open('r', encoding='utf-8') as file:
            yield from file


def iter_documents(source: Union[str, Path]) -> Iterator[SgmlDocument]:
    """
    Stream SGML documents from either a URL or file path, yielding parsed documents.

    Args:
        source: Either a URL string or a file path (string or Path object)

    Yields:
        SgmlDocument objects containing the parsed content

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

def list_documents(source: Union[str, Path]) -> list[SgmlDocument]:
    """
    Convenience method to parse all documents from a source into a list.

    Args:
        source: Either a URL string or a file path

    Returns:
        List of SgmlDocument objects
    """
    return list(iter_documents(source))


def parse_file(source: Union[str, Path]) -> list[SgmlDocument]:
    """
    Convenience method to parse all documents from a source into a list.

    Args:
        source: Either a URL string or a file path

    Returns:
        List of SgmlDocument objects
    """
    return list(iter_documents(source))

class FilingSgml:

    def __init__(self, sgml_documents: Dict[str, SgmlDocument]):
        self.sgml_documents = sgml_documents


    def get_by_sequence(self, sequence:str) -> SgmlDocument:
        """Get the sqml document by sequence number."""
        return self.sgml_documents.get(sequence)


    @classmethod
    def from_source(cls, source:Union[str, Path]):
        sgml_documents = {
            document.sequence: document
            for document in iter_documents(source)
        }
        return cls(sgml_documents)

    @classmethod
    def from_filing(cls, filing: 'Filing'):
        return cls.from_source(filing.text_url)

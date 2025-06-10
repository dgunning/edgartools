import re
import warnings
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import Iterator, Optional

from edgar.sgml.tools import get_content_between_tags
from edgar.vendored import uu

__all__ = ['SGMLParser', 'SGMLFormatType', 'SGMLDocument']

class SGMLFormatType(Enum):
    SEC_DOCUMENT = "sec_document"  # <SEC-DOCUMENT>...<SEC-HEADER> style
    SUBMISSION = "submission"  # <SUBMISSION>...<FILER> style


@dataclass
class SGMLDocument:
    type: str
    sequence: str
    filename: str
    description: str
    raw_content: str = ""

    @classmethod
    def from_parsed_data(cls, data: dict) -> 'SGMLDocument':
        """Create document from parser output"""
        return cls(
            type=data['type'],
            sequence=data['sequence'],
            filename=data['filename'],
            description=data['description'],
            raw_content=data['content']
        )

    @property
    def content(self):
        raw_content = get_content_between_tags(self.raw_content)
        if raw_content:
            if raw_content.startswith("begin"):
                # Create input and output streams
                # Suppress the binascii warning

                warnings.filterwarnings('ignore')

                # Create input and output streams
                input_stream = BytesIO(raw_content.encode("utf-8"))
                output_stream = BytesIO()

                # Decode the UU content
                uu.decode(input_stream, output_stream, quiet=True)

                # Get the decoded bytes
                return output_stream.getvalue()
            return raw_content

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

class SGMLParser:
    @staticmethod
    def detect_format(content: str) -> SGMLFormatType:
        """Detect SGML format based on root element"""
        if content.lstrip().startswith('<SUBMISSION>'):
            return SGMLFormatType.SUBMISSION
        elif '<SEC-DOCUMENT>' in content:
            return SGMLFormatType.SEC_DOCUMENT
        elif '<IMS-DOCUMENT>' in content:
            # For old filings from the 1990's
            return SGMLFormatType.SEC_DOCUMENT
        elif '<DOCUMENT>' in content[:1000]:
            # For old filings from the 1990's
            return SGMLFormatType.SEC_DOCUMENT
        raise ValueError("Unknown SGML format")

    def parse(self, content) -> dict:
        """Main entry point for parsing"""
        format_type = self.detect_format(content)

        if format_type == SGMLFormatType.SUBMISSION:
            return self._parse_submission_format(content)
        else:
            return self._parse_sec_document_format(content)

    def _parse_submission_format(self, content):
        parser = SubmissionFormatParser()
        return parser.parse(content)

    def _parse_sec_document_format(self, content):
        parser = SecDocumentFormatParser()
        return parser.parse(content)


class SubmissionFormatParser:
    def __init__(self):
        # Initialize main data structure
        self.data = {
            'format': SGMLFormatType.SUBMISSION,
            'header': '',
            'documents': [],
        }

        # Parser state
        self.current_path = []  # Stack to track current position in hierarchy
        self.header_lines = []  # Collect header lines
        self.in_documents = False

        # Known section tags that can contain nested content
        self.SECTION_TAGS = {
            'FILER',
            'OWNER-DATA',
            'COMPANY-DATA',
            'REPORTING-OWNER',
            'ISSUER',
            'DEPOSITOR',
            'SECURITIZER',
            'ISSUING_ENTITY',
            'FORMER-COMPANY',
            'SUBJECT-COMPANY',
            'FILED-BY',
            'FORMER-NAME',
            'FILING-VALUES',
            'BUSINESS-ADDRESS',
            'MAIL-ADDRESS',
            'CLASS-CONTRACT',
            'SERIES',
            'NEW-SERIES',
            'NEW-CLASSES-CONTRACTS',
            'ACQUIRING-DATA',
            'TARGET-DATA',
            'SERIAL-COMPANY',
            'MERGER',
            'SERIES-AND-CLASSES-CONTRACTS-DATA',
            'NEW-SERIES-AND-CLASSES-CONTRACTS',
            'MERGER-SERIES-AND-CLASSES-CONTRACTS',
            'EXISTING-SERIES-AND-CLASSES-CONTRACTS'
        }

        # Tags that can appear multiple times and should be stored as lists
        self.REPEATABLE_TAGS = {
            'FILER',
            'REPORTING-OWNER',
            'SERIES',
            'CLASS-CONTRACT',
            'FORMER-COMPANY',
            'SUBJECT-COMPANY'
        }

    def _get_current_context(self) -> dict:
        """Navigate to current position in data hierarchy."""
        context = self.data
        for path_element in self.current_path:
            tag, index = path_element
            if index is not None:
                context = context[tag][index]
            else:
                context = context[tag]
        return context

    def _is_unclosed_tag(self, line: str) -> bool:
        """Check if line is an unclosed tag with value."""
        line = line.strip()
        if not (line.startswith('<') and '>' in line and not line.startswith('</')):
            return False

        tag_end = line.index('>')
        content_after = line[tag_end + 1:].strip()
        return bool(content_after)

    def _is_section_end(self, line: str) -> bool:
        """Check if line ends a section."""
        return line.strip().startswith('</')

    def _is_section_start(self, line: str) -> bool:
        """Identifies if a line starts a new nested section."""
        line = line.strip()
        if not line.startswith('<') or not line.endswith('>'):
            return False

        tag = line[1:-1]  # Remove < and >
        return tag in self.SECTION_TAGS

    def _is_data_tag(self, line: str) -> bool:
        """Identifies if a line contains a tag with a value."""
        line = line.strip()
        if not line.startswith('<'):
            return False

        parts = line.split('>')
        return len(parts) == 2 and bool(parts[1].strip())

    def _is_empty_tag(self, line: str) -> bool:
        """Identifies if a line is an empty tag."""
        line = line.strip()
        return (line.startswith('<') and
                line.endswith('>') and
                not line.startswith('</') and
                not self._is_section_start(line) and
                not self._is_data_tag(line))

    def _handle_section_start(self, line: str) -> None:
        """Handle start of nested section."""
        tag = line.strip()[1:-1]  # Remove < and >

        current_context = self._get_current_context()

        # Initialize tag in current context if needed
        if tag not in current_context:
            if tag in self.REPEATABLE_TAGS:
                current_context[tag] = []
            else:
                current_context[tag] = {}

        # For repeatable tags, append new dict and track index
        if tag in self.REPEATABLE_TAGS:
            current_context[tag].append({})
            self.current_path.append((tag, len(current_context[tag]) - 1))
        else:
            self.current_path.append((tag, None))

    def _handle_section_end(self, line: str) -> None:
        """Handle end of nested section."""
        tag = line.strip()[2:-1]  # Remove </ and >

        # Verify we're closing the correct tag
        current_tag, _ = self.current_path[-1]
        if tag != current_tag:
            raise ValueError(f"Mismatched tags: expected </{current_tag}>, got </{tag}>")

        # Pop the current section from the path
        self.current_path.pop()

    def _handle_data_tag(self, line: str) -> None:
        """Handle tags with values."""
        line = line.strip()
        tag_end = line.index('>')
        tag = line[1:tag_end]
        value = line[tag_end + 1:].strip()

        current_context = self._get_current_context()

        # Handle repeated tags
        if tag in current_context:
            if not isinstance(current_context[tag], list):
                current_context[tag] = [current_context[tag]]
            current_context[tag].append(value)
        else:
            current_context[tag] = value

    def _handle_empty_tag(self, line: str) -> None:
        """Handle empty tags."""
        tag = line.strip()[1:-1]  # Remove < and >
        current_context = self._get_current_context()
        current_context[tag] = ""

    def _handle_unclosed_tag(self, line: str) -> None:
        """Handle tags like <ITEMS>value."""
        line = line.strip()
        tag_end = line.index('>')
        tag = line[1:tag_end]
        value = line[tag_end + 1:].strip()

        current_context = self._get_current_context()

        if tag in current_context:
            if not isinstance(current_context[tag], list):
                current_context[tag] = [current_context[tag]]
            current_context[tag].append(value)
        else:
            current_context[tag] = value

    def parse(self, content: str) -> dict:
        """Parse SGML content in SUBMISSION format."""
        document_buffer = None

        for line in content.splitlines():
            # Check for document section
            if '<DOCUMENT>' in line:
                self.data['header'] = '\n'.join(self.header_lines)
                self.in_documents = True
                document_buffer = [line]
                continue

            if self.in_documents:
                if '</DOCUMENT>' in line:
                    document_buffer.append(line)
                    doc_content = '\n'.join(document_buffer)
                    doc_data = self._parse_document_section(doc_content)
                    if doc_data:
                        self.data['documents'].append(doc_data)
                    document_buffer = None
                elif document_buffer is not None:
                    document_buffer.append(line)
            else:
                # Header section parsing
                self.header_lines.append(line)
                line = line.strip()

                if not line:
                    continue

                if self._is_section_start(line):
                    self._handle_section_start(line)
                elif self._is_section_end(line):
                    self._handle_section_end(line)
                elif self._is_data_tag(line):
                    self._handle_data_tag(line)
                elif self._is_empty_tag(line):
                    self._handle_empty_tag(line)
                elif self._is_unclosed_tag(line):
                    self._handle_unclosed_tag(line)

        return self.data

    def _parse_document_section(self, content: str) -> dict:
        """Parse a single document section."""
        doc_data = {
            'type': '',
            'sequence': '',
            'filename': '',
            'description': '',
            'content': content
        }

        # Extract document metadata
        type_match = re.search(r'<TYPE>([^<\n]+)', content)
        if type_match:
            doc_data['type'] = type_match.group(1).strip()

        sequence_match = re.search(r'<SEQUENCE>([^<\n]+)', content)
        if sequence_match:
            doc_data['sequence'] = sequence_match.group(1).strip()

        filename_match = re.search(r'<FILENAME>([^<\n]+)', content)
        if filename_match:
            doc_data['filename'] = filename_match.group(1).strip()

        description_match = re.search(r'<DESCRIPTION>([^<\n]+)', content)
        if description_match:
            doc_data['description'] = description_match.group(1).strip()

        return doc_data

class SecDocumentFormatParser:
    """Parser for <SEC-DOCUMENT> style SGML"""

    def __init__(self):
        self.in_header = False
        self.data = {
            'format': SGMLFormatType.SEC_DOCUMENT,
            'header': '',
            'documents': [],
            'filer': {}
        }
        self.current_document = {}
        self.header_text = []

    def parse(self, content: str) -> dict:
        """Parse SGML content in SEC-DOCUMENT format

        Args:
            content: The full SGML content as string

        Returns:
            dict containing parsed header and documents
        """
        document_buffer = []

        for line in content.splitlines():
            if '<SEC-HEADER>' in line or '<IMS-HEADER>' in line:
                self.in_header = True
                continue
            elif '</SEC-HEADER>' in line or '</IMS-HEADER>' in line:
                self.in_header = False
                self.data['header'] = '\n'.join(self.header_text)
                continue

            if self.in_header:
                # Collect header text
                self.header_text.append(line)

            # Handle document sections
            if '<DOCUMENT>' in line:
                document_buffer = []  # Start new document
            elif '</DOCUMENT>' in line and document_buffer:
                # Parse completed document
                doc_content = '\n'.join(document_buffer)
                doc_data = self._parse_document_section(doc_content)
                if doc_data:
                    self.data['documents'].append(doc_data)
                document_buffer = []
            elif document_buffer is not None:  # Currently collecting document content
                document_buffer.append(line)

        return self.data

    def _parse_document_section(self, content: str) -> dict:
        """Parse a single document section

        Args:
            content: Content between <DOCUMENT> tags

        Returns:
            dict with document metadata and content
        """
        doc_data = {
            'type': '',
            'sequence': '',
            'filename': '',
            'description': '',
            'content': content
        }

        # Extract document metadata using regex
        type_match = re.search(r'<TYPE>([^<\n]+)', content)
        if type_match:
            doc_data['type'] = type_match.group(1).strip()

        sequence_match = re.search(r'<SEQUENCE>([^<\n]+)', content)
        if sequence_match:
            doc_data['sequence'] = sequence_match.group(1).strip()

        filename_match = re.search(r'<FILENAME>([^<\n]+)', content)
        if filename_match:
            doc_data['filename'] = filename_match.group(1).strip()

        description_match = re.search(r'<DESCRIPTION>([^<\n]+)', content)
        if description_match:
            doc_data['description'] = description_match.group(1).strip()

        return doc_data

def list_documents(content:str) -> list[SGMLDocument]:
    """
    Convenience method to parse all documents from a source into a list.

    Args:
        content: The content string to parse

    Returns:
        List of SGMLDocument objects
    """
    return list(iter_documents(content))

def iter_documents(content:str) -> Iterator[SGMLDocument]:
    """
    Stream SGML documents from either a URL or file path, yielding parsed documents.

    Args:
        content: The content string to parse

    Yields:
        SGMLDocument objects containing the parsed content

    Raises:
        ValueError: If the source is invalid
        ConnectionError: If URL retrieval fails after retries
        FileNotFoundError: If the file path doesn't exist
    """
    document_pattern = re.compile(r'<DOCUMENT>([\s\S]*?)</DOCUMENT>')

    for match in document_pattern.finditer(content):
        document = parse_document(match.group(1))
        if document:
            yield document


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

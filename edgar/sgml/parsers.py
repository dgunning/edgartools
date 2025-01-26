import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Optional
from edgar.sgml.tools import get_content_between_tags, decode_uu

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
        text = get_content_between_tags(self.raw_content)
        if text:
            if text.startswith("begin"):
                return decode_uu(text)
            return text

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
        self.stack = []
        self.data = {
            'format': SGMLFormatType.SUBMISSION,
            'header': '',
            'documents': [],
            'filer': {}
        }
        self.current_tag = None
        self.buffer = []
        self.header_lines = []
        self.in_documents = False


    def _is_unclosed_tag(self, line: str) -> bool:
        """
        Check if line is an unclosed tag with value.

        Examples:
            "<TAG>value" -> True
            "<TAG>" -> False
            "</TAG>" -> False
            "<TAG>  " -> False
        """
        line = line.strip()
        if not (line.startswith('<') and '>' in line and not line.startswith('</')):
            return False

        # Get the content after the tag
        tag_end = line.index('>')
        content_after = line[tag_end + 1:].strip()

        # It's an unclosed tag only if there's non-empty content after the '>'
        return bool(content_after)

    def _is_section_start(self, line: str) -> bool:
        """Check if line starts a new section"""
        line = line.strip()
        return (line.startswith('<') and
                '>' in line and
                not line.startswith('</') and
                line.endswith('>'))

    def _is_section_end(self, line: str) -> bool:
        """Check if line ends a section"""
        return line.strip().startswith('</')

    def _is_section_start(self, line: str) -> bool:
        """
        Identifies if a line starts a new nested section.
        These are tags that will be followed by more tags.

        Examples:
            "<FILER>" -> True
            "<COMPANY-DATA>" -> True
            "<ACCESSION-NUMBER>12345" -> False
            "<ORGANIZATION-NAME>" -> False
        """
        SECTION_TAGS = {
            'FILER',
            'OWNER-DATA',
            'COMPANY-DATA',
            'REPORTING-OWNER',
            'ISSUER',
            'FORMER-COMPANY',
            'FORMER-NAME',
            'FILING-VALUES',
            'BUSINESS-ADDRESS',
            'MAIL-ADDRESS',
            'CLASS-CONTRACT',
            'SERIES',
            'EXISTING-SERIES-AND-CLASSES-CONTRACTS',
            'SERIES-AND-CLASSES-CONTRACTS-DATA',
            'SUBJECT-COMPANY',
            'FILED-BY',
            'DEPOSITOR',
            'SECURITIZER'
            # Add other section tags as needed
        }

        line = line.strip()
        if not line.startswith('<') or not line.endswith('>'):
            return False

        # Extract tag name
        tag = line[1:-1]  # Remove < and >
        return tag in SECTION_TAGS

    def _is_data_tag(self, line: str) -> bool:
        """
        Identifies if a line contains a tag with a value.

        Examples:
            "<ACCESSION-NUMBER>0002002260-24-000001" -> True
            "<TYPE>D" -> True
            "<ORGANIZATION-NAME>" -> False
            "<FILER>" -> False
        """
        line = line.strip()
        if not line.startswith('<'):
            return False

        parts = line.split('>')
        return len(parts) == 2 and bool(parts[1].strip())

    def _is_empty_tag(self, line: str) -> bool:
        """
        Identifies if a line is an empty tag.

        Examples:
            "<ORGANIZATION-NAME>" -> True
            "<ACCESSION-NUMBER>12345" -> False
            "<FILER>" -> False
        """
        line = line.strip()
        return (line.startswith('<') and
                line.endswith('>') and
                not line.startswith('</') and
                not self._is_section_start(line) and
                not self._is_data_tag(line))

    def _handle_unclosed_tag(self, line: str) -> None:
        """Handle tags like <ITEMS>value"""
        line = line.strip()
        tag_end = line.index('>')
        tag = line[1:tag_end]
        value = line[tag_end + 1:].strip()

        # Handle repeated tags (like ITEMS)
        if tag in self.data:
            if not isinstance(self.data[tag], list):
                self.data[tag] = [self.data[tag]]
            self.data[tag].append(value)
        else:
            self.data[tag] = value

    def _handle_section_start(self, line: str) -> None:
        """Handle start of nested section, e.g. <FILER>"""
        line = line.strip()
        tag = line[1:-1]  # Remove < and >

        # Push current state to stack
        if self.current_tag:
            self.stack.append((self.current_tag, self.buffer))

        self.current_tag = tag
        self.buffer = []

        # Initialize data structure for this section
        if tag not in self.data:
            self.data[tag] = []
        # Add new empty dict for this section instance
        self.data[tag].append({})

    def _handle_section_end(self, line: str) -> None:
        """Handle end of nested section"""
        line = line.strip()
        tag = line[2:-1]  # Remove </ and >

        if tag != self.current_tag:
            raise ValueError(f"Mismatched tags: expected </{self.current_tag}>, got </{tag}>")

        # Process buffered content
        section_data = {}
        nested_buffer = []

        for content in self.buffer:
            if self._is_unclosed_tag(content):
                # Handle single line tag-value pair
                tag_end = content.index('>')
                nested_tag = content[1:tag_end]
                value = content[tag_end + 1:].strip()
                section_data[nested_tag] = value
            else:
                # Add to nested buffer
                nested_buffer.append(content)

        if nested_buffer:
            section_data['_content'] = '\n'.join(nested_buffer)

        # Add processed section to data
        if self.current_tag in self.data:
            if not isinstance(self.data[self.current_tag], list):
                self.data[self.current_tag] = [self.data[self.current_tag]]
            self.data[self.current_tag].append(section_data)
        else:
            self.data[self.current_tag] = section_data

        # Restore previous state from stack
        if self.stack:
            self.current_tag, self.buffer = self.stack.pop()
        else:
            self.current_tag = None
            self.buffer = []

    def _handle_content(self, line: str) -> None:
        """Handle content within sections"""
        if self.current_tag:
            self.buffer.append(line.rstrip())

    def _handle_data_tag(self, line: str) -> None:
        """
        Handle tags with values, e.g., "<ACCESSION-NUMBER>0002002260-24-000001"
        Stores the tag value in the current data context.
        """
        line = line.strip()
        tag_end = line.index('>')
        tag = line[1:tag_end]  # Remove < and get tag name
        value = line[tag_end + 1:].strip()

        # If we're inside a nested structure, add to current context
        if self.current_tag:
            current_section = self.data[self.current_tag][-1]
            if tag in current_section:
                # If tag already exists, convert to list or append to existing list
                existing = current_section[tag]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    current_section[tag] = [existing, value]
            else:
                current_section[tag] = value
        else:
            # Add to root level data
            if tag in self.data:
                # Handle repeated tags (like ITEMS)
                if isinstance(self.data[tag], list):
                    self.data[tag].append(value)
                else:
                    self.data[tag] = [self.data[tag], value]
            else:
                self.data[tag] = value

    def _handle_empty_tag(self, line: str) -> None:
        """
        Handle empty tags like "<ORGANIZATION-NAME>"
        Stores as an empty string or None depending on context
        """
        line = line.strip()
        tag = line[1:-1]  # Remove < and >

        # If we're inside a nested structure
        if self.current_tag:
            self.data[self.current_tag][-1][tag] = ""
        else:
            # Add to root level data
            self.data[tag] = ""

    def parse(self, content: str) -> dict:
        """Parse SGML content in SUBMISSION format"""
        for line in content.splitlines():
            # Once we hit <DOCUMENT>, stop header parsing
            if '<DOCUMENT>' in line:
                # Store accumulated header
                self.data['header'] = '\n'.join(self.header_lines)
                self.in_documents = True
                # Start collecting document content
                document_buffer = [line]
                continue

            if self.in_documents:
                # Handle document section separately
                if '</DOCUMENT>' in line:
                    document_buffer.append(line)
                    doc_content = '\n'.join(document_buffer)
                    doc_data = self._parse_document_section(doc_content)
                    if doc_data:
                        self.data['documents'].append(doc_data)
                    document_buffer = []
                else:
                    document_buffer.append(line)
            else:
                # Still in header section
                self.header_lines.append(line)
                if self._is_section_start(line):
                    self._handle_section_start(line)
                elif self._is_data_tag(line):
                    self._handle_data_tag(line)
                elif self._is_empty_tag(line):
                    self._handle_empty_tag(line)
                elif line.startswith('</'):
                    self._handle_section_end(line)
                elif line.strip():
                    self._handle_content(line)

        return self.data

    def _parse_document_section(self, content: str) -> dict:
        """Parse a single document section"""
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

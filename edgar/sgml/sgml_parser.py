import logging
import re
import warnings
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from typing import Iterator, Optional

from edgar.core import has_html_content
from edgar.sgml.tools import get_content_between_tags
from edgar.vendored import uu

log = logging.getLogger(__name__)

# Maximum content size (500MB). Larger inputs are rejected to prevent OOM.
# Some real SEC filings (e.g., 10-Ks with embedded images) can exceed 300MB.
_MAX_CONTENT_SIZE = 500 * 1024 * 1024

__all__ = ['SGMLParser', 'SGMLFormatType', 'SGMLDocument', 'SECIdentityError',
           'FilingNotFoundError', 'SECHTMLResponseError',
           'SECFilingNotFoundError']  # last is a deprecated alias, removed in 6.0

# Pre-compiled patterns for content extraction
_TEXT_RE = re.compile(r'<TEXT>([\s\S]*?)</TEXT>', re.DOTALL | re.IGNORECASE)
_XML_RE = re.compile(r'<XML>([\s\S]*?)</XML>', re.DOTALL | re.IGNORECASE)
_HTML_RE = re.compile(r'<HTML>([\s\S]*?)</HTML>', re.DOTALL | re.IGNORECASE)
_XBRL_RE = re.compile(r'<XBRL>([\s\S]*?)</XBRL>', re.DOTALL | re.IGNORECASE)

# Document metadata tags and their lengths
_DOC_META_TAGS = (
    ('<TYPE>', 6),
    ('<SEQUENCE>', 10),
    ('<FILENAME>', 10),
    ('<DESCRIPTION>', 13),
)


# These three are branches of the tree in edgar.exceptions (bead
# edgartools-07lk.10): SECIdentityError joins IdentityNotSetError under
# IdentityError (same root cause, noticed at different layers), and a filing
# that does not exist is a NotFoundError like any other missing thing.
from edgar._compat import deprecated_alias
from edgar.exceptions import FilingNotFoundError, SECIdentityError, TransportError


class SECHTMLResponseError(TransportError):
    """Raised when SEC returns HTML content instead of expected SGML"""


__getattr__ = deprecated_alias(SECFilingNotFoundError=FilingNotFoundError)

class SGMLFormatType(Enum):
    SEC_DOCUMENT = "sec_document"  # <SEC-DOCUMENT>...<SEC-HEADER> style
    SUBMISSION = "submission"  # <SUBMISSION>...<FILER> style


def _extract_tag_value(content: str, tag: str, tag_len: int, search_start: int, search_end: int) -> str:
    """Extract value after a tag using str.find(). Returns empty string if not found."""
    idx = content.find(tag, search_start, search_end)
    if idx < 0:
        return ''
    val_start = idx + tag_len
    val_end = content.find('\n', val_start, search_end)
    if val_end < 0:
        return content[val_start:search_end].strip()
    return content[val_start:val_end].strip()


def _extract_doc_metadata(content: str, start: int, end: int) -> dict:
    """Extract TYPE, SEQUENCE, FILENAME, DESCRIPTION from first ~500 chars of a document."""
    search_end = min(start + 500, end)
    return {
        'type': _extract_tag_value(content, '<TYPE>', 6, start, search_end),
        'sequence': _extract_tag_value(content, '<SEQUENCE>', 10, start, search_end),
        'filename': _extract_tag_value(content, '<FILENAME>', 10, start, search_end),
        'description': _extract_tag_value(content, '<DESCRIPTION>', 13, start, search_end),
    }


@dataclass
class SGMLDocument:
    type: str
    sequence: str
    filename: str
    description: str
    # Lazy content: store reference + offsets instead of copying
    _content_ref: str = field(default="", repr=False)
    _content_start: int = field(default=0, repr=False)
    _content_end: Optional[int] = field(default=None, repr=False)

    @classmethod
    def from_content_ref(cls, metadata: dict, content_ref: str, start: int, end: int) -> 'SGMLDocument':
        """Create document with lazy content reference (zero-copy)."""
        return cls(
            type=metadata['type'],
            sequence=metadata['sequence'],
            filename=metadata['filename'],
            description=metadata['description'],
            _content_ref=content_ref,
            _content_start=start,
            _content_end=end,
        )

    @classmethod
    def from_parsed_data(cls, data: dict) -> 'SGMLDocument':
        """Create document from parser output (legacy compatibility)."""
        content = data['content']
        return cls(
            type=data['type'],
            sequence=data['sequence'],
            filename=data['filename'],
            description=data['description'],
            _content_ref=content,
            _content_start=0,
            _content_end=len(content),
        )

    @property
    def raw_content(self) -> str:
        """Content materialized from reference on access."""
        if self._content_end is None:
            return self._content_ref
        return self._content_ref[self._content_start:self._content_end]

    @raw_content.setter
    def raw_content(self, value: str):
        """Allow direct assignment for backward compatibility."""
        self._content_ref = value
        self._content_start = 0
        self._content_end = len(value)

    @property
    def content(self):
        raw_content = get_content_between_tags(self.raw_content)
        if raw_content:
            if raw_content.startswith("begin"):
                warnings.filterwarnings('ignore')
                input_stream = BytesIO(raw_content.encode("utf-8"))
                output_stream = BytesIO()
                uu.decode(input_stream, output_stream, quiet=True)
                return output_stream.getvalue()
            return raw_content

    def __str__(self):
        return f"Document(type={self.type}, sequence={self.sequence}, filename={self.filename}, description={self.description})"

    def text(self) -> str:
        """Extract content between <TEXT> tags."""
        match = _TEXT_RE.search(self.raw_content)
        return match.group(1).strip() if match else ""

    def xml(self) -> Optional[str]:
        """Extract content between <XML> tags if present."""
        match = _XML_RE.search(self.raw_content)
        return match.group(1).strip() if match else None

    def html(self) -> Optional[str]:
        """Extract content between <HTML> tags if present."""
        match = _HTML_RE.search(self.raw_content)
        return match.group(1).strip() if match else None

    def xbrl(self) -> Optional[str]:
        """Extract content between <XBRL> tags if present."""
        match = _XBRL_RE.search(self.raw_content)
        return match.group(1).strip() if match else None

    def get_content_type(self) -> str:
        """
        Determine the primary content type of the document.
        Returns: 'xml', 'html', 'xbrl', or 'text'
        """
        raw = self.raw_content
        if _XML_RE.search(raw):
            return 'xml'
        elif _HTML_RE.search(raw):
            return 'html'
        elif _XBRL_RE.search(raw):
            return 'xbrl'
        return 'text'

def _raise_sec_html_error(content: str):
    """
    Analyze HTML/XML error content from SEC and raise appropriate specific exception.

    Args:
        content: HTML or XML content received from SEC

    Raises:
        SECIdentityError: For identity-related errors
        FilingNotFoundError: For missing filing errors
        SECHTMLResponseError: For other HTML/XML responses
    """
    # Check for identity error
    if "Your Request Originates from an Undeclared Automated Tool" in content:
        raise SECIdentityError(
            "SEC rejected request due to invalid or missing EDGAR_IDENTITY. "
            "Please set a valid identity using set_identity('Your Name your.email@domain.com'). "
            "See https://www.sec.gov/os/accessing-edgar-data"
        )

    # Check for AWS S3 NoSuchKey error (XML format)
    if "<Code>NoSuchKey</Code>" in content and "<Message>The specified key does not exist.</Message>" in content:
        raise FilingNotFoundError(
            "SEC filing not found - the specified key does not exist in EDGAR archives. "
            "Check that the accession number and filing date are correct."
        )

    # Check for general not found errors
    if "Not Found" in content or "404" in content:
        raise FilingNotFoundError(
            "SEC filing not found. Check that the accession number and filing date are correct."
        )

    # Generic HTML/XML response error
    raise SECHTMLResponseError(
        "SEC returned HTML or XML content instead of expected SGML filing data. "
        "This may indicate an invalid request or temporary SEC server issue."
    )


_HEADER_ROOT_TAGS = ('<SEC-HEADER>', '<IMS-HEADER>')


def _is_tagged_header_dialect(content_stripped: str) -> bool:
    """Is this header written in the hyphenated tag dialect?

    Pre-2004 ``.hdr.sgml`` artifacts served as the submission text file use
    tags, e.g. accession 0000950123-96-000525::

        <SEC-HEADER>0000950123-96-000525.hdr.sgml : 19960213
        <ACCESSION-NUMBER>0000950123-96-000525
        <TYPE>SC 13G/A

    while the same root tag can also introduce the tab-indented "space"
    dialect (``ACCESSION NUMBER:\t0000950123-96-000524``). The distinction is
    load-bearing: SubmissionFormatParser skips every line of the space dialect
    and yields an empty header *without raising*, so misrouting here produces a
    silent all-None header rather than an error. Decide on the first header
    line after the root tag.
    """
    # Skip the root tag's own line, which carries the "<file> : <date>" stamp.
    newline = content_stripped.find('\n')
    if newline < 0:
        return False
    for line in content_stripped[newline + 1:].splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        return stripped.startswith('<') and not stripped.startswith('</')
    return False


class SGMLParser:
    @staticmethod
    def detect_format(content: str) -> SGMLFormatType:
        """Detect SGML format based on root element"""
        # First check for valid SGML structure before checking for HTML content
        content_stripped = content.lstrip()

        # Check for valid SGML formats first
        if content_stripped.startswith('<SUBMISSION>'):
            return SGMLFormatType.SUBMISSION
        elif '<SEC-DOCUMENT>' in content:
            return SGMLFormatType.SEC_DOCUMENT
        elif '<IMS-DOCUMENT>' in content:
            # For old filings from the 1990's
            return SGMLFormatType.SEC_DOCUMENT
        elif '<DOCUMENT>' in content[:1000]:
            # For old filings from the 1990's
            return SGMLFormatType.SEC_DOCUMENT
        elif content_stripped.startswith(_HEADER_ROOT_TAGS):
            # Pre-2004: EDGAR sometimes serves the .hdr.sgml artifact as the
            # submission text file. There is no <SEC-DOCUMENT> wrapper and often
            # no document body at all. Route on the header dialect, since the two
            # are read by different parsers.
            return (SGMLFormatType.SUBMISSION
                    if _is_tagged_header_dialect(content_stripped)
                    else SGMLFormatType.SEC_DOCUMENT)

        # Only check for HTML content if it's not valid SGML structure
        # This prevents false positives when SGML contains HTML within <TEXT> sections
        if has_html_content(content):
            _raise_sec_html_error(content)

        # Check if we received XML error content (like AWS S3 NoSuchKey errors)
        if content_stripped.startswith('<?xml') and '<Error>' in content:
            _raise_sec_html_error(content)

        # Provide actionable diagnostics instead of a bare "Unknown SGML format"
        content_lower = content_stripped[:500].lower()
        content_len = len(content)
        preview = content_stripped[:200].replace('\n', ' ').strip()

        # Check for rate-limiting / access denied responses
        if 'request was denied' in content_lower or 'access denied' in content_lower:
            raise ValueError(
                f"SEC request was denied (possible rate limiting or IP block). "
                f"Content length: {content_len}. Preview: {preview!r}"
            )

        # Check for empty or truncated responses
        if content_len < 50:
            raise ValueError(
                f"SEC returned an empty or truncated response ({content_len} bytes). "
                f"This may indicate a transient server issue. Content: {preview!r}"
            )

        # Check for SEC error pages that slipped past HTML detection
        if ('sec' in content_lower and 'error' in content_lower) or 'denied' in content_lower:
            raise ValueError(
                f"SEC returned an error page instead of SGML filing data. "
                f"Content length: {content_len}. Preview: {preview!r}"
            )

        raise ValueError(
            f"Unknown SGML format. Content length: {content_len}. "
            f"Preview: {preview!r}"
        )

    def parse(self, content: str) -> dict:
        """Main entry point for parsing.

        Returns a dict with keys: format, header, documents.
        For SUBMISSION format, also includes parsed header structure (FILER, etc.).
        Documents are dicts with: type, sequence, filename, description, content,
        plus _content_start and _content_end offsets into the original content string.
        """
        if len(content) > _MAX_CONTENT_SIZE:
            raise ValueError(
                f"Content size ({len(content):,} bytes) exceeds maximum ({_MAX_CONTENT_SIZE:,} bytes). "
                "This may indicate corrupted input."
            )
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


# Known section tags that can contain nested content (SUBMISSION format)
_SECTION_TAGS = frozenset({
    'FILER',
    'OWNER-DATA',
    'COMPANY-DATA',
    'REPORTING-OWNER',
    'ISSUER',
    'DEPOSITOR',
    'SECURITIZER',
    'UNDERWRITER',
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
    'EXISTING-SERIES-AND-CLASSES-CONTRACTS',
    'RULE',
    'ITEM'
})

# Tags that can appear multiple times and should be stored as lists
_REPEATABLE_TAGS = frozenset({
    'FILER',
    'REPORTING-OWNER',
    'UNDERWRITER',
    'SERIES',
    'CLASS-CONTRACT',
    'FORMER-COMPANY',
    'SUBJECT-COMPANY',
    'ITEM'
})


class SubmissionFormatParser:
    """Parser for <SUBMISSION> style SGML (modern format).

    The header section (before <DOCUMENT>) is parsed line-by-line to build
    a hierarchical dict structure. Documents are extracted using str.find()
    offset scanning for performance.
    """

    def __init__(self):
        self.data = {
            'format': SGMLFormatType.SUBMISSION,
            'header': '',
            'documents': [],
        }
        self.current_path = []  # Stack to track current position in hierarchy
        self.header_lines = []
        self.in_documents = False

    def _get_current_context(self) -> dict:
        """Navigate to current position in data hierarchy."""
        context = self.data
        for tag, index in self.current_path:
            if index is not None:
                context = context[tag][index]
            else:
                context = context[tag]
        return context  # type: ignore[return-value]

    def _handle_header_line(self, line: str) -> None:
        """Classify and handle a single header line."""
        stripped = line.strip()
        if not stripped:
            return

        if stripped.startswith('</'):
            # Section end
            tag = stripped[2:-1]
            if self.current_path:
                current_tag, _ = self.current_path[-1]
                if tag != current_tag:
                    raise ValueError(f"Mismatched tags: expected </{current_tag}>, got </{tag}>")
                self.current_path.pop()
            return

        if stripped.startswith('<') and stripped.endswith('>'):
            tag = stripped[1:-1]
            if tag in _SECTION_TAGS:
                # Section start
                current_context = self._get_current_context()
                if tag not in current_context:
                    current_context[tag] = [] if tag in _REPEATABLE_TAGS else {}
                if tag in _REPEATABLE_TAGS:
                    current_context[tag].append({})
                    self.current_path.append((tag, len(current_context[tag]) - 1))
                else:
                    self.current_path.append((tag, None))
                return
            # Empty tag (not a section, no value)
            current_context = self._get_current_context()
            current_context[tag] = ""
            return

        if stripped.startswith('<') and '>' in stripped and not stripped.startswith('</'):
            # Data tag: <TAG>value or unclosed tag like <ITEMS>06b
            tag_end = stripped.index('>')
            tag = stripped[1:tag_end]
            value = stripped[tag_end + 1:].strip()

            current_context = self._get_current_context()
            if tag in current_context:
                if not isinstance(current_context[tag], list):
                    current_context[tag] = [current_context[tag]]
                current_context[tag].append(value)
            else:
                current_context[tag] = value

    def parse(self, content: str) -> dict:
        """Parse SGML content in SUBMISSION format.

        Header is parsed line-by-line for structure.
        Documents are extracted using fast str.find() scanning.
        """
        # Find the first <DOCUMENT> to split header from documents
        first_doc = content.find('<DOCUMENT>')

        # Parse header section line-by-line (typically small, <2KB)
        if first_doc >= 0:
            header_text = content[:first_doc]
        else:
            header_text = content

        self.data['header'] = header_text
        for line in header_text.splitlines():
            self.header_lines.append(line)
            self._handle_header_line(line)

        # Extract documents using str.find() offset scanning
        if first_doc >= 0:
            self.data['documents'] = _extract_all_documents(content, first_doc)

        return self.data


class SecDocumentFormatParser:
    """Parser for <SEC-DOCUMENT> style SGML (older format).

    Uses str.find() for header boundary and document extraction.
    """

    def __init__(self):
        self.data = {
            'format': SGMLFormatType.SEC_DOCUMENT,
            'header': '',
            'documents': [],
            'filer': {}
        }

    def parse(self, content: str) -> dict:
        """Parse SGML content in SEC-DOCUMENT format."""
        # Extract header using str.find()
        for hdr_start_tag, hdr_end_tag in (
            ('<SEC-HEADER>', '</SEC-HEADER>'),
            ('<IMS-HEADER>', '</IMS-HEADER>'),
        ):
            hdr_start = content.find(hdr_start_tag)
            if hdr_start >= 0:
                hdr_end = content.find(hdr_end_tag, hdr_start)
                if hdr_end >= 0:
                    # Extract header text (skip the tag line itself)
                    inner_start = content.find('\n', hdr_start)
                    if inner_start >= 0 and inner_start < hdr_end:
                        self.data['header'] = content[inner_start + 1:hdr_end]
                    else:
                        self.data['header'] = content[hdr_start + len(hdr_start_tag):hdr_end]
                break

        # Extract documents using str.find() offset scanning
        first_doc = content.find('<DOCUMENT>')
        if first_doc >= 0:
            self.data['documents'] = _extract_all_documents(content, first_doc)

        return self.data


def _extract_all_documents(content: str, start_pos: int = 0) -> list:
    """Extract all documents from content using str.find() offset scanning.

    Returns list of dicts with metadata + content reference offsets.
    """
    documents = []
    pos = start_pos

    while True:
        doc_start = content.find('<DOCUMENT>', pos)
        if doc_start < 0:
            break
        doc_end = content.find('</DOCUMENT>', doc_start)
        if doc_end < 0:
            # Structural proof of truncation, not a heuristic: EDGAR always closes
            # <DOCUMENT>. Continuing here silently returned a partial submission —
            # 0 documents when the cut fell inside the first one (edgartools-88ml).
            raise ValueError(
                f"Truncated SGML content: <DOCUMENT> at offset {doc_start:,} has no "
                f"matching </DOCUMENT> ({len(content):,} bytes total, "
                f"{len(documents)} complete document(s) before the cut). "
                "The submission was cut off mid-document — if it was downloaded, "
                "the transfer likely failed partway; re-download it or clear the cached copy."
            )

        inner_start = doc_start + 10  # len('<DOCUMENT>')
        metadata = _extract_doc_metadata(content, inner_start, doc_end)
        metadata['content'] = content  # reference, not copy
        metadata['_content_start'] = inner_start
        metadata['_content_end'] = doc_end

        documents.append(metadata)
        pos = doc_end + 11  # len('</DOCUMENT>')

    return documents


def list_documents(content: str) -> list[SGMLDocument]:
    """
    Convenience method to parse all documents from content into a list.

    Args:
        content: The content string to parse

    Returns:
        List of SGMLDocument objects
    """
    return list(iter_documents(content))


def iter_documents(content: str) -> Iterator[SGMLDocument]:
    """
    Yield SGMLDocument objects from SGML content using fast str.find() scanning.

    Args:
        content: The content string to parse

    Yields:
        SGMLDocument objects containing the parsed content
    """
    pos = 0
    while True:
        doc_start = content.find('<DOCUMENT>', pos)
        if doc_start < 0:
            break
        doc_end = content.find('</DOCUMENT>', doc_start)
        if doc_end < 0:
            # Same truncation contract as _extract_all_documents (edgartools-88ml).
            raise ValueError(
                f"Truncated SGML content: <DOCUMENT> at offset {doc_start:,} has no "
                f"matching </DOCUMENT> ({len(content):,} bytes total). "
                "The submission was cut off mid-document — if it was downloaded, "
                "the transfer likely failed partway; re-download it or clear the cached copy."
            )

        inner_start = doc_start + 10
        metadata = _extract_doc_metadata(content, inner_start, doc_end)
        yield SGMLDocument.from_content_ref(metadata, content, inner_start, doc_end)
        pos = doc_end + 11


def parse_document(document_str: str) -> SGMLDocument:
    """
    Parse a single SGML document section, maintaining raw content.
    """
    metadata = _extract_doc_metadata(document_str, 0, len(document_str))
    return SGMLDocument(
        type=metadata['type'],
        sequence=metadata['sequence'],
        filename=metadata['filename'],
        description=metadata['description'],
        _content_ref=document_str,
        _content_start=0,
        _content_end=len(document_str),
    )

"""
Handles the parsing of SGML documents from the SEC EDGAR database.
"""
import re

from pydantic import BaseModel

from edgar.httprequests import stream_with_retry
from pathlib import Path

__all__ = ['SgmlDocument', 'stream_documents']


class SgmlDocument(BaseModel):
    type: str
    sequence: str
    filename: str
    description: str
    text_content: str = ""

    def __str__(self):
        return f"Document(type={self.type}, sequence={self.sequence}, filename={self.filename}, description={self.description})"

    def __repr__(self):
        return f"Document(type={self.type}, sequence={self.sequence}, filename={self.filename}, description={self.description})"


def strip_tags(text: str, start_tag: str, end_tag: str) -> str:
    if text.startswith(start_tag) and text.endswith(end_tag):
        return text[len(start_tag):-len(end_tag)].strip()
    return text


def parse_document(document_str: str) -> SgmlDocument:
    fields_pattern = re.compile(
        r'<TYPE>([^\n<]+)\s*'
        r'<SEQUENCE>([^\n<]+)\s*'
        r'<FILENAME>([^\n<]+)\s*'
        r'(?:<DESCRIPTION>([^\n<]+)\s*)?',
        re.DOTALL
    )
    text_pattern = re.compile(r'<TEXT>(.*?)</TEXT>', re.DOTALL)

    fields_match = fields_pattern.search(document_str)
    text_match = text_pattern.search(document_str)

    # Check and strip XML or HTML tags from text content
    text_content = text_match.group(1).strip() if text_match else ""
    text_content = strip_tags(text_content, '<XML>', '</XML>')
    text_content = strip_tags(text_content, '<HTML>', '</HTML>')

    return SgmlDocument(
        type=fields_match.group(1).strip() if fields_match else "",
        sequence=fields_match.group(2).strip() if fields_match else "",
        filename=fields_match.group(3).strip() if fields_match else "",
        description=fields_match.group(4).strip() if fields_match and fields_match.group(4) else "",
        text_content=text_content
    )


def stream_documents(source):
    if isinstance(source, str) and source.startswith('http'):
        # Handle URL
        for response in stream_with_retry(source):
            yield from process_stream(response.iter_lines())
    elif isinstance(source, (str, Path)):
        # Handle file path
        file_path = Path(source)
        with file_path.open('r') as file:
            yield from process_stream(file)
    else:
        raise ValueError("Source must be a URL or a file path")


def process_stream(line_iterable):
    document_str = ""
    in_document = False
    for line in line_iterable:
        if '<DOCUMENT>' in line:
            in_document = True
            document_str = line
        elif '</DOCUMENT>' in line:
            in_document = False
            document_str += line
            document = parse_document(document_str)
            if document:
                yield document
            document_str = ""
        elif in_document:
            document_str += line

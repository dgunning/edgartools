"""Press release attachment classes for 8-K filings."""
from functools import lru_cache
from typing import Optional

from edgar._filings import Attachment, Attachments
from edgar._markdown import MarkdownContent
from edgar.files.html_documents import HtmlDocument
from edgar.richtools import repr_rich

__all__ = ['PressRelease', 'PressReleases']


class PressReleases:
    """
    Represent the attachment on an 8-K filing that could be press releases
    """

    def __init__(self, attachments: Attachments):
        self.attachments: Attachments = attachments

    def __len__(self):
        return len(self.attachments)

    def __getitem__(self, item):
        attachment = self.attachments.get_by_index(item)
        if attachment:
            return PressRelease(attachment)

    def __rich__(self):
        return self.attachments.__rich__()

    def __repr__(self):
        return repr_rich(self.__rich__())


class PressRelease:
    """
    Represents a press release attachment from an 8-K filing
    With the Type EX-99.1
    """

    def __init__(self, attachment: Attachment):
        self.attachment: Attachment = attachment

    def url(self):
        return self.attachment.url

    @property
    def document(self) -> str:
        return self.attachment.document

    @property
    def description(self) -> str:
        return self.attachment.description

    @lru_cache(maxsize=1)
    def html(self) -> Optional[str]:
        content = self.attachment.download()
        if content is None:
            return None
        if isinstance(content, bytes):
            return content.decode('utf-8', errors='replace')
        return content

    def text(self) -> Optional[str]:
        html = self.html()
        if html:
            return HtmlDocument.from_html(html, extract_data=False).text
        return None

    def open(self):
        self.attachment.open()

    def view(self):
        return self.to_markdown().view()

    def to_markdown(self):
        html = self.html()
        markdown_content = MarkdownContent.from_html(html, title="8-K Press Release")
        return markdown_content

    def __rich__(self):
        return self.to_markdown()

    def __repr__(self):
        return repr_rich(self.__rich__())

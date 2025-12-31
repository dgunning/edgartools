from dataclasses import dataclass

__all__ = ["ExtractedSection"]


@dataclass
class ExtractedSection:
    """
    Extracted section with LLM-optimized markdown.

    Attributes:
        title: Section title
        markdown: Markdown content
        source: Source identifier (e.g., 'xbrl:IncomeStatement', 'item:1', 'notes:xbrl:5')
        is_xbrl: Whether content comes from XBRL data
    """
    title: str
    markdown: str
    source: str
    is_xbrl: bool = False

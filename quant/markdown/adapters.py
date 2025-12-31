from typing import List, Optional

from edgar.core import log

__all__ = [
    "get_item_section",
    "get_section_text",
    "get_available_sections",
    "get_section_info",
]


def get_item_section(doc, item: str, part: Optional[str] = None):
    """
    Resolve a section by item name with optional part.

    Uses doc.get_section/doc.sections if available, with a safe fallback
    for older Document implementations.
    """
    if hasattr(doc, "get_section"):
        try:
            return doc.get_section(item, part=part)
        except Exception:
            pass

    sections = getattr(doc, "sections", None)
    if not sections:
        return None

    if hasattr(sections, "get_item"):
        try:
            return sections.get_item(item, part=part)
        except Exception:
            return None

    item_clean = item.replace("Item ", "").replace("item ", "").strip().upper()
    part_clean = part.replace("Part ", "").replace("part ", "").strip().upper() if part else None
    for _, section in sections.items():
        sec_item = getattr(section, "item", None)
        sec_part = getattr(section, "part", None)
        if sec_item and sec_item.upper() == item_clean:
            if part_clean is None:
                return section
            if sec_part and sec_part.upper() == part_clean:
                return section
    return None


def get_section_text(doc, section_name: str, clean: bool = True, include_subsections: bool = True) -> Optional[str]:
    """
    Extract section text using built-in helpers when available.
    """
    if hasattr(doc, "get_sec_section"):
        try:
            return doc.get_sec_section(section_name, clean=clean, include_subsections=include_subsections)
        except Exception as exc:
            log.debug(f"get_sec_section failed for {section_name}: {exc}")

    section = get_item_section(doc, section_name)
    if section:
        try:
            return section.text()
        except Exception as exc:
            log.debug(f"Section text extraction failed for {section_name}: {exc}")
    return None


def get_available_sections(doc) -> List[str]:
    """
    List SEC section names available for extraction.
    """
    if hasattr(doc, "get_available_sec_sections"):
        try:
            return doc.get_available_sec_sections()
        except Exception:
            return []
    sections = getattr(doc, "sections", None)
    if not sections:
        return []
    return [getattr(sec, "title", name) for name, sec in sections.items()]


def get_section_info(doc, section_name: str):
    """
    Return metadata for a section if supported by the Document implementation.
    """
    if hasattr(doc, "get_sec_section_info"):
        try:
            return doc.get_sec_section_info(section_name)
        except Exception:
            return None
    return None

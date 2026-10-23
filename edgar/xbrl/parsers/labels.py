"""
Labels parser for XBRL documents.

This module handles parsing of XBRL label linkbases and extracting
element labels for display purposes.
"""

import sys
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from lxml import etree as ET

from edgar.xbrl.core import STANDARD_LABEL, extract_element_id
from edgar.xbrl.models import ElementCatalog, XBRLProcessingError
from edgar.xmltools import xml_parser

from .base import BaseParser


def _english_rank(lang: str) -> Optional[int]:
    """
    Rank an xml:lang value among English variants: 0 for en-US, 1 for en, 2 for
    any other en-* (en-GB, ...), None for a language that is not English.

    XBRL 2.1 section 5.2.2.2 lets a label carry any language code, and the IFRS
    taxonomy writes "en" (GH #1744). The code is matched without case.
    """
    lang = lang.lower()
    if lang == 'en-us':
        return 0
    if lang == 'en':
        return 1
    if lang.startswith('en-'):
        return 2
    return None


def _english_labels(labels_by_lang: Dict[str, Dict[str, str]]) -> Dict[str, Tuple[int, str]]:
    """
    A label resource set's English labels by role, each with its language rank.
    An en-US label wins over en, and en over other English variants; empty when
    no label is English.
    """
    best: Dict[str, Tuple[int, str]] = {}
    for lang in sorted(labels_by_lang):
        rank = _english_rank(lang)
        if rank is None:
            continue
        for role, text in labels_by_lang[lang].items():
            held = best.get(role)
            if held is None or rank < held[0]:
                best[role] = (rank, text)
    return best


class LabelsParser(BaseParser):
    """Parser for XBRL label linkbases."""

    def __init__(self, element_catalog: Dict[str, ElementCatalog]):
        """
        Initialize labels parser with data structure references.

        Args:
            element_catalog: Reference to element catalog dictionary
        """
        super().__init__()

        # Store references to data structures
        self.element_catalog = element_catalog

        # Language rank of the label held for each (element, role). A filer may
        # write one label resource per language, each with its own arc, so the
        # en-US-first preference has to hold across arcs, not only inside one
        # resource set (GH #1744).
        self._label_ranks: Dict[Tuple[str, str], int] = {}

    def parse_labels(self, file_path: Union[str, Path]) -> None:
        """Parse label linkbase file and extract label information."""
        try:
            content = Path(file_path).read_text()
            self.parse_labels_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing label file {file_path}: {str(e)}") from e

    def parse_labels_content(self, content: str) -> None:
        """Parse label linkbase content and extract label information."""
        try:
            # Optimize: Register namespaces for faster XPath lookups
            nsmap = {
                'link': 'http://www.xbrl.org/2003/linkbase',
                'xlink': 'http://www.w3.org/1999/xlink',
                'xml': 'http://www.w3.org/XML/1998/namespace'
            }

            # Optimize: Use lxml parser with smart string handling
            parser = xml_parser(remove_blank_text=True, recover=True)
            root = ET.XML(content.encode('utf-8'), parser)

            # Optimize: Use specific XPath expressions with namespaces for faster lookups
            # This is much faster than using findall with '//' in element tree
            label_arcs = root.xpath('//link:labelArc', namespaces=nsmap)
            labels = root.xpath('//link:label', namespaces=nsmap)

            # Optimize: Pre-allocate dictionary with expected size
            label_lookup = {}

            # Optimize: Cache attribute lookups
            xlink_label = '{http://www.w3.org/1999/xlink}label'
            xlink_role = '{http://www.w3.org/1999/xlink}role'
            xml_lang = '{http://www.w3.org/XML/1998/namespace}lang'
            default_role = 'http://www.xbrl.org/2003/role/label'

            # Intern role URIs: the same ~10 role strings repeat for every element.
            # sys.intern deduplicates them to a single object, saving significant memory.
            _intern = sys.intern
            _role_intern_cache = {}

            def _intern_role(role_str):
                cached = _role_intern_cache.get(role_str)
                if cached is not None:
                    return cached
                interned = _intern(role_str)
                _role_intern_cache[role_str] = interned
                return interned

            # Optimize: Process labels in a single pass with direct attribute access
            for label in labels:
                label_id = label.get(xlink_label)
                if not label_id:
                    continue

                # Get text first - if empty, skip further processing
                text = label.text
                if text is None:
                    continue

                # Get attributes - direct lookup is faster than method calls
                role = _intern_role(label.get(xlink_role, default_role))
                lang = label.get(xml_lang, 'en-US')

                # Create nested dictionaries only when needed
                if label_id not in label_lookup:
                    label_lookup[label_id] = {}

                if lang not in label_lookup[label_id]:
                    label_lookup[label_id][lang] = {}

                label_lookup[label_id][lang][role] = text

            # Optimize: Cache attribute lookups for arcs
            xlink_from = '{http://www.w3.org/1999/xlink}from'
            xlink_to = '{http://www.w3.org/1999/xlink}to'
            xlink_href = '{http://www.w3.org/1999/xlink}href'

            # Optimize: Create a lookup table for locators by label for faster access
            loc_by_label = {}
            for loc in root.xpath('//link:loc', namespaces=nsmap):
                loc_label = loc.get(xlink_label)
                if loc_label:
                    loc_by_label[loc_label] = loc.get(xlink_href)

            # Connect labels to elements using arcs - with optimized lookups
            for arc in label_arcs:
                from_ref = arc.get(xlink_from)
                to_ref = arc.get(xlink_to)

                if not from_ref or not to_ref or to_ref not in label_lookup:
                    continue

                # Use cached locator lookup instead of expensive XPath
                href = loc_by_label.get(from_ref)
                if not href:
                    continue

                # Extract element ID from href
                element_id = extract_element_id(href)

                # Find this element's English labels (en-US, en, en-GB, ...).
                # A lower-ranked language never replaces a label already held
                # in a higher-ranked one, whichever arc came first.
                ranked_labels = _english_labels(label_lookup[to_ref])
                if ranked_labels:
                    element_labels = {}
                    for role, (rank, text) in ranked_labels.items():
                        key = (element_id, role)
                        held = self._label_ranks.get(key)
                        if held is None or rank <= held:
                            self._label_ranks[key] = rank
                            element_labels[role] = text

                    # Optimize: Update catalog with minimal overhead
                    catalog_entry = self.element_catalog.get(element_id)
                    if catalog_entry:
                        catalog_entry.labels.update(element_labels)
                    else:
                        # A labeled element the filing's own schema does not
                        # declare comes from a schema the filing imports but does
                        # not contain (us-gaap, dei, srt), so its type, period
                        # type and balance are unknown. None says so; "" and
                        # "duration" read as answers, and "duration" is wrong for
                        # every instant concept. The parser fills the period type
                        # in from the facts once the instance is read.
                        self.element_catalog[element_id] = ElementCatalog(
                            name=element_id,
                            data_type=None,
                            period_type=None,
                            labels=element_labels
                        )

        except Exception as e:
            raise XBRLProcessingError(f"Error parsing label content: {str(e)}") from e

    def get_element_label(self, element_id: str) -> str:
        """Get the label for an element, falling back to the element ID if not found."""
        if element_id in self.element_catalog and self.element_catalog[element_id].labels:
            # Use standard label if available
            standard_label = self.element_catalog[element_id].labels.get(STANDARD_LABEL)
            if standard_label:
                return standard_label
        return element_id  # Fallback to element ID

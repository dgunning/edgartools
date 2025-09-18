from decimal import Decimal
from typing import List, Optional, Tuple, Union

from bs4 import BeautifulSoup, Tag

__all__ = [
    'child_text',
    'child_value',
    'child_texts',
    'find_element',
    'get_footnote_ids',
    'optional_decimal',
    'value_or_footnote',
    'extract_child_text',
    'extract_child_value',
    'value_with_footnotes',
]


def find_element(
        xml_tag_or_string: Union[str, BeautifulSoup, Tag],
        element_name) -> Tag:
    """
    Find the element with that name in the string or Tag
    :param xml_tag_or_string: either an exml tag or string containing xml
    :param element_name: The name of the element to find
    :return: An element
    """
    if isinstance(xml_tag_or_string, Tag):
        return xml_tag_or_string.find(element_name)
    elif isinstance(xml_tag_or_string, str) and "<" in xml_tag_or_string:
        soup: BeautifulSoup = BeautifulSoup(xml_tag_or_string, features="xml")
        return soup.find(element_name)


def get_footnote_ids(tag: Tag,
                     sep: str = ',') -> str:
    """Get the footnotes from the tag as a string"""
    return sep.join([
        el.attrs.get('id') for el in tag.find_all("footnoteId")
    ])


def value_with_footnotes(tag: Tag,
                         footnote_sep: str = ",") -> str:
    """Get the value from the tag, including footnotes if there are any
    Example: Given this xml
        <underlyingSecurityTitle>
            <value>Class B Common Stock</value>
            <footnoteId id="F2"/>
            <footnoteId id="F3"/>
        </underlyingSecurityTitle>

        return "Class B Common Stock [F2,F3]"
    """
    value_tag = tag.find('value')
    value = value_tag.text if value_tag else ""

    footnote_ids = get_footnote_ids(tag, footnote_sep)
    footnote_str = f"[{footnote_ids}]" if footnote_ids else ""
    if value:
        return f"{value} {footnote_str}" if footnote_str else value
    return footnote_str


def value_or_footnote(el: Tag) -> Optional[str]:
    value_el = el.find('value')
    if value_el:
        return value_el.text.strip()
    else:
        footnote = el.find('footnote')
        if not footnote:
            footnote = el.find("footnoteId")
        if footnote:
            return footnote.attrs['id']


def child_text(parent: Tag,
               child: str) -> Optional[str]:
    """
    Get the text of the child element if it exists or None
    :param parent: The parent tag
    :param child: The name of the child element
    :return: the text of the child element if it exists or None
    """
    el = parent.find(child)
    if el:
        return el.text.strip()


def child_value(parent: Tag,
                child: str,
                default_value: str = None) -> str:
    """
    Get the text of the value tag within the child tag if it exists or None

    :param parent: The parent tag
    :param child: The name of the child element
    :param default_value: The default value to return if the value is None
    :return: the text of the child element if it exists or None
    """
    el = parent.find(child)
    if el:
        return value_with_footnotes(el)
    return default_value


def child_texts(parent: Tag,
                child: str) -> List[str]:
    """
    Get the text of the value tag within the child tag if it exists or None

    :param parent: The parent tag
    :param child: The name of the child element
    :return: the text of the child element if it exists or None
    """
    return [el.text for el in parent.find_all(child)]


def optional_decimal(parent: Tag,
                     child: str) -> Optional[Decimal]:
    text = child_text(parent, child)
    if text:
        if text == "N/A":
            return None
        return Decimal(text)


def extract_child_text(tag: Tag,
                       key: str,
                       child_tag_name: str) -> Tuple[str, str]:
    """Get the child text from the tag and return a Tuple (key, child_value)
      Useful for populating dicts

      :param tag The element
      :param key The dict key to use to pupulate the dict or DataFrame
      :param child_tag_name The child tag name
    """
    return key, child_text(tag, child_tag_name)


def extract_child_value(tag: Tag,
                        key: str,
                        child_tag_name: str) -> Tuple[str, str]:
    """Get the child value from the tag and return a Tuple (key, child_value)
      Useful for populating dicts
      :param tag The element
      :param key The dict key to use to pupulate the dict or DataFrame
      :param child_tag_name The child tag name
    """
    return key, child_value(tag, child_tag_name)

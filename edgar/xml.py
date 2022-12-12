from bs4 import Tag
from typing import Optional


def value_or_footnote(el: Tag) -> Optional[str]:
    value_el = el.find('value')
    if value_el:
        return value_el.text.strip()
    else:
        footnote = el.find('footnote')
        if footnote:
            return footnote.attrs['id']


def child_text(parent: Tag,
               child: str):
    el = parent.find(child)
    if el:
        return el.text


def child_value(parent: Tag,
                child: str,
                default_value: str = None) -> str:
    el = parent.find(child)
    if el:
        return value_or_footnote(el)
    return default_value

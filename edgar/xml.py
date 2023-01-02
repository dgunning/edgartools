from bs4 import Tag
from typing import Optional

__all__ = [
    'child_text',
    'child_value',
    'value_or_footnote',
    'child_value_or_footnote'
]


def value_or_footnote(el: Tag) -> Optional[str]:
    value_el = el.find('value')
    if value_el:
        return value_el.text.strip()
    else:
        footnote = el.find('footnote')
        if footnote:
            return footnote.attrs['id']


def child_value_or_footnote(parent: Tag,
                            child: str):
    el = parent.find(child)
    if el:
        return value_or_footnote(el)


def child_text(parent: Tag,
               child: str):
    el = parent.find(child)
    if el:
        return el.text.strip()


def child_value(parent: Tag,
                child: str,
                default_value: str = None) -> str:
    el = parent.find(child)
    if el:
        return value_or_footnote(el)
    return default_value

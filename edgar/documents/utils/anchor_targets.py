"""Utilities for resolving and matching SEC anchor targets."""


def find_anchor_targets(tree, anchor_id: str):
    """Find elements matching an anchor target via either id or name."""
    if not anchor_id:
        return []

    return tree.xpath('//*[@id=$anchor_id or @name=$anchor_id]', anchor_id=anchor_id)


def is_anchor_match(element, anchor_id: str) -> bool:
    """Return True if an element matches the given anchor by id or name."""
    if not anchor_id:
        return False

    return element.get('id', '') == anchor_id or element.get('name', '') == anchor_id

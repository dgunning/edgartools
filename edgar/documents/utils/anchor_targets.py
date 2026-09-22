"""Utilities for resolving and matching SEC anchor targets."""

from weakref import WeakKeyDictionary

# One anchor index per document tree.
#
# Anchor resolution used to run a full-document XPath per lookup, and section
# extraction calls it from eleven sites: on a 9.8MB 10-K that was 92 calls
# resolving 30 distinct ids against one tree, 3,854ms — 60% of the whole
# sections stage — with 67% of calls re-resolving an id already looked up on the
# same tree (edgartools-llmp.7). One index pass costs ~31ms on that document and
# serves every subsequent lookup.
#
# Keyed weakly on the document root element so the index dies with the tree.
# lxml.html elements support weak references (lxml.etree._ElementTree does not,
# which is why the key is normalized to the root element), and a weak key avoids
# the id()-reuse hazard of caching on id(tree) — lxml materializes element
# proxies on demand, so an id() is only unique while a proxy is alive.
#
# Safe to cache because nothing in the section-extraction path mutates a shared
# tree: section_slicer deep-copies elements before re-parenting them precisely so
# that re-parenting cannot mutate the source (see its ``_clone``). A caller that
# does mutate a tree must drop the entry via ``invalidate_anchor_index``.
_ANCHOR_INDEX_CACHE: "WeakKeyDictionary" = WeakKeyDictionary()


def _document_root(tree):
    """Normalize an element or ElementTree to the document root element.

    ``tree.xpath('//*[...]')`` is an absolute path — it searches from the
    document root no matter which element it is called on — so an index built by
    walking a subtree would resolve fewer anchors than the XPath it replaces.
    Both entry points converge here.

    ``getroot()`` returns an identity-stable proxy, which is what makes it usable
    as a cache key; ``getroottree()`` builds a fresh wrapper each call and is not.
    """
    getroot = getattr(tree, 'getroot', None)
    if getroot is not None:          # an _ElementTree
        return getroot()
    getroottree = getattr(tree, 'getroottree', None)
    if getroottree is not None:      # an element
        return getroottree().getroot()
    return tree


def _build_anchor_index(root):
    """Map every anchor id/name to its elements, in document order.

    Mirrors ``//*[@id=$a or (self::a and @name=$a)]`` exactly:
      * ``//*`` selects elements only, so comments and processing instructions
        (which ``iter()`` also yields) are skipped via the ``str`` tag check.
      * the ``or`` means an ``<a>`` carrying the same value as both ``id`` and
        ``name`` matches once, not twice — hence the ``name != anchor_id`` guard.
      * ``iter()`` yields document order, which is the order XPath returns.
    """
    index: dict = {}
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        anchor_id = el.get('id')
        if anchor_id:
            index.setdefault(anchor_id, []).append(el)
        if el.tag == 'a':
            name = el.get('name')
            if name and name != anchor_id:
                index.setdefault(name, []).append(el)
    return index


def _anchor_index(tree):
    """Index for ``tree``'s document, building and caching it on first use.

    Returns None when the tree cannot serve as a weak key, so the caller falls
    back to the XPath rather than failing.
    """
    try:
        root = _document_root(tree)
    except Exception:
        return None

    try:
        index = _ANCHOR_INDEX_CACHE.get(root)
    except TypeError:
        return None  # unhashable or not weak-referenceable

    if index is None:
        index = _build_anchor_index(root)
        try:
            _ANCHOR_INDEX_CACHE[root] = index
        except TypeError:
            pass  # usable for this call, just not cacheable
    return index


def invalidate_anchor_index(tree) -> None:
    """Drop the cached index for ``tree``'s document.

    Only needed if a caller mutates a tree's ids, names or structure after
    anchors have been resolved against it. No current code path does.
    """
    try:
        _ANCHOR_INDEX_CACHE.pop(_document_root(tree), None)
    except TypeError:
        pass


def find_anchor_targets(tree, anchor_id: str):
    """Find elements matching an anchor target via either id or name."""
    if not anchor_id:
        return []

    index = _anchor_index(tree)
    if index is None:
        return tree.xpath('//*[@id=$anchor_id or (self::a and @name=$anchor_id)]', anchor_id=anchor_id)

    # Copy so a caller mutating the result cannot corrupt the cached index.
    return list(index.get(anchor_id, ()))


def is_anchor_match(element, anchor_id: str) -> bool:
    """Return True if an element matches the given anchor by id or name."""
    if not anchor_id:
        return False

    if element.get('id', '') == anchor_id:
        return True
    return element.tag == 'a' and element.get('name', '') == anchor_id

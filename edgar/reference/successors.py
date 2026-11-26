"""
Successor registrants: companies whose history SEC left under an earlier CIK.

When a company forms a holding company or redomiciles, SEC moves its ticker to a
new CIK and its filing history stays on the old one. ``successor_registrants.csv``
lists the pairs reviewed by hand (GH #1821).

New successions arrive as ``successor-review`` issues from the weekly scan in
``scripts/scan_successor_registrants.py``. Add a row only for a continuation: the
successor holds the ticker, the predecessor stopped filing 10-Ks and 10-Qs at the
succession, at most 5% of shared facts differ, and it is not a merger.
"""
from functools import lru_cache
from typing import Dict, List, NamedTuple, Optional, Union

from edgar.reference.data.common import read_csv_from_package

__all__ = ['Predecessor', 'get_predecessor', 'get_predecessor_chain', 'get_successor']


class Predecessor(NamedTuple):
    """The registrant whose history a successor registrant continues."""
    cik: int
    effective_date: str
    evidence_accession: str


@lru_cache(maxsize=1)
def _get_predecessor_lookup() -> Dict[int, Predecessor]:
    df = read_csv_from_package('successor_registrants.csv', dtype=str)
    return {int(row.successor_cik): Predecessor(int(row.predecessor_cik), row.effective_date, row.evidence_accession)
            for row in df.itertuples(index=False)}


def _normalize_cik(cik: Union[int, str]) -> Optional[int]:
    try:
        return int(str(cik).lstrip('0') or 0)
    except (TypeError, ValueError):
        return None


def get_predecessor(cik: Union[int, str]) -> Optional[Predecessor]:
    """
    Get the predecessor of a successor registrant, if it continues one.

    When a company forms a holding company or redomiciles, SEC moves its ticker to a
    new CIK and its filing history stays on the old one: XOM moved from Exxon Mobil
    Corp (34088) to ExxonMobil Holdings Corp (2115436) on 2026-07-01 (GH #1821). An
    8-K12B marks the succession but is often a merger rather than a continuation,
    so ``successor_registrants.csv`` lists only pairs reviewed by hand, whose facts
    agree where both CIKs report them.

    :param cik: The successor's CIK
    :return: A Predecessor, or None if this CIK has no listed predecessor
    """
    cik = _normalize_cik(cik)
    return None if cik is None else _get_predecessor_lookup().get(cik)


def get_predecessor_chain(cik: Union[int, str]) -> List[Predecessor]:
    """
    Every registrant a successor continues, nearest first.

    A company that succeeded a registrant which had itself succeeded another has a
    chain of two; each link keeps its own effective date. A CIK seen twice ends the
    walk, so a mistaken cycle in the CSV cannot loop.

    :param cik: The successor's CIK
    :return: The predecessors, nearest first; empty if this CIK has none
    """
    chain: List[Predecessor] = []
    seen = {_normalize_cik(cik)}
    predecessor = get_predecessor(cik)
    while predecessor is not None and predecessor.cik not in seen:
        chain.append(predecessor)
        seen.add(predecessor.cik)
        predecessor = get_predecessor(predecessor.cik)
    return chain


@lru_cache(maxsize=1)
def _get_successor_lookup() -> Dict[int, int]:
    return {predecessor.cik: successor for successor, predecessor in _get_predecessor_lookup().items()}


def get_successor(cik: Union[int, str]) -> Optional[int]:
    """
    The CIK of the registrant that continues this one, if a reviewed succession lists it.

    Exxon Mobil Corp (34088) is continued by ExxonMobil Holdings Corp (2115436).

    :param cik: The predecessor's CIK
    :return: The successor's CIK, or None
    """
    cik = _normalize_cik(cik)
    return None if cik is None else _get_successor_lookup().get(cik)

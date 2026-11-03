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
from typing import Dict, NamedTuple, Optional, Union

from edgar.reference.data.common import read_csv_from_package

__all__ = ['Predecessor', 'get_predecessor']


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
    try:
        cik = int(str(cik).lstrip('0') or 0)
    except (TypeError, ValueError):
        return None
    return _get_predecessor_lookup().get(cik)

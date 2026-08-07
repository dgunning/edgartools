"""
Regression test for Issue fu3x: ShelfLifecycle date anchoring.

Beads: edgartools-fu3x

Bug: ShelfLifecycle conflated two distinct shelf facts into one filing.
  - `shelf_registration` returned the first shelf-base form in `_related`
    ordering rather than an explicitly-selected one, so its result depended
    on `get_filings` sort order (fragile, impact #3).
  - `shelf_expires` was anchored on the *filed* date rather than current
    effectiveness, so for a re-registered shelf it reported the shelf as long
    expired (a 2013-originated shelf re-registered in 2025 reported as expired
    in 2016).

Fix: split one fact into two, each selected explicitly by date:
  - `shelf_registration` / `shelf_filed_date` -> the EARLIEST shelf-base form
    (vintage; order-independent via min-by-filing_date).
  - `effective_date` -> the EARLIEST EFFECT (initial review period).
  - `current_effective_date` -> the LATEST EFFECT, with an ASR fallback to the
    latest automatic-shelf filing (operative effectiveness).
  - `shelf_expires` -> current_effective_date + 3 years (Rule 415(a)(5)/(6)),
    so a genuine re-registration resets the clock while a cosmetic amendment
    does not.

Ground truth verified by hand against SEC EDGAR on 2026-06-18.
"""
from datetime import date

import pytest

from edgar import Company
from edgar.offerings.prospectus import ShelfLifecycle


def _lifecycle(cik, file_number):
    """Build a ShelfLifecycle from a shelf family, current filing = latest."""
    filings = Company(cik).get_filings(
        file_number=file_number,
        sort_by=[("filing_date", "ascending"), ("accession_number", "ascending")],
        trigger_full_load=False,
    )
    return ShelfLifecycle(filings[-1], filings)


@pytest.mark.network
def test_first_bancshares_re_registered_shelf():
    """333-188922: 2013 S-3 re-registered 2025; vintage 2013, expiry 2028.

    Family: S-3 2013-05-29, S-3/A 2013-06-17, EFFECT 2013-06-27,
            S-3/A 2025-04-07, POS AM 2025-04-08, EFFECT 2025-04-09.
    """
    lc = _lifecycle(947559, "333-188922")

    # Vintage: the ORIGINAL 2013 S-3, never the 2025 amendment.
    assert lc.shelf_registration.form == "S-3"
    assert str(lc.shelf_registration.filing_date) == "2013-05-29"
    assert lc.shelf_filed_date == "2013-05-29"

    # Initial vs current effectiveness are distinct facts.
    assert lc.effective_date == "2013-06-27"          # first EFFECT
    assert lc.current_effective_date == "2025-04-09"  # latest EFFECT

    # Expiry anchors on CURRENT effectiveness (2025-04-09 + 3y), not the
    # 2013 filing. The shelf is live, not expired in 2016.
    assert lc.shelf_expires == date(2028, 4, 9)
    assert lc.days_to_expiry > 0

    # Review period measured from the ORIGINAL filing/effectiveness.
    assert lc.review_period_days == 29  # 2013-05-29 -> 2013-06-27


@pytest.mark.network
def test_atento_original_registration_not_amendment():
    """333-220065: shelf_registration is the 2017 F-3, not the 2023 F-3/A."""
    lc = _lifecycle("0001606457", "333-220065")

    assert lc.shelf_registration.form == "F-3"
    assert str(lc.shelf_registration.filing_date) == "2017-08-21"
    assert lc.shelf_filed_date == "2017-08-21"

    # Re-registered in 2023: current effectiveness advances past the original.
    assert lc.effective_date == "2017-08-30"
    assert lc.current_effective_date is not None
    assert lc.current_effective_date > lc.effective_date
    assert lc.shelf_expires is not None


@pytest.mark.network
def test_selection_is_order_independent():
    """shelf_registration picks earliest by date regardless of `_related` order.

    Reversing the related-filings order must not change the result (the bug was
    that the outcome depended entirely on sort order).
    """
    filings = Company(947559).get_filings(
        file_number="333-188922",
        sort_by=[("filing_date", "ascending"), ("accession_number", "ascending")],
        trigger_full_load=False,
    )
    forward = ShelfLifecycle(filings[-1], filings)

    # Reverse the related-filings order; selection must not change.
    reversed_filings = list(filings)[::-1]
    backward = ShelfLifecycle(reversed_filings[0], reversed_filings)

    assert forward.shelf_registration.accession_no == backward.shelf_registration.accession_no
    assert forward.shelf_filed_date == backward.shelf_filed_date == "2013-05-29"
    assert forward.current_effective_date == backward.current_effective_date == "2025-04-09"
    assert forward.shelf_expires == backward.shelf_expires == date(2028, 4, 9)

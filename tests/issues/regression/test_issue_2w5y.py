"""
Regression test for Issue 2w5y: ShelfLifecycle derived lifecycle signals.

Beads: edgartools-2w5y (builds on edgartools-fu3x date anchoring)

ShelfLifecycle exposed raw facts but not the derived signals consumers need
(status, effectiveness, re-registration, continuity), forcing every consumer to
re-derive them. These now live on ShelfLifecycle.

The careful one is continuity: 're-registered' is two different business facts.
  - Renewal: new registration effective BEFORE the prior shelf expired
    (Rule 415(a)(6)) — securities/fees carry forward, continuous coverage.
  - Revival: a new shelf effective AFTER the prior one lapsed — a gap with no
    shelf access. Must NOT be reported as 'continuously registered since {orig}'.

Ground truth verified by hand against SEC EDGAR on 2026-06-18/20.
"""
import pytest

from edgar import Company
from edgar.offerings.prospectus import ShelfLifecycle


def _lifecycle(cik, file_number):
    filings = Company(cik).get_filings(
        file_number=file_number,
        sort_by=[("filing_date", "ascending"), ("accession_number", "ascending")],
        trigger_full_load=False,
    )
    return ShelfLifecycle(filings[-1], filings)


@pytest.mark.network
def test_first_bancshares_revival_is_lapsed_not_continuous():
    """333-188922: 2013 shelf expired 2016, revived 2025 — a 9-year gap.

    The naive model would claim continuous registration since 2013; the
    gap-aware continuity logic must instead report 'lapsed' and measure program
    age from the CURRENT (2025) generation, not the dead 2013 one.
    """
    lc = _lifecycle(947559, "333-188922")

    assert lc.is_effective is True
    assert lc.is_re_registered is True
    assert lc.is_automatic_shelf is False
    assert lc.continuity == "lapsed"
    assert lc.has_registration_gap is True

    # Two generations: original 2013 effectiveness, revived 2025 effectiveness.
    assert lc._generations[0].year == 2013
    assert lc._generations[-1].year == 2025

    # status: effective (live, not yet past the 2028 expiry).
    assert lc.status == "effective"

    # program_age measured from the CURRENT generation (2025), so well under the
    # ~12 years that an original-anchored age would (wrongly) report.
    assert lc.program_age_days is not None
    assert lc.program_age_days < 366 * 4


@pytest.mark.network
def test_alzamend_single_generation_is_continuous():
    """Alzamend single-generation S-3 (333-273610): continuous, not re-registered."""
    lc = _lifecycle(1677077, "333-273610")

    assert lc.is_effective is True
    assert lc.is_re_registered is False
    assert lc.has_registration_gap is False
    assert lc.continuity == "continuous"
    assert lc.status == "effective"
    assert len(lc._generations) == 1

    # 5 takedowns off this shelf; standard cadence (<= 50).
    assert lc.total_takedowns == 5
    assert lc.program_mode == "standard"
    assert lc.days_since_last_takedown is not None
    assert lc.days_since_last_takedown >= 0


@pytest.mark.network
def test_status_precedence_and_signals_consistency():
    """Derived signals are internally consistent for a re-registered shelf."""
    lc = _lifecycle("0001606457", "333-220065")  # Atento F-3

    # is_re_registered implies more than one generation.
    assert lc.is_re_registered == (len(lc._generations) > 1)
    # continuity is only one of the two known values when effective.
    assert lc.continuity in ("continuous", "lapsed")
    # has_registration_gap mirrors continuity == 'lapsed'.
    assert lc.has_registration_gap == (lc.continuity == "lapsed")
    # An effective, non-withdrawn shelf is 'effective' or 'expired', never 'registered'.
    assert lc.status in ("effective", "expired")

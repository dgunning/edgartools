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
from datetime import date

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


# ---------------------------------------------------------------------------
# Fast, network-free edge cases (synthetic filings) for the code-review fixes.
# ShelfLifecycle only reads .form, .filing_date, .accession_no off each filing.
# ---------------------------------------------------------------------------

class _FakeFiling:
    def __init__(self, form, filing_date, accession_no="acc"):
        self.form = form
        self.filing_date = date.fromisoformat(filing_date)
        self.accession_no = accession_no


def _lc(related):
    return ShelfLifecycle(related[-1], related)


def test_rw_wd_rescinds_withdrawal_not_withdrawn():
    """'RW WD' rescinds an earlier 'RW' — the registration is NOT withdrawn."""
    lc = _lc([
        _FakeFiling("S-3", "2020-01-01"),
        _FakeFiling("EFFECT", "2020-01-10"),
        _FakeFiling("RW", "2021-01-01"),
        _FakeFiling("RW WD", "2021-02-01"),
    ])
    assert lc.is_withdrawn is False


def test_rw_without_rescission_is_withdrawn():
    """A lone 'RW' withdraws the registration."""
    lc = _lc([
        _FakeFiling("S-3", "2020-01-01"),
        _FakeFiling("EFFECT", "2020-01-10"),
        _FakeFiling("RW", "2021-03-01"),
    ])
    assert lc.is_withdrawn is True
    assert lc.status == "withdrawn"


def test_aw_does_not_withdraw_registration():
    """'AW' withdraws an amendment only, not the registration."""
    lc = _lc([
        _FakeFiling("S-3", "2020-01-01"),
        _FakeFiling("EFFECT", "2020-01-10"),
        _FakeFiling("AW", "2021-03-01"),
    ])
    assert lc.is_withdrawn is False


def test_later_rw_after_rescission_is_withdrawn():
    """A fresh 'RW' after a prior 'RW WD' re-withdraws the registration."""
    lc = _lc([
        _FakeFiling("S-3", "2020-01-01"),
        _FakeFiling("EFFECT", "2020-01-10"),
        _FakeFiling("RW", "2021-01-01"),
        _FakeFiling("RW WD", "2021-02-01"),
        _FakeFiling("RW", "2021-05-01"),
    ])
    assert lc.is_withdrawn is True


def test_mixed_effect_then_asr_uses_latest_effectiveness():
    """An S-3 (EFFECT 2017) re-registered as S-3ASR (2023, no EFFECT).

    current effectiveness must be the 2023 ASR, and shelf_expires/current must
    agree with the latest generation (the #2 EFFECT-first short-circuit bug).
    """
    lc = _lc([
        _FakeFiling("S-3", "2017-08-21"),
        _FakeFiling("EFFECT", "2017-08-30"),
        _FakeFiling("S-3ASR", "2023-06-01"),
    ])
    assert lc.current_effective_date == "2023-06-01"
    assert lc.shelf_expires == date(2026, 6, 1)
    assert str(lc._generations[-1]) == lc.current_effective_date  # internal consistency
    assert lc.is_automatic_shelf is True


def test_takedown_only_old_shelf_is_expired():
    """Effectiveness proven only by takedowns whose latest is > 3y old -> expired.

    EFFECT is outside the loaded window so shelf_expires is None, but a shelf
    cannot take down after expiry, so the latest takedown + 3y bounds it.
    """
    lc = _lc([
        _FakeFiling("424B5", "2018-05-01"),
        _FakeFiling("424B5", "2018-09-01"),
    ])
    assert lc.is_effective is True
    assert lc.shelf_expires is None
    assert lc.status == "expired"


def test_takedown_only_recent_shelf_is_effective():
    """A recent takedown (within 3y) without a visible EFFECT stays 'effective'."""
    lc = _lc([
        _FakeFiling("424B5", "2024-05-01"),
        _FakeFiling("424B5", "2025-09-01"),
    ])
    assert lc.status == "effective"

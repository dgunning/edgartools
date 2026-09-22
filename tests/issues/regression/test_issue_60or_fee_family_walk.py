"""Resolving an amendment's fee exhibit must not download its file-number family.

``RegistrationS1.from_filing`` extracts the fee table eagerly, so ``filing.obj()``
on a registration reaches ``_resolve_fee_source``. That function asked
"does this sibling carry an EX-FILING FEES exhibit?" about every registration in
the family — and the question costs a full ``.txt`` submission download, because
``filing.attachments`` resolves through ``filing.sgml()``.

Measured on Learn CW Investment Corp's S-1 (``0001140361-21-010426``) by wrapping
``httpx.Client.send``: 2,393,430 bytes for the filing the caller asked for, then
3,807,137 + 3,800,905 + 2,191,043 bytes of siblings. 12.2MB transferred for a
2.4MB filing.

None of it could ever pay. Exhibit 107 did not exist before the SEC's filing-fee
modernization rule, so a 2021 family has no exhibit anywhere in it by
construction; ``_resolve_fee_source`` returned None and the correct answer came
from the pre-EX-107 inline body table — ``total_offering_amount`` 287,500,000.0
for Learn CW, 1,000,000,000.0 for Airbnb's S-1, 54,337,500.0 for Unicycive's
S-1/A, all read from HTML already in hand. Same shape on all three.

Two fixes, both about how many siblings get probed rather than which one wins:
siblings filed before the regime are dropped without being probed, and the
survivors are probed in priority order until one hits instead of all being probed
and the maximum taken afterwards. The selection is unchanged — that is what the
ordering tests below pin (bead edgartools-60or).

The families here are the real ones, with the dates and exhibit flags as measured
from EDGAR. Stubs rather than cassettes because the thing under test is how many
downloads happen, and a stub can count them exactly.
"""
import pytest

from edgar.offerings.prospectus._fee_table.extract import (
    _EX107_EARLIEST_FILING_DATE,
    _resolve_fee_source,
)


class StubAttachment:
    def __init__(self, document_type):
        self.document_type = document_type


class StubFiling:
    """A filing that records every time its attachments are read.

    Reading ``.attachments`` is the expensive operation being counted: on a real
    filing it downloads the whole submission.
    """

    def __init__(self, accession_no, form, filing_date, has_exhibit=False,
                 probe_log=None, unreadable=False):
        self.accession_no = accession_no
        self.form = form
        self.filing_date = filing_date
        self._has_exhibit = has_exhibit
        self._probe_log = probe_log if probe_log is not None else []
        self._unreadable = unreadable
        self._family = []

    @property
    def attachments(self):
        self._probe_log.append(self.accession_no)
        if self._unreadable:
            raise OSError(f"could not download {self.accession_no}")
        return [StubAttachment('EX-FILING FEES')] if self._has_exhibit else [
            StubAttachment('EX-99.1')]

    def related_filings(self):
        return self._family


def build_family(subject_spec, sibling_specs):
    """Return (subject, probe_log). Specs are (accession, form, date, has_exhibit)."""
    probe_log = []
    subject = StubFiling(*subject_spec[:3], has_exhibit=subject_spec[3], probe_log=probe_log)
    siblings = [StubFiling(*spec[:3], has_exhibit=spec[3], probe_log=probe_log)
                for spec in sibling_specs]
    family = [subject, *siblings]
    for filing in family:
        filing._family = family
    return subject, probe_log


class TestPreRegimeSiblingsAreNotProbed:
    """The population that could never pay: no exhibit existed yet."""

    def test_airbnb_shaped_family_is_not_downloaded(self):
        """Airbnb's S-1 (0001193125-20-294801) and its two 2020 amendments.

        Both siblings predate Exhibit 107, so neither is worth a download.
        """
        subject, probes = build_family(
            ("0001193125-20-294801", "S-1", "2020-11-16", False),
            [("0001193125-20-306257", "S-1/A", "2020-12-01", False),
             ("0001193125-20-311265", "S-1/A", "2020-12-07", False)],
        )
        assert _resolve_fee_source(subject) is None
        assert probes == []

    def test_unicycive_shaped_family_is_not_downloaded(self):
        """Unicycive's S-1/A (0001213900-21-035033) and its five 2021 siblings."""
        subject, probes = build_family(
            ("0001213900-21-035033", "S-1/A", "2021-06-30", False),
            [("0001213900-21-028391", "S-1", "2021-05-21", False),
             ("0001213900-21-031134", "S-1/A", "2021-06-07", False),
             ("0001213900-21-033200", "S-1/A", "2021-06-21", False),
             ("0001213900-21-036490", "S-1/A", "2021-07-12", False),
             ("0001213900-21-036535", "S-1/A", "2021-07-12", False)],
        )
        assert _resolve_fee_source(subject) is None
        assert probes == []

    def test_only_the_post_regime_sibling_is_probed(self):
        """Learn CW's family straddles the gate: two 2021 amendments before it,
        one after. Only the one that could carry an exhibit costs a download."""
        subject, probes = build_family(
            ("0001140361-21-010426", "S-1", "2021-03-29", False),
            [("0001140361-21-017313", "S-1/A", "2021-05-14", False),
             ("0001140361-21-031541", "S-1/A", "2021-09-17", False),
             ("0001140361-21-033432", "S-1/A", "2021-10-04", False)],
        )
        assert _resolve_fee_source(subject) is None
        assert probes == ["0001140361-21-033432"]

    def test_the_gate_sits_before_the_rule_took_effect(self):
        """A gate set too late would skip a real exhibit; too early only costs a
        probe. The constant is on the harmless side of the 2022-01-31 effective
        date deliberately, so this pins the direction of the error."""
        assert _EX107_EARLIEST_FILING_DATE < "2022-01-31"


class TestProbingStopsAtTheFirstHit:

    def test_vincerx_shaped_family_stops_before_the_later_filing(self):
        """Vincerx's S-3/A (0001193125-25-068723) recovers from the S-3 that
        precedes it; the POS AM filed a month later is never worth reading."""
        subject, probes = build_family(
            ("0001193125-25-068723", "S-3/A", "2025-03-31", False),
            [("0001193125-25-012209", "S-3", "2025-01-24", True),
             ("0001193125-25-110092", "POS AM", "2025-05-01", False)],
        )
        source = _resolve_fee_source(subject)
        assert source.accession_no == "0001193125-25-012209"
        assert probes == ["0001193125-25-012209"]

    def test_tr_finance_shaped_family(self):
        """TR Finance's F-3/A (0001193125-25-068799) — one sibling, one probe."""
        subject, probes = build_family(
            ("0001193125-25-068799", "F-3/A", "2025-03-31", False),
            [("0001193125-25-057913", "F-3", "2025-03-19", True)],
        )
        source = _resolve_fee_source(subject)
        assert source.accession_no == "0001193125-25-057913"
        assert probes == ["0001193125-25-057913"]


class TestSelectionIsUnchanged:
    """The old code probed everything, then took the latest. These pin that the
    same filing still wins now that probing stops early."""

    def test_latest_at_or_before_wins(self):
        subject, probes = build_family(
            ("0000000000-25-000009", "S-3/A", "2025-06-01", False),
            [("0000000000-25-000001", "S-3", "2025-01-01", True),
             ("0000000000-25-000002", "S-3/A", "2025-03-01", True)],
        )
        source = _resolve_fee_source(subject)
        assert source.accession_no == "0000000000-25-000002"
        # The older one is never reached.
        assert probes == ["0000000000-25-000002"]

    def test_a_later_filing_loses_to_an_earlier_one(self):
        subject, probes = build_family(
            ("0000000000-25-000009", "S-3/A", "2025-06-01", False),
            [("0000000000-25-000002", "S-3", "2025-03-01", True),
             ("0000000000-25-000008", "S-3/A", "2025-09-01", True)],
        )
        assert _resolve_fee_source(subject).accession_no == "0000000000-25-000002"
        assert probes == ["0000000000-25-000002"]

    def test_falls_back_to_the_latest_later_filing(self):
        """Nothing at or before carries one, so the family's later filings are
        tried, latest first — what max() over all candidates used to return."""
        subject, probes = build_family(
            ("0000000000-25-000009", "S-3/A", "2025-06-01", False),
            [("0000000000-25-000002", "S-3", "2025-03-01", False),
             ("0000000000-25-000007", "S-3/A", "2025-07-01", True),
             ("0000000000-25-000008", "S-3/A", "2025-09-01", True)],
        )
        source = _resolve_fee_source(subject)
        assert source.accession_no == "0000000000-25-000008"
        assert probes == ["0000000000-25-000002", "0000000000-25-000008"]

    def test_same_date_siblings_keep_family_order(self):
        """Unicycive files two amendments on one day. max() returned the first of
        the tied maxima in family order; the sort is stable, so this still does."""
        subject, probes = build_family(
            ("0000000000-25-000009", "S-3/A", "2025-06-01", False),
            [("0000000000-25-000004", "S-3/A", "2025-04-01", True),
             ("0000000000-25-000005", "S-3/A", "2025-04-01", True)],
        )
        assert _resolve_fee_source(subject).accession_no == "0000000000-25-000004"
        assert probes == ["0000000000-25-000004"]


class TestSilence:
    """Bad input produces a usable answer, not a crash and not a wrong source."""

    def test_a_sibling_that_cannot_be_downloaded_does_not_abort_the_walk(self):
        """A failed download must not be read as 'no exhibit anywhere' — the walk
        carries on to the next candidate, which is the one that actually has it."""
        probe_log = []
        subject = StubFiling("0000000000-25-000009", "S-3/A", "2025-06-01",
                             probe_log=probe_log)
        broken = StubFiling("0000000000-25-000005", "S-3/A", "2025-05-01",
                            probe_log=probe_log, unreadable=True)
        good = StubFiling("0000000000-25-000002", "S-3", "2025-02-01",
                          has_exhibit=True, probe_log=probe_log)
        family = [subject, broken, good]
        for filing in family:
            filing._family = family

        source = _resolve_fee_source(subject)
        assert source.accession_no == "0000000000-25-000002"
        assert probe_log == ["0000000000-25-000005", "0000000000-25-000002"]

    def test_a_non_registration_form_never_walks(self):
        """424B takedowns and reports have no fee exhibit to recover."""
        subject, probes = build_family(
            ("0000000000-25-000009", "424B5", "2025-06-01", False),
            [("0000000000-25-000002", "S-3", "2025-03-01", True)],
        )
        assert _resolve_fee_source(subject) is None
        assert probes == []

    def test_a_family_of_one_costs_nothing(self):
        subject, probes = build_family(
            ("0000000000-25-000009", "S-3", "2025-06-01", False), [])
        assert _resolve_fee_source(subject) is None
        assert probes == []

    def test_related_filings_failure_is_not_fatal(self):
        class Exploding(StubFiling):
            def related_filings(self):
                raise RuntimeError("submissions unavailable")

        subject = Exploding("0000000000-25-000009", "S-3/A", "2025-06-01")
        assert _resolve_fee_source(subject) is None


@pytest.mark.parametrize("form", ["S-1", "S-3", "F-1", "F-3", "S-4", "F-4", "S-11",
                                  "S-3/A", "POS AM", "S-3ASR"])
def test_every_fee_bearing_form_still_reaches_the_walk(form):
    """The gate and the short-circuit must not have narrowed which forms recover."""
    subject, probes = build_family(
        ("0000000000-25-000009", form, "2025-06-01", False),
        [("0000000000-25-000002", "S-3", "2025-03-01", True)],
    )
    assert _resolve_fee_source(subject).accession_no == "0000000000-25-000002"
    assert probes == ["0000000000-25-000002"]

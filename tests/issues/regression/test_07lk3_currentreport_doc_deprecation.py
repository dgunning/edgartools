"""``CurrentReport.doc`` was the last un-warned public route into ``edgar.files``.

Bead: edgartools-07lk.3, staging row for edgartools-07lk.23.

``edgar.files`` is deleted in 6.0, and the rule on 07lk.23 is that every break
ships its additive half — a deprecation the user can see — in a *released* 5.x
before the freeze window opens. ``chunked_document`` warned, ``Document`` warned,
``detect_page_breaks`` and ``mark_page_breaks`` warned after
``test_07lk3_page_break_deprecation.py``. This one did not, and it is reachable
from an ordinary ``filing.obj().doc``.

WHY IT WAS MISSED, which is the part worth pinning. ``CompanyReport.doc`` returns
``self.document`` — the *new* parser's document — so on a 10-K, 10-Q or 20-F the
attribute is not legacy at all and needs no warning. ``CurrentReport`` overrides
it to return ``self._chunked_document``. So the same attribute name yields two
unrelated types depending on the form, and a survey of ``.doc`` that starts at
the base class concludes, correctly and uselessly, that ``.doc`` is modern.

That type split is asserted below rather than described, because it is the whole
reason the override exists and the whole reason it needs its own deprecation.

A NOTE ON THE PROBE. Asserting "some DeprecationWarning arrived" passes on
noise: pandas emits ``future.no_silent_downcasting`` during 8-K construction, and
an unfiltered check reported this property as already-warning when it was silent.
Every assertion here matches on the message text.
"""
import pathlib
import warnings

import pytest

from edgar.company_reports.current_report import CurrentReport
from edgar.company_reports.ten_k import TenK

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"
# Tracked, so these assertions run in CI rather than skipping on a machine that
# happens to hold the gitignored era corpus.
GATE_8K = FIXTURES / "parity_gate" / "8-K" / "0000887919-21-000012.html"
GATE_10K = FIXTURES / "parity_gate" / "10-K" / "0000950153-99-001234.html"


class FixtureFiling:
    """The minimum surface the report classes touch, backed by a local file."""

    filing_date = None

    def __init__(self, path: pathlib.Path, form: str):
        self._path = path
        self.form = form
        self.company = "fixture"
        self.accession_number = path.stem
        self.base_dir = str(path.parent)

    def html(self):
        return self._path.read_text(encoding="utf-8", errors="replace")

    def text(self):
        return self.html()


def _legacy_warnings(fn):
    """DeprecationWarnings that actually name this deprecation, not ambient noise."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fn()
    return [
        str(w.message)
        for w in caught
        if issubclass(w.category, DeprecationWarning) and "edgar.files" in str(w.message)
    ]


@pytest.fixture
def eightk():
    return CurrentReport(FixtureFiling(GATE_8K, "8-K"))


def test_doc_warns_and_names_both_the_removal_and_the_replacement(eightk):
    messages = _legacy_warnings(lambda: eightk.doc)
    assert messages, "CurrentReport.doc reached edgar.files without warning anybody"
    message = messages[0]
    assert "6.0" in message, "a deprecation that does not name the release is not actionable"
    assert ".document" in message, (
        "unlike the page-break renderer, this one HAS a replacement — say so, or "
        "the reader goes looking for a migration target and finds none"
    )


def test_document_is_the_migration_target_and_is_itself_quiet(eightk):
    """The advice the warning gives must not lead to another warning."""
    assert not _legacy_warnings(lambda: eightk.document)


def test_doc_returns_the_legacy_type_here_and_the_modern_one_everywhere_else():
    """The split this deprecation exists for.

    If a later change aligns ``CurrentReport.doc`` with its base class — which is
    what 6.0 does — this test fails, and that failure is the signal to delete the
    override and this file together rather than a regression to fix.
    """
    from edgar.documents import Document as ModernDocument
    from edgar.files.htmltools import ChunkedDocument

    tenk = TenK(FixtureFiling(GATE_10K, "10-K"))
    assert isinstance(tenk.doc, ModernDocument)

    eightk = CurrentReport(FixtureFiling(GATE_8K, "8-K"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert isinstance(eightk.doc, ChunkedDocument)

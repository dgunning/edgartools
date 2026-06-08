"""Regression test for GitHub issue #840.

`filing.obj()` returned ``None`` for Schedule 13D/G filings that predate the SEC
structured-XML mandate (effective 2024-12-18). Those filings are HTML/text only and
have no primary XML, so ``Schedule13{D,G}.from_filing()`` fell through to
``return None`` and failed silently — even though ``filing.obj_type`` advertised a
``Schedule13G`` / ``Schedule13D`` object.

Agreed contract (see bead edgartools-xbbp): ``obj()`` returns ``None`` only when the
form has no data-object type at all. When a type exists, ``obj()`` must return an
instance — fully populated from XML when available, otherwise a **partial** instance
built from the SGML header (filer + issuer identities, ``has_structured_data == False``)
with beneficial-ownership numerics reported as unavailable (``None``), never zero.

The fast tests mock the filing so they are deterministic and network-free; the single
network test pins a ground-truth identity from the real pre-mandate AAPL filing cited
in the issue.
"""
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from edgar.beneficial_ownership import Schedule13D, Schedule13G

TEST_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "beneficial_ownership"
SCHEDULE_13D_XML = TEST_DATA_DIR / "schedule13d.xml"
SCHEDULE_13G_XML = TEST_DATA_DIR / "schedule13g.xml"


def _mock_header(filer_name, filer_cik, subject_name, subject_cik):
    filer = Mock()
    filer.company_information = Mock()
    filer.company_information.name = filer_name
    filer.company_information.cik = filer_cik
    subject = Mock()
    subject.company_information = Mock()
    subject.company_information.name = subject_name
    subject.company_information.cik = subject_cik
    header = Mock()
    header.filers = [filer]
    header.subject_companies = [subject]
    return header


def _mock_html_only_filing(form, filer, filer_cik, subject, subject_cik):
    """A pre-mandate filing: no XML, header identities only."""
    filing = Mock()
    filing.form = form
    filing.xml = Mock(return_value=None)
    filing.filing_date = date(2024, 2, 14)
    filing.header = _mock_header(filer, filer_cik, subject, subject_cik)
    filing.cik = int(subject_cik)
    filing.company = subject
    return filing


# --------------------------------------------------------------------------- #
# Partial-object contract (fast, no network)
# --------------------------------------------------------------------------- #

@pytest.mark.fast
@pytest.mark.parametrize("cls,form", [
    (Schedule13G, "SC 13G/A"),
    (Schedule13D, "SC 13D/A"),
])
def test_html_only_filing_returns_partial_object_not_none(cls, form):
    filing = _mock_html_only_filing(form, "BERKSHIRE HATHAWAY INC", "0001067983",
                                    "Apple Inc.", "0000320193")
    obj = cls.from_filing(filing)

    # The core of #840: not None for a form that advertises a data object.
    assert obj is not None
    assert isinstance(obj, cls)
    assert obj.has_structured_data is False

    # Identities are recovered from the header.
    assert obj.issuer_info.name == "Apple Inc."
    assert obj.issuer_info.cik == "0000320193"
    assert obj.reporting_persons[0].name == "BERKSHIRE HATHAWAY INC"
    assert obj.reporting_persons[0].cik == "0001067983"

    # Ownership numerics are unavailable (None), NOT a misleading zero.
    assert obj.total_shares is None
    assert obj.total_percent is None


@pytest.mark.fast
@pytest.mark.parametrize("cls,form", [
    (Schedule13G, "SC 13G"),
    (Schedule13D, "SC 13D"),
])
def test_partial_object_renders_without_error(cls, form):
    """repr() and to_context() must not blow up on None numerics."""
    filing = _mock_html_only_filing(form, "Vanguard Group Inc", "0000102909",
                                    "Tesla, Inc.", "0001318605")
    obj = cls.from_filing(filing)

    for detail in ("minimal", "standard", "full"):
        ctx = obj.to_context(detail)
        assert "unavailable" in ctx.lower()
        assert "2024-12-18" in ctx  # the loud mandate notice
    # Rich rendering path (repr -> __rich__ -> render_schedule13*)
    assert repr(obj)


@pytest.mark.fast
def test_structured_xml_still_fully_populated():
    """The XML path is unchanged: has_structured_data True, real numerics."""
    filing = Mock()
    filing.form = "SCHEDULE 13G"
    filing.filing_date = date(2025, 11, 26)
    filing.xml = Mock(return_value=SCHEDULE_13G_XML.read_text())

    obj = Schedule13G.from_filing(filing)
    assert obj is not None
    assert obj.has_structured_data is True
    assert obj.total_shares is not None
    assert obj.total_percent is not None
    assert obj.total_percent > 0


@pytest.mark.fast
def test_from_header_falls_back_to_filing_company_without_subject():
    """When the header has no subject company, the issuer comes from the filing."""
    filing = Mock()
    filing.form = "SCHEDULE 13G"
    filing.xml = Mock(return_value=None)
    filing.filing_date = date(2023, 1, 1)
    header = Mock()
    header.filers = []
    header.subject_companies = []
    filing.header = header
    filing.cik = 320193
    filing.company = "Apple Inc."

    obj = Schedule13G.from_filing(filing)
    assert obj is not None
    assert obj.has_structured_data is False
    assert obj.issuer_info.name == "Apple Inc."


# --------------------------------------------------------------------------- #
# Ground truth from the real filing cited in the issue (network)
# --------------------------------------------------------------------------- #

@pytest.mark.network
def test_aapl_pre_mandate_sc13g_ground_truth():
    import edgar
    edgar.set_identity("research@example.com")

    filing = edgar.Company("AAPL").get_filings(form="SC 13G").latest(1)
    # Sanity: this is a pre-mandate HTML-only filing (the #840 scenario).
    assert filing.xml() is None
    assert filing.obj_type == "Schedule13G"  # form advertises a data object

    obj = filing.obj()
    assert obj is not None                      # <-- the bug: used to be None
    assert type(obj).__name__ == "Schedule13G"
    assert obj.has_structured_data is False
    assert obj.issuer_info.name == "Apple Inc."
    assert obj.total_percent is None
    assert obj.reporting_persons  # at least the filer identity is present

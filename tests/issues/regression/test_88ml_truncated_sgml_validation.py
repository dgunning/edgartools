"""Regression tests for edgartools-88ml and edgartools-r5ye.

edgartools-88ml: FilingSGML.from_text() on truncated SGML content (a download
that failed partway, a cut-off local file) silently succeeded with zero
documents, and text() then returned None. Truncation is structurally provable
— EDGAR always closes <DOCUMENT> — so an unterminated document now raises
ValueError at parse time instead of degrading silently.

edgartools-r5ye: the header's PUBLIC DOCUMENT COUNT was never checked against
the parsed document count. It now is, with two deliberate tolerances measured
from real filings:

- A deficit of exactly one is normal: complete dissemination .txt files
  routinely carry declared-1 <DOCUMENT> blocks (Apple's full 10-K
  0000320193-24-000123 declares 103 and ships 102 — verified by counting raw
  tags in the fixture). Off-by-one must NOT warn.
- Zero parsed documents is the pre-2004 header-only artifact (see
  test_issue_etoo_header_only_submissions.py), which declares its real
  submission's count while legitimately carrying no document body. Must NOT
  warn — warning on every historic fetch is noise (the edgartools-knkk class).
"""

import logging
from pathlib import Path

import pytest

from edgar.sgml import FilingSGML
from edgar.sgml.sgml_parser import iter_documents

pytestmark = pytest.mark.fast


def _header(document_count: int) -> str:
    return f"""<SEC-DOCUMENT>0000000001-24-000001.txt : 20240101
<SEC-HEADER>0000000001-24-000001.hdr.sgml : 20240101
<ACCEPTANCE-DATETIME>20240101060000
ACCESSION NUMBER:\t\t0000000001-24-000001
CONFORMED SUBMISSION TYPE:\t8-K
PUBLIC DOCUMENT COUNT:\t\t{document_count}
FILED AS OF DATE:\t\t20240101

FILER:

\tCOMPANY DATA:\t
\t\tCOMPANY CONFORMED NAME:\t\t\tTEST CO
\t\tCENTRAL INDEX KEY:\t\t\t0000000001

\tFILING VALUES:
\t\tFORM TYPE:\t\t8-K
</SEC-HEADER>
"""


def _document(sequence: int, filename: str, body: str) -> str:
    return (
        f"<DOCUMENT>\n<TYPE>8-K\n<SEQUENCE>{sequence}\n<FILENAME>{filename}\n"
        f"<TEXT>\n{body}\n</TEXT>\n</DOCUMENT>\n"
    )


def _submission(document_count: int, *bodies: str) -> str:
    docs = "".join(
        _document(i + 1, f"doc{i + 1}.htm", body) for i, body in enumerate(bodies)
    )
    return _header(document_count) + docs + "</SEC-DOCUMENT>\n"


COMPLETE = _submission(
    2,
    "<html><body><p>Item 8.01 Other Events. The registrant announced.</p></body></html>",
    "<html><body><p>Exhibit 99.1</p></body></html>",
)


class TestTruncationRaises:
    """88ml: an unterminated <DOCUMENT> is truncation, and truncation raises."""

    def test_cut_inside_first_document_raises(self):
        # The exact 88ml shape: the cut falls inside the only/first document,
        # which previously produced a FilingSGML with 0 documents.
        cut = COMPLETE[: COMPLETE.index("Item 8.01") + 5]
        with pytest.raises(ValueError, match="Truncated SGML"):
            FilingSGML.from_text(cut)

    def test_cut_inside_second_document_raises(self):
        # One complete document before the cut: previously returned a partial
        # submission with no signal beyond a log line.
        cut = COMPLETE[: COMPLETE.index("Exhibit 99.1")]
        with pytest.raises(ValueError, match="1 complete document"):
            FilingSGML.from_text(cut)

    def test_error_message_says_what_to_do(self):
        cut = COMPLETE[: COMPLETE.index("Exhibit 99.1")]
        with pytest.raises(ValueError, match="re-download"):
            FilingSGML.from_text(cut)

    def test_iter_documents_raises_on_truncation(self):
        cut = COMPLETE[: COMPLETE.index("Exhibit 99.1")]
        with pytest.raises(ValueError, match="Truncated SGML"):
            list(iter_documents(cut))

    def test_complete_submission_still_parses(self):
        sgml = FilingSGML.from_text(COMPLETE)
        assert sgml.get_document_count() == 2
        text = sgml.text()
        assert "Item 8.01 Other Events" in text


class TestDocumentCountValidation:
    """r5ye: declared PUBLIC DOCUMENT COUNT vs parsed count."""

    def test_deficit_of_two_or_more_warns(self, caplog):
        with caplog.at_level(logging.WARNING, logger="edgar.sgml.sgml_common"):
            FilingSGML.from_text(_submission(4, "<p>one</p>", "<p>two</p>"))
        assert "declares 4" in caplog.text
        assert "2 were parsed" in caplog.text

    def test_off_by_one_does_not_warn(self, caplog):
        # Complete dissemination files routinely ship declared-1 documents;
        # warning here would fire on most large modern filings.
        with caplog.at_level(logging.WARNING, logger="edgar.sgml.sgml_common"):
            FilingSGML.from_text(_submission(3, "<p>one</p>", "<p>two</p>"))
        assert "were parsed" not in caplog.text

    def test_exact_match_does_not_warn(self, caplog):
        with caplog.at_level(logging.WARNING, logger="edgar.sgml.sgml_common"):
            FilingSGML.from_text(COMPLETE)
        assert "were parsed" not in caplog.text

    def test_header_only_artifact_does_not_warn(self, caplog):
        # Pre-2004 .hdr.sgml served as the submission: declares a count,
        # legitimately carries no documents. Parsing it is covered by
        # test_issue_etoo_header_only_submissions.py; here we pin that the
        # count check stays silent for it.
        header_only = (
            "<SEC-HEADER>0000950123-96-000524.hdr.sgml : 19960213\n"
            "ACCESSION NUMBER:\t\t0000950123-96-000524\n"
            "CONFORMED SUBMISSION TYPE:\t10-K\n"
            "PUBLIC DOCUMENT COUNT:\t\t4\n"
            "FILED AS OF DATE:\t\t19960213\n"
            "</SEC-HEADER>\n"
        )
        with caplog.at_level(logging.WARNING, logger="edgar.sgml.sgml_common"):
            sgml = FilingSGML.from_text(header_only)
        assert sgml.get_document_count() == 0
        assert "were parsed" not in caplog.text


class TestGroundTruthFixture:
    """The off-by-one tolerance is measured, not assumed: Apple's complete
    10-K submission declares 103 documents and ships 102 <DOCUMENT> blocks."""

    FIXTURE = Path(__file__).parents[3] / "data" / "sgml" / "0000320193-24-000123.txt"

    def test_apple_10k_parses_all_shipped_documents_without_warning(self, caplog):
        assert self.FIXTURE.exists(), f"committed fixture missing: {self.FIXTURE}"
        with caplog.at_level(logging.WARNING, logger="edgar.sgml.sgml_common"):
            sgml = FilingSGML.from_source(self.FIXTURE)
        assert sgml.header.document_count == 103
        assert sgml.get_document_count() == 102
        assert "were parsed" not in caplog.text

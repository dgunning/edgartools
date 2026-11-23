"""Regression test for GitHub issue #844 (binary-classification half).

The TypeError crash was fixed in the legacy ``html_documents.get_root`` (PR
#845); since 6.0 that decoding rule lives in
``edgar.sgml.text_extraction.html_to_text`` (see ``test_issue_844.py``). This test covers the *complementary* root cause: 6-K
attachment lists include XBRL viewer artifacts such as ``Financial_Report.xlsx``
and ``<accession>-xbrl.zip``, and ``binary_extensions`` previously omitted
``.xlsx`` / ``.zip``. Those artifacts therefore reported ``is_binary() == False``,
slipped past the exhibit filter in ``SixK._content_renderables()``, and were
rendered into ``sixk.text()`` output — the ``.zip`` as raw binary mojibake.

Adding the archive/office extensions to ``binary_extensions`` makes
``is_binary()`` skip them. That left the rest of the XBRL files in the text:
``SixK.exhibits`` kept every attachment but graphics and the cover, so the
instance, linkbases, R*.htm viewer pages, Show.js and report.css were all
rendered, 13.5 million characters for the FUTU 6-K. It now follows
``filing.exhibits`` (the EX-* documents), and ``text()`` renders the cover page
too, so a 6-K whose content is all in the cover no longer comes back empty.

GitHub Issue: https://github.com/dgunning/edgartools/issues/844
"""
import gzip
from pathlib import Path

import pytest

from edgar.attachments import Attachment
from edgar.core import binary_extensions
from edgar.sgml import FilingSGML
from tests._offline_filings import offline_filing


def _make_attachment(document: str, document_type: str = "EXCEL") -> Attachment:
    return Attachment(
        sequence_number="1",
        description=document,
        document=document,
        ixbrl=False,
        path=f"/some/path/{document}",
        document_type=document_type,
        size=None,
    )


@pytest.mark.fast
@pytest.mark.parametrize("ext", [".xlsx", ".xls", ".zip", ".docx", ".pptx"])
def test_office_and_archive_extensions_are_binary(ext):
    """Office documents and archives must be recognized as binary (GH #844)."""
    assert ext in binary_extensions


@pytest.mark.fast
@pytest.mark.parametrize("document", ["Financial_Report.xlsx", "0001104659-22-129316-xbrl.zip"])
def test_xbrl_artifacts_flagged_binary(document):
    """The artifacts that polluted sixk.text() now report is_binary() == True."""
    assert _make_attachment(document).is_binary() is True


SGML_GZ = Path(__file__).parents[2] / "fixtures" / "sgml_gz"

FUTU_6K = "0001104659-22-129316"     # Futu Holdings 6-K with XBRL, the GH #844 filing
CRESUD_6K = "0001654954-18-006914"   # Cresud 6-K whose content is all in the cover page

# Text from the XBRL files SEC adds to a filing. None of it belongs in sixk.text().
XBRL_ARTIFACT_MARKERS = [
    "EX-101",                  # the instance/linkbase panels' titles
    "link:presentationLink",   # the schema's role listings
    "Financial_Report",        # the viewer workbook
    "MetaLinks",
]


def _sixk_from_fixture(accession_number: str, tmp_path):
    """The SixK for a committed full submission text file, with no network."""
    path = tmp_path / f"{accession_number}.txt"
    path.write_bytes(gzip.decompress((SGML_GZ / f"{accession_number}.txt.gz").read_bytes()))
    filing = offline_filing(accession_number)
    filing._sgml = FilingSGML.from_source(path)
    return filing.obj()


@pytest.mark.fast
def test_futu_sixk_exhibits_are_its_ex99_documents(tmp_path):
    """The XBRL viewer files are not exhibits: FUTU had about 140, it has two."""
    sixk = _sixk_from_fixture(FUTU_6K, tmp_path)

    assert [ex.document_type for ex in sixk.exhibits] == ["EX-99.1", "EX-99.2"]
    assert [ex.document for ex in sixk.exhibits] == [
        "futu-20220930xex99d1.htm", "futu-20220930xex99d2.htm"]


@pytest.mark.fast
def test_futu_sixk_text_is_its_content_without_xbrl_artifacts(tmp_path):
    """FUTU 6-K text holds the exhibits' figures and none of the XBRL files (GH #844).

    It was 13.5 million characters, nearly all XBRL instance, linkbases and
    R*.htm viewer pages, and took about 28 s to render.
    """
    sixk = _sixk_from_fixture(FUTU_6K, tmp_path)
    text = sixk.text()

    # EX-99.1 income statement, total revenues in the 2021 and 2022 columns
    assert "3,781,461" in text
    assert "3,387,728" in text
    # Net income attributable to ordinary shareholders of the Company, same columns
    assert "1,696,190" in text
    assert [m for m in XBRL_ARTIFACT_MARKERS if m in text] == []
    assert len(text) < 1_000_000


@pytest.mark.fast
def test_cover_page_only_sixk_text_is_not_empty(tmp_path):
    """A 6-K with no exhibits carries its content in the cover page, which text() renders."""
    sixk = _sixk_from_fixture(CRESUD_6K, tmp_path)

    assert sixk.exhibits == []
    text = sixk.text()
    assert "For the month of June, 2018" in text
    assert "Moreno 877" in text   # the registrant's address on the cover

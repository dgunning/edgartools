"""Regression test for GitHub issue #844 (binary-classification half).

The TypeError crash is fixed in ``html_documents.get_root`` (PR #845, see
``test_issue_844.py``). This test covers the *complementary* root cause: 6-K
attachment lists include XBRL viewer artifacts such as ``Financial_Report.xlsx``
and ``<accession>-xbrl.zip``, and ``binary_extensions`` previously omitted
``.xlsx`` / ``.zip``. Those artifacts therefore reported ``is_binary() == False``,
slipped past the exhibit filter in ``SixK._content_renderables()``, and were
rendered into ``sixk.text()`` output — the ``.zip`` as raw binary mojibake.

Adding the archive/office extensions to ``binary_extensions`` makes
``is_binary()`` skip them, so they no longer pollute the rendered text.
"""
import pytest

from edgar.attachments import Attachment
from edgar.core import binary_extensions


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


@pytest.mark.network
def test_futu_sixk_text_excludes_binary_artifacts():
    """FUTU 6-K renders text without the binary XBRL artifacts (GH #844)."""
    import edgar

    filing = edgar.get_by_accession_number("0001104659-22-129316")  # FUTU 6-K
    sixk = filing.obj()

    text = sixk.text()
    assert isinstance(text, str)
    assert len(text) > 0
    assert "FUTU" in text  # real Exhibit 99.1 content is present

    # The xlsx / xbrl.zip artifacts must be filtered out, not rendered.
    binary_artifacts = [ex for ex in sixk.exhibits if ex.extension in (".xlsx", ".zip")]
    assert binary_artifacts, "expected the FUTU filing to still contain xlsx/zip artifacts"
    assert all(ex.is_binary() for ex in binary_artifacts)

"""
Regression test for GitHub Issue #1563:
An 8-K whose primary document is one preformatted (``<pre>``) block of plain
text kept the SIGNATURE block inside its last item, undoing #1393.

Bug (FIXED): #1393 ends an 8-K's last item at the signature statement when the
filing has no ``SIGNATURES`` heading (Strategy 5c of
``edgar/documents/extractors/pattern_section_extractor.py``). #1534 then made a
plain-text filing with no ``<TABLE>`` split at blank lines
(``edgar/documents/strategies/document_builder.py``, see ``_add_text``). In this
filing the source has no blank line between the bare ``SIGNATURE`` heading and
the sentence Form 8-K's General Instructions prescribe, so the two now arrive as
one paragraph. ``_SIGNATURE_STATEMENT`` was anchored at ``^Pursuant to ...`` and
no longer matched, so Strategy 5c found no boundary and the last item ran on
through the signature block.

Affected filing (Liaoning Shuiyun Qinghe Rice Industry Co., Ltd., CIK 710782):
    Accession: 0000710782-24-000002
    Filed: 2024-02-05, Item 8.01 (Other Events), primary document 8k01.htm,
    one ``<pre>`` block of plain text (3,411 characters).
    Before fix: Item 8.01 = 1,348 chars, SIGNATURE at offset 3,037 included.
    After fix:  Item 8.01 = 972 chars, ending "...global competitiveness."

Fix: ``_SIGNATURE_STATEMENT`` accepts an optional leading ``SIGNATURE``/
``SIGNATURES`` label before the prescribed sentence, so the boundary is found
whether the heading was split off or glued to the statement by blank-line
splitting.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1563
Related: #1393 (merged), #1531, #1534 (merged)
"""

from pathlib import Path

import pytest

pytestmark = [pytest.mark.regression]

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"
# Liaoning Shuiyun Qinghe Rice Industry Co., Ltd., 8-K filed 2024-02-05.
REPORT_8K = FIXTURES / "issues" / "0000710782-24-000002.html"


def _parse_report():
    from edgar.documents import parse_html
    from edgar.documents.config import ParserConfig

    html = REPORT_8K.read_text(encoding="utf-8")
    return parse_html(html, ParserConfig(form="8-K"))


class TestLastItemEndsAtSignatureStatement:
    """Item 8.01 stops before the SIGNATURE block (offline, no network)."""

    def test_item_801_excludes_signature_block(self):
        doc = _parse_report()
        sections = doc.sections
        assert "item_801" in sections, "Item 8.01 not detected"

        text = sections["item_801"].text()
        assert "SIGNATURE" not in text, "signature block leaked into Item 8.01"
        assert "Baobing He" not in text, "signer name leaked into Item 8.01"

    def test_item_801_length_matches_v5_62_0(self):
        """The item ends where it did before #1534: 972 chars."""
        doc = _parse_report()
        text = doc.sections["item_801"].text()
        assert len(text) == 972
        assert text.endswith(
            "enhancing the company's global competitiveness."
        )

    def test_signature_statement_still_becomes_a_section(self):
        """The signature block is a section of its own, not dropped."""
        doc = _parse_report()
        signatures = doc.sections.named("signatures")
        assert signatures is not None
        assert "Baobing He" in signatures.text()
        assert "SIGNATURE" in signatures.text()

"""
Regression test for edgartools-llmp.12: an exhibit index or schedule after a TOC-listed Signatures section.

When a 10-K's table of contents lists SIGNATURES, the signature block is its
own section, and whatever the filer prints after it ran on inside it:
Intuit's (2007) and Tetra Tech's (2015) exhibit indexes, Sanmina's (2017)
Schedule II. The policy decided on 2026-10-14 matches the one for an index
after Item 16: the last item ends before the Signatures section, the
Signatures section holds the signature block, and the index or schedule is
the non-item ``exhibit_index`` section.
"""
import pytest

from edgar.documents import HTMLParser, ParserConfig
from tests.paths import FIXTURES_DIR

RETIRED = FIXTURES_DIR / "heldout_retired" / "10-K"


def _sections(accession):
    html = (RETIRED / f"{accession}.html").read_text(errors="ignore")
    return HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(html).sections


def _text(section):
    return " ".join(section.text().split())


@pytest.mark.parametrize("accession, item_15_ends, signatures_end, index_opens, index_ends", [
    ("0000950134-07-020001", "(d) Financial Statement Schedules See Item 15(a)(2) above.",
     "Director September 14, 2007 Stratton D. Sclavos", "EXHIBIT INDEX Exhibit Number",
     "except to the extent that Intuit specifically incorporates it by reference."),
    ("0000897723-17-000029", "(c) Financial Statement Schedules. See Item 15(a)(2) above.",
     "is filed as part of this Form 10-K.", "SANMINA CORPORATION SCHEDULE II-VALUATION AND QUALIFYING ACCOUNTS",
     "Fiscal year ended September 30, 2017 $15,081 $(747) $ $14,334"),
    ("0001047469-15-008864", "related to net operating loss carry-forwards.",
     "Director November 18, 2015 Kimberly E. Ritrievi", "INDEX TO EXHIBITS",
     "except as shall be expressly set forth by specific reference in such filings."),
])
def test_the_index_after_the_signatures_is_its_own_section(accession, item_15_ends, signatures_end,
                                                            index_opens, index_ends):
    sections = _sections(accession)
    assert _text(sections["part_iv_item_15"]).endswith(item_15_ends)
    signatures = _text(sections["part_iv_signatures"])
    assert signatures.endswith(signatures_end)  # ran on through the index or schedule
    assert index_opens not in signatures
    index = _text(sections["exhibit_index"])
    assert index.startswith(index_opens)
    assert index.endswith(index_ends)

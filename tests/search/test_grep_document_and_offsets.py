"""Filing.grep document selection and literal-match offsets.

edgartools-5qqy: document="EX-10.1" was a substring test against the document
type, so it also searched EX-10.10 through EX-10.19.

edgartools-6th2: a literal grep found positions in text.lower() and sliced the
original text with them. Lowercasing "İ" gives two characters, so every match
after one came back shifted.
"""
from collections import Counter
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

import pytest

from edgar import Filing
from edgar.search.grep import _grep_text


def _attachment(seq, document_type, document, text=""):
    return SimpleNamespace(sequence_number=seq, document_type=document_type, document=document,
                           empty=False, is_binary=lambda: False, text=lambda: text)


ATTACHMENTS = [
    _attachment("1", "S-1", "ea0288470-s1.htm", "primary agreement"),
    _attachment("2", "EX-10.1", "ex10-1.htm", "stockholder support agreement"),
    _attachment("3", "EX-10.10", "ex10-10.htm", "employment agreement"),
    _attachment("4", "EX-10.11", "ex10-11.htm", "employment agreement"),
    _attachment("5", "EX-21.1", "ex21-1.htm", "subsidiaries"),
]


def _selected(document):
    return [a.sequence_number for a in Filing._select_attachments(ATTACHMENTS, document)]


@pytest.mark.fast
class TestDocumentSelection:

    def test_an_exact_type_selects_only_that_exhibit(self):
        assert _selected("EX-10.1") == ["2"]
        assert _selected("ex-10.1") == ["2"]

    def test_an_exact_filename_wins(self):
        assert _selected("ex10-10.htm") == ["3"]

    def test_a_partial_name_still_selects_by_substring(self):
        assert _selected("EX-10") == ["2", "3", "4"]
        assert _selected("ex21") == ["5"]

    def test_primary_and_no_filter(self):
        assert _selected("primary") == ["1"]
        assert _selected(None) == ["1", "2", "3", "4", "5"]

    def test_grep_reports_matches_from_the_selected_exhibit_only(self):
        filing = Filing(cik=1, company="Test", form="S-1", filing_date="2026-06-01",
                        accession_no="0000000001-26-000001")
        with patch.object(Filing, "attachments", new_callable=PropertyMock, return_value=ATTACHMENTS):
            result = filing.grep("agreement", document="EX-10.1")
        assert [m.location for m in result] == ["EX-10.1"]


@pytest.mark.fast
class TestLiteralOffsets:

    def test_text_whose_lowercase_is_longer_does_not_shift_the_match(self):
        text = "İİİİ Istanbul text says going concern doubt here"
        assert "İ".lower() != "İ" and len("İ".lower()) == 2  # the premise

        [m] = _grep_text(text, "going concern", "p")

        assert m.match == "going concern"
        assert m.context == text

    def test_the_match_keeps_the_source_casing(self):
        [m] = _grep_text("Substantial Doubt about Going Concern", "going concern", "p")
        assert m.match == "Going Concern"

    def test_overlapping_matches_are_still_found(self):
        assert [m.match for m in _grep_text("aaa", "aa", "p")] == ["aa", "aa"]

    def test_regex_metacharacters_in_a_literal_are_literal(self):
        assert [m.match for m in _grep_text("rate of 5.0% (fixed)", "5.0% (fixed)", "p")] == ["5.0% (fixed)"]
        assert _grep_text("rate of 510% fixed", "5.0%", "p") == []


@pytest.mark.network
def test_seeqc_s1_ex_10_1_excludes_the_employment_agreements():
    """SeeQC's S-1 (0001213900-26-073222) has EX-10.1, a Stockholder Support Agreement,
    and EX-10.10 to EX-10.12, employment agreements. "agreement" in EX-10.1 is 133
    matches; the substring filter added 245 more from the other three."""
    from edgar import find
    result = find("0001213900-26-073222").grep("agreement", document="EX-10.1")

    assert Counter(m.location for m in result) == {"EX-10.1": 133}
    assert "STOCKHOLDER SUPPORT AGREEMENT" in result[0].context

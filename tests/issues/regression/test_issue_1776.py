"""
Regression test: the 8-K earnings lookup skipped EX-99 / EX-99.1 exhibits whose
description and filename omit "ex-99".

GitHub Issue: https://github.com/dgunning/edgartools/issues/1776

``find_earnings_exhibits`` looked for "EX-99" in the description and "ex-99"/"ex99" in the
filename but never read the SEC document type. Accenture's q1fy26earnings8-kexhibit.htm
(type EX-99, description "NEWS RELEASE OF ACCENTURE, DATED DECEMBER 18, 2025") was missed,
so ``filing.obj().earnings`` was None. The document type is now matched, and exhibits sort by
the number in their document type, so an EX-99.1 release beats an EX-99.2 supplement.
"""

import pytest

from edgar import find
from edgar.earnings import find_earnings_exhibits


class _Attachment:
    def __init__(self, document, document_type, description):
        self.document = document
        self.document_type = document_type
        self.description = description

    def is_html(self):
        return self.document.endswith(".htm")


@pytest.mark.regression
def test_document_type_ex99_is_found():
    release = _Attachment("q1fy26earnings8-kexhibit.htm", "EX-99",
                          "NEWS RELEASE OF ACCENTURE, DATED DECEMBER 18, 2025")
    other = _Attachment("acn-20251218.htm", "8-K", "8-K")
    assert find_earnings_exhibits([other, release]) == [release]


@pytest.mark.regression
def test_release_sorts_before_supplement_by_document_type():
    # JPMorgan 0001628280-26-065582 shape: only the supplement's filename contains "ex99"
    supplement = _Attachment("a3q26erfex992supplement.htm", "EX-99.2", "FINANCIAL SUPPLEMENT")
    release = _Attachment("a3q26erfexhibit991narrative.htm", "EX-99.1", "EARNINGS RELEASE")
    assert find_earnings_exhibits([supplement, release]) == [release, supplement]


@pytest.mark.regression
def test_non_ex99_html_is_still_ignored():
    assert find_earnings_exhibits([_Attachment("ex10-1.htm", "EX-10.1", "AGREEMENT")]) == []


@pytest.mark.regression
@pytest.mark.network
@pytest.mark.vcr
def test_issue_1776_accenture_ex99_earnings_found():
    # Accenture 8-K 0001467373-25-000221, EX-99 news release: Revenues $18,742,125 thousand
    filing = find("0001467373-25-000221")
    earnings = filing.obj().earnings
    assert earnings.attachment.document == "q1fy26earnings8-kexhibit.htm"
    assert earnings.get_key_metrics()["revenue"] == pytest.approx(18_742_125_000)

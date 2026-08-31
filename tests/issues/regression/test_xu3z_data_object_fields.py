"""Three typed fields that were silently wrong (edgartools-xu3z; gh #1192, #1193, #1195).

Every expectation here is read out of the raw fixture text, never from the objects
under test. That is the whole point of the file. All three bugs had existing tests
over them, and two of those tests asserted the *parser's* answer back at itself --
`test_regd_notice_contract.py` pinned an inverted `is_new` and
`test_144_notice_contract.py` pinned the string `"N"` -- so the suite agreed with
the defect for as long as the defect existed.

The reads below are deliberately crude string slicing rather than an XML parse.
These fixtures are small, checked in and static, the values wanted are leaf text,
and using no parser at all is the strongest available guarantee that the
expectation is not produced by the machinery under test.
"""
import re
from pathlib import Path

import pytest

from edgar.offerings.exempt.formd import FormD
from edgar.ownership.form144 import Form144

AP_FUND = Path('data/D.APFund.xml')
SHEPHERDS = Path('data/D.Shepards.xml')
REIT_1685 = Path('data/D.1685REIT.xml')
SAMPLE_144 = Path('data/144/EDGAR Form 144 XML Samples/Sample 144.xml')


def _section(text: str, tag: str) -> str:
    """The text between <tag> and </tag>, or '' when the element is absent."""
    match = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1) if match else ""


def _leaves(text: str, tag: str) -> list:
    """Every <tag>value</tag> in document order. Form 144 is namespaced, so the
    prefix is optional here the way `xmltools` matches on the local name."""
    return re.findall(rf"<(?:\w+:)?{tag}\b[^>]*>(.*?)</(?:\w+:)?{tag}>", text, re.DOTALL)


def _leaf(text: str, tag: str):
    values = _leaves(text, tag)
    return values[0] if values else None


# --------------------------------------------------------------------------- #
# gh #1193 -- the ZIP tag name was the sample value pasted from the docstring
# --------------------------------------------------------------------------- #

def test_sales_compensation_recipients_keep_their_filed_zip_codes():
    """`child_text(address_tag, "30361")` looked for a child element named <30361>,
    so every recipient ZIP was None. The same field on related persons was always
    read correctly, which is why nothing downstream looked wrong."""
    raw = REIT_1685.read_text()
    filed = _leaves(_section(raw, "salesCompensationList"), "zipCode")
    assert filed == ["30361", "30361", "30361", "30361"], "fixture changed"

    form_d = FormD.from_xml(raw)
    parsed = [r.address.zipcode for r in form_d.offering_data.sales_compensation_recipients]
    assert parsed == filed


def test_related_person_zip_codes_still_work():
    """The control: this read was never broken, and must not regress while the
    sibling one is fixed."""
    raw = REIT_1685.read_text()
    filed = _leaves(_section(raw, "relatedPersonsList"), "zipCode")
    assert filed, "fixture changed"

    form_d = FormD.from_xml(raw)
    parsed = [p.address.zipcode for p in form_d.related_persons if p.address is not None]
    assert parsed == filed


# --------------------------------------------------------------------------- #
# gh #1192 -- is_new held the is-amendment answer
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("path", [AP_FUND, SHEPHERDS, REIT_1685], ids=lambda p: p.stem)
def test_is_new_agrees_with_the_filed_amendment_flag(path):
    """`<isAmendment>` answers the opposite question. The fixtures were wrong in
    both directions: a base Form D reported is_new=False and a Form D/A reported
    is_new=True."""
    raw = path.read_text()
    filed_is_amendment = _leaf(_section(raw, "newOrAmendment"), "isAmendment") == "true"

    assert FormD.from_xml(raw).is_new is not filed_is_amendment


@pytest.mark.parametrize("path", [AP_FUND, SHEPHERDS, REIT_1685], ids=lambda p: p.stem)
def test_the_context_heading_agrees_with_the_filed_submission_type(path):
    """The heading rendered the amendment marker off the inverted boolean, so it
    contradicted `submission_type` on the same object. It now comes from the SEC's
    own field and cannot disagree."""
    raw = path.read_text()
    filed_submission_type = _leaf(raw, "submissionType")
    assert filed_submission_type in ("D", "D/A"), "fixture changed"

    form_d = FormD.from_xml(raw)
    assert form_d.submission_type == filed_submission_type
    assert form_d.to_context().startswith(f"FORM{filed_submission_type}:")


def test_a_base_notice_and_an_amendment_disagree_with_each_other():
    """Guards against a fix that inverts the constant and passes the paired test
    above while making every filing report the same thing."""
    base = FormD.from_xml(REIT_1685.read_text())
    amendment = FormD.from_xml(SHEPHERDS.read_text())
    assert (base.is_new, amendment.is_new) == (True, False)


# --------------------------------------------------------------------------- #
# gh #1195 -- a truthy "N"
# --------------------------------------------------------------------------- #

def test_nothing_to_report_is_a_boolean_that_matches_the_filed_flag():
    """`bool("N")` is True, so `if form.nothing_to_report:` read a filing that
    *does* have sales to report as having nothing to report. The sale rows were
    always present -- only the flag lied."""
    raw = SAMPLE_144.read_text()
    filed_flag = _leaf(raw, "nothingToReportFlagOnSecuritiesSoldInPast3Months")
    filed_sale_rows = len(_leaves(raw, "securitiesSoldInPast3Months"))
    assert (filed_flag, filed_sale_rows) == ("N", 1), "fixture changed"

    parsed = Form144.parse_xml(raw)
    assert parsed['nothing_to_report'] is False
    assert bool(parsed['nothing_to_report']) is False


def test_an_unanswered_flag_stays_none_rather_than_defaulting():
    """Absent is not the same as 'N'. A default would be a silent invention, and
    a caller cannot tell the two apart once it is made."""
    from edgar.ownership.form144 import _yes_no_flag

    assert _yes_no_flag('Y') is True
    assert _yes_no_flag('N') is False
    assert _yes_no_flag('n') is False
    assert _yes_no_flag(None) is None
    assert _yes_no_flag('') is None
    assert _yes_no_flag('maybe') is None

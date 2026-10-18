"""
Regression test for GitHub Issue #1581: FortyF and TwentyF section properties
raised SectionNotFoundError where TenK's return None.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1581

Since #1557 (07lk.10) `report[item]` raises for a missing section. TenK's
section properties go through `.get()` and keep returning None, the documented
probe behaviour ("if tenk.risk_factors:"). The six FortyF and ten TwentyF
properties returned `self[...]`, so on Shopify's 40-F (0001594805-24-000007)
`forty_f.capital_structure` raised instead of answering None as the FortyF
guide documents.

Fix: the FortyF and TwentyF properties go through `.get()` as TenK's do; the
subscript still raises.

Filings, offline:
  - Nymox Pharmaceutical (CIK 1018735), 20-F 0001640334-25-000972
    (tests/fixtures/html/1018735/20f/1018735-20-f-2025-06-03.html). Item 3 starts
    "ITEM 3. KEY INFORMATION"; the absent case removes Item 15 from its sections.
  - FortyF: a two-heading AIF text. Shopify's real 40-F is covered by the network
    test tests/company_reports/test_forty_f.py::test_capital_structure_none_when_absent.
"""
from functools import cached_property
from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar.company_reports import FortyF, TwentyF
from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.exceptions import SectionNotFoundError

pytestmark = [pytest.mark.regression]

NYMOX_20F = Path(__file__).parent.parent.parent / "fixtures" / "html" / "1018735" / "20f" / "1018735-20-f-2025-06-03.html"

TWENTY_F_PROPERTIES = [
    "key_information", "risk_factors", "business", "company_information", "operating_review",
    "management_discussion", "directors_and_employees", "major_shareholders",
    "financial_information", "controls_and_procedures",
]
FORTY_F_PROPERTIES = [
    "risk_factors", "corporate_structure", "dividends", "capital_structure",
    "directors_and_officers", "legal_proceedings",
]


@pytest.fixture(scope="module")
def nymox_document():
    return parse_html(NYMOX_20F.read_text(errors="replace"), ParserConfig(form="20-F"))


def _twenty_f(document, drop=()):
    class FixtureTwentyF(TwentyF):
        @cached_property
        def document(self):
            return document

        @property
        def sections(self):
            return {k: v for k, v in document.sections.items() if k not in drop}

    filing = SimpleNamespace(form="20-F", accession_number="0001640334-25-000972",
                             accession_no="0001640334-25-000972")
    return FixtureTwentyF(filing)


def test_twenty_f_properties_answer_from_the_filing(nymox_document):
    twenty_f = _twenty_f(nymox_document)
    assert twenty_f.key_information.startswith("ITEM 3. KEY INFORMATION")
    assert twenty_f.controls_and_procedures.startswith("ITEM 15. CONTROLS AND PROCEDURES")


def test_twenty_f_property_is_none_for_a_missing_item(nymox_document):
    twenty_f = _twenty_f(nymox_document, drop={"item_15"})
    assert twenty_f.controls_and_procedures is None
    with pytest.raises(SectionNotFoundError, match="has no 'Item 15'"):
        twenty_f["Item 15"]


def test_no_twenty_f_property_raises_on_a_filing_with_no_items(nymox_document):
    twenty_f = _twenty_f(nymox_document, drop=set(nymox_document.sections))
    assert {name: getattr(twenty_f, name) for name in TWENTY_F_PROPERTIES} == dict.fromkeys(TWENTY_F_PROPERTIES)


# FortyF looks for headings only after the first 5,000 characters (past the cover
# page and table of contents), so the stub AIF starts with that much preamble.
AIF_TEXT = (
    "ANNUAL INFORMATION FORM\n\n" + "Forward-looking statements and definitions.\n" * 150
    + "\nRISK FACTORS\n\n" + "Our business is subject to risks, including competition.\n" * 10
    + "\nDIVIDENDS\n\nWe have never declared or paid any cash dividends on our shares.\n"
)


def _forty_f(text):
    class FixtureFortyF(FortyF):
        @cached_property
        def aif_text(self):
            return text

    filing = SimpleNamespace(form="40-F", accession_number="0000000000-00-000000",
                             accession_no="0000000000-00-000000")
    return FixtureFortyF(filing)


def test_forty_f_property_is_none_for_a_missing_section():
    forty_f = _forty_f(AIF_TEXT)
    assert forty_f.items == ["Risk Factors", "Dividends"]
    assert forty_f.dividends == "DIVIDENDS We have never declared or paid any cash dividends on our shares."
    assert forty_f.capital_structure is None
    with pytest.raises(SectionNotFoundError, match="has no 'Description Of Capital Structure'"):
        forty_f["Description Of Capital Structure"]


@pytest.mark.parametrize("text", [AIF_TEXT, None], ids=["some-sections", "no-aif"])
def test_no_forty_f_property_raises(text):
    forty_f = _forty_f(text)
    values = {name: getattr(forty_f, name) for name in FORTY_F_PROPERTIES}
    expected_present = {"risk_factors", "dividends"} if text else set()
    assert {name for name, value in values.items() if value is not None} == expected_present

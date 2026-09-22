"""Regression test for issue #1226.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1226

`XBRL.entity_info` classified the report by comparing the whole
`dei:DocumentType` against `'10-K'`, so Shopify's 10-K/A came back with
`amendment=True` alongside `annual_report=False` — a classification that
contradicts itself and the filing, which tags `dei:DocumentAnnualReport` true.

An amended annual report is still an annual report. The suffix is now stripped
before classifying, and the form list `period_selector` kept as its own tuple
for the same decision is now the one both use
(`edgar.xbrl.core.is_annual_document_type`).
"""

import pytest

from edgar.xbrl.core import (
    is_amendment_document_type,
    is_annual_document_type,
    is_quarterly_document_type,
)
from edgar.xbrl.parsers import XBRLParser

INSTANCE = """<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance"
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:dei="http://xbrl.sec.gov/dei/2024"
      xmlns:xlink="http://www.w3.org/1999/xlink">
  <context id="c1">
    <entity><identifier scheme="http://www.sec.gov/CIK">0001594805</identifier></entity>
    <period><startDate>2024-01-01</startDate><endDate>2024-12-31</endDate></period>
  </context>
  <dei:DocumentType contextRef="c1">{document_type}</dei:DocumentType>
  <dei:AmendmentFlag contextRef="c1">true</dei:AmendmentFlag>
  <dei:DocumentAnnualReport contextRef="c1">true</dei:DocumentAnnualReport>
  <dei:DocumentFiscalPeriodFocus contextRef="c1">FY</dei:DocumentFiscalPeriodFocus>
  <dei:DocumentFiscalYearFocus contextRef="c1">2024</dei:DocumentFiscalYearFocus>
  <dei:EntityRegistrantName contextRef="c1">SHOPIFY INC.</dei:EntityRegistrantName>
</xbrl>
"""


def _entity_info(document_type):
    parser = XBRLParser()
    parser.parse_instance_content(INSTANCE.format(document_type=document_type))
    return parser.entity_info


def test_amended_annual_report_keeps_both_halves_of_its_identity():
    """The report's own case: Shopify's 10-K/A, accession 0001594805-25-000039."""
    info = _entity_info("10-K/A")

    assert info["entity_name"] == "SHOPIFY INC."
    assert info["document_type"] == "10-K/A"
    assert info["annual_report"] is True
    assert info["amendment"] is True
    assert info["quarterly_report"] is False


def test_an_unamended_annual_report_is_unchanged():
    info = _entity_info("10-K")

    assert info["annual_report"] is True
    assert info["amendment"] is False


def test_an_amended_quarterly_report_is_still_quarterly():
    info = _entity_info("10-Q/A")

    assert info["quarterly_report"] is True
    assert info["amendment"] is True
    assert info["annual_report"] is False


@pytest.mark.parametrize("document_type,annual,quarterly,amendment", [
    ("10-K", True, False, False),
    ("10-K/A", True, False, True),
    ("10-KT", True, False, False),
    ("20-F", True, False, False),
    ("20-F/A", True, False, True),
    ("40-F", True, False, False),
    ("10-Q", False, True, False),
    ("10-Q/A", False, True, True),
    ("8-K", False, False, False),
    ("", False, False, False),
    (None, False, False, False),
])
def test_document_type_classification(document_type, annual, quarterly, amendment):
    assert is_annual_document_type(document_type) is annual
    assert is_quarterly_document_type(document_type) is quarterly
    assert is_amendment_document_type(document_type) is amendment

"""
Context periods are read as xbrli:dateUnion values, not raw text.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1762

The instance parser stored the raw text of ``instant``, ``startDate`` and
``endDate``. A whitespace-padded date got its own period key with the spaces in
it, a whole-day dateTime got a key apart from the date it equals, and neither
reached ``reporting_periods`` because that is built with ``strptime('%Y-%m-%d')``.
Both readers now collapse whitespace and fold a whole-day dateTime onto its
date (XBRL 2.1 §4.7.2: a date-only instant or endDate is the end of that day).

The EDGAR Filer Manual requires plain yyyy-mm-dd dates, so no SEC filing writes
these forms. The first test therefore takes a real instance, IBM's 10-K for
fiscal 2024 (accession 0000051143-25-000015, the tracked EDGAR-extracted
instance ``tests/fixtures/xbrl/ibm/10k_2024/ibm-20241231_htm.xml``), respells
its fiscal-2024 periods in the equivalent dateUnion forms, and checks that the
filed values still land in the same periods and statements. The second test is
the issue's minimal synthetic instance.

Forever contexts are not covered here: where a forever fact belongs in a
dated statement column is an open design question on the issue.
"""
import tempfile
from pathlib import Path

import pytest

from edgar.dates import normalize_period_boundary
from edgar.documents.strategies.xbrl_extraction import XBRLExtractor
from edgar.xbrl import XBRL

IBM_DIR = Path(__file__).parents[2] / "fixtures" / "xbrl" / "ibm" / "10k_2024"


def _respelled_ibm_instance(tmp_path: Path) -> Path:
    text = (IBM_DIR / "ibm-20241231_htm.xml").read_text(encoding="utf-8")
    # The same instants and durations, written as other members of the value space.
    text = text.replace("<instant>2024-12-31</instant>", "<instant>2025-01-01T00:00:00</instant>")
    text = text.replace("<startDate>2024-01-01</startDate>", "<startDate>\n  2024-01-01T00:00:00 </startDate>")
    text = text.replace("<endDate>2024-12-31</endDate>", "<endDate> 2024-12-31\n</endDate>")
    path = tmp_path / "ibm-20241231_htm.xml"
    path.write_text(text, encoding="utf-8")
    return path


def _ibm_xbrl(instance: Path) -> XBRL:
    return XBRL.from_files(
        instance_file=instance,
        presentation_file=IBM_DIR / "ibm-20241231_pre.xml",
        label_file=IBM_DIR / "ibm-20241231_lab.xml",
        calculation_file=IBM_DIR / "ibm-20241231_cal.xml",
    )


def _line_value(statement_data, concept, period_key):
    for item in statement_data:
        if item["concept"] == concept and not item.get("is_dimension"):
            if period_key in item["values"]:
                return item["values"][period_key]
    raise AssertionError(f"{concept} has no value for {period_key}")


@pytest.fixture(scope="module")
def ibm_pair():
    with tempfile.TemporaryDirectory() as tmp:
        respelled = _ibm_xbrl(_respelled_ibm_instance(Path(tmp)))
    return _ibm_xbrl(IBM_DIR / "ibm-20241231_htm.xml"), respelled


def test_ibm_respelled_periods_keep_their_keys(ibm_pair):
    original, respelled = ibm_pair
    assert respelled.context_period_map["c-73"] == "instant_2024-12-31"
    assert respelled.context_period_map["c-1"] == "duration_2024-01-01_2024-12-31"
    assert [p["key"] for p in respelled.reporting_periods] == [p["key"] for p in original.reporting_periods]
    fy2024 = next(p for p in respelled.reporting_periods if p["key"] == "duration_2024-01-01_2024-12-31")
    assert fy2024["days"] == 366


def test_ibm_respelled_periods_reach_the_statements(ibm_pair):
    _, respelled = ibm_pair
    balance_sheet = respelled.get_statement("BalanceSheet")
    assert _line_value(balance_sheet, "us-gaap_Assets", "instant_2024-12-31") == 137_175_000_000
    assert _line_value(balance_sheet, "us-gaap_Assets", "instant_2023-12-31") == 135_241_000_000
    income = respelled.get_statement("IncomeStatement")
    assert _line_value(income, "us-gaap_Revenues", "duration_2024-01-01_2024-12-31") == 62_753_000_000


def _ctx(cid, period):
    return (f'<xbrli:context id="{cid}"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">'
            f'0000000001</xbrli:identifier></xbrli:entity><xbrli:period>{period}</xbrli:period></xbrli:context>')


def test_issue_synthetic_instance(tmp_path):
    periods = {"C1": "<xbrli:instant>2025-01-01T00:00:00</xbrli:instant>",
               "C2": "<xbrli:instant>2024-12-31</xbrli:instant>",
               "C3": "<xbrli:instant> 2024-06-30 </xbrli:instant>"}
    facts = "".join(f'<us-gaap:Cash contextRef="{c}" unitRef="USD" decimals="0">{i}00</us-gaap:Cash>'
                    for i, c in enumerate(periods, 1))
    instance = ('<?xml version="1.0" encoding="utf-8"?>'
                '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
                'xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:us-gaap="http://fasb.org/us-gaap/2024">'
                + "".join(_ctx(c, p) for c, p in periods.items())
                + '<xbrli:unit id="USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
                + facts + '</xbrli:xbrl>')
    path = tmp_path / "min.xml"
    path.write_text(instance, encoding="utf-8")
    x = XBRL.from_files(instance_file=path)
    assert x.context_period_map == {"C1": "instant_2024-12-31", "C2": "instant_2024-12-31",
                                    "C3": "instant_2024-06-30"}
    assert [p["key"] for p in x.reporting_periods] == ["instant_2024-12-31", "instant_2024-06-30"]


@pytest.mark.parametrize("text,is_end,expected", [
    ("2024-12-31", True, "2024-12-31"),
    (" 2024-06-30\n", True, "2024-06-30"),
    ("2025-01-01T00:00:00", True, "2024-12-31"),       # end of 2024-12-31
    ("2024-12-31T24:00:00", True, "2024-12-31"),
    ("2024-01-01T00:00:00", False, "2024-01-01"),      # start of 2024-01-01
    ("2023-12-31T24:00:00", False, "2024-01-01"),
    ("2025-03-01T00:00:00.000", True, "2025-02-28"),
    # No date-only equivalent: only the whitespace is collapsed.
    ("2024-12-31T12:30:00", True, "2024-12-31T12:30:00"),
    (" 2025-01-01T00:00:00Z ", True, "2025-01-01T00:00:00Z"),
])
def test_period_boundary_reading(text, is_end, expected):
    assert normalize_period_boundary(text, is_end=is_end) == expected


def test_inline_context_reader_uses_the_same_rule():
    from lxml import html as lxml_html
    doc = lxml_html.fromstring(
        '<html><body><div><ix:resources><xbrli:context id="d1"><xbrli:entity>'
        '<xbrli:identifier scheme="http://www.sec.gov/CIK">1</xbrli:identifier></xbrli:entity>'
        '<xbrli:period><xbrli:startDate>2024-01-01T00:00:00</xbrli:startDate>'
        '<xbrli:endDate> 2025-01-01T00:00:00 </xbrli:endDate></xbrli:period></xbrli:context>'
        '</ix:resources></div></body></html>')
    extractor = XBRLExtractor()
    context = extractor._find_first(doc, "context")
    assert extractor._extract_period(context) == {
        "start_date": "2024-01-01", "end_date": "2024-12-31", "period_type": "duration"}

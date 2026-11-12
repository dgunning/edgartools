"""
Regression test for GitHub issue #1208: entity_info['reporting_end_date'] was not the period end

reporting_end_date was the latest instant among all of a filing's contexts. That
is usually the cover's share-count date, weeks after the period the document
reports on, and it can be anything a filer types: American Airlines' 10-Q for
the quarter to 2026-06-30 dates its share count 2027-07-17.

reporting_end_date is now dei:DocumentPeriodEndDate as a date, and the old
value moves to max_instant_context_date. document_period_end_date stays the
filed string.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1208
"""

from datetime import date
from pathlib import Path

from edgar.xbrl.parsers import XBRLParser

FIXTURES = Path("tests/fixtures/xbrl")

# Apple FY2023 10-K, 0000320193-23-000106: shares outstanding as of 2023-10-20
AAPL = FIXTURES / "aapl/10k_2023/aapl-20230930_htm.xml"
# American Airlines Q2 2026 10-Q, 0000006201-26-000052: shares outstanding "as of" 2027-07-17
AAL = FIXTURES / "aal/10q_2026q2/aal-20260630_htm.xml"


def _entity_info(content):
    parser = XBRLParser()
    parser.parse_instance_content(content)
    return parser.entity_info


def test_apple_reporting_end_date_is_the_fiscal_year_end_not_the_share_count_date():
    info = _entity_info(AAPL.read_bytes())
    assert info["reporting_end_date"] == date(2023, 9, 30)
    assert info["max_instant_context_date"] == date(2023, 10, 20)
    assert info["document_period_end_date"] == "2023-09-30"


def test_american_airlines_reporting_end_date_ignores_a_mistyped_cover_date():
    info = _entity_info(AAL.read_bytes())
    assert info["reporting_end_date"] == date(2026, 6, 30)
    assert info["max_instant_context_date"] == date(2027, 7, 17)


def _cover(*facts):
    body = "\n".join(facts)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:dei="http://xbrl.sec.gov/dei/2025">
<context id="c-1"><entity><identifier scheme="http://www.sec.gov/CIK">0000000001</identifier></entity>
<period><startDate>2025-01-01</startDate><endDate>2025-12-31</endDate></period></context>
<context id="c-2"><entity><identifier scheme="http://www.sec.gov/CIK">0000000001</identifier></entity>
<period><instant>2026-02-14</instant></period></context>
<dei:DocumentType contextRef="c-1">10-K</dei:DocumentType>
{body}
</xbrl>
"""


def test_no_document_period_end_date_means_no_reporting_end_date():
    # None of the tracked instances omits DocumentPeriodEndDate, so this cover is synthetic.
    info = _entity_info(_cover())
    assert info["reporting_end_date"] is None
    assert info["document_period_end_date"] is None
    assert info["max_instant_context_date"] == date(2026, 2, 14)


def test_an_unparseable_document_period_end_date_is_not_a_date():
    info = _entity_info(_cover('<dei:DocumentPeriodEndDate contextRef="c-1">December 31, 2025</dei:DocumentPeriodEndDate>'))
    assert info["reporting_end_date"] is None
    assert info["document_period_end_date"] == "December 31, 2025"


def test_both_keys_exist_before_any_instance_is_parsed():
    info = XBRLParser().entity_info
    assert info["reporting_end_date"] is None
    assert info["max_instant_context_date"] is None

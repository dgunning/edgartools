"""
Regression test for GitHub issue #1501: acceptance_datetime from get_filings() can be hours off

``EntityFiling.acceptance_datetime`` is ``acceptanceDateTime`` from SEC's
submissions JSON, which SEC labels UTC but served 4 h late for Apple (and others)
through October 2026, with the offset following each rebuild of a company's file.
The agreed design (maintainer comment, 2026-10-21): no per-file correction; an
exact ``Filing.accepted_at`` read from ``{accession}-index-headers.html`` as a
tz-aware ``America/New_York`` datetime, a bulk ``Filings.accepted_at()``, and the
JSON value kept as ``reported_acceptance_datetime`` with the old name deprecated.

Ground truth, the "Accepted" time on each filing's SEC index page (read 2026-11-10):
- Apple 10-Q 0000320193-26-000020: 2026-07-31 06:01:02 (EDT, = 10:01:02 UTC)
- Apple director Form 4 0001059235-26-000004: 2026-02-26 18:34:19 (EST, = 23:34:19 UTC)
The pair straddles DST, so a 4 h vs 5 h offset error fails one of them.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1501
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pyarrow as pa
import pytest

from edgar import Filing, Filings
from edgar.entity.filings import EntityFiling
from edgar.exceptions import ParsingError

APPLE_10Q = dict(cik=320193, company="Apple Inc.", form="10-Q", filing_date="2026-07-31",
                 accession_no="0000320193-26-000020")
WAGNER_FORM4 = dict(cik=1059235, company="WAGNER SUSAN", form="4", filing_date="2026-02-26",
                    accession_no="0001059235-26-000004")


@pytest.mark.network
@pytest.mark.vcr
def test_accepted_at_is_the_index_page_time_in_new_york():
    summer = Filing(**APPLE_10Q).accepted_at
    winter = Filing(**WAGNER_FORM4).accepted_at

    assert summer.tzinfo is not None and str(summer.tzinfo) == "America/New_York"
    assert summer.replace(tzinfo=None) == datetime(2026, 7, 31, 6, 1, 2)
    assert summer.astimezone(timezone.utc) == datetime(2026, 7, 31, 10, 1, 2, tzinfo=timezone.utc)
    assert winter.replace(tzinfo=None) == datetime(2026, 2, 26, 18, 34, 19)
    assert winter.astimezone(timezone.utc) == datetime(2026, 2, 26, 23, 34, 19, tzinfo=timezone.utc)


@pytest.mark.network
@pytest.mark.vcr
def test_bulk_accepted_at_matches_one_by_one():
    rows = [APPLE_10Q, WAGNER_FORM4]
    filings = Filings(pa.table({
        "form": [r["form"] for r in rows],
        "company": [r["company"] for r in rows],
        "cik": [r["cik"] for r in rows],
        "filing_date": pa.array([datetime.strptime(r["filing_date"], "%Y-%m-%d").date() for r in rows]),
        "accession_number": [r["accession_no"] for r in rows],
    }))
    times = filings.accepted_at(show_progress=False)
    assert times.name == "accepted_at"
    assert list(times.index) == ["0000320193-26-000020", "0001059235-26-000004"]
    assert str(times.dtype) == "datetime64[ns, America/New_York]"
    assert times["0000320193-26-000020"].tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S") == "2026-07-31 10:01:02"
    assert times["0001059235-26-000004"].tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S") == "2026-02-26 23:34:19"


def _entity_filing(reported):
    return EntityFiling(cik=320193, company="Apple Inc.", form="10-Q", filing_date="2026-07-31",
                        report_date="2026-06-27", reported_acceptance_datetime=reported,
                        accession_no="0000320193-26-000020", file_number="001-36743", items="",
                        size=0, primary_document="aapl-20260627.htm", primary_doc_description="10-Q",
                        is_xbrl=True, is_inline_xbrl=True)


def test_the_json_value_keeps_working_under_its_new_name():
    # 14:01:02Z is what Apple's submissions file reported for this 10-Q in October 2026.
    reported = datetime(2026, 7, 31, 14, 1, 2, tzinfo=timezone.utc)
    filing = _entity_filing(reported)
    assert filing.reported_acceptance_datetime == reported
    with pytest.warns(DeprecationWarning, match="accepted_at"):
        assert filing.acceptance_datetime == reported


def test_to_pandas_keeps_the_sec_column_name_and_the_reported_value():
    # Maintainer decision 2026-11-11: the to_pandas() column keeps SEC's field name
    # (renaming a column cannot warn first), documented as the reported JSON value.
    from edgar.entity.data import create_company_filings

    row = dict(accessionNumber="0000320193-26-000020", filingDate="2026-07-31", reportDate="2026-06-27",
               acceptanceDateTime="2026-07-31T14:01:02.000Z", act="34", form="10-Q", fileNumber="001-36743",
               items="", size=1, isXBRL=1, isInlineXBRL=1, primaryDocument="aapl-20260627.htm",
               primaryDocDescription="10-Q")
    filings = create_company_filings({"recent": {k: [v] for k, v in row.items()}, "files": []},
                                     320193, "Apple Inc.")
    df = filings.to_pandas()
    reported = datetime(2026, 7, 31, 14, 1, 2, tzinfo=timezone.utc)

    assert "acceptanceDateTime" in df.columns
    assert "reported_acceptance_datetime" not in df.columns
    assert df["acceptanceDateTime"].iloc[0] == reported
    assert filings[0].reported_acceptance_datetime == reported


def test_a_header_without_an_acceptance_time_raises():
    filing = Filing(**APPLE_10Q)
    filing.__dict__["index_headers"] = SimpleNamespace(acceptance_datetime=None)
    with pytest.raises(ParsingError, match="0000320193-26-000020"):
        filing.accepted_at  # noqa: B018

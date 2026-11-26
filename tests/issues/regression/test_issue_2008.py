"""GitHub Issue: https://github.com/dgunning/edgartools/issues/2008"""

from datetime import date

import pyarrow as pa
import pytest

from edgar import Company
from edgar.entity.data import create_default_entity_data
from edgar.entity.filings import COMPANY_FILINGS_SCHEMA, EntityFilings


@pytest.fixture
def apple():
    company = Company(320193)
    company._data = create_default_entity_data(company.cik)
    # SEC filing indexes for Apple's FY2023 and FY2024 10-Ks.
    rows = [
        {
            "accession_number": "0000320193-23-000106",
            "filing_date": date(2023, 11, 3),
            "reportDate": "2023-09-30",
            "form": "10-K",
        },
        {
            "accession_number": "0000320193-24-000123",
            "filing_date": date(2024, 11, 1),
            "reportDate": "2024-09-28",
            "form": "10-K",
        },
    ]
    table = pa.Table.from_pylist(rows, schema=COMPANY_FILINGS_SCHEMA)
    company._data.filings = EntityFilings(table, cik=company.cik, company_name="Apple Inc.")
    return company


def test_company_filings_filter_by_report_date(apple):
    filings = apple.get_filings(
        form="10-K", report_date="2023-09-30", amendments=False, trigger_full_load=False
    )
    assert len(filings) == 1
    assert filings[0].accession_no == "0000320193-23-000106"
    assert filings[0].report_date == "2023-09-30"
    assert filings[0].filing_date == date(2023, 11, 3)


def test_report_date_composes_with_filing_date(apple):
    options = {"form": "10-K", "report_date": "2023-09-30", "trigger_full_load": False}
    filings = apple.get_filings(**options, date="2023-11-03")
    assert [filing.accession_no for filing in filings] == ["0000320193-23-000106"]
    assert apple.get_filings(**options, filing_date="2023-09-30").empty
    assert apple.get_filings(
        accession_number="0000320193-23-000106",
        report_date="2023-11-03",
        trigger_full_load=False,
    ).empty


def test_invalid_report_date_raises(apple):
    with pytest.raises(ValueError, match="report_date"):
        apple.get_filings(report_date="2023-02-30", trigger_full_load=False)

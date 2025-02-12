from edgar import *


def test_filing_reports_for_10K():
    filing = Filing(form='10-K', filing_date='2025-02-11', company='HIGHWOODS REALTY LTD PARTNERSHIP', cik=941713, accession_no='0000921082-25-000004')
    reports = filing.reports
    assert reports

    statements = reports.statements
    assert statements

    assert filing.statements

def test_form4_has_no_reports():
    filing = Filing(form='4', filing_date='2025-02-11', company='AMERIPRISE FINANCIAL INC', cik=820027, accession_no='0001415889-25-003646')
    reports = filing.reports
    assert not reports

    statements = filing.statements
    assert not statements
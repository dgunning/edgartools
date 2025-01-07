from edgar import Filing, FilingHomepage

def test_get_filing_period_from_homepage():
    f = Filing(company='VISA INC.', cik=1403161, form='4', filing_date='2025-01-03', accession_no='0001127602-25-000445')
    home = f.homepage
    filing_date, acceptance, period = home.get_filing_dates()
    assert (filing_date, acceptance, period) == ('2025-01-03', '2025-01-03 16:28:38', '2025-01-02')
    assert home.period_of_report == '2025-01-02'
    assert f.period_of_report == '2025-01-02'

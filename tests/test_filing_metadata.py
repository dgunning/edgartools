from edgar import Filing, find

def test_get_filing_period_from_homepage():
    f = Filing(company='VISA INC.', cik=1403161, form='4', filing_date='2025-01-03', accession_no='0001127602-25-000445')
    home = f.homepage
    filing_date, acceptance, period = home.get_filing_dates()
    assert (filing_date, acceptance, period) == ('2025-01-03', '2025-01-03 16:28:38', '2025-01-02')
    assert home.period_of_report == '2025-01-02'
    assert f.period_of_report == '2025-01-02'


def test_get_metadata_from_filing():
    filing = Filing(form='144', filing_date='2024-12-27', company='Bissell John', cik=1863704, accession_no='0001971857-24-000904')
    filing = find("0001959173-24-008236")
    #print(str(filing))
    homepage = filing.homepage
    filing_date, acceptance_datetime, period_of_report = homepage.get_filing_dates()
    assert filing.accession_number
    assert not period_of_report
    assert acceptance_datetime
    assert homepage.url
    assert filing.text_url
    assert filing.document.url

import re
from functools import lru_cache
from pathlib import Path

import httpx
import humanize
import pandas as pd
import pytest

from edgar import get_filings, Filings, Filing, get_company
from edgar.filing import FilingHomepage, FilingDocument, read_fixed_width_index, form_specs, company_specs

pd.options.display.max_colwidth = 200


def test_read_fixed_width_index():
    index_text = Path('data/form.20200318.idx').read_text()
    index_data = read_fixed_width_index(index_text, form_specs)
    index_df = index_data.to_pandas()
    invalid_accession = index_df.query("~accessionNumber.str.match('[0-9]{10}\\-[0-9]{2}\\-[0-9]{6}')")
    assert len(invalid_accession) == 0


def test_read_form_filing_index_year_and_quarter():
    filings: Filings = get_filings(2021, 1)
    assert filings
    assert filings.data
    assert 500000 > len(filings) > 300000

    df = filings.to_pandas()
    assert len(df) == len(filings) == len(filings.data)
    assert filings.data.column_names == ['form', 'company', 'cik', 'filingDate', 'accessionNumber']
    print(filings.data.schema)
    print('Bytes', humanize.naturalsize(filings.data.nbytes, binary=True))
    assert filings.data[0][0].as_py() == '1-A'


def test_read_form_filing_index_year():
    filings: Filings = get_filings(2021)
    assert filings
    assert filings.data
    assert 1500000 > len(filings) > 1000000

    df = filings.to_pandas()
    assert len(df) == len(filings) == len(filings.data)
    assert filings.data.column_names == ['form', 'company', 'cik', 'filingDate', 'accessionNumber']
    print(filings.data.schema)

    print('Bytes', humanize.naturalsize(filings.data.nbytes, binary=True))


def test_read_company_filing_index_year_and_quarter():
    company_filings: Filings = get_filings(year=2022, quarter=2, index="company")
    assert company_filings
    assert company_filings.data
    assert 500000 > len(company_filings) > 200000

    df = company_filings.to_pandas()
    assert len(df) == len(company_filings) == len(company_filings.data)
    assert company_filings.data.column_names == ['company', 'form', 'cik', 'filingDate', 'accessionNumber']
    print(company_filings.data.schema)

    print('Bytes', humanize.naturalsize(company_filings.data.nbytes, binary=True))


def test_read_form_filing_index_xbrl():
    filings: Filings = get_filings(2021, 1, index="xbrl")
    assert filings.data
    assert 40000 > len(filings) > 10000

    df = filings.to_pandas()
    assert len(df) == len(filings) == len(filings.data)
    assert filings.data.column_names == ['cik', 'company', 'form', 'filingDate', 'accessionNumber']
    print(filings.data.schema)
    print(filings.to_pandas())
    print('Bytes', humanize.naturalsize(filings.data.nbytes, binary=True))
    assert re.match(r'\d{10}\-\d{2}\-\d{6}', filings.data[4][-1].as_py())


def test_get_filings_gets_correct_accession_number():
    # Get the filings and test that the accession number is correct for all rows e.g. 0001185185-20-000088
    filings: Filings = get_filings(2021, 1)
    data = filings.data.to_pandas()
    misparsed_accessions = data.query("accessionNumber.str.endswith('.')")
    assert len(misparsed_accessions) == 0


@lru_cache(maxsize=8)
def cached_filings(year: int, quarter: int, index: str):
    return get_filings(year, quarter, index=index)


def test_filings_date_range():
    filings: Filings = cached_filings(2021, 1, index="xbrl")
    start_date, end_date = filings.date_range
    print(start_date, end_date)
    assert end_date > start_date


def test_filings_repr():
    filings: Filings = cached_filings(2021, 1, index="xbrl")
    filings_repr = str(filings)
    assert filings_repr


def test_filing_head():
    filings: Filings = cached_filings(2021, 1, index="xbrl")
    assert len(filings) > 100
    top_10_filings = filings.head(10)
    assert len(top_10_filings) == 10

    # Try to get 20 filings should still return 10
    assert len(top_10_filings.head(20)) == 10

    # Try to get zero rows
    with pytest.raises(AssertionError):
        top_10_filings.head(0)

    # Try to get negative rows
    with pytest.raises(AssertionError):
        top_10_filings.head(-1)

    assert filings[0] == top_10_filings[0]


def test_filing_tail():
    filings: Filings = cached_filings(2021, 1, index="xbrl")
    assert len(filings) > 100
    bottom_10_filings = filings.tail(10)
    assert len(bottom_10_filings) == 10

    # Try to get 20 filings should still return 10
    assert len(bottom_10_filings.head(20)) == 10

    # Try to get zero rows
    with pytest.raises(AssertionError):
        bottom_10_filings.tail(0)

    # Try to get negative rows
    with pytest.raises(AssertionError):
        bottom_10_filings.tail(-1)

    assert filings[-1] == bottom_10_filings[-1]


def test_filings_latest():
    filings: Filings = cached_filings(2021, 1, index="xbrl")
    latest_filings = filings.latest(20)
    assert len(latest_filings) == 20
    start_date, end_date = latest_filings.date_range
    assert (start_date.year, start_date.month, start_date.day) == (2021, 3, 31)
    assert (end_date.year, end_date.month, end_date.day) == (2021, 3, 31)


def test_iterate_filings():
    filings: Filings = cached_filings(2021, 1, index="xbrl").head(10)
    for index, filing in enumerate(filings):
        assert filing


carbo_10K = Filing(form='10-K', company='CARBO CERAMICS INC', cik=1009672, date='2018-03-08',
                   accession_no='0001564590-18-004771')

four37_capital_staff_filing = Filing(form='SEC STAFF ACTION', company='437 CAPITAL Fund Corp', cik=1805559,
                                     date='2022-03-24', accession_no='9999999997-22-001189')


def test_filing_homepage_url():
    assert carbo_10K.homepage_url == "https://www.sec.gov/Archives/edgar/data/1009672/0001564590-18-004771-index.html"
    r = httpx.get(carbo_10K.homepage_url, headers={'User-Agent': 'Dwight Gunning dgunning@gmail.com'})
    assert r.status_code == 200


def test_filing_primary_document():
    homepage_url = four37_capital_staff_filing.homepage_url
    assert homepage_url == 'https://www.sec.gov/Archives/edgar/data/1805559/9999999997-22-001189-index.html'
    homepage: FilingHomepage = four37_capital_staff_filing.homepage
    assert homepage
    primary_document = homepage.primary_document
    assert primary_document
    company = get_company(cik=1805559)
    filings = company.get_filings()
    print(filings.to_pandas("form", "filingDate", "primaryDocument"))
    filing = filings[0]
    assert filing


def test_filing_homepage_for_filing():
    filing_homepage: FilingHomepage = carbo_10K.homepage
    assert 'Description'
    assert len(filing_homepage.documents) > 8
    assert len(filing_homepage.datafiles) >= 6
    assert filing_homepage.url == carbo_10K.url


def test_filing_document():
    assert carbo_10K.homepage.primary_document.url == \
           'https://www.sec.gov/Archives/edgar/data/1009672/000156459018004771/crr-10k_20171231.htm'


def test_xbrl_document():
    xbrl_document = carbo_10K.homepage.xbrl_document
    assert xbrl_document.url == \
           'https://www.sec.gov/Archives/edgar/data/1009672/000156459018004771/crr-20171231.xml'


def test_get_matching_document():
    filing_document = carbo_10K.homepage.get_matching_document("Seq=='1'")
    assert filing_document
    assert filing_document.seq == 1
    assert filing_document.path == '/Archives/edgar/data/1009672/000156459018004771/crr-10k_20171231.htm'
    assert filing_document.url == 'https://www.sec.gov/Archives/edgar/data' + \
           '/1009672/000156459018004771/crr-10k_20171231.htm'
    assert filing_document.name == 'crr-10k_20171231.htm'


def test_filing_homepage_get_by_seq():
    filing_document = carbo_10K.homepage.get_by_seq(1)
    assert filing_document
    assert carbo_10K.homepage.get_by_seq(1) == carbo_10K.homepage.get_by_seq("1")

    # Now get a datafile by seq
    datafile = carbo_10K.homepage.get_by_seq(17)
    print(datafile)


def test_download_filing_document():
    filing_document = carbo_10K.homepage.get_matching_document("Seq=='1'")
    contents = filing_document.download()
    assert '<html>' in contents


def test_filings_get_item_as_filing():
    filings: Filings = get_filings(2021, 1, index="xbrl")
    filing: Filing = filings[0]
    assert filing
    assert isinstance(filing.cik, int)
    assert isinstance(filing.form, str)
    assert isinstance(filing.company, str)
    assert isinstance(filing.accession_no, str)
    print(filing)


def test_form_specs():
    assert form_specs.splits[0] == (0, 12)
    assert form_specs.splits[1] == (12, 74)
    assert form_specs.schema.names[:2] == ['form', 'company']


def test_company_specs():
    assert company_specs.splits[0] == (0, 62)
    assert company_specs.splits[1] == (62, 74)
    assert company_specs.schema.names[:2] == ['company', 'form']


def test_filings_toduckdb():
    filings = cached_filings(2022, 3, "xbrl")
    filings_db = filings.to_duckdb()
    result_df = filings_db.execute("""
    select * from filings where form=='10-Q'
    """).df()
    assert len(result_df.form.drop_duplicates()) == 1


def test_filing_primary_document():
    filing = Filing(form='DEF 14A', company='180 DEGREE CAPITAL CORP. /NY/', cik=893739, date='2020-03-25',
                    accession_no='0000893739-20-000019')
    primary_document: FilingDocument = filing.primary_document
    assert primary_document
    assert primary_document.url == \
           'https://www.sec.gov/Archives/edgar/data/893739/000089373920000019/annualmeetingproxy2020-doc.htm'
    assert primary_document.extension == '.htm'
    assert primary_document.seq == 1


barclays_filing = Filing(form='ATS-N/MA', company='BARCLAYS CAPITAL INC.', cik=851376, date='2020-02-21',
                         accession_no='0000851376-20-000003')


def test_filing_primary_document_seq_5():
    primary_document: FilingDocument = barclays_filing.primary_document
    assert primary_document
    assert primary_document.url == \
           'https://www.sec.gov/Archives/edgar/data/851376/000085137620000003/xslATSN_COVER_X01/coverpage.xml'
    assert primary_document.extension == '.xml'
    assert primary_document.seq == 5


def test_filing_html():
    filing = Filing(form='10-K', company='10x Genomics, Inc.',
                    cik=1770787, date='2020-02-27',
                    accession_no='0001193125-20-052640')
    html = filing.html()
    assert html
    assert "<HTML>" in html


def test_filing_html_is_non_for_xml_filing():
    html = barclays_filing.html()
    assert html is None

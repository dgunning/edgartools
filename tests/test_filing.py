from edgar import get_filings, Filings, Filing
from edgar.filing import form_specs, company_specs, FilingHomepage
import humanize
import re
import httpx
import pandas as pd

pd.options.display.max_colwidth = 200


def test_read_form_filing_index_year_and_quarter():
    filings: Filings = get_filings(2021, 1)
    assert filings
    assert filings.filing_index
    assert 500000 > len(filings) > 300000

    df = filings.to_pandas()
    assert len(df) == len(filings) == len(filings.filing_index)
    assert filings.filing_index.column_names == ['form', 'company', 'cik', 'filingDate', 'accessionNumber']
    print(filings.filing_index.schema)
    print('Bytes', humanize.naturalsize(filings.filing_index.nbytes, binary=True))
    assert filings.filing_index[0][0].as_py() == '1-A'


def test_read_form_filing_index_year():
    filings: Filings = get_filings(2021)
    assert filings
    assert filings.filing_index
    assert 1500000 > len(filings) > 1000000

    df = filings.to_pandas()
    assert len(df) == len(filings) == len(filings.filing_index)
    assert filings.filing_index.column_names == ['form', 'company', 'cik', 'filingDate', 'accessionNumber']
    print(filings.filing_index.schema)

    print('Bytes', humanize.naturalsize(filings.filing_index.nbytes, binary=True))


def test_read_company_filing_index_year_and_quarter():
    company_filings: Filings = get_filings(year=2022, quarter=2, index="company")
    assert company_filings
    assert company_filings.filing_index
    assert 500000 > len(company_filings) > 200000

    df = company_filings.to_pandas()
    assert len(df) == len(company_filings) == len(company_filings.filing_index)
    assert company_filings.filing_index.column_names == ['company', 'form', 'cik', 'filingDate', 'accessionNumber']
    print(company_filings.filing_index.schema)

    print('Bytes', humanize.naturalsize(company_filings.filing_index.nbytes, binary=True))


def test_read_form_filing_index_xbrl():
    filings: Filings = get_filings(2021, 1, index="xbrl")
    assert filings.filing_index
    assert 40000 > len(filings) > 10000

    df = filings.to_pandas()
    assert len(df) == len(filings) == len(filings.filing_index)
    assert filings.filing_index.column_names == ['cik', 'company', 'form', 'filingDate', 'accessionNumber']
    print(filings.filing_index.schema)
    print(filings.to_pandas())
    print('Bytes', humanize.naturalsize(filings.filing_index.nbytes, binary=True))
    assert re.match(r'\d{10}\-\d{2}\-\d{6}', filings.filing_index[4][-1].as_py())


def test_filings_date_range():
    filings: Filings = get_filings(2021, 1, index="xbrl")
    start_date, end_date = filings.date_range
    print(start_date, end_date)
    assert end_date > start_date


def test_filings_repr():
    filings: Filings = get_filings(2021, 1, index="xbrl")
    filings_repr = str(filings)
    assert filings_repr


def test_iterate_filings():
    filings: Filings = get_filings(2021, 1, index="xbrl")
    count = 0
    for filing in filings:
        assert filing
        count += 1
        if count >= 10:
            break

    print(filings)


carbo_10K = Filing(form='10-K', company='CARBO CERAMICS INC', cik=1009672, date='2018-03-08',
                   accession_no='0001564590-18-004771')


def test_filing_homepage_url():
    assert carbo_10K.homepage_url == "https://www.sec.gov/Archives/edgar/data/1009672/0001564590-18-004771-index.html"
    r = httpx.get(carbo_10K.homepage_url, headers={'User-Agent': 'Dwight Gunning dgunning@gmail.com'})
    assert r.status_code == 200


def test_filing_homepage_for_filing():
    filing_homepage: FilingHomepage = carbo_10K.get_homepage()
    assert 'Description'
    assert len(filing_homepage.documents) > 8
    assert len(filing_homepage.datafiles) >= 6


def test_filing_document():
    assert carbo_10K.get_homepage().filing_document.url == \
           'https://www.sec.gov/Archives/edgar/data/1009672/000156459018004771/crr-10k_20171231.htm'


def test_xbrl_document():
    xbrl_document = carbo_10K.get_homepage().xbrl_document
    assert xbrl_document.url == \
           'https://www.sec.gov/Archives/edgar/data/1009672/000156459018004771/crr-20171231.xml'


def test_get_matching_document():
    filing_document = carbo_10K.get_homepage().get_matching_document("Seq=='1'")
    assert filing_document
    assert filing_document.seq == 1
    assert filing_document.path == '/Archives/edgar/data/1009672/000156459018004771/crr-10k_20171231.htm'
    assert filing_document.url == 'https://www.sec.gov/Archives/edgar/data' + \
           '/1009672/000156459018004771/crr-10k_20171231.htm'
    assert filing_document.name == 'crr-10k_20171231.htm'


def test_filing_homepage_get_by_seq():
    filing_document = carbo_10K.get_homepage().get_by_seq(1)
    assert filing_document
    assert carbo_10K.get_homepage().get_by_seq(1) == carbo_10K.get_homepage().get_by_seq("1")

    # Now get a datafile by seq
    datafile = carbo_10K.get_homepage().get_by_seq(17)
    print(datafile)


def test_download_filing_document():
    filing_document = carbo_10K.get_homepage().get_matching_document("Seq=='1'")
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


def test_open_homepage():
    carbo_10K.open_homepage()


def test_open_filing():
    carbo_10K.open_filing()

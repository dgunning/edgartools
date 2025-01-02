import datetime
import re
import tempfile
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import List
from unittest.mock import patch, MagicMock

import httpx
import humanize
import pandas as pd
import pytest
from rich import print

from edgar import get_filings, Filings, Filing, get_entity, get_by_accession_number
from edgar._filings import FilingHomepage, read_fixed_width_index, form_specs, company_specs, Attachment, \
    get_current_filings, fetch_daily_filing_index, filing_date_to_year_quarters, get_filing_by_accession
from edgar.company_reports import TenK
from edgar.core import default_page_size
from edgar.entities import Company

pd.options.display.max_colwidth = 200


@pytest.fixture(scope='module')
def filings_2022_q3():
    return get_filings(2022, 3)


@pytest.fixture(scope='module')
def filings_2021_q1():
    return get_filings(2021, 1)


@pytest.fixture(scope='module')
def filings_2021_q1_xbrl():
    return get_filings(2021, 1, index="xbrl")


def test_read_fixed_width_index_for_daily_file():
    index_text = Path('data/form.20200318.idx').read_text()
    index_data = read_fixed_width_index(index_text, form_specs)
    index_df = index_data.to_pandas()
    invalid_accession = index_df.query("~accession_number.str.match(r'[0-9]{10}\\-[0-9]{2}\\-[0-9]{6}')")
    assert len(invalid_accession) == 0
    # The first record is there
    assert index_df.iloc[0]['accession_number'] == '0001140361-20-006155'
    # The last record is there
    assert index_df.iloc[-1]['accession_number'] == '0001105608-20-000004'


def test_read_fixed_width_index_for_quarterly_file():
    index_text = Path('data/form.idx').read_text()
    index_data = read_fixed_width_index(index_text, form_specs)
    index_df = index_data.to_pandas()
    # The first record is there
    assert index_df.iloc[0]['accession_number'] == '0001683168-24-000531'
    # The last record is there
    assert index_df.iloc[-1]['accession_number'] == '0001085910-24-000002'


def test_read_form_filing_index_year_and_quarter():
    filings: Filings = get_filings(2021, 1)
    assert filings
    assert filings.data
    assert 500000 > len(filings) > 300000

    df = filings.to_pandas()
    assert len(df) == len(filings) == len(filings.data)
    assert filings.data.column_names == ['form', 'company', 'cik', 'filing_date', 'accession_number']
    print(filings.data.schema)
    print('Bytes', humanize.naturalsize(filings.data.nbytes, binary=True))
    assert filings.data[0][0].as_py() == '10-Q'


def test_read_form_filing_index_year():
    filings: Filings = get_filings(2021)
    assert filings
    assert filings.data
    assert 1500000 > len(filings) > 1000000

    df = filings.to_pandas()
    assert len(df) == len(filings) == len(filings.data)
    assert filings.data.column_names == ['form', 'company', 'cik', 'filing_date', 'accession_number']
    print(filings.data.schema)

    print('Bytes', humanize.naturalsize(filings.data.nbytes, binary=True))


def test_read_form_filing_index_xbrl(filings_2021_q1_xbrl):
    filings: Filings = filings_2021_q1_xbrl
    assert filings.data
    assert 40000 > len(filings) > 10000

    df = filings.to_pandas()
    assert len(df) == len(filings) == len(filings.data)
    assert filings.data.column_names == ['cik', 'company', 'form', 'filing_date', 'accession_number']
    assert re.match(r'\d{10}\-\d{2}\-\d{6}', filings.data[4][-1].as_py())


def test_get_filings_gets_correct_accession_number(filings_2021_q1):
    # Get the filings and test that the accession number is correct for all rows e.g. 0001185185-20-000088
    data = filings_2021_q1.data.to_pandas()
    misparsed_accessions = data.query("accession_number.str.endswith('.')")
    assert len(misparsed_accessions) == 0


@lru_cache(maxsize=8)
def cached_filings(year: int, quarter: int, index: str = "form"):
    return get_filings(year, quarter, index=index)


def test_filings_date_range(filings_2021_q1_xbrl):
    filings: Filings = filings_2021_q1_xbrl
    start_date, end_date = filings.date_range
    assert end_date > start_date


def test_filings_repr(filings_2021_q1_xbrl):
    filings: Filings = filings_2021_q1_xbrl
    print()
    print(filings)
    filings_repr = str(filings)
    assert filings_repr


def test_filing_head(filings_2021_q1_xbrl):
    filings: Filings = filings_2021_q1_xbrl
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


def test_filing_sample(filings_2021_q1_xbrl):
    filings: Filings = filings_2021_q1_xbrl
    sample_filings = filings.sample(10)
    assert len(sample_filings) == 10
    print(sample_filings)

    # Try sampling equal to number of filings
    assert len(filings.sample(5).sample(5)) == 5


def test_filter_filings_by_form(filings_2021_q1_xbrl):
    filings: Filings = filings_2021_q1_xbrl
    forms = list(set(filings.data['form'].to_pylist()))
    assert len(forms) > 25

    tenk_filings = filings.filter(form="10-Q")
    assert list(set(tenk_filings.data['form'].to_pylist())) == ["10-Q"]

    tenk_filings = filings.filter(form="10-Q", amendments=True)
    assert set(tenk_filings.data['form'].to_pylist()) == {"10-Q", '10-Q/A'}


def test_filter_filings_by_date(filings_2021_q1_xbrl):
    filings: Filings = filings_2021_q1_xbrl
    filtered_filings = filings.filter(filing_date='2021-03-04')
    assert len(set(filtered_filings.data['filing_date'].to_pylist())) == 1
    assert not filtered_filings.empty
    assert len(filtered_filings) < len(filings)

    # filter by form and date
    filings_by_date_and_form = filings.filter(form=['10-Q'], filing_date='2021-03-04')
    assert list(set(filings_by_date_and_form.data['form'].to_pylist())) == ['10-Q']
    assert len(set(filings_by_date_and_form.data['filing_date'].to_pylist())) == 1


def test_filing_tail(filings_2021_q1_xbrl):
    filings: Filings = filings_2021_q1_xbrl
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


def test_filings_latest(filings_2021_q1_xbrl):
    filings: Filings = filings_2021_q1_xbrl
    latest_filings = filings.latest(20)
    assert len(latest_filings) == 20
    start_date, end_date = latest_filings.date_range
    assert (start_date.year, start_date.month, start_date.day) == (2021, 3, 31)
    assert (end_date.year, end_date.month, end_date.day) == (2021, 3, 31)


def test_iterate_filings(filings_2021_q1_xbrl):
    filings: Filings = filings_2021_q1_xbrl.head(10)
    for index, filing in enumerate(filings):
        assert filing


carbo_10K = Filing(form='10-K', company='CARBO CERAMICS INC', cik=1009672, filing_date='2018-03-08',
                   accession_no='0001564590-18-004771')

four37_capital_staff_filing = Filing(form='SEC STAFF ACTION', company='437 CAPITAL Fund Corp', cik=1805559,
                                     filing_date='2022-03-24', accession_no='9999999997-22-001189')


def test_filing_homepage_url():
    assert carbo_10K.homepage_url == "https://www.sec.gov/Archives/edgar/data/1009672/0001564590-18-004771-index.html"
    r = httpx.get(carbo_10K.homepage_url, headers={'User-Agent': 'Mike Banton mb@yahoo.com'})
    assert r.status_code == 200


def test_filing_primary_document():
    homepage_url = four37_capital_staff_filing.homepage_url
    assert homepage_url == 'https://www.sec.gov/Archives/edgar/data/1805559/9999999997-22-001189-index.html'
    homepage: FilingHomepage = four37_capital_staff_filing.homepage
    assert homepage
    primary_document = homepage.primary_document
    assert primary_document
    company = get_entity(1805559)
    filings = company.get_filings()
    print(filings.to_pandas("form", "filing_date", "primaryDocument"))
    filing = filings[0]
    assert filing


def test_filing_homepage_for_filing():
    filing_homepage: FilingHomepage = carbo_10K.homepage
    assert 'Description'
    assert filing_homepage.url == carbo_10K.url
    assert carbo_10K.home == carbo_10K.homepage


def test_filing_homepage_for_filing_multiple_instruments():
    filing = Filing(form='DEF 14A', filing_date='2023-06-16', company='T. Rowe Price All-Cap Opportunities Fund, Inc.',
                    cik=773485, accession_no='0001741773-23-002051')
    homepage: FilingHomepage = filing.homepage
    print(homepage)
    assert homepage


def test_filing_homepage_documents_and_datafiles():
    filing_homepage: FilingHomepage = carbo_10K.homepage
    assert 'Description'
    assert len(filing_homepage.documents) > 8
    assert len(filing_homepage.datafiles) >= 6
    assert filing_homepage.url == carbo_10K.url


def test_parse_filing_homepage_with_multiple_instruments():
    filing = Filing(form='DEF 14A', filing_date='2023-06-16', company='T. Rowe Price All-Cap Opportunities Fund, Inc.',
                    cik=773485, accession_no='0001741773-23-002051')

    homepage_html = Path('data/troweprice.DEF14A.html').read_text()
    filing_homepage = filing.homepage

    filers = filing_homepage.get_filers()
    assert len(filing_homepage.get_filers()) > 60
    filer_info = filers[0]
    assert filer_info.company_name == "T. Rowe Price Small-Cap Stock Fund, Inc."
    assert "100 EAST PRATT STRET" in filer_info.addresses[0]


def test_filing_document():
    assert carbo_10K.homepage.primary_html_document.url == \
           'https://www.sec.gov/Archives/edgar/data/1009672/000156459018004771/crr-10k_20171231.htm'


def test_xbrl_document():
    xbrl_document = carbo_10K.homepage.xbrl_document
    assert xbrl_document.url == \
           'https://www.sec.gov/Archives/edgar/data/1009672/000156459018004771/crr-20171231.xml'


def test_filing_homepage_get_file():
    filing_document = carbo_10K.homepage.attachments.get_by_sequence(1)
    assert filing_document
    assert filing_document.sequence_number == '1'
    assert filing_document.path == '/Archives/edgar/data/1009672/000156459018004771/crr-10k_20171231.htm'
    assert filing_document.url == 'https://www.sec.gov/Archives/edgar/data' + \
           '/1009672/000156459018004771/crr-10k_20171231.htm'
    assert filing_document.document == 'crr-10k_20171231.htm'


def test_download_filing_document():
    filing_document = carbo_10K.homepage.primary_html_document
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


def test_filing_primary_document():
    filing = Filing(form='DEF 14A', company='180 DEGREE CAPITAL CORP. /NY/', cik=893739, filing_date='2020-03-25',
                    accession_no='0000893739-20-000019')
    primary_document: Attachment = filing.document
    assert primary_document
    assert primary_document.url == \
           'https://www.sec.gov/Archives/edgar/data/893739/000089373920000019/annualmeetingproxy2020-doc.htm'
    assert primary_document.extension == '.htm'
    assert primary_document.sequence_number == '1'


barclays_filing = Filing(form='ATS-N/MA', company='BARCLAYS CAPITAL INC.', cik=851376, filing_date='2020-02-21',
                         accession_no='0000851376-20-000003')


def test_filing_primary_document_seq_5():
    primary_document: Attachment = barclays_filing.document
    assert primary_document
    assert primary_document.url == \
           'https://www.sec.gov/Archives/edgar/data/851376/000085137620000003/xslATSN_COVER_X01/coverpage.xml'
    assert primary_document.extension == '.xml'
    assert primary_document.sequence_number == '5'


def test_filing_html():
    filing = Filing(form='10-K', company='10x Genomics, Inc.',
                    cik=1770787, filing_date='2020-02-27',
                    accession_no='0001193125-20-052640')
    html = filing.html()
    assert html
    assert "<HTML>" in html
    assert "10x Genomics, Inc." in html


def test_filing_markdown():
    filing = Filing(form='10-K', company='10x Genomics, Inc.',
                    cik=1770787, filing_date='2020-02-27',
                    accession_no='0001193125-20-052640')
    markdown = filing.markdown()
    assert markdown
    assert "10x Genomics, Inc." in markdown


ONE_800_FLOWERS_10Q = Filing(form='10-Q', company='1 800 FLOWERS COM INC',
                             cik=1084869, filing_date='2023-02-10',
                             accession_no='0001437749-23-002992')


def test_filing_url_for_ixbrl_filing():
    # ixbrl url
    'https://www.sec.gov/ix.xhtml?doc=/Archives/edgar/data/1084869/000143774923002992/flws20230101_10q.htm'

    # actual url
    actual_url = 'https://www.sec.gov/Archives/edgar/data/1084869/000143774923002992/flws20230101_10q.htm'

    assert ONE_800_FLOWERS_10Q.document.url == actual_url


def test_filing_html_for_ixbrl_filing():
    filing = ONE_800_FLOWERS_10Q
    html = filing.html()
    assert html
    assert "1-800-FLOWERS.COM" in html

    filing = Filing(form='10-Q', company='RALPH LAUREN CORP',
                    cik=1037038, filing_date='2023-02-10',
                    accession_no='0001037038-23-000009')
    assert "RALPH LAUREN" in filing.html()


def test_filing_text():
    filing = Filing(form='10-K', company='10x Genomics, Inc.',
                    cik=1770787, filing_date='2020-02-27',
                    accession_no='0001193125-20-052640')
    text_document = filing.homepage.text_document
    assert text_document.description == "Complete submission text file"
    assert text_document.document == "0001193125-20-052640.txt"
    assert text_document
    # Get the text
    text = filing.full_text_submission()
    assert text
    assert "ACCESSION NUMBER:		0001193125-20-052640" in text


def test_primary_xml_for_10k():
    filing = Filing(form='10-K', company='10x Genomics, Inc.',
                    cik=1770787, filing_date='2020-02-27',
                    accession_no='0001193125-20-052640')
    xml_document = filing.homepage.primary_xml_document
    assert xml_document is None
    html_document = filing.document
    assert html_document
    primary_documents = filing.primary_documents
    print(primary_documents)
    assert len(primary_documents) == 1


def test_filing_html_is_xhtml_for_xml_filing():
    html = barclays_filing.html()
    assert "-//W3C//DTD XHTML 1.0 Strict//EN" in html


def test_filing_html_for_pdf_only_filing():
    filing = Filing(form='40-17G', filing_date='2024-02-27', company='FIDELITY CAPITAL TRUST', cik=275309,
                    accession_no='0000880195-24-000030')
    assert not filing.html()


def test_filing_homepage_primary_documents():
    filing = Filing(form='4', company='Orion Engineered Carbons S.A.',
                    cik=1609804, filing_date='2022-11-04',
                    accession_no='0000950142-22-003095')
    print()
    primary_documents: List[Attachment] = filing.homepage.primary_documents
    assert len(primary_documents) == 2

    primary_html = primary_documents[0]
    assert primary_html.sequence_number == '1'
    assert primary_html.document == 'es220296680_4-davis.html'  # Displayed as html
    assert primary_html.description == 'OWNERSHIP DOCUMENT'
    assert primary_html.path.endswith('xslF345X03/es220296680_4-davis.xml')
    assert primary_html.display_extension == '.html'

    primary_xml = primary_documents[1]
    assert primary_xml.sequence_number == '1'
    assert primary_xml.document == 'es220296680_4-davis.xml'
    assert primary_xml.description == 'OWNERSHIP DOCUMENT'
    assert primary_xml.path.endswith('000095014222003095/es220296680_4-davis.xml')
    assert primary_xml.display_extension == '.xml'


orion_form4 = Filing(form='4', company='Orion Engineered Carbons S.A.',
                     cik=1609804, filing_date='2022-11-04',
                     accession_no='0000950142-22-003095')


def test_filing_primary_xml_document():
    xml_document = orion_form4.homepage.primary_xml_document
    print(xml_document)
    assert xml_document.display_extension == ".xml"
    assert xml_document.document == "es220296680_4-davis.xml"
    assert xml_document.path == "/Archives/edgar/data/1300650/000095014222003095/es220296680_4-davis.xml"

    html_document = orion_form4.homepage.primary_html_document
    print(html_document)
    assert html_document.display_extension == ".html"
    assert html_document.document == "es220296680_4-davis.html"
    assert html_document.path == "/Archives/edgar/data/1300650/000095014222003095/xslF345X03/es220296680_4-davis.xml"


def test_filing_xml_downoads_xml_if_filing_has_xml():
    assert carbo_10K.xml() is None
    assert orion_form4.xml()


def test_filing_get_entity():
    company = carbo_10K.get_entity()
    assert company.cik == carbo_10K.cik


def test_get_related_filings():
    related_filings = carbo_10K.related_filings()
    assert len(related_filings) > 200
    file_numbers = list(set(related_filings.data['fileNumber'].to_pylist()))
    assert len(file_numbers) == 1


def test_print_filings():
    filings = get_filings(2022, 1, index="xbrl")
    print(filings)
    print("Works")

    # Filter by form and see if it still prints
    ten_k_filings = filings.filter(form="10-K")
    print(ten_k_filings)

    # Filter with non-existent form
    loop_filings = ten_k_filings.filter("LOOP")
    print(loop_filings)


def test_create_filings_with_empty_table():
    filings = get_filings(2022, 1, index="xbrl")
    data = filings.filter(form="LOOP").data
    filings_copy = Filings(filing_index=data)
    page = filings_copy.data_pager.current()
    assert len(page) == 0
    print(page)
    print(filings_copy)
    assert len(filings_copy) == 0
    assert filings_copy.empty


def test_filing_str():
    filing_str = str(carbo_10K)
    assert str(carbo_10K.cik) in filing_str
    assert str(carbo_10K.company) in filing_str
    assert str(carbo_10K.form) in filing_str
    assert str(carbo_10K.filing_date) in filing_str
    print(filing_str)


def test_filing_repr():
    filing_repr = carbo_10K.__repr__()
    assert str(carbo_10K.cik) in filing_repr
    assert str(carbo_10K.company) in filing_repr
    assert str(carbo_10K.form) in filing_repr
    assert str(carbo_10K.filing_date) in filing_repr
    print(carbo_10K)


def test_filing_homepage_repr():
    homepage = carbo_10K.homepage
    print(homepage.__repr__())


def test_filing_filter_by_form():
    filings = get_filings(2014, 4, form="10-K")
    assert set(filings.data['form'].to_pylist()) == {'10-K', '10-K/A'}

    filings = get_filings(2014, 4, form=["10-K", "8-K"])
    assert set(filings.data['form'].to_pylist()) == {'10-K', '10-K/A', '8-K', '8-K/A'}


def test_filter_by_cik():
    # Test non-xbrl filings
    filings = get_filings(2022, 3).filter(cik=[1078799, 1877934])
    assert len(filings) == 17


def test_filter_by_date():
    # Test non-xbrl filings
    filings = get_filings(2022, 3)
    filings_on_date = filings.filter(filing_date='2022-08-10')
    filing_dates = [d.strftime('%Y-%m-%d') for d in set(filings_on_date.data['filing_date'].to_pylist())]
    assert filing_dates == ['2022-08-10']

    # Test filter by date range
    filings_for_range = filings.filter(filing_date='2022-08-10:2022-08-16')
    filing_dates = [d.strftime('%Y-%m-%d') for d in set(filings_for_range.data['filing_date'].to_pylist())]
    assert sorted(filing_dates) == ['2022-08-10', '2022-08-11', '2022-08-12', '2022-08-15', '2022-08-16']

    # Partial date range
    filings_before = filings.filter(filing_date=':2022-08-16')
    assert not filings_before.empty
    end_date = filings_before.date_range[1]
    assert end_date == datetime.datetime.strptime("2022-08-16", "%Y-%m-%d").date()

    filings_after = filings.filter(filing_date='2022-08-16:')
    assert not filings_after.empty
    start_date = filings_after.date_range[0]
    assert start_date == datetime.datetime.strptime("2022-08-16", "%Y-%m-%d").date()


def test_filter_invalid_date(filings_2022_q3):
    filings = filings_2022_q3
    filtered = filings.filter(filing_date="2022-08:")
    assert not filtered


def test_filter_by_date_xbrl():
    # Test XBRL filings
    filings = get_filings(2022, 3, index="xbrl")
    filings_on_date = filings.filter(filing_date='2022-08-10')
    assert not filings.empty
    assert len(filings) > 500
    filing_dates = [d.strftime('%Y-%m-%d') for d in set(filings_on_date.data['filing_date'].to_pylist())]
    assert filing_dates == ['2022-08-10']


def test_filing_filter_by_form_no_amendments():
    filings = get_filings(2014,
                          4,
                          form="10-K",
                          amendments=False)
    assert set(filings.data['form'].to_pylist()) == {'10-K'}


def test_filings_next_and_previous():
    filings: Filings = cached_filings(2021, 1, index="xbrl")
    print(filings)
    page2 = filings.next()
    assert len(page2) == default_page_size
    print(page2)
    page3 = filings.next()
    print(page3)
    page2_again = filings.previous()
    print(page2_again)

    assert page2[0].accession_no == page2_again[0].accession_no
    assert filings.previous()
    assert not filings.previous()


def test_get_filings_for_future_period(capsys):
    filings = get_filings(2050, 1)
    assert filings is None


def test_get_filings_default():
    filings = get_filings()
    assert filings is not None

    filings = get_filings(form="8-K")
    assert filings is not None


def test_filings_get_by_index_or_accession_number():
    filings = cached_filings(2022, 1)
    print()
    filing: Filing = filings.get("0001721868-22-000010")

    assert filing.cik == 884380
    assert filing.accession_no == "0001721868-22-000010"

    # Invalid accession number
    assert filings.get("0001721868-22") is None

    filing_one_hundred = filings.get(100)
    filing_100 = filings.get("100")
    assert filing_100.accession_no == filing_one_hundred.accession_no

def test_find_company_in_filings():
    # TODO: Looks like the search results ordering is broken for some reason
    filings = cached_filings(2022, 1)
    oracle_filings: Filings = filings.find('Oracle')
    assert len(oracle_filings) > 0

    tesla_filings: Filings = filings.find('TSLA')
    assert len(tesla_filings) > 0

    filings = filings.find('Anheuser-Busch')
    print(filings)
    assert set(filings.data['cik'].to_pylist()) == {1668717}


def test_filing_sections():
    sections = carbo_10K.sections()
    assert len(sections) > 20


def test_filing_with_complex_sections():
    filing = Filing(form='8-K', filing_date='2023-03-15', company='ADOBE INC.', cik=796343,
                    accession_no='0000796343-23-000044')

    sections = filing.sections()
    for section in sections:
        if "Item 2.0.2" in section:
            assert "Financial Condition. On March 15, 2023," in section


def test_search_for_text_in_filing_with_bm25():
    print()
    results = carbo_10K.search("risks")
    assert len(results) > 10
    print(results)


def test_search_for_text_with_regex():
    print()

    filing = Filing(company="NORDSTROM INC", cik=72333, form="8-K",
                    filing_date="2023-03-06", accession_no="0000072333-23-000015")
    results = filing.search(r"Item\s5.02", regex=True)
    assert len(results) > 0
    print(results)

    filing = Filing(company="BLACKROCK INC", cik=1364742, form="8-K",
                    filing_date="2023-02-24", accession_no="0001193125-23-048785")
    results = filing.search(r"Item\s5.02", regex=True)
    assert len(results) > 0
    print(results)


def test_get_by_accession_number():
    filing = get_by_accession_number("0000072333-23-000015")
    assert filing.company == "NORDSTROM INC"
    assert filing.cik == 72333
    assert filing.form == "8-K"
    assert filing.filing_date == datetime.date(2023, 3, 6)
    assert filing.accession_no == "0000072333-23-000015"

    # filings from the 90's
    assert get_by_accession_number("0000320193-96-000018")

    # Not found
    assert get_by_accession_number("9990072333-45-000015") is None
    assert get_by_accession_number("9990072333-22-000015") is None

def test_get_by_accession_number_show_progress_false():
    filing = get_by_accession_number("0000072333-23-000015", show_progress=False)
    assert filing.company == "NORDSTROM INC"
    assert filing.cik == 72333
    assert filing.form == "8-K"


def test_find_old_filing():
    filing = get_by_accession_number("0000320193-96-000018")
    assert filing


def test_get_current_filing_by_accession_number():
    current_filings = get_current_filings()
    print()
    print(current_filings)
    filing = current_filings[0]
    # Now find the filing
    filing = get_by_accession_number(filing.accession_no)
    assert filing
    assert filing.accession_no == current_filings[0].accession_no

    # Now find a filing that is on the next page
    current_filings = current_filings.next()
    filing_on_next_page = current_filings[40]
    print(filing_on_next_page)



def test_as_company_filing():
    company_filing = carbo_10K.as_company_filing()
    assert company_filing.cik == carbo_10K.cik


def test_10K_filing_with_no_financial_data():
    filing = Filing(form='10-K', filing_date='2023-05-26', company='CarMax Auto Owner Trust 2019-3', cik=1779026,
                    accession_no='0001779026-23-000027')
    tenk: TenK = filing.obj()
    assert not tenk.financials
    assert not tenk.balance_sheet
    assert not tenk.income_statement
    assert not tenk.cash_flow_statement
    print(tenk)


def test_text_url_for_filing():
    assert carbo_10K.text_url \
           == 'https://www.sec.gov/Archives/edgar/data/1009672/000156459018004771/0001564590-18-004771.txt'


def test_get_current_filings():
    filings = get_current_filings()
    print()
    print(filings)
    assert not filings.empty

    filing = filings[0]
    print(str(filing))


def test_get_current_filings_by_form():
    filings = get_current_filings(form="3")
    print()
    print(filings)
    assert not filings.empty


def test_filings_get_by_invalid_accession_number(capsys):
    assert cached_filings(2022, 1).get('INVALID-ACCESS-NUMBER') is None


def test_filing_to_dict():
    filing = Filing(form='8-K', filing_date='2024-03-08', company='3M CO', cik=66740,
                    accession_no='0000066740-24-000023')
    filing_dict = filing.to_dict()
    assert filing_dict['form'] == '8-K'
    assert filing_dict['filing_date'] == '2024-03-08'
    assert filing_dict['company'] == '3M CO'
    assert filing_dict['cik'] == 66740
    assert filing_dict['accession_number'] == '0000066740-24-000023'

    filing = Filing.from_dict(filing_dict)
    assert filing.form == '8-K'
    assert filing.filing_date == '2024-03-08'
    assert filing.company == '3M CO'
    assert filing.cik == 66740
    assert filing.accession_number == '0000066740-24-000023'


def test_save_filing_to_file():
    filing = Filing(form='8-K', filing_date='2024-03-08', company='3M CO', cik=66740,
                    accession_no='0000066740-24-000023')
    filing_path = tempfile.NamedTemporaryFile()
    print(filing_path.name)
    assert Path(filing_path.name).is_file()
    filing.save(Path(filing_path.name))
    # Now load it
    filing = Filing.load(Path(filing_path.name))
    assert filing.filing_date == '2024-03-08'


def test_save_filing_to_directory():
    filing = Filing(form='8-K', filing_date='2024-03-08', company='3M CO', cik=66740,
                    accession_no='0000066740-24-000023')

    directory = tempfile.TemporaryDirectory()
    filing_dir = Path(directory.name)
    print(filing_dir)
    filing.save(filing_dir)
    # Now load the filing
    filing_path = filing_dir / f"{filing.accession_no}.pkl"
    assert filing_path.exists()
    filing = Filing.load(filing_path)
    assert filing.filing_date == '2024-03-08'


def test_filing_date_to_year_quarter():
    # Test case 1: Single date
    assert filing_date_to_year_quarters("2024-03-01") == [(2024, 1)]
    assert filing_date_to_year_quarters("2024-04-10") == [(2024, 2)]

    # Test case 2: Date range within the same year
    assert filing_date_to_year_quarters("2024-01-01:2024-04-14") == [(2024, 1), (2024, 2)]
    assert filing_date_to_year_quarters("2024-01-01:2024-12-31") == [(2024, 1), (2024, 2), (2024, 3), (2024, 4)]

    # Test case 3: Date range across multiple years
    assert filing_date_to_year_quarters("2022-04-02:2023-01-23") == [(2022, 2), (2022, 3), (2022, 4), (2023, 1)]
    assert filing_date_to_year_quarters("2022-01-01:2024-04-14") == [
        (2022, 1), (2022, 2), (2022, 3), (2022, 4),
        (2023, 1), (2023, 2), (2023, 3), (2023, 4),
        (2024, 1), (2024, 2)
    ]

    # Test case 4: Open-ended date range (start date only)
    current_year = date.today().year
    current_quarter = (date.today().month - 1) // 3 + 1
    assert filing_date_to_year_quarters("2022-01-01:") == [
        (year, quarter)
        for year in range(2022, current_year + 1)
        for quarter in (range(1, 5) if year < current_year else range(1, current_quarter + 1))
    ]

    # Test case 5: Open-ended date range (end date only)
    assert filing_date_to_year_quarters(":2022-01-01") == [
        (year, quarter)
        for year in range(1994, 2023)
        for quarter in (range(2, 5) if year == 1994 else range(1, 2) if year == 2022 else range(1, 5))
    ]


def test_get_filings_by_filing_date():
    filings = get_filings(filing_date='2023-02-01')
    assert filings.date_range == (datetime.date(2023, 2, 1), datetime.date(2023, 2, 1))

    filings = get_filings(filing_date='2023-02-01:2023-02-28')
    assert filings.date_range == (datetime.date(2023, 2, 1), datetime.date(2023, 2, 28))

    filings = get_filings(filing_date='2023-02-01:2024-01-02')
    assert filings.date_range == (datetime.date(2023, 2, 1), datetime.date(2024, 1, 2))

    # Ignore the year if filing date os present
    filings = get_filings(filing_date='2023-02-01', year=2020)
    assert filings.date_range == (datetime.date(2023, 2, 1), datetime.date(2023, 2, 1))

    # Invalid filing date
    assert get_filings(filing_date='2023-02-01:2024-01-02:2025-01-02') is None
    assert get_filings(filing_date="01-02-2023") is None


def test_get_text_from_old_filing():
    filing = Filing(form='10-Q', filing_date='2000-05-11', company='APPLE COMPUTER INC', cik=320193,
                    accession_no='0000912057-00-023442')
    assert filing.document.empty
    html = filing.html()
    assert html is None
    text = filing.text()
    assert text


def test_filings_to_dict():
    filings: Filings = get_filings(filing_date='2023-02-01')
    filings_json = filings.to_dict()
    assert len(filings_json) == 1000
    assert len(filings.to_dict(50)) == 50
    assert len(filings.head(10).to_dict()) == 10


def test_company_filing_to_dict():
    company = Company(320193)
    filing = company.get_filings(form="4").latest(1)
    filing_dict = filing.to_dict()
    assert filing_dict['form'] == '4'
    assert filing_dict['company'] == 'Apple Inc.'
    assert filing_dict['cik'] == 320193


def test_filter_by_ticker(filings_2022_q3):
    tesla_filings = filings_2022_q3.filter(ticker="TSLA")
    assert len(tesla_filings) > 0
    assert set(tesla_filings.data['company'].to_pylist()) == {'Tesla, Inc.'}

    # Test with multiple tickers
    tesla_and_apple_filings = filings_2022_q3.filter(ticker=["TSLA", "AAPL"])
    assert len(tesla_and_apple_filings) > 0
    assert set(tesla_and_apple_filings.data['company'].to_pylist()) == {'Tesla, Inc.', 'Apple Inc.'}

    # Tesla 8-K
    tesla_8k = filings_2022_q3.filter(ticker="TSLA", form="8-K")
    assert len(tesla_8k) > 0
    assert set(tesla_8k.data['form'].to_pylist()) == {'8-K'}

def test_filter_by_amendments(filings_2022_q3):
    filings = filings_2022_q3.filter(form=["10-K", "20-F", "40-F"])
    filings_no_amendments = filings.filter(amendments=False)
    forms = set(filings_no_amendments.data['form'].to_pylist())
    assert forms == {"10-K", "20-F", "40-F"}




@pytest.fixture
def mock_filings():
    return {
        "0000000123-22-000456": MagicMock(
            accession_number="0000000123-22-000456",
            form="10-K",
            company="Test Corp"
        )
    }


@pytest.fixture
def mock_cached_filings():
    def _get_cached_filings(year, quarter):
        if year == 2022 and quarter == 2:
            return {
                "0000000123-22-000456": MagicMock(
                    accession_number="0000000123-22-000456",
                    form="10-K",
                    company="Test Corp"
                )
            }
        return {}

    return _get_cached_filings


def test_get_filing_by_accession_found(mock_cached_filings):
    with patch('edgar._filings._get_cached_filings', mock_cached_filings):
        # First call - should hit the mock and cache
        result1 = get_filing_by_accession("0000000123-22-000456", 2022)
        assert result1.accession_number == "0000000123-22-000456"
        assert result1.form == "10-K"

        # Second call - should use cached value
        result2 = get_filing_by_accession("0000000123-22-000456", 2022)
        assert result2.accession_number == "0000000123-22-000456"

        # Verify it's the same cached object
        assert result1 is result2


def test_get_filing_by_accession_not_found(mock_cached_filings):
    with patch('edgar._filings._get_cached_filings', mock_cached_filings):
        # Non-existent filing
        result = get_filing_by_accession("0000000999-22-000999", 2022)
        assert result is None

        # Verify the None result wasn't cached by calling again
        cache_info = get_filing_by_accession.cache_info()
        assert cache_info.hits == 0  # Should be no cache hits


def test_get_filing_by_accession_invalid_format():
    with pytest.raises(AssertionError):
        get_filing_by_accession("invalid-format", 2022)


@pytest.mark.parametrize("accession_number,expected_year", [
    ("0000000123-98-000456", 1998),  # 1900s
    ("0000000123-22-000456", 2022),  # 2000s
    ("0000000123-00-000456", 2000),  # Edge case - year 2000
    ("0000000123-99-000456", 1999),  # Edge case - year 1999
])
def test_year_extraction_parametrized(accession_number, expected_year):
    year = int("19" + accession_number[11:13]) if accession_number[11] == '9' else int("20" + accession_number[11:13])
    assert year == expected_year

def test_get_filings_by_range():
    filings = get_filings(year=range(2022, 2024))
    assert not filings.empty
    assert len(filings) > 1000
    assert filings.date_range == (datetime.date(2022, 1, 3), datetime.date(2023, 12, 29))



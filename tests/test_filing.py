import datetime
import re
from functools import lru_cache
from pathlib import Path

import httpx
import humanize
import pandas as pd
import pytest
from typing import List

from edgar import get_filings, Filings, Filing, get_company, get_by_accession_number
from edgar.core import default_page_size
from edgar._filings import FilingHomepage, SECHeader, read_fixed_width_index, form_specs, company_specs, Attachments, \
    Attachment, Filer, get_current_filings

from edgar.forms import TenK
from rich import print

pd.options.display.max_colwidth = 200


def test_read_fixed_width_index():
    index_text = Path('data/form.20200318.idx').read_text()
    index_data = read_fixed_width_index(index_text, form_specs)
    index_df = index_data.to_pandas()
    invalid_accession = index_df.query("~accession_number.str.match(r'[0-9]{10}\\-[0-9]{2}\\-[0-9]{6}')")
    assert len(invalid_accession) == 0


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
    assert filings.data[0][0].as_py() == '1-A'


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


def test_read_form_filing_index_xbrl():
    filings: Filings = get_filings(2021, 1, index="xbrl")
    assert filings.data
    assert 40000 > len(filings) > 10000

    df = filings.to_pandas()
    assert len(df) == len(filings) == len(filings.data)
    assert filings.data.column_names == ['cik', 'company', 'form', 'filing_date', 'accession_number']
    print('Bytes', humanize.naturalsize(filings.data.nbytes, binary=True))
    assert re.match(r'\d{10}\-\d{2}\-\d{6}', filings.data[4][-1].as_py())


def test_get_filings_gets_correct_accession_number():
    # Get the filings and test that the accession number is correct for all rows e.g. 0001185185-20-000088
    filings: Filings = cached_filings(2021, 1)
    data = filings.data.to_pandas()
    misparsed_accessions = data.query("accession_number.str.endswith('.')")
    assert len(misparsed_accessions) == 0


@lru_cache(maxsize=8)
def cached_filings(year: int, quarter: int, index: str = "form"):
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
    print()
    print(filings_repr)


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


def test_filing_sample():
    filings: Filings = cached_filings(2021, 1, index="xbrl")
    sample_filings = filings.sample(10)
    assert len(sample_filings) == 10
    print(sample_filings)

    # Try sampling equal to number of filings
    assert len(filings.sample(5).sample(5)) == 5


def test_filter_filings_by_form():
    filings: Filings = cached_filings(2021, 1, index="xbrl")
    forms = list(set(filings.data['form'].to_pylist()))
    assert len(forms) > 25

    tenk_filings = filings.filter(form="10-Q")
    assert list(set(tenk_filings.data['form'].to_pylist())) == ["10-Q"]

    tenk_filings = filings.filter(form="10-Q", amendments=True)
    assert set(tenk_filings.data['form'].to_pylist()) == {"10-Q", '10-Q/A'}


def test_filter_filings_by_date():
    filings: Filings = cached_filings(2021, 1, index="xbrl")
    filtered_filings = filings.filter(filing_date='2021-03-04')
    assert len(set(filtered_filings.data['filing_date'].to_pylist())) == 1
    assert not filtered_filings.empty
    assert len(filtered_filings) < len(filings)

    # filter by form and date
    filings_by_date_and_form = filings.filter(form=['10-Q'], filing_date='2021-03-04')
    assert list(set(filings_by_date_and_form.data['form'].to_pylist())) == ['10-Q']
    assert len(set(filings_by_date_and_form.data['filing_date'].to_pylist())) == 1


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


carbo_10K = Filing(form='10-K', company='CARBO CERAMICS INC', cik=1009672, filing_date='2018-03-08',
                   accession_no='0001564590-18-004771')

four37_capital_staff_filing = Filing(form='SEC STAFF ACTION', company='437 CAPITAL Fund Corp', cik=1805559,
                                     filing_date='2022-03-24', accession_no='9999999997-22-001189')


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
    company = get_company(1805559)
    filings = company.get_filings()
    print(filings.to_pandas("form", "filing_date", "primaryDocument"))
    filing = filings[0]
    assert filing


def test_filing_homepage_for_filing():
    filing_homepage: FilingHomepage = carbo_10K.homepage
    assert 'Description'
    assert filing_homepage.url == carbo_10K.url

def test_filing_homepage_for_filing_multiple_instruments():
    filing = Filing(form='DEF 14A', filing_date='2023-06-16', company='T. Rowe Price All-Cap Opportunities Fund, Inc.',
                    cik=773485, accession_no='0001741773-23-002051')
    homepage:FilingHomepage = filing.homepage
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
    filing_homepage = FilingHomepage.from_html(homepage_html, url=filing.homepage_url, filing=filing)
    print()

    assert len(filing_homepage.filer_infos) >60
    filer_info = filing_homepage.filer_infos[0]
    assert filer_info.company_name == "T. Rowe Price Small-Cap Stock Fund, Inc. (Filer) CIK: 0000075170"
    assert "100 EAST PRATT STRET" in filer_info.addresses[0]
    print(filing_homepage)


def test_get_filer_info_from_homepage():
    # This is a form 4 filing so there is an Issuer "LiveRamp Holdings" and a Reporter "Scott E Rowe"
    filing = Filing(form='4', filing_date='2023-08-23', company='Howe Scott E', cik=1369558,
                    accession_no='0001903601-23-000091')
    print()
    print(filing.homepage)
    print(filing.homepage.filer_infos)



def test_get_matching_files():
    document_files = carbo_10K.homepage.get_matching_files("table=='Document Format Files'")
    assert len(document_files) >= 12

    data_files = carbo_10K.homepage.get_matching_files("table=='Data Files'")
    assert len(data_files) >= 6


def test_filing_document():
    assert carbo_10K.homepage.primary_html_document.url == \
           'https://www.sec.gov/Archives/edgar/data/1009672/000156459018004771/crr-10k_20171231.htm'


def test_xbrl_document():
    xbrl_document = carbo_10K.homepage.xbrl_document
    assert xbrl_document.url == \
           'https://www.sec.gov/Archives/edgar/data/1009672/000156459018004771/crr-20171231.xml'


def test_filing_homepage_get_file():
    filing_document = carbo_10K.homepage.get_file(seq=1)
    assert filing_document
    assert filing_document.seq == '1'
    assert filing_document.path == '/Archives/edgar/data/1009672/000156459018004771/crr-10k_20171231.htm'
    assert filing_document.url == 'https://www.sec.gov/Archives/edgar/data' + \
           '/1009672/000156459018004771/crr-10k_20171231.htm'
    assert filing_document.name == 'crr-10k_20171231.htm'


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
    assert primary_document.seq == '1'


barclays_filing = Filing(form='ATS-N/MA', company='BARCLAYS CAPITAL INC.', cik=851376, filing_date='2020-02-21',
                         accession_no='0000851376-20-000003')


def test_filing_primary_document_seq_5():
    primary_document: Attachment = barclays_filing.document
    assert primary_document
    assert primary_document.url == \
           'https://www.sec.gov/Archives/edgar/data/851376/000085137620000003/xslATSN_COVER_X01/coverpage.xml'
    assert primary_document.extension == '.xml'
    assert primary_document.seq == '5'


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


def test_filing_html_for_ixbrl_filing():
    filing = Filing(form='10-Q', company='1 800 FLOWERS COM INC',
                    cik=1084869, filing_date='2023-02-10',
                    accession_no='0001437749-23-002992')
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
    text = filing.text()
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


def test_filing_homepage_get_minimum_seq():
    filing = Filing(form='4', company='Orion Engineered Carbons S.A.',
                    cik=1609804, filing_date='2022-11-04',
                    accession_no='0000950142-22-003095')
    min_seq = filing.homepage.min_seq()
    assert min_seq == '1'
    print(min_seq)


def test_filing_homepage_primary_documents():
    filing = Filing(form='4', company='Orion Engineered Carbons S.A.',
                    cik=1609804, filing_date='2022-11-04',
                    accession_no='0000950142-22-003095')
    print()
    primary_documents: List[Attachment] = filing.homepage.primary_documents
    assert len(primary_documents) == 2

    primary_html = primary_documents[0]
    assert primary_html.seq == '1'
    assert primary_html.document == 'es220296680_4-davis.html'  # Displayed as html
    assert primary_html.description == 'OWNERSHIP DOCUMENT'
    assert primary_html.path.endswith('xslF345X03/es220296680_4-davis.xml')
    assert primary_html.display_extension == '.html'

    primary_xml = primary_documents[1]
    assert primary_xml.seq == '1'
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


def test_filter_invalid_date():
    filings = cached_filings(2022, 3)
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
    assert not filings.empty

    filings = get_filings(form="8-K")
    assert not filings.empty
    print()
    print(filings)


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


def test_find_company():
    # TODO: Looks like the search results ordering is broken for some reason
    filings = cached_filings(2022, 1)
    company_search_filings: Filings = filings.find('Tailwind')
    print()
    print(company_search_filings)
    companies = company_search_filings.data['company'].to_pylist()
    # Temporarily disabled until we can fix the search results ordering
    # assert 'Tailwind International Acquisition Corp.' in companies
    # print(filings.find('SCHWEITZER'))


def test_filing_sections():
    sections = carbo_10K.sections()
    assert len(sections) > 20
    print(sections[10])


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


def test_get_by_acession_number():
    filing = get_by_accession_number("0000072333-23-000015")
    assert filing.company == "NORDSTROM INC"
    assert filing.cik == 72333
    assert filing.form == "8-K"
    assert filing.filing_date == datetime.date(2023, 3, 6)
    assert filing.accession_no == "0000072333-23-000015"

    assert get_by_accession_number("9990072333-45-000015") is None
    assert get_by_accession_number("9990072333-22-000015") is None


def test_attachments():
    filing = Filing(company="BLACKROCK INC", cik=1364742, form="8-K",
                    filing_date="2023-02-24", accession_no="0001193125-23-048785")
    attachments = Attachments(filing.homepage._files)
    assert len(attachments) == len(filing.homepage._files)

    print(attachments)
    attachment = attachments[2]
    assert attachment
    assert attachment.name == 'blk25-20230224.xsd'
    assert attachment.url == 'https://www.sec.gov/Archives/edgar/data/1364742/000119312523048785/blk25-20230224.xsd'

    text = attachment.download()
    assert text
    assert "<?xml version=" in text

    # Test the filing homepage attachments
    assert filing.homepage.attachments
    assert len(filing.homepage.attachments) == 7

    # Test the filing attachments
    assert filing.attachments
    assert len(filing.attachments) == 7
    assert filing.attachments[4].description == "XBRL TAXONOMY EXTENSION LABEL LINKBASE"

    # Get the filing using the document name
    assert filing.attachments["blk25-20230224.xsd"].description == "XBRL TAXONOMY EXTENSION SCHEMA"
    assert filing.attachments.get("blk25-20230224.xsd").description == "XBRL TAXONOMY EXTENSION SCHEMA"


def test_download_filing_attachment():
    filing = Filing(form='10-K', filing_date='2023-06-02', company='Cyber App Solutions Corp.', cik=1851048,
                    accession_no='0001477932-23-004175')
    attachments = filing.attachments
    print(attachments)

    # Get a text/htm attachment
    attachment = attachments[0]
    assert attachment.name == "cyber_10k.htm"
    text = attachment.download()
    assert isinstance(text, str)

    # Get a jpg attachment
    attachment = attachments[3]
    assert attachment.name == "cyber_10kimg1.jpg"
    b = attachment.download()
    assert isinstance(b, bytes)


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


def test_filing_sec_header():
    sec_header: SECHeader = carbo_10K.header
    print()
    print(sec_header)
    assert len(sec_header.filers) == 1
    filer = sec_header.filers[0]
    assert filer
    assert filer.company_information.name == 'CARBO CERAMICS INC'
    assert filer.company_information.cik == '0001009672'
    assert filer.company_information.irs_number == '721100013'
    assert filer.company_information.state_of_incorporation == 'DE'
    assert filer.company_information.fiscal_year_end == '1231'
    assert filer.company_information.sic == 'ABRASIVE ASBESTOS & MISC NONMETALLIC MINERAL PRODUCTS [3290]'

    assert filer.filing_information.form == '10-K'
    assert filer.filing_information.file_number == '001-15903'
    assert filer.filing_information.film_number == '18674418'
    assert filer.filing_information.sec_act == '1934 Act'

    assert filer.business_address.street1 == '575 NORTH DAIRY ASHFORD'
    assert filer.business_address.street2 == 'SUITE 300'
    assert filer.business_address.city == 'HOUSTON'
    assert filer.business_address.state_or_country == 'TX'
    assert filer.business_address.zipcode == '77079'


def test_parse_sec_header_with_filer():

    header_content = Path('data/secheader.424B5.abeona.txt').read_text()
    sec_header = SECHeader.parse(header_content)
    print()
    print(sec_header)
    # Metadata
    assert sec_header.filing_metadata
    assert sec_header.filing_metadata['FILED AS OF DATE'] =='20230607'
    assert sec_header.filing_date == '20230607'
    assert sec_header.accession_number == '0001493152-23-020412'
    assert sec_header.acceptance_datetime == datetime.datetime(2023, 6, 7, 16, 10, 23)

    # FILERS
    assert sec_header.filers
    filer = sec_header.filers[0]

    # Company Information
    assert filer.company_information.name == 'ABEONA THERAPEUTICS INC.'
    assert filer.company_information.cik == '0000318306'
    assert filer.company_information.irs_number == '830221517'
    assert filer.company_information.state_of_incorporation == 'DE'
    assert filer.company_information.fiscal_year_end == '1231'
    assert filer.company_information.sic == 'PHARMACEUTICAL PREPARATIONS [2834]'

    # Business Address
    assert filer.business_address.street1 == '6555 CARNEGIE AVE, 4TH FLOOR'
    assert filer.business_address.city == 'CLEVELAND'
    assert filer.business_address.state_or_country == 'OH'
    assert filer.business_address.zipcode == '44103'

    # Mailing Address
    assert filer.mailing_address.street1 == '6555 CARNEGIE AVE, 4TH FLOOR'
    assert filer.mailing_address.city == 'CLEVELAND'
    assert filer.mailing_address.state_or_country == 'OH'
    assert filer.mailing_address.zipcode == '44103'

    assert len(filer.former_company_names) == 3
    assert filer.former_company_names[0].name == 'PLASMATECH BIOPHARMACEUTICALS INC'

    assert not sec_header.reporting_owners
    assert not sec_header.issuers


    # Goldman Sachs
    # This Goldman Sachs filing has an extra : in the Street2 field
    # 		STREET 2:		ATT: PRIVATE CREDIT GROUP
    header_content = Path('data/secheader.N2A.goldman.txt').read_text()
    print(header_content)
    sec_header = SECHeader.parse(header_content)
    assert sec_header.filers[0].business_address.street1 == '200 WEST STREET'
    assert sec_header.filers[0].business_address.street2 == 'ATT: PRIVATE CREDIT GROUP'




def test_parse_sec_header_with_reporting_owner():
    header_content = Path('data/secheader.4.evercommerce.txt').read_text()
    print(header_content)
    sec_header = SECHeader.parse(header_content)
    print(sec_header)

    assert sec_header.filers == []
    reporting_owner = sec_header.reporting_owners[0]
    assert reporting_owner
    assert reporting_owner.owner.name == 'Driggers Shane'
    assert reporting_owner.owner.cik == '0001927858'
    assert reporting_owner.filing_information.form == '4'
    assert reporting_owner.filing_information.file_number == '001-40575'
    assert reporting_owner.filing_information.film_number == '23997535'

    assert sec_header.issuers
    issuer = sec_header.issuers[0]
    assert issuer.company_information.name == 'EverCommerce Inc.'
    assert issuer.company_information.cik == '0001853145'
    assert issuer.company_information.sic == 'SERVICES-PREPACKAGED SOFTWARE [7372]'
    assert issuer.company_information.irs_number == '814063428'
    assert issuer.company_information.state_of_incorporation == 'DE'

    assert issuer.business_address.street1 == '3601 WALNUT STREET'
    assert issuer.business_address.street2 == 'SUITE 400'
    assert issuer.business_address.city == 'DENVER'
    assert issuer.business_address.state_or_country == 'CO'
    assert issuer.business_address.zipcode == '80205'

def test_parse_header_with_subject_company():

    sec_header = SECHeader.parse("""
<ACCEPTANCE-DATETIME>20230612150550
ACCESSION NUMBER:		0001971857-23-000246
CONFORMED SUBMISSION TYPE:	144
PUBLIC DOCUMENT COUNT:		1
FILED AS OF DATE:		20230612
DATE AS OF CHANGE:		20230612

SUBJECT COMPANY:	

	COMPANY DATA:	
		COMPANY CONFORMED NAME:			CONSUMERS ENERGY CO
		CENTRAL INDEX KEY:			0000201533
		STANDARD INDUSTRIAL CLASSIFICATION:	ELECTRIC & OTHER SERVICES COMBINED [4931]
		IRS NUMBER:				380442310
		STATE OF INCORPORATION:			MI
		FISCAL YEAR END:			1231

	FILING VALUES:
		FORM TYPE:		144
		SEC ACT:		1933 Act
		SEC FILE NUMBER:	001-05611
		FILM NUMBER:		231007818

	BUSINESS ADDRESS:	
		STREET 1:		ONE ENERGY PLAZA
		CITY:			JACKSON
		STATE:			MI
		ZIP:			49201
		BUSINESS PHONE:		5177880550

	MAIL ADDRESS:	
		STREET 1:		ONE ENERGY PLAZA
		CITY:			JACKSON
		STATE:			MI
		ZIP:			49201

	FORMER COMPANY:	
		FORMER CONFORMED NAME:	CONSUMERS POWER CO
		DATE OF NAME CHANGE:	19920703

REPORTING-OWNER:	

	COMPANY DATA:	
		COMPANY CONFORMED NAME:			Hendrian Catherine A
		CENTRAL INDEX KEY:			0001701746

	FILING VALUES:
		FORM TYPE:		144

	MAIL ADDRESS:	
		STREET 1:		ONE ENERGY PLAZA
		CITY:			JACKSON
		STATE:			MI
		ZIP:			49201
		""")
    print(sec_header)
    assert sec_header.subject_companies
    subject_company = sec_header.subject_companies[0]
    assert subject_company.company_information.name == 'CONSUMERS ENERGY CO'
    assert subject_company.company_information.cik == '0000201533'
    assert subject_company.company_information.sic == 'ELECTRIC & OTHER SERVICES COMBINED [4931]'
    assert subject_company.company_information.irs_number == '380442310'
    assert subject_company.company_information.state_of_incorporation == 'MI'
    assert subject_company.company_information.fiscal_year_end == '1231'

    assert subject_company.business_address.street1 == 'ONE ENERGY PLAZA'
    assert subject_company.business_address.city == 'JACKSON'
    assert subject_company.business_address.state_or_country == 'MI'
    assert subject_company.business_address.zipcode == '49201'

    assert subject_company.mailing_address.street1 == 'ONE ENERGY PLAZA'
    assert subject_company.mailing_address.city == 'JACKSON'
    assert subject_company.mailing_address.state_or_country == 'MI'
    assert subject_company.mailing_address.zipcode == '49201'

    # Reporting owner
    assert sec_header.reporting_owners
    reporting_owner = sec_header.reporting_owners[0]
    assert reporting_owner.company_information.name == 'Hendrian Catherine A'
    assert reporting_owner.company_information.cik == '0001701746'


    assert len(subject_company.former_company_names) == 1


def test_parse_header_filing_with_multiple_filers():
    """
    filing = Filing(form='10-D', filing_date='2023-06-09', company='FIRST NATIONAL FUNDING LLC', cik=1171040,
                    accession_no='0001104659-23-069855')
                        :return:
    """
    sec_header=SECHeader.parse(
"""<ACCEPTANCE-DATETIME>20230609145616
ACCESSION NUMBER:		0001104659-23-069855
CONFORMED SUBMISSION TYPE:	10-D
PUBLIC DOCUMENT COUNT:		2
CONFORMED PERIOD OF REPORT:	20230531
<DEPOSITOR-CIK>0001171040
<SPONSOR-CIK>0000036644
FILED AS OF DATE:		20230609
DATE AS OF CHANGE:		20230609
ABS ASSET CLASS:             	Credit card

FILER:

	COMPANY DATA:	
		COMPANY CONFORMED NAME:			First National Master Note Trust
		CENTRAL INDEX KEY:			0001396730
		STANDARD INDUSTRIAL CLASSIFICATION:	ASSET-BACKED SECURITIES [6189]
		IRS NUMBER:				000000000
		STATE OF INCORPORATION:			DE
		FISCAL YEAR END:			1231

	FILING VALUES:
		FORM TYPE:		10-D
		SEC ACT:		1934 Act
		SEC FILE NUMBER:	333-140273-01
		FILM NUMBER:		231004915

	BUSINESS ADDRESS:	
		STREET 1:		1620 DODGE STREET STOP CODE 3395
		CITY:			OMAHA
		STATE:			NE
		ZIP:			68197
		BUSINESS PHONE:		402-341-0500

	MAIL ADDRESS:	
		STREET 1:		1620 DODGE STREET STOP CODE 3395
		CITY:			OMAHA
		STATE:			NE
		ZIP:			68197

FILER:

	COMPANY DATA:	
		COMPANY CONFORMED NAME:			FIRST NATIONAL FUNDING LLC
		CENTRAL INDEX KEY:			0001171040
		STANDARD INDUSTRIAL CLASSIFICATION:	ASSET-BACKED SECURITIES [6189]
		IRS NUMBER:				000000000
		STATE OF INCORPORATION:			NE

	FILING VALUES:
		FORM TYPE:		10-D
		SEC ACT:		1934 Act
		SEC FILE NUMBER:	000-50139
		FILM NUMBER:		231004916

	MAIL ADDRESS:	
		STREET 1:		1620 DODGE STREET
		CITY:			OHAHA
		STATE:			NE
		ZIP:			68102
    """)
    print(sec_header)
    assert len(sec_header.filers) == 2

    filer0 = sec_header.filers[0]
    assert filer0.company_information.name == 'First National Master Note Trust'
    assert filer0.company_information.cik == '0001396730'
    assert filer0.company_information.irs_number == '000000000'
    assert filer0.company_information.state_of_incorporation == 'DE'
    assert filer0.filing_information.form == '10-D'
    assert filer0.filing_information.sec_act == '1934 Act'
    assert filer0.filing_information.file_number == '333-140273-01'
    assert filer0.filing_information.film_number == '231004915'
    assert filer0.business_address.street1 == '1620 DODGE STREET STOP CODE 3395'
    assert filer0.business_address.city == 'OMAHA'
    assert filer0.business_address.state_or_country == 'NE'
    assert filer0.business_address.zipcode == '68197'
    assert filer0.mailing_address.street1 == '1620 DODGE STREET STOP CODE 3395'
    assert filer0.mailing_address.city == 'OMAHA'
    assert filer0.mailing_address.state_or_country == 'NE'
    assert filer0.mailing_address.zipcode == '68197'



    filer1 = sec_header.filers[1]
    assert filer1.company_information.name == 'FIRST NATIONAL FUNDING LLC'
    assert filer1.company_information.cik == '0001171040'
    assert filer1.company_information.irs_number == '000000000'
    assert filer1.company_information.state_of_incorporation == 'NE'
    assert filer1.filing_information.form == '10-D'
    assert filer1.filing_information.sec_act == '1934 Act'
    assert filer1.filing_information.file_number == '000-50139'
    assert filer1.filing_information.film_number == '231004916'
    assert not filer1.business_address


def test_parse_header_filing_with_multiple_former_companies():
    sec_header = SECHeader.parse(
    """
<ACCEPTANCE-DATETIME>20230609124624
ACCESSION NUMBER:		0001472375-23-000090
CONFORMED SUBMISSION TYPE:	10-K
PUBLIC DOCUMENT COUNT:		54
CONFORMED PERIOD OF REPORT:	20230331
FILED AS OF DATE:		20230609
DATE AS OF CHANGE:		20230609

FILER:

	COMPANY DATA:	
		COMPANY CONFORMED NAME:			REGENEREX PHARMA, INC.
		CENTRAL INDEX KEY:			0001357878
		STANDARD INDUSTRIAL CLASSIFICATION:	PHARMACEUTICAL PREPARATIONS [2834]
		IRS NUMBER:				980479983
		STATE OF INCORPORATION:			NV
		FISCAL YEAR END:			0331

	FILING VALUES:
		FORM TYPE:		10-K
		SEC ACT:		1934 Act
		SEC FILE NUMBER:	000-53230
		FILM NUMBER:		231004569

	BUSINESS ADDRESS:	
		STREET 1:		5348 VEGAS DRIVE, SUITE 177
		CITY:			LAS VEGAS
		STATE:			NV
		ZIP:			89108
		BUSINESS PHONE:		305-927-5191

	MAIL ADDRESS:	
		STREET 1:		5348 VEGAS DRIVE, SUITE 177
		CITY:			LAS VEGAS
		STATE:			NV
		ZIP:			89108

	FORMER COMPANY:	
		FORMER CONFORMED NAME:	PEPTIDE TECHNOLOGIES, INC.
		DATE OF NAME CHANGE:	20180309

	FORMER COMPANY:	
		FORMER CONFORMED NAME:	Eternelle Skincare Products Inc.
		DATE OF NAME CHANGE:	20170621

	FORMER COMPANY:	
		FORMER CONFORMED NAME:	PEPTIDE TECHNOLOGIES, INC.
		DATE OF NAME CHANGE:	20111007        
    """)
    print(sec_header)
    assert len(sec_header.filers) == 1
    filer:Filer = sec_header.filers[0]
    assert len(filer.former_company_names) == 3
    assert filer.former_company_names[0].name == 'PEPTIDE TECHNOLOGIES, INC.'
    assert filer.former_company_names[1].name == 'Eternelle Skincare Products Inc.'
    assert filer.former_company_names[2].name == 'PEPTIDE TECHNOLOGIES, INC.'
    assert filer.former_company_names[0].date_of_change == '20180309'
    assert filer.former_company_names[1].date_of_change == '20170621'
    assert filer.former_company_names[2].date_of_change == '20111007'

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
import re
from functools import lru_cache
from pathlib import Path

import httpx
import humanize
import pandas as pd
import pytest
from typing import List

from edgar import get_filings, Filings, Filing, get_company
from edgar.core import default_page_size
from edgar.filing import FilingHomepage, FilingDocument, read_fixed_width_index, form_specs, company_specs
from rich import print

pd.options.display.max_colwidth = 200


def test_read_fixed_width_index():
    index_text = Path('data/form.20200318.idx').read_text()
    index_data = read_fixed_width_index(index_text, form_specs)
    index_df = index_data.to_pandas()
    invalid_accession = index_df.query("~accession_number.str.match('[0-9]{10}\\-[0-9]{2}\\-[0-9]{6}')")
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


def test_filing_homepage_documents_and_datafiles():
    filing_homepage: FilingHomepage = carbo_10K.homepage
    assert 'Description'
    assert len(filing_homepage.documents) > 8
    assert len(filing_homepage.datafiles) >= 6
    assert filing_homepage.url == carbo_10K.url


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


def test_filings_toduckdb():
    filings = cached_filings(2022, 3, index="xbrl")
    filings_db = filings.to_duckdb()
    result_df = filings_db.execute("""
    select * from filings where form=='10-Q'
    """).df()
    assert len(result_df.form.drop_duplicates()) == 1


def test_filing_primary_document():
    filing = Filing(form='DEF 14A', company='180 DEGREE CAPITAL CORP. /NY/', cik=893739, filing_date='2020-03-25',
                    accession_no='0000893739-20-000019')
    primary_document: FilingDocument = filing.document
    assert primary_document
    assert primary_document.url == \
           'https://www.sec.gov/Archives/edgar/data/893739/000089373920000019/annualmeetingproxy2020-doc.htm'
    assert primary_document.extension == '.htm'
    assert primary_document.seq == '1'


barclays_filing = Filing(form='ATS-N/MA', company='BARCLAYS CAPITAL INC.', cik=851376, filing_date='2020-02-21',
                         accession_no='0000851376-20-000003')


def test_filing_primary_document_seq_5():
    primary_document: FilingDocument = barclays_filing.document
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
    primary_documents: List[FilingDocument] = filing.homepage.primary_documents
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
    related_filings = carbo_10K.get_related_filings()
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

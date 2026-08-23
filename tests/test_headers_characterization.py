"""
Characterization tests for edgar.headers.IndexHeaders.load().

These pin the exact behaviour of the bs4-based implementation *before* the
lxml.html port (#1101, part of #931). The SEC-HEADER payload lives inside an
HTML comment, so the comment-handling semantics are the risk area of the
port. Each test asserts specific values from real fixtures per the repo's
verification constitution.
"""
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import BaseModel

from edgar.headers import IndexHeaders

HEADERS_DIR = Path('data/headers')


def _load(name):
    return IndexHeaders.load((HEADERS_DIR / name).read_text())


def _flatten(obj, prefix='', out=None):
    """Flatten a pydantic model into {dotted.path: value} for exact comparison."""
    if out is None:
        out = {}
    if isinstance(obj, BaseModel):
        for name, value in obj:
            _flatten(value, f'{prefix}.{name}' if prefix else name, out)
    elif isinstance(obj, dict):
        for name, value in obj.items():
            _flatten(value, f'{prefix}.{name}', out)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            _flatten(value, f'{prefix}[{i}]', out)
    else:
        out[prefix] = obj
    return out


# --- Real fixtures: full structure pinned field-by-field -------------------

@pytest.mark.fast
def test_8k_header_full_structure():
    header = _load('23AndMe.index-headers.html')
    fields = _flatten(header)
    assert fields == {
        'acceptance_datetime': datetime(2024, 6, 3, 8, 6, 2),
        'accession_number': '0001193125-24-152391',
        'date_of_filing_date_change': '2024-06-03',
        'effectiveness_date': None,
        'filer.business_address.city': 'SOUTH SAN FRANCISCO',
        'filer.business_address.state_or_country': 'CA',
        'filer.business_address.state_or_country_description': None,
        'filer.business_address.street1': '349 OYSTER POINT BOULEVARD',
        'filer.business_address.street2': None,
        'filer.business_address.zipcode': '94080',
        'filer.company_data.assigned_sic': '2834',
        'filer.company_data.cik': '0001804591',
        'filer.company_data.conformed_name': '23andMe Holding Co.',
        'filer.company_data.fiscal_year_end': '0331',
        'filer.company_data.irs_number': '871240344',
        'filer.company_data.organization_name': '03 Life Sciences',
        'filer.filing_values.act': '34',
        'filer.filing_values.file_number': '001-39587',
        'filer.filing_values.film_number': '241012050',
        'filer.filing_values.form_type': '8-K',
        'filer.mail_address.city': 'SOUTH SAN FRANCISCO',
        'filer.mail_address.state_or_country': 'CA',
        'filer.mail_address.state_or_country_description': None,
        'filer.mail_address.street1': '349 OYSTER POINT BOULEVARD',
        'filer.mail_address.street2': None,
        'filer.mail_address.zipcode': '94080',
        'filing_date': '2024-06-03',
        'form': '8-K',
        'issuer': None,
        'items[0]': '7.01',
        'items[1]': '9.01',
        'period': '20240603',
        'public_document_count': 14,
        'reporting_owner': None,
        'subject_company': None,
    }


@pytest.mark.fast
def test_form4_with_reporting_owner_structure():
    # This fixture is bare SGML (no <HTML> wrapper and no HTML comment), so it
    # exercises the "comment missing" path of load() today.
    text = (HEADERS_DIR / 'form4.index-headers.html').read_text()
    with pytest.raises(IndexError):
        IndexHeaders.load(text)


@pytest.mark.fast
def test_144_header_full_structure():
    header = _load('0001971857-23-000246-index-headers.html')
    fields = _flatten(header)
    assert fields == {
        'acceptance_datetime': datetime(2023, 6, 12, 15, 5, 50),
        'accession_number': '0001971857-23-000246',
        'date_of_filing_date_change': '2023-06-12',
        'effectiveness_date': None,
        'filer': None,
        'filing_date': '2023-06-12',
        'form': '144',
        'issuer': None,
        'period': None,
        'public_document_count': 1,
        'reporting_owner.company_data.assigned_sic': None,
        'reporting_owner.company_data.cik': '0001701746',
        'reporting_owner.company_data.conformed_name': 'Hendrian Catherine A',
        'reporting_owner.company_data.fiscal_year_end': None,
        'reporting_owner.company_data.irs_number': None,
        'reporting_owner.company_data.organization_name': None,
        'reporting_owner.filing_values.act': '',
        'reporting_owner.filing_values.file_number': '',
        'reporting_owner.filing_values.film_number': '',
        'reporting_owner.filing_values.form_type': '144',
        'reporting_owner.mail_address.city': 'JACKSON',
        'reporting_owner.mail_address.state_or_country': 'MI',
        'reporting_owner.mail_address.state_or_country_description': None,
        'reporting_owner.mail_address.street1': 'ONE ENERGY PLAZA',
        'reporting_owner.mail_address.street2': None,
        'reporting_owner.mail_address.zipcode': '49201',
        'reporting_owner.owner_data': None,
        'subject_company.business_address.city': 'JACKSON',
        'subject_company.business_address.state_or_country': 'MI',
        'subject_company.business_address.state_or_country_description': None,
        'subject_company.business_address.street1': 'ONE ENERGY PLAZA',
        'subject_company.business_address.street2': None,
        'subject_company.business_address.zipcode': '49201',
        'subject_company.company_data.assigned_sic': '4931',
        'subject_company.company_data.cik': '0000201533',
        'subject_company.company_data.conformed_name': 'CONSUMERS ENERGY CO',
        'subject_company.company_data.fiscal_year_end': '1231',
        'subject_company.company_data.irs_number': '380442310',
        'subject_company.company_data.organization_name': None,
        'subject_company.filing_values.act': '33',
        'subject_company.filing_values.file_number': '001-05611',
        'subject_company.filing_values.film_number': '231007818',
        'subject_company.filing_values.form_type': '144',
        'subject_company.mail_address.city': 'JACKSON',
        'subject_company.mail_address.state_or_country': 'MI',
        'subject_company.mail_address.state_or_country_description': None,
        'subject_company.mail_address.street1': 'ONE ENERGY PLAZA',
        'subject_company.mail_address.street2': None,
        'subject_company.mail_address.zipcode': '49201',
    }
    assert fields['subject_company.company_data.conformed_name'] == 'CONSUMERS ENERGY CO'
    assert header.form == '144'


@pytest.mark.fast
def test_13f_header_parses():
    header = _load('objectivecapital.form144-index-headers.html')
    assert header.form == '13F-HR'
    assert header.filer.company_data.conformed_name == 'Objective Capital Management, LLC'


@pytest.mark.fast
def test_8k_choiceone_items_list():
    header = _load('index-headers.html')
    assert header.form == '8-K'
    assert header.items == ['5.07']


# --- Edge cases: current contract is IndexError ----------------------------

@pytest.mark.fast
def test_empty_input_raises_index_error():
    with pytest.raises(IndexError):
        IndexHeaders.load('')


@pytest.mark.fast
def test_whitespace_only_input_raises_index_error():
    with pytest.raises(IndexError):
        IndexHeaders.load('   ')


@pytest.mark.fast
def test_html_without_comment_raises_index_error():
    with pytest.raises(IndexError):
        IndexHeaders.load('<HTML><HEAD><TITLE>x</TITLE></HEAD><BODY>hi</BODY></HTML>')


@pytest.mark.fast
def test_result_is_pydantic_model():
    header = _load('23AndMe.index-headers.html')
    assert isinstance(header, BaseModel)

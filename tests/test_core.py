import datetime
import os
import tempfile
from datetime import datetime

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pytest
from freezegun import freeze_time
from rich.table import Table
from pathlib import Path
import edgar
from edgar.core import (decode_content,
                        get_identity,
                        set_identity,
                        ask_for_identity,
                        display_size,
                        Result,
                        filter_by_date,
                        filter_by_form,
                        filter_by_cik,
                        InvalidDateException,
                        client_headers,
                        CRAWL, CAUTION, extract_dates,
                        reverse_name,
                        get_bool,
                        is_start_of_quarter,
                        split_camel_case,
                        download_edgar_data, filter_by_ticker)
from edgar.richtools import *


def test_decode_content():
    text = "Kyle Walker vs Mbappe"
    assert decode_content(text.encode('utf-8')) == text
    assert decode_content(text.encode('latin-1')) == text


def test_decode_latin1():
    text = "Mbappe vs Messi"
    assert decode_content(text.encode("latin-1")) == text


def test_get_identity():
    identity = get_identity()
    assert identity


def test_get_identity_environment_variable_not_set(monkeypatch):
    monkeypatch.setattr('builtins.input', lambda: "Tom Holland tholland@restishistory.com")
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)
    identity = get_identity()
    assert identity == "Tom Holland tholland@restishistory.com"


def test_set_identity():
    old_identity = get_identity()
    set_identity("Mike Tirico mtirico@cal.com")
    assert get_identity() == "Mike Tirico mtirico@cal.com"
    set_identity(old_identity)


def test_ask_for_identity(monkeypatch):
    monkeypatch.setattr('builtins.input', lambda: "Tom Holland tholland@restishistory.com")
    identity = ask_for_identity()
    assert identity == "Tom Holland tholland@restishistory.com"


def test_ask_for_identity_prompt(monkeypatch, capsys):
    monkeypatch.setattr('builtins.input', lambda: "Tom Holland tholland@restishistory.com")
    identity = ask_for_identity("Who are you")
    assert identity == "Tom Holland tholland@restishistory.com"
    captured = capsys.readouterr()
    assert 'Who are you' in captured.out


def test_ask_for_identity_keyboard_interrupt(monkeypatch):
    def input_interrupt():
        raise KeyboardInterrupt()

    monkeypatch.setattr('builtins.input', input_interrupt)
    with pytest.raises(TimeoutError) as exc:
        ask_for_identity("Who are you")


def test_get_header():
    assert client_headers()['User-Agent'] == get_identity()


def test_df_to_rich_table():
    df = pd.read_csv('data/cereal.csv')
    table: Table = df_to_rich_table(df)
    assert table
    assert len(table.rows) == 21


def test_repr_rich():
    df = pd.read_csv('data/cereal.csv',
                     usecols=['name', 'mfr', 'type', 'calories', 'protein', 'fat', 'sodium'])
    table: Table = df_to_rich_table(df)
    value = repr_rich(table)
    assert '100% Bran' in value


def test_result():
    result = Result.Ok(value=1)
    assert result.success
    assert not result.failure
    assert result.value == 1

    assert "Success" in str(result)

    result = Result.Fail("Does not work")
    assert result.failure
    assert not result.success
    assert not result.value
    assert result.error == "Does not work"
    assert "Failure" in str(result)


def test_display_size():
    assert display_size(117000) == "114.3 KB"
    assert display_size(1170000) == "1.1 MB"
    assert display_size("117000") == "114.3 KB"
    assert display_size("1170000") == "1.1 MB"
    assert display_size(None) == ""
    assert display_size("aaa") == ""
    assert display_size("\x01") == ""


def test_extract_dates():
    assert extract_dates("2022-03-04") == (datetime.strptime("2022-03-04", "%Y-%m-%d"), None, False)
    assert extract_dates("2022-03-04:") == (datetime.strptime("2022-03-04", "%Y-%m-%d"), None, True)
    assert extract_dates(":2022-03-04") == (None, datetime.strptime("2022-03-04", "%Y-%m-%d"), True)
    assert extract_dates("2022-03-04:2022-04-04") == (
        datetime.strptime("2022-03-04", "%Y-%m-%d"), datetime.strptime("2022-04-04", "%Y-%m-%d"), True)

    # Invalid dates
    with pytest.raises(InvalidDateException):
        extract_dates("2022-44-44")


def test_invalid_date_exception():
    exception = InvalidDateException("Something went wrong")
    assert str(exception) == "Something went wrong"


def test_filter_by_date():
    arrays = [pa.array(['a', 'b', 'c']),
              pa.array([3, 2, 1]),
              pc.cast(pc.strptime(pa.array(['2013-04-24', '2015-12-03', '2017-08-10']), '%Y-%m-%d', 'us'), pa.date32())]

    # arrays[2] = pc.cast(pc.strptime(arrays[2], '%Y-%m-%d', 'us'), pa.date32())
    table = pa.Table.from_arrays(arrays,
                                 names=['item', 'value', 'date']
                                 )

    assert len(filter_by_date(table, '2013-04-24', 'date')) == 1
    assert len(filter_by_date(table, '2013-04-24:2016-04-24', 'date')) == 2

    # Use datetime to filter by date
    assert len(filter_by_date(table, datetime.strptime('2013-04-24', '%Y-%m-%d'), 'date')) == 1


def test_filter_by_form():
    arrays = [pa.array(['a', 'b', 'c', 'd']),
              pa.array([3, 2, 1, 4]),
              pa.array(['10-K', '10-Q', '10-K', '10-K/A'])]

    table = pa.Table.from_arrays(arrays, names=['item', 'value', 'form'])

    assert len(filter_by_form(table, '10-K', )) == 3
    assert len(filter_by_form(table, ['10-K', '10-Q'], )) == 4

    # Amendments false
    assert len(filter_by_form(table, form='10-K', amendments=False)) == 2

    assert len(filter_by_form(table, form=['10-K', '10-Q', '10-K/A'], amendments=False)) == 3
    assert len(filter_by_form(table, form=['10-K', '10-Q', '10-K/A'], amendments=True)) == 4


def test_filter_by_cik():
    arrays = [pa.array(['a', 'b', 'c', 'd', 'e']),
              pa.array([3, 2, 1, 4, 4]),
              pa.array(['10-K', '10-Q', '10-K', '10-K/A', '4-K']),
              pa.array([3, 2, 1, 4, 4])
              ]

    table = pa.Table.from_arrays(arrays, names=['item', 'value', 'form', 'cik'])

    assert len(filter_by_cik(table, 1)) == 1
    assert len(filter_by_cik(table, [3, 4], )) == 3
    assert len(filter_by_cik(table, ['3', 4], )) == 3
    assert len(filter_by_cik(table, ['3'], )) == 1


def test_filter_by_ticker():

    arrays = [pa.array(['a', 'b', 'c', 'd', 'e']),
              pa.array([3, 2, 1, 4, 4]),
              pa.array(['10-K', '10-Q', '10-K', '10-K/A', '4-K']),
              pa.array([1318605, 320193, 1341439, 789019, 789019]),
              pa.array(['TSLA', 'AAPL', 'ORCL', 'MSFT', 'MSFT'])
              ]

    table = pa.Table.from_arrays(arrays, names=['item', 'value', 'form', 'cik', 'ticker'])
    assert len(filter_by_ticker(table, 'TSLA')) == 1
    assert len(filter_by_ticker(table, 'MSFT')) == 2
    assert len(filter_by_ticker(table, 'ORCL')) == 1
    assert len(filter_by_ticker(table, 'PD')) == 0


def test_dataframe_pager():
    from edgar.core import DataPager
    import numpy as np
    df = pd.DataFrame({'A': np.random.randint(0, 100, size=150),
                       'B': np.random.randint(0, 100, size=150)})
    pager = DataPager(df, 100)
    # Test getting the first page
    first_page = pager.current()
    assert len(first_page) == 100

    """ 

    # Test getting the next page
    second_page = pager.next()
    assert len(second_page) == 50
    assert all(first_page.iloc[-1] != second_page.iloc[0])

    # Test getting the previous page
    prev_page = pager.previous()
    assert len(prev_page) == 100
    assert all(first_page == prev_page)

    # Test going to the next page again
    next_page = pager.next()
    assert len(next_page) == 50
    assert all(second_page == next_page)

    # Test going to the next page when there is no more page
    last_page = pager.next()
    assert last_page is None
    """


def test_settings():
    assert edgar.edgar_mode.max_connections == 10

    edgar.edgar_mode = CAUTION
    assert edgar.edgar_mode.max_connections == 5

    edgar.edgar_mode = CRAWL
    assert edgar.edgar_mode.max_connections == 2


def test_reverse_name():
    assert reverse_name('WALKER KYLE') == 'Kyle Walker'
    assert reverse_name('KONDO CHRIS') == 'Chris Kondo'
    assert reverse_name('KONDO CHRIS Jr') == 'Chris Kondo Jr'
    assert reverse_name('KONDO CHRIS Jr.') == 'Chris Kondo Jr.'
    assert reverse_name('KONDO CHRIS Jr ET AL') == 'Chris Kondo Jr ET AL'
    assert reverse_name('KONDO CHRIS Jr et al') == 'Chris Kondo Jr et al'
    assert reverse_name('KONDO CHRIS Jr et al.') == 'Chris Kondo Jr et al.'
    assert reverse_name('JAMES HAMILTON E') == 'Hamilton E James'
    assert reverse_name('BURNS BENJAMIN MICHAEL') == 'Benjamin Michael Burns'
    assert reverse_name('FROST PHILLIP MD') == 'Phillip Frost MD'
    assert reverse_name('FROST PHILLIP MD ET AL') == 'Phillip Frost MD ET AL'
    assert reverse_name("Borninkhof K. Michelle") == "Michelle K. Borninkhof"
    assert reverse_name("Bennett C Frank") == "Frank C Bennett"
    assert reverse_name("Frank Thomas AJ") == "Thomas AJ Frank"

    assert reverse_name("FOSTER WATT R JR") == "Watt R Foster JR"
    # Single word name
    assert reverse_name("WATT") == "Watt"
    # O'Names
    assert reverse_name("O'CONNELL BENJAMIN") == "Benjamin O'Connell"


def test_get_bool():
    assert get_bool(1)
    assert get_bool("1")
    assert get_bool("Y")
    assert get_bool("true")
    assert get_bool("TRUE")
    assert get_bool("True")


def test_split_camel_case():
    assert split_camel_case("CoverPage") == "Cover Page"
    assert split_camel_case("CONSOLIDATEDBALANCESHEETS") == "CONSOLIDATEDBALANCESHEETS"
    assert split_camel_case("consolidatedbalancesheets") == "consolidatedbalancesheets"
    assert split_camel_case("SummaryofSignificantAccountingPolicies") == "Summaryof Significant Accounting Policies"
    assert split_camel_case("RoleStatementINCOMESTATEMENTS") == "Role Statement INCOMESTATEMENTS"


@pytest.mark.parametrize("test_date, expected_result", [
    ("2024-01-01", True),  # New Year's Day (start of Q1)
    ("2024-01-02", True),  # First business day after New Year's
    ("2024-01-03", False),  # Second business day after New Year's
    ("2024-03-31", False),  # Last day of Q1
    ("2024-04-01", True),  # First day of Q2
    ("2024-04-02", True),  # Possibly first business day of Q2
    ("2024-04-03", False),  # Second business day of Q2
    ("2024-07-01", True),  # First day of Q3
    ("2024-07-02", True),  # Possibly first business day of Q3
    ("2024-07-03", False),  # Second business day of Q3
    ("2024-10-01", True),  # First day of Q4
    ("2024-10-02", True),  # Possibly first business day of Q4
    ("2024-10-03", False),  # Second business day of Q4
    ("2024-12-31", False),  # Last day of Q4
    ("2024-05-15", False),  # Random day in middle of quarter
])
def test_is_start_of_quarter(test_date, expected_result):
    with freeze_time(test_date):
        assert is_start_of_quarter() == expected_result


@pytest.mark.parametrize("test_datetime, expected_result", [
    ("2024-01-01 00:00:01", True),  # Just after midnight on New Year's
    ("2024-01-02 23:59:59", True),  # Just before midnight on Jan 2
    ("2024-01-03 00:00:01", False),  # Just after midnight on Jan 3
    ("2024-04-01 12:00:00", True),  # Noon on first day of Q2
    ("2024-07-01 18:30:00", True),  # Evening on first day of Q3
    ("2024-10-02 09:00:00", True),  # Morning of possibly first business day of Q4
])
def test_is_start_of_quarter_with_time(test_datetime, expected_result):
    with freeze_time(test_datetime):
        assert is_start_of_quarter() == expected_result


""" 
def test_download_edgar_data(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv("EDGAR_LOCAL_DATA_DIR", d)
        assert os.environ["EDGAR_LOCAL_DATA_DIR"] == d
        download_edgar_data(submissions=False, facts=False, reference=True)
        files = set(f.name for f in (Path(d) /"reference").glob("*"))
        assert files & {'ticker.txt', 'company_tickers_exchange.json', 'company_tickers.json',
                         'company_tickers_mf.json'}
"""

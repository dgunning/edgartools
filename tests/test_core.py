import datetime

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import importlib
from datetime import datetime
import edgar
from edgar._rich import *
from edgar.core import (decode_content,
                        get_identity,
                        set_identity,
                        ask_for_identity,
                        display_size,
                        Result,
                        filter_by_date,
                        http_client,
                        InvalidDateException,
                        client_headers,
                        CRAWL, CAUTION, NORMAL,
                        download_file,
                        extract_dates)
import re
from rich.table import Table
import pytest


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


def test_download_index_file():
    xbrl_gz = download_file('https://www.sec.gov/Archives/edgar/full-index/2021/QTR1/xbrl.gz')
    assert isinstance(xbrl_gz, bytes)
    assert len(xbrl_gz) > 10000

    xbrl_idx = download_file('https://www.sec.gov/Archives/edgar/full-index/2021/QTR1/xbrl.idx')
    assert isinstance(xbrl_idx, str)


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


def test_detect_charset():
    url = 'https://www.sec.gov/Archives/edgar/data/1089113/000165495420002467/a7664f.htm'
    client = http_client()
    r = client.get(url)
    print(r.encoding)
    assert r.encoding == 'ascii'


def test_download_image():
    url = 'https://www.sec.gov/Archives/edgar/data/1640147/000164014722000023/snow-20220131_g1.jpg'
    client = http_client()
    r = client.get(url)
    print(r.encoding)
    print(r.content)
    download_file(url)


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


def test_dataframe_pager():
    from edgar.core import DataPager
    import numpy as np
    df = pd.DataFrame({'A': np.random.randint(0, 100, size=150),
                       'B': np.random.randint(0, 100, size=150)})
    pager = DataPager(df, 100)
    # Test getting the first page
    first_page = pager.current()
    assert len(first_page) == 100

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


def test_settings():
    assert edgar.edgar_mode.max_connections == 10

    edgar.edgar_mode = CAUTION
    assert edgar.edgar_mode.max_connections == 5

    edgar.edgar_mode = CRAWL
    assert edgar.edgar_mode.max_connections == 2

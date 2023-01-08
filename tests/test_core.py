import pandas as pd
import importlib

from edgar.core import (decode_content,
                        get_identity,
                        set_identity,
                        ask_for_identity,
                        repr_rich,
                        Result,
                        get_resource,
                        client_headers,
                        df_to_table,
                        download_file)
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
    table: Table = df_to_table(df)
    assert table
    assert len(table.rows) == 21


def test_repr_rich():
    df = pd.read_csv('data/cereal.csv',
                     usecols=['name', 'mfr', 'type', 'calories', 'protein', 'fat', 'sodium'])
    table: Table = df_to_table(df)
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


def test_get_resource():
    data_dir = get_resource('data')
    assert str(data_dir).endswith('data')
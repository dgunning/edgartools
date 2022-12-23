from edgar.core import (decode_content,
                        get_identity,
                        set_identity,
                        client_headers,
                        download_file)
import re


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


def test_set_identity():
    old_identity = get_identity()
    set_identity("Mike Tirico mtirico@cal.com")
    assert get_identity() == "Mike Tirico mtirico@cal.com"
    set_identity(old_identity)


def test_get_header():
    assert client_headers()['User-Agent'] == get_identity()


def test_download_index_file():
    xbrl_gz = download_file('https://www.sec.gov/Archives/edgar/full-index/2021/QTR1/xbrl.gz')
    assert isinstance(xbrl_gz, bytes)
    assert len(xbrl_gz) > 10000

    xbrl_idx = download_file('https://www.sec.gov/Archives/edgar/full-index/2021/QTR1/xbrl.idx')
    assert isinstance(xbrl_idx, str)


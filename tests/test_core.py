from edgar.core import decode_content, get_identity, set_identity, client_headers
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

from edgar.core import decode_content, get_edgar_identity, set_edgar_identity, client_headers
import re


def test_decode_content():
    text = "Kyle Walker vs Mbappe"
    assert decode_content(text.encode('utf-8')) == text
    assert decode_content(text.encode('latin-1')) == text


def test_get_identity():
    identity = get_edgar_identity()
    assert identity


def test_set_identity():
    old_identity = get_edgar_identity()
    name, email = ' '.join(old_identity.split(' ')[:2]), old_identity.split(' ')[2]
    set_edgar_identity("Mike Tirico", "mtirico@cal.com")
    assert get_edgar_identity() == "Mike Tirico mtirico@cal.com"
    set_edgar_identity(name, email)


def test_get_header():
    assert client_headers()['User-Agent'] == get_edgar_identity()

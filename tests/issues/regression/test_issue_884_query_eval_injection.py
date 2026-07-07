"""Regression test for GH #884 — eval injection in Attachments.query().

edgar/attachments.py previously evaluated the query string with ``eval()`` and a
globals dict that omitted ``__builtins__``, so Python auto-injected the full
builtin namespace and any query string could execute arbitrary code
(``__import__('os').system(...)``, ``open('/etc/passwd').read()``, ...).

The query is now parsed and evaluated against a restricted AST
(``_AttachmentQuery``). These tests assert that legitimate filter strings still
work and that injection payloads raise ``ValueError`` instead of executing.
"""
import pytest

from edgar.attachments import _AttachmentQuery


class _FakeAttachment:
    """Minimal stand-in exposing the three query fields."""

    def __init__(self, document, description, document_type):
        self.document = document
        self.description = description
        self.document_type = document_type


@pytest.fixture
def docs():
    return [
        _FakeAttachment('ea023837201ex99-1_abvcbio.htm', 'PRESS RELEASE', 'EX-99.1'),
        _FakeAttachment('mmm-form.xml', 'DATA FILE', 'EX-101'),
        _FakeAttachment('other.txt', 'nothing here', 'EX-99'),
    ]


def _run(query_str, docs):
    evaluator = _AttachmentQuery(query_str)
    return [d.document for d in docs if evaluator.matches(d)]


# --- Legitimate queries must keep working ---------------------------------

def test_regex_and_membership(docs):
    result = _run("re.match('ea.*.htm', document) and document_type in ['EX-99', 'EX-99.1']", docs)
    assert result == ['ea023837201ex99-1_abvcbio.htm']


def test_equality_no_match(docs):
    assert _run("document_type=='NONEXISTENT'", docs) == []


def test_endswith(docs):
    assert _run("document.endswith('.xml')", docs) == ['mmm-form.xml']


def test_substring_in_description(docs):
    result = _run(
        "document.endswith('.htm') and 'RELEASE' in description "
        "and document_type in ['EX-99.1', 'EX-99', 'EX-99.01']",
        docs,
    )
    assert result == ['ea023837201ex99-1_abvcbio.htm']


def test_not_in(docs):
    assert _run("document_type not in ['EX-99']", docs) == [
        'ea023837201ex99-1_abvcbio.htm',
        'mmm-form.xml',
    ]


# --- Injection payloads must be rejected, never executed ------------------

@pytest.mark.parametrize("payload", [
    "__import__('os').system('echo pwned')",
    "open('/etc/passwd').read()",
    "().__class__.__bases__[0].__subclasses__()",
    "__import__('urllib.request', fromlist=['urlopen']).urlopen('http://x')",
    "document.encode().decode()",          # non-whitelisted string method
    "eval('1')",                            # bare builtin call
    "exec('x=1')",
    "[c for c in ()]",                      # comprehension
    "globals()",
])
def test_injection_payloads_raise(payload):
    with pytest.raises(ValueError):
        # Construction validates the AST, so the payload is rejected before any
        # attachment is scanned.
        _AttachmentQuery(payload)


def test_injection_does_not_execute(tmp_path):
    """A payload that would write a file must not run — the file stays absent."""
    marker = tmp_path / "pwned.txt"
    payload = f"open({str(marker)!r}, 'w').write('x')"
    with pytest.raises(ValueError):
        _AttachmentQuery(payload)
    assert not marker.exists()


def test_syntactically_invalid_query_raises():
    with pytest.raises(ValueError):
        _AttachmentQuery("document ==")

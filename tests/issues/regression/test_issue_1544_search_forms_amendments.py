"""
Regression test for GitHub issue #1544: an amendment code in ``forms`` dropped every original filing

EFTS returns amendments only as soon as ``forms`` holds an amendment code
(``S-1/A``), for every form in the list, while a root code (``S-1``) already
matches its amendments. ``search_filings(q, forms=["F-1", "F-1/A"])`` therefore
returned no F-1 at all: for ``"YHTE"`` (Primagrove Ltd, F-1 filed 2026-09-30)
``["F-1"]`` found 1 filing and ``["F-1", "F-1/A"]`` found 0, measured by the
reporter on 2026-10-14. The amendment code is now dropped when its root form is
listed, and mixing an amendment code without its root with other forms warns.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1544
"""

import warnings
from types import SimpleNamespace

import pytest

from edgar.search import efts

pytestmark = pytest.mark.fast

EMPTY_BODY = (b'{"took":5,"timed_out":false,"_shards":{"total":50,"successful":50,"skipped":0,"failed":0},'
              b'"hits":{"total":{"value":0,"relation":"eq"},"max_score":null,"hits":[]}}')


@pytest.fixture
def sent_forms(monkeypatch):
    requests = []

    def fake_get(url, params=None, **kwargs):
        requests.append(dict(params or {}))
        return SimpleNamespace(content=EMPTY_BODY)

    monkeypatch.setattr("edgar.httprequests.get_with_retry", fake_get)

    def search(forms):
        efts.search_filings('"YHTE"', forms=forms)
        return requests[-1].get("forms")

    return search


@pytest.mark.parametrize("forms, expected", [
    (["F-1", "F-1/A"], "F-1"),
    (["S-1", "S-1/A", "F-1", "F-1/A", "424B4"], "S-1,F-1,424B4"),
    (["F-1/A", "F-1"], "F-1"),
])
def test_amendment_code_with_its_root_is_not_sent(sent_forms, forms, expected):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert sent_forms(forms) == expected


@pytest.mark.parametrize("forms, expected", [
    ("S-1/A", "S-1/A"),
    (["S-1/A"], "S-1/A"),
    (["S-1/A", "F-1/A"], "S-1/A,F-1/A"),
    (["S-1", "F-1"], "S-1,F-1"),
])
def test_other_form_lists_are_sent_unchanged_without_warning(sent_forms, forms, expected):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert sent_forms(forms) == expected


def test_amendment_code_without_its_root_mixed_with_other_forms_warns(sent_forms):
    with pytest.warns(UserWarning, match="List the root form instead \\(S-1\\)"):
        assert sent_forms(["S-1/A", "F-1"]) == "S-1/A,F-1"

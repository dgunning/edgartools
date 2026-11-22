"""
XBRL.element_metadata(): what a concept is (GH #1426).

Ground truth from tracked fixtures, read offline:
- Apple's 10-Q for the quarter ended 2025-03-29 (accession 0000320193-25-000057),
  tests/fixtures/attachments/aapl/20250329, whose MetaLinks.json lists
  us-gaap_Assets as monetaryItemType, crdr debit, with 30 ASC references, the
  first ASC 942-210-S99-1, and no crdr for CommonStockSharesOutstanding (6
  references). Its own schema declares aapl_A0.875NotesDue2025Member abstract.
- Microsoft's FY2024 10-K (accession 0000950170-24-087843), which has no
  MetaLinks.json in its fixture directory.

Oracle's 10-Q 0001193125-26-389274 (the issue's example) was checked live:
IncreaseDecreaseInContractWithCustomerLiability is debit with references ASC
912-310-45-11 and 230-10-45-28.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1426
"""

from pathlib import Path

import pandas as pd
import pytest

import edgar.httprequests
from edgar.exceptions import TransportError
from edgar.xbrl import XBRL, ElementMetadata
from edgar.xbrl.element_metadata import MetaLinksSource, _FilingMetaLinks

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
AAPL_10Q = FIXTURES / "attachments" / "aapl" / "20250329"
MSFT_10K = FIXTURES / "xbrl" / "msft" / "10k_2024"
METALINKS_TEXT = (AAPL_10Q / "MetaLinks.json").read_text()


@pytest.fixture(scope="module")
def aapl():
    return XBRL.from_directory(AAPL_10Q)


def test_standard_concept_metadata(aapl):
    meta = aapl.element_metadata("us-gaap:Assets")
    assert isinstance(meta, ElementMetadata)
    assert meta.concept == "us-gaap_Assets"
    assert (meta.prefix, meta.name, meta.is_standard) == ("us-gaap", "Assets", True)
    assert meta.data_type == "xbrli:monetaryItemType"
    assert meta.balance == "debit"
    assert meta.period_type == "instant"
    assert meta.abstract is False
    assert meta.documentation == "Amount of asset recognized for present right to economic benefit."
    assert len(meta.references) == 30
    first = meta.references[0]
    assert (first.topic, first.sub_topic, first.section, first.paragraph) == ("942", "210", "S99", "1")


def test_both_spellings_give_the_same_answer(aapl):
    assert aapl.element_metadata("us-gaap:Assets") == aapl.element_metadata("us-gaap_Assets")


def test_no_balance_is_none_not_a_default(aapl):
    shares = aapl.element_metadata("us-gaap_CommonStockSharesOutstanding")
    assert shares.balance is None
    assert shares.data_type == "xbrli:sharesItemType"
    assert len(shares.references) == 6
    cash = aapl.element_metadata("us-gaap:NetCashProvidedByUsedInOperatingActivities")
    assert cash.balance is None
    assert cash.period_type == "duration"


def test_extension_concept_uses_the_filing_declaration(aapl):
    meta = aapl.element_metadata("aapl_A0.875NotesDue2025Member")
    assert meta.is_standard is False
    assert meta.abstract is True
    assert meta.data_type.endswith("domainItemType")
    # MetaLinks was read and lists no references for it
    assert meta.references == ()


def test_dei_abstract_is_unknown_not_guessed(aapl):
    # dei is not in the bundled table and the filing does not declare it
    meta = aapl.element_metadata("dei:EntityRegistrantName")
    assert meta.abstract is None
    assert meta.documentation.startswith("The exact name of the entity filing the report")


def test_unknown_concept_returns_none(aapl):
    assert aapl.element_metadata("us-gaap:NoSuchConcept") is None
    assert aapl.element_metadata("abc:Nothing") is None


@pytest.mark.parametrize("bad,error", [("Assets", ValueError), ("", ValueError), (None, TypeError)])
def test_bad_concept_raises_a_useful_error(aapl, bad, error):
    with pytest.raises(error, match="us-gaap:Assets"):
        aapl.element_metadata(bad)


def test_without_metalinks_references_are_unavailable():
    meta = XBRL.from_directory(MSFT_10K).element_metadata("us-gaap:Assets")
    # Declared fields still come from the bundled FASB table
    assert (meta.balance, meta.period_type, meta.abstract) == ("debit", "instant", False)
    assert meta.references is None
    assert meta.documentation is None


def test_lookup_does_not_change_statements():
    xbrl = XBRL.from_directory(AAPL_10Q)
    before = xbrl.statements.balance_sheet().to_dataframe()
    xbrl.element_metadata("us-gaap:Assets")
    pd.testing.assert_frame_equal(before, xbrl.statements.balance_sheet().to_dataframe())


def test_metalinks_read_once_and_absence_is_kept():
    calls = []

    def load():
        calls.append(1)
        return METALINKS_TEXT

    source = MetaLinksSource(load, "test")
    assert calls == []  # nothing read until asked
    assert source.get().get_tag("us-gaap_Assets").crdr == "debit"
    source.get()
    assert calls == [1]

    absent = MetaLinksSource(lambda: calls.append(2), "test")
    assert absent.get() is None and absent.get() is None
    assert calls == [1, 2]


def test_failed_metalinks_read_is_retried():
    attempts = []

    def load():
        attempts.append(1)
        if len(attempts) == 1:
            raise TransportError("connection reset")
        return METALINKS_TEXT

    source = MetaLinksSource(load, "test")
    with pytest.raises(TransportError):
        source.get()
    assert source.get() is not None


class _Sgml:
    def get_content(self, name):
        assert name == "MetaLinks.json"
        return METALINKS_TEXT


class _Filing:
    base_dir = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000057"
    accession_no = "0000320193-25-000057"

    def __init__(self, sgml=None):
        self._sgml = sgml

    def sgml(self):
        return self._sgml


def test_filing_with_loaded_submission_reads_it(monkeypatch):
    monkeypatch.setattr(edgar.httprequests, "download_file", lambda *a, **k: pytest.fail("no download expected"))
    assert _FilingMetaLinks(_Filing(_Sgml()))() == METALINKS_TEXT


def test_filing_without_submission_fetches_one_file(monkeypatch):
    urls = []
    monkeypatch.setattr(edgar.httprequests, "download_file", lambda url, **k: urls.append(url) or METALINKS_TEXT)
    assert _FilingMetaLinks(_Filing())() == METALINKS_TEXT
    assert urls == [f"{_Filing.base_dir}/MetaLinks.json"]


def test_filing_without_metalinks_is_absent_but_other_errors_raise(monkeypatch):
    def not_found(url, **k):
        raise TransportError("HTTP 404", url=url, status_code=404)

    monkeypatch.setattr(edgar.httprequests, "download_file", not_found)
    assert _FilingMetaLinks(_Filing())() is None

    def forbidden(url, **k):
        raise TransportError("HTTP 403", url=url, status_code=403)

    monkeypatch.setattr(edgar.httprequests, "download_file", forbidden)
    with pytest.raises(TransportError):
        _FilingMetaLinks(_Filing())()

"""
EFTSResult answers to the Filing names accession_no and filing_date.

A full-text search result names its fields after EFTS (``accession_number``,
``filed``); a ``Filing`` names them after the filing index (``accession_no``,
``filing_date``). In the README agent eval (07lk.19.16, Sonnet 5.5, 132 runs),
every API error on the full-text task was ``result.accession_no`` or
``result.filing_date``, written by agents with and without the README. Both
are now read-only aliases. ``filing_date`` is a ``datetime.date``, as on Filing;
``filed`` keeps the ISO string.

Ground truth: NVIDIA's earnings 8-K filed 2026-08-26, accession
0001045810-26-000073, items 2.02 and 9.01 (data.sec.gov submissions JSON).
"""
from datetime import date

import pytest

from edgar.search.efts import EFTSResult, search_filings

NVDA_8K = "0001045810-26-000073"


def _result(**kw) -> EFTSResult:
    return EFTSResult(**{"accession_number": NVDA_8K, "form": "8-K", "filed": "2026-08-26", **kw})


@pytest.mark.fast
def test_accession_no_is_accession_number():
    assert _result().accession_no == NVDA_8K


@pytest.mark.fast
def test_filing_date_is_a_date_like_on_filing():
    result = _result()
    assert result.filing_date == date(2026, 8, 26)
    assert result.filed == "2026-08-26"  # unchanged: still the string EFTS returns


@pytest.mark.fast
def test_no_date_means_no_filing_date():
    assert _result(filed="").filing_date is None


@pytest.mark.fast
def test_a_malformed_date_raises_rather_than_hiding():
    with pytest.raises(ValueError):
        _result(filed="26/08/2026").filing_date  # noqa: B018


@pytest.mark.fast
def test_the_aliases_are_not_fields():
    """Serialized results (MCP, to_context) must not grow duplicate keys."""
    from dataclasses import asdict
    assert {"accession_no", "filing_date"}.isdisjoint(asdict(_result()))


@pytest.mark.network
def test_live_search_result_uses_filing_names():
    results = search_filings(forms="8-K", items="2.02", ticker="NVDA",
                             start_date="2026-08-26", end_date="2026-08-26")
    hit = next(r for r in results if r.accession_number == NVDA_8K)
    assert hit.accession_no == NVDA_8K
    assert hit.filing_date == date(2026, 8, 26)
    assert hit.get_filing().accession_no == hit.accession_no

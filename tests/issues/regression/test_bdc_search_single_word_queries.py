"""Searching a BDC by the one word anyone knows it by found nothing.

`_bdc_score` scored names with `fuzz.ratio`, a whole-string similarity, against
a threshold of 50. A BDC's registered name is longer than the part of it anyone
types, and `ratio` charges the query for the difference, so whether a search
worked came down to how long the query happened to be relative to the name:

    fuzz.ratio("ARES",       "ARES CORE INFRASTRUCTURE")  = 28.6  -> dropped
    fuzz.ratio("ANTARES",    "ANTARES PRIVATE CREDIT")    = 48.3  -> dropped
    fuzz.ratio("BLACKSTONE", "BLACKSTONE PRIVATE CREDIT") = 57.1  -> kept

`find_bdc("Ares")` and `find_bdc("Antares")` therefore returned nothing while
`find_bdc("Blackstone")` returned two, and the difference was six characters of
query, not the quality of the match. The candidate set is built from an exact
word index, so every name that reaches scoring has already matched a whole word
— the scorer was throwing away hits the index had confirmed.

`token_set_ratio` scores those word hits. `partial_ratio` would too, but it also
scores "ARES" against "ANTARES PRIVATE CREDIT" at 100, because ARES is a
substring of ANTARES; token matching gives that pair 30.8 and keeps it out.

The module's own docstring example (`find_bdc("Ares")` -> `ARES CAPITAL CORP`)
needs both this and the report-year problem fixed to hold, since the 2026 BDC
report does not list ARES CAPITAL CORP at all (#1146).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1145
"""

import pyarrow as pa
import pytest

from edgar.bdc.search import _bdc_preprocess, _bdc_score
from edgar.search.datasearch import FastSearch

THRESHOLD = 50  # BDCSearchIndex.search's default

# Names as the SEC BDC report writes them, and as _bdc_preprocess stores them.
NAMES = [
    "ARES CAPITAL CORP",             # -> "ares" ("capital"/"corp" are stripped)
    "Ares Core Infrastructure Fund",  # -> "ares core infrastructure"
    "ARES STRATEGIC INCOME FUND",     # -> "ares strategic income"
    "Antares Private Credit Fund",    # -> "antares private credit"
    "Oaktree Strategic Credit Fund",  # -> "oaktree strategic credit"
    "Blackstone Private Credit Fund",  # -> "blackstone private credit"
]


def _score(query: str, name: str) -> float:
    """Score as the index does: both sides preprocessed first."""
    return _bdc_score(_bdc_preprocess(query), _bdc_preprocess(name), "name")


def _index() -> FastSearch:
    table = pa.table({
        "name": pa.array(NAMES, type=pa.string()),
        "ticker": pa.array([""] * len(NAMES), type=pa.string()),
    })
    return FastSearch(table, ["name", "ticker"],
                      preprocess_func=_bdc_preprocess, score_func=_bdc_score)


@pytest.mark.parametrize("query,name", [
    ("Ares", "Ares Core Infrastructure Fund"),
    ("Ares", "ARES STRATEGIC INCOME FUND"),
    ("Antares", "Antares Private Credit Fund"),
    ("Blackstone", "Blackstone Private Credit Fund"),
])
def test_a_whole_word_hit_scores_above_the_threshold(query, name):
    """Length of the name is not evidence against the match."""
    assert _score(query, name) >= THRESHOLD


def test_a_substring_of_another_word_is_not_a_hit():
    """ARES is inside ANTARES, which is what rules `partial_ratio` out."""
    assert _score("Ares", "Antares Private Credit Fund") < THRESHOLD


def test_an_unrelated_name_is_not_a_hit():
    assert _score("Ares", "Oaktree Strategic Credit Fund") < THRESHOLD


def test_the_whole_name_match_ranks_above_the_partial_one():
    """Every word hit scores 100, so the tie has to break somewhere sensible."""
    exact = _score("Ares", "ARES CAPITAL CORP")
    partial = _score("Ares", "Ares Core Infrastructure Fund")

    assert exact > partial
    assert exact == 100


def test_one_word_finds_the_funds_that_carry_it():
    results = _index().search("Ares", top_n=10, threshold=THRESHOLD)
    found = {r["name"] for r in results}

    assert found == {
        "ARES CAPITAL CORP",
        "Ares Core Infrastructure Fund",
        "ARES STRATEGIC INCOME FUND",
    }
    assert results[0]["name"] == "ARES CAPITAL CORP"


def test_tickers_still_match_exactly_and_by_prefix():
    """The short-query ticker branch is untouched."""
    assert _bdc_score("ARCC", "ARCC", "ticker") == 100
    assert _bdc_score("ARC", "ARCC", "ticker") > 90
    assert _bdc_score("ARCC", "OBDC", "ticker") == 0

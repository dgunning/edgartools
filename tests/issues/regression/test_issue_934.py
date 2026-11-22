"""Name search drops two dependencies: GPL unidecode and textdistance.

unidecode is GPL-licensed and shipped inside this MIT library, used only to
transliterate names before company and BDC search indexes them. anyascii (ISC)
replaces it. textdistance supplied one function, ``jaro``, to
``SimilaritySearchIndex.similar``; rapidfuzz, already a dependency, has the
same measure as ``rapidfuzz.distance.Jaro.similarity``.

Measured before the swap (anyascii 0.3.3, unidecode 1.4.0, textdistance 4.6.3,
rapidfuzz 3.14.6):

- the search preprocessing produced identical output for all 141,949 strings in
  the bundled company_tickers.parquet and ct.pq;
- accented Latin letters (U+00A0 to U+017F) transliterate the same, except the
  archaic kra (U+0138), which no SEC name uses;
- Jaro similarity was identical to the last bit on 220,005 name pairs.

The search indexes are held only in memory, so no saved index built with the
old transliteration can meet a query built with the new one.

Bead: edgartools-07lk.7
GitHub Issue: https://github.com/dgunning/edgartools/issues/934
"""
import ast
import tomllib
from pathlib import Path

import pandas as pd
import pytest

from edgar.bdc.search import _bdc_preprocess
from edgar.search.datasearch import FastSearch, preprocess_company_name
from edgar.search.textsearch import SimilaritySearchIndex

REPO = Path(__file__).resolve().parents[3]
DROPPED = {"unidecode", "textdistance"}


@pytest.mark.fast
@pytest.mark.parametrize("name,expected", [
    ("Apple Inc.", "apple inc"),
    ("Société Générale", "societe generale"),
    ("Telefônica Brasil S.A.", "telefonica brasil sa"),
    ("Banco Bradesco S.A. – ADR", "banco bradesco sa adr"),
    ("ÅF Pöyry AB", "af poyry ab"),
    ("Straße Holding AG", "strasse holding ag"),
])
def test_company_names_transliterate_to_ascii(name, expected):
    assert preprocess_company_name(name) == expected
    assert FastSearch._default_preprocess(name) == expected


@pytest.mark.fast
def test_bdc_names_transliterate_and_drop_common_terms():
    assert _bdc_preprocess("Société Générale Capital Corp") == "societe generale"


@pytest.mark.fast
def test_jaro_similarity_scores_are_unchanged():
    df = pd.DataFrame({"name": ["apple", "microsft", "apple inc"], "id": [1, 2, 3]})
    result = SimilaritySearchIndex(df, "name").similar("apple inc", threshold=0.6)
    # textdistance.jaro scored these 1.0, 0.8518... and 0.0; .similar rounds to 2 places
    assert dict(zip(result.id, result.match, strict=True)) == {3: 1.0, 1: 0.85}


@pytest.mark.fast
def test_dropped_packages_are_not_declared():
    deps = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["dependencies"]
    names = {d.split(">")[0].split("=")[0].split("<")[0].strip().lower() for d in deps}
    assert not names & DROPPED
    assert "anyascii" in names


@pytest.mark.fast
def test_nothing_shipped_imports_the_dropped_packages():
    offenders = []
    for path in (REPO / "edgar").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            else:
                continue
            if any(m.split(".")[0] in DROPPED for m in mods):
                offenders.append(f"{path.relative_to(REPO)}:{node.lineno}")
    assert offenders == []

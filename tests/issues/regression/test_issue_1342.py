"""Regression test: `parse_investment_identifier` recompiles its regexes on every call.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1342

Six sites in `edgar/bdc/investments.py` built a pattern per call from
`re.escape()` over the module's own 181-entry `INVESTMENT_TYPES`. One piped
identifier touched 933 of them, past the 512 entries `re` caches, so every
call compiled all 933 again. On BXSL's Q2 2026 10-Q (0001736035-26-000016),
parsing its 703 identifiers once each took 40.8 s; with the patterns cached,
1.1 s, every parsed field identical.

The identifier below is one of BXSL's own rows, in that 10-Q and in its FY2025
10-K (0001736035-26-000004). Counted at `re._compiler.compile`, which every
compilation passes through; the public `re.compile` count misses the ones the
module-level `re.search`/`re.match` make. Offline: `member_candidates=()`
needs no filing.
"""

import re

import pytest

from edgar.bdc.investments import parse_investment_identifier

SNOOPY = 'Snoopy Bidco, Inc. | Non-Affiliated Issuer'


@pytest.fixture
def compilations(monkeypatch):
    counted = []
    real = re._compiler.compile

    def counting(*args, **kwargs):
        counted.append(args[0])
        return real(*args, **kwargs)

    monkeypatch.setattr(re._compiler, 'compile', counting)
    return counted


def test_a_repeated_piped_identifier_compiles_no_regex(compilations):
    # Two calls fill the cache and re-admit the module's constant patterns
    # that the first call's fill pushed out of `re`'s own 512 entries.
    for _ in range(2):
        parse_investment_identifier(SNOOPY, member_candidates=())
    compilations.clear()

    parsed = parse_investment_identifier(SNOOPY, member_candidates=())

    assert compilations == []            # 933 on every call before the fix
    assert parsed.company_name == 'Snoopy Bidco, Inc.'
    assert parsed.investment_type == 'Unclassified'
    assert parsed.industry is None

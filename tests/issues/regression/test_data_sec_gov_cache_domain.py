"""
Regression test: cache rules never matched data.sec.gov (host-key bug).

GitHub PR: https://github.com/dgunning/edgartools/pull/989

Root Cause:
-----------
`_get_cache_rules()` (edgar/httpclient.py) derived its single site-pattern key
from `SEC_BASE_URL` only (default "www.sec.gov"). httpxthrottlecache's
`get_rules()` matches the *request host* against that key with `re.match`,
which requires the pattern to appear as a prefix-anchored substring of the
host -- "www.sec.gov" never matches inside "data.sec.gov". Two of the five
rules in CACHE_RULES ("/submissions.*" and, after this fix, the new
companyfacts rule) are served from `SEC_DATA_URL` ("data.sec.gov"), not
SEC_BASE_URL -- so those rules were dead code: every request to
data.sec.gov silently skipped caching, logging "No patterns matched
data.sec.gov" (httpxthrottlecache.controller, INFO level) and always paying
full network cost, regardless of how "warm" the local cache directory was.

This was not simulated: reproduced live against data.sec.gov (two separate
fresh Python processes, no client/connection reuse possible), both showing
"No patterns matched data.sec.gov" and paying full network latency every
time. Confirmed structurally by tracing `get_rules()`/`match_request()` in
httpxthrottlecache.controller against the actual CACHE_RULES dict.

Fix:
----
`_get_cache_rules()` now derives ONE key per distinct host actually used by
`edgar.urls` (SEC_BASE_URL for tickers/index/archives, SEC_DATA_URL for
submissions/companyfacts), and routes each rule under the key for the host it
is really served from. If a custom mirror points both env vars at the same
host, the two rule sets merge under one key -- so this does not regress the
documented "custom SEC mirror" support.

Each key matches its host EXACTLY (`_host_key`), for two reasons that the
`TestHostKeyIsExact` and `TestHostKeyUsesTheSameParserAsTheMatcher` classes
below pin as regressions:

* An unanchored key leaks ACROSS hosts. `.*mirror\\.com` matches
  "data.mirror.com", and `get_rules` returns the FIRST matching key, so a
  mirror configured as base=mirror.com / data=data.mirror.com would resolve
  its data requests to the base rule set -- reproducing this very bug for
  mirror users while fixing it for sec.gov.
* The host must come from the SAME parser that produces it at match time
  (`request.url.host`, i.e. httpx). A hand-rolled `https?://([^/]+)` regex
  keeps case, port, `user@` and percent-encoding that httpx normalises away,
  so a perfectly valid mirror URL yields a key that cannot match any real
  request.

The checks are deterministic and hit no network.
"""

import importlib
import logging
import os
import re

import pytest

import edgar.config
from edgar.httpclient import (
    MAX_INDEX_AGE_SECONDS,
    MAX_SUBMISSIONS_AGE_SECONDS,
    _get_cache_rules,
)


def _rule_for(cache_rules: dict, host: str, path: str):
    """Mirror httpxthrottlecache.controller.get_rule_for_request without importing it,
    so this test does not silently pass if that dependency's matching semantics change
    underneath us without our noticing (pin OUR expectation, not their internals).

    The single load-bearing detail is that the host loop does NOT continue: `get_rules`
    returns the FIRST matching key, and `match_request` then searches only that rule set.
    A helper that falls through to later keys is strictly more permissive than the real
    matcher, and every cross-host test below would pass on an unanchored key -- green,
    and unable to fail.
    """
    for site_pattern, rules in cache_rules.items():
        if re.match(site_pattern, host):
            for rule_pattern, value in rules.items():
                if re.match(rule_pattern, path):
                    return value
            return None
    return None


@pytest.fixture
def mirror_rules():
    """Build the cache rules as a process configured for a given mirror would see them.

    `edgar.config` reads its env vars once at import time, so the reload is what makes an
    override visible; `_get_cache_rules` imports from it per call, so the function itself
    needs no re-import.

    Teardown owns the env vars rather than delegating to monkeypatch, because the order
    matters and is easy to get silently wrong: fixtures unwind in reverse, so a fixture
    that only reloads would run BEFORE monkeypatch restores the environment and would
    reload the mirror config back in. The next test then reads a mirror as if it were
    sec.gov -- and a test asserting "this host gets no rules" passes for the wrong
    reason, because under a mirror config no sec.gov host matches anything.
    """
    saved = {name: os.environ.get(name) for name in ("EDGAR_BASE_URL", "EDGAR_DATA_URL")}

    def build(base_url: str, data_url: str) -> dict:
        os.environ["EDGAR_BASE_URL"] = base_url
        os.environ["EDGAR_DATA_URL"] = data_url
        importlib.reload(edgar.config)
        return _get_cache_rules()

    yield build

    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    importlib.reload(edgar.config)


class TestTheHelperAgreesWithTheRealMatcher:
    """Everything else in this file asks `_rule_for`, our replica of the matcher. A replica
    can be wrong in the same direction as the code it is checking, and this one was: an
    earlier version fell through to later keys, which made every cross-host assertion
    unable to fail. So the replica itself is pinned, once, against the real
    `httpxthrottlecache.controller.get_rule_for_request`.

    Only this class imports the dependency's internals. If a future version changes its
    matching semantics, this fails here -- one clear failure about the contract -- instead
    of leaving the rest of the file quietly asserting the wrong thing.
    """

    # Deliberately overlapping keys, which the exact-matching rules no longer produce.
    # Agreement on non-overlapping keys is free -- any replica gets those right -- so a
    # check built only from the live rules could not fail. Insertion order is the whole
    # question: "data.overlap.test" matches both keys, and the library commits to the
    # first and searches nothing else.
    OVERLAPPING_RULES = {
        r".*overlap\.test": {"/Archives/edgar/data": True},
        r".*data\.overlap\.test": {"/submissions.*": MAX_SUBMISSIONS_AGE_SECONDS},
    }

    @pytest.mark.parametrize(
        ("rules_name", "host", "path"),
        [
            ("live", "data.sec.gov", "/submissions/CIK0000320193.json"),
            ("live", "data.sec.gov", "/api/xbrl/companyfacts/CIK0000320193.json"),
            ("live", "www.sec.gov", "/Archives/edgar/data"),
            ("live", "example.com", "/submissions/CIK0000320193.json"),
            ("live", "www.sec.gov.attacker.test", "/Archives/edgar/data"),
            # The two a fall-through replica gets wrong: the library answers None, because
            # the first matching key wins and it holds no rule for that path.
            ("overlapping", "data.overlap.test", "/submissions/CIK0000320193.json"),
            ("overlapping", "data.overlap.test", "/Archives/edgar/data"),
        ],
    )
    def test_replica_returns_what_the_library_returns(self, rules_name, host, path):
        from httpxthrottlecache.controller import get_rule_for_request

        rules = _get_cache_rules() if rules_name == "live" else self.OVERLAPPING_RULES

        assert _rule_for(rules, host, path) == get_rule_for_request(request_host=host, target=path, cache_rules=rules)


class TestDataSecGovCacheDomainRegex:
    def test_submissions_matches_under_data_sec_gov(self):
        """The bug: this returned None before the fix (rule existed, host never matched)."""
        rules = _get_cache_rules()
        value = _rule_for(rules, "data.sec.gov", "/submissions/CIK0000320193.json")
        assert value == MAX_SUBMISSIONS_AGE_SECONDS

    def test_companyfacts_matches_under_data_sec_gov(self):
        rules = _get_cache_rules()
        value = _rule_for(rules, "data.sec.gov", "/api/xbrl/companyfacts/CIK0000320193.json")
        assert value == MAX_SUBMISSIONS_AGE_SECONDS

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("/include/ticker.txt", MAX_SUBMISSIONS_AGE_SECONDS),
            ("/files/company_tickers.json", MAX_SUBMISSIONS_AGE_SECONDS),
            ("/Archives/edgar/full-index/2024/QTR4/", MAX_INDEX_AGE_SECONDS),
        ],
    )
    def test_www_sec_gov_ttl_rules_unaffected(self, path, expected):
        """Regression guard: fixing data.sec.gov must not disturb the (already-working)
        www.sec.gov rules. One case per rule, so a break names the rule it broke rather
        than stopping at the first assert and hiding the ones after it."""
        assert _rule_for(_get_cache_rules(), "www.sec.gov", path) == expected

    def test_archives_stay_cached_forever(self):
        """`True` is not a duration, it means never revalidate -- asserted by identity,
        and apart from the TTL cases, because that distinction is the rule."""
        assert _rule_for(_get_cache_rules(), "www.sec.gov", "/Archives/edgar/data") is True

    def test_unrelated_host_still_uncached(self):
        """A host matching neither pattern must still fall through to no cache policy
        (not silently start caching everything -- this pins the negative case, the
        thing a permissive "catch-all" fix could too easily get wrong)."""
        rules = _get_cache_rules()
        assert _rule_for(rules, "example.com", "/submissions/CIK0000320193.json") is None

    def test_custom_mirror_same_host_merges_rule_sets(self, mirror_rules):
        """When EDGAR_BASE_URL and EDGAR_DATA_URL point at the SAME custom host (the
        documented single-mirror case), both rule sets must still resolve under that
        one host -- this is the scenario the original single-domain-key design was
        built for, and the fix must not regress it."""
        rules = mirror_rules("https://mirror.example.org", "https://mirror.example.org")

        assert len(rules) == 1, "same-host mirror must not produce two separate keys"
        assert _rule_for(rules, "mirror.example.org", "/submissions/CIK0000320193.json") == MAX_SUBMISSIONS_AGE_SECONDS
        assert _rule_for(rules, "mirror.example.org", "/api/xbrl/companyfacts/CIK0000320193.json") == MAX_SUBMISSIONS_AGE_SECONDS
        assert _rule_for(rules, "mirror.example.org", "/Archives/edgar/data") is True


class TestHostKeyIsExact:
    """A rule written for one host must never answer for another.

    Every case here passes on an unanchored `.*<domain>` key by matching the WRONG
    rule set, which is how the data-host rules went missing on sec.gov in the first
    place (GH #490). The asserts are on the data rules, because those are the ones an
    over-broad base key silently swallows.
    """

    def test_mirror_with_separate_data_subdomain(self, mirror_rules):
        """base=mirror.example.org, data=data.mirror.example.org -- the ordinary
        two-host mirror, and the exact shape `.*mirror\\.example\\.org` absorbs."""
        rules = mirror_rules("https://mirror.example.org", "https://data.mirror.example.org")

        assert _rule_for(rules, "data.mirror.example.org", "/submissions/CIK0000320193.json") == MAX_SUBMISSIONS_AGE_SECONDS
        assert _rule_for(rules, "data.mirror.example.org", "/api/xbrl/companyfacts/CIK0000320193.json") == MAX_SUBMISSIONS_AGE_SECONDS
        assert _rule_for(rules, "mirror.example.org", "/Archives/edgar/data") is True

    def test_data_host_that_ends_with_the_base_host(self, mirror_rules):
        """The suffix case: "sec.mirror.test" is a suffix of "data.sec.mirror.test", so
        an unanchored base key matches the data host and wins on insertion order."""
        rules = mirror_rules("https://sec.mirror.test", "https://data.sec.mirror.test")

        assert _rule_for(rules, "data.sec.mirror.test", "/submissions/CIK0000320193.json") == MAX_SUBMISSIONS_AGE_SECONDS
        assert _rule_for(rules, "sec.mirror.test", "/Archives/edgar/data") is True

    def test_lookalike_host_gets_no_rules(self):
        """ "www.sec.gov.attacker.test" contains our host as a prefix. Under `.*www\\.sec\\.gov`
        it inherits every rule -- including the cache-forever Archives rule -- so a
        third party could be served from, and written into, our cache namespace."""
        rules = _get_cache_rules()

        assert _rule_for(rules, "www.sec.gov.attacker.test", "/Archives/edgar/data") is None
        assert _rule_for(rules, "data.sec.gov.attacker.test", "/submissions/CIK0000320193.json") is None


class TestHostKeyUsesTheSameParserAsTheMatcher:
    """The key is compared against `request.url.host`, so it must be built by the parser
    that produces that value. Each URL below is a valid way to configure a mirror whose
    hand-parsed key (case kept, port kept, `user@` kept) cannot match any real request:
    the mirror silently loses caching entirely.
    """

    @pytest.mark.parametrize(
        ("data_url", "request_host"),
        [
            ("https://DATA.mirror.example.org", "data.mirror.example.org"),  # httpx lowercases the host
            ("https://data.mirror.example.org:8443", "data.mirror.example.org"),  # ...the port is not part of it
            ("https://user:pw@data.mirror.example.org", "data.mirror.example.org"),  # ...nor are credentials
            ("https://mirr%C3%B6r.example.org", "mirr%c3%b6r.example.org"),  # ...and percent-encoding is lowercased
        ],
    )
    def test_configured_url_forms_still_match_the_real_request_host(self, mirror_rules, data_url, request_host):
        rules = mirror_rules("https://mirror.example.org", data_url)

        assert _rule_for(rules, request_host, "/submissions/CIK0000320193.json") == MAX_SUBMISSIONS_AGE_SECONDS

    def test_unparseable_url_caches_nothing_rather_than_borrowing_rules(self, mirror_rules, caplog):
        """A misconfigured mirror must degrade to "slow", never to "cached under some
        other host's rules". The warning is part of the contract: silence here would be
        a config error nobody can see."""
        with caplog.at_level(logging.WARNING):
            rules = mirror_rules("https://mirror.example.org", "not-a-url")

        assert "not-a-url" in caplog.text
        assert _rule_for(rules, "data.sec.gov", "/submissions/CIK0000320193.json") is None
        assert _rule_for(rules, "mirror.example.org", "/submissions/CIK0000320193.json") is None
        assert _rule_for(rules, "mirror.example.org", "/Archives/edgar/data") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

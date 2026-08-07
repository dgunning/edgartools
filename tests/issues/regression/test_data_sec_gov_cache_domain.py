"""
Regression test: data.sec.gov cache rules never matched (domain regex bug).

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
`_get_cache_rules()` now derives ONE domain pattern per distinct host
actually used by `edgar.urls` (SEC_BASE_URL for tickers/index/archives,
SEC_DATA_URL for submissions/companyfacts), and routes each rule under the
key for the host it is really served from. If a custom mirror points both
env vars at the same host, the two rule sets merge under one key -- so this
does not regress the documented "custom SEC mirror" support.

This test pins the regression with a deterministic, no-network check: build
the rules for both the default hosts and for a same-host custom mirror, and
assert every existing rule is still reachable under the host it is actually
served from.
"""

import re

import pytest

from edgar.httpclient import (
    MAX_INDEX_AGE_SECONDS,
    MAX_SUBMISSIONS_AGE_SECONDS,
    _get_cache_rules,
)


def _rule_for(cache_rules: dict, host: str, path: str):
    """Mirror httpxthrottlecache.controller.get_rule_for_request without importing it,
    so this test does not silently pass if that dependency's matching semantics change
    underneath us without our noticing (pin OUR expectation, not their internals)."""
    for site_pattern, rules in cache_rules.items():
        if re.match(site_pattern, host):
            for rule_pattern, value in rules.items():
                if re.match(rule_pattern, path):
                    return value
    return None


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

    def test_www_sec_gov_rules_unaffected(self):
        """Regression guard: fixing data.sec.gov must not disturb the (already-working)
        www.sec.gov rules -- ticker files, full-text index, and the cache-forever
        Archives rule."""
        rules = _get_cache_rules()
        assert _rule_for(rules, "www.sec.gov", "/include/ticker.txt") == MAX_SUBMISSIONS_AGE_SECONDS
        assert _rule_for(rules, "www.sec.gov", "/files/company_tickers.json") == MAX_SUBMISSIONS_AGE_SECONDS
        assert _rule_for(rules, "www.sec.gov", "/Archives/edgar/full-index/2024/QTR4/") == MAX_INDEX_AGE_SECONDS
        assert _rule_for(rules, "www.sec.gov", "/Archives/edgar/data") is True

    def test_unrelated_host_still_uncached(self):
        """A host matching neither pattern must still fall through to no cache policy
        (not silently start caching everything -- this pins the negative case, the
        thing a permissive "catch-all" fix could too easily get wrong)."""
        rules = _get_cache_rules()
        assert _rule_for(rules, "example.com", "/submissions/CIK0000320193.json") is None

    def test_custom_mirror_same_host_merges_rule_sets(self, monkeypatch):
        """When EDGAR_BASE_URL and EDGAR_DATA_URL point at the SAME custom host (the
        documented single-mirror case), both rule sets must still resolve under that
        one host -- this is the scenario the original single-domain-key design was
        built for, and the fix must not regress it."""
        monkeypatch.setenv("EDGAR_BASE_URL", "https://mirror.example.org")
        monkeypatch.setenv("EDGAR_DATA_URL", "https://mirror.example.org")
        import importlib

        import edgar.config as config_module

        importlib.reload(config_module)
        from edgar.httpclient import _get_cache_rules as get_rules_reloaded

        rules = get_rules_reloaded()
        assert len(rules) == 1, "same-host mirror must not produce two separate keys"
        assert _rule_for(rules, "mirror.example.org", "/submissions/CIK0000320193.json") == MAX_SUBMISSIONS_AGE_SECONDS
        assert _rule_for(rules, "mirror.example.org", "/api/xbrl/companyfacts/CIK0000320193.json") == MAX_SUBMISSIONS_AGE_SECONDS
        assert _rule_for(rules, "mirror.example.org", "/Archives/edgar/data") is True

        importlib.reload(config_module)  # restore for other tests in the session


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

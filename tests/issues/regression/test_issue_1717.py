"""The DEF 14A example in the reports skill and ``ProxyStatement.sections`` used section keys unguarded.

``proxy.section('compensation_discussion_and_analysis').text()`` raised
``AttributeError: 'NoneType' object has no attribute 'text'`` and
``proxy.sections['corporate_governance'].text()`` raised ``KeyError`` on Microsoft's 2025
proxy, whose section map has neither key. The skill's own note says ``proxy.section(key)``
returns None for an absent key. Both lines, and the ``ProxyStatement.sections`` docstring,
now test before calling ``.text()``.

The code is executed here as written in ``edgar/ai/skills/reports/skill.yaml``.

Ground truth (section maps read from the filings): Microsoft DEF 14A 0001193125-25-245150
(filed 2025-10-21) has the sections pay_versus_performance, equity_compensation_plan_information,
voting_proposals and stockholder_proposals, so both keys are absent. Apple DEF 14A
0001308179-26-000008 (filed 2026-01-08) has both.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1717
"""
import inspect

import pytest
import yaml

from edgar.httprequests import download_file
from edgar.proxy import ProxyStatement
from tests.paths import REPO_ROOT

SKILL = REPO_ROOT / "edgar/ai/skills/reports/skill.yaml"
# The primary documents, fetched alone: the full submissions are 30 MB and 15 MB.
MSFT_PROXY = "https://www.sec.gov/Archives/edgar/data/789019/000119312525245150/d908201ddef14a.htm"
AAPL_PROXY = "https://www.sec.gov/Archives/edgar/data/320193/000130817926000008/aapl014016-def14a.htm"


def proxy_code():
    """The sections part of the documented DEF 14A pattern (before the XBRL-only lines)."""
    patterns = yaml.safe_load(SKILL.read_text(encoding="utf-8"))["patterns"]
    code = next(p["code"] for p in patterns if p["name"] == "DEF 14A Proxy Sections")
    return code[:code.index("# Structured compensation/governance data")]


class ProxyFiling:
    """A DEF 14A whose HTML is the primary document, as ``Filing.html()`` returns it."""
    form = "DEF 14A"

    def __init__(self, url):
        self.url = url

    def html(self):
        return download_file(self.url)

    def obj(self):
        return ProxyStatement(self)


class FakeCompany:
    def __init__(self, filing):
        self.filing = filing

    def get_filings(self, form):
        return [self.filing]


def run_pattern(url):
    ns = {"company": FakeCompany(ProxyFiling(url))}
    exec(compile(proxy_code(), "skill.yaml", "exec"), ns)  # noqa: S102 - our own documentation
    return ns


@pytest.mark.vcr
def test_issue_1717_absent_sections_give_none_not_an_error():
    ns = run_pattern(MSFT_PROXY)
    assert list(ns["proxy"].sections) == [
        "pay_versus_performance", "equity_compensation_plan_information",
        "voting_proposals", "stockholder_proposals"]
    assert ns["cda_text"] is None
    assert ns["governance_text"] is None


@pytest.mark.vcr
def test_issue_1717_present_sections_give_text():
    ns = run_pattern(AAPL_PROXY)
    assert len(ns["cda_text"]) == 49_534
    assert len(ns["governance_text"]) == 26_405


@pytest.mark.fast
def test_sections_docstring_guards_the_key():
    doc = inspect.getdoc(ProxyStatement.sections.fget)
    assert ">>> proxy.sections['compensation_discussion_and_analysis'].text()" not in doc
    assert "cda.text()[:40] if cda is not None else None" in doc

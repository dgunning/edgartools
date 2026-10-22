"""Regression tests for the attack-surface audit 2026-10-22.

Bead: edgartools-vbutj
GitHub PR: https://github.com/dgunning/edgartools/pull/1768

Origin: attack-surface audit 2026-10-22 (findings 3, 4, 5, 6 and 9), run
against origin/main 50813f0c.

3. A filer-chosen attachment name (``../x``, ``/abs/x``) chose where
   ``download()`` wrote, and became a zip member name verbatim.
4. Two regexes over filer-supplied text were super-linear: the TOC page-number
   stripper took 10.7 s on 33 KB of ". ", and the iXBRL ``durwordsen`` phrase
   regex took 9 s on 24 KB of "a ".
5. MCP ``limit`` had no ceiling, so ``edgar_ownership`` would parse 2 * limit
   Form 4 filings and ``edgar_compare`` would load every company in an industry.
6. ``EDGAR_RATE_LIMIT_PER_SEC`` <= 0 failed with a bare AssertionError, and
   under ``python -O`` (asserts stripped) disabled throttling: 30 requests in
   0.00 s.
9. Turning off certificate verification was silent.

All tests are offline.
"""

import asyncio
import re
import time
import warnings
import zipfile
from collections import defaultdict
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from edgar.attachments import Attachment, Attachments, safe_attachment_filename
from edgar.exceptions import ValidationError
from edgar.sgml.sgml_common import FilingSGML
from edgar.sgml.sgml_parser import SGMLDocument

# ---------------------------------------------------------------------------
# 3. Attachment names cannot leave the download directory
# ---------------------------------------------------------------------------

def _sgml_with(*names):
    docs = defaultdict(list)
    for i, name in enumerate(names, start=1):
        raw = f"<TEXT>\ncontent of {i}\n</TEXT>"
        docs[str(i)].append(SGMLDocument.from_parsed_data(
            dict(type="EX-99", sequence=str(i), filename=name, description="", content=raw)))
    return FilingSGML(header=None, documents=docs)


def _files_under(root: Path):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def test_sgml_download_keeps_traversal_names_inside_target(tmp_path):
    target = tmp_path / "out"
    target.mkdir()
    absolute = str(tmp_path / "abs_escape.txt")
    _sgml_with("../escaped.txt", absolute, "aapl-20240928.htm").download(target)

    assert not (tmp_path / "escaped.txt").exists()
    assert not Path(absolute).exists()
    assert _files_under(tmp_path) == ["out/aapl-20240928.htm", "out/abs_escape.txt", "out/escaped.txt"]
    # An ordinary name saves exactly as before, with its content.
    assert (target / "aapl-20240928.htm").read_text() == "content of 3"


def test_sgml_zip_member_names_are_bare(tmp_path):
    archive = tmp_path / "filing.zip"
    _sgml_with("../../etc/x.txt", "sub\\dir\\y.txt", "ex-21.htm").download(archive, archive=True)
    assert sorted(zipfile.ZipFile(archive).namelist()) == ["ex-21.htm", "x.txt", "y.txt"]


def _attachment(name):
    att = Attachment(sequence_number="1", description="", document=name, ixbrl=False,
                     path=f"/Archives/edgar/data/1/{name}", document_type="EX-99", size=None)
    att._content_override = "payload"
    return att


def test_single_attachment_download_stays_inside_directory(tmp_path):
    target = tmp_path / "out"
    target.mkdir()
    saved = _attachment("../escaped.htm").download(target)
    assert Path(saved) == target / "escaped.htm"
    assert not (tmp_path / "escaped.htm").exists()
    assert (target / "escaped.htm").read_text() == "payload"


def test_attachments_download_without_sgml_stays_inside_directory(tmp_path):
    target = tmp_path / "out"
    target.mkdir()
    attachments = Attachments(document_files=[_attachment("../a.htm"), _attachment("b.htm")],
                              data_files=[], primary_documents=[])
    with patch.object(Attachments, "_download_all_attachments",
                      AsyncMock(return_value=["A", b"B"])):
        attachments.download(target)
        attachments.download(tmp_path / "all.zip", archive=True)
    assert _files_under(tmp_path) == ["all.zip", "out/a.htm", "out/b.htm"]
    assert sorted(zipfile.ZipFile(tmp_path / "all.zip").namelist()) == ["a.htm", "b.htm"]


@pytest.mark.parametrize("name", ["..", ".", "", "dir/", "../.."])
def test_unusable_attachment_name_raises(name):
    with pytest.raises(ValidationError, match="not a usable file name"):
        safe_attachment_filename(name)


def test_ordinary_attachment_names_unchanged():
    for name in ("aapl-20240928.htm", "R1.htm", "Financial_Report.xlsx", "ex-99 1.htm"):
        assert safe_attachment_filename(name) == name


# ---------------------------------------------------------------------------
# 4. Regex DoS
# ---------------------------------------------------------------------------

_OLD_TOC_PAGE_TAIL = re.compile(r'[\s.…]*\d{0,4}\s*$')


def test_toc_page_tail_is_linear_on_adversarial_input():
    from edgar.documents.utils.toc_analyzer import TOCAnalyzer
    text = ". " * 16500 + "x"          # 33 KB; 10.7 s with the old regex
    start = time.perf_counter()
    assert TOCAnalyzer._strip_toc_page_tail(text) == text
    assert time.perf_counter() - start < 1.0


@pytest.mark.parametrize("text", [
    "Use of Proceeds .... 12", "Risk Factors 7", "Item 1A. Risk Factors", "Business....",
    "Item 7 … 123", "Notes 12345", "PROPOSAL NO. 1", "  ", "", "Dividends 2024\xa0",
    "Exhibits . . . 101", "Legal Proceedings\t\t42 ",
])
def test_toc_page_tail_matches_old_regex(text):
    from edgar.documents.utils.toc_analyzer import TOCAnalyzer
    assert TOCAnalyzer._strip_toc_page_tail(text) == _OLD_TOC_PAGE_TAIL.sub('', text)


def test_durwordsen_refuses_overlong_input_quickly():
    from edgar.documents.strategies.ixbrl_transforms import TransformError, apply_transform
    text = "a " * 12000                 # 24 KB; 9 s of regex matching before the cap
    start = time.perf_counter()
    with pytest.raises(TransformError, match="longer than 200 characters"):
        apply_transform("ixt-sec:durwordsen", text)
    assert time.perf_counter() - start < 1.0


@pytest.mark.parametrize("text, expected", [
    ("five years", "P5Y"), ("three-year", "P3Y"), ("364-day", "P364D"),
    ("two years and six months", "P2Y6M"), ("three years, six months", "P3Y6M"),
])
def test_durwordsen_real_values_unchanged(text, expected):
    from edgar.documents.strategies.ixbrl_transforms import apply_transform
    assert apply_transform("ixt-sec:durwordsen", text) == expected


# ---------------------------------------------------------------------------
# 5. MCP limit ceilings
# ---------------------------------------------------------------------------

def test_ownership_limit_schema_and_clamp():
    from edgar.ai.mcp.tools import ownership
    from edgar.ai.mcp.tools.base import TOOLS
    schema = TOOLS["edgar_ownership"]["schema"]["properties"]["limit"]
    assert (schema["minimum"], schema["maximum"]) == (1, 100)

    with patch.object(ownership, "_get_insider_transactions", AsyncMock(return_value="ok")) as insiders, \
         patch.object(ownership, "_get_fund_holdings", AsyncMock(return_value="ok")) as holdings:
        asyncio.run(ownership.edgar_ownership("AAPL", "insiders", limit=1_000_000))
        asyncio.run(ownership.edgar_ownership("1067983", "fund_portfolio", limit=-5))
        asyncio.run(ownership.edgar_ownership("AAPL", "insiders", limit=20))
    assert [c.args[2] for c in insiders.call_args_list] == [100, 20]
    assert holdings.call_args.args[1] == 1


def test_compare_industry_limit_schema_and_clamp():
    from edgar.ai.mcp.tools import compare
    from edgar.ai.mcp.tools.base import TOOLS
    schema = TOOLS["edgar_compare"]["schema"]["properties"]["limit"]
    assert (schema["minimum"], schema["maximum"]) == (1, 10)

    with patch.object(compare, "_get_industry_companies", AsyncMock(return_value=[])) as industry:
        asyncio.run(compare.edgar_compare(industry="software", limit=1_000_000))
    assert industry.call_args.args == ("software", 10)


# ---------------------------------------------------------------------------
# 6. EDGAR_RATE_LIMIT_PER_SEC must be a positive integer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["-1", "0", "abc", "9.5", ""])
def test_bad_rate_limit_env_raises_useful_error(monkeypatch, value):
    from edgar.httpclient import get_edgar_rate_limit_per_sec
    monkeypatch.setenv("EDGAR_RATE_LIMIT_PER_SEC", value)
    with pytest.raises(ValidationError, match="EDGAR_RATE_LIMIT_PER_SEC must be a whole number"):
        get_edgar_rate_limit_per_sec()


def test_good_rate_limit_env_is_read(monkeypatch):
    from edgar.httpclient import get_edgar_rate_limit_per_sec
    monkeypatch.setenv("EDGAR_RATE_LIMIT_PER_SEC", "5")
    assert get_edgar_rate_limit_per_sec() == 5
    monkeypatch.delenv("EDGAR_RATE_LIMIT_PER_SEC")
    assert get_edgar_rate_limit_per_sec() == 9


def test_rate_limiter_refuses_non_positive_rate():
    # Under python -O pyrate-limiter's own assert vanishes and -1 means unlimited.
    from edgar.httpclient import _create_rate_limiter
    with pytest.raises(ValidationError, match="requests_per_second"):
        _create_rate_limiter(-1)


# ---------------------------------------------------------------------------
# 9. Disabling certificate verification warns
# ---------------------------------------------------------------------------

def test_env_disabled_ssl_verification_warns_once(monkeypatch):
    from edgar import httpclient
    monkeypatch.setattr(httpclient, "_ssl_disabled_warned", False)
    monkeypatch.setenv("EDGAR_VERIFY_SSL", "false")
    monkeypatch.setenv("EDGAR_USE_SYSTEM_CERTS", "false")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        httpclient.get_http_mgr(cache_enabled=False)
        httpclient.get_http_mgr(cache_enabled=False)
    messages = [str(w.message) for w in caught if "verification is disabled" in str(w.message)]
    assert len(messages) == 1


def test_configure_http_disabling_ssl_warns(monkeypatch):
    from edgar import httpclient
    monkeypatch.setattr(httpclient, "_ssl_disabled_warned", False)
    original = httpclient.HTTP_MGR.httpx_params.get("verify", True)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            httpclient.configure_http(verify_ssl=True)
            assert not [w for w in caught if "verification is disabled" in str(w.message)]
            httpclient.configure_http(verify_ssl=False)
        assert [w for w in caught if "verification is disabled" in str(w.message)]
    finally:
        httpclient.HTTP_MGR.httpx_params["verify"] = original

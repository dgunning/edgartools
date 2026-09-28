"""
Tests for the continuation service (edgar.ai.mcp.tools.continuation).

This module is the one place cursor encode/decode, pagination and the
in-process result cache live for MCP tools (Tasks 4-6 wire it into
edgar_fund, edgar_notes and edgar_read). It is pure Python: no network, no
edgar imports beyond base.py's error() helper, so every test here is
@pytest.mark.fast.

Cursors are self-describing (tool, accession, document, query, offset,
fingerprint) because the MCP may run under streamable-http with multiple
processes or restart between calls, so nothing about a cursor can depend on
in-process state persisting.
"""

import base64
import json
import os
import threading

import pytest

from edgar.ai.mcp.tools import continuation
from edgar.ai.mcp.tools.continuation import (
    CURSOR_VERSION,
    MAX_CURSOR_CHARS,
    TEXT_PAGE_CHARS,
    CursorError,
    ResultCache,
    check_fingerprint,
    decode_cursor,
    encode_cursor,
    fingerprint,
    paginate,
    paginate_text,
)


# =============================================================================
# fingerprint
# =============================================================================

@pytest.mark.fast
def test_fingerprint_stable_for_same_input():
    a = fingerprint(["acc-1", "doc-1", "footnote"])
    b = fingerprint(["acc-1", "doc-1", "footnote"])
    assert a == b
    assert len(a) == 12
    # hex chars only
    int(a, 16)


@pytest.mark.fast
def test_fingerprint_sensitive_to_order():
    a = fingerprint(["acc-1", "doc-1"])
    b = fingerprint(["doc-1", "acc-1"])
    assert a != b


@pytest.mark.fast
def test_fingerprint_sensitive_to_content():
    a = fingerprint(["acc-1", "doc-1"])
    b = fingerprint(["acc-1", "doc-2"])
    assert a != b


# =============================================================================
# encode_cursor / decode_cursor - round trip
# =============================================================================

@pytest.mark.fast
def test_round_trip_encode_decode():
    cursor = encode_cursor(
        tool="edgar_notes",
        accession="0001628280-26-050307",
        offset=40,
        fp="abc123def456",
        document="nonaccrual",
        query={"filter": "footnote"},
    )
    payload = decode_cursor(
        cursor,
        tool="edgar_notes",
        accession="0001628280-26-050307",
        document="nonaccrual",
        query={"filter": "footnote"},
    )
    assert payload == {
        "v": CURSOR_VERSION,
        "tool": "edgar_notes",
        "acc": "0001628280-26-050307",
        "doc": "nonaccrual",
        "q": {"filter": "footnote"},
        "off": 40,
        "fp": "abc123def456",
    }


@pytest.mark.fast
def test_round_trip_with_missing_optionals():
    cursor = encode_cursor(
        tool="edgar_read",
        accession="0001628280-26-050307",
        offset=0,
        fp="fp000000000a",
    )
    payload = decode_cursor(
        cursor,
        tool="edgar_read",
        accession="0001628280-26-050307",
    )
    assert payload["doc"] is None
    assert payload["q"] is None


@pytest.mark.fast
def test_cursor_is_urlsafe_base64_without_padding():
    cursor = encode_cursor(
        tool="edgar_read", accession="acc", offset=0, fp="f" * 12
    )
    # urlsafe alphabet only, no '=' padding
    assert "=" not in cursor
    for ch in cursor:
        assert ch.isalnum() or ch in "-_"
    # Decodable back to the exact JSON payload with padding restored.
    padded = cursor + "=" * ((-len(cursor)) % 4)
    raw = base64.urlsafe_b64decode(padded)
    payload = json.loads(raw)
    assert payload["v"] == CURSOR_VERSION
    assert set(payload.keys()) == {"v", "tool", "acc", "doc", "q", "off", "fp"}


@pytest.mark.fast
def test_encode_cursor_keys_sorted_and_compact():
    cursor = encode_cursor(tool="edgar_read", accession="acc", offset=0, fp="f" * 12)
    padded = cursor + "=" * ((-len(cursor)) % 4)
    raw = base64.urlsafe_b64decode(padded).decode("utf-8")
    assert " " not in raw  # compact separators
    # sorted keys: acc, doc, fp, off, q, tool, v
    assert list(json.loads(raw).keys()) == sorted(json.loads(raw).keys())


# =============================================================================
# decode_cursor - error paths
# =============================================================================

@pytest.mark.fast
def test_decode_cursor_oversize_raises_invalid_cursor():
    # encode_cursor itself now refuses to produce an oversize cursor (see the
    # encode_cursor tests below), so decode_cursor's own size check is
    # exercised here against a cursor built by hand, bypassing that guard.
    huge_query = {"x": "y" * (MAX_CURSOR_CHARS * 2)}
    payload = {
        "v": CURSOR_VERSION, "tool": "edgar_read", "acc": "acc",
        "doc": None, "q": huge_query, "off": 0, "fp": "f" * 12,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    cursor = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    assert len(cursor) > MAX_CURSOR_CHARS
    with pytest.raises(CursorError) as exc_info:
        decode_cursor(cursor, tool="edgar_read", accession="acc", query=huge_query)
    assert exc_info.value.error_code == "INVALID_CURSOR"


@pytest.mark.fast
def test_encode_cursor_over_cap_raises_invalid_cursor():
    huge_query = {"x": "y" * (MAX_CURSOR_CHARS * 2)}
    with pytest.raises(CursorError) as exc_info:
        encode_cursor(tool="edgar_notes", accession="acc", offset=0, fp="f" * 12, query=huge_query)
    assert exc_info.value.error_code == "INVALID_CURSOR"
    assert "2,048" in exc_info.value.message or "2048" in exc_info.value.message


@pytest.mark.fast
def test_encode_cursor_at_or_below_cap_round_trips():
    # Build a query whose encoded cursor lands exactly at MAX_CURSOR_CHARS,
    # then one character below it, and confirm both still round-trip through
    # decode_cursor rather than being rejected by the new cap check.
    #
    # Measures length by replicating encode_cursor's own encoding (sorted,
    # compact JSON -> urlsafe base64, padding stripped) without its cap
    # check, since encode_cursor itself now raises above the cap and cannot
    # be used to probe for where the cap lands.
    def cursor_len(pad_len: int) -> int:
        payload = {
            "v": CURSOR_VERSION, "tool": "edgar_notes", "acc": "acc",
            "doc": None, "q": {"x": "y" * pad_len}, "off": 0, "fp": "f" * 12,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return len(base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("="))

    # Binary search for the pad length that lands the cursor exactly at the cap.
    lo, hi = 0, MAX_CURSOR_CHARS
    while cursor_len(hi) < MAX_CURSOR_CHARS:
        hi *= 2
    while lo < hi:
        mid = (lo + hi) // 2
        if cursor_len(mid) < MAX_CURSOR_CHARS:
            lo = mid + 1
        else:
            hi = mid
    at_cap_pad = lo
    assert cursor_len(at_cap_pad) == MAX_CURSOR_CHARS

    query_at_cap = {"x": "y" * at_cap_pad}
    cursor_at_cap = encode_cursor(tool="edgar_notes", accession="acc", offset=0, fp="f" * 12, query=query_at_cap)
    assert len(cursor_at_cap) == MAX_CURSOR_CHARS
    payload = decode_cursor(cursor_at_cap, tool="edgar_notes", accession="acc", query=query_at_cap)
    assert payload["q"] == query_at_cap

    query_below_cap = {"x": "y" * (at_cap_pad - 1)}
    cursor_below_cap = encode_cursor(tool="edgar_notes", accession="acc", offset=0, fp="f" * 12, query=query_below_cap)
    assert len(cursor_below_cap) < MAX_CURSOR_CHARS
    payload = decode_cursor(cursor_below_cap, tool="edgar_notes", accession="acc", query=query_below_cap)
    assert payload["q"] == query_below_cap


@pytest.mark.fast
def test_decode_cursor_tampered_undecodable_raises_invalid_cursor():
    cursor = encode_cursor(tool="edgar_read", accession="acc", offset=0, fp="f" * 12)
    tampered = "!!!not-base64-or-json!!!"
    with pytest.raises(CursorError) as exc_info:
        decode_cursor(tampered, tool="edgar_read", accession="acc")
    assert exc_info.value.error_code == "INVALID_CURSOR"
    assert cursor != tampered  # sanity: didn't accidentally reuse a valid cursor


@pytest.mark.fast
def test_decode_cursor_non_dict_json_raises_invalid_cursor():
    raw = json.dumps([1, 2, 3])
    cursor = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    with pytest.raises(CursorError) as exc_info:
        decode_cursor(cursor, tool="edgar_read", accession="acc")
    assert exc_info.value.error_code == "INVALID_CURSOR"


@pytest.mark.fast
def test_decode_cursor_wrong_version_raises_invalid_cursor():
    payload = {"v": CURSOR_VERSION + 1, "tool": "edgar_read", "acc": "acc", "doc": None, "q": None, "off": 0, "fp": "f" * 12}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    cursor = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    with pytest.raises(CursorError) as exc_info:
        decode_cursor(cursor, tool="edgar_read", accession="acc")
    assert exc_info.value.error_code == "INVALID_CURSOR"


@pytest.mark.fast
@pytest.mark.parametrize("bad_off", [-1, "5", 5.0, True, None])
def test_decode_cursor_invalid_offset_raises_invalid_cursor(bad_off):
    payload = {"v": CURSOR_VERSION, "tool": "edgar_read", "acc": "acc", "doc": None, "q": None, "off": bad_off, "fp": "f" * 12}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    cursor = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    with pytest.raises(CursorError) as exc_info:
        decode_cursor(cursor, tool="edgar_read", accession="acc")
    assert exc_info.value.error_code == "INVALID_CURSOR"


@pytest.mark.fast
def test_decode_cursor_tool_mismatch_raises_cursor_mismatch():
    cursor = encode_cursor(tool="edgar_read", accession="acc", offset=0, fp="f" * 12)
    with pytest.raises(CursorError) as exc_info:
        decode_cursor(cursor, tool="edgar_notes", accession="acc")
    assert exc_info.value.error_code == "CURSOR_MISMATCH"


@pytest.mark.fast
def test_decode_cursor_accession_mismatch_raises_cursor_mismatch():
    cursor = encode_cursor(tool="edgar_read", accession="acc-1", offset=0, fp="f" * 12)
    with pytest.raises(CursorError) as exc_info:
        decode_cursor(cursor, tool="edgar_read", accession="acc-2")
    assert exc_info.value.error_code == "CURSOR_MISMATCH"


@pytest.mark.fast
def test_decode_cursor_document_mismatch_raises_cursor_mismatch():
    cursor = encode_cursor(tool="edgar_read", accession="acc", offset=0, fp="f" * 12, document="doc-1")
    with pytest.raises(CursorError) as exc_info:
        decode_cursor(cursor, tool="edgar_read", accession="acc", document="doc-2")
    assert exc_info.value.error_code == "CURSOR_MISMATCH"


@pytest.mark.fast
def test_decode_cursor_query_mismatch_raises_cursor_mismatch():
    cursor = encode_cursor(tool="edgar_read", accession="acc", offset=0, fp="f" * 12, query={"a": 1})
    with pytest.raises(CursorError) as exc_info:
        decode_cursor(cursor, tool="edgar_read", accession="acc", query={"a": 2})
    assert exc_info.value.error_code == "CURSOR_MISMATCH"


@pytest.mark.fast
def test_decode_cursor_missing_document_equals_none():
    """A cursor's doc/q compared to the current call: missing and None are equal."""
    cursor = encode_cursor(tool="edgar_read", accession="acc", offset=0, fp="f" * 12, document=None)
    payload = decode_cursor(cursor, tool="edgar_read", accession="acc", document=None)
    assert payload["doc"] is None


@pytest.mark.fast
def test_decode_cursor_to_response_has_restart_suggestion():
    cursor = encode_cursor(tool="edgar_read", accession="acc-1", offset=0, fp="f" * 12)
    with pytest.raises(CursorError) as exc_info:
        decode_cursor(cursor, tool="edgar_read", accession="acc-2")
    response = exc_info.value.to_response()
    assert response.success is False
    assert response.error_code == "CURSOR_MISMATCH"
    assert response.suggestions
    assert any("cursor" in s.lower() for s in response.suggestions)


# =============================================================================
# check_fingerprint
# =============================================================================

@pytest.mark.fast
def test_check_fingerprint_matching_is_silent():
    payload = {"fp": "abc123def456"}
    check_fingerprint(payload, "abc123def456")  # no raise


@pytest.mark.fast
def test_check_fingerprint_mismatch_raises_cursor_stale():
    payload = {"fp": "abc123def456"}
    with pytest.raises(CursorError) as exc_info:
        check_fingerprint(payload, "different0000")
    assert exc_info.value.error_code == "CURSOR_STALE"


@pytest.mark.fast
def test_full_stale_cursor_flow():
    """Decodes fine (same tool/acc/doc/q) but the recomputed fingerprint differs."""
    cursor = encode_cursor(tool="edgar_notes", accession="acc", offset=0, fp="original000")
    payload = decode_cursor(cursor, tool="edgar_notes", accession="acc")
    with pytest.raises(CursorError) as exc_info:
        check_fingerprint(payload, "recomputed00")
    assert exc_info.value.error_code == "CURSOR_STALE"


# =============================================================================
# paginate
# =============================================================================

@pytest.mark.fast
def test_paginate_first_page():
    items = list(range(25))
    page, meta = paginate(items, offset=0, limit=10)
    assert page == list(range(10))
    assert meta == {"offset": 0, "returned": 10, "total": 25, "remaining": 15}


@pytest.mark.fast
def test_paginate_middle_page():
    items = list(range(25))
    page, meta = paginate(items, offset=10, limit=10)
    assert page == list(range(10, 20))
    assert meta == {"offset": 10, "returned": 10, "total": 25, "remaining": 5}


@pytest.mark.fast
def test_paginate_last_partial_page():
    items = list(range(25))
    page, meta = paginate(items, offset=20, limit=10)
    assert page == list(range(20, 25))
    assert meta == {"offset": 20, "returned": 5, "total": 25, "remaining": 0}


@pytest.mark.fast
def test_paginate_offset_past_end_is_not_an_error():
    items = list(range(25))
    page, meta = paginate(items, offset=100, limit=10)
    assert page == []
    assert meta == {"offset": 100, "returned": 0, "total": 25, "remaining": 0}


@pytest.mark.fast
def test_paginate_limit_one():
    items = list(range(25))
    page, meta = paginate(items, offset=5, limit=1)
    assert page == [5]
    assert meta == {"offset": 5, "returned": 1, "total": 25, "remaining": 19}


@pytest.mark.fast
def test_paginate_empty_items():
    page, meta = paginate([], offset=0, limit=10)
    assert page == []
    assert meta == {"offset": 0, "returned": 0, "total": 0, "remaining": 0}


# =============================================================================
# paginate_text
# =============================================================================

@pytest.mark.fast
def test_paginate_text_single_page_when_short():
    text = "short text, no pagination needed"
    chunk, meta = paginate_text(text, offset=0, budget=TEXT_PAGE_CHARS)
    assert chunk == text
    assert meta == {
        "offset": 0,
        "returned_chars": len(text),
        "total_chars": len(text),
        "remaining_chars": 0,
        "next_offset": None,
    }


@pytest.mark.fast
def test_paginate_text_reassembly_multi_paragraph():
    paragraphs = [f"Paragraph {i}. " + ("word " * 30) for i in range(40)]
    text = "\n\n".join(paragraphs)
    budget = 500
    assert len(text) > budget * 3  # more than 3 pages

    reassembled = ""
    offset = 0
    pages = 0
    seen_offsets = set()
    while True:
        chunk, meta = paginate_text(text, offset=offset, budget=budget)
        assert len(chunk) <= budget
        assert meta["offset"] == offset
        assert offset not in seen_offsets  # never loops
        seen_offsets.add(offset)
        reassembled += chunk
        pages += 1
        if meta["next_offset"] is None:
            assert meta["remaining_chars"] == 0
            break
        offset = meta["next_offset"]
        assert pages < 10_000  # safety valve against infinite loop bugs

    assert reassembled == text
    assert pages > 3


@pytest.mark.fast
def test_paginate_text_no_newlines_hard_cuts_at_budget():
    text = "x" * 5000
    budget = 1000
    chunk, meta = paginate_text(text, offset=0, budget=budget)
    assert len(chunk) == budget
    assert meta["returned_chars"] == budget
    assert meta["next_offset"] == budget
    assert meta["remaining_chars"] == 5000 - budget

    # Full reassembly still holds with hard cuts.
    reassembled = ""
    offset = 0
    while True:
        chunk, meta = paginate_text(text, offset=offset, budget=budget)
        reassembled += chunk
        if meta["next_offset"] is None:
            break
        offset = meta["next_offset"]
    assert reassembled == text


@pytest.mark.fast
def test_paginate_text_breaks_at_paragraph_boundary_in_last_30_percent():
    # Paragraph boundary sits at position 780 inside a 1000-char budget window,
    # i.e. within the last 30% (>= 700), so the break should land there rather
    # than hard-cutting at 1000.
    before = "a" * 778
    after = "b" * 1000
    text = before + "\n\n" + after
    budget = 1000
    chunk, meta = paginate_text(text, offset=0, budget=budget)
    assert chunk == before + "\n\n"
    assert meta["next_offset"] == len(before) + 2
    assert len(chunk) <= budget


@pytest.mark.fast
def test_paginate_text_ignores_paragraph_boundary_outside_last_30_percent():
    # Paragraph boundary at position 100 of a 1000-char budget window is well
    # outside the last 30% (>= 700), so it must be ignored and the page hard
    # cut at the full budget instead.
    before = "a" * 98
    after = "b" * 2000
    text = before + "\n\n" + after
    budget = 1000
    chunk, meta = paginate_text(text, offset=0, budget=budget)
    assert len(chunk) == budget
    assert "\n\n" in chunk  # the boundary is inside the window, just not used to break


@pytest.mark.fast
def test_paginate_text_offset_past_end_is_not_an_error():
    text = "hello world"
    chunk, meta = paginate_text(text, offset=1000, budget=TEXT_PAGE_CHARS)
    assert chunk == ""
    assert meta == {
        "offset": 1000,
        "returned_chars": 0,
        "total_chars": len(text),
        "remaining_chars": 0,
        "next_offset": None,
    }


@pytest.mark.fast
def test_paginate_text_chunk_never_exceeds_budget():
    text = ("para one\n\n" * 5) + ("x" * 2000)
    budget = 300
    offset = 0
    while True:
        chunk, meta = paginate_text(text, offset=offset, budget=budget)
        assert len(chunk) <= budget
        if meta["next_offset"] is None:
            break
        offset = meta["next_offset"]


# =============================================================================
# ResultCache
# =============================================================================

@pytest.mark.fast
def test_result_cache_get_put_roundtrip():
    cache = ResultCache(max_entries=8)
    cache.put(("k1",), "value1")
    assert cache.get(("k1",)) == "value1"


@pytest.mark.fast
def test_result_cache_miss_returns_none():
    cache = ResultCache(max_entries=8)
    assert cache.get(("missing",)) is None


@pytest.mark.fast
def test_result_cache_lru_eviction_by_count():
    cache = ResultCache(max_entries=2)
    cache.put(("a",), 1)
    cache.put(("b",), 2)
    cache.put(("c",), 3)  # evicts "a" (least recently used)
    assert cache.get(("a",)) is None
    assert cache.get(("b",)) == 2
    assert cache.get(("c",)) == 3
    stats = cache.stats()
    assert stats["evictions"] == 1
    assert stats["entries"] == 2


@pytest.mark.fast
def test_result_cache_get_refreshes_recency():
    cache = ResultCache(max_entries=2)
    cache.put(("a",), 1)
    cache.put(("b",), 2)
    cache.get(("a",))  # "a" is now more recently used than "b"
    cache.put(("c",), 3)  # should evict "b", not "a"
    assert cache.get(("a",)) == 1
    assert cache.get(("b",)) is None
    assert cache.get(("c",)) == 3


@pytest.mark.fast
def test_result_cache_lru_eviction_by_bytes():
    cache = ResultCache(max_entries=100, max_bytes=1000)
    cache.put(("a",), "a" * 10, size_bytes=600)
    cache.put(("b",), "b" * 10, size_bytes=600)  # total 1200 > 1000, evicts "a"
    assert cache.get(("a",)) is None
    assert cache.get(("b",)) == "b" * 10
    stats = cache.stats()
    assert stats["bytes"] <= 1000


@pytest.mark.fast
def test_result_cache_oversize_item_not_cached():
    cache = ResultCache(max_entries=100, max_bytes=1000)
    cache.put(("huge",), "x", size_bytes=5000)
    assert cache.get(("huge",)) is None
    stats = cache.stats()
    assert stats["entries"] == 0


@pytest.mark.fast
def test_result_cache_max_bytes_zero_is_unbounded():
    cache = ResultCache(max_entries=100, max_bytes=0)
    cache.put(("a",), "value", size_bytes=10_000_000)
    assert cache.get(("a",)) == "value"


@pytest.mark.fast
def test_result_cache_stats_tracks_hits_and_misses():
    cache = ResultCache(max_entries=8)
    cache.put(("a",), 1)
    cache.get(("a",))
    cache.get(("missing",))
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1


@pytest.mark.fast
def test_result_cache_thread_safe_concurrent_puts():
    cache = ResultCache(max_entries=1000)
    errors = []

    def worker(n):
        try:
            for i in range(50):
                cache.put((n, i), i)
                cache.get((n, i))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors


# =============================================================================
# Module singletons / env fallback
# =============================================================================

@pytest.mark.fast
def test_results_cache_and_text_cache_singletons_exist():
    assert isinstance(continuation.results_cache, ResultCache)
    assert isinstance(continuation.text_cache, ResultCache)


@pytest.mark.fast
def test_env_int_falls_back_to_default_on_invalid_value(monkeypatch, caplog):
    monkeypatch.setenv("EDGAR_MCP_CACHE_MAX_RESULTS", "not-a-number")
    with caplog.at_level("WARNING"):
        value = continuation._env_int("EDGAR_MCP_CACHE_MAX_RESULTS", 8)
    assert value == 8
    assert any("EDGAR_MCP_CACHE_MAX_RESULTS" in r.message for r in caplog.records)


@pytest.mark.fast
def test_env_int_falls_back_to_default_on_negative_value(monkeypatch, caplog):
    monkeypatch.setenv("EDGAR_MCP_CACHE_MAX_RESULTS", "-3")
    with caplog.at_level("WARNING"):
        value = continuation._env_int("EDGAR_MCP_CACHE_MAX_RESULTS", 8)
    assert value == 8


@pytest.mark.fast
def test_env_int_uses_valid_value(monkeypatch):
    monkeypatch.setenv("EDGAR_MCP_CACHE_MAX_RESULTS", "16")
    value = continuation._env_int("EDGAR_MCP_CACHE_MAX_RESULTS", 8)
    assert value == 16


@pytest.mark.fast
def test_env_int_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv("EDGAR_MCP_CACHE_MAX_RESULTS", raising=False)
    value = continuation._env_int("EDGAR_MCP_CACHE_MAX_RESULTS", 8)
    assert value == 8

"""Character offsets returned by the filing text grep helper."""

import pytest

import edgar.search.grep as grep_module
from edgar.search.grep import GrepMatch, _grep_text


@pytest.mark.fast
def test_literal_match_reports_source_character_offset():
    matches = _grep_text("ABC covenant XYZ", "covenant", "primary")

    assert matches[0].char_offset == 4


@pytest.mark.fast
def test_literal_match_slicing_uses_original_unicode_source_indexes():
    matches = _grep_text("İst", "st", "EX-10.1")

    assert matches[0].char_offset == 1
    assert matches[0].match == "st"
    assert "İst" in matches[0].context


@pytest.mark.fast
def test_long_text_uses_sparse_lowercase_expansion_boundaries():
    prefix_len = 100_000
    text = "A" * prefix_len + "İ" + "B" * 100_000
    matches = _grep_text(text, "İB", "EX-10.1")

    assert matches[0].char_offset == prefix_len
    assert matches[0].match == "İB"
    assert text[prefix_len - 100:prefix_len + 102] in matches[0].context

    build_boundaries = getattr(grep_module, "_lowercase_expansion_boundaries", None)
    assert callable(build_boundaries), "lowercase index map must store sparse expansion boundaries"
    boundaries = build_boundaries(text)
    assert len(boundaries) == 1
    assert boundaries[0][:3] == (prefix_len, prefix_len + 2, prefix_len)

    source_index = getattr(grep_module, "_lowered_index_to_source_index", None)
    assert callable(source_index), "lowered indexes must map through expansion boundaries"
    assert source_index(prefix_len, boundaries) == prefix_len
    assert source_index(prefix_len + 1, boundaries) == prefix_len
    assert source_index(prefix_len + 2, boundaries) == prefix_len + 1

    bounded = _grep_text(text, "İB", "EX-10.1", max_match_chars=1)
    assert len(bounded) == 1
    assert bounded[0].overflowed is True
    assert bounded[0].char_offset == prefix_len


@pytest.mark.fast
def test_regex_match_reports_source_character_offset_across_newlines():
    matches = _grep_text(
        "A\nCOVENANT; later", "COVENANT", "primary", regex=True
    )

    assert matches[0].char_offset == 2


@pytest.mark.fast
def test_legacy_grep_match_construction_defaults_offset_to_none():
    match = GrepMatch("primary", "covenant", "covenant context")

    assert match.char_offset is None


@pytest.mark.fast
def test_bounded_grep_stops_after_one_overflow_sentinel():
    matches = _grep_text(
        "x" * 100_000,
        r"(?s).",
        "EX-10.1",
        regex=True,
        max_matches=10,
        max_match_chars=2_048,
    )

    assert len(matches) == 11
    assert all(match.match == "x" for match in matches[:-1])
    assert matches[-1].overflowed is True
    assert matches[-1].match == ""


@pytest.mark.fast
def test_bounded_grep_rejects_long_regex_span_before_materializing_match():
    matches = _grep_text(
        "x" * 10_000,
        r"(?s).*",
        "EX-10.1",
        regex=True,
        max_matches=10,
        max_match_chars=2_048,
    )

    assert len(matches) == 1
    assert matches[0].overflowed is True
    assert matches[0].match == ""


@pytest.mark.fast
def test_catastrophic_regex_backtracking_stops_at_timeout():
    with pytest.raises(TimeoutError):
        _grep_text(
            "a" * 50_000 + "!",
            r"(a+)+$",
            "primary",
            regex=True,
            regex_timeout=0.01,
        )


@pytest.mark.fast
def test_timed_regex_preserves_empty_match_iteration_behavior():
    text = "abc"
    pattern = r".*?"

    default_matches = _grep_text(text, pattern, "primary", regex=True)
    timed_matches = _grep_text(
        text, pattern, "primary", regex=True, regex_timeout=0.1
    )

    assert [(match.char_offset, match.match) for match in timed_matches] == [
        (match.char_offset, match.match) for match in default_matches
    ]

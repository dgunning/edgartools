"""
Tests for Table of Contents link filter (edgar.documents.utils.toc_filter).

Pure text processing — no network calls.
"""

from edgar.documents.utils.toc_filter import filter_toc_links, get_toc_link_stats


class TestFilterTocLinks:

    def test_removes_table_of_contents(self):
        text = "Line 1\nTable of Contents\nLine 2"
        result = filter_toc_links(text)
        assert "Table of Contents" not in result
        assert "Line 1" in result
        assert "Line 2" in result

    def test_removes_index_to_financial_statements(self):
        text = "Data\nIndex to Financial Statements\nMore data"
        assert "Index to Financial Statements" not in filter_toc_links(text)

    def test_removes_index_to_exhibits(self):
        text = "Data\nIndex to Exhibits\nMore data"
        assert "Index to Exhibits" not in filter_toc_links(text)

    def test_case_insensitive(self):
        text = "Data\nTABLE OF CONTENTS\nMore"
        assert "TABLE OF CONTENTS" not in filter_toc_links(text)

    def test_keeps_non_matching_lines(self):
        text = "Revenue\nNet Income\nTotal Assets"
        assert filter_toc_links(text) == text

    def test_empty_string(self):
        assert filter_toc_links("") == ""

    def test_none_returns_none(self):
        assert filter_toc_links(None) is None

    def test_partial_match_kept(self):
        text = "See Table of Contents for details"
        # The regex uses ^...$, so partial lines should be kept
        result = filter_toc_links(text)
        assert "Table of Contents" in result

    def test_multiple_toc_lines_removed(self):
        lines = ["Section 1", "Table of Contents", "Section 2",
                 "Table of Contents", "Section 3"]
        result = filter_toc_links("\n".join(lines))
        assert result.count("Table of Contents") == 0
        assert "Section 1" in result
        assert "Section 3" in result


class TestGetTocLinkStats:

    def test_counts_matches(self):
        text = "A\nTable of Contents\nB\nTable of Contents\nC"
        stats = get_toc_link_stats(text)
        assert stats["total_matches"] == 2
        assert stats["patterns"]["Table of Contents"] == 2

    def test_empty_text(self):
        stats = get_toc_link_stats("")
        assert stats["total_matches"] == 0

    def test_none_text(self):
        stats = get_toc_link_stats(None)
        assert stats["total_matches"] == 0

    def test_no_matches(self):
        stats = get_toc_link_stats("Revenue\nNet Income")
        assert stats["total_matches"] == 0

    def test_total_lines_counted(self):
        stats = get_toc_link_stats("A\nB\nC")
        assert stats["total_lines"] == 3

    def test_mixed_patterns(self):
        text = "Table of Contents\nIndex to Financial Statements\nIndex to Exhibits"
        stats = get_toc_link_stats(text)
        assert stats["total_matches"] == 3

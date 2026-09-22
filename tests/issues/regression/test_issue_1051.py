"""
Regression test for Issue #1051: both import-time cache clears fired on every
import because each one's marker file lived inside the directory the other one
shutil.rmtree'd.

edgar/__init__.py runs two "one-time" cache clears at import:
  1. clear_locale_corrupted_cache()  (#457) - marker was _tcache/.locale_fix_457_applied
  2. clear_empty_cached_responses()  (#672) - marker was _tcache/.empty_response_fix_672_applied

The second clear's rmtree deleted the marker the first clear had just written,
so on the next import the first clear fired again (deleting the second's
marker), forever. The HTTP cache was wiped twice on every process start, and a
wipe landing on a concurrent edgar process's in-flight cache write crashed it.

The fix keeps migration markers in <data-dir>/.migrations, OUTSIDE the cache
directory, and runs all migrations as a single pass that clears at most once.
Legacy in-cache markers written by older versions are honored so upgrading
performs at most one final clear.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1051
"""

from unittest.mock import patch

import pytest

from edgar.httpclient import (
    _run_import_time_cache_migrations,
    clear_empty_cached_responses,
    clear_locale_corrupted_cache,
)


@pytest.fixture
def cache_dir(tmp_path):
    d = tmp_path / "_tcache"
    d.mkdir()
    with patch("edgar.httpclient.get_cache_directory", return_value=str(d)):
        yield d


class TestMarkersSurviveBothClears:
    """The core #1051 scenario: the two clears must not delete each other's markers."""

    def test_second_import_does_not_clear_again(self, tmp_path, cache_dir):
        # First "import": both clears run, in the same order as edgar/__init__.py
        clear_locale_corrupted_cache()
        clear_empty_cached_responses()

        # Both markers must be present after the first pass
        migrations_dir = tmp_path / ".migrations"
        assert (migrations_dir / "locale_fix_457").exists()
        assert (migrations_dir / "empty_response_fix_672").exists()

        # Cache content created between "imports" (the reporter's canary)
        canary = cache_dir / "CANARY"
        canary.write_text("cached response")

        # Second "import": neither clear may fire
        assert clear_locale_corrupted_cache() is False
        assert clear_empty_cached_responses() is False
        assert canary.exists(), "cache was wiped on a subsequent import (#1051)"

    def test_single_pass_clears_at_most_once(self, tmp_path, cache_dir):
        (cache_dir / "stale_entry").write_text("stale")

        assert _run_import_time_cache_migrations() is True
        assert not (cache_dir / "stale_entry").exists()

        canary = cache_dir / "CANARY"
        canary.write_text("cached response")

        # Second pass is a no-op
        assert _run_import_time_cache_migrations() is False
        assert canary.exists()


class TestLegacyMarkersHonored:
    """Markers written inside _tcache by older versions count as already applied."""

    def test_legacy_672_marker_prevents_wipe_on_upgrade(self, tmp_path, cache_dir):
        # Steady state under the bug: only the 672 marker survives in _tcache
        (cache_dir / ".empty_response_fix_672_applied").touch()
        canary = cache_dir / "CANARY"
        canary.write_text("cached response")

        # 672 is satisfied by the legacy marker; only 457 is pending, so the
        # upgrade performs exactly one final clear...
        assert _run_import_time_cache_migrations() is True
        migrations_dir = tmp_path / ".migrations"
        assert (migrations_dir / "locale_fix_457").exists()
        assert (migrations_dir / "empty_response_fix_672").exists()

        # ...and never clears again
        canary.write_text("cached response")
        assert _run_import_time_cache_migrations() is False
        assert canary.exists()

    def test_both_legacy_markers_mean_no_wipe_at_all(self, cache_dir):
        (cache_dir / ".locale_fix_457_applied").touch()
        (cache_dir / ".empty_response_fix_672_applied").touch()
        canary = cache_dir / "CANARY"
        canary.write_text("cached response")

        assert _run_import_time_cache_migrations() is False
        assert canary.exists()


class TestReturnValueContract:
    """The public functions keep their documented return semantics."""

    def test_first_call_with_cache_returns_true(self, cache_dir):
        (cache_dir / "entry").write_text("x")
        assert clear_empty_cached_responses() is True

    def test_no_cache_dir_returns_false_and_creates_marker(self, tmp_path):
        cache_dir = tmp_path / "_tcache"  # does not exist
        with patch("edgar.httpclient.get_cache_directory", return_value=str(cache_dir)):
            assert clear_empty_cached_responses() is False
        assert cache_dir.exists()
        assert (tmp_path / ".migrations" / "empty_response_fix_672").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

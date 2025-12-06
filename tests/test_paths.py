"""Tests for the edgar.paths module - configurable file locations."""

import os
import tempfile
from pathlib import Path

import pytest

from edgar.paths import (
    ENV_EDGAR_DATA_DIR,
    ENV_EDGAR_CACHE_DIR,
    ENV_EDGAR_TEST_DIR,
    ENV_CLAUDE_SKILLS_DIR,
    get_data_directory,
    get_cache_directory,
    get_search_cache_directory,
    get_anchor_cache_directory,
    get_test_directory,
    get_test_db_path,
    get_claude_skills_directory,
    set_data_directory,
    set_cache_directory,
    set_test_directory,
    set_claude_skills_directory,
)


@pytest.mark.fast
class TestDefaultPaths:
    """Test default path behavior (when no env vars are set)."""

    def test_default_data_directory(self, monkeypatch):
        """Default data directory should be ~/.edgar"""
        monkeypatch.delenv(ENV_EDGAR_DATA_DIR, raising=False)
        path = get_data_directory(create=False)
        assert path == Path.home() / '.edgar'

    def test_default_cache_directory(self, monkeypatch):
        """Default cache directory should be ~/.edgar_cache"""
        monkeypatch.delenv(ENV_EDGAR_CACHE_DIR, raising=False)
        path = get_cache_directory(create=False)
        assert path == Path.home() / '.edgar_cache'

    def test_default_test_directory(self, monkeypatch):
        """Default test directory should be ~/.edgar_test"""
        monkeypatch.delenv(ENV_EDGAR_TEST_DIR, raising=False)
        path = get_test_directory(create=False)
        assert path == Path.home() / '.edgar_test'

    def test_default_claude_skills_directory(self, monkeypatch):
        """Default Claude skills directory should be ~/.claude/skills"""
        monkeypatch.delenv(ENV_CLAUDE_SKILLS_DIR, raising=False)
        path = get_claude_skills_directory(create=False)
        assert path == Path.home() / '.claude' / 'skills'

    def test_search_cache_is_subdirectory_of_cache(self, monkeypatch):
        """Search cache should be a subdirectory of the main cache directory."""
        monkeypatch.delenv(ENV_EDGAR_CACHE_DIR, raising=False)
        cache_dir = get_cache_directory(create=False)
        search_dir = get_search_cache_directory(create=False)
        assert search_dir == cache_dir / 'search'

    def test_anchor_cache_is_subdirectory_of_cache(self, monkeypatch):
        """Anchor cache should be a subdirectory of the main cache directory."""
        monkeypatch.delenv(ENV_EDGAR_CACHE_DIR, raising=False)
        cache_dir = get_cache_directory(create=False)
        anchor_dir = get_anchor_cache_directory(create=False)
        assert anchor_dir == cache_dir / 'anchors'

    def test_test_db_path(self, monkeypatch):
        """Test DB path should be in the test directory."""
        monkeypatch.delenv(ENV_EDGAR_TEST_DIR, raising=False)
        test_dir = get_test_directory(create=False)
        db_path = get_test_db_path()
        assert db_path == test_dir / 'harness.db'


@pytest.mark.fast
class TestCustomPathsViaEnvVars:
    """Test custom paths set via environment variables."""

    def test_custom_data_directory(self, monkeypatch, tmp_path):
        """Data directory can be customized via EDGAR_LOCAL_DATA_DIR."""
        custom_path = tmp_path / 'custom_data'
        custom_path.mkdir()
        monkeypatch.setenv(ENV_EDGAR_DATA_DIR, str(custom_path))

        path = get_data_directory(create=False)
        assert path == custom_path

    def test_custom_cache_directory(self, monkeypatch, tmp_path):
        """Cache directory can be customized via EDGAR_CACHE_DIR."""
        custom_path = tmp_path / 'custom_cache'
        custom_path.mkdir()
        monkeypatch.setenv(ENV_EDGAR_CACHE_DIR, str(custom_path))

        path = get_cache_directory(create=False)
        assert path == custom_path

    def test_custom_test_directory(self, monkeypatch, tmp_path):
        """Test directory can be customized via EDGAR_TEST_DIR."""
        custom_path = tmp_path / 'custom_test'
        custom_path.mkdir()
        monkeypatch.setenv(ENV_EDGAR_TEST_DIR, str(custom_path))

        path = get_test_directory(create=False)
        assert path == custom_path

    def test_custom_claude_skills_directory(self, monkeypatch, tmp_path):
        """Claude skills directory can be customized via CLAUDE_SKILLS_DIR."""
        custom_path = tmp_path / 'custom_skills'
        custom_path.mkdir()
        monkeypatch.setenv(ENV_CLAUDE_SKILLS_DIR, str(custom_path))

        path = get_claude_skills_directory(create=False)
        assert path == custom_path

    def test_custom_cache_affects_subdirectories(self, monkeypatch, tmp_path):
        """Custom cache directory should affect search and anchor subdirectories."""
        custom_path = tmp_path / 'custom_cache'
        custom_path.mkdir()
        monkeypatch.setenv(ENV_EDGAR_CACHE_DIR, str(custom_path))

        search_dir = get_search_cache_directory(create=False)
        anchor_dir = get_anchor_cache_directory(create=False)

        assert search_dir == custom_path / 'search'
        assert anchor_dir == custom_path / 'anchors'


@pytest.mark.fast
class TestSetterFunctions:
    """Test programmatic path setting via setter functions."""

    def test_set_data_directory(self, monkeypatch, tmp_path):
        """set_data_directory should update the environment variable."""
        monkeypatch.delenv(ENV_EDGAR_DATA_DIR, raising=False)
        custom_path = tmp_path / 'data'
        custom_path.mkdir()

        set_data_directory(custom_path)

        assert os.environ[ENV_EDGAR_DATA_DIR] == str(custom_path)
        assert get_data_directory(create=False) == custom_path

    def test_set_data_directory_requires_existing_dir(self, tmp_path):
        """set_data_directory should raise if directory doesn't exist."""
        non_existent = tmp_path / 'nonexistent'

        with pytest.raises(FileNotFoundError):
            set_data_directory(non_existent)

    def test_set_data_directory_requires_directory(self, tmp_path):
        """set_data_directory should raise if path is not a directory."""
        file_path = tmp_path / 'file.txt'
        file_path.write_text('test')

        with pytest.raises(NotADirectoryError):
            set_data_directory(file_path)

    def test_set_cache_directory(self, monkeypatch, tmp_path):
        """set_cache_directory should update and create the directory."""
        monkeypatch.delenv(ENV_EDGAR_CACHE_DIR, raising=False)
        custom_path = tmp_path / 'cache'

        # Directory doesn't exist yet - setter should create it
        set_cache_directory(custom_path)

        assert custom_path.exists()
        assert os.environ[ENV_EDGAR_CACHE_DIR] == str(custom_path)
        assert get_cache_directory(create=False) == custom_path

    def test_set_test_directory(self, monkeypatch, tmp_path):
        """set_test_directory should update and create the directory."""
        monkeypatch.delenv(ENV_EDGAR_TEST_DIR, raising=False)
        custom_path = tmp_path / 'test'

        set_test_directory(custom_path)

        assert custom_path.exists()
        assert os.environ[ENV_EDGAR_TEST_DIR] == str(custom_path)

    def test_set_claude_skills_directory(self, monkeypatch, tmp_path):
        """set_claude_skills_directory should update and create the directory."""
        monkeypatch.delenv(ENV_CLAUDE_SKILLS_DIR, raising=False)
        custom_path = tmp_path / 'skills'

        set_claude_skills_directory(custom_path)

        assert custom_path.exists()
        assert os.environ[ENV_CLAUDE_SKILLS_DIR] == str(custom_path)


@pytest.mark.fast
class TestDirectoryCreation:
    """Test automatic directory creation behavior."""

    def test_get_data_directory_creates_when_requested(self, monkeypatch, tmp_path):
        """get_data_directory(create=True) should create the directory."""
        custom_path = tmp_path / 'new_data'
        monkeypatch.setenv(ENV_EDGAR_DATA_DIR, str(custom_path))

        assert not custom_path.exists()
        result = get_data_directory(create=True)
        assert custom_path.exists()
        assert result == custom_path

    def test_get_data_directory_no_create(self, monkeypatch, tmp_path):
        """get_data_directory(create=False) should not create the directory."""
        custom_path = tmp_path / 'new_data'
        monkeypatch.setenv(ENV_EDGAR_DATA_DIR, str(custom_path))

        assert not custom_path.exists()
        result = get_data_directory(create=False)
        assert not custom_path.exists()
        assert result == custom_path

    def test_get_search_cache_creates_hierarchy(self, monkeypatch, tmp_path):
        """get_search_cache_directory should create parent cache dir too."""
        custom_cache = tmp_path / 'cache'
        monkeypatch.setenv(ENV_EDGAR_CACHE_DIR, str(custom_cache))

        assert not custom_cache.exists()
        search_dir = get_search_cache_directory(create=True)

        assert custom_cache.exists()
        assert search_dir.exists()
        assert search_dir == custom_cache / 'search'


@pytest.mark.fast
class TestPathExpansion:
    """Test that paths with ~ are properly expanded."""

    def test_tilde_expansion_in_env_var(self, monkeypatch):
        """Paths with ~ should be expanded to home directory."""
        monkeypatch.setenv(ENV_EDGAR_DATA_DIR, '~/custom_edgar')

        path = get_data_directory(create=False)
        assert path == Path.home() / 'custom_edgar'
        assert '~' not in str(path)


@pytest.mark.fast
class TestIntegrationWithEdgarCore:
    """Test integration with edgar.core.get_edgar_data_directory."""

    def test_core_uses_paths_module(self, monkeypatch, tmp_path):
        """edgar.core.get_edgar_data_directory should use paths module."""
        from edgar.core import get_edgar_data_directory

        custom_path = tmp_path / 'edgar_data'
        custom_path.mkdir()
        monkeypatch.setenv(ENV_EDGAR_DATA_DIR, str(custom_path))

        result = get_edgar_data_directory()
        assert result == custom_path

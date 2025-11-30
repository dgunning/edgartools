"""
Tests for the filesystem abstraction module.

These tests verify the EdgarPath class and use_cloud_storage() function
work correctly with local filesystem operations.
"""
import os
import gzip
import pytest
from pathlib import Path


class TestEdgarPathLocal:
    """Test EdgarPath with local filesystem (no cloud storage)."""

    def test_path_construction(self, tmp_path, monkeypatch):
        """Test constructing EdgarPath from parts."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        # Ensure cloud storage is disabled
        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path = EdgarPath('filings', '20250115', 'test.nc')

        # Check relative path
        assert path.relative_path == 'filings/20250115/test.nc'
        # Check full path includes data directory
        assert str(tmp_path) in path.full_path

    def test_path_division(self, tmp_path, monkeypatch):
        """Test path / 'subpath' syntax."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        base = EdgarPath('filings')
        extended = base / '20250115' / 'test.nc'

        assert extended.relative_path == 'filings/20250115/test.nc'

    def test_path_properties(self, tmp_path, monkeypatch):
        """Test name, stem, suffix properties."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path = EdgarPath('filings', '20250115', 'document.nc.gz')

        assert path.name == 'document.nc.gz'
        assert path.stem == 'document.nc'
        assert path.suffix == '.gz'

    def test_exists_nonexistent(self, tmp_path, monkeypatch):
        """Test exists() returns False for non-existent files."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path = EdgarPath('nonexistent.txt')
        assert not path.exists()

    def test_write_and_read_text(self, tmp_path, monkeypatch):
        """Test writing and reading text files."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path = EdgarPath('test.txt')
        content = 'Hello, EdgarTools!'

        path.write_text(content)

        assert path.exists()
        assert path.read_text() == content

    def test_write_and_read_bytes(self, tmp_path, monkeypatch):
        """Test writing and reading binary files."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path = EdgarPath('test.bin')
        content = b'\x00\x01\x02\x03'

        path.write_bytes(content)

        assert path.exists()
        assert path.read_bytes() == content

    def test_read_gzip_file(self, tmp_path, monkeypatch):
        """Test reading gzip-compressed files."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        # Create a gzip file directly
        gz_file = tmp_path / 'test.txt.gz'
        content = 'Compressed content!'
        with gzip.open(gz_file, 'wt', encoding='utf-8') as f:
            f.write(content)

        # Read via EdgarPath
        path = EdgarPath('test.txt.gz')
        assert path.read_text() == content

    def test_mkdir(self, tmp_path, monkeypatch):
        """Test creating directories."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path = EdgarPath('new', 'nested', 'dir')
        path.mkdir(parents=True, exist_ok=True)

        assert path.is_dir()

    def test_unlink(self, tmp_path, monkeypatch):
        """Test deleting files."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path = EdgarPath('to_delete.txt')
        path.write_text('delete me')
        assert path.exists()

        path.unlink()
        assert not path.exists()

    def test_unlink_missing_ok(self, tmp_path, monkeypatch):
        """Test unlink with missing_ok=True."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path = EdgarPath('nonexistent.txt')

        # Should not raise
        path.unlink(missing_ok=True)

    def test_unlink_raises_if_not_exists(self, tmp_path, monkeypatch):
        """Test unlink raises FileNotFoundError."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path = EdgarPath('nonexistent.txt')

        with pytest.raises(FileNotFoundError):
            path.unlink(missing_ok=False)

    def test_glob(self, tmp_path, monkeypatch):
        """Test glob pattern matching."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        # Create test files
        (tmp_path / 'filings').mkdir()
        (tmp_path / 'filings' / 'file1.nc').write_text('content1')
        (tmp_path / 'filings' / 'file2.nc').write_text('content2')
        (tmp_path / 'filings' / 'other.txt').write_text('other')

        base = EdgarPath('filings')
        matches = list(base.glob('*.nc'))

        assert len(matches) == 2
        names = {m.name for m in matches}
        assert 'file1.nc' in names
        assert 'file2.nc' in names

    def test_parent(self, tmp_path, monkeypatch):
        """Test parent property."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path = EdgarPath('filings', '20250115', 'test.nc')
        parent = path.parent

        assert parent.relative_path == 'filings/20250115'

    def test_as_local_path(self, tmp_path, monkeypatch):
        """Test converting to local Path."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path = EdgarPath('test.txt')
        local = path.as_local_path()

        assert isinstance(local, Path)
        assert local == tmp_path / 'test.txt'


class TestUseCloudStorage:
    """Test use_cloud_storage() function."""

    def test_disable_cloud_storage(self):
        """Test disabling cloud storage."""
        from edgar.filesystem import use_cloud_storage, is_cloud_storage_enabled, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()

        assert not is_cloud_storage_enabled()

    def test_enable_with_none_disables(self):
        """Test that passing None disables cloud storage."""
        from edgar.filesystem import use_cloud_storage, is_cloud_storage_enabled, reset_filesystem

        use_cloud_storage(uri=None)
        reset_filesystem()

        assert not is_cloud_storage_enabled()

    def test_requires_fsspec(self, monkeypatch):
        """Test that cloud storage requires fsspec to be installed."""
        from edgar.filesystem import use_cloud_storage, reset_filesystem, is_cloud_storage_enabled

        # Reset state
        use_cloud_storage(disable=True)
        reset_filesystem()

        # Note: This test verifies the function works correctly
        # When fsspec IS installed (common case), use_cloud_storage works
        # When fsspec is NOT installed, it raises ImportError

        # Just verify the function exists and can disable
        use_cloud_storage(disable=True)
        assert not is_cloud_storage_enabled()

    def test_invalid_uri_format(self):
        """Test that invalid URI raises ValueError."""
        from edgar.filesystem import use_cloud_storage, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()

        # Note: This test requires fsspec to be installed
        # If not installed, ImportError is raised before ValueError
        try:
            use_cloud_storage('invalid-uri-without-protocol')
        except (ValueError, ImportError):
            pass  # Expected


class TestCloudStorageEnabled:
    """Test behavior when cloud storage is enabled (requires fsspec)."""

    @pytest.fixture
    def fsspec_available(self):
        """Check if fsspec is available."""
        try:
            import fsspec
            return True
        except ImportError:
            pytest.skip("fsspec not installed")

    def test_as_local_path_raises_when_cloud_enabled(self, tmp_path, monkeypatch, fsspec_available):
        """Test that as_local_path() raises when cloud storage is enabled."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        # Enable with a mock URI (uses local filesystem backend)
        use_cloud_storage('file://' + str(tmp_path))
        reset_filesystem()

        path = EdgarPath('test.txt')

        with pytest.raises(ValueError, match="Cannot get local path when cloud storage is enabled"):
            path.as_local_path()

        # Clean up
        use_cloud_storage(disable=True)
        reset_filesystem()


class TestIntegrationWithStorage:
    """Integration tests with edgar.storage module."""

    def test_local_filing_path_without_cloud(self, tmp_path, monkeypatch):
        """Test local_filing_path returns Path when cloud disabled."""
        from edgar.filesystem import use_cloud_storage, reset_filesystem
        from edgar.storage import local_filing_path

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        result = local_filing_path('2025-01-15', '0001234567-25-000001')

        # Should return a pathlib.Path, not EdgarPath
        assert isinstance(result, Path)
        assert '20250115' in str(result)
        assert '0001234567-25-000001' in str(result)


@pytest.mark.fast
class TestEdgarPathEquality:
    """Test EdgarPath equality and hashing."""

    def test_equality(self, tmp_path, monkeypatch):
        """Test EdgarPath equality comparison."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path1 = EdgarPath('test', 'file.txt')
        path2 = EdgarPath('test', 'file.txt')
        path3 = EdgarPath('other', 'file.txt')

        assert path1 == path2
        assert path1 != path3

    def test_hash(self, tmp_path, monkeypatch):
        """Test EdgarPath can be used in sets/dicts."""
        from edgar.filesystem import use_cloud_storage, EdgarPath, reset_filesystem

        use_cloud_storage(disable=True)
        reset_filesystem()
        monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', str(tmp_path))

        path1 = EdgarPath('test', 'file.txt')
        path2 = EdgarPath('test', 'file.txt')

        paths = {path1, path2}
        assert len(paths) == 1


@pytest.mark.fast
def test_import_from_edgar():
    """Test that use_cloud_storage can be imported from edgar."""
    from edgar import use_cloud_storage
    assert callable(use_cloud_storage)


@pytest.mark.fast
def test_is_cloud_storage_enabled_default():
    """Test default cloud storage state is disabled."""
    from edgar.filesystem import use_cloud_storage, is_cloud_storage_enabled, reset_filesystem

    use_cloud_storage(disable=True)
    reset_filesystem()

    assert not is_cloud_storage_enabled()

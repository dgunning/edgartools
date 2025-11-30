"""
Filesystem abstraction for EdgarTools cloud storage.

This module provides a thin wrapper around fsspec for cloud storage support.
It allows EdgarTools to seamlessly work with local filesystem or cloud storage
(S3, GCS, Azure, R2, MinIO) using a unified interface.

Usage:
    >>> import edgar
    >>> edgar.use_cloud_storage('s3://my-bucket/')
    >>> # Now all file operations use S3

    >>> # Or with custom endpoint (Cloudflare R2, MinIO)
    >>> edgar.use_cloud_storage(
    ...     's3://my-bucket/',
    ...     client_kwargs={'endpoint_url': 'https://ACCOUNT.r2.cloudflarestorage.com'}
    ... )
"""
from __future__ import annotations

import gzip
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Dict, Iterator, Optional, TextIO, Union

if TYPE_CHECKING:
    import fsspec

__all__ = [
    'use_cloud_storage',
    'is_cloud_storage_enabled',
    'get_filesystem',
    'get_storage_root',
    'EdgarPath',
    'reset_filesystem',
]

# Thread lock for configuration changes
_config_lock = threading.Lock()

# Module-level state for cloud storage configuration
_cloud_uri: Optional[str] = None
_client_kwargs: Optional[Dict[str, Any]] = None
_fs: Optional['fsspec.AbstractFileSystem'] = None


def use_cloud_storage(
    uri: Optional[str] = None,
    *,
    client_kwargs: Optional[Dict[str, Any]] = None,
    disable: bool = False
) -> None:
    """
    Configure cloud storage for EdgarTools.

    Once configured, all file operations (reading filings, storing data)
    will use the specified cloud storage instead of local filesystem.

    This function is thread-safe.

    Args:
        uri: Cloud storage URI. Supported formats:
            - AWS S3: 's3://bucket-name/prefix/'
            - Google Cloud Storage: 'gs://bucket-name/prefix/'
            - Azure Blob Storage: 'az://container/prefix/'
            - S3-compatible (R2, MinIO): 's3://bucket/' with endpoint_url in client_kwargs
        client_kwargs: Optional provider-specific configuration:
            - For S3: region_name, aws_access_key_id, aws_secret_access_key
            - For R2/MinIO: endpoint_url, region_name='auto'
            - For GCS: project, token
            - For Azure: account_name, account_key
        disable: If True, disable cloud storage and revert to local filesystem.

    Examples:
        >>> import edgar

        >>> # AWS S3 (uses default credentials from ~/.aws or environment)
        >>> edgar.use_cloud_storage('s3://my-edgar-bucket/')

        >>> # Cloudflare R2
        >>> edgar.use_cloud_storage(
        ...     's3://my-bucket/',
        ...     client_kwargs={
        ...         'endpoint_url': 'https://ACCOUNT_ID.r2.cloudflarestorage.com',
        ...         'region_name': 'auto'
        ...     }
        ... )

        >>> # Google Cloud Storage
        >>> edgar.use_cloud_storage('gs://my-edgar-bucket/')

        >>> # Azure Blob Storage
        >>> edgar.use_cloud_storage('az://my-container/edgar/')

        >>> # MinIO (self-hosted S3)
        >>> edgar.use_cloud_storage(
        ...     's3://edgar-data/',
        ...     client_kwargs={'endpoint_url': 'http://localhost:9000'}
        ... )

        >>> # Disable cloud storage
        >>> edgar.use_cloud_storage(disable=True)

    Raises:
        ImportError: If fsspec or required cloud packages are not installed.
        ValueError: If URI format is invalid.
    """
    global _cloud_uri, _client_kwargs, _fs

    with _config_lock:
        if disable or uri is None:
            _cloud_uri = None
            _client_kwargs = None
            _fs = None
            return

        # Validate and import fsspec
        try:
            import fsspec  # noqa: F401
        except ImportError:
            raise ImportError(
                "Cloud storage requires fsspec. Install with:\n\n"
                "  pip install edgartools[cloud]\n\n"
                "Or for specific providers:\n"
                "  pip install edgartools[s3]     # AWS S3, R2, MinIO\n"
                "  pip install edgartools[gcs]    # Google Cloud Storage\n"
                "  pip install edgartools[azure]  # Azure Blob Storage\n"
            )

        # Validate URI format
        if '://' not in uri:
            raise ValueError(
                f"Invalid cloud URI: {uri}\n"
                "Expected format: protocol://bucket/prefix (e.g., 's3://my-bucket/')"
            )

        protocol = uri.split('://')[0]
        _validate_backend(protocol)

        # Normalize URI to always end with /
        _cloud_uri = uri.rstrip('/') + '/'
        _client_kwargs = client_kwargs or {}
        _fs = None  # Reset filesystem for lazy initialization

        # Enable local storage mode since we're using our own storage
        os.environ['EDGAR_USE_LOCAL_DATA'] = '1'


def _validate_backend(protocol: str) -> None:
    """
    Validate that required cloud packages are installed for the given protocol.

    Args:
        protocol: Storage protocol (s3, gs, gcs, az, abfs)

    Raises:
        ImportError: If required package is not installed
    """
    packages = {
        's3': 's3fs',
        'gs': 'gcsfs',
        'gcs': 'gcsfs',
        'az': 'adlfs',
        'abfs': 'adlfs',
    }

    if protocol in packages:
        package = packages[protocol]
        try:
            __import__(package)
        except ImportError:
            raise ImportError(
                f"Protocol '{protocol}' requires {package}. "
                f"Install with: pip install {package}"
            )


def is_cloud_storage_enabled() -> bool:
    """
    Check if cloud storage is currently configured.

    Returns:
        True if cloud storage is enabled, False otherwise.
    """
    return _cloud_uri is not None


def get_filesystem() -> 'fsspec.AbstractFileSystem':
    """
    Get the configured fsspec filesystem instance.

    Returns a filesystem appropriate for the current storage configuration:
    - If cloud storage is enabled, returns cloud filesystem (S3, GCS, etc.)
    - If cloud storage is disabled, returns None (use pathlib directly)

    Returns:
        fsspec.AbstractFileSystem or None: The configured filesystem,
        or None if using local storage without fsspec.

    Raises:
        ImportError: If fsspec is not installed but cloud storage is enabled.
    """
    global _fs

    # Fast path: already initialized
    if _fs is not None:
        return _fs

    with _config_lock:
        # Double-check after acquiring lock
        if _fs is not None:
            return _fs

        if _cloud_uri is None:
            # For local storage, we can use pathlib directly without fsspec
            # Return None to signal using pathlib operations
            return None

        # Cloud storage requires fsspec
        import fsspec
        protocol = _cloud_uri.split('://')[0]
        _fs = fsspec.filesystem(protocol, **(_client_kwargs or {}))

        return _fs


def get_storage_root() -> str:
    """
    Get the root path/URI for storage.

    Returns:
        str: Cloud URI if cloud storage is enabled,
             otherwise local edgar data directory path.
    """
    if _cloud_uri:
        return _cloud_uri
    from edgar.core import get_edgar_data_directory
    return str(get_edgar_data_directory())


def reset_filesystem() -> None:
    """
    Reset the filesystem cache.

    Forces re-initialization of the filesystem on next access.
    Useful for testing or when credentials change.

    This function is thread-safe.
    """
    global _fs
    with _config_lock:
        _fs = None


class EdgarPath:
    """
    Path-like object that works with both local and cloud storage.

    Provides a subset of pathlib.Path interface that works transparently
    with local filesystem or cloud storage via fsspec.

    This class is used internally by EdgarTools when cloud storage is enabled,
    but can also be used directly for custom storage operations.

    Examples:
        >>> from edgar.filesystem import EdgarPath, use_cloud_storage

        >>> # Local storage
        >>> use_cloud_storage(disable=True)
        >>> path = EdgarPath('filings', '20250115', 'filing.nc')
        >>> path.exists()
        False

        >>> # Cloud storage
        >>> use_cloud_storage('s3://my-bucket/')
        >>> path = EdgarPath('filings', '20250115', 'filing.nc')
        >>> str(path)
        's3://my-bucket/filings/20250115/filing.nc'
    """

    def __init__(self, *parts: Union[str, Path, 'EdgarPath']):
        """
        Initialize an EdgarPath.

        Args:
            *parts: Path components to join. Can be strings, Path objects,
                    or other EdgarPath instances.
        """
        normalized = []
        for part in parts:
            if isinstance(part, EdgarPath):
                normalized.append(part._path)
            else:
                # Normalize path separators
                normalized.append(str(part).replace('\\', '/'))

        # Join parts, stripping leading/trailing slashes from each
        self._path = '/'.join(p.strip('/') for p in normalized if p)

    def __truediv__(self, other: Union[str, Path, 'EdgarPath']) -> 'EdgarPath':
        """Support path / 'subpath' syntax."""
        return EdgarPath(self._path, str(other))

    def __str__(self) -> str:
        """Return the full path including storage root."""
        return self.full_path

    def __repr__(self) -> str:
        return f"EdgarPath('{self._path}')"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EdgarPath):
            return self._path == other._path
        return False

    def __hash__(self) -> int:
        return hash(self._path)

    @property
    def full_path(self) -> str:
        """
        Get the full path including storage root.

        Returns cloud URI or local absolute path depending on configuration.
        """
        root = get_storage_root()
        if root.endswith('/'):
            return f"{root}{self._path}"
        return f"{root}/{self._path}"

    @property
    def relative_path(self) -> str:
        """Get the relative path (without storage root)."""
        return self._path

    @property
    def name(self) -> str:
        """The final component of the path."""
        return self._path.rsplit('/', 1)[-1] if '/' in self._path else self._path

    @property
    def stem(self) -> str:
        """The final component without its suffix."""
        name = self.name
        return name.rsplit('.', 1)[0] if '.' in name else name

    @property
    def suffix(self) -> str:
        """The file extension of the final component."""
        name = self.name
        if '.' in name:
            return '.' + name.rsplit('.', 1)[1]
        return ''

    @property
    def parent(self) -> 'EdgarPath':
        """The logical parent of this path."""
        if '/' in self._path:
            return EdgarPath(self._path.rsplit('/', 1)[0])
        return EdgarPath('')

    def _local_path(self) -> Path:
        """Get the local Path for this EdgarPath (internal use)."""
        from edgar.core import get_edgar_data_directory
        return get_edgar_data_directory() / self._path

    def exists(self) -> bool:
        """Check if this path exists."""
        fs = get_filesystem()
        if fs is None:
            return self._local_path().exists()
        return fs.exists(self.full_path)

    def is_file(self) -> bool:
        """Check if this path is a file."""
        fs = get_filesystem()
        if fs is None:
            return self._local_path().is_file()
        return fs.isfile(self.full_path)

    def is_dir(self) -> bool:
        """Check if this path is a directory."""
        fs = get_filesystem()
        if fs is None:
            return self._local_path().is_dir()
        return fs.isdir(self.full_path)

    def mkdir(self, parents: bool = False, exist_ok: bool = False) -> None:
        """
        Create a directory at this path.

        Args:
            parents: If True, create parent directories as needed.
            exist_ok: If True, don't raise error if directory exists.
        """
        fs = get_filesystem()
        if fs is None:
            self._local_path().mkdir(parents=parents, exist_ok=exist_ok)
        else:
            fs.makedirs(self.full_path, exist_ok=exist_ok)

    def read_text(self, encoding: str = 'utf-8') -> str:
        """
        Read the file contents as text.

        Automatically handles gzip-compressed files based on .gz extension.

        Args:
            encoding: Text encoding to use.

        Returns:
            File contents as string.
        """
        fs = get_filesystem()
        path = self.full_path

        if fs is None:
            # Local filesystem
            local_path = self._local_path()
            if str(local_path).endswith('.gz'):
                with gzip.open(local_path, 'rt', encoding=encoding, errors='replace') as f:
                    return f.read()
            return local_path.read_text(encoding=encoding)

        # Cloud filesystem
        if path.endswith('.gz'):
            with fs.open(path, 'rb') as f:
                return gzip.decompress(f.read()).decode(encoding, errors='replace')

        with fs.open(path, 'r', encoding=encoding) as f:
            return f.read()

    def read_bytes(self) -> bytes:
        """
        Read the file contents as bytes.

        Automatically decompresses gzip files based on .gz extension.

        Returns:
            File contents as bytes.
        """
        fs = get_filesystem()
        path = self.full_path

        if fs is None:
            # Local filesystem
            local_path = self._local_path()
            if str(local_path).endswith('.gz'):
                with gzip.open(local_path, 'rb') as f:
                    return f.read()
            return local_path.read_bytes()

        # Cloud filesystem
        if path.endswith('.gz'):
            with fs.open(path, 'rb') as f:
                return gzip.decompress(f.read())

        with fs.open(path, 'rb') as f:
            return f.read()

    def write_text(self, data: str, encoding: str = 'utf-8') -> int:
        """
        Write text to the file.

        Args:
            data: Text content to write.
            encoding: Text encoding to use.

        Returns:
            Number of characters written.
        """
        fs = get_filesystem()
        if fs is None:
            # Local filesystem
            local_path = self._local_path()
            local_path.parent.mkdir(parents=True, exist_ok=True)
            return local_path.write_text(data, encoding=encoding)

        with fs.open(self.full_path, 'w', encoding=encoding) as f:
            return f.write(data)

    def write_bytes(self, data: bytes) -> int:
        """
        Write bytes to the file.

        Args:
            data: Binary content to write.

        Returns:
            Number of bytes written.
        """
        fs = get_filesystem()
        if fs is None:
            # Local filesystem
            local_path = self._local_path()
            local_path.parent.mkdir(parents=True, exist_ok=True)
            return local_path.write_bytes(data)

        with fs.open(self.full_path, 'wb') as f:
            return f.write(data)

    def open(self, mode: str = 'r', **kwargs) -> Union[BinaryIO, TextIO]:
        """
        Open the file and return a file-like object.

        Args:
            mode: File open mode ('r', 'rb', 'w', 'wb', etc.)
            **kwargs: Additional arguments passed to fsspec.open()

        Returns:
            File-like object.
        """
        fs = get_filesystem()
        if fs is None:
            # Local filesystem
            return self._local_path().open(mode, **kwargs)

        return fs.open(self.full_path, mode, **kwargs)

    def glob(self, pattern: str) -> Iterator['EdgarPath']:
        """
        Glob for files matching pattern relative to this path.

        Args:
            pattern: Glob pattern (e.g., '*.nc', '**/*.gz')

        Yields:
            EdgarPath objects for matching files.
        """
        fs = get_filesystem()

        if fs is None:
            # Local filesystem
            from edgar.core import get_edgar_data_directory
            local_base = self._local_path()
            data_dir = get_edgar_data_directory()
            for match in local_base.glob(pattern):
                try:
                    rel_path = match.relative_to(data_dir)
                    yield EdgarPath(str(rel_path))
                except ValueError:
                    yield EdgarPath(str(match))
            return

        # Cloud filesystem
        root = get_storage_root()
        full_pattern = f"{self.full_path}/{pattern}"

        for match in fs.glob(full_pattern):
            # Remove protocol prefix for relative path
            if '://' in match:
                # Cloud path: s3://bucket/path -> path
                _, path_part = match.split('://', 1)
                # Remove bucket name for S3-like paths
                if '/' in path_part:
                    _, rel_path = path_part.split('/', 1)
                else:
                    rel_path = ''
            else:
                # Local path: remove root
                rel_path = match.replace(root, '').lstrip('/')

            yield EdgarPath(rel_path)

    def iterdir(self) -> Iterator['EdgarPath']:
        """
        Iterate over the contents of this directory.

        Yields:
            EdgarPath objects for each item in the directory.
        """
        fs = get_filesystem()

        if fs is None:
            # Local filesystem
            from edgar.core import get_edgar_data_directory
            local_path = self._local_path()
            data_dir = get_edgar_data_directory()
            for item in local_path.iterdir():
                try:
                    rel_path = item.relative_to(data_dir)
                    yield EdgarPath(str(rel_path))
                except ValueError:
                    yield EdgarPath(str(item))
            return

        # Cloud filesystem
        root = get_storage_root()

        for item in fs.ls(self.full_path, detail=False):
            # Normalize to relative path
            if '://' in item:
                _, path_part = item.split('://', 1)
                if '/' in path_part:
                    _, rel_path = path_part.split('/', 1)
                else:
                    rel_path = ''
            else:
                rel_path = item.replace(root, '').lstrip('/')

            yield EdgarPath(rel_path)

    def unlink(self, missing_ok: bool = False) -> None:
        """
        Remove this file.

        Args:
            missing_ok: If True, don't raise error if file doesn't exist.

        Raises:
            FileNotFoundError: If file doesn't exist and missing_ok is False.
        """
        fs = get_filesystem()

        if fs is None:
            # Local filesystem
            local_path = self._local_path()
            if not local_path.exists():
                if missing_ok:
                    return
                raise FileNotFoundError(f"No such file: {self.full_path}")
            local_path.unlink()
            return

        # Cloud filesystem
        if not self.exists():
            if missing_ok:
                return
            raise FileNotFoundError(f"No such file: {self.full_path}")
        fs.rm(self.full_path)

    def rmdir(self) -> None:
        """Remove this directory (must be empty)."""
        fs = get_filesystem()
        if fs is None:
            # Local filesystem
            self._local_path().rmdir()
            return

        fs.rmdir(self.full_path)

    def as_local_path(self) -> Path:
        """
        Get this path as a local pathlib.Path.

        Only works when cloud storage is disabled.

        Returns:
            pathlib.Path object for local filesystem.

        Raises:
            ValueError: If cloud storage is enabled.
        """
        if is_cloud_storage_enabled():
            raise ValueError(
                "Cannot get local path when cloud storage is enabled. "
                "Use read_text(), read_bytes(), or open() instead."
            )
        from edgar.core import get_edgar_data_directory
        return get_edgar_data_directory() / self._path

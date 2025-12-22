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
import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Dict, Iterator, Optional, TextIO, Union, cast

if TYPE_CHECKING:
    import fsspec

log = logging.getLogger(__name__)

__all__ = [
    'use_cloud_storage',
    'is_cloud_storage_enabled',
    'get_filesystem',
    'get_storage_root',
    'EdgarPath',
    'reset_filesystem',
    'sync_to_cloud',
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
    disable: bool = False,
    verify: bool = True
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
        verify: If True (default), verify the connection by listing the bucket.
            Set to False to skip verification (useful for faster startup).

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
        except ImportError as e:
            raise ImportError(
                "Cloud storage requires fsspec. Install with:\n\n"
                '  pip install "edgartools[cloud]"\n\n'
                "Or for specific providers:\n"
                '  pip install "edgartools[s3]"     # AWS S3, R2, MinIO\n'
                '  pip install "edgartools[gcs]"    # Google Cloud Storage\n'
                '  pip install "edgartools[azure]"  # Azure Blob Storage\n'
            ) from e

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

        log.info("Cloud storage configured: %s", _cloud_uri)

    # Verify connection outside of lock (network call)
    if verify:
        _verify_connection()


def _verify_connection() -> None:
    """
    Verify the cloud storage connection works.

    Tests connectivity by listing the configured bucket/container.
    Raises ConnectionError with a helpful message if it fails.
    """
    try:
        fs = get_filesystem()
        # Extract bucket/container from URI for listing
        # e.g., 's3://bucket/prefix/' -> 'bucket'
        uri_path = _cloud_uri.split('://')[1].rstrip('/')
        bucket = uri_path.split('/')[0] if '/' in uri_path else uri_path

        protocol = _cloud_uri.split('://')[0]
        if protocol == 's3':
            # For S3, list the bucket root
            fs.ls(bucket)
        elif protocol in ('gs', 'gcs'):
            fs.ls(bucket)
        elif protocol in ('az', 'abfs'):
            fs.ls(bucket)
        else:
            # For unknown protocols, try listing the full path
            fs.ls(_cloud_uri.rstrip('/'))

        log.debug("Connection verified successfully")

    except Exception as e:
        error_msg = str(e)

        # Provide helpful error messages for common issues
        if 'NoCredentialsError' in error_msg or 'credentials' in error_msg.lower():
            raise ConnectionError(
                f"Cloud storage authentication failed: {error_msg}\n\n"
                "Check your credentials in client_kwargs or environment variables."
            ) from e
        elif 'NoSuchBucket' in error_msg or 'not found' in error_msg.lower():
            raise ConnectionError(
                f"Bucket/container not found: {error_msg}\n\n"
                "Verify the bucket exists and you have access to it."
            ) from e
        elif 'Connection' in error_msg or 'timeout' in error_msg.lower():
            raise ConnectionError(
                f"Could not connect to cloud storage: {error_msg}\n\n"
                "Check your network connection and endpoint_url."
            ) from e
        else:
            raise ConnectionError(
                f"Cloud storage connection failed: {error_msg}\n\n"
                "Use verify=False to skip connection verification."
            ) from e


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
        except ImportError as e:
            raise ImportError(
                f"Protocol '{protocol}' requires {package}. "
                f"Install with: pip install {package}"
            ) from e


def is_cloud_storage_enabled() -> bool:
    """
    Check if cloud storage is currently configured.

    Returns:
        True if cloud storage is enabled, False otherwise.
    """
    return _cloud_uri is not None


def get_filesystem() -> Optional['fsspec.AbstractFileSystem']:
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

        # Normalize kwargs for the specific backend
        kwargs = dict(_client_kwargs or {})

        if protocol == 's3':
            # s3fs uses 'key' and 'secret', not aws_access_key_id/aws_secret_access_key
            # Also, endpoint_url must be in a nested 'client_kwargs' dict
            s3_client_kwargs = {}

            # Map credential names
            if 'aws_access_key_id' in kwargs:
                kwargs['key'] = kwargs.pop('aws_access_key_id')
            if 'aws_secret_access_key' in kwargs:
                kwargs['secret'] = kwargs.pop('aws_secret_access_key')

            # Move endpoint_url and region_name to client_kwargs
            if 'endpoint_url' in kwargs:
                s3_client_kwargs['endpoint_url'] = kwargs.pop('endpoint_url')
            if 'region_name' in kwargs:
                s3_client_kwargs['region_name'] = kwargs.pop('region_name')

            if s3_client_kwargs:
                kwargs['client_kwargs'] = s3_client_kwargs

        log.debug("Initializing %s filesystem", protocol)
        _fs = fsspec.filesystem(protocol, **kwargs)
        log.debug("Filesystem initialized successfully")

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
            # Local filesystem - Path.open() returns IO[Any]
            return cast(Union[BinaryIO, TextIO], self._local_path().open(mode, **kwargs))

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


def sync_to_cloud(
    source_path: Optional[str] = None,
    *,
    pattern: str = '**/*',
    batch_size: int = 20,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Sync local filing data to configured cloud storage.

    This function uploads files from local storage to cloud storage using
    parallel batch uploads for efficiency. It's useful for populating cloud
    storage with data downloaded via download_filings() or download_edgar_data().

    Args:
        source_path: Local path to sync. Defaults to the Edgar data directory.
            Can be a subdirectory like 'filings' or 'filings/20250115'.
        pattern: Glob pattern for files to sync. Default is '**/*' (all files).
        batch_size: Number of concurrent file transfers. Default is 20.
            Higher values increase throughput but use more connections.
        overwrite: If True, overwrite existing files in cloud. Default is False.
        dry_run: If True, only report what would be uploaded without uploading.

    Returns:
        dict with keys:
            - 'uploaded': Number of files uploaded
            - 'skipped': Number of files skipped (already exist)
            - 'failed': Number of files that failed to upload
            - 'errors': List of error messages for failed uploads

    Raises:
        ValueError: If cloud storage is not configured.
        ImportError: If fsspec is not installed.

    Examples:
        >>> import edgar
        >>> # First configure cloud storage
        >>> edgar.use_cloud_storage('s3://my-bucket/edgar/')

        >>> # Sync all local data to cloud
        >>> result = edgar.sync_to_cloud()
        >>> print(f"Uploaded {result['uploaded']} files")

        >>> # Sync only filings directory
        >>> edgar.sync_to_cloud('filings')

        >>> # Sync specific date
        >>> edgar.sync_to_cloud('filings/20250115')

        >>> # Preview what would be uploaded
        >>> edgar.sync_to_cloud(dry_run=True)
    """
    if not is_cloud_storage_enabled():
        raise ValueError(
            "Cloud storage is not configured. Call use_cloud_storage() first.\n\n"
            "Example:\n"
            "  import edgar\n"
            "  edgar.use_cloud_storage('s3://my-bucket/edgar/')\n"
            "  edgar.sync_to_cloud()"
        )

    from edgar.core import get_edgar_data_directory

    # Determine source directory
    local_base = get_edgar_data_directory()
    if source_path:
        local_base = local_base / source_path

    if not local_base.exists():
        raise ValueError(f"Source path does not exist: {local_base}")

    # Get filesystem and cloud root
    fs = get_filesystem()
    cloud_root = get_storage_root().rstrip('/')

    # Find files to sync
    log.debug("Scanning %s with pattern '%s'", local_base, pattern)
    files_to_upload = []
    for local_file in local_base.glob(pattern):
        if local_file.is_file():
            # Compute relative path from edgar data directory
            try:
                rel_path = local_file.relative_to(get_edgar_data_directory())
            except ValueError:
                rel_path = local_file.relative_to(local_base)

            # Use as_posix() to ensure forward slashes on all platforms (Windows fix)
            cloud_path = f"{cloud_root}/{rel_path.as_posix()}"
            files_to_upload.append((str(local_file), cloud_path))

    log.debug("Found %d files to potentially upload", len(files_to_upload))

    if not files_to_upload:
        return {'uploaded': 0, 'skipped': 0, 'failed': 0, 'errors': []}

    # Filter out existing files if not overwriting
    if not overwrite:
        # Batch check for existing files using fs.ls() instead of per-file fs.exists()
        # This reduces N API calls to ~1 call per unique directory
        existing_files = set()
        directories_checked = set()

        for _, cloud_path in files_to_upload:
            # Get parent directory
            parent_dir = cloud_path.rsplit('/', 1)[0] if '/' in cloud_path else cloud_root
            if parent_dir not in directories_checked:
                directories_checked.add(parent_dir)
                try:
                    # List all files in this directory (single API call per directory)
                    for item in fs.ls(parent_dir, detail=False):
                        existing_files.add(item)
                except FileNotFoundError:
                    # Directory doesn't exist yet - all files are new
                    pass
                except Exception as e:
                    log.debug("Could not list directory %s: %s", parent_dir, e)

        log.debug("Checked %d directories, found %d existing files",
                  len(directories_checked), len(existing_files))

        filtered = []
        for local_path, cloud_path in files_to_upload:
            if cloud_path not in existing_files:
                filtered.append((local_path, cloud_path))
        skipped = len(files_to_upload) - len(filtered)
        files_to_upload = filtered
    else:
        skipped = 0

    if dry_run:
        print(f"Would upload {len(files_to_upload)} files to {cloud_root}")
        for local_path, cloud_path in files_to_upload[:10]:
            print(f"  {local_path} -> {cloud_path}")
        if len(files_to_upload) > 10:
            print(f"  ... and {len(files_to_upload) - 10} more files")
        return {
            'uploaded': 0,
            'skipped': skipped,
            'failed': 0,
            'errors': [],
            'would_upload': len(files_to_upload),
        }

    # Upload files in batches
    uploaded = 0
    failed = 0
    errors = []

    # Use fsspec's put() for batch uploads
    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None

    # Process in batches for progress tracking
    total = len(files_to_upload)
    iterator = range(0, total, batch_size)
    if tqdm:
        iterator = tqdm(iterator, desc="Uploading to cloud", unit="batch")

    for i in iterator:
        batch = files_to_upload[i:i + batch_size]
        local_paths = [p[0] for p in batch]
        cloud_paths = [p[1] for p in batch]

        try:
            # fs.put supports batch uploads with lists
            fs.put(local_paths, cloud_paths)
            uploaded += len(batch)
        except Exception:
            # Fall back to individual uploads on batch failure
            # Skip files that already exist (may have been partially uploaded)
            for local_path, cloud_path in batch:
                try:
                    # Check if file already exists to avoid re-uploading
                    if fs.exists(cloud_path):
                        uploaded += 1  # Count as success since it's there
                    else:
                        fs.put(local_path, cloud_path)
                        uploaded += 1
                except Exception as file_error:
                    failed += 1
                    if len(errors) < 100:  # Limit error messages to prevent memory growth
                        errors.append(f"{local_path}: {file_error}")

    log.info("Sync complete: uploaded=%d, skipped=%d, failed=%d", uploaded, skipped, failed)

    return {
        'uploaded': uploaded,
        'skipped': skipped,
        'failed': failed,
        'errors': errors,
    }

"""
Centralized path configuration for edgartools.

This module provides configurable paths for all file I/O operations. All paths
can be customized via environment variables or programmatically.

Environment Variables:
    EDGAR_LOCAL_DATA_DIR: Root directory for Edgar data (default: ~/.edgar)
    EDGAR_CACHE_DIR: Root directory for caches (default: ~/.edgar_cache)
    EDGAR_TEST_DIR: Root directory for test data (default: ~/.edgar_test)
    CLAUDE_SKILLS_DIR: Directory for Claude skills installation (default: ~/.claude/skills)

Example:
    # Set via environment variables
    import os
    os.environ['EDGAR_LOCAL_DATA_DIR'] = '/data/edgar'
    os.environ['EDGAR_CACHE_DIR'] = '/data/cache'

    # Or set programmatically
    from edgar.paths import set_data_directory, set_cache_directory
    set_data_directory('/data/edgar')
    set_cache_directory('/data/cache')
"""

import os
from pathlib import Path
from typing import Union

__all__ = [
    # Environment variable names
    'ENV_EDGAR_DATA_DIR',
    'ENV_EDGAR_CACHE_DIR',
    'ENV_EDGAR_TEST_DIR',
    'ENV_CLAUDE_SKILLS_DIR',
    # Getter functions
    'get_data_directory',
    'get_cache_directory',
    'get_search_cache_directory',
    'get_anchor_cache_directory',
    'get_test_directory',
    'get_test_db_path',
    'get_claude_skills_directory',
    # Setter functions
    'set_data_directory',
    'set_cache_directory',
    'set_test_directory',
    'set_claude_skills_directory',
]

# Environment variable names
ENV_EDGAR_DATA_DIR = 'EDGAR_LOCAL_DATA_DIR'
ENV_EDGAR_CACHE_DIR = 'EDGAR_CACHE_DIR'
ENV_EDGAR_TEST_DIR = 'EDGAR_TEST_DIR'
ENV_CLAUDE_SKILLS_DIR = 'CLAUDE_SKILLS_DIR'

# Default directory names (relative to home)
DEFAULT_DATA_DIR_NAME = '.edgar'
DEFAULT_CACHE_DIR_NAME = '.edgar_cache'
DEFAULT_TEST_DIR_NAME = '.edgar_test'
DEFAULT_CLAUDE_SKILLS_PATH = '.claude/skills'


def _resolve_path(path: Union[str, Path]) -> Path:
    """Resolve a path, expanding user home directory and making it absolute."""
    return Path(path).expanduser().resolve()


def _get_default_data_directory() -> Path:
    """Get the default data directory path."""
    return Path.home() / DEFAULT_DATA_DIR_NAME


def _get_default_cache_directory() -> Path:
    """Get the default cache directory path."""
    return Path.home() / DEFAULT_CACHE_DIR_NAME


def _get_default_test_directory() -> Path:
    """Get the default test directory path."""
    return Path.home() / DEFAULT_TEST_DIR_NAME


def _get_default_claude_skills_directory() -> Path:
    """Get the default Claude skills directory path."""
    return Path.home() / DEFAULT_CLAUDE_SKILLS_PATH


# ============================================================================
# Data Directory (main Edgar data storage)
# ============================================================================

def get_data_directory(create: bool = True) -> Path:
    """
    Get the Edgar data directory.

    This is the root directory for storing downloaded Edgar data including
    filings, company facts, submissions, and reference data.

    Args:
        create: If True, create the directory if it doesn't exist.

    Returns:
        Path to the Edgar data directory.

    Environment Variable:
        EDGAR_LOCAL_DATA_DIR: Override the default path (~/.edgar)
    """
    env_path = os.getenv(ENV_EDGAR_DATA_DIR)
    if env_path:
        path = _resolve_path(env_path)
    else:
        path = _get_default_data_directory()

    if create:
        path.mkdir(parents=True, exist_ok=True)

    return path


def set_data_directory(path: Union[str, Path]) -> None:
    """
    Set the Edgar data directory.

    This sets the EDGAR_LOCAL_DATA_DIR environment variable. The directory
    must already exist.

    Args:
        path: Path to the directory.

    Raises:
        FileNotFoundError: If the directory does not exist.
        NotADirectoryError: If the path exists but is not a directory.
    """
    resolved = _resolve_path(path)

    if not resolved.exists():
        raise FileNotFoundError(f"Directory does not exist: {resolved}")

    if not resolved.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {resolved}")

    os.environ[ENV_EDGAR_DATA_DIR] = str(resolved)


# ============================================================================
# Cache Directory (search indices, anchor caches, etc.)
# ============================================================================

def get_cache_directory(create: bool = True) -> Path:
    """
    Get the Edgar cache directory.

    This is the root directory for caches including search indices and
    anchor analysis caches.

    Args:
        create: If True, create the directory if it doesn't exist.

    Returns:
        Path to the cache directory.

    Environment Variable:
        EDGAR_CACHE_DIR: Override the default path (~/.edgar_cache)
    """
    env_path = os.getenv(ENV_EDGAR_CACHE_DIR)
    if env_path:
        path = _resolve_path(env_path)
    else:
        path = _get_default_cache_directory()

    if create:
        path.mkdir(parents=True, exist_ok=True)

    return path


def set_cache_directory(path: Union[str, Path]) -> None:
    """
    Set the Edgar cache directory.

    Args:
        path: Path to the directory. Will be created if it doesn't exist.
    """
    resolved = _resolve_path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    os.environ[ENV_EDGAR_CACHE_DIR] = str(resolved)


def get_search_cache_directory(create: bool = True) -> Path:
    """
    Get the search index cache directory.

    Args:
        create: If True, create the directory if it doesn't exist.

    Returns:
        Path to the search cache directory (cache_dir/search).
    """
    path = get_cache_directory(create=False) / 'search'
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def get_anchor_cache_directory(create: bool = True) -> Path:
    """
    Get the anchor analysis cache directory.

    Args:
        create: If True, create the directory if it doesn't exist.

    Returns:
        Path to the anchor cache directory (cache_dir/anchors).
    """
    path = get_cache_directory(create=False) / 'anchors'
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


# ============================================================================
# Test Directory (test harness data)
# ============================================================================

def get_test_directory(create: bool = True) -> Path:
    """
    Get the Edgar test directory.

    This is the root directory for test harness data.

    Args:
        create: If True, create the directory if it doesn't exist.

    Returns:
        Path to the test directory.

    Environment Variable:
        EDGAR_TEST_DIR: Override the default path (~/.edgar_test)
    """
    env_path = os.getenv(ENV_EDGAR_TEST_DIR)
    if env_path:
        path = _resolve_path(env_path)
    else:
        path = _get_default_test_directory()

    if create:
        path.mkdir(parents=True, exist_ok=True)

    return path


def set_test_directory(path: Union[str, Path]) -> None:
    """
    Set the Edgar test directory.

    Args:
        path: Path to the directory. Will be created if it doesn't exist.
    """
    resolved = _resolve_path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    os.environ[ENV_EDGAR_TEST_DIR] = str(resolved)


def get_test_db_path() -> Path:
    """
    Get the path to the test harness database.

    Returns:
        Path to the test harness SQLite database.
    """
    return get_test_directory() / 'harness.db'


# ============================================================================
# Claude Skills Directory
# ============================================================================

def get_claude_skills_directory(create: bool = False) -> Path:
    """
    Get the Claude skills installation directory.

    By default, this follows Anthropic's convention of ~/.claude/skills/.

    Args:
        create: If True, create the directory if it doesn't exist.

    Returns:
        Path to the Claude skills directory.

    Environment Variable:
        CLAUDE_SKILLS_DIR: Override the default path (~/.claude/skills)
    """
    env_path = os.getenv(ENV_CLAUDE_SKILLS_DIR)
    if env_path:
        path = _resolve_path(env_path)
    else:
        path = _get_default_claude_skills_directory()

    if create:
        path.mkdir(parents=True, exist_ok=True)

    return path


def set_claude_skills_directory(path: Union[str, Path]) -> None:
    """
    Set the Claude skills installation directory.

    Args:
        path: Path to the directory. Will be created if it doesn't exist.
    """
    resolved = _resolve_path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    os.environ[ENV_CLAUDE_SKILLS_DIR] = str(resolved)

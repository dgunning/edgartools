"""
Storage Management for EdgarTools

This module provides visibility, analytics, and management capabilities for EdgarTools'
local storage. It helps users understand what data is downloaded locally and provides
tools to optimize and clean up storage.

Functions:
    storage_info() - Get overview of local storage with statistics
    check_filing() - Check if a filing is available locally
    check_filings_batch() - Check multiple filings efficiently
    availability_summary() - Get summary of filing availability
    analyze_storage() - Analyze storage with optimization recommendations
    optimize_storage() - Compress uncompressed files
    cleanup_storage() - Remove old files (dry-run by default)
    clear_cache() - Clear HTTP cache directories (with obsolete cache detection)

Classes:
    StorageInfo - Storage statistics dataclass with Rich display
    StorageAnalysis - Storage analysis with recommendations
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
import time
from edgar.richtools import repr_rich

if TYPE_CHECKING:
    from edgar._filings import Filing

# Cache storage statistics for 60 seconds
_storage_cache: Optional[Tuple['StorageInfo', float]] = None
_CACHE_TTL = 60.0


@dataclass
class StorageAnalysis:
    """Analysis of storage with optimization recommendations"""
    storage_info: 'StorageInfo'
    issues: List[str]
    recommendations: List[str]
    potential_savings_bytes: int

    def __rich__(self):
        """Rich Panel display with analysis and recommendations"""
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        # Create main table
        analysis = Table(show_header=False, box=None, padding=(0, 2))
        analysis.add_column(style="dim")
        analysis.add_column()

        # Storage summary
        total_gb = self.storage_info.total_size_bytes / (1024**3)
        compressed_gb = self.storage_info.total_size_compressed / (1024**3)
        potential_gb = self.potential_savings_bytes / (1024**3)

        analysis.add_row("📊 Current Size:", f"{compressed_gb:.2f} GB")
        analysis.add_row("💾 Total Files:", f"{self.storage_info.file_count:,}")

        if self.potential_savings_bytes > 0:
            analysis.add_row("💰 Potential Savings:", f"{potential_gb:.2f} GB")

        # Issues section
        if self.issues:
            analysis.add_row("", "")  # Spacer
            analysis.add_row("[bold red]⚠️  Issues Found:[/bold red]", "")
            for issue in self.issues:
                analysis.add_row("", f"• {issue}")

        # Recommendations section
        if self.recommendations:
            analysis.add_row("", "")  # Spacer
            analysis.add_row("[bold green]💡 Recommendations:[/bold green]", "")
            for rec in self.recommendations:
                analysis.add_row("", f"• {rec}")

        # All good message
        if not self.issues and not self.recommendations:
            analysis.add_row("", "")
            analysis.add_row("[bold green]✅ Storage is optimized[/bold green]", "")

        return Panel(
            analysis,
            title="[bold]Storage Analysis[/bold]",
            border_style="blue",
            padding=(1, 2)
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


@dataclass
class StorageInfo:
    """Statistics about EdgarTools local storage"""
    total_size_bytes: int
    total_size_compressed: int  # Actual disk usage
    file_count: int
    filing_count: int
    compression_savings_bytes: int
    compression_ratio: float
    by_type: Dict[str, int]  # {'filings': 1247, 'companyfacts': 18839, ...}
    by_form: Dict[str, int]  # {'10-K': 234, '10-Q': 456, ...} (future)
    by_year: Dict[str, int]  # {2025: 45, 2024: 1202, ...}
    last_updated: datetime
    storage_path: Path

    def __rich__(self):
        """Rich Panel display"""
        from rich.panel import Panel
        from rich.table import Table

        # Create statistics table
        stats = Table(show_header=False, box=None, padding=(0, 2))
        stats.add_column(style="dim", justify="right")
        stats.add_column(style="bold")

        # Format sizes
        total_gb = self.total_size_bytes / (1024**3)
        compressed_gb = self.total_size_compressed / (1024**3)
        savings_gb = self.compression_savings_bytes / (1024**3)

        stats.add_row("Total Size:", f"{total_gb:.2f} GB (uncompressed)")
        stats.add_row("Disk Usage:", f"{compressed_gb:.2f} GB (compressed)")
        stats.add_row("Space Saved:", f"{savings_gb:.2f} GB ({self.compression_ratio:.1%})")
        stats.add_row("Total Files:", f"{self.file_count:,}")
        stats.add_row("Filings:", f"{self.filing_count:,}")
        stats.add_row("Location:", str(self.storage_path))

        # Create breakdown by type with descriptive labels
        if self.by_type:
            stats.add_row("", "")  # Spacer

            # Define labels for cache directories
            cache_labels = {
                '_tcache': '_tcache (HTTP cache):',
                '_pcache': '_pcache (obsolete cache):',
                '_cache': '_cache (legacy cache):'
            }

            for data_type, count in sorted(self.by_type.items()):
                # Use descriptive label for cache directories
                label = cache_labels.get(data_type, f"{data_type}:")
                stats.add_row(label, f"{count:,} files")

        return Panel(
            stats,
            title="[bold]EdgarTools Local Storage[/bold]",
            border_style="blue",
            padding=(1, 2)
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

def _scan_storage(force_refresh: bool = False) -> StorageInfo:
    """
    Scan .edgar directory and collect storage statistics.
    Results are cached for 60 seconds unless force_refresh=True.
    """
    global _storage_cache

    # Check cache
    if not force_refresh and _storage_cache is not None:
        info, timestamp = _storage_cache
        if time.time() - timestamp < _CACHE_TTL:
            return info

    from edgar.core import get_edgar_data_directory
    storage_path = get_edgar_data_directory()

    # Initialize counters
    total_size_bytes = 0
    total_size_compressed = 0
    file_count = 0
    filing_count = 0
    by_type = {}
    by_form = {}
    by_year = {}

    # Scan subdirectories
    for subdir in ['filings', 'companyfacts', 'submissions', 'reference', '_cache', '_pcache', '_tcache']:
        subdir_path = storage_path / subdir
        if not subdir_path.exists():
            continue

        type_files = 0

        # Recursively scan files
        for file_path in subdir_path.rglob('*'):
            if not file_path.is_file():
                continue

            file_size = file_path.stat().st_size
            type_files += 1
            file_count += 1
            total_size_compressed += file_size

            # Calculate uncompressed size
            if str(file_path).endswith('.gz'):
                # Estimate: compressed files are typically 70% smaller
                # For accuracy, could decompress header, but that's expensive
                estimated_uncompressed = file_size / 0.3  # Assuming 70% compression
                total_size_bytes += estimated_uncompressed
            else:
                total_size_bytes += file_size

            # Count filings specifically
            if subdir == 'filings' and (file_path.suffix == '.nc' or file_path.name.endswith('.nc.gz')):
                filing_count += 1

                # Extract year from path (filings/YYYYMMDD/*.nc)
                date_dir = file_path.parent.name
                if len(date_dir) == 8 and date_dir.isdigit():
                    year = int(date_dir[:4])
                    by_year[year] = by_year.get(year, 0) + 1

        by_type[subdir] = type_files

    # Calculate compression savings
    compression_savings = total_size_bytes - total_size_compressed
    compression_ratio = compression_savings / total_size_bytes if total_size_bytes > 0 else 0.0

    # Create info object
    info = StorageInfo(
        total_size_bytes=int(total_size_bytes),
        total_size_compressed=int(total_size_compressed),
        file_count=file_count,
        filing_count=filing_count,
        compression_savings_bytes=int(compression_savings),
        compression_ratio=compression_ratio,
        by_type=by_type,
        by_form={},  # Phase 2: parse form types from filenames
        by_year=by_year,
        last_updated=datetime.now(),
        storage_path=storage_path
    )

    # Update cache
    _storage_cache = (info, time.time())

    return info


def storage_info(force_refresh: bool = False) -> StorageInfo:
    """
    Get overview of EdgarTools local storage.

    Returns statistics about total size, file counts, compression ratios,
    and breakdown by data type.

    Args:
        force_refresh: If True, bypass cache and rescan filesystem

    Returns:
        StorageInfo: Storage statistics with Rich display support

    Example:
        >>> from edgar.storage_management import storage_info
        >>> info = storage_info()
        >>> print(info)  # Rich-formatted panel
        >>> print(f"Total size: {info.total_size_bytes / 1e9:.2f} GB")
    """
    return _scan_storage(force_refresh=force_refresh)


def check_filing(filing: 'Filing') -> bool:
    """
    Check if a filing is available in local storage.

    Args:
        filing: Filing object to check

    Returns:
        bool: True if filing exists locally, False otherwise

    Example:
        >>> from edgar import Company
        >>> from edgar.storage_management import check_filing
        >>> filing = Company("AAPL").latest("10-K")
        >>> if check_filing(filing):
        ...     print("Available offline!")
    """
    from edgar.storage import local_filing_path

    local_path = local_filing_path(
        filing_date=str(filing.filing_date),
        accession_number=filing.accession_no
    )

    return local_path.exists()


def check_filings_batch(filings: List['Filing']) -> Dict[str, bool]:
    """
    Efficiently check availability of multiple filings.

    Args:
        filings: List of Filing objects to check

    Returns:
        Dict mapping accession number to availability (True/False)

    Example:
        >>> from edgar import get_filings
        >>> from edgar.storage_management import check_filings_batch
        >>> filings = get_filings(filing_date="2025-01-15").sample(10)
        >>> availability = check_filings_batch(filings)
        >>> available = [f for f in filings if availability[f.accession_no]]
        >>> print(f"{len(available)} of {len(filings)} available offline")
    """
    from edgar.storage import local_filing_path

    availability = {}
    for filing in filings:
        local_path = local_filing_path(
            filing_date=str(filing.filing_date),
            accession_number=filing.accession_no
        )
        availability[filing.accession_no] = local_path.exists()

    return availability


def availability_summary(filings: List['Filing']) -> str:
    """
    Get a summary string of filing availability.

    Args:
        filings: List of Filing objects

    Returns:
        str: Summary like "45 of 100 filings available offline (45%)"

    Example:
        >>> from edgar import get_filings
        >>> from edgar.storage_management import availability_summary
        >>> filings = get_filings(filing_date="2025-01-15").head(100)
        >>> print(availability_summary(filings))
        45 of 100 filings available offline (45%)
    """
    availability = check_filings_batch(filings)
    available_count = sum(availability.values())
    total_count = len(filings)
    percentage = (available_count / total_count * 100) if total_count > 0 else 0

    return f"{available_count} of {total_count} filings available offline ({percentage:.0f}%)"


def analyze_storage(force_refresh: bool = False) -> StorageAnalysis:
    """
    Analyze storage and provide optimization recommendations.

    Scans local storage for potential issues and suggests improvements like:
    - Compressing uncompressed files
    - Cleaning up old cache files
    - Identifying duplicate or orphaned data

    Args:
        force_refresh: If True, bypass cache and rescan filesystem

    Returns:
        StorageAnalysis: Analysis with issues and recommendations

    Example:
        >>> from edgar.storage_management import analyze_storage
        >>> analysis = analyze_storage()
        >>> print(analysis)  # Rich-formatted panel with recommendations
        >>> if analysis.potential_savings_bytes > 1e9:
        ...     print(f"Can save {analysis.potential_savings_bytes / 1e9:.1f} GB")
    """
    from edgar.core import get_edgar_data_directory

    info = storage_info(force_refresh=force_refresh)
    storage_path = get_edgar_data_directory()

    issues = []
    recommendations = []
    potential_savings = 0

    # Check for uncompressed files
    uncompressed_count = 0
    uncompressed_size = 0

    for subdir in ['filings', 'companyfacts', 'submissions']:
        subdir_path = storage_path / subdir
        if not subdir_path.exists():
            continue

        for file_path in subdir_path.rglob('*'):
            if not file_path.is_file():
                continue

            # Check if file should be compressed
            if file_path.suffix in ['.json', '.xml', '.txt', '.nc'] and not str(file_path).endswith('.gz'):
                uncompressed_count += 1
                file_size = file_path.stat().st_size
                uncompressed_size += file_size
                # Estimate 70% compression savings
                potential_savings += int(file_size * 0.7)

    if uncompressed_count > 0:
        issues.append(f"Found {uncompressed_count:,} uncompressed files ({uncompressed_size / 1e9:.2f} GB)")
        recommendations.append(f"Run optimize_storage() to compress files and save ~{potential_savings / 1e9:.1f} GB")

    # Check for obsolete _pcache directory (replaced by _tcache in commit 3bfba7e)
    pcache_path = storage_path / '_pcache'
    pcache_size = 0
    pcache_files = 0
    if pcache_path.exists():
        for file_path in pcache_path.rglob('*'):
            if file_path.is_file():
                pcache_files += 1
                pcache_size += file_path.stat().st_size

        if pcache_files > 0:
            issues.append(f"Obsolete _pcache directory contains {pcache_files:,} files ({pcache_size / 1e9:.2f} GB)")
            recommendations.append(f"Run clear_cache(obsolete_only=True) to remove old cache and free {pcache_size / 1e9:.1f} GB")

    # Check for large cache directories
    cache_size = 0
    cache_files = 0
    for cache_dir in ['_cache', '_tcache']:  # Only check active cache directories
        cache_path = storage_path / cache_dir
        if cache_path.exists():
            for file_path in cache_path.rglob('*'):
                if file_path.is_file():
                    cache_files += 1
                    cache_size += file_path.stat().st_size

    if cache_size > 1e9:  # More than 1 GB
        issues.append(f"Cache directories contain {cache_files:,} files ({cache_size / 1e9:.2f} GB)")
        recommendations.append(f"Run clear_cache() to free up {cache_size / 1e9:.1f} GB")

    # Check for old filings (over 1 year old) - only if many exist
    from datetime import datetime, timedelta
    old_threshold = datetime.now() - timedelta(days=365)
    old_filings = 0
    old_filings_size = 0

    filings_dir = storage_path / 'filings'
    if filings_dir.exists():
        for date_dir in filings_dir.iterdir():
            if not date_dir.is_dir():
                continue

            # Parse date from directory name (YYYYMMDD)
            if len(date_dir.name) == 8 and date_dir.name.isdigit():
                try:
                    dir_date = datetime.strptime(date_dir.name, '%Y%m%d')
                    if dir_date < old_threshold:
                        for file_path in date_dir.rglob('*'):
                            if file_path.is_file():
                                old_filings += 1
                                old_filings_size += file_path.stat().st_size
                except ValueError:
                    continue

    if old_filings > 100:  # Only flag if substantial
        recommendations.append(
            f"Consider cleanup_storage(days=365) to remove {old_filings:,} old filings "
            f"({old_filings_size / 1e9:.1f} GB)"
        )

    # Overall health check
    if not issues:
        recommendations.append("Storage is well-optimized!")

    return StorageAnalysis(
        storage_info=info,
        issues=issues,
        recommendations=recommendations,
        potential_savings_bytes=potential_savings
    )


def optimize_storage(dry_run: bool = True) -> Dict[str, int]:
    """
    Compress uncompressed files to save disk space.

    Compresses .json, .xml, .txt, and .nc files in filings, companyfacts,
    and submissions directories using gzip. Original files are replaced with
    .gz versions.

    Args:
        dry_run: If True, only report what would be done without making changes

    Returns:
        Dict with 'files_compressed', 'bytes_saved', 'errors'

    Example:
        >>> from edgar.storage_management import optimize_storage
        >>> # First see what would happen
        >>> result = optimize_storage(dry_run=True)
        >>> print(f"Would compress {result['files_compressed']} files")
        >>> # Then do it
        >>> result = optimize_storage(dry_run=False)
        >>> print(f"Saved {result['bytes_saved'] / 1e9:.1f} GB")
    """
    import gzip
    import shutil
    from edgar.core import get_edgar_data_directory

    storage_path = get_edgar_data_directory()
    files_compressed = 0
    bytes_saved = 0
    errors = 0

    for subdir in ['filings', 'companyfacts', 'submissions']:
        subdir_path = storage_path / subdir
        if not subdir_path.exists():
            continue

        for file_path in subdir_path.rglob('*'):
            if not file_path.is_file():
                continue

            # Check if file should be compressed
            if file_path.suffix in ['.json', '.xml', '.txt', '.nc'] and not str(file_path).endswith('.gz'):
                try:
                    original_size = file_path.stat().st_size

                    if not dry_run:
                        # Compress file
                        gz_path = Path(str(file_path) + '.gz')
                        with open(file_path, 'rb') as f_in:
                            with gzip.open(gz_path, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)

                        # Verify compressed file exists
                        if gz_path.exists():
                            compressed_size = gz_path.stat().st_size
                            bytes_saved += (original_size - compressed_size)
                            file_path.unlink()  # Remove original
                        else:
                            errors += 1
                            continue
                    else:
                        # Estimate 70% compression
                        bytes_saved += int(original_size * 0.7)

                    files_compressed += 1

                except Exception as e:
                    errors += 1
                    continue

    return {
        'files_compressed': files_compressed,
        'bytes_saved': bytes_saved,
        'errors': errors
    }


def cleanup_storage(days: int = 365, dry_run: bool = True) -> Dict[str, int]:
    """
    Remove old filings from local storage.

    Deletes filing files older than the specified number of days. This helps
    free up space for users who only need recent filings.

    Args:
        days: Remove filings older than this many days (default: 365)
        dry_run: If True, only report what would be deleted without making changes

    Returns:
        Dict with 'files_deleted', 'bytes_freed', 'errors'

    Example:
        >>> from edgar.storage_management import cleanup_storage
        >>> # First see what would be deleted
        >>> result = cleanup_storage(days=365, dry_run=True)
        >>> print(f"Would delete {result['files_deleted']} files")
        >>> # Then do it
        >>> result = cleanup_storage(days=365, dry_run=False)
        >>> print(f"Freed {result['bytes_freed'] / 1e9:.1f} GB")
    """
    from datetime import datetime, timedelta
    from edgar.core import get_edgar_data_directory

    storage_path = get_edgar_data_directory()
    cutoff_date = datetime.now() - timedelta(days=days)

    files_deleted = 0
    bytes_freed = 0
    errors = 0

    filings_dir = storage_path / 'filings'
    if not filings_dir.exists():
        return {'files_deleted': 0, 'bytes_freed': 0, 'errors': 0}

    for date_dir in filings_dir.iterdir():
        if not date_dir.is_dir():
            continue

        # Parse date from directory name (YYYYMMDD)
        if len(date_dir.name) == 8 and date_dir.name.isdigit():
            try:
                dir_date = datetime.strptime(date_dir.name, '%Y%m%d')

                if dir_date < cutoff_date:
                    # Delete all files in this directory
                    for file_path in date_dir.rglob('*'):
                        if file_path.is_file():
                            try:
                                file_size = file_path.stat().st_size
                                bytes_freed += file_size

                                if not dry_run:
                                    file_path.unlink()

                                files_deleted += 1
                            except Exception:
                                errors += 1
                                continue

                    # Remove empty directory
                    if not dry_run:
                        try:
                            # Remove all empty subdirectories
                            for subdir in reversed(list(date_dir.rglob('*'))):
                                if subdir.is_dir() and not list(subdir.iterdir()):
                                    subdir.rmdir()
                            # Remove date directory if empty
                            if not list(date_dir.iterdir()):
                                date_dir.rmdir()
                        except Exception:
                            errors += 1

            except ValueError:
                continue

    return {
        'files_deleted': files_deleted,
        'bytes_freed': bytes_freed,
        'errors': errors
    }


def clear_cache(dry_run: bool = True, obsolete_only: bool = False) -> Dict[str, int]:
    """
    Clear HTTP cache directories to free up space.

    Removes cached HTTP responses from cache directories. By default clears all
    cache directories (_cache, _tcache). Use obsolete_only=True to only remove
    the obsolete _pcache directory (replaced by _tcache in Aug 2025).

    Args:
        dry_run: If True, only report what would be deleted without making changes
        obsolete_only: If True, only clear obsolete _pcache directory

    Returns:
        Dict with 'files_deleted', 'bytes_freed', 'errors'

    Example:
        >>> from edgar.storage_management import clear_cache
        >>> # Clear obsolete cache only
        >>> result = clear_cache(obsolete_only=True, dry_run=False)
        >>> print(f"Freed {result['bytes_freed'] / 1e9:.1f} GB")
        >>> # Clear all caches
        >>> result = clear_cache(dry_run=False)
        >>> print(f"Cleared {result['files_deleted']} cache files")
    """
    from edgar.core import get_edgar_data_directory

    storage_path = get_edgar_data_directory()
    files_deleted = 0
    bytes_freed = 0
    errors = 0

    # Determine which cache directories to clear
    if obsolete_only:
        cache_dirs = ['_pcache']  # Only obsolete cache
    else:
        cache_dirs = ['_cache', '_tcache']  # Active caches only

    for cache_dir_name in cache_dirs:
        cache_dir = storage_path / cache_dir_name
        if not cache_dir.exists():
            continue

        for file_path in cache_dir.rglob('*'):
            if file_path.is_file():
                try:
                    file_size = file_path.stat().st_size
                    bytes_freed += file_size

                    if not dry_run:
                        file_path.unlink()

                    files_deleted += 1
                except Exception:
                    errors += 1
                    continue

        # Remove empty directories
        if not dry_run:
            try:
                for subdir in reversed(list(cache_dir.rglob('*'))):
                    if subdir.is_dir() and not list(subdir.iterdir()):
                        subdir.rmdir()
                # Remove the cache directory itself if empty
                if not list(cache_dir.iterdir()):
                    cache_dir.rmdir()
            except Exception:
                errors += 1

    return {
        'files_deleted': files_deleted,
        'bytes_freed': bytes_freed,
        'errors': errors
    }

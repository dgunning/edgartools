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
    clear_cache() - Clear HTTP cache directories

Classes:
    StorageInfo - Storage statistics dataclass with Rich display
    StorageAnalysis - Storage analysis with recommendations
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
import time

if TYPE_CHECKING:
    from edgar._filings import Filing

# Cache storage statistics for 60 seconds
_storage_cache: Optional[Tuple['StorageInfo', float]] = None
_CACHE_TTL = 60.0


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
        stats.add_column(style="dim")
        stats.add_column(style="bold")

        # Format sizes
        total_gb = self.total_size_bytes / (1024**3)
        compressed_gb = self.total_size_compressed / (1024**3)
        savings_gb = self.compression_savings_bytes / (1024**3)

        stats.add_row("📊 Total Size:", f"{total_gb:.2f} GB (uncompressed)")
        stats.add_row("💾 Disk Usage:", f"{compressed_gb:.2f} GB (compressed)")
        stats.add_row("🗜️ Space Saved:", f"{savings_gb:.2f} GB ({self.compression_ratio:.1%})")
        stats.add_row("📁 Total Files:", f"{self.file_count:,}")
        stats.add_row("📄 Filings:", f"{self.filing_count:,}")
        stats.add_row("📍 Location:", str(self.storage_path))

        # Create breakdown by type
        if self.by_type:
            stats.add_row("", "")  # Spacer
            for data_type, count in sorted(self.by_type.items()):
                stats.add_row(f"  {data_type}:", f"{count:,} files")

        return Panel(
            stats,
            title="[bold]EdgarTools Local Storage[/bold]",
            border_style="blue",
            padding=(1, 2)
        )


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

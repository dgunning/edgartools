"""
Datamule storage provider — configuration and accession index.

Datamule distributes SEC filings as tar archives. Each tar contains one or more
filings with a metadata.json and the raw document files (HTML, XML, etc.).

Usage:
    edgar.use_datamule_storage("/path/to/tars")   # scans tars, builds index
    edgar.use_datamule_storage(disable=True)       # turn it off
"""

import logging
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from edgar.sgml.sgml_common import FilingSGML

log = logging.getLogger(__name__)

__all__ = ['use_datamule_storage', 'is_using_datamule_storage', 'get_datamule_filing']

# Module-level state
_datamule_path: Optional[Path] = None
_accession_index: Dict[str, Path] = {}  # accession_no -> tar_path


def use_datamule_storage(path=None, *, disable=False):
    """
    Configure a datamule tar directory as a filing source.

    Scans the directory for .tar files and builds an accession-number index
    by reading metadata.json from each tar.

    Args:
        path: Directory containing datamule tar files. If None and not disabling,
              raises ValueError.
        disable: If True, disable datamule storage and clear the index.

    Examples:
        >>> use_datamule_storage("/data/datamule/tars")
        >>> use_datamule_storage(disable=True)
    """
    global _datamule_path, _accession_index

    if disable:
        _datamule_path = None
        _accession_index.clear()
        log.info("Datamule storage disabled")
        return

    if path is None:
        raise ValueError("Must provide a path to datamule tar directory, or pass disable=True")

    tar_dir = Path(path).expanduser().resolve()
    if not tar_dir.exists():
        raise FileNotFoundError(f"Datamule directory does not exist: {tar_dir}")
    if not tar_dir.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {tar_dir}")

    _datamule_path = tar_dir
    _accession_index.clear()
    _scan_tars(tar_dir)
    log.info("Datamule storage enabled: %s (%d filings indexed)", tar_dir, len(_accession_index))


def is_using_datamule_storage() -> bool:
    """Return True if datamule storage is configured and active."""
    return _datamule_path is not None


def get_datamule_filing(accession_no: str) -> Optional['FilingSGML']:
    """
    Look up an accession number in the datamule index and load the filing.

    Args:
        accession_no: SEC accession number (e.g. '0001193125-24-012345')

    Returns:
        FilingSGML if found, None otherwise
    """
    tar_path = _accession_index.get(accession_no)
    if tar_path is None:
        return None

    from edgar.storage.datamule.reader import load_filing_from_tar
    return load_filing_from_tar(tar_path, accession_no=accession_no)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scan_tars(tar_dir: Path):
    """Scan all .tar files in the directory and index accession numbers."""
    import json

    tar_files = sorted(tar_dir.glob("*.tar"))
    if not tar_files:
        log.warning("No .tar files found in %s", tar_dir)
        return

    for tar_path in tar_files:
        try:
            _index_tar(tar_path)
        except Exception as e:
            log.warning("Failed to index %s: %s", tar_path.name, e)


def _index_tar(tar_path: Path):
    """
    Read a single tar and map accession numbers to tar_path.

    Handles two layouts:
    - Single-filing tar: metadata.json at the root
    - Batch tar: <accession_no>/metadata.json for each filing
    """
    import json

    with tarfile.open(tar_path, 'r') as tf:
        metadata_members = [m for m in tf.getmembers() if m.name.endswith('metadata.json')]

        for member in metadata_members:
            try:
                f = tf.extractfile(member)
                if f is None:
                    continue
                metadata = json.loads(f.read().decode('utf-8'))
                accession_no = metadata.get('accession-number') or metadata.get('accession_number') or metadata.get('accessionNumber')
                if accession_no:
                    # Normalize to dashed format (0001193125-24-012345)
                    accession_no = _normalize_accession(accession_no)
                    _accession_index[accession_no] = tar_path
            except Exception as e:
                log.debug("Skipping %s in %s: %s", member.name, tar_path.name, e)


def _normalize_accession(accession_no: str) -> str:
    """Normalize accession number to dashed format."""
    accession_no = accession_no.strip()
    # If it's already dashed (0001193125-24-012345), return as-is
    if '-' in accession_no:
        return accession_no
    # Convert undashed 18-digit to dashed
    if len(accession_no) == 18 and accession_no.isdigit():
        return f"{accession_no[:10]}-{accession_no[10:12]}-{accession_no[12:]}"
    return accession_no

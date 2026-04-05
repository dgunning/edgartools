"""
Datamule tar reader.

Reads filing data from datamule-format tar archives and constructs
FilingSGML objects compatible with the rest of EdgarTools.

Tar layout (single filing):
    metadata.json
    primary-document.htm
    R1.htm
    ...

Tar layout (batch):
    0001193125-24-012345/metadata.json
    0001193125-24-012345/primary-document.htm
    0001193125-24-067890/metadata.json
    ...
"""

import json
import logging
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from edgar.sgml.sgml_common import FilingSGML
from edgar.storage.datamule.documents import TarSGMLDocument
from edgar.storage.datamule.metadata import filing_header_from_metadata

log = logging.getLogger(__name__)

__all__ = ['load_filing_from_tar']


def load_filing_from_tar(tar_path: Path, accession_no: Optional[str] = None) -> Optional[FilingSGML]:
    """
    Load a filing from a datamule tar archive.

    Args:
        tar_path: Path to the tar file.
        accession_no: Specific accession number to extract. If None,
            loads the first (or only) filing in the tar.

    Returns:
        FilingSGML or None if the filing could not be loaded.
    """
    tar_path = Path(tar_path)
    if not tar_path.exists():
        log.warning("Tar file not found: %s", tar_path)
        return None

    try:
        with tarfile.open(tar_path, 'r') as tf:
            return _load_from_open_tar(tf, accession_no)
    except (tarfile.TarError, json.JSONDecodeError) as e:
        log.warning("Failed to read tar %s: %s", tar_path.name, e)
        return None


def _load_from_open_tar(tf: tarfile.TarFile, accession_no: Optional[str]) -> Optional[FilingSGML]:
    """Load a filing from an already-opened tar file."""
    members = tf.getmembers()
    if not members:
        return None

    # Determine tar layout: single-filing vs batch
    # Batch tars have metadata.json files in subdirectories
    metadata_members = [m for m in members if m.name.endswith('metadata.json')]

    if not metadata_members:
        log.warning("No metadata.json found in tar")
        return None

    # Find the right metadata member
    target_meta = None
    prefix = ''

    if accession_no:
        # Look for the accession's metadata
        for m in metadata_members:
            meta_f = tf.extractfile(m)
            if meta_f is None:
                continue
            metadata = json.loads(meta_f.read().decode('utf-8'))
            found_accession = metadata.get('accession-number') or metadata.get('accession_number') or metadata.get('accessionNumber') or ''
            found_accession = _normalize_accession(found_accession)
            if found_accession == accession_no:
                target_meta = m
                prefix = _get_prefix(m.name)
                break
    else:
        # Use the first metadata
        target_meta = metadata_members[0]
        prefix = _get_prefix(target_meta.name)

    if target_meta is None:
        log.warning("Accession %s not found in tar", accession_no)
        return None

    # Read metadata
    meta_f = tf.extractfile(target_meta)
    if meta_f is None:
        return None
    metadata = json.loads(meta_f.read().decode('utf-8'))

    return _build_filing_sgml(tf, metadata, prefix, members)


def _build_filing_sgml(
    tf: tarfile.TarFile,
    metadata: Dict,
    prefix: str,
    members: List[tarfile.TarInfo],
) -> FilingSGML:
    """Construct a FilingSGML from tar contents."""
    header = filing_header_from_metadata(metadata)

    # Build a filename→doc_info map from the documents array if available
    doc_info_map: Dict[str, Dict] = {}
    if isinstance(metadata.get('documents'), list):
        for doc_info in metadata['documents']:
            if isinstance(doc_info, dict) and 'filename' in doc_info:
                doc_info_map[doc_info['filename']] = doc_info

    # Build documents from tar members
    documents_by_sequence = defaultdict(list)
    seq = 1

    for member in members:
        # Skip directories, metadata.json, and files outside our prefix
        if member.isdir():
            continue
        if member.name.endswith('metadata.json'):
            continue
        if prefix and not member.name.startswith(prefix):
            continue

        f = tf.extractfile(member)
        if f is None:
            continue

        filename = _strip_prefix(member.name, prefix)
        raw_content = f.read()

        # Decompress zstd-compressed content (datamule uses zstandard)
        raw_content = _maybe_decompress_zstd(raw_content)

        # Try to decode as text; keep as bytes for binary files
        try:
            content_str = raw_content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content_str = raw_content.decode('latin-1')
            except UnicodeDecodeError:
                content_str = raw_content.decode('utf-8', errors='replace')

        # Use metadata documents array for type/sequence/description if available
        info = doc_info_map.get(filename)
        if info:
            doc_seq = info.get('sequence', str(seq))
            doc_type = info.get('type', _infer_doc_type(filename))
            doc_desc = info.get('description', '')
        else:
            doc_seq = str(seq)
            doc_type = _infer_doc_type(filename)
            doc_desc = ''

        doc = TarSGMLDocument.create(
            sequence=doc_seq,
            type=doc_type,
            filename=filename,
            description=doc_desc,
            raw_content=content_str,
        )
        documents_by_sequence[doc_seq].append(doc)
        seq += 1

    return FilingSGML(header=header, documents=documents_by_sequence)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_prefix(metadata_path: str) -> str:
    """Extract the directory prefix from a metadata.json path.

    'metadata.json' -> ''
    '0001193125-24-012345/metadata.json' -> '0001193125-24-012345/'
    """
    parts = metadata_path.rsplit('/', 1)
    if len(parts) == 1:
        return ''
    return parts[0] + '/'


def _strip_prefix(name: str, prefix: str) -> str:
    """Remove prefix from a tar member name."""
    if prefix and name.startswith(prefix):
        return name[len(prefix):]
    return name


def _normalize_accession(accession_no: str) -> str:
    """Normalize accession number to dashed format."""
    accession_no = accession_no.strip()
    if '-' in accession_no:
        return accession_no
    if len(accession_no) == 18 and accession_no.isdigit():
        return f"{accession_no[:10]}-{accession_no[10:12]}-{accession_no[12:]}"
    return accession_no


_ZSTD_MAGIC = b'\x28\xb5\x2f\xfd'


def _maybe_decompress_zstd(data: bytes) -> bytes:
    """Decompress zstd-compressed data if detected, otherwise return as-is."""
    if not data or not data[:4] == _ZSTD_MAGIC:
        return data
    try:
        import zstandard
        dctx = zstandard.ZstdDecompressor()
        return dctx.decompress(data)
    except ImportError:
        log.warning("zstandard package not installed; cannot decompress zstd content")
        return data
    except Exception as e:
        log.warning("Failed to decompress zstd content: %s", e)
        return data


def _infer_doc_type(filename: str) -> str:
    """Infer a document type string from filename extension."""
    ext = Path(filename).suffix.lower()
    type_map = {
        '.htm': 'HTML',
        '.html': 'HTML',
        '.xml': 'XML',
        '.xsd': 'XML',
        '.txt': 'TEXT',
        '.json': 'JSON',
        '.jpg': 'GRAPHIC',
        '.jpeg': 'GRAPHIC',
        '.png': 'GRAPHIC',
        '.gif': 'GRAPHIC',
        '.pdf': 'PDF',
        '.xlsx': 'EXCEL',
        '.zip': 'ZIP',
    }
    return type_map.get(ext, filename.split('.')[-1].upper() if '.' in filename else '')

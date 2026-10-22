"""GitHub PR: https://github.com/dgunning/edgartools/pull/1598

Maintainer-reported archive recovery and incremental feed regressions.
Fabricated archives only; no requests reach the SEC.
"""
import asyncio
import gzip
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pyarrow as pa
import pytest

from edgar import Filings, httprequests
from edgar.storage import _local
from tests.test_bulk_refresh_atomicity import PREVIOUS, refresh, tree, write_archive

pytestmark = pytest.mark.fast


@pytest.mark.parametrize("compress", [False, True])
def test_two_filtered_downloads_keep_both_filings(tmp_path, compress):
    first, second = "0000000001-24-000001", "0000000002-24-000002"
    batches = iter([{first + ".nc": b"filing A"}, {second + ".nc": b"filing B"}])

    async def stream(url, **kwargs):
        write_archive(kwargs["path"] / "20240102.nc.tar.gz", next(batches))

    feed = pd.DataFrame([{"Name": "20240102.nc.tar.gz", "File": "https://example.invalid/20240102.nc.tar.gz"}])
    with patch.object(_local, "list_filing_feed_files_for_quarter", return_value=feed), \
            patch.object(_local, "check_filings_exist_locally", return_value=False), \
            patch.object(httprequests, "stream_file", stream):
        for accession in [first, second]:
            filings = Filings(pa.table({"accession_number": [accession], "filing_date": [date(2024, 1, 2)],
                                        "cik": [1], "company": ["Fixture"], "form": ["10-K"]}))
            _local.download_filings("2024-01-02", data_directory=tmp_path, filings=filings,
                                    overwrite_existing=True, compress=compress, disable_progress=True)
    for accession, content in [(first, b"filing A"), (second, b"filing B")]:
        path = tmp_path / "20240102" / (accession + (".nc.gz" if compress else ".nc"))
        assert (gzip.decompress(path.read_bytes()) if compress else path.read_bytes()) == content


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_failed_publication_and_restore_retain_recovery(tmp_path, caplog, failure):
    target = tmp_path / "bulk"
    target.mkdir()
    for name, content in PREVIOUS.items():
        (target / name).write_bytes(content)
    replace = os.replace

    def fail(source, destination):
        if Path(destination) == target:
            if Path(source).name == "previous":
                raise OSError("synthetic restore failure")
            raise failure("synthetic publication failure")
        return replace(source, destination)

    with patch.object(httprequests.os, "replace", fail), pytest.raises(failure):
        refresh(tmp_path, "zip")
    recoveries = list(tmp_path.glob(".bulk-*/previous"))
    assert len(recoveries) == 1
    assert tree(recoveries[0]) == PREVIOUS
    assert str(recoveries[0]) in caplog.text
    # A later call must retain that only old copy, even if it publishes a fresh tree.
    refresh(tmp_path, "zip")
    assert tree(recoveries[0]) == PREVIOUS


def test_next_call_sweeps_crashed_owned_stage(tmp_path):
    program = """
import os, sys
from pathlib import Path
from edgar.httprequests import _bulk_staging
with _bulk_staging(Path(sys.argv[1]), 'bulk') as stage:
    (stage / 'partial').write_bytes(b'crashed download')
    os._exit(0)
"""
    subprocess.run([sys.executable, "-c", program, str(tmp_path)], check=True, timeout=30)  # noqa: S603
    abandoned = list(tmp_path.glob(".bulk-*"))
    assert len(abandoned) == 1
    refresh(tmp_path, "zip")
    assert not abandoned[0].exists()


def test_sweep_preserves_active_unknown_and_symlink_stages(tmp_path):
    unknown = tmp_path / ".bulk-user-data"
    unknown.mkdir()
    (unknown / "keep").write_bytes(b"unknown ownership")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_bytes(b"outside")
    linked = tmp_path / ".bulk-linked"
    linked.symlink_to(outside, target_is_directory=True)
    with httprequests._bulk_staging(tmp_path, "bulk") as active:
        (active / "partial").write_bytes(b"active download")
        refresh(tmp_path, "zip")
        assert (active / "partial").read_bytes() == b"active download"
        assert (unknown / "keep").read_bytes() == b"unknown ownership"
        assert linked.is_symlink()
        assert (outside / "keep").read_bytes() == b"outside"


def test_preservation_does_not_follow_existing_filing_link(tmp_path):
    target = tmp_path / "bulk"
    target.mkdir()
    outside = tmp_path / "outside.nc"
    outside.write_bytes(b"outside")
    (target / "old.nc").symlink_to(outside)

    async def stream(url, **kwargs):
        write_archive(kwargs["path"] / "bulk.zip")

    with patch.object(httprequests, "stream_file", stream), pytest.raises(ValueError, match="regular files"):
        asyncio.run(httprequests.download_bulk_data.__wrapped__("https://example.invalid/bulk.zip", tmp_path,
                                                              disable_progress=True,
                                                              preserve_existing_filings=True))
    assert outside.read_bytes() == b"outside"
    assert (target / "old.nc").is_symlink()

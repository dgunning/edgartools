"""GitHub PR: https://github.com/dgunning/edgartools/pull/1598

Maintainer-reported archive recovery and incremental feed regressions.
Fabricated archives only; no requests reach the SEC.
"""
import asyncio
import errno
import gzip
import os
import subprocess
import sys
from contextlib import contextmanager
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


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt, asyncio.CancelledError])
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


def test_sweep_preserves_active_and_unknown_stages(tmp_path):
    unknown = tmp_path / ".bulk-user-data"
    unknown.mkdir()
    (unknown / "keep").write_bytes(b"unknown ownership")
    with httprequests._bulk_staging(tmp_path, "bulk") as active:
        (active / "partial").write_bytes(b"active download")
        refresh(tmp_path, "zip")
        assert (active / "partial").read_bytes() == b"active download"
        assert (unknown / "keep").read_bytes() == b"unknown ownership"


@pytest.mark.parametrize("setup_step", ["marker", "lease"])
def test_failed_stage_setup_leaves_no_orphan(tmp_path, setup_step):
    write = Path.write_bytes
    lock = httprequests._bulk_file_lock

    def fail_marker(path, content):
        if path.name == httprequests._BULK_STAGE_MARKER:
            raise OSError("synthetic marker failure")
        return write(path, content)

    @contextmanager
    def fail_lease(path, blocking=True):
        if path.name == httprequests._BULK_STAGE_MARKER:
            raise OSError("synthetic lease failure")
        with lock(path, blocking) as acquired:
            yield acquired

    target = "write_bytes" if setup_step == "marker" else "_bulk_file_lock"
    owner = Path if setup_step == "marker" else httprequests
    replacement = fail_marker if setup_step == "marker" else fail_lease
    with patch.object(owner, target, replacement), pytest.raises(OSError, match="synthetic"):
        with httprequests._bulk_staging(tmp_path, "bulk"):
            pytest.fail("failed setup must not yield a stage")
    assert list(tmp_path.glob(".bulk-*")) == []


@pytest.mark.parametrize("blocking", [False, True])
def test_lock_errors_other_than_contention_propagate(tmp_path, blocking):
    module = __import__("msvcrt" if os.name == "nt" else "fcntl")
    operation = "locking" if os.name == "nt" else "flock"
    with patch.object(module, operation, side_effect=OSError(errno.EBADF, "synthetic invalid descriptor")), \
            pytest.raises(OSError, match="invalid descriptor"):
        with httprequests._bulk_file_lock(tmp_path / ".bulk.lock", blocking=blocking):
            pytest.fail("non-contention errors must propagate")


def test_coordinator_waits_through_long_contention(tmp_path):
    program = """
import sys
from pathlib import Path
from edgar.httprequests import _bulk_file_lock
print('waiting', flush=True)
with _bulk_file_lock(Path(sys.argv[1])):
    print('acquired', flush=True)
"""
    with httprequests._bulk_file_lock(tmp_path / ".bulk.lock"):
        waiter = subprocess.Popen([sys.executable, "-c", program, str(tmp_path / ".bulk.lock")],  # noqa: S603
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            assert waiter.stdout.readline().strip() == "waiting"
            with pytest.raises(subprocess.TimeoutExpired):
                waiter.communicate(timeout=12)
            assert waiter.poll() is None
        except BaseException:
            waiter.kill()
            waiter.communicate(timeout=10)
            raise
    try:
        output, error = waiter.communicate(timeout=10)
        assert waiter.returncode == 0, error
        assert output.strip() == "acquired"
    finally:
        if waiter.poll() is None:
            waiter.kill()
            waiter.communicate(timeout=10)

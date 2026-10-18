"""Bulk refresh publishes a complete archive or leaves the cache as it was.

Fabricated archives only; stream_file is patched, so nothing reaches the SEC.
"""
import asyncio
import io
import os
import tarfile
import zipfile
from unittest.mock import patch

import pytest

from edgar import httprequests

# The retry policy is separate from filesystem ownership, so call the undecorated function.
download_bulk_data = httprequests.download_bulk_data.__wrapped__

FILES = {"first.json": b"new first", "second.json": b"new second", "nested/third.json": b"new third"}


def write_archive(path, files=FILES):
    if path.name.endswith(".zip"):
        with zipfile.ZipFile(path, "w") as archive:
            for name, value in files.items():
                archive.writestr(name, value)
    else:
        with tarfile.open(path, "w:gz") as archive:
            for name, value in files.items():
                member = tarfile.TarInfo(name)
                member.size = len(value)
                archive.addfile(member, io.BytesIO(value))


def refresh(root, extension, stream=None):
    async def default_stream(url, **kwargs):
        write_archive(kwargs["path"] / f"bulk.{extension}")

    with patch.object(httprequests, "stream_file", stream or default_stream):
        return asyncio.run(download_bulk_data(f"https://example.invalid/bulk.{extension}", root,
                                              disable_progress=True))


def tree(path):
    return {str(p.relative_to(path)).replace(os.sep, "/"): p.read_bytes()
            for p in sorted(path.rglob("*")) if p.is_file()}


@pytest.fixture
def cache(tmp_path):
    target = tmp_path / "bulk"
    target.mkdir()
    (target / "first.json").write_bytes(b"previous")
    (target / "stale.json").write_bytes(b"dropped from the new archive")
    return tmp_path, target


PREVIOUS = {"first.json": b"previous", "stale.json": b"dropped from the new archive"}


@pytest.mark.fast
@pytest.mark.parametrize("extension", ["zip", "tar.gz"])
def test_success_replaces_the_whole_tree(cache, extension):
    root, target = cache
    assert refresh(root, extension) == target
    assert tree(target) == FILES
    assert set(root.iterdir()) == {target}


@pytest.mark.fast
@pytest.mark.parametrize("extension", ["zip", "tar.gz"])
def test_first_run_creates_the_tree(tmp_path, extension):
    assert tree(refresh(tmp_path, extension)) == FILES
    assert set(tmp_path.iterdir()) == {tmp_path / "bulk"}


@pytest.mark.fast
@pytest.mark.parametrize("extension", ["zip", "tar.gz"])
@pytest.mark.parametrize("existing", [True, False])
@pytest.mark.parametrize("failure", ["download", "extract", "publish"])
def test_failure_leaves_the_cache_as_it_was(tmp_path, extension, existing, failure):
    target = tmp_path / "bulk"
    if existing:
        target.mkdir()
        (target / "first.json").write_bytes(b"previous")

    async def stream(url, **kwargs):
        write_archive(kwargs["path"] / f"bulk.{extension}")
        if failure == "download":
            raise OSError("synthetic download failure")

    owner = zipfile.ZipFile if extension == "zip" else tarfile.TarFile
    extract, replace = owner.extract, os.replace
    calls = {"extract": 0}

    def failing_extract(archive, *args, **kwargs):
        calls["extract"] += 1
        if failure == "extract" and calls["extract"] == 2:
            raise OSError("synthetic extraction failure")
        return extract(archive, *args, **kwargs)

    def failing_replace(source, destination):
        # Fail moving the new tree into place, after any old tree has been moved aside.
        if failure == "publish" and str(destination) == str(target) and "previous" not in str(source):
            raise OSError("synthetic publication failure")
        return replace(source, destination)

    with patch.object(owner, "extract", failing_extract), \
            patch.object(httprequests.os, "replace", failing_replace), pytest.raises(OSError):
        refresh(tmp_path, extension, stream)
    if existing:
        assert tree(target) == {"first.json": b"previous"}
    assert set(tmp_path.iterdir()) == ({target} if existing else set())


@pytest.mark.fast
@pytest.mark.parametrize("link_type", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE])
def test_tar_links_and_special_files_are_refused(cache, link_type):
    root, target = cache

    async def stream(url, **kwargs):
        with tarfile.open(kwargs["path"] / "bulk.tar.gz", "w:gz") as archive:
            first = tarfile.TarInfo("first.json")
            first.size = 1
            archive.addfile(first, io.BytesIO(b"1"))
            member = tarfile.TarInfo("linked.json")
            member.type = link_type
            member.linkname = "first.json"
            archive.addfile(member)

    with pytest.raises(ValueError, match="regular files"):
        refresh(root, "tar.gz", stream)
    assert tree(target) == PREVIOUS
    assert set(root.iterdir()) == {target}


@pytest.mark.fast
@pytest.mark.parametrize("name", ["../escape.json", "nested/../../escape.json", "../../bulk/first.json",
                                  "/absolute/first.json"])
def test_tar_paths_outside_staging_are_refused(cache, name):
    root, target = cache

    async def stream(url, **kwargs):
        write_archive(kwargs["path"] / "bulk.tar.gz", {name: b"new"})

    with pytest.raises((ValueError, tarfile.TarError)):
        refresh(root, "tar.gz", stream)
    assert tree(target) == PREVIOUS
    assert set(root.iterdir()) == {target}


@pytest.mark.fast
def test_tar_path_that_stays_inside_staging_is_extracted(tmp_path):
    async def stream(url, **kwargs):
        write_archive(kwargs["path"] / "bulk.tar.gz", {"nested/../first.json": b"new"})

    assert tree(refresh(tmp_path, "tar.gz", stream)) == {"first.json": b"new"}


@pytest.mark.fast
def test_tar_filter_rejection_is_not_retried_without_the_filter(cache):
    root, target = cache
    unfiltered = []

    def extract(archive, member, *args, **kwargs):
        if "filter" in kwargs:
            raise TypeError("synthetic filter rejection")
        unfiltered.append(member.name)

    with patch.object(tarfile.TarFile, "extract", extract), pytest.raises(TypeError, match="synthetic"):
        refresh(root, "tar.gz")
    assert unfiltered == []
    assert tree(target) == PREVIOUS


@pytest.mark.fast
def test_python_without_tar_filters_gets_a_clear_error(cache, monkeypatch):
    root, target = cache
    monkeypatch.delattr(tarfile, "tar_filter")
    with pytest.raises(RuntimeError, match="Python 3.11.4 or later"):
        refresh(root, "tar.gz")
    assert tree(target) == PREVIOUS


@pytest.mark.fast
@pytest.mark.parametrize("extension", ["zip", "tar.gz"])
def test_links_in_the_old_tree_are_replaced_not_followed(cache, extension):
    root, target = cache
    outside = root / "outside"
    outside.mkdir()
    (outside / "third.json").write_bytes(b"outside")
    try:
        (target / "nested").symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlinks unavailable: {error}")

    refresh(root, extension)
    assert tree(target) == FILES
    assert not (target / "nested").is_symlink()
    assert (outside / "third.json").read_bytes() == b"outside"

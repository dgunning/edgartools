"""Fabricated archives exercise refresh failure without SEC or cache access."""
import ast
import io
import logging
import os
import shutil
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Optional
from unittest.mock import patch


class Progress:
    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def update(self, amount):
        pass


class BulkRefreshTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / "edgar" / "httprequests.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                        and node.name == "download_bulk_data")
        function.decorator_list = []  # Retry policy is separate from filesystem ownership.
        self.namespace = dict(Path=Path, Optional=Optional, AsyncClient=object, os=os,
                              tarfile=tarfile, tempfile=tempfile, zipfile=zipfile, shutil=shutil,
                              logger=logging.getLogger(__name__), tqdm=Progress)
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), self.namespace)

    def archive(self, extension):
        result = io.BytesIO()
        if extension == "zip":
            with zipfile.ZipFile(result, "w") as archive:
                archive.writestr("first.json", b"new first")
                archive.writestr("second.json", b"new second")
                archive.writestr("nested/third.json", b"new third")
        else:
            with tarfile.open(fileobj=result, mode="w:gz") as archive:
                for name, value in (("first.json", b"new first"), ("second.json", b"new second"),
                                    ("nested/third.json", b"new third")):
                    member = tarfile.TarInfo(name)
                    member.size = len(value)
                    archive.addfile(member, io.BytesIO(value))
        return result.getvalue()

    async def test_refresh_failure_preserves_existing_and_first_run(self):
        for extension in ("zip", "tar.gz"):
            for existing in (False, True):
                for failure in ("download", "extract"):
                    with self.subTest(extension=extension, existing=existing, failure=failure):
                        with tempfile.TemporaryDirectory() as folder:
                            root = Path(folder)
                            target = root / "bulk"
                            if existing:
                                target.mkdir()
                                (target / "first.json").write_bytes(b"previous")

                            async def stream(url, **kwargs):
                                (kwargs["path"] / f"bulk.{extension}").write_bytes(self.archive(extension))
                                if failure == "download":
                                    raise OSError("synthetic download failure")

                            self.namespace["stream_file"] = stream
                            owner = zipfile.ZipFile if extension == "zip" else tarfile.TarFile
                            original = owner.extract
                            calls = 0

                            def extract(archive, *args, **kwargs):
                                nonlocal calls
                                calls += 1
                                if calls == 2:
                                    raise OSError("synthetic extraction failure")
                                return original(archive, *args, **kwargs)

                            with patch.object(owner, "extract", extract):
                                with self.assertRaises(OSError):
                                    await self.namespace["download_bulk_data"](
                                        f"https://example.invalid/bulk.{extension}", root, disable_progress=True)
                            if existing:
                                self.assertEqual((target / "first.json").read_bytes(), b"previous")
                                self.assertEqual(set(target.iterdir()), {target / "first.json"})
                            else:
                                self.assertFalse(target.exists())
                            self.assertEqual(set(root.iterdir()), {target} if existing else set())

    async def test_archive_links_are_refused_before_publication(self):
        for link_type in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE):
            with self.subTest(link_type=link_type), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                target = root / "bulk"
                target.mkdir()
                (target / "previous.json").write_bytes(b"previous")

                async def stream(url, **kwargs):
                    with tarfile.open(kwargs["path"] / "bulk.tar.gz", "w:gz") as archive:
                        first = tarfile.TarInfo("first.json")
                        first.size = 1
                        archive.addfile(first, io.BytesIO(b"1"))
                        member = tarfile.TarInfo("linked.json")
                        member.type = link_type
                        member.linkname = "first.json"
                        archive.addfile(member)

                self.namespace["stream_file"] = stream
                with self.assertRaisesRegex(ValueError, "regular files"):
                    await self.namespace["download_bulk_data"]("https://example.invalid/bulk.tar.gz", root)
                self.assertEqual((target / "previous.json").read_bytes(), b"previous")
                self.assertEqual(set(root.iterdir()), {target})

    async def test_tar_filter_failure_does_not_retry_without_filter(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "bulk"
            target.mkdir()
            (target / "first.json").write_bytes(b"previous")

            async def stream(url, **kwargs):
                (kwargs["path"] / "bulk.tar.gz").write_bytes(self.archive("tar.gz"))

            self.namespace["stream_file"] = stream
            original = tarfile.TarFile.extract
            unfiltered_calls = []

            def extract(archive, *args, **kwargs):
                if "filter" in kwargs:
                    raise TypeError("synthetic filter rejection")
                unfiltered_calls.append(args[0].name)
                return original(archive, *args, filter="fully_trusted", **kwargs)

            with patch.object(tarfile.TarFile, "extract", extract):
                with self.assertRaisesRegex(TypeError, "synthetic filter rejection"):
                    await self.namespace["download_bulk_data"](
                        "https://example.invalid/bulk.tar.gz", root)
            self.assertEqual(unfiltered_calls, [])
            self.assertEqual((target / "first.json").read_bytes(), b"previous")
            self.assertEqual(set(root.iterdir()), {target})

    async def test_destination_directory_redirect_is_refused_before_publication(self):
        for extension in ("zip", "tar.gz"):
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                target = root / "bulk"
                outside = root / "outside"
                target.mkdir()
                outside.mkdir()
                (outside / "item.json").write_bytes(b"previous")
                try:
                    (target / "nested").symlink_to(outside, target_is_directory=True)
                except OSError as error:
                    self.skipTest(f"Directory symlinks unavailable: {error}")

                async def stream(url, **kwargs):
                    archive_path = kwargs["path"] / f"bulk.{extension}"
                    if extension == "zip":
                        with zipfile.ZipFile(archive_path, "w") as archive:
                            archive.writestr("nested/item.json", b"new")
                    else:
                        with tarfile.open(archive_path, "w:gz") as archive:
                            member = tarfile.TarInfo("nested/item.json")
                            member.size = 3
                            archive.addfile(member, io.BytesIO(b"new"))

                self.namespace["stream_file"] = stream
                with self.assertRaisesRegex(ValueError, "destination"):
                    await self.namespace["download_bulk_data"](
                        f"https://example.invalid/bulk.{extension}", root)
                self.assertEqual((outside / "item.json").read_bytes(), b"previous")
                self.assertEqual(set(root.iterdir()), {target, outside})

    async def test_tar_paths_remain_inside_staging(self):
        for form in ("parent", "nested-parent", "absolute", "excursion-return", "safe"):
            with self.subTest(form=form), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                target = root / "bulk"
                target.mkdir()
                (target / "previous.json").write_bytes(b"previous")

                async def stream(url, **kwargs):
                    stage = kwargs["path"]
                    names = {
                        "parent": "../bulk/previous.json",
                        "nested-parent": "nested/../../bulk/previous.json",
                        "absolute": str(target / "previous.json"),
                        "excursion-return": f"../outside/../{stage.name}/first.json",
                        "safe": "nested/../first.json",
                    }
                    with tarfile.open(stage / "bulk.tar.gz", "w:gz") as archive:
                        member = tarfile.TarInfo(names[form])
                        member.size = 3
                        archive.addfile(member, io.BytesIO(b"new"))

                self.namespace["stream_file"] = stream
                if form in ("safe", "excursion-return"):
                    await self.namespace["download_bulk_data"](
                        "https://example.invalid/bulk.tar.gz", root)
                    self.assertEqual((target / "first.json").read_bytes(), b"new")
                else:
                    with self.assertRaises((ValueError, tarfile.TarError)):
                        await self.namespace["download_bulk_data"](
                            "https://example.invalid/bulk.tar.gz", root)
                self.assertEqual((target / "previous.json").read_bytes(), b"previous")
                self.assertEqual(set(root.iterdir()), {target})

    async def test_success_replaces_complete_members_and_retains_extra_files(self):
        for extension in ("zip", "tar.gz"):
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                target = root / "bulk"
                target.mkdir()
                (target / "first.json").write_bytes(b"previous")
                (target / "extra.json").write_bytes(b"retained")

                async def stream(url, **kwargs):
                    (kwargs["path"] / f"bulk.{extension}").write_bytes(self.archive(extension))

                self.namespace["stream_file"] = stream
                result = await self.namespace["download_bulk_data"](
                    f"https://example.invalid/bulk.{extension}", root, disable_progress=True)
                self.assertEqual(result, target)
                self.assertEqual((target / "first.json").read_bytes(), b"new first")
                self.assertEqual((target / "second.json").read_bytes(), b"new second")
                self.assertEqual((target / "nested" / "third.json").read_bytes(), b"new third")
                self.assertEqual((target / "extra.json").read_bytes(), b"retained")
                self.assertEqual(set(root.iterdir()), {target})

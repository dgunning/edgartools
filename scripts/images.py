#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "Pillow>=10.0",
#     "playwright>=1.40",
# ]
# ///
"""Convert and optimize images for the docs site and the edgartools.io blog.

Runnable standalone with `uv run scripts/images.py ...`, which is how the blog's
figure scripts reach it: those run in their own pinned environment and have no
Pillow of their own. Chromium comes from the shared per-user Playwright cache,
not the ephemeral env, so `playwright install chromium` is a one-time setup.


One entry point for the whole chain — SVG, PNG, JPEG or WebP in, an optimized
WebP (or PNG) out. Supersedes convert_png_to_webp.py and convert_svg_to_png.py,
which handled one leg each and required Inkscape for the SVG leg.

    python scripts/images.py convert posts/images/*.svg
    python scripts/images.py convert diagram.png --out-dir docs/images
    python scripts/images.py convert hero.png --max-width 2400 --quality 90
    python scripts/images.py info docs/images/*.webp

Why WebP: both the docs site and Ghost serve it, and for the flat-colour
screenshots and diagrams this project produces it is dramatically smaller than
PNG at visually identical quality.

Sizing. --max-width is the output pixel cap and defaults to 1440px, which is 2x
the 720px content column both the docs theme and Ghost's Source theme render at
— so the default is already the retina size, and anything wider is bytes nobody
sees. Images narrower than the cap are never upscaled. SVG is rendered at
max-width * --scale and then downsampled to max-width, so the supersampling
cleans up text edges while every output, vector or raster, lands at the same
width.

Lossy or lossless. --lossless auto (the default) encodes both ways and keeps
whichever file is smaller. Screenshots and diagrams have large flat areas where
lossless WebP usually wins outright and is also sharper; photographs go the
other way. Guessing per-image is unnecessary when trying both is this cheap.

SVG rasterization has two backends, picked by --rasterizer (default auto):

  inkscape   a real SVG renderer, offline and deterministic. Found via the macOS
             app bundle as well as PATH, since the bundle is not on PATH.
  chromium   headless Chromium via Playwright, already used by the Rich-console
             capture scripts.

auto routes per file rather than picking one globally: an SVG that references
something over http(s) goes to Chromium, everything else to Inkscape. That split
is not cosmetic — Rich's console export loads Fira Code from a CDN, and rendered
through Inkscape its bold runs come back flattened to regular weight because the
font never loads. Self-contained diagrams have no such problem and Inkscape is
the better renderer for them.

Requires: Pillow. SVG input additionally requires Inkscape or playwright+chromium.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("images.py needs Pillow: pip install Pillow")

RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
SVG_SUFFIXES = {".svg"}
DEFAULT_MAX_WIDTH = 1440
DEFAULT_QUALITY = 82
VIEWBOX_RE = re.compile(r'viewBox\s*=\s*["\']([\d.\s+-]+)["\']', re.I)
DIM_RE = re.compile(r'\b(width|height)\s*=\s*["\']([\d.]+)(px)?["\']', re.I)


def human(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if abs(n) < 1024 or unit == "MB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n / 1:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}MB"


def size_str(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f}KB"
    return f"{n / (1024 * 1024):.2f}MB"


@dataclass
class Result:
    src: Path
    dest: Path | None
    before: int
    after: int
    note: str = ""
    vector: bool = False  # SVG source: "% smaller" vs the vector file is meaningless

    @property
    def saved_pct(self) -> float:
        return 0.0 if not self.before else (1 - self.after / self.before) * 100


# --------------------------------------------------------------------------- SVG


def svg_root_tag(text: str) -> str:
    """The opening <svg ...> tag only.

    Attributes must be read from the root element, never from the document at
    large: Rich's terminal export puts no width/height on <svg> but does put
    them on child <rect>s, and matching those yields a wildly wrong aspect ratio.
    """
    start = text.find("<svg")
    if start == -1:
        return ""
    end = text.find(">", start)
    return text[start : end + 1] if end != -1 else text[start : start + 2000]


def svg_intrinsic_size(text: str) -> tuple[float, float] | None:
    """Best-effort intrinsic size: root width/height attrs, else the viewBox."""
    root = svg_root_tag(text)
    if not root:
        return None
    dims = {k.lower(): float(v) for k, v, _ in DIM_RE.findall(root)}
    if dims.get("width", 0) > 0 and dims.get("height", 0) > 0:
        return dims["width"], dims["height"]
    m = VIEWBOX_RE.search(root)
    if m:
        parts = [float(p) for p in m.group(1).replace(",", " ").split()]
        if len(parts) == 4 and parts[2] > 0 and parts[3] > 0:
            return parts[2], parts[3]
    return None


def find_inkscape() -> str | None:
    """Inkscape ships as a macOS app bundle that is not on PATH, so check both."""
    from shutil import which

    found = which("inkscape")
    if found:
        return found
    candidates = [
        "/Applications/Inkscape.app/Contents/MacOS/inkscape",
        str(Path.home() / "Applications/Inkscape.app/Contents/MacOS/inkscape"),
        "/opt/homebrew/bin/inkscape",
        "/usr/local/bin/inkscape",
        "/usr/bin/inkscape",
        "/snap/bin/inkscape",
        r"C:\Program Files\Inkscape\bin\inkscape.exe",
    ]
    return next((c for c in candidates if Path(c).is_file()), None)


def _rasterize_inkscape(exe: str, jobs: list[tuple[Path, Path, int, int]]) -> list[str]:
    import subprocess

    errors: list[str] = []
    for src, dest, width, scale in jobs:
        cmd = [
            exe,
            "--export-type=png",
            f"--export-filename={dest}",
            f"--export-width={width * scale}",
            "--export-background-opacity=0",
            str(src),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as e:
            errors.append(f"{src}: inkscape failed: {e}")
            continue
        if proc.returncode != 0 or not dest.exists():
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            errors.append(f"{src}: inkscape failed: {detail[-1] if detail else 'no output'}")
    return errors


async def _rasterize_all(jobs: list[tuple[Path, Path, int, int]]) -> list[str]:
    """jobs: (svg path, png dest, css width px, device scale). Returns error strings."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return [f"{src}: SVG input needs playwright (pip install playwright && "
                f"playwright install chromium)" for src, *_ in jobs]

    errors: list[str] = []
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            # Browsers live in a per-user cache keyed by Playwright's build
            # number, so a newer Playwright (as an ephemeral `uv run` env will
            # resolve) wants a build the cache may not have. The library's own
            # error is a wall of async stack frames; say the fix instead.
            if "Executable doesn't exist" in str(e):
                return [f"{src}: chromium missing for this Playwright build — run "
                        f"`uv run --with playwright --no-project python -m playwright "
                        f"install chromium` once" for src, *_ in jobs]
            raise
        try:
            for src, dest, width, scale in jobs:
                text = src.read_text(encoding="utf-8")
                intrinsic = svg_intrinsic_size(text)
                if intrinsic is None:
                    errors.append(f"{src}: no width/height or viewBox — cannot size it")
                    continue
                iw, ih = intrinsic
                height = max(1, round(width * ih / iw))
                page = await browser.new_page(
                    viewport={"width": width, "height": height},
                    device_scale_factor=scale,
                )
                # Inline the SVG so it scales to the viewport exactly; transparent
                # background is preserved via omit_background on the screenshot.
                await page.set_content(
                    "<style>html,body{margin:0;padding:0;background:transparent}"
                    f"svg{{display:block;width:{width}px;height:{height}px}}</style>"
                    + text,
                    wait_until="networkidle",
                )
                try:  # Rich SVGs pull a webfont; without it metrics shift slightly
                    await page.evaluate("document.fonts.ready")
                except Exception:
                    pass
                await page.wait_for_timeout(250)
                await page.screenshot(path=str(dest), omit_background=True)
                await page.close()
        finally:
            await browser.close()
    return errors


# Two shapes: an XML attribute (xlink:href="https://…") and a CSS url() inside a
# <style> block, which is where @font-face lives — the Rich export uses the latter,
# so an attribute-only pattern silently matches nothing.
REMOTE_REF_RE = re.compile(
    r'(?:(?:src|href|xlink:href)\s*=\s*["\']?https?://)|(?:url\(\s*["\']?https?://)',
    re.I,
)


def needs_browser(svg: Path) -> bool:
    """True when the SVG pulls something off the network — typically a webfont.

    Inkscape renders local vector geometry faithfully but will not fetch remote
    resources, so a Rich console export (which loads Fira Code from a CDN) comes
    out with its bold runs flattened to regular. Chromium fetches the font and
    the weights survive.
    """
    try:
        return bool(REMOTE_REF_RE.search(svg.read_text(encoding="utf-8", errors="ignore")))
    except OSError:
        return False


def rasterize(jobs: list[tuple[Path, Path, int, int]], backend: str) -> list[str]:
    if not jobs:
        return []
    exe = find_inkscape() if backend in ("auto", "inkscape") else None

    if backend == "inkscape":
        if not exe:
            return [f"{src}: --rasterizer inkscape but Inkscape was not found"
                    for src, *_ in jobs]
        return _rasterize_inkscape(exe, jobs)

    if backend == "chromium":
        return asyncio.run(_rasterize_all(jobs))

    # auto: Inkscape for self-contained SVGs, Chromium for anything that needs
    # the network. Falls back to Chromium entirely when Inkscape is absent.
    if not exe:
        return asyncio.run(_rasterize_all(jobs))
    browser_jobs = [j for j in jobs if needs_browser(j[0])]
    local_jobs = [j for j in jobs if not needs_browser(j[0])]
    errors = _rasterize_inkscape(exe, local_jobs) if local_jobs else []
    if browser_jobs:
        errors += asyncio.run(_rasterize_all(browser_jobs))
    return errors


# ------------------------------------------------------------------------ encode


def encode(img: Image.Image, dest: Path, fmt: str, quality: int, mode: str) -> None:
    """Write img to dest. mode: auto | lossy | lossless (auto keeps the smaller)."""
    if fmt == "png":
        img.save(dest, "PNG", optimize=True)
        return

    common = {"method": 6}
    if mode == "lossy":
        img.save(dest, "WEBP", quality=quality, **common)
        return
    if mode == "lossless":
        img.save(dest, "WEBP", lossless=True, **common)
        return

    lossy_tmp = dest.with_suffix(".lossy.tmp")
    lossless_tmp = dest.with_suffix(".lossless.tmp")
    try:
        img.save(lossy_tmp, "WEBP", quality=quality, **common)
        img.save(lossless_tmp, "WEBP", lossless=True, **common)
        winner = min(lossy_tmp, lossless_tmp, key=lambda p: p.stat().st_size)
        dest.write_bytes(winner.read_bytes())
    finally:
        for tmp in (lossy_tmp, lossless_tmp):
            tmp.unlink(missing_ok=True)


def load_and_fit(path: Path, max_width: int) -> Image.Image:
    img = Image.open(path)
    if img.mode == "P":
        img = img.convert("RGBA" if "transparency" in img.info else "RGB")
    elif img.mode == "CMYK":
        img = img.convert("RGB")
    if max_width and img.width > max_width:
        height = max(1, round(img.height * max_width / img.width))
        img = img.resize((max_width, height), Image.LANCZOS)
    return img


def convert_one(src: Path, dest: Path, args) -> Result:
    before = src.stat().st_size
    img = load_and_fit(src, args.max_width)
    encode(img, dest, args.format, args.quality, args.lossless)
    return Result(src, dest, before, dest.stat().st_size)


# --------------------------------------------------------------------------- cli


def resolve_dest(src: Path, args, suffix: str) -> Path:
    if args.out and len(args.inputs) == 1 and not args.out.is_dir():
        return args.out
    outdir = args.out if args.out else (args.out_dir or src.parent)
    return Path(outdir) / (src.stem + suffix)


def cmd_convert(args: argparse.Namespace) -> int:
    suffix = "." + args.format
    paths = [Path(p) for p in args.inputs]
    missing = [p for p in paths if not p.is_file()]
    for p in missing:
        print(f"{p}: no such file", file=sys.stderr)
    paths = [p for p in paths if p.is_file()]
    if not paths:
        return 2

    results: list[Result] = []
    svg_jobs: list[tuple[Path, Path, int, int]] = []
    svg_dests: dict[Path, Path] = {}

    # foo.svg and foo.png both want foo.webp. Without this the second one wins
    # silently, and which one that is depends on shell glob order.
    claimed: dict[Path, Path] = {}

    for src in paths:
        dest = resolve_dest(src, args, suffix)
        dest.parent.mkdir(parents=True, exist_ok=True)
        owner = claimed.get(dest.resolve())
        if owner is not None:
            results.append(Result(src, None, src.stat().st_size, 0,
                                  f"skipped: {dest.name} already claimed by {owner.name}"))
            continue
        claimed[dest.resolve()] = src
        if dest.resolve() == src.resolve():
            results.append(Result(src, None, src.stat().st_size, src.stat().st_size,
                                  "skipped: would overwrite the input"))
            continue
        if dest.exists() and not args.force:
            results.append(Result(src, None, src.stat().st_size, dest.stat().st_size,
                                  "skipped: exists (use --force)"))
            continue

        ext = src.suffix.lower()
        if ext in SVG_SUFFIXES:
            tmp_png = dest.with_suffix(".raster.tmp.png")
            svg_jobs.append((src, tmp_png, args.max_width, args.scale))
            svg_dests[src] = dest
        elif ext in RASTER_SUFFIXES:
            try:
                results.append(convert_one(src, dest, args))
            except Exception as e:  # noqa: BLE001 - report and keep going
                results.append(Result(src, None, src.stat().st_size, 0, f"failed: {e}"))
        else:
            results.append(Result(src, None, src.stat().st_size, 0,
                                  f"skipped: unsupported type '{ext}'"))

    for err in rasterize(svg_jobs, args.rasterizer):
        print(err, file=sys.stderr)

    for src, tmp_png, _, _ in svg_jobs:
        dest = svg_dests[src]
        if not tmp_png.exists():
            results.append(Result(src, None, src.stat().st_size, 0, "failed: not rasterized"))
            continue
        try:
            before = src.stat().st_size
            # Rendered at max_width * scale, then downsampled to max_width: the
            # supersampling cleans up text edges, and the output ends up the same
            # pixel width a raster input would, so --max-width means one thing.
            img = load_and_fit(tmp_png, args.max_width)
            encode(img, dest, args.format, args.quality, args.lossless)
            results.append(Result(src, dest, before, dest.stat().st_size,
                                  note=f"{img.width}x{img.height}", vector=True))
        except Exception as e:  # noqa: BLE001
            results.append(Result(src, None, src.stat().st_size, 0, f"failed: {e}"))
        finally:
            tmp_png.unlink(missing_ok=True)

    return report(results)


def report(results: list[Result]) -> int:
    width = max((len(r.src.name) for r in results), default=10)
    total_before = total_after = 0
    failures = 0
    for r in sorted(results, key=lambda r: r.src.name):
        if r.dest is None:
            marker = "!" if r.note.startswith("failed") else "-"
            failures += r.note.startswith("failed")
            print(f"{marker} {r.src.name:<{width}}  {r.note}")
            continue
        if r.vector:
            # Rasterizing a vector can legitimately grow the file — a 35KB Rich
            # SVG is text; its retina raster is pixels. Reporting that as
            # "-285% smaller" would read as a failure, so show the size instead.
            print(f"  {r.src.name:<{width}}  {size_str(r.before):>9} → "
                  f"{size_str(r.after):>9}  {r.note:>11}  {r.dest}")
            continue
        total_before += r.before
        total_after += r.after
        print(f"  {r.src.name:<{width}}  {size_str(r.before):>9} → "
              f"{size_str(r.after):>9}  {r.saved_pct:5.1f}%  {r.dest}")

    rasters = [r for r in results if r.dest and not r.vector]
    vectors = [r for r in results if r.dest and r.vector]
    if rasters:
        pct = (1 - total_after / total_before) * 100 if total_before else 0
        print(f"\n{len(rasters)} raster image(s): {size_str(total_before)} → "
              f"{size_str(total_after)} ({pct:.1f}% smaller)")
    if vectors:
        print(f"{len(vectors)} vector image(s) rasterized → "
              f"{size_str(sum(r.after for r in vectors))} total")
    return 1 if failures else 0


def cmd_info(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.inputs if Path(p).is_file()]
    if not paths:
        return 2
    width = max(len(p.name) for p in paths)
    for p in sorted(paths):
        if p.suffix.lower() in SVG_SUFFIXES:
            dims = svg_intrinsic_size(p.read_text(encoding="utf-8"))
            shape = f"{dims[0]:.0f}x{dims[1]:.0f}" if dims else "unsized"
            print(f"{p.name:<{width}}  SVG   {shape:>12}  {size_str(p.stat().st_size):>9}")
            continue
        try:
            with Image.open(p) as img:
                fmt, shape = img.format or "?", f"{img.width}x{img.height}"
                mode = img.mode
        except Exception as e:  # noqa: BLE001
            print(f"{p.name:<{width}}  unreadable: {e}")
            continue
        print(f"{p.name:<{width}}  {fmt:<5} {shape:>12}  "
              f"{size_str(p.stat().st_size):>9}  {mode}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Convert and optimize images for the docs site and blog.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="SVG input requires playwright + chromium; everything else needs Pillow.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("convert", help="convert/optimize images (default target: WebP)")
    c.add_argument("inputs", nargs="+")
    c.add_argument("-o", "--out", type=Path,
                   help="output file (single input) or directory")
    c.add_argument("--out-dir", type=Path, help="output directory")
    c.add_argument("--format", choices=("webp", "png"), default="webp")
    c.add_argument("--quality", type=int, default=DEFAULT_QUALITY,
                   help=f"WebP quality 1-100 (default {DEFAULT_QUALITY})")
    c.add_argument("--max-width", type=int, default=DEFAULT_MAX_WIDTH,
                   help=f"cap width in px, never upscales (default {DEFAULT_MAX_WIDTH}; "
                        f"0 disables)")
    c.add_argument("--lossless", choices=("auto", "yes", "no"), default="auto",
                   help="auto keeps whichever of lossy/lossless is smaller")
    c.add_argument("--scale", type=int, default=2,
                   help="device pixel ratio when rasterizing SVG (default 2)")
    c.add_argument("--rasterizer", choices=("auto", "inkscape", "chromium"),
                   default="auto",
                   help="SVG backend; auto routes per file: Chromium for SVGs with "
                        "remote refs, Inkscape otherwise (default auto)")
    c.add_argument("--force", action="store_true", help="overwrite existing output")
    c.set_defaults(func=cmd_convert)

    i = sub.add_parser("info", help="report format, dimensions and size")
    i.add_argument("inputs", nargs="+")
    i.set_defaults(func=cmd_info)

    args = ap.parse_args(argv)
    if args.cmd == "convert":
        args.lossless = {"yes": "lossless", "no": "lossy", "auto": "auto"}[args.lossless]
        if not 1 <= args.quality <= 100:
            ap.error("--quality must be between 1 and 100")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

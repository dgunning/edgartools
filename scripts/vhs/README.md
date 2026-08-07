# EdgarTools demo recordings (VHS)

Reproducible terminal demo clips for the README, docs, and social — real
terminal, real Rich output, scripted with [VHS](https://github.com/charmbracelet/vhs).

Each clip is defined by a `.tape` file and renders to **both a GIF and an MP4**
from one source, so the same recording serves all three venues:

- **GIF** → README + social autoplay
- **MP4** → docs-page embeds + social with captions/voiceover added in post

No Homebrew required. Everything runs in a Docker image that bundles
`vhs` + `ttyd` + `ffmpeg` and a venv with `edgartools`.

## One-time setup

```bash
# Build the recording image (installs edgartools inside the vhs image).
docker build -t edgartools-vhs scripts/vhs
```

Rebuild only when `Dockerfile` / `pystartup.py` change or to pick up a newer
edgartools release.

## Render a clip

From the repo root (uses your `EDGAR_IDENTITY` for SEC access):

```bash
docker run --rm \
  -e EDGAR_IDENTITY="$EDGAR_IDENTITY" \
  -v "$PWD:/vhs" -w /vhs \
  edgartools-vhs scripts/vhs/hero-income-statement.tape
```

Outputs land in `scripts/vhs/out/`. Promote a final clip to the published
location when happy (the README hero lives at `docs/images/`):

```bash
cp scripts/vhs/out/hero-income-statement.gif docs/images/
```

## How it's wired

| File | Role |
|------|------|
| `Dockerfile` | `FROM` Charm's vhs image; adds a venv with `edgartools` + the prelude. |
| `pystartup.py` | Off-camera REPL prelude: `set_identity`, pre-imports, and a Rich display hook so a bare expression renders the formatted table in colour at a fixed width (`VHS_CONSOLE_WIDTH`, default 100). |
| `theme.tape` | Shared "set design" (font, size, theme, typing speed). `Source`d by every tape — edit once to restyle the series. |
| `*.tape` | One clip each. |
| `out/` | Rendered GIFs/MP4s (working dir; not the published location). |

The tape pattern: launch `python -q` **hidden** (identity + imports load from
`PYTHONSTARTUP`), `Ctrl+L` to a clean prompt, `Show`, then type the single
on-camera expression. Viewers never see boilerplate.

## Clips

| Tape | Clip | Status |
|------|------|--------|
| `hero-reel.tape` | 🌟 Hero reel — 30s tour: Company → filings → 10-K (TOC) → financials | ✅ done |
| `hero-income-statement.tape` | Focused hero — Apple income statement in three lines | ✅ done |
| `insider-form4.tape` | Insider trades — Tesla's latest Form 4 as a structured object | ✅ done |
| `quickstart-form4.tape` | Quick Start — Apple Form 4 in three beats: `get_filings("4").head(5)` → `.obj().to_dataframe([...])` → the full panel (README Quick Start) | ✅ done |
| `thirteenf-holdings.tape` | 13F holdings — `Company("BRK.A")` → top 10 (`holdings_view`) → quarter-over-quarter changes (`compare_holdings`) | ✅ done |
| `universal-find.tape` | Universal `find()` — ticker / CIK / accession, stacked | ✅ done |
| `live-filings.tape` | Live feed — `get_current_filings()` (re-render in market hours) | ✅ done |

### Adding a clip

1. Copy `hero-income-statement.tape`.
2. Change the two `Output` paths and the on-camera `Type` line.
3. Adjust `Set Height` if the output is taller/shorter than the default 720
   (the hero uses 860 because the income statement is a tall table).
4. Tune the post-`Enter` `Sleep` to cover the live SEC fetch (≈8–10s cold).

## Tips

- **`Env` must come AFTER all `Set` directives** (and after `Source`). If an
  `Env` line sits between `Source` and a `Set`, VHS silently drops the
  following `Set` commands — e.g. `Set Height` reverts to the theme default and
  the output is the wrong size. Order: `Source` → `Set ...` → `Env ...` →
  `Output`. (`thirteenf-holdings.tape` widens the Rich console via
  `Env VHS_CONSOLE_WIDTH "124"`.)
- **Lines render tall (~40px at FontSize 16).** Budget height generously — a
  ~19-line panel needs `Set Height 880`, not the ~500 the arithmetic suggests.
- **Console width must be ≤ the VHS terminal column count**, or a Rich panel's
  right border wraps and doubles. The terminal is ~119 cols at FontSize 16 /
  Width 1280; to fit a 120-col panel cleanly, widen the frame (`Set Width 1320`
  → ~122 cols) and set `Env VHS_CONSOLE_WIDTH "120"`. Measure cols by running
  `python3 -c "import shutil; print(shutil.get_terminal_size().columns)"` inside
  a throwaway tape.
- **Frame height = fit the output, no scroll.** If a table scrolls, its header
  is gone from the final hold frame. Raise `Set Height` until the whole result
  fits (≈21.6px per line at FontSize 18, plus padding).
- **Determinism.** `pystartup.py` pins the Rich console width so layout is
  identical run to run regardless of PTY size. SEC values change over time —
  re-render to refresh numbers.
- **Inspect a frame** without opening the video:
  `docker run --rm -v "$PWD:/vhs" -w /vhs --entrypoint ffmpeg edgartools-vhs \
   -sseof -2.5 -i scripts/vhs/out/<clip>.mp4 -frames:v 1 -update 1 -y /tmp/f.png`

# HERO REEL — the 30-second tour of EdgarTools.
# Four beats, one company, escalating payoff:
#   1. Company(...)               → company panel
#   2. .get_filings("10-K")       → filings table
#   3. .latest_tenk               → the 10-K as a structured object (TOC tree)
#   4. .income_statement          → the financials
#
# Render (from repo root):
#   docker run --rm -e EDGAR_IDENTITY="$EDGAR_IDENTITY" \
#       -v "$PWD:/vhs" -w /vhs edgartools-vhs scripts/vhs/hero-reel.tape

Source scripts/vhs/theme.tape

# Snappier typing for a montage; taller frame so the income statement (the
# payoff, shown last on a clean screen) is fully visible on the hold.
Set TypingSpeed 55ms
Set Height 820

Output scripts/vhs/out/hero-reel.gif
Output scripts/vhs/out/hero-reel.mp4

# --- Off-camera: launch REPL (identity + imports via PYTHONSTARTUP), clean prompt. ---
Hide
Type "python -q"
Enter
Sleep 6s
Ctrl+L
Show

# --- Beat 1: start with a ticker. ---
Sleep 700ms
Type "company = Company('AAPL')"
Enter
Sleep 400ms
Type "company"
Enter
Sleep 3s
Sleep 1500ms
Ctrl+L

# --- Beat 2: browse its filings. ---
Sleep 400ms
Type "company.get_filings(form='10-K').head(6)"
Enter
Sleep 3s
Sleep 1800ms
Ctrl+L

# --- Beat 3: the latest 10-K as a structured object — full table of contents. ---
Sleep 400ms
Type "tenk = company.latest_tenk"
Enter
Sleep 2500ms
Type "tenk"
Enter
Sleep 3500ms
Sleep 1800ms
Ctrl+L

# --- Beat 4: the financials (payoff — hold long). ---
Sleep 400ms
Type "tenk.income_statement"
Enter
Sleep 4s
Sleep 3500ms

# HERO CLIP — "Apple's income statement in three lines."
# The canonical README/social demo: tiny input, fully-formatted financials.
#
# Render (from repo root):
#   docker run --rm -e EDGAR_IDENTITY="$EDGAR_IDENTITY" \
#       -v "$PWD:/vhs" -w /vhs edgartools-vhs scripts/vhs/hero-income-statement.tape

Source scripts/vhs/theme.tape

# The income statement is a tall table — give this clip a taller frame so the
# full statement (title through EPS) is visible on the final hold, not scrolled.
Set Height 860

Output scripts/vhs/out/hero-income-statement.gif
Output scripts/vhs/out/hero-income-statement.mp4

# --- Off-camera prelude: launch the REPL (identity + imports + Rich hook
#     come from PYTHONSTARTUP), then clear to a pristine prompt. ---
Hide
Type "python -q"
Enter
Sleep 6s
Ctrl+L
Show

# --- On camera: one expression, a full income statement. ---
Sleep 800ms
Type@90ms "Company('AAPL').get_financials().income_statement()"
Sleep 1s
Enter
Sleep 9s

# Hold the final frame so the GIF reads at a glance and loops cleanly.
Sleep 2500ms

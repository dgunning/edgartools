# CLIP — 13F institutional holdings.
# Berkshire Hathaway's latest 13F, top 10 positions by value — the iconic
# portfolio (Apple, Amex, Coca-Cola, BofA, Chevron...) in one clean frame.
#
# Uses holdings_view(10) (value-sorted, deduped) instead of the raw object,
# which would render ~98 alphabetical rows and scroll the headline off-screen.
# Env widens the Rich console to 124 so issuer names and dollar values aren't
# truncated; FontSize 16 keeps that width inside the standard 1280px frame.
#
# Render:
#   docker run --rm -e EDGAR_IDENTITY="$EDGAR_IDENTITY" \
#       -v "$PWD:/vhs" -w /vhs edgartools-vhs scripts/vhs/thirteenf-holdings.tape

Source scripts/vhs/theme.tape
Set FontSize 16
Set Height 880
Env VHS_CONSOLE_WIDTH "124"

Output scripts/vhs/out/thirteenf-holdings.gif
Output scripts/vhs/out/thirteenf-holdings.mp4

# Load Berkshire's latest 13F off-camera so the reveal is instant and the panel
# (title + header + 10 rows) fits without the load line pushing it off-screen.
Hide
Type "python -q"
Enter
Sleep 6s
Type "brk = Company('BRK.B').get_filings(form='13F-HR').latest().obj()"
Enter
Sleep 7s
Ctrl+L
Show

# Reveal the top holdings by value.
Sleep 800ms
Type@80ms "brk.holdings_view(10)"
Sleep 600ms
Enter
Sleep 2s
Sleep 3500ms

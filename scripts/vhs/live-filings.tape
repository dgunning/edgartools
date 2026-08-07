# CLIP — Live filing feed.
# What's hitting EDGAR right now: get_current_filings() with live accepted
# timestamps.
#
# NOTE: content is live and time-dependent. Render during US market hours for a
# diverse mix of forms; off-hours the feed can be dominated by a single filer.
#
# Render:
#   docker run --rm -e EDGAR_IDENTITY="$EDGAR_IDENTITY" \
#       -v "$PWD:/vhs" -w /vhs edgartools-vhs scripts/vhs/live-filings.tape

Source scripts/vhs/theme.tape
Set Height 720

Output scripts/vhs/out/live-filings.gif
Output scripts/vhs/out/live-filings.mp4

Hide
Type "python -q"
Enter
Sleep 6s
Ctrl+L
Show

Sleep 800ms
Type@80ms "get_current_filings()"
Sleep 1s
Enter
Sleep 9s
Sleep 3s

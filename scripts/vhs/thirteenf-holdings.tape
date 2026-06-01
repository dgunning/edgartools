# CLIP — 13F institutional holdings.
# Berkshire Hathaway's latest 13F: the report summary (manager, holdings count,
# total value) and the full portfolio, scrolling through 90 positions.
#
# Render:
#   docker run --rm -e EDGAR_IDENTITY="$EDGAR_IDENTITY" \
#       -v "$PWD:/vhs" -w /vhs edgartools-vhs scripts/vhs/thirteenf-holdings.tape

Source scripts/vhs/theme.tape
Set Height 720

Output scripts/vhs/out/thirteenf-holdings.gif
Output scripts/vhs/out/thirteenf-holdings.mp4

Hide
Type "python -q"
Enter
Sleep 6s
Ctrl+L
Show

Sleep 800ms
Type@80ms "Company('BRK.B').get_filings(form='13F-HR').latest().obj()"
Sleep 1s
Enter
Sleep 6s
Sleep 3s

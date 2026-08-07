# CLIP — Insider trading (Form 4).
# Tesla's latest Form 4 as a structured object: insider, role, and every
# common-stock + derivative transaction with prices and values.
#
# Render:
#   docker run --rm -e EDGAR_IDENTITY="$EDGAR_IDENTITY" \
#       -v "$PWD:/vhs" -w /vhs edgartools-vhs scripts/vhs/insider-form4.tape

Source scripts/vhs/theme.tape
Set Height 760

Output scripts/vhs/out/insider-form4.gif
Output scripts/vhs/out/insider-form4.mp4

Hide
Type "python -q"
Enter
Sleep 6s
Ctrl+L
Show

Sleep 800ms
Type@80ms "Company('TSLA').get_filings(form='4').latest().obj()"
Sleep 1s
Enter
Sleep 5s
Sleep 3s

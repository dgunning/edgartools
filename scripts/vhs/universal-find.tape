# CLIP — One function, any identifier.
# find() resolves a ticker, a CIK, and an accession number — stacked so the
# three results sit on screen together: ticker and CIK land on the same
# company, the accession lands on the filing.
#
# Render:
#   docker run --rm -e EDGAR_IDENTITY="$EDGAR_IDENTITY" \
#       -v "$PWD:/vhs" -w /vhs edgartools-vhs scripts/vhs/universal-find.tape

Source scripts/vhs/theme.tape
Set TypingSpeed 65ms
Set Height 820

Output scripts/vhs/out/universal-find.gif
Output scripts/vhs/out/universal-find.mp4

Hide
Type "python -q"
Enter
Sleep 6s
Ctrl+L
Show

# Ticker
Sleep 700ms
Type "find('AAPL')"
Enter
Sleep 2500ms

# CIK -> same company
Type "find(320193)"
Enter
Sleep 2500ms

# Accession number -> the filing (cold filing fetch can be slow)
Type "find('0000320193-25-000079')"
Enter
Sleep 8s
Sleep 2500ms

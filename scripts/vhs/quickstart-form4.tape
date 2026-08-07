# CLIP — Quick Start: Form 4 insider trades, three beats:
#   1. Company("AAPL").get_filings(form="4").head(5)         → recent Form 4s
#   2. filings.latest().obj().to_dataframe([...])            → transactions as data
#   3. form4                                                 → the full structured panel
#
# Everything fits the default 100-col Rich console: the Form 4 panel caps ~90
# cols, the filings table ~100, the focused DataFrame ~48. Height 920 fits the
# tallest single beat (the ~18-line panel plus the typed line and prompt).
#
# Render:
#   docker run --rm -e EDGAR_IDENTITY="$EDGAR_IDENTITY" \
#       -v "$PWD:/vhs" -w /vhs edgartools-vhs scripts/vhs/quickstart-form4.tape

Source scripts/vhs/theme.tape
Set Height 560

Output scripts/vhs/out/quickstart-form4.gif
Output scripts/vhs/out/quickstart-form4.mp4

# Warm the lookup, the Form 4 object, and the DataFrame off-camera so every
# on-screen reveal is instant.
Hide
Type "python -q"
Enter
Sleep 6s
Type "filings = Company('AAPL').get_filings(form='4')"
Enter
Sleep 4s
Type "form4 = filings.latest().obj()"
Enter
Sleep 4s
Type "_ = form4.to_dataframe()"
Enter
Sleep 2s
Ctrl+L
Show

# Beat 1: recent Form 4 filings.
Sleep 800ms
Type@80ms "filings = Company('AAPL').get_filings(form='4')"
Sleep 400ms
Enter
Sleep 600ms
Type@80ms "filings.head(5)"
Sleep 400ms
Enter
Sleep 3s
Ctrl+L

# Beat 2: the transactions as data.
Sleep 500ms
Type@80ms "form4 = filings.latest().obj()"
Sleep 400ms
Enter
Sleep 1200ms
Type@80ms "form4.to_dataframe()[['Insider','Code','Shares','Price','Value']]"
Sleep 400ms
Enter
Sleep 3s
Ctrl+L

# Beat 3: the full structured object.
Sleep 500ms
Type@80ms "form4"
Sleep 400ms
Enter
Sleep 3s
Sleep 3500ms

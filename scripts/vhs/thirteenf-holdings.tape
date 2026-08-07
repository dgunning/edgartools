# CLIP — 13F institutional holdings, three beats:
#   1. Company("BRK.A")          → the company panel
#   2. ...obj().holdings_view(10) → top 10 positions by value
#   3. ...compare_holdings(8)     → what changed since last quarter (NEW /
#                                   CLOSED / INCREASED / DECREASED + deltas)
#
# The comparison is a wide 10-column table, so the clip uses a wider frame and
# a 160-col Rich console (compare is clean at 160; holdings spreads to fill it;
# the company panel caps ~85 cols and sits compact on the left).
#
# Width rule: the Rich console (160) must be <= the VHS terminal column count
# or a panel's right border wraps and doubles. At FontSize 16 a 1760px frame
# gives ~165 cols. Env must follow all Set directives (else Set is dropped).
#
# Render:
#   docker run --rm -e EDGAR_IDENTITY="$EDGAR_IDENTITY" \
#       -v "$PWD:/vhs" -w /vhs edgartools-vhs scripts/vhs/thirteenf-holdings.tape

Source scripts/vhs/theme.tape
Set FontSize 16
Set Width 1760
Set Height 880
Env VHS_CONSOLE_WIDTH "160"

Output scripts/vhs/out/thirteenf-holdings.gif
Output scripts/vhs/out/thirteenf-holdings.mp4

# Warm the lookup, the 13F object, and the prior-quarter comparison off-camera
# so every on-screen reveal is instant.
Hide
Type "python -q"
Enter
Sleep 6s
Type "company = Company('BRK.A')"
Enter
Sleep 3s
Type "thirteenf = company.get_filings(form='13F-HR').latest().obj()"
Enter
Sleep 7s
Type "_ = thirteenf.compare_holdings(8)"
Enter
Sleep 8s
Ctrl+L
Show

# Beat 1: create the company.
Sleep 800ms
Type@80ms "company = Company('BRK.A')"
Sleep 400ms
Enter
Sleep 400ms
Type@80ms "company"
Sleep 400ms
Enter
Sleep 3s
Ctrl+L

# Beat 2: top holdings by value.
Sleep 500ms
Type@80ms "thirteenf = company.get_filings(form='13F-HR').latest().obj()"
Sleep 400ms
Enter
Sleep 1500ms
Type@80ms "thirteenf.holdings_view(10)"
Sleep 400ms
Enter
Sleep 3s
Ctrl+L

# Beat 3: what changed since last quarter.
Sleep 500ms
Type@80ms "thirteenf.compare_holdings(8)"
Sleep 400ms
Enter
Sleep 3s
Sleep 3500ms

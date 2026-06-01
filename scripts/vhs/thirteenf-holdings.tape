# CLIP — 13F institutional holdings, two beats:
#   1. holdings_view(10)    → Berkshire's top 10 positions by value
#   2. compare_holdings(8)  → what changed since last quarter (NEW / CLOSED /
#                             INCREASED / DECREASED, with per-position deltas)
#
# Both views render value-sorted/deduped (not the raw ~98-row object). The
# comparison is a wide 10-column table, so this clip uses a wider frame and a
# 160-col Rich console; holdings_view simply spreads to fill it.
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

# Load the 13F and warm the prior-quarter comparison off-camera so both reveals
# are instant (compare_holdings fetches the previous quarter's filing).
Hide
Type "python -q"
Enter
Sleep 6s
Type "brk = Company('BRK.B').get_filings(form='13F-HR').latest().obj()"
Enter
Sleep 7s
Type "_ = brk.compare_holdings(8)"
Enter
Sleep 8s
Ctrl+L
Show

# Beat 1: top holdings by value.
Sleep 800ms
Type@80ms "brk.holdings_view(10)"
Sleep 600ms
Enter
Sleep 3s
Ctrl+L

# Beat 2: what changed since last quarter.
Sleep 500ms
Type@80ms "brk.compare_holdings(8)"
Sleep 600ms
Enter
Sleep 3s
Sleep 3500ms
